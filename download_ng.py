"""Скачивание M1-свечей фьючерса на газ (NGV6 = NG-10.26)."""

import time
import pandas as pd
import requests


def download_ng(start_date="2026-09-01", end_date="2026-10-13"):
    ticker = "NGV6"    # ← короткий код
    base_url = (
        "https://iss.moex.com/iss/engines/futures/markets/forts/"
        f"securities/{ticker}/candles.json"
    )

    all_rows = []
    columns = None
    start = 0

    while True:
        params = {
            "from": start_date, "till": end_date,
            "interval": 1, "start": start,
        }
        resp = requests.get(base_url, params=params, timeout=30)
        resp.raise_for_status()
        candles = resp.json()["candles"]

        if columns is None:
            columns = candles["columns"]
        rows = candles["data"]
        if not rows:
            break

        all_rows.extend(rows)
        print(f"  скачано {len(all_rows)} свечей...")
        if len(rows) < 500:
            break
        start += len(rows)
        time.sleep(0.3)

    df = pd.DataFrame(all_rows, columns=columns)
    if df.empty:
        raise RuntimeError(f"Пустой ответ для {ticker}")

    df["begin"] = pd.to_datetime(df["begin"])
    df = df.set_index("begin").sort_index()
    df = df.rename(columns={
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume",
    })
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df = df[df["Volume"] > 0]
    df.to_csv("ng_m1.csv")

    print(f"\nСохранено: ng_m1.csv")
    print(f"Баров: {len(df)}")
    print(f"Период: {df.index[0]} — {df.index[-1]}")
    print(f"Цена: {df['Close'].min():.3f} … {df['Close'].max():.3f}")
    return df


if __name__ == "__main__":
    download_ng(start_date="2026-09-01", end_date="2026-10-13")