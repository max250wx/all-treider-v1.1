"""Портфельный walk-forward: LKOH + VTBR + ROSN одновременно."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

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
SESSION_START = 7
SESSION_END = 15
SESSION_CLOSE = 15


def add_ind(df):
    c = df["close"]
    df["ema"] = c.ewm(span=EMA_TREND, adjust=False).mean()
    d = c.diff()
    g = d.where(d > 0, 0).ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    loss = (-d.where(d < 0, 0)).ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    df["rsi"] = 100 - 100 / (1 + g / loss.replace(0, np.nan))
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - c.shift()).abs(), (df["low"] - c.shift()).abs()],
        axis=1,
    ).max(axis=1)
    df["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    return df.dropna().copy()


def run_ticker(df):
    """Возвращает DataFrame сделок: entry_time, exit_time, pnl."""
    trades = []
    pos = None
    for i in range(1, len(df)):
        r = df.iloc[i]
        pr = df.iloc[i - 1]
        hr = df.index[i].hour
        if pos:
            xpnl, rsn = None, None
            if pos["s"] == "L" and r["low"] <= pos["st"]:
                xpnl = (min(pos["st"], r["open"]) * (1 - SLIP) - pos["en"]) * pos["q"]
                rsn = "st"
            elif pos["s"] == "S" and r["high"] >= pos["st"]:
                xpnl = (pos["en"] - max(pos["st"], r["open"]) * (1 + SLIP)) * pos["q"]
                rsn = "st"
            if not rsn:
                if pos["s"] == "L" and r["high"] >= pos["tp"]:
                    xpnl, rsn = (pos["tp"] - pos["en"]) * pos["q"], "tp"
                elif pos["s"] == "S" and r["low"] <= pos["tp"]:
                    xpnl, rsn = (pos["en"] - pos["tp"]) * pos["q"], "tp"
            if not rsn:
                if pos["s"] == "L" and pr["rsi"] < 50 <= r["rsi"]:
                    xpnl, rsn = (r["close"] - pos["en"]) * pos["q"], "rsi"
                elif pos["s"] == "S" and pr["rsi"] > 50 >= r["rsi"]:
                    xpnl, rsn = (pos["en"] - r["close"]) * pos["q"], "rsi"
            if not rsn and hr >= SESSION_CLOSE:
                xpnl = (
                    (r["close"] - pos["en"]) * pos["q"]
                    if pos["s"] == "L"
                    else (pos["en"] - r["close"]) * pos["q"]
                )
                rsn = "sess"
            if rsn:
                trades.append({"entry": pos["entry_time"], "exit": df.index[i], "pnl": xpnl})
                pos = None
        if pos is None and SESSION_START <= hr < SESSION_END:
            if r["close"] > r["ema"] and r["rsi"] < RSI_LO:
                en = r["close"]
                st = en - ATR_MULT * r["atr"]
                rk = en - st
                if rk > 0:
                    pos = {
                        "s": "L",
                        "en": en,
                        "st": st,
                        "tp": en + TP_R * rk,
                        "q": min(CAPITAL * RISK / rk, CAPITAL * 0.3 / en),
                        "entry_time": df.index[i],
                    }
            elif r["close"] < r["ema"] and r["rsi"] > RSI_HI:
                en = r["close"]
                st = en + ATR_MULT * r["atr"]
                rk = st - en
                if rk > 0:
                    pos = {
                        "s": "S",
                        "en": en,
                        "st": st,
                        "tp": en - TP_R * rk,
                        "q": min(CAPITAL * RISK / rk, CAPITAL * 0.3 / en),
                        "entry_time": df.index[i],
                    }
    return pd.DataFrame(trades)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", default="LKOH_M10.csv,VTBR_M10.csv,ROSN_M10.csv")
    ap.add_argument("--windows", type=int, default=6)
    a = ap.parse_args()

    files = [f.strip() for f in a.files.split(",")]
    print(f"Портфель: {files}")

    # Собираем данные
    dfs = {}
    for f in files:
        p = ROOT / "data/history" / f
        if not p.exists():
            print(f"НЕТ: {p}")
            continue
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close", "volume"]].dropna()
        df = df[df["volume"] > 0].sort_index()
        dfs[f] = add_ind(df)

    # Общий временной ряд
    all_trades = []
    for f, df in dfs.items():
        tr = run_ticker(df)
        tr["ticker"] = f
        all_trades.extend(tr.to_dict("records"))
        print(f"  {f}: {len(tr)} сделок")

    trades = pd.DataFrame(all_trades).sort_values("exit").reset_index(drop=True)
    print(f"\nВсего сделок в портфеле: {len(trades)}")

    # Walk-forward по времени (не по сделкам)
    tmin = trades["exit"].min()
    tmax = trades["exit"].max()
    span = (tmax - tmin) / a.windows

    results = []
    for k in range(a.windows):
        s = tmin + k * span
        e = tmin + (k + 1) * span if k < a.windows - 1 else tmax
        chunk = trades[(trades["exit"] >= s) & (trades["exit"] < e)]
        if chunk.empty:
            continue
        eq = CAPITAL
        peak = CAPITAL
        max_dd = 0
        for _, t in chunk.iterrows():
            eq += t["pnl"]
            if eq > peak:
                peak = eq
            dd = (eq - peak) / peak
            if dd < max_dd:
                max_dd = dd
        pnl = chunk["pnl"]
        wins = pnl[pnl > 0]
        losses = pnl[pnl <= 0]
        gw = wins.sum() if len(wins) else 0
        gl = abs(losses.sum()) if len(losses) else 0
        pf = gw / gl if gl > 0 else (99 if gw > 0 else 0)
        wr = len(wins) / len(chunk) * 100
        ret = (eq - CAPITAL) / CAPITAL * 100
        results.append(
            {"w": k + 1, "trades": len(chunk), "wr": wr, "pf": pf, "ret": ret, "dd": max_dd * 100}
        )
        print(
            f"  W{k + 1}: {s:%Y-%m-%d}..{e:%Y-%m-%d}  "
            f"trades={len(chunk)}  WR={wr:.1f}%  PF={pf:.2f}  "
            f"DD={max_dd * 100:.2f}%  ret={ret:+.2f}%"
        )

    if results:
        prof = sum(1 for r in results if r["ret"] > 0)
        pfs = [r["pf"] for r in results if r["pf"] < 99]
        print(f"\nПрибыльных окон: {prof}/{len(results)} ({prof / len(results) * 100:.0f}%)")
        print(f"Средний PF: {sum(pfs) / len(pfs):.2f}")
        print(f"Медиана PF: {sorted(pfs)[len(pfs) // 2]:.2f}")
        print(f"Средний return: {sum(r['ret'] for r in results) / len(results):+.2f}%")
        print(f"Средний DD: {sum(r['dd'] for r in results) / len(results):.2f}%")


if __name__ == "__main__":
    main()
