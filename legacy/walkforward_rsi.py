import argparse, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CAPITAL = 200000
RISK = 0.003
SLIP = 0.0005
RSI_PERIOD = 9
RSI_LO = 40
RSI_HI = 60
EMA_TREND = 200
ATR_MULT = 2.0
TP_R = 2.0
SESSION_START = 7   # 10:00 МСК = 07:00 UTC
SESSION_END = 15    # 18:00 МСК = 15:00 UTC
SESSION_CLOSE = 15


def run(name):
    p = ROOT / "data/history" / name
    if not p.exists():
        print(f"NO FILE: {p}")
        sys.exit(1)
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]].dropna()
    df = df[df["volume"] > 0].sort_index()
    c = df["close"]
    df["ema"] = c.ewm(span=EMA_TREND, adjust=False).mean()
    d = c.diff()
    g = d.where(d > 0, 0).ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    l = (-d.where(d < 0, 0)).ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    df["rsi"] = 100 - 100 / (1 + g / l.replace(0, np.nan))
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - c.shift()).abs(), (df["low"] - c.shift()).abs()],
        axis=1,
    ).max(axis=1)
    df["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    df = df.dropna()

    long_bars = ((df["close"] > df["ema"]) & (df["rsi"] < RSI_LO)).sum()
    short_bars = ((df["close"] < df["ema"]) & (df["rsi"] > RSI_HI)).sum()
    print(f"DEBUG: RSI={RSI_PERIOD} LO={RSI_LO} HI={RSI_HI} EMA={EMA_TREND} SESSION={SESSION_START}-{SESSION_END} UTC")
    print(f"Bars: {len(df)}, LONG-bars: {long_bars}, SHORT-bars: {short_bars}")
    print(f"RSI range: {df['rsi'].min():.1f}..{df['rsi'].max():.1f}, median={df['rsi'].median():.1f}")

    size = len(df) // 6
    results = []
    for k in range(6):
        s = k * size
        e = (k + 1) * size if k < 5 else len(df)
        chunk = df.iloc[s:e]
        eq = CAPITAL
        peak = CAPITAL
        max_dd = 0
        pos = None
        trades = []
        ld = None
        dpnl = 0
        for i in range(1, len(chunk)):
            r = chunk.iloc[i]
            pr = chunk.iloc[i - 1]
            dt = chunk.index[i].date()
            hr = chunk.index[i].hour
            if dt != ld:
                dpnl = 0
                ld = dt
            if pos:
                xpnl = 0
                rsn = None
                if pos["s"] == "L" and r["low"] <= pos["st"]:
                    xpnl = (min(pos["st"], r["open"]) * (1 - SLIP) - pos["en"]) * pos["q"]
                    rsn = "st"
                elif pos["s"] == "S" and r["high"] >= pos["st"]:
                    xpnl = (pos["en"] - max(pos["st"], r["open"]) * (1 + SLIP)) * pos["q"]
                    rsn = "st"
                if not rsn:
                    if pos["s"] == "L" and r["high"] >= pos["tp"]:
                        xpnl = (pos["tp"] - pos["en"]) * pos["q"]
                        rsn = "tp"
                    elif pos["s"] == "S" and r["low"] <= pos["tp"]:
                        xpnl = (pos["en"] - pos["tp"]) * pos["q"]
                        rsn = "tp"
                if not rsn:
                    if pos["s"] == "L" and pr["rsi"] < 50 <= r["rsi"]:
                        xpnl = (r["close"] - pos["en"]) * pos["q"]
                        rsn = "rsi"
                    elif pos["s"] == "S" and pr["rsi"] > 50 >= r["rsi"]:
                        xpnl = (pos["en"] - r["close"]) * pos["q"]
                        rsn = "rsi"
                if not rsn and hr >= SESSION_CLOSE:
                    if pos["s"] == "L":
                        xpnl = (r["close"] - pos["en"]) * pos["q"]
                    else:
                        xpnl = (pos["en"] - r["close"]) * pos["q"]
                    rsn = "sess"
                if rsn:
                    eq += xpnl
                    dpnl += xpnl
                    trades.append(xpnl)
                    pos = None
            if pos is None and dpnl > -CAPITAL * 0.015 and SESSION_START <= hr < SESSION_END:
                if r["close"] > r["ema"] and r["rsi"] < RSI_LO:
                    en = r["close"]
                    st = en - ATR_MULT * r["atr"]
                    rk = en - st
                    if rk > 0:
                        pos = {"s": "L", "en": en, "st": st, "tp": en + TP_R * rk, "q": min(CAPITAL * RISK / rk, CAPITAL * 0.3 / en)}
                elif r["close"] < r["ema"] and r["rsi"] > RSI_HI:
                    en = r["close"]
                    st = en + ATR_MULT * r["atr"]
                    rk = st - en
                    if rk > 0:
                        pos = {"s": "S", "en": en, "st": st, "tp": en - TP_R * rk, "q": min(CAPITAL * RISK / rk, CAPITAL * 0.3 / en)}
            if eq > peak:
                peak = eq
            dd = (eq - peak) / peak
            if dd < max_dd:
                max_dd = dd
        wins = [t for t in trades if t > 0]
        gw = sum(wins)
        gl = abs(sum(t for t in trades if t <= 0))
        pf = gw / gl if gl > 0 else (99 if gw > 0 else 0)
        wr = len(wins) / len(trades) * 100 if trades else 0
        ret = (eq - CAPITAL) / CAPITAL * 100
        results.append((len(trades), wr, pf, ret, max_dd * 100))
        print(f"  W{k+1}: {chunk.index[0]:%Y-%m-%d}..{chunk.index[-1]:%Y-%m-%d} trades={len(trades)} WR={wr:.1f}% PF={pf:.2f} DD={max_dd*100:.2f}% ret={ret:+.2f}%")

    total = sum(r[0] for r in results)
    pfs = [r[2] for r in results if r[2] < 99]
    avg_pf = sum(pfs) / max(1, len(pfs))
    med_pf = sorted(pfs)[len(pfs) // 2] if pfs else 0
    prof = sum(1 for r in results if r[3] > 0)
    print(f"Total trades: {total}, Profitable windows: {prof}/6, Avg PF: {avg_pf:.2f}, Median PF: {med_pf:.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    a = ap.parse_args()
    run(a.file)