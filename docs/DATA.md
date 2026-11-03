# 数据格式

**本项目不包含任何行情数据。** 数据需要你自行获取，或者用 `scripts/make_demo_data.py`
随机生成一份示例。你只需要把 `KLINE_DATA_DIR` 指到放数据的目录。

## 目录结构

```
<KLINE_DATA_DIR>/
  meta.parquet              标的清单
  bars/
    000001.parquet          一只票一个文件
    600519.parquet
    ...
```

## meta.parquet

| 列 | 类型 | 说明 |
|---|---|---|
| `code` | string | 6 位代码，如 `600519` |
| `name` | string | 名称 |
| `industry` | string | 行业（可为空） |
| `board` / `market` | string/int | 板块（可选，用于排除北交所等） |
| `price` / `pct_chg` | float | 最新价 / 当日涨跌幅（可选） |
| `total_mv` / `float_mv` | float | 市值，单位万元（可选） |

**必需列**：`code`、`name`。其它列没有也能跑，只是界面上少显示。

## bars/<code>.parquet

| 列 | 类型 | 说明 |
|---|---|---|
| `date` | date / datetime | 交易日，升序无所谓，代码里会排 |
| `open` | float | 开盘价 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `close` | float | 收盘价 |
| `volume` | float | 成交量（股） |
| `amount` | float | 成交额（元） |

**必需列**：`date`、`open`、`high`、`low`、`close`、`volume`。
`amount` 少了只有「成交额过滤」类条件用不了。

`code` 列可有可无（文件名已经是代码）；有的话会被统一补成 6 位。

## 价格口径

- 代码不做复权换算，**存什么价就用什么价**。请自己保证整段是同一口径
  （前复权最好，这样跨除权日不会出现假跳空）。
- 停牌日可以缺行；一局里如果遇到缺行，就当那天没交易。

## 没有数据也能跑

想先看看长什么样，可以造一份**纯虚构**的示例数据（固定随机种子，不涉及任何真实行情）：

```bash
python scripts/make_demo_data.py --out .\demo-data --stocks 40 --days 400
set KLINE_DATA_DIR=.\demo-data
python run.py
```

生成器写得很明确：价格是随机游走，代码是 `3100xx`（A 股里没有这个号段），不会和真实票撞车。

## 为什么数据不进仓库

1. 体积大（全市场日线约 1.7 亿行），git 存不下也拉不动
2. 如果你用的是付费数据源，二次分发可能违反数据方的授权
3. 换数据源时仓库不用改 —— 只要按上面的列名导出即可

`.gitignore` 里已经挡掉：`data/`、`*.parquet`、`*.csv`、`*.sqlite3`、`output/`。
提交前请确认 `git status` 里没有数据文件。
