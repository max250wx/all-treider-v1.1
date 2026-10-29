"""Портфель с IMOEX-фильтром: LONG только если IMOEX > EMA200, SHORT если ниже."""
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
SESSION_START = 7
SESSION_END = 15
SESSION_CLOSE = 15


def load_add(f):
    p = ROOT / "data/history" / f
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]].dropna()
    if df["volume"].fillna(0).sum() > 0:
        df = df[df["volume"] > 0]
    df = df.sort_index()
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
    return df.dropna().copy()


def run_ticker(df, imoex):
    imoex_aligned = imoex.reindex(df.index, method="ffill")
    df = df.copy()
    df["imoex_close"] = imoex_aligned["imoex_close"]
    df["imoex_ema"] = imoex_aligned["imoex_ema"]
    df = df.dropna(subset=["imoex_ema"])

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
                xpnl = (r["close"] - pos["en"]) * pos["q"] if pos["s"] == "L" else (pos["en"] - r["close"]) * pos["q"]
                rsn = "sess"
            if rsn:
                trades.append({"entry": pos["entry_time"], "exit": df.index[i], "pnl": xpnl, "ticker": pos["tk"]})
                pos = None
        if pos is None and SESSION_START <= hr < SESSION_END:
            imoex_up = r["imoex_close"] > r["imoex_ema"]
            imoex_dn = r["imoex_close"] < r["imoex_ema"]
            if r["close"] > r["ema"] and r["rsi"] < RSI_LO and imoex_up:
                en = r["close"]
                st = en - ATR_MULT * r["atr"]
                rk = en - st
                if rk > 0:
                    pos = {"s": "L", "en": en, "st": st, "tp": en + TP_R * rk,
                           "q": min(CAPITAL * RISK / rk, CAPITAL * 0.3 / en),
                           "entry_time": df.index[i], "tk": df.attrs.get("ticker", "?")}
            elif r["close"] < r["ema"] and r["rsi"] > RSI_HI and imoex_dn:
                en = r["close"]
                st = en + ATR_MULT * r["atr"]
                rk = st - en
                if rk > 0:
                    pos = {"s": "S", "en": en, "st": st, "tp": en - TP_R * rk,
                           "q": min(CAPITAL * RISK / rk, CAPITAL * 0.3 / en),
                           "entry_time": df.index[i], "tk": df.attrs.get("ticker", "?")}
    return pd.DataFrame(trades)


def main():
    imoex = load_add("IMOEX_M10.csv")[["close", "ema"]].rename(
        columns={"close": "imoex_close", "ema": "imoex_ema"}
    )
    print(f"IMOEX: {len(imoex)} баров")
    imoex_up_bars = (imoex["imoex_close"] > imoex["imoex_ema"]).sum()
    imoex_dn_bars = (imoex["imoex_close"] < imoex["imoex_ema"]).sum()
    print(f"  IMOEX выше EMA200: {imoex_up_bars} ({imoex_up_bars/len(imoex)*100:.1f}%)")
    print(f"  IMOEX ниже EMA200: {imoex_dn_bars} ({imoex_dn_bars/len(imoex)*100:.1f}%)")

    files = ["LKOH_M10.csv", "VTBR_M10.csv", "ROSN_M10.csv"]
    print(f"\nПортфель + IMOEX-фильтр: {files}")
    all_trades = []
    for f in files:
        df = load_add(f)
        df.attrs["ticker"] = f
        tr = run_ticker(df, imoex)
        all_trades.extend(tr.to_dict("records"))
        print(f"  {f}: {len(tr)} сделок")

    trades = pd.DataFrame(all_trades).sort_values("exit").reset_index(drop=True)
    if trades.empty:
        print("Нет сделок")
        return
    print(f"\nВсего сделок: {len(trades)}")

    tmin = trades["exit"].min()
    tmax = trades["exit"].max()
    span = (tmax - tmin) / 6

    results = []
    for k in range(6):
        s = tmin + k * span
        e = tmin + (k + 1) * span if k < 5 else tmax
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
        results.append({"trades": len(chunk), "pf": pf, "ret": ret, "dd": max_dd * 100})
        print(f"  W{k+1}: {s:%Y-%m-%d}..{e:%Y-%m-%d} trades={len(chunk)} WR={wr:.1f}% PF={pf:.2f} DD={max_dd*100:.2f}% ret={ret:+.2f}%")

    prof = sum(1 for r in results if r["ret"] > 0)
    pfs = [r["pf"] for r in results if r["pf"] < 99]
    print(f"\nПрибыльных: {prof}/{len(results)}")
    print(f"Avg PF: {sum(pfs)/len(pfs):.2f}")
    print(f"Median PF: {sorted(pfs)[len(pfs)//2]:.2f}")
    print(f"Avg return: {sum(r['ret'] for r in results)/len(results):+.2f}%")
    print(f"Avg DD: {sum(r['dd'] for r in results)/len(results):.2f}%")


if __name__ == "__main__":
    main()