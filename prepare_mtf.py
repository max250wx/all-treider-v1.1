"""
Подготовка многотаймфреймовых данных.
Из M1 строим M15 (вход), H1, H4, D1 (фильтры тренда).
Добавляем колонки d1_trend / h4_trend / h1_trend без look-ahead bias.
"""

import pandas as pd
import numpy as np


def prepare_mtf(in_csv, entry_tf, out_csv, label):
    print(f"\n=== {label}: {in_csv} ===")
    df = pd.read_csv(in_csv, parse_dates=True, index_col=0)
    df = df.rename(columns={
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume",
    })
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df = df[df["Volume"] > 0].sort_index()

    # ── Entry TF ──
    entry = df.resample(entry_tf).agg({
        "Open": "first", "High": "max", "Low": "min",
        "Close": "last", "Volume": "sum",
    }).dropna()
    entry = entry[entry["Volume"] > 0]
    print(f"  Entry TF ({entry_tf}): {len(entry)} баров")

    # ── H1 ──
    h1 = df.resample("1h").agg({"Close": "last"}).dropna()
    h1["fast"] = h1["Close"].ewm(span=9, adjust=False).mean()
    h1["slow"] = h1["Close"].ewm(span=21, adjust=False).mean()
    h1["h1_trend"] = (h1["fast"] > h1["slow"]).astype(int)
    # Сдвигаем на момент закрытия H1-бара
    h1_idx = h1.index + pd.Timedelta(hours=1)
    h1 = h1[["h1_trend"]].copy()
    h1.index = h1_idx
    print(f"  H1: {len(h1)} баров")

    # ── H4 ──
    h4 = df.resample("4h").agg({"Close": "last"}).dropna()
    h4["fast"] = h4["Close"].ewm(span=20, adjust=False).mean()
    h4["slow"] = h4["Close"].ewm(span=50, adjust=False).mean()
    h4["h4_trend"] = (h4["fast"] > h4["slow"]).astype(int)
    h4_idx = h4.index + pd.Timedelta(hours=4)
    h4 = h4[["h4_trend"]].copy()
    h4.index = h4_idx
    print(f"  H4: {len(h4)} баров")

    # ── D1 ──
    d1 = df.resample("1D").agg({"Close": "last"}).dropna()
    d1["ema"] = d1["Close"].ewm(span=20, adjust=False).mean()
    d1["d1_trend"] = (d1["Close"] > d1["ema"]).astype(int)
    d1_idx = d1.index + pd.Timedelta(days=1)
    d1 = d1[["d1_trend"]].copy()
    d1.index = d1_idx
    print(f"  D1: {len(d1)} баров")

    # ── Merge HTF trends onto entry TF ──
    entry = entry.join(h1.reindex(entry.index, method="ffill"))
    entry = entry.join(h4.reindex(entry.index, method="ffill"))
    entry = entry.join(d1.reindex(entry.index, method="ffill"))
    entry = entry.dropna()

    # Переименуем в капитализированные имена для backtesting.py
    entry = entry.rename(columns={
        "h1_trend": "H1Trend", "h4_trend": "H4Trend", "d1_trend": "D1Trend",
    })

    entry.to_csv(out_csv)
    print(f"  → Сохранено: {out_csv}")
    print(f"  Баров на entry TF: {len(entry)}")
    print(f"  Период: {entry.index[0]} — {entry.index[-1]}")
    print(f"  Цена: {entry['Close'].min():.3f} … {entry['Close'].max():.3f}")
    return entry


if __name__ == "__main__":
    prepare_mtf("ngu6_m1.csv", "15min", "ngu6_mtf.csv", "NGU6 газ")
    prepare_mtf("ng_m1.csv",   "15min", "ngv6_mtf.csv", "NGV6 газ")
    prepare_mtf("sber_m1.csv", "15min", "sber_mtf.csv", "SBER акции")