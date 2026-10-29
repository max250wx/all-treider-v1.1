"""Скачивает IMOEX M10 через MOEX ISS (индексы, не акции)."""

import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/history/IMOEX_M10.csv"
OUT.parent.mkdir(parents=True, exist_ok=True)


def fetch(ticker, interval, days=365):
    now = datetime.now()
    date_from = now - timedelta(days=days)
    all_rows, cols = [], None
    start = 0
    while True:
        url = f"https://iss.moex.com/iss/engines/stock/markets/index/boards/SNDX/securities/{ticker}/candles.json"
        params = {
            "interval": interval,
            "from": date_from.strftime("%Y-%m-%d"),
            "till": now.strftime("%Y-%m-%d"),
            "start": start,
            "iss.meta": "off",
        }
        payload = None
        for attempt in range(3):
            try:
                r = requests.get(
                    url, params=params, timeout=30, headers={"User-Agent": "Mozilla/5.0"}
                )
                r.raise_for_status()
                payload = r.json()
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2**attempt)
                else:
                    print(f"err: {e}")
        if payload is None:
            break
        c = payload.get("candles", {})
        if cols is None:
            cols = c.get("columns", [])
        rows = c.get("data", [])
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < 500:
            break
        start += 500
        time.sleep(0.3)
    return cols, all_rows


print("Скачиваю IMOEX M10...")
cols, rows = fetch("IMOEX", 10, 365)
print(f"получено: {len(rows)} свечей")
if not rows:
    raise SystemExit(1)
df = pd.DataFrame(rows, columns=cols).rename(columns={"begin": "timestamp"})
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.set_index("timestamp").sort_index()[["open", "high", "low", "close", "volume"]]
df.to_csv(OUT)
print(f"сохранено: {OUT} ({len(df)} строк, {df.index[0]:%Y-%m-%d} — {df.index[-1]:%Y-%m-%d})")
