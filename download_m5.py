"""Скачивание M5-данных газа: NGU6 и NGV6."""

import time
import pandas as pd
import requests


def download(ticker, start, end, out_csv):
    base_url = ("https://iss.moex.com/iss/engines/futures/markets/forts/"
                f"securities/{ticker}/candles.json")
    rows, columns, s = [], None, 0
    while True:
        r = requests.get(base_url,
                         params={"from": start, "till": end, "interval": 5, "start": s},
                         timeout=30)
        r.raise_for_status()
        c = r.json()["candles"]
        if columns is None:
            columns = c["columns"]
        if not c["data"]:
            break
        rows.extend(c["data"])
        print(f"  {ticker}: {len(rows)} свечей...")
        if len(c["data"]) < 500:
            break
        s += len(c["data"])
        time.sleep(0.3)
    df = pd.DataFrame(rows, columns=columns)
    df["begin"] = pd.to_datetime(df["begin"])
    df = df.set_index("begin").sort_index()
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                             "close": "Close", "volume": "Volume"})
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df = df[df["Volume"] > 0]
    df.to_csv(out_csv)
    print(f"Сохранено: {out_csv}")
    print(f"Баров: {len(df)}")
    print(f"Период: {df.index[0]} — {df.index[-1]}\n")
    return df


if __name__ == "__main__":
    print("Качаем NGU6 (июль–сентябрь)...")
    download("NGU6", "2026-07-01", "2026-09-25", "ngu6_m5.csv")

    print("Качаем NGV6 (сентябрь–октябрь)...")
    download("NGV6", "2026-09-01", "2026-10-13", "ngv6_m5.csv")