"""IMOEX M10 через MOEX ISS (T-Invest не отдаёт индексы).
Пишет data/live/candles_IMOEX.csv каждые 10 минут.
"""
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)
OUT = ROOT / CFG["paths"]["data_live"] / "candles_IMOEX.csv"
OUT.parent.mkdir(parents=True, exist_ok=True)
POLL_MIN = CFG["collectors"].get("candles_interval_min", 10)


def fetch(days=7):
    now = datetime.now()
    url = "https://iss.moex.com/iss/engines/stock/markets/index/boards/SNDX/securities/IMOEX/candles.json"
    all_rows, cols = [], None
    start = 0
    while True:
        params = {"interval": 10, "from": (now-timedelta(days=days)).strftime("%Y-%m-%d"),
                  "till": now.strftime("%Y-%m-%d"), "start": start, "iss.meta": "off"}
        payload = None
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
                payload = r.json()
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2**attempt)
                else:
                    print(f"  err: {e}")
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


def run(once=False):
    while True:
        cols, rows = fetch(days=7)
        if rows and cols:
            df = pd.DataFrame(rows, columns=cols).rename(columns={"begin": "timestamp"})
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp").sort_index()
            df = df[["open", "high", "low", "close", "volume"]]
            df.to_csv(OUT)
            print(f"[{datetime.now():%H:%M:%S}] IMOEX: {len(df)} баров, последний {df.index[-1]:%Y-%m-%d %H:%M}")
        else:
            print(f"[{datetime.now():%H:%M:%S}] IMOEX: 0 свечей")
        if once:
            break
        time.sleep(POLL_MIN * 60)


if __name__ == "__main__":
    import sys
    run(once="--once" in sys.argv)