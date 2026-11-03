# 副图公式（语法与示例）

K 线下面默认就有**成交量**和 **MACD(12,26,9)** 两块副图；再往下可以自己加，
**最多加 3 个**公式副图（加满后按钮会变灰，删掉一个就能再加）。

公式怎么算到图上：**你把公式写出来，后端算成一条序列画出来。**
所有计算都只用「当前已经走到的那些 K 线」，所以副图同样不会偷看未来。

> 这里只放**公开的教科书式示例**。你自己的战法指标不要写进仓库，
> 写进下面说的 `formulas.json` 就行（那个文件不进 git）。

## 公式存在哪：`formulas.json`

副图列表不写死在代码里，而是读项目根目录的 **`formulas.json`**：

```json
{
  "items": [
    {"名称": "价格偏离 20 日线（%）", "公式": "(CLOSE - MA(CLOSE,20)) / MA(CLOSE,20) * 100"},
    {"名称": "量比", "公式": "VOLUME / MA(VOLUME,5)", "说明": "1 以上=放量"}
  ]
}
```

- **至少要有 `名称` 和 `公式` 两个值**，`说明` 可选（会显示成下拉项的悬浮提示）
- 英文键 `name` / `formula` / `hint` 也认
- 改完这个文件，**刷新页面就生效**，不用重启服务
- 没有 `formulas.json` 时用仓库里的 `formulas.example.json`（公开示例）

### `formulas.json` 不进 git

这个文件可能写着你自己私有的指标，所以已在 `.gitignore` 里。
界面上的「存为我的公式」会把当前面板的公式（和名称）写进它，下次打开还在；
也可以直接用记事本改。想放别处：`set KLINE_FORMULAS=.\my-formulas.json`

## 语法

一行表达式，四则运算 + 括号，支持下面这些名字和函数：

| 名字 | 含义 |
|---|---|
| `CLOSE` / `C` | 收盘价 |
| `OPEN` / `O` | 开盘价 |
| `HIGH` / `H` | 最高价 |
| `LOW` / `L` | 最低价 |
| `VOLUME` / `V` | 成交量 |
| `AMOUNT` | 成交额 |

| 函数 | 说明 |
|---|---|
| `MA(X,N)` | N 根简单均线 |
| `EMA(X,N)` | N 根指数均线 |
| `REF(X,N)` | 往前 N 根的值 |
| `SUM(X,N)` | N 根求和 |
| `HHV(X,N)` / `LLV(X,N)` | N 根最高 / 最低 |
| `STD(X,N)` | N 根标准差（总体口径） |
| `MAX(a,b)` / `MIN(a,b)` | 逐根取大 / 取小 |
| `ABS(a)` | 绝对值 |
| `CROSS(a,b)` | a 上穿 b 记 1，否则 0 |

运算优先级和数学一致：`* /` 先于 `+ -`，括号最高；`-` 可以做负号。
`X/0` 得到空值（图上断开），不会崩。

## 示例（`klinecamp/formulas.py` 里的六条）

```text
价格偏离 20 日均线%   (CLOSE - MA(CLOSE,20)) / MA(CLOSE,20) * 100
量比（5 日）          VOLUME / MA(VOLUME,5)
10 日动量%            (CLOSE - REF(CLOSE,10)) / REF(CLOSE,10) * 100
双均线差              EMA(CLOSE,12) - EMA(CLOSE,26)
20 日波动率%          STD(CLOSE,20) / MA(CLOSE,20) * 100
20 日新高标记          CROSS(CLOSE, HHV(CLOSE,20))
```

写错的公式会直接告诉你错在第几个字符，例如：

```
MA(CLOSE)      →  MA 需要 2 个参数，给了 1 个
FOO(1,2)       →  不支持的函数 FOO（可用：ABS, CROSS, EMA, HHV, LLV, MA, MAX, MIN, REF, STD, SUM）
(CLOSE         →  公式没写完（少了一个值或右括号）
MA(CLOSE,0)    →  MA 的第二个参数必须是正整数（现在是 0.0）
```

## 接口

```
GET /api/formulas                       → 示例列表
GET /api/session/{id}/indicator?id=ma_gap
GET /api/session/{id}/indicator?formula=(CLOSE-MA(CLOSE,20))/MA(CLOSE,20)*100
```

返回：

```json
{"ok": true, "formula": "...", "values": [{"time": "2026-03-02", "value": 1.23}, ...]}
```

值是**当前可见区间**算出来的，每走一根就重算一次——所以它和 K 线一样，永远只反映已经发生的事。
