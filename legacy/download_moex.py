"""Скачивает историю через MOEX ISS (M10, H1, D1) за год.
M10 — ближайший к M5 доступный интервал.
"""

import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)
HISTORY_DIR = ROOT / "data" / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

TICKERS = ["SBER", "GAZP", "LKOH", "VTBR", "ROSN"]

# interval: 1=1min, 10=10min, 60=1h, 24=1d
INTERVALS = {
    "M10": 10,
    "H1": 60,
    "D1": 24,
}


def fetch_candles(ticker, board, interval, date_from, date_till, retries=3):
    """Скачивает все свечи через пагинацию (start=0, 500, 1000...)."""
    all_rows = []
    columns = None
    start = 0
    while True:
        url = (
            f"https://iss.moex.com/iss/engines/stock/markets/shares/"
            f"boards/{board}/securities/{ticker}/candles.json"
        )
        params = {
            "interval": interval,
            "from": date_from.strftime("%Y-%m-%d"),
            "till": date_till.strftime("%Y-%m-%d"),
            "start": start,
            "iss.meta": "off",
        }
        payload = None
        for attempt in range(retries):
            try:
                r = requests.get(
                    url,
                    params=params,
                    timeout=30,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                r.raise_for_status()
                payload = r.json()
                break
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                else:
                    print(f"    ошибка start={start}: {e}")
        if payload is None:
            break

        candles = payload.get("candles", {})
        cols = candles.get("columns", [])
        rows = candles.get("data", [])
        if columns is None:
            columns = cols
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < 500:
            break
        start += 500
        time.sleep(0.3)
    return columns, all_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default=",".join(TICKERS))
    ap.add_argument("--intervals", default="M10")
    ap.add_argument("--days", type=int, default=365)
    a = ap.parse_args()

    tickers = [t.strip().upper() for t in a.tickers.split(",")]
    intervals = [i.strip().upper() for i in a.intervals.split(",")]

    now = datetime.now()
    date_from = now - timedelta(days=a.days)
    date_till = now
    print(f"Скачиваю через MOEX ISS, период {date_from:%Y-%m-%d} — {date_till:%Y-%m-%d}")
    print(f"Тикеры: {tickers}, интервалы: {intervals}\n")

    for ticker in tickers:
        for tf in intervals:
            if tf not in INTERVALS:
                print(f"{tf}: неизвестный интервал, пропуск")
                continue
            print(f"{ticker} {tf}:")
            cols, rows = fetch_candles(ticker, "TQBR", INTERVALS[tf], date_from, date_till)
            print(f"  получено: {len(rows)} свечей")
            if not rows or not cols:
                continue

            df = pd.DataFrame(rows, columns=cols)
            df = df.rename(columns={"begin": "timestamp"})
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=False)
            df = df.set_index("timestamp").sort_index()
            df = df[["open", "high", "low", "close", "volume"]]

            out = HISTORY_DIR / f"{ticker}_{tf}.csv"
            df.to_csv(out)
            print(
                f"  сохранено: {out.name} "
                f"({len(df)} строк, "
                f"{df.index[0]:%Y-%m-%d} — {df.index[-1]:%Y-%m-%d})\n"
            )


if __name__ == "__main__":
    main()
