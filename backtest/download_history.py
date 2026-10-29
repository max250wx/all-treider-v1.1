"""Скачивает исторические свечи через T-Invest API.
UID получаем через find_instrument (get_instrument_by не работает с figi в этой версии SDK).
"""

import argparse
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv
from t_tech.invest import CandleInterval, Client

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)
with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

TOKEN = os.environ["T_INVEST_TOKEN"]
HISTORY_DIR = ROOT / "data" / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

TICKERS = {
    "SBER": "TQBR",
    "GAZP": "TQBR",
    "LKOH": "TQBR",
    "VTBR": "TQBR",
    "ROSN": "TQBR",
    "GMKN": "TQBR",
    "NVTK": "TQBR",
    "TATN": "TQBR",
}

INTERVALS = {
    "M1": CandleInterval.CANDLE_INTERVAL_1_MIN,
    "M5": CandleInterval.CANDLE_INTERVAL_5_MIN,
    "M15": CandleInterval.CANDLE_INTERVAL_15_MIN,
    "H1": CandleInterval.CANDLE_INTERVAL_HOUR,
}


def get_uid(client, ticker, class_code="TQBR"):
    """Ищем инструмент нужного класса (TQBR) с доступом через API."""
    try:
        r = client.instruments.find_instrument(query=ticker)
        # фильтр: ticker совпадает, class_code = TQBR, api_trade_available_flag = True
        matches = [
            i
            for i in r.instruments
            if i.ticker == ticker and i.class_code == class_code and i.api_trade_available_flag
        ]
        if not matches:
            # fallback: любой с api_trade_available_flag=True
            matches = [
                i for i in r.instruments if i.ticker == ticker and i.api_trade_available_flag
            ]
        if not matches:
            return None, None
        inst = matches[0]
        return inst.uid, inst.name
    except Exception as e:
        print(f"  поиск {ticker}: {e}")
        return None, None


def get_candles(client, uid, interval, days_back=365):
    end = datetime.now(UTC)
    start = end - timedelta(days=days_back)
    all_candles = []
    cursor = start
    errors = 0
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=7), end)
        try:
            r = client.market_data.get_candles(
                instrument_id=uid,
                from_=cursor,
                to=chunk_end,
                interval=interval,
            )
            all_candles.extend(r.candles)
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  ошибка {cursor:%Y-%m-%d}: {str(e)[:100]}")
        cursor = chunk_end
        time.sleep(0.15)
    if errors > 3:
        print(f"  всего ошибок: {errors}")
    return all_candles


def to_df(candles):
    rows = []
    for c in candles:
        rows.append(
            {
                "timestamp": c.time,
                "open": c.open.units + c.open.nano / 1e9,
                "high": c.high.units + c.high.nano / 1e9,
                "low": c.low.units + c.low.nano / 1e9,
                "close": c.close.units + c.close.nano / 1e9,
                "volume": c.volume,
            }
        )
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.set_index("timestamp").sort_index()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="SBER,GAZP,LKOH")
    ap.add_argument("--intervals", default="M5")
    ap.add_argument("--days", type=int, default=365)
    a = ap.parse_args()

    tickers = [t.strip().upper() for t in a.tickers.split(",")]
    intervals = [i.strip().upper() for i in a.intervals.split(",")]

    print(f"Скачиваю {tickers} за {a.days} дней, интервалы: {intervals}\n")

    with Client(TOKEN) as client:
        for ticker in tickers:
            uid, name = get_uid(client, ticker)
            if not uid:
                print(f"{ticker}: UID не получен, пропуск")
                continue
            print(f"{ticker} ({name}) uid={uid[:12]}...")

            for tf in intervals:
                if tf not in INTERVALS:
                    print(f"  {tf}: неизвестный интервал")
                    continue
                print(f"  {tf}:")
                candles = get_candles(client, uid, INTERVALS[tf], a.days)
                print(f"    получено: {len(candles)} свечей")
                if not candles:
                    continue
                df = to_df(candles)
                out = HISTORY_DIR / f"{ticker}_{tf}.csv"
                df.to_csv(out)
                print(
                    f"    сохранено: {out.name} "
                    f"({len(df)} строк, "
                    f"{df.index[0]:%Y-%m-%d} — {df.index[-1]:%Y-%m-%d})"
                )


if __name__ == "__main__":
    main()
