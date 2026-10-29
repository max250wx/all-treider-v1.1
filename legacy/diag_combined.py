"""Распределение book_imbalance и trade_imbalance в combined_data.csv."""

import pandas as pd
import numpy as np

df = pd.read_csv("combined_data.csv", parse_dates=True, index_col="timestamp")
print("Строк:", len(df))
print()

for col in ["book_imbalance", "trade_imbalance", "news_sentiment"]:
    if col not in df.columns:
        print(f"{col}: НЕТ")
        continue
    s = df[col].dropna()
    print(f"{col}:")
    print(f"  min     = {s.min():.3f}")
    print(f"  10%     = {s.quantile(0.10):.3f}")
    print(f"  25%     = {s.quantile(0.25):.3f}")
    print(f"  median  = {s.median():.3f}")
    print(f"  75%     = {s.quantile(0.75):.3f}")
    print(f"  90%     = {s.quantile(0.90):.3f}")
    print(f"  max     = {s.max():.3f}")
    print(f"  среднее = {s.mean():.3f}")
    print()

# Комбинации, при которых срабатывает вход
bi = df["book_imbalance"]
ti = df["trade_imbalance"]

print("=" * 60)
print("Сколько баров проходят фильтры:")
print()

for bthr in [0.05, 0.10, 0.15, 0.20]:
    for tthr in [0.05, 0.10, 0.15]:
        long_cnt = ((bi > bthr) & (ti > tthr)).sum()
        short_cnt = ((bi < -bthr) & (ti < -tthr)).sum()
        print(f"  book>{bthr:.2f} & trade>{tthr:.2f}:  long={long_cnt:3d}  short={short_cnt:3d}  всего={long_cnt+short_cnt}")
    print()

print("=" * 60)
print("Со сглаживанием SMA(3):")
bi_ma = bi.rolling(3).mean()
ti_ma = ti.rolling(3).mean()

for bthr in [0.05, 0.10, 0.15]:
    for tthr in [0.05, 0.10, 0.15]:
        long_cnt = ((bi_ma > bthr) & (ti_ma > tthr)).sum()
        short_cnt = ((bi_ma < -bthr) & (ti_ma < -tthr)).sum()
        print(f"  book>{bthr:.2f} & trade>{tthr:.2f}:  long={long_cnt:3d}  short={short_cnt:3d}  всего={long_cnt+short_cnt}")
