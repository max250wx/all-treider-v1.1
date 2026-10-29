"""Есть ли информация в book_imbalance и trade_imbalance?
Считаем корреляцию с будущей доходностью на разных горизонтах."""

import numpy as np
import pandas as pd

df = pd.read_csv("combined_data.csv", parse_dates=True, index_col="timestamp")
df = df.sort_index()

print(f"Баров: {len(df)}")
print(f"Период: {df.index[0]} — {df.index[-1]}")
print()

# Будущая доходность mid_price на разных горизонтах
for h in [1, 3, 6, 12, 24]:
    df[f"ret_fwd_{h}"] = df["mid_price"].shift(-h) / df["mid_price"] - 1

# Корреляции
print("=" * 70)
print("  КОРРЕЛЯЦИЯ С БУДУЩЕЙ ДОХОДНОСТЬЮ")
print("=" * 70)
print()
print(f"{'Горизонт':>10} | {'book_imb':>12} | {'trade_imb':>12} | {'microprice':>12}")
print("-" * 60)

for h in [1, 3, 6, 12, 24]:
    col = f"ret_fwd_{h}"
    sub = df[[col, "book_imbalance", "trade_imbalance"]].dropna()
    r_book = sub[col].corr(sub["book_imbalance"])
    r_trade = sub[col].corr(sub["trade_imbalance"])
    print(f"{h:>10} | {r_book:>12.4f} | {r_trade:>12.4f} |")

print()
print("Интерпретация:")
print("  |r| < 0.05   → нет связи")
print("  |r| 0.05-0.15 → слабая связь")
print("  |r| > 0.15   → значимая связь")

print()
print("=" * 70)
print("  КОРРЕЛЯЦИЯ book_imbalance × trade_imbalance")
print("=" * 70)
sub = df[["book_imbalance", "trade_imbalance"]].dropna()
r_bt = sub["book_imbalance"].corr(sub["trade_imbalance"])
print(f"  r(book, trade) = {r_bt:.4f}")

print()
print("=" * 70)
print("  БУДУЩЕЕ ДВИЖЕНИЕ ЦЕНЫ ПО КВАРТИЛЯМ book_imbalance")
print("=" * 70)
print()
print(f"{'Квартиль':>10} | {'N':>5} | {'Средний ret_fwd_6':>20}")
print("-" * 50)

df["book_q"] = pd.qcut(df["book_imbalance"], 4, labels=["Q1 low", "Q2", "Q3", "Q4 high"], duplicates="drop")
for q in ["Q1 low", "Q2", "Q3", "Q4 high"]:
    sub = df[df["book_q"] == q]
    if len(sub) > 0:
        mean_ret = sub["ret_fwd_6"].mean() * 100
        print(f"{q:>10} | {len(sub):>5} | {mean_ret:>20.4f}%")

print()
print("=" * 70)
print("  БУДУЩЕЕ ДВИЖЕНИЕ ЦЕНЫ ПО КВАРТИЛЯМ trade_imbalance")
print("=" * 70)
print()
df["trade_q"] = pd.qcut(df["trade_imbalance"], 4, labels=["Q1 low", "Q2", "Q3", "Q4 high"], duplicates="drop")
for q in ["Q1 low", "Q2", "Q3", "Q4 high"]:
    sub = df[df["trade_q"] == q]
    if len(sub) > 0:
        mean_ret = sub["ret_fwd_6"].mean() * 100
        print(f"{q:>10} | {len(sub):>5} | {mean_ret:>20.4f}%")