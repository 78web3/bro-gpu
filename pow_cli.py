"""
命令行工具：GPU PoW 挖矿（Numba CUDA，仅 GPU，无 CPU 回退）

用法 1（阈值模式，一次性扫描）:
  python pow_cli.py --txid <txid> --vout <vout> --threshold 20 \
      --start 0 --count 5000000 --blocks 256 --tpb 256

用法 2（持续模式，不设阈值，发现更优即打印一次）:
  python pow_cli.py --txid <txid> --vout <vout> --stream \
      --start 0 --batch 5000000 --baseline 0 --blocks 256 --tpb 256
"""

import json
import argparse
try:
    # Prefer CuPy backend
    from cupy_pow import mine_gpu
except Exception:
    # Fallback to Numba backend if CuPy isn't available
    from gpu_pow import mine_gpu

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--txid', help='交易ID')
    p.add_argument('--vout', type=int, help='输出索引')
    p.add_argument('--threshold', '-t', type=int, help='前导零位阈值（与 --stream 互斥）')
    p.add_argument('--stream', action='store_true', help='持续模式：不设阈值，发现更优即打印一次')
    p.add_argument('--start', type=int, default=0, help='起始 nonce')
    p.add_argument('--count', type=int, default=1_000_000, help='一次性扫描 nonce 数（阈值模式）')
    p.add_argument('--batch', type=int, default=1_000_000, help='每轮批大小（持续模式）')
    p.add_argument('--baseline', type=int, default=0, help='持续模式初始基线（前导零位）')
    p.add_argument('--blocks', type=int, default=256, help='CUDA blocks 数')
    p.add_argument('--tpb', type=int, default=256, help='每个 block 的线程数 (threads per block)')
    # HTTP 服务
    p.add_argument('--serve', action='store_true', help='启动HTTP服务')
    p.add_argument('--host', default='0.0.0.0', help='HTTP服务监听地址')
    p.add_argument('--port', type=int, default=8080, help='HTTP服务端口')
    args = p.parse_args()

    # HTTP 服务模式
    if args.serve:
        # 配置默认参数
        default_blocks = args.blocks
        default_tpb = args.tpb
        default_start = args.start
        default_count = args.count

        # 结果缓存与全局排他锁（同一时间仅允许一个计算，无论key）
        cache_file = 'pow_results_cache.json'
        busy_lock = threading.Lock()
        state_lock = threading.Lock()
        current_key = {'value': None}
        cache = {}      # key -> {challenge, params, result, ts}

        def make_key(txid, vout, threshold):
            return f"{txid}:{vout}:{threshold}"

        def load_cache():
            nonlocal cache
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
            except Exception:
                cache = {}

        def save_cache():
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache, f, ensure_ascii=False)
            except Exception:
                pass

        load_cache()

        class Handler(BaseHTTPRequestHandler):
            def _json(self, code, obj):
                body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
                self.send_response(code)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    raw = self.rfile.read(length) if length > 0 else b''
                    try:
                        data = json.loads(raw.decode('utf-8')) if raw else {}
                    except Exception:
                        return self._json(400, {'error': 'bad_request', 'message': 'invalid json'})

                    txid = (data.get('txid') or '').strip()
                    vout = data.get('vout')
                    threshold = data.get('threshold')
                    if not txid or not isinstance(vout, int) or threshold is None:
                        return self._json(400, {'error': 'bad_request', 'message': 'required: txid(string), vout(int), threshold(int)'})

                    # 固定参数（直到命中为止，不接受覆盖）
                    start = default_start
                    count = default_count
                    blocks = default_blocks
                    tpb = default_tpb

                    challenge = f"{txid}:{vout}"
                    key = make_key(txid, vout, int(threshold))

                    # 已有缓存则直接返回
                    if key in cache and isinstance(cache[key], dict) and 'result' in cache[key]:
                        return self._json(200, cache[key])

                    # 全局排他：任意时刻只允许一个计算，其它返回423
                    if not busy_lock.acquire(blocking=False):
                        # 判断是否同一个key
                        with state_lock:
                            running_key = current_key.get('value')
                        if running_key == key:
                            return self._json(423, {
                                'status': 'running',
                                'message': 'the same job is currently running; please retry later or check cache',
                                'key': key,
                                'hint': 'server caches results by key (txid:vout:threshold)'
                            })
                        return self._json(423, {
                            'status': 'busy',
                            'message': 'another job is running; please retry later',
                            'current_key': running_key
                        })
                    try:
                        with state_lock:
                            current_key['value'] = key
                        current = start
                        batches_run = 0
                        print(f"[JOB START] key={key} challenge={challenge} threshold={int(threshold)} start={start} count={count} blocks={blocks} tpb={tpb}")
                        while True:
                            res = mine_gpu(
                                challenge=challenge,
                                threshold_bits=int(threshold),
                                start_nonce=current,
                                total_nonces=count,
                                blocks=blocks,
                                threads_per_block=tpb,
                            )
                            batches_run += 1
                            if res and res.get('leading_zero_bits', 0) >= int(threshold):
                                try:
                                    print(f"[JOB DONE] key={key} batches_run={batches_run} nonce={res.get('nonce')} lz={res.get('leading_zero_bits')}")
                                except Exception:
                                    pass
                                cache[key] = {
                                    'status': 'done',
                                    'challenge': challenge,
                                    'params': {'txid': txid, 'vout': vout, 'threshold': int(threshold)},
                                    'result': res,
                                    'batches_run': batches_run
                                }
                                save_cache()
                                try:
                                    return self._json(200, cache[key])
                                except Exception:
                                    return
                            current += count
                            # 无上限：持续批量推进直到命中
                    finally:
                        if busy_lock.locked():
                            busy_lock.release()
                        with state_lock:
                            current_key['value'] = None
                        try:
                            print(f"[JOB RELEASE] key={key}")
                        except Exception:
                            pass
                except Exception as e:
                    return self._json(500, {'error': 'internal', 'message': str(e)})

        httpd = ThreadingHTTPServer((args.host, args.port), Handler)
        print(f"HTTP server listening on http://{args.host}:{args.port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.server_close()
        return

    challenge = f"{args.txid}:{args.vout}"

    if args.stream:
        # 持续模式：不断以当前 baseline 为阈值滚动搜索，发现 >= baseline 即打印并提升 baseline
        baseline = int(args.baseline)
        current = int(args.start)
        batch = int(args.batch)
        while True:
            res = mine_gpu(
                challenge=challenge,
                threshold_bits=baseline,
                start_nonce=current,
                total_nonces=batch,
                blocks=args.blocks,
                threads_per_block=args.tpb,
            )
            if res and res.get('leading_zero_bits', 0) >= baseline:
                baseline = int(res['leading_zero_bits'])
                print(json.dumps({
                    'mode': 'stream',
                    'challenge': challenge,
                    'best': res,
                    'baseline': baseline
                }, ensure_ascii=False), flush=True)
            current += batch
    else:
        if args.threshold is None:
            raise SystemExit('缺少 --threshold 或使用 --stream 模式')
        res = mine_gpu(
            challenge=challenge,
            threshold_bits=args.threshold,
            start_nonce=args.start,
            total_nonces=args.count,
            blocks=args.blocks,
            threads_per_block=args.tpb,
        )
        print(json.dumps({
            'mode': 'threshold',
            'challenge': challenge,
            'threshold': args.threshold,
            'result': res
        }, ensure_ascii=False))


if __name__ == '__main__':
    main()


