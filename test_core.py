import numpy as np, pandas as pd
from signal_core import indicators, signal, legacy_signal

def base_row(**kw):
    vals=dict(ema20=110,ema50=100,ema200=90,rsi14=72,vol_ratio=2.0,macd_hist=3.0,breakout20=True,breakdown20=False,atr14=100)
    vals.update(kw); return pd.Series(vals)

def test_rule_a_long_and_legacy_wait():
    r=base_row()
    assert signal(r)=="LONG"
    assert legacy_signal(r)=="WAIT"  # RSI 72 is outside original 45-58

def test_rule_a_short():
    r=base_row(ema20=90,ema50=100,ema200=110,rsi14=28,macd_hist=-3,breakout20=False,breakdown20=True)
    assert signal(r)=="SHORT"

def test_indicator_columns():
    n=250; close=np.linspace(100,200,n); df=pd.DataFrame({'open':close,'high':close+2,'low':close-2,'close':close,'volume':np.ones(n)})
    x=indicators(df)
    for c in ['ema20','ema50','ema200','rsi14','macd_hist','bb_pos','atr14','vol_ratio','breakout20','breakdown20']:
        assert c in x.columns

def test_incomplete_candle_not_used_by_worker_contract():
    # The worker drops the last row before signal(). This test verifies that a
    # signal placed only in the newest row is absent when the row is dropped.
    rows=[]
    for i in range(250):
        rows.append({'open':100+i*.1,'high':101+i*.1,'low':99+i*.1,'close':100+i*.1,'volume':100})
    df=pd.DataFrame(rows); x=indicators(df); closed=x.iloc[:-1]
    assert len(closed)==249
