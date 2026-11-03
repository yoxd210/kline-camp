# 第三方组件与致谢

这个项目能跑起来，是因为别人先写好了这些。

## 一、代码里直接用到 / 随仓库分发的

### TradingView Lightweight Charts™ v4.1.3

- **用途**：所有 K 线和副图的绘制（`web/vendor/lightweight-charts.js`）
- **作者**：TradingView, Inc.
- **许可**：Apache License 2.0
- **协议全文**：[`web/vendor/LICENSE-lightweight-charts.txt`](web/vendor/LICENSE-lightweight-charts.txt)
- **项目主页**：<https://github.com/tradingview/lightweight-charts>
- **版权声明**（保留在文件头）：

```
TradingView Lightweight Charts™ v4.1.3
Copyright (c) 2024 TradingView, Inc.
Licensed under Apache License 2.0
https://www.apache.org/licenses/LICENSE-2.0
```

> Apache-2.0 要求：分发时保留版权与许可声明、附带协议文本、标注修改。
> 我们**没有修改**这个文件，是原封不动放在 `web/vendor/` 下的。

### Python 依赖（运行时安装，不随仓库分发）

| 包 | 许可 | 用途 |
|---|---|---|
| [FastAPI](https://github.com/fastapi/fastapi) | MIT | HTTP 接口 |
| [Uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause | ASGI 服务器 |
| [pandas](https://github.com/pandas-dev/pandas) | BSD-3-Clause | 数据处理 |
| [pyarrow](https://github.com/apache/arrow) | Apache-2.0 | 读 parquet |
| [httpx](https://github.com/encode/httpx) | BSD-3-Clause | 测试用 |
| [pytest](https://github.com/pytest-dev/pytest) | MIT | 测试 |

它们通过 `requirements.txt` 安装，各自的许可随包分发。

## 二、启发与致谢

下面这些项目 / 产品，教会了我们"这个东西该长什么样"。

- **[KLinePlayground](https://github.com/FAT7/KLinePlayground)**（fat7，MIT）——
  同类里做得最完整的 A 股 K 线复盘训练器。我们学到的三样东西：
  「盲盒 / 指定」两种出题方式、T+1 加佣金印花税的口径、训练结束后出胜率与交易明细。
  想找功能更全的现成软件，直接用它。
- **同花顺**（商业软件）——界面布局的参考：主图 + 等高副图、左上角的指标名称与数值、
  十字光标贯穿所有副图。对齐的是交互习惯。
- **[TradingView Bar Replay](https://www.tradingview.com/)**、**[FX Replay](https://fxreplay.com/)** ——
  「隐藏未来、逐根推进」这个训练范式最早的普及者。

## 三、数据

本项目**不包含任何行情数据**，也不连任何行情接口。

- 数据需要使用者自行获取（本地 parquet，格式见 [docs/DATA.md](docs/DATA.md)），
  也可以用 `scripts/make_demo_data.py` 随机生成一份示例。
- 如果你用的是付费数据源，建议别把它提交到公开仓库，以免违反数据方的授权；
  `.gitignore` 已经默认挡掉 `*.parquet` / `*.csv` / `data/`。
- 演示数据完全是随机数字，不对应任何真实证券。

## 四、如果我们要改别人的代码

现在的规矩是：**能不复制就不复制**。真要复制，按这个流程走：

1. 先看许可：MIT / BSD / Apache-2.0 可以（保留声明）；GPL / AGPL 要谨慎（会传染）；
   没写许可的等于"保留所有权利"，不能拿。
2. 把文件放进 `third_party/`，原样保留文件头的版权声明。
3. 在这个文件里加一条：来源、版本、许可、链接、**改了什么**。
4. 随仓库放一份协议全文。
