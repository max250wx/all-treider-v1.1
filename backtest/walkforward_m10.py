"""Walk-forward на M10 (данные MOEX ISS, время МСК).
Без trailing EMA50 (проверено, что он режет прибыль).
Partial TP 50% на 1R + стоп в БУ, остаток до 2R.
Сессия 10:00-18:00 МСК.
ATR-пороги подобраны под M10.
"""
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
SLIPPAGE_PCT = 0.0005   # 0.05% проскальзывание (акции TQBR)

# ATR-пороги под M10 (в 1.4x от M5)
ATR_NORMAL_MAX = 0.45
ATR_PANIC = 0.85
ATR_MIN = 0.04
ATR_MAX = 0.85

# HALT при санкционном шоке: ATR в 4x медианы (только реальные паники)
HALT_MULT = 4.0


def find_file(name):
    for cand in [ROOT / "data/history" / name]:
        if cand.exists():
            return cand
    return None


def load_csv(name):
    p = find_file(name)
    if p is None:
        print(f"ОШИБКА: {name} не найден в data/history")
        sys.exit(1)
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={"vol": "volume"})
    df = df[["open", "high", "low", "close", "volume"]].dropna()
    df = df[df["volume"] > 0].sort_index()
    print(f"{name}: {len(df)} баров "
          f"({df.index[0]:%Y-%m-%d} — {df.index[-1]:%Y-%m-%d})")
    return df


def add_indicators(df):
    c = df["close"]
    df["ema20"] = c.ewm(span=20, adjust=False).mean()
    df["ema50"] = c.ewm(span=50, adjust=False).mean()
    df["ema200"] = c.ewm(span=200, adjust=False).mean()

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - c.shift()).abs(),
        (df["low"] - c.shift()).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    df["atr_pct"] = df["atr"] / c * 100
    df["atr_median"] = df["atr_pct"].rolling(200).median()

    df["vol_sma"] = df["volume"].rolling(20).mean()
    tp = (df["high"] + df["low"] + c) / 3
    df["vwap"] = (tp * df["volume"]).rolling(50).sum() / df["volume"].rolling(50).sum()

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
        hour = df.index[i].hour

        if date != last_date:
            daily_pnl = 0.0
            last_date = date

        # ─── ВЫХОДЫ ───
        if position:
            exit_pnl = 0.0
            reason = None

            # HALT при санкционном шоке
            if pd.notna(row["atr_median"]) and row["atr_pct"] > HALT_MULT * row["atr_median"]:
                px = row["close"]
                if position["side"] == "LONG":
                    px *= (1 - SLIPPAGE_PCT)
                    exit_pnl = (px - position["entry"]) * position["qty"]
                else:
                    px *= (1 + SLIPPAGE_PCT)
                    exit_pnl = (position["entry"] - px) * position["qty"]
                reason = "halt_shock"

            # Stop (с учётом гэпа)
            if not reason:
                if position["side"] == "LONG" and row["low"] <= position["stop"]:
                    fill = min(position["stop"], row["open"])
                    fill *= (1 - SLIPPAGE_PCT)
                    exit_pnl = (fill - position["entry"]) * position["qty"]
                    reason = "stop_gap" if row["open"] < position["stop"] else "stop"
                elif position["side"] == "SHORT" and row["high"] >= position["stop"]:
                    fill = max(position["stop"], row["open"])
                    fill *= (1 + SLIPPAGE_PCT)
                    exit_pnl = (position["entry"] - fill) * position["qty"]
                    reason = "stop_gap" if row["open"] > position["stop"] else "stop"

            # TP2 (полное)
            if not reason:
                if position["side"] == "LONG" and row["high"] >= position["tp2"]:
                    exit_pnl = (position["tp2"] - position["entry"]) * position["qty"]
                    reason = "tp2"
                elif position["side"] == "SHORT" and row["low"] <= position["tp2"]:
                    exit_pnl = (position["entry"] - position["tp2"]) * position["qty"]
                    reason = "tp2"

            # TP1 (50%, стоп в БУ)
            if not reason and not position["partial_done"]:
                if position["side"] == "LONG" and row["high"] >= position["tp1"]:
                    q = position["qty"] * 0.5
                    pnl1 = (position["tp1"] - position["entry"]) * q
                    equity += pnl1
                    daily_pnl += pnl1
                    trades.append({"pnl": pnl1, "reason": "tp1_partial"})
                    position["qty"] -= q
                    position["stop"] = position["entry"]
                    position["partial_done"] = True
                elif position["side"] == "SHORT" and row["low"] <= position["tp1"]:
                    q = position["qty"] * 0.5
                    pnl1 = (position["entry"] - position["tp1"]) * q
                    equity += pnl1
                    daily_pnl += pnl1
                    trades.append({"pnl": pnl1, "reason": "tp1_partial"})
                    position["qty"] -= q
                    position["stop"] = position["entry"]
                    position["partial_done"] = True

            if reason:
                equity += exit_pnl
                daily_pnl += exit_pnl
                trades.append({"pnl": exit_pnl, "reason": reason})
                position = None

        # ─── ВХОДЫ ───
        if position is None and daily_pnl > -CAPITAL * DAILY_LOSS_LIMIT:
            # Сессия 10:00-18:00 МСК (данные MOEX ISS уже в МСК)
            if not (10 <= hour < 18):
                continue

            # HALT: не входим в панику
            if pd.notna(row["atr_median"]) and row["atr_pct"] > HALT_MULT * row["atr_median"]:
                continue

            regime = "SIDEWAYS"
            if row["ema20"] > row["ema50"] > row["ema200"] and row["close"] > row["ema20"]:
                regime = "UPTREND"
            elif row["ema20"] < row["ema50"] < row["ema200"] and row["close"] < row["ema20"]:
                regime = "DOWNTREND"

            if row["atr_pct"] < ATR_PANIC and ATR_MIN <= row["atr_pct"] <= ATR_MAX:
                obv_up = row["obv"] > df["obv"].iloc[i - 5] if i >= 5 else False
                obv_dn = row["obv"] < df["obv"].iloc[i - 5] if i >= 5 else False

                # LONG
                if (regime == "UPTREND" and row["close"] > prev["high"]
                        and row["volume"] >= row["vol_sma"]
                        and row["close"] > row["vwap"]
                        and obv_up and row["atr_pct"] < ATR_NORMAL_MAX):
                    entry = row["close"]
                    stop = entry - 2.0 * row["atr"]
                    risk = entry - stop
                    if risk > 0:
                        qty = min((CAPITAL * RISK_PER_TRADE) / risk,
                                  CAPITAL * MAX_EXPOSURE / entry)
                        position = {"side": "LONG", "entry": entry, "stop": stop,
                                    "tp1": entry + risk, "tp2": entry + 2 * risk,
                                    "qty": qty, "partial_done": False}

                # SHORT
                elif (regime == "DOWNTREND" and row["close"] < prev["low"]
                        and row["volume"] >= row["vol_sma"]
                        and row["close"] < row["vwap"]
                        and obv_dn and row["atr_pct"] < ATR_NORMAL_MAX):
                    entry = row["close"]
                    stop = entry + 2.0 * row["atr"]
                    risk = stop - entry
                    if risk > 0:
                        qty = min((CAPITAL * RISK_PER_TRADE) / risk,
                                  CAPITAL * MAX_EXPOSURE / entry)
                        position = {"side": "SHORT", "entry": entry, "stop": stop,
                                    "tp1": entry - risk, "tp2": entry - 2 * risk,
                                    "qty": qty, "partial_done": False}

        if equity > peak:
            peak = equity
        dd = (equity - peak) / peak
        if dd < max_dd:
            max_dd = dd

    return trades, equity, max_dd


def metrics(trades, equity_end, max_dd):
    if not trades:
        return {"trades": 0, "winrate": 0, "pf": 0, "pnl": 0, "dd": 0, "return_pct": 0}
    pnl = pd.Series([t["pnl"] for t in trades])
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
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
    }


def walk_forward(df, n_windows=6):
    size = len(df) // n_windows
    rows = []
    for k in range(n_windows):
        s = k * size
        e = (k + 1) * size if k < n_windows - 1 else len(df)
        chunk = df.iloc[s:e]
        if len(chunk) < 500:
            continue
        trades, eq, dd = run_backtest(chunk)
        m = metrics(trades, eq, dd)
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
    ap.add_argument("--file", required=True)
    ap.add_argument("--windows", type=int, default=6)
    a = ap.parse_args()

    df = load_csv(a.file)
    df = add_indicators(df)
    print(f"После индикаторов: {len(df)} баров")
    print(f"ATR%: min={df['atr_pct'].min():.3f} "
          f"median={df['atr_pct'].median():.3f} "
          f"max={df['atr_pct'].max():.3f}")
    print(f"Пороги: min={ATR_MIN} normal_max={ATR_NORMAL_MAX} "
          f"panic={ATR_PANIC} halt={HALT_MULT}x\n")

    print(f"Walk-forward M10: {a.windows} окон")
    res = walk_forward(df, n_windows=a.windows)
    print()

    if res.empty:
        print("Нет результатов")
        return

    print("=" * 100)
    print(res.to_string(index=False))
    print("=" * 100)

    prof = (res["return_pct"] > 0).sum()
    print(f"Прибыльных окон: {prof}/{len(res)} ({prof / len(res) * 100:.0f}%)")
    print(f"Средний PF:     {res['pf'].replace('inf', 99).astype(float).mean():.2f}")
    print(f"Медиана PF:     {res['pf'].replace('inf', 99).astype(float).median():.2f}")
    print(f"Средний return: {res['return_pct'].mean():+.2f}%")
    print(f"Средний DD:     {res['dd'].mean():.2f}%")
    print(f"Всего сделок:   {res['trades'].sum()}")

    print("\nКритерии V2.4.1:")
    pfs = res["pf"].replace("inf", 99).astype(float)
    print(f"  PF > 1.3 на OOS:  {'OK' if (pfs > 1.3).sum() >= len(res) * 0.6 else 'FAIL'}")
    print(f"  Max DD < 15%:     {'OK' if res['dd'].min() > -15 else 'FAIL'}")
    print(f"  Сделок OOS > 30:  {'OK' if res['trades'].sum() > 30 else 'FAIL'}")

    out = RESULTS_DIR / f"wf_m10_{a.file.replace('.csv', '')}_{datetime.now():%Y%m%d_%H%M}.csv"
    res.to_csv(out, index=False)
    print(f"\nСохранено: {out}")


if __name__ == "__main__":
    main()