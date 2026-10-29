"""Live scalper: RSI mean-reversion на LKOH+VTBR+ROSN с IMOEX-фильтром.
Не торгует — только сигналы (dry-run). Ордера не выставляет.
Пишет в results/journal/signals.csv.
"""
import csv
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

DATA_DIR = ROOT / CFG["paths"]["data_live"]
RESULTS_DIR = ROOT / CFG["paths"]["results"] / "journal"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
SIGNALS_CSV = RESULTS_DIR / "signals.csv"

STRAT = CFG["rsi_strategy"]
LIVE = CFG["live"]

TICKERS = [t for t in CFG["collectors"]["tickers"] if t != "IMOEX"]
DEPOSIT = LIVE.get("deposit", 200000)
RISK = STRAT["risk_per_trade"]
MAX_EXP = STRAT["max_exposure"]
ATR_MULT = STRAT["atr_stop_mult"]
TP_R = STRAT["tp_r_mult"]
RSI_P = STRAT["rsi_period"]
RSI_LO = STRAT["rsi_lo"]
RSI_HI = STRAT["rsi_hi"]
RSI_EXIT = STRAT["rsi_exit"]
EMA_TREND = STRAT["ema_trend"]
SESSION_START = STRAT["session_start_utc"]
SESSION_END = STRAT["session_end_utc"]
COOLDOWN_SEC = LIVE["cooldown_sec"]

# Telegram (опционально)
try:
    import sys
    sys.path.insert(0, str(ROOT))
    from bot.telegram import send_signal, enabled as tg_on
except Exception:
    send_signal = None
    def tg_on(): return False


def load_candles(ticker):
    p = DATA_DIR / f"candles_{ticker}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    return df.sort_index()


def add_indicators(df):
    c = df["close"]
    df["ema"] = c.ewm(span=EMA_TREND, adjust=False).mean()
    d = c.diff()
    g = d.where(d > 0, 0).ewm(alpha=1 / RSI_P, adjust=False).mean()
    l = (-d.where(d < 0, 0)).ewm(alpha=1 / RSI_P, adjust=False).mean()
    df["rsi"] = 100 - 100 / (1 + g / l.replace(0, np.nan))
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - c.shift()).abs(),
        (df["low"] - c.shift()).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    return df.dropna()


def imoex_filter():
    """True = LONG разрешён, False = SHORT разрешён, None = нет данных."""
    df = load_candles("IMOEX")
    if df is None or len(df) < EMA_TREND:
        return None
    imoex_ema = df["close"].ewm(span=EMA_TREND, adjust=False).mean().iloc[-1]
    imoex_last = df["close"].iloc[-1]
    return imoex_last > imoex_ema


def signal_for(ticker, imoex_up):
    df = load_candles(ticker)
    if df is None or len(df) < EMA_TREND + 10:
        return None

    df = add_indicators(df)
    last = df.iloc[-1]
    prev = df.iloc[-2]
    hour = df.index[-1].hour

    # Вне сессии — не входим
    if not (SESSION_START <= hour < SESSION_END):
        return {"ticker": ticker, "action": "-", "reason": "out_of_session"}

    price = last["close"]
    rsi = last["rsi"]
    ema = last["ema"]
    atr = last["atr"]

    # Проверка триггера
    long_cond = price > ema and rsi < RSI_LO and imoex_up is True
    short_cond = price < ema and rsi > RSI_HI and imoex_up is False

    if long_cond:
        side = "LONG"
    elif short_cond:
        side = "SHORT"
    else:
        return {"ticker": ticker, "action": "-", "reason": "no_signal",
                "price": price, "rsi": rsi, "ema": ema}

    # Размер позиции и стопы
    if side == "LONG":
        stop = price - ATR_MULT * atr
        risk = price - stop
        tp = price + TP_R * risk
    else:
        stop = price + ATR_MULT * atr
        risk = stop - price
        tp = price - TP_R * risk

    if risk <= 0:
        return {"ticker": ticker, "action": "-", "reason": "bad_risk"}

    qty = min(int((DEPOSIT * RISK) / risk), int((DEPOSIT * MAX_EXP) / price))

    return {
        "ticker": ticker, "action": side, "price": price,
        "rsi": rsi, "ema": ema, "atr": atr,
        "stop": stop, "tp": tp, "qty": qty,
    }


def log_signal(sig):
    header = not SIGNALS_CSV.exists()
    with open(SIGNALS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if header:
            w.writerow(["ts", "ticker", "side", "price", "rsi", "ema",
                        "atr", "stop", "tp", "qty", "imoex_up"])
        w.writerow([
            datetime.now().isoformat(timespec="seconds"),
            sig["ticker"], sig["action"], round(sig["price"], 2),
            round(sig["rsi"], 2), round(sig["ema"], 2), round(sig["atr"], 3),
            round(sig["stop"], 2), round(sig["tp"], 2), sig["qty"],
            sig.get("imoex_up"),
        ])


def run():
    print(f"[scalper] старт. Тикеры: {TICKERS}")
    print(f"[scalper] RSI({RSI_P}) <{RSI_LO} LONG, >{RSI_HI} SHORT")
    print(f"[scalper] EMA{EMA_TREND}, сессия {SESSION_START}-{SESSION_END} UTC")
    print(f"[scalper] cooldown {COOLDOWN_SEC}s, депозит {DEPOSIT}, риск {RISK*100:.1f}%")
    print(f"[scalper] пишу: {SIGNALS_CSV}\n")

    last_signal_ts = {t: 0.0 for t in TICKERS}
    last_side = {t: "-" for t in TICKERS}

    while True:
        try:
            imoex_up = imoex_filter()
            imoex_str = "UP" if imoex_up is True else "DN" if imoex_up is False else "?"

            line_parts = []
            for ticker in TICKERS:
                sig = signal_for(ticker, imoex_up)
                if sig is None:
                    line_parts.append(f"{ticker}: нет данных")
                    continue

                if sig["action"] == "-":
                    line_parts.append(f"{ticker}:- [{sig.get('reason','')}]")
                    last_side[ticker] = "-"
                    continue

                now = time.time()
                cool_ok = (now - last_signal_ts[ticker]) >= COOLDOWN_SEC
                new_side = sig["action"] != last_side[ticker]

                if new_side and cool_ok:
                    log_signal({**sig, "imoex_up": imoex_up})
                    print(f"  >>> {sig['action']} {ticker} @ {sig['price']:.2f} "
                          f"(RSI={sig['rsi']:.1f}, ATR={sig['atr']:.3f}, "
                          f"stop={sig['stop']:.2f}, tp={sig['tp']:.2f}, qty={sig['qty']})")
                    if send_signal and tg_on():
                        send_signal(ticker, sig["action"], 0, sig["price"])
                    last_signal_ts[ticker] = now
                    last_side[ticker] = sig["action"]

                line_parts.append(
                    f"{ticker}:{sig['action']} RSI={sig['rsi']:.1f} "
                    f"px={sig['price']:.2f}"
                )

            print(f"[{datetime.now():%H:%M:%S}] IMOEX={imoex_str} | " + " | ".join(line_parts))
            time.sleep(15)

        except KeyboardInterrupt:
            print("\n[scalper] остановлен")
            break
        except Exception as e:
            print(f"[scalper] ошибка: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run()