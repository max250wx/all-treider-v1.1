"""Скачивание NGX6 и NGZ6 за доступный период (сентябрь-октябрь 2026)."""

import time
import pandas as pd
import requests


def download(ticker, start, end, out_csv):
    base_url = ("https://iss.moex.com/iss/engines/futures/markets/forts/"
                f"securities/{ticker}/candles.json")
    rows, columns, s = [], None, 0
    while True:
        r = requests.get(base_url,
                         params={"from": start, "till": end, "interval": 1, "start": s},
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
    if df.empty:
        print(f"  {ticker}: 0 свечей (нет данных за период)")
        return None
    df["begin"] = pd.to_datetime(df["begin"])
    df = df.set_index("begin").sort_index()
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                             "close": "Close", "volume": "Volume"})
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df = df[df["Volume"] > 0]
    df.to_csv(out_csv)
    print(f"  Сохранено: {out_csv}, баров M1: {len(df)}")
    print(f"  Период: {df.index[0]} — {df.index[-1]}")
    print(f"  Цена: {df['Close'].min():.3f} … {df['Close'].max():.3f}")

    # M5-агрегация
    df_m5 = df.resample("5min").agg({
        "Open": "first", "High": "max", "Low": "min",
        "Close": "last", "Volume": "sum",
    }).dropna()
    df_m5 = df_m5[df_m5["Volume"] > 0]
    out_m5 = out_csv.replace("_m1", "_m5")
    df_m5.to_csv(out_m5)
    print(f"  Сохранено: {out_m5}, баров M5: {len(df_m5)}")
    print()
    return df_m5


if __name__ == "__main__":
    # Пробуем разные стартовые даты — биржа отдаёт то, что есть
    print("=== NGX6 (NG-11.26) ===")
    download("NGX6", "2026-09-15", "2026-10-13", "ngx6_m1.csv")

    print("=== NGZ6 (NG-12.26) ===")
    download("NGZ6", "2026-09-15", "2026-10-13", "ngz6_m1.csv")