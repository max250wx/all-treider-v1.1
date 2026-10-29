"""Скачивание газа за 6 месяцев — сшиваем последовательные контракты."""

import time
import pandas as pd
import requests


def download(ticker, start, end):
    base_url = ("https://iss.moex.com/iss/engines/futures/markets/forts/"
                f"securities/{ticker}/candles.json")
    rows_out, columns, s = [], None, 0
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
        rows_out.extend(c["data"])
        print(f"  {ticker}: {len(rows_out)} свечей...")
        if len(c["data"]) < 500:
            break
        s += len(c["data"])
        time.sleep(0.3)
    df = pd.DataFrame(rows_out, columns=columns)
    if df.empty:
        return None
    df["begin"] = pd.to_datetime(df["begin"])
    df = df.set_index("begin").sort_index()
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                             "close": "Close", "volume": "Volume"})
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


if __name__ == "__main__":
    print("Качаем последовательные контракты газа...")
    dfs = []
    for ticker, start, end in [
        ("NGQ6", "2026-05-01", "2026-07-28"),  # NG-8.26
        ("NGU6", "2026-07-15", "2026-09-28"),  # NG-9.26
        ("NGV6", "2026-09-15", "2026-10-28"),  # NG-10.26
    ]:
        d = download(ticker, start, end)
        if d is not None:
            print(f"  {ticker}: {len(d)} баров")
            dfs.append(d)

    if dfs:
        full = pd.concat(dfs).sort_index()
        full = full[~full.index.duplicated(keep="first")]
        full = full[full["Volume"] > 0]
        full.to_csv("ng_long.csv")
        print(f"\nСохранено: ng_long.csv")
        print(f"Баров: {len(full)}")
        print(f"Период: {full.index[0]} — {full.index[-1]}")
        print(f"Цена: {full['Close'].min():.3f} … {full['Close'].max():.3f}")