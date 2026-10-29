"""Walk-forward бэктест по правилам V2.4.1 на реальных данных MOEX."""
import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

RESULTS_DIR = ROOT / CFG["paths"]["results"] / "walkforward"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

CAPITAL = 200_000
RISK_PER_TRADE = 0.003
DAILY_LOSS_LIMIT = 0.015
MAX_EXPOSURE = 0.30

ATR_NORMAL_MAX = 0.15     # было 2.5 — на M1 медиана 0.055, 3× медианы
ATR_PANIC = 0.30          # было 4.0 — почти максимум
ATR_MIN = 0.005           # было 0.5 — отсекаем самые тихие 5–10%
ATR_MAX = 0.30            # было 6.0 — отсекаем топ-1% самых волатильных


def find_file(name):
    for cand in [ROOT / "data/history" / name, Path(r"C:\trading") / name]:
        if cand.exists():
            return cand
    return None


def load_csv(name):
    p = find_file(name)
    if p is None:
        print(f"ОШИБКА: файл {name} не найден")
        sys.exit(1)
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={"vol": "volume"})
    needed = ["open", "high", "low", "close", "volume"]
    df = df[[c for c in needed if c in df.columns]].dropna()
    df = df[df["volume"] > 0].sort_index()
    print(f"Загружено {len(df)} баров из {p.name} ({df.index[0]:%Y-%m-%d} — {df.index[-1]:%Y-%m-%d})")
    return df


def add_indicators(df):
    c = df["close"]
    df["ema20"] = c.ewm(span=20, adjust=False).mean()
    df["ema50"] = c.ewm(span=50, adjust=False).mean()
    df["ema200"] = c.ewm(span=200, adjust=False).mean()

    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - c.shift()).abs()
    tr3 = (df["low"] - c.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1/14, adjust=False).mean()
    df["atr_pct"] = df["atr"] / c * 100

    df["vol_sma"] = df["volume"].rolling(20).mean()

    tp = (df["high"] + df["low"] + c) / 3
    df["vwap"] = (tp * df["volume"]).rolling(100).sum() / df["volume"].rolling(100).sum()

    sign = np.sign(c.diff()).fillna(0)
    df["obv"] = (sign * df["volume"]).cumsum()
    return df.dropna().copy()


def run_backtest(df):
    equity = CAPITAL
    peak = CAPITAL
    max_dd = 0.0
    trades = []
    position = None
    last_date = None
    daily_pnl = 0.0

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        date = df.index[i].date()

        if date != last_date:
            daily_pnl = 0.0
            last_date = date

        if position:
            exit_pnl = 0.0
            reason = None

            if position["side"] == "LONG" and row["low"] <= position["stop"]:
                exit_pnl = (position["stop"] - position["entry"]) * position["qty"]
                reason = "stop"
            elif position["side"] == "SHORT" and row["high"] >= position["stop"]:
                exit_pnl = (position["entry"] - position["stop"]) * position["qty"]
                reason = "stop"

            if not reason:
                if position["side"] == "LONG" and row["close"] < row["ema50"]:
                    exit_pnl = (row["close"] - position["entry"]) * position["qty"]
                    reason = "trail_ema50"
                elif position["side"] == "SHORT" and row["close"] > row["ema50"]:
                    exit_pnl = (position["entry"] - row["close"]) * position["qty"]
                    reason = "trail_ema50"

            if not reason:
                if position["side"] == "LONG" and row["ema20"] < row["ema50"]:
                    exit_pnl = (row["close"] - position["entry"]) * position["qty"]
                    reason = "trend_exit"
                elif position["side"] == "SHORT" and row["ema20"] > row["ema50"]:
                    exit_pnl = (position["entry"] - row["close"]) * position["qty"]
                    reason = "trend_exit"

            if not reason:
                if position["side"] == "LONG" and row["high"] >= position["tp2"]:
                    exit_pnl = (position["tp2"] - position["entry"]) * position["qty"]
                    reason = "tp2"
                elif position["side"] == "SHORT" and row["low"] <= position["tp2"]:
                    exit_pnl = (position["entry"] - position["tp2"]) * position["qty"]
                    reason = "tp2"

            if not reason and not position["partial_done"]:
                if position["side"] == "LONG" and row["high"] >= position["tp1"]:
                    partial_qty = position["qty"] * 0.5
                    pnl1 = (position["tp1"] - position["entry"]) * partial_qty
                    equity += pnl1
                    daily_pnl += pnl1
                    trades.append({
                        "entry_time": position["entry_time"], "exit_time": df.index[i],
                        "side": position["side"], "pnl": pnl1, "reason": "tp1_partial",
                    })
                    position["qty"] -= partial_qty
                    position["stop"] = position["entry"]
                    position["partial_done"] = True
                elif position["side"] == "SHORT" and row["low"] <= position["tp1"]:
                    partial_qty = position["qty"] * 0.5
                    pnl1 = (position["entry"] - position["tp1"]) * partial_qty
                    equity += pnl1
                    daily_pnl += pnl1
                    trades.append({
                        "entry_time": position["entry_time"], "exit_time": df.index[i],
                        "side": position["side"], "pnl": pnl1, "reason": "tp1_partial",
                    })
                    position["qty"] -= partial_qty
                    position["stop"] = position["entry"]
                    position["partial_done"] = True

            if reason:
                equity += exit_pnl
                daily_pnl += exit_pnl
                trades.append({
                    "entry_time": position["entry_time"], "exit_time": df.index[i],
                    "side": position["side"], "pnl": exit_pnl, "reason": reason,
                })
                position = None

        if position is None and daily_pnl > -CAPITAL * DAILY_LOSS_LIMIT:
            regime = "SIDEWAYS"
            if row["ema20"] > row["ema50"] > row["ema200"] and row["close"] > row["ema20"]:
                regime = "UPTREND"
            elif row["ema20"] < row["ema50"] < row["ema200"] and row["close"] < row["ema20"]:
                regime = "DOWNTREND"

            if row["atr_pct"] < ATR_PANIC and ATR_MIN <= row["atr_pct"] <= ATR_MAX:
                obv_up = row["obv"] > df["obv"].iloc[i - 5] if i >= 5 else False
                obv_dn = row["obv"] < df["obv"].iloc[i - 5] if i >= 5 else False

                if (regime == "UPTREND" and row["close"] > prev["high"]
                        and row["volume"] >= row["vol_sma"]
                        and row["close"] > row["vwap"]
                        and obv_up and row["atr_pct"] < ATR_NORMAL_MAX):
                    entry = row["close"]
                    stop = entry - 2.0 * row["atr"]
                    risk = entry - stop
                    if risk > 0:
                        qty = (CAPITAL * RISK_PER_TRADE) / risk
                        qty = min(qty, CAPITAL * MAX_EXPOSURE / entry)
                        position = {
                            "side": "LONG", "entry": entry, "stop": stop,
                            "tp1": entry + risk, "tp2": entry + 2 * risk,
                            "qty": qty, "partial_done": False,
                            "entry_time": df.index[i],
                        }
                elif (regime == "DOWNTREND" and row["close"] < prev["low"]
                        and row["volume"] >= row["vol_sma"]
                        and row["close"] < row["vwap"]
                        and obv_dn and row["atr_pct"] < ATR_NORMAL_MAX):
                    entry = row["close"]
                    stop = entry + 2.0 * row["atr"]
                    risk = stop - entry
                    if risk > 0:
                        qty = (CAPITAL * RISK_PER_TRADE) / risk
                        qty = min(qty, CAPITAL * MAX_EXPOSURE / entry)
                        position = {
                            "side": "SHORT", "entry": entry, "stop": stop,
                            "tp1": entry - risk, "tp2": entry - 2 * risk,
                            "qty": qty, "partial_done": False,
                            "entry_time": df.index[i],
                        }

        if equity > peak:
            peak = equity
        dd = (equity - peak) / peak
        if dd < max_dd:
            max_dd = dd

    return trades, equity, max_dd


def metrics(trades, equity_end, max_dd):
    if not trades:
        return {"trades": 0, "winrate": 0, "pf": 0, "pnl": 0,
                "dd": 0, "return_pct": 0, "avg_r": 0}
    pnl_series = pd.Series([t["pnl"] for t in trades])
    wins = pnl_series[pnl_series > 0]
    losses = pnl_series[pnl_series <= 0]
    gw = wins.sum() if len(wins) else 0
    gl = abs(losses.sum()) if len(losses) else 0
    pf = gw / gl if gl > 0 else (float("inf") if gw > 0 else 0)
    return {
        "trades": len(trades),
        "winrate": round(len(wins) / len(trades) * 100, 1),
        "pf": round(pf, 2) if pf != float("inf") else "inf",
        "pnl": round(equity_end - CAPITAL),
        "dd": round(max_dd * 100, 2),
        "return_pct": round((equity_end - CAPITAL) / CAPITAL * 100, 2),
        "avg_r": round(pnl_series.mean(), 2),
    }


def walk_forward(df, n_windows=6):
    size = len(df) // n_windows
    rows = []
    for k in range(n_windows):
        s = k * size
        e = (k + 1) * size if k < n_windows - 1 else len(df)
        chunk = df.iloc[s:e]
        if len(chunk) < 200:
            continue
        trades, equity_end, max_dd = run_backtest(chunk)
        m = metrics(trades, equity_end, max_dd)
        m["window"] = k + 1
        m["from"] = chunk.index[0].strftime("%Y-%m-%d")
        m["to"] = chunk.index[-1].strftime("%Y-%m-%d")
        rows.append(m)
        print(f"  окно {k+1}: {m['from']}..{m['to']}  "
              f"сделок {m['trades']:>3}  WR {m['winrate']:>5}%  "
              f"PF {str(m['pf']):>5}  DD {m['dd']:>6}%  ret {m['return_pct']:+.2f}%")
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="imoexf_m1.csv")
    ap.add_argument("--windows", type=int, default=6)
    a = ap.parse_args()

    df = load_csv(a.file)
    df = add_indicators(df)
    print(f"После индикаторов: {len(df)} баров\n")

    print(f"Walk-forward: {a.windows} окон")
    res = walk_forward(df, n_windows=a.windows)
    print()

    if res.empty:
        print("Нет результатов")
        return

    print("=" * 100)
    print(res.to_string(index=False))
    print("=" * 100)

    profitable = (res["return_pct"] > 0).sum()
    print(f"Прибыльных окон: {profitable}/{len(res)} ({profitable / len(res) * 100:.0f}%)")
    print(f"Средний PF:     {res['pf'].replace('inf', 99).astype(float).mean():.2f}")
    print(f"Средний return: {res['return_pct'].mean():+.2f}%")
    print(f"Средний DD:     {res['dd'].mean():.2f}%")
    print(f"Всего сделок:   {res['trades'].sum()}")

    print("\nКритерии V2.4.1:")
    pfs = res["pf"].replace("inf", 99).astype(float)
    print(f"  PF > 1.3 на OOS:  {'OK' if (pfs > 1.3).sum() >= len(res) * 0.6 else 'FAIL'}")
    print(f"  Max DD < 15%:     {'OK' if res['dd'].min() > -15 else 'FAIL'}")
    print(f"  Сделок OOS > 30:  {'OK' if res['trades'].sum() > 30 else 'FAIL'}")

    out = RESULTS_DIR / f"wf_{a.file.replace('.csv', '')}_{datetime.now():%Y%m%d_%H%M}.csv"
    res.to_csv(out, index=False)
    print(f"\nСохранено: {out}")


if __name__ == "__main__":
    main()