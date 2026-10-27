"""
Скачивание минутных свечей SBER через открытый API МосБиржи (ISS).
Без токена, без регистрации. Данные — с задержкой 15 минут.
"""

import time
import pandas as pd
import requests


def download_sber(start_date="2026-09-01", end_date="2026-10-13"):
    """Скачивает M1-свечи SBER (TQBR) и сохраняет в sber_m1.csv."""
    base_url = (
        "https://iss.moex.com/iss/engines/stock/markets/shares/"
        "boards/TQBR/securities/SBER/candles.json"
    )

    all_rows = []
    columns = None
    start = 0

    while True:
        params = {
            "from": start_date,
            "till": end_date,
            "interval": 1,        # 1 = минутные свечи
            "start": start,       # пагинация
        }
        resp = requests.get(base_url, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        candles = payload["candles"]
        if columns is None:
            columns = candles["columns"]

        rows = candles["data"]
        if not rows:
            break

        all_rows.extend(rows)
        print(f"  скачано {len(all_rows)} свечей...")

        # Пагинация: если пришло меньше 500 — это конец
        if len(rows) < 500:
            break

        start += len(rows)
        time.sleep(0.3)   # вежливая пауза

    df = pd.DataFrame(all_rows, columns=columns)
    if df.empty:
        raise RuntimeError("МосБиржа вернула пустой ответ")

    df["begin"] = pd.to_datetime(df["begin"])
    df = df.set_index("begin").sort_index()
    df = df.rename(columns={
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume",
    })
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df = df[df["Volume"] > 0]

    df.to_csv("sber_m1.csv")
    print(f"\nСохранено: sber_m1.csv")
    print(f"Баров: {len(df)}")
    print(f"Период: {df.index[0]} — {df.index[-1]}")
    print(f"Цена: {df['Close'].min():.2f} … {df['Close'].max():.2f}")
    return df


if __name__ == "__main__":
    download_sber(start_date="2026-09-01", end_date="2026-10-13")