"""
CuPy-based PoW miner (double SHA-256 over UTF-8 bytes of "challenge + nonce(decimal)")

Requirements:
  - NVIDIA GPU with CUDA
  - Python packages: cupy (pip install cupy-cuda12x)

API:
  - mine_gpu(challenge: str, threshold_bits: int, start_nonce: int, total_nonces: int,
             blocks: int = 256, threads_per_block: int = 256, iters_per_thread: int = 64) -> dict | None

Notes:
  - baseline/threshold_bits 为当前基线，批内收集最优（>= baseline）并返回
  - 返回 {'nonce', 'hash_hex', 'leading_zero_bits} 或 None
"""

from __future__ import annotations

import math
from typing import Optional, Dict
import threading

import numpy as np
import cupy as cp


CUDA_SRC = r"""
extern "C" {

__device__ __forceinline__ unsigned int ROTR(unsigned int x, unsigned int n){
    return (x >> n) | (x << (32 - n));
}
__device__ __forceinline__ unsigned int Ch(unsigned int x, unsigned int y, unsigned int z){
    return (x & y) ^ (~x & z);
}
__device__ __forceinline__ unsigned int Maj(unsigned int x, unsigned int y, unsigned int z){
    return (x & y) ^ (x & z) ^ (y & z);
}
__device__ __forceinline__ unsigned int BSIG0(unsigned int x){
    return ROTR(x,2) ^ ROTR(x,13) ^ ROTR(x,22);
}
__device__ __forceinline__ unsigned int BSIG1(unsigned int x){
    return ROTR(x,6) ^ ROTR(x,11) ^ ROTR(x,25);
}
__device__ __forceinline__ unsigned int SSIG0(unsigned int x){
    return ROTR(x,7) ^ ROTR(x,18) ^ (x >> 3);
}
__device__ __forceinline__ unsigned int SSIG1(unsigned int x){
    return ROTR(x,17) ^ ROTR(x,19) ^ (x >> 10);
}

__device__ __forceinline__ void sha256_compress(const unsigned char* chunk, unsigned int* state){
    const unsigned int Kc[64] = {
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
    };
    unsigned int w[64];
    #pragma unroll
    for (int i=0;i<16;i++){
        int j=i*4;
        w[i] = ( (unsigned int)chunk[j] << 24 ) | ( (unsigned int)chunk[j+1] << 16 ) | ( (unsigned int)chunk[j+2] << 8 ) | ( (unsigned int)chunk[j+3] );
    }
    #pragma unroll
    for (int i=16;i<64;i++){
        w[i] = (w[i-16] + SSIG0(w[i-15]) + w[i-7] + SSIG1(w[i-2]));
    }
    unsigned int a=state[0],b=state[1],c=state[2],d=state[3],e=state[4],f=state[5],g=state[6],h=state[7];
    #pragma unroll
    for (int i=0;i<64;i++){
        unsigned int t1 = h + BSIG1(e) + Ch(e,f,g) + Kc[i] + w[i];
        unsigned int t2 = BSIG0(a) + Maj(a,b,c);
        h=g; g=f; f=e; e=d + t1; d=c; c=b; b=a; a=t1+t2;
    }
    state[0]+=a; state[1]+=b; state[2]+=c; state[3]+=d;
    state[4]+=e; state[5]+=f; state[6]+=g; state[7]+=h;
}

__device__ __forceinline__ void sha256(const unsigned char* msg, int msg_len, unsigned char* out32){
    unsigned int state[8] = {0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    int full = msg_len / 64;
    for (int b=0;b<full;b++) sha256_compress(msg + b*64, state);
    int rem = msg_len % 64;
    unsigned char tail[128];
    for (int i=0;i<rem;i++) tail[i] = msg[full*64 + i];
    tail[rem] = 0x80; int rem_plus = rem + 1;
    unsigned long long total_bits = (unsigned long long)msg_len * 8ULL;
    if (rem_plus <= 56){
        for (int i=rem_plus;i<56;i++) tail[i]=0;
        for (int i=0;i<8;i++) tail[56+i] = (unsigned char)((total_bits >> (8*(7-i))) & 0xff);
        sha256_compress(tail, state);
    } else {
        for (int i=rem_plus;i<64;i++) tail[i]=0;
        sha256_compress(tail, state);
        for (int i=0;i<56;i++) tail[i]=0;
        for (int i=0;i<8;i++) tail[56+i] = (unsigned char)((total_bits >> (8*(7-i))) & 0xff);
        sha256_compress(tail, state);
    }
    for (int i=0;i<8;i++){
        out32[i*4+0] = (unsigned char)((state[i] >> 24) & 0xff);
        out32[i*4+1] = (unsigned char)((state[i] >> 16) & 0xff);
        out32[i*4+2] = (unsigned char)((state[i] >> 8) & 0xff);
        out32[i*4+3] = (unsigned char)((state[i] >> 0) & 0xff);
    }
}

__device__ __forceinline__ void double_sha256(const unsigned char* msg, int msg_len, unsigned char* out32){
    unsigned char t[32];
    sha256(msg, msg_len, t);
    sha256(t, 32, out32);
}

__device__ __forceinline__ int count_lz_bits(const unsigned char* h32){
    int bits=0;
    for (int i=0;i<32;i++){
        unsigned char b = h32[i];
        for (int j=7;j>=0;j--){
            if ((b >> j) & 1) return bits;
            bits++;
        }
    }
    return bits;
}

__global__ void pow_kernel(const unsigned char* __restrict__ challenge, const int chal_len,
                const unsigned long long start_nonce, const unsigned long long total,
                const int baseline_bits,
                const int iters_per_thread,
                int* __restrict__ best_lz,
                unsigned long long* __restrict__ best_nonce,
                unsigned char* __restrict__ best_hash) {
    unsigned long long idx = (unsigned long long)(blockIdx.x) * (unsigned long long)(blockDim.x) + (unsigned long long)(threadIdx.x);
    unsigned long long grid = (unsigned long long)(gridDim.x) * (unsigned long long)(blockDim.x);
    unsigned long long end_nonce = start_nonce + total;

    unsigned long long base = start_nonce + idx * (unsigned long long)iters_per_thread;
    while (base < end_nonce){
        for (int step=0; step<iters_per_thread; ++step){
            unsigned long long nonce = base + (unsigned long long)step;
            if (nonce >= end_nonce) break;

            unsigned char buf[128];
            for (int i=0;i<chal_len;i++) buf[i] = challenge[i];
            unsigned long long n = nonce; int tlen=0; unsigned char tmp[20];
            if (n==0){ buf[chal_len]='0'; tlen=1; }
            else {
                while (n>0 && tlen<20){ tmp[tlen] = (unsigned char)('0' + (n%10ULL)); n/=10ULL; tlen++; }
                for (int k=0;k<tlen;k++) buf[chal_len+k] = tmp[tlen-1-k];
            }
            int msg_len = chal_len + tlen;
            unsigned char h[32];
            double_sha256(buf, msg_len, h);
            int lz = count_lz_bits(h);
            if (lz >= baseline_bits){
                int prev = atomicMax(best_lz, lz);
                if (lz > prev){
                    *best_nonce = nonce;
                    for (int i=0;i<32;i++) best_hash[i] = h[i];
                }
            }
        }
        base += grid * (unsigned long long)iters_per_thread;
    }
}

} // extern "C"
"""

_raw_mod = cp.RawModule(code=CUDA_SRC, name_expressions=("pow_kernel",))
_pow_kernel = _raw_mod.get_function("pow_kernel")


def _to_bytes(s: str) -> np.ndarray:
    return np.frombuffer(s.encode('utf-8'), dtype=np.uint8)


def _bytes_to_hex(b: np.ndarray) -> str:
    return ''.join(f'{x:02x}' for x in b.tolist())


def mine_gpu(challenge: str,
             threshold_bits: int,
             start_nonce: int,
             total_nonces: int,
             blocks: int = 256,
             threads_per_block: int = 256,
             iters_per_thread: int = 64) -> Optional[Dict]:
    if threshold_bits < 0 or threshold_bits > 256:
        raise ValueError('threshold_bits must be in [0, 256]')

    # device count
    try:
        ndev = cp.cuda.runtime.getDeviceCount()
    except cp.cuda.runtime.CUDARuntimeError:
        ndev = 0
    if ndev <= 0:
        raise RuntimeError('CUDA device is required (no CPU fallback).')

    chal = _to_bytes(challenge)
    if chal.size > 96:
        raise ValueError('challenge too long (max 96 bytes for this demo)')

    total = int(total_nonces)
    if total <= 0:
        raise ValueError('total_nonces must be > 0')

    grid = blocks * threads_per_block
    if total < grid:
        blocks = max(1, math.ceil(total / threads_per_block))

    devices = list(range(ndev))
    if len(devices) == 1:
        with cp.cuda.Device(devices[0]):
            d_chal = cp.asarray(chal.astype(np.uint8))
            d_best_lz = cp.asarray(np.array([int(threshold_bits)], dtype=np.int32))
            d_best_nonce = cp.asarray(np.zeros(1, dtype=np.uint64))
            d_best_hash = cp.asarray(np.zeros(32, dtype=np.uint8))

            _pow_kernel((blocks,), (threads_per_block,),
                        (d_chal, np.int32(chal.size),
                         np.uint64(start_nonce), np.uint64(total),
                         np.int32(threshold_bits), np.int32(iters_per_thread),
                         d_best_lz, d_best_nonce, d_best_hash))
            cp.cuda.runtime.deviceSynchronize()

            best_lz = int(d_best_lz.get()[0])
            if best_lz > int(threshold_bits):
                return {
                    'nonce': int(d_best_nonce.get()[0]),
                    'hash_hex': _bytes_to_hex(d_best_hash.get()),
                    'leading_zero_bits': best_lz,
                }
            return None

    # multi-gpu split
    ng = len(devices)
    chunk = total // ng
    rem = total % ng

    per_dev_best_lz = [int(threshold_bits)] * ng
    per_dev_best_nonce = [0] * ng
    per_dev_best_hash: list[bytes] = [bytes(32)] * ng

    def worker(dev_idx: int, dev_start: int, dev_total: int):
        if dev_total <= 0:
            return
        try:
            with cp.cuda.Device(devices[dev_idx]):
                d_chal = cp.asarray(chal.astype(np.uint8))
                d_best_lz = cp.asarray(np.array([int(threshold_bits)], dtype=np.int32))
                d_best_nonce = cp.asarray(np.zeros(1, dtype=np.uint64))
                d_best_hash = cp.asarray(np.zeros(32, dtype=np.uint8))

                _pow_kernel((blocks,), (threads_per_block,),
                            (d_chal, np.int32(chal.size),
                             np.uint64(dev_start), np.uint64(dev_total),
                             np.int32(threshold_bits), np.int32(iters_per_thread),
                             d_best_lz, d_best_nonce, d_best_hash))
                cp.cuda.runtime.deviceSynchronize()

                per_dev_best_lz[dev_idx] = int(d_best_lz.get()[0])
                per_dev_best_nonce[dev_idx] = int(d_best_nonce.get()[0])
                per_dev_best_hash[dev_idx] = bytes(d_best_hash.get())
        except Exception:
            pass

    threads = []
    cur = int(start_nonce)
    for i in range(ng):
        size = chunk + (1 if i < rem else 0)
        t = threading.Thread(target=worker, args=(i, cur, size))
        threads.append(t)
        cur += size
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    best_idx = max(range(ng), key=lambda i: per_dev_best_lz[i])
    best_lz = per_dev_best_lz[best_idx]
    if best_lz > int(threshold_bits):
        return {
            'nonce': per_dev_best_nonce[best_idx],
            'hash_hex': per_dev_best_hash[best_idx].hex(),
            'leading_zero_bits': best_lz,
        }
    return None


