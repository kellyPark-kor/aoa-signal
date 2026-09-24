"""Pure indicator/signal logic for AOA Signal.

Safety: this module contains market-data analysis only. It does not place orders.
The indicator formulas are copied from the original AOA_Signal_Lab app.
The selected default rule is A (breakout + volume + trend event), which intentionally
removes the RSI filter because the original RSI filter produced zero signals on the
2018-2021 research dataset. This is NOT a profitability claim.
"""
from __future__ import annotations
import json
from typing import Any, Dict
import numpy as np
import pandas as pd

# Preserved from the original app. These keys are intentionally retained even though
# the original signal() did not actually read ema_stack/macd_positive/macd_negative.
DEFAULT_RULES = {
    "long": {
        "ema_stack": True, "rsi_min": 45, "rsi_max": 58,
        "vol_min": 1.5, "macd_positive": True, "breakout": True
    },
    "short": {
        "ema_stack": True, "rsi_min": 42, "rsi_max": 55,
        "vol_min": 1.5, "macd_negative": True, "breakdown": True
    },
    "research_rule": "A",
    "use_rsi_filter": False,
}

DISCLAIMER = "검증되지 않은 연구용 규칙, 수익 근거 없음. AOA가 실제로 이 규칙을 사용했다는 뜻이 아닙니다."


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def indicators(df: pd.DataFrame) -> pd.DataFrame:
    # Formula intentionally preserved from the original app.py.
    x = df.copy()
    x["ema20"] = ema(x.close, 20); x["ema50"] = ema(x.close, 50); x["ema200"] = ema(x.close, 200)
    d = x.close.diff()
    gain = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain/loss.replace(0, np.nan)
    x["rsi14"] = 100-(100/(1+rs))
    fast = ema(x.close, 12); slow = ema(x.close, 26)
    x["macd"] = fast-slow; x["macd_signal"] = ema(x.macd, 9)
    x["macd_hist"] = x.macd-x.macd_signal
    x["bb_mid"] = x.close.rolling(20).mean()
    sd = x.close.rolling(20).std()
    x["bb_up"] = x.bb_mid+2*sd; x["bb_dn"] = x.bb_mid-2*sd
    x["bb_pos"] = (x.close-x.bb_dn)/(x.bb_up-x.bb_dn)
    tr = pd.concat([(x.high-x.low),(x.high-x.close.shift()).abs(),(x.low-x.close.shift()).abs()],axis=1).max(axis=1)
    x["atr14"] = tr.ewm(alpha=1/14, adjust=False).mean()
    x["vol_ratio"] = x.volume/x.volume.rolling(20).mean()
    x["high20_prev"] = x.high.shift(1).rolling(20).max()
    x["low20_prev"] = x.low.shift(1).rolling(20).min()
    x["breakout20"] = x.close>x.high20_prev
    x["breakdown20"] = x.close<x.low20_prev
    return x


def load_rules(path: str | None = None) -> Dict[str, Any]:
    if not path:
        return json.loads(json.dumps(DEFAULT_RULES))
    try:
        import yaml
        with open(path, 'r', encoding='utf-8') as f:
            loaded = yaml.safe_load(f) or {}
    except Exception as e:
        raise RuntimeError(f"규칙 설정을 읽지 못했습니다: {e}") from e
    rules = json.loads(json.dumps(DEFAULT_RULES))
    rules.update({k:v for k,v in loaded.items() if k in {"research_rule", "use_rsi_filter", "long", "short"}})
    return rules


def signal(row: pd.Series, rules: Dict[str, Any] | None = None) -> str:
    """Return LONG/SHORT/WAIT for a completed candle.

    Rule A disables only the RSI filter. EMA stack, volume, MACD direction and
    20-bar breakout/breakdown remain required. The existing indicator formulas
    are unchanged. The preserved DEFAULT_RULES boolean keys are not consulted,
    matching the original app's behavior.
    """
    rules = rules or DEFAULT_RULES
    use_rsi = bool(rules.get("use_rsi_filter", False))
    long_rsi_ok = (rules["long"]["rsi_min"] <= row.rsi14 <= rules["long"]["rsi_max"]) if use_rsi else True
    short_rsi_ok = (rules["short"]["rsi_min"] <= row.rsi14 <= rules["short"]["rsi_max"]) if use_rsi else True
    long_ok = (
        row.ema20 > row.ema50 > row.ema200 and
        long_rsi_ok and
        row.vol_ratio >= rules["long"]["vol_min"] and
        row.macd_hist > 0 and row.breakout20
    )
    short_ok = (
        row.ema20 < row.ema50 < row.ema200 and
        short_rsi_ok and
        row.vol_ratio >= rules["short"]["vol_min"] and
        row.macd_hist < 0 and row.breakdown20
    )
    if long_ok: return "LONG"
    if short_ok: return "SHORT"
    return "WAIT"


def legacy_signal(row: pd.Series, rules: Dict[str, Any] | None = None) -> str:
    """Exact original signal logic, kept for regression tests/documentation."""
    rules = rules or DEFAULT_RULES
    long_ok = (
        row.ema20 > row.ema50 > row.ema200 and
        rules["long"]["rsi_min"] <= row.rsi14 <= rules["long"]["rsi_max"] and
        row.vol_ratio >= rules["long"]["vol_min"] and
        row.macd_hist > 0 and row.breakout20
    )
    short_ok = (
        row.ema20 < row.ema50 < row.ema200 and
        rules["short"]["rsi_min"] <= row.rsi14 <= rules["short"]["rsi_max"] and
        row.vol_ratio >= rules["short"]["vol_min"] and
        row.macd_hist < 0 and row.breakdown20
    )
    if long_ok: return "LONG"
    if short_ok: return "SHORT"
    return "WAIT"
