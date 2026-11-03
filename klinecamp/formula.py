"""一个够用的指标公式引擎（副图用）。

只支持「逐根计算」的表达式，不搞变量赋值、循环、多行脚本——训练营的副图不需要那些，
而多一个语法就多一堆坑。

支持的写法：

    CLOSE                     收盘价（也可写 C）
    OPEN HIGH LOW VOLUME AMOUNT
    MA(CLOSE,20)              简单均线
    EMA(CLOSE,12)             指数均线
    REF(CLOSE,1)              往前取 N 根
    SUM(VOLUME,5)             最近 N 根求和
    HHV(HIGH,20) / LLV(LOW,20) 最近 N 根最高/最低
    STD(CLOSE,20)             标准差
    MAX(a,b) / MIN(a,b) / ABS(a)
    CROSS(a,b)                a 上穿 b → 1，否则 0
    四则运算 + 括号，数字可以带小数

算不出来就抛 FormulaError，带上出错位置，前端直接显示原文。
"""

from __future__ import annotations

import math
import re

import pandas as pd

TOKEN_RE = re.compile(
    r"\s*(?:(?P<num>\d+(?:\.\d+)?)|(?P<name>[A-Za-z_][A-Za-z0-9_]*)|(?P<op>[-+*/(),<>]))"
)

FIELDS = {
    "CLOSE": "close", "C": "close",
    "OPEN": "open", "O": "open",
    "HIGH": "high", "H": "high",
    "LOW": "low", "L": "low",
    "VOLUME": "volume", "VOL": "volume", "V": "volume",
    "AMOUNT": "amount", "AMO": "amount",
}

FUNCS = {"MA", "EMA", "REF", "SUM", "HHV", "LLV", "STD", "MAX", "MIN", "ABS", "CROSS"}


class FormulaError(ValueError):
    """公式有问题（语法 / 未知函数 / 参数不合法）。"""


def tokenize(text: str) -> list[tuple[str, str, int]]:
    out, pos = [], 0
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise FormulaError(f"第 {pos + 1} 个字符看不懂：{text[pos]!r}")
        pos = m.end()
        if m.group("num"):
            out.append(("num", m.group("num"), m.start("num")))
        elif m.group("name"):
            out.append(("name", m.group("name").upper(), m.start("name")))
        elif m.group("op"):
            out.append(("op", m.group("op"), m.start("op")))
    return out


class _Parser:
    def __init__(self, tokens: list[tuple[str, str, int]], bars: pd.DataFrame) -> None:
        self.t = tokens
        self.i = 0
        self.bars = bars

    def peek(self) -> tuple[str, str, int] | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self, kind: str | None = None, value: str | None = None):
        tok = self.peek()
        if tok is None:
            raise FormulaError("公式没写完（少了一个值或右括号）")
        if kind and tok[0] != kind:
            raise FormulaError(f"第 {tok[2] + 1} 个字符处应该是 {kind}，实际是 {tok[1]!r}")
        if value and tok[1] != value:
            raise FormulaError(f"第 {tok[2] + 1} 个字符处应该是 {value!r}，实际是 {tok[1]!r}")
        self.i += 1
        return tok

    # expr := term (('+'|'-') term)*
    def expr(self):
        node = self.term()
        while True:
            tok = self.peek()
            if tok and tok[0] == "op" and tok[1] in "+-":
                self.take()
                node = node + self.term() if tok[1] == "+" else node - self.term()
            else:
                return node

    # term := factor (('*'|'/') factor)*
    def term(self):
        node = self.factor()
        while True:
            tok = self.peek()
            if tok and tok[0] == "op" and tok[1] in "*/":
                self.take()
                rhs = self.factor()
                node = node * rhs if tok[1] == "*" else node / rhs.replace(0, float("nan"))
            else:
                return node

    # factor := ['-'] primary
    def factor(self):
        tok = self.peek()
        if tok and tok[0] == "op" and tok[1] == "-":
            self.take()
            return -self.factor()
        return self.primary()

    def primary(self):
        tok = self.take()
        if tok[0] == "num":
            return pd.Series(float(tok[1]), index=self.bars.index, dtype="float64")
        if tok[0] == "op" and tok[1] == "(":
            node = self.expr()
            self.take("op", ")")
            return node
        if tok[0] == "name":
            name = tok[1]
            nxt = self.peek()
            if nxt and nxt[0] == "op" and nxt[1] == "(":
                self.take("op", "(")
                args = [self.expr()]
                while True:
                    n2 = self.peek()
                    if n2 and n2[0] == "op" and n2[1] == ",":
                        self.take()
                        args.append(self.expr())
                        continue
                    break
                self.take("op", ")")
                return self.call(name, args, tok[2])
            if name in FIELDS:
                return self.bars[FIELDS[name]].astype("float64")
            raise FormulaError(f"不认识的名称 {name}（可用：{', '.join(sorted(FIELDS))}）")
        raise FormulaError(f"第 {tok[2] + 1} 个字符处语法不对：{tok[1]!r}")

    def call(self, name: str, args: list, pos: int):
        if name not in FUNCS:
            raise FormulaError(f"不支持的函数 {name}（可用：{', '.join(sorted(FUNCS))}）")
        need = 2 if name in {"MA", "EMA", "REF", "SUM", "HHV", "LLV", "STD", "MAX", "MIN", "CROSS"} else 1
        if len(args) != need:
            raise FormulaError(f"{name} 需要 {need} 个参数，给了 {len(args)} 个")

        a = args[0]
        if name == "ABS":
            return a.abs()
        if name in {"MAX", "MIN"}:
            b = args[1]
            return a.combine(b, max) if name == "MAX" else a.combine(b, min)
        if name == "CROSS":
            b = args[1]
            up = (a > b) & (a.shift(1) <= b.shift(1))
            return up.astype("float64")

        n = _int_arg(args[1], name, pos)
        if name == "REF":
            return a.shift(n)
        if name == "MA":
            return a.rolling(n, min_periods=n).mean()
        if name == "EMA":
            return a.ewm(span=n, adjust=False).mean()
        if name == "SUM":
            return a.rolling(n, min_periods=n).sum()
        if name == "HHV":
            return a.rolling(n, min_periods=n).max()
        if name == "LLV":
            return a.rolling(n, min_periods=n).min()
        if name == "STD":
            return a.rolling(n, min_periods=n).std(ddof=0)
        raise FormulaError(f"不支持的函数 {name}")  # pragma: no cover


def _int_arg(series, name: str, pos: int) -> int:
    try:
        v = float(series.iloc[0]) if hasattr(series, "iloc") else float(series)
    except Exception as exc:  # noqa: BLE001
        raise FormulaError(f"{name} 的第二个参数必须是整数") from exc
    if not math.isfinite(v) or v <= 0 or v != int(v):
        raise FormulaError(f"{name} 的第二个参数必须是正整数（现在是 {v}）")
    return int(v)


def evaluate(formula: str, bars: pd.DataFrame) -> pd.Series:
    """把公式算成一条序列（长度同 bars，前几根可能是 NaN）。"""
    text = (formula or "").strip()
    if not text:
        raise FormulaError("公式是空的")
    if len(text) > 300:
        raise FormulaError("公式太长（上限 300 字符）")
    tokens = tokenize(text)
    if not tokens:
        raise FormulaError("公式里没有可计算的内容")
    parser = _Parser(tokens, bars.reset_index(drop=True))
    series = parser.expr()
    if parser.peek() is not None:
        tok = parser.peek()
        raise FormulaError(f"第 {tok[2] + 1} 个字符之后多出来了：{tok[1]!r}")
    return series
