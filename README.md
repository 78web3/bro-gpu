# 前置条件

**有 N 卡，需要安装驱动**

# 使用说明

## 步骤一、生成 nonce 和 hexhash

https://bro.charms.dev/

在页面的钱包上找到两个参数：

![params](./asserts/params.png "params")

使用python程序，先安装依赖：

```bash
pip install numpy cupy-cuda12x Flask
```

然后运行程序：

```bash
python pow_cli.py --txid {txid} --vout {vout} --stream
```

这样子程序就会一直输出你的结果，注意自己用 Transaction ID 和 Output Index 替换命令中的 txid 和 vout

直到难度你满意之后就可以停下了

## 替换计算结果

在页面上点击一次 start，然后 stop

在页面中按 F12，在 devtools 中找到 Application - LocalStorage

找到 miningProgress，其右边对应的 value，这是一个 json，把其复制出来，将刚才用显卡计算得到的结果中的 best 的 nonce、hash_hex、leading_zero_bits 替换掉复制出来的 json 中对应的数据，再将结果粘贴回去

刷新页面即可继续

## 代码操作 localstorage

在 devtools 的 console 页面输入下面代码：

```
const best =  {"nonce": 287286380054, "hash_hex": "0000000000786540680ad450e011574b384704ab7a24f41344bb053d22020dc7", "leading_zero_bits": 41}
const result = {
  "nonce": best.nonce,
  "hash": best.hash_hex,
  "bestHash": best.hash_hex,
  "bestNonce": best.nonce,
  "bestLeadingZeros": best.leading_zero_bits,
  "timestamp": Date.now(),
  "completed": true
}
localStorage.setItem("miningResult", JSON.stringify(result))
```

**注意一定要自己替换代码计算出来的 best 的部分**