"""Диагностика: почему в июле-августе нет сделок."""

import pandas as pd

df = pd.read_csv("ngu6_mtf.csv", parse_dates=True, index_col=0)
print("Всего баров:", len(df))
print("Период:", df.index[0], "—", df.index[-1])
print("")

# Сколько каждого тренда
print("D1Trend=1: {} ({:.1f}%)".format(
    (df["D1Trend"] == 1).sum(),
    100 * (df["D1Trend"] == 1).mean()))
print("H4Trend=1: {} ({:.1f}%)".format(
    (df["H4Trend"] == 1).sum(),
    100 * (df["H4Trend"] == 1).mean()))
print("H1Trend=1: {} ({:.1f}%)".format(
    (df["H1Trend"] == 1).sum(),
    100 * (df["H1Trend"] == 1).mean()))
print("")

# Разбивка по окнам
n_windows = 5
total = len(df)
block_size = total // (n_windows + 1)

for k in range(n_windows):
    start = block_size * (k + 1)
    end = block_size * (k + 2)
    w = df.iloc[start:end]
    if len(w) == 0:
        continue

    strict_long = ((w["D1Trend"] == 1) & (w["H4Trend"] == 1) & (w["H1Trend"] == 1)).sum()
    strict_short = ((w["D1Trend"] == 0) & (w["H4Trend"] == 0) & (w["H1Trend"] == 0)).sum()

    up_count_2plus = ((w["D1Trend"] + w["H4Trend"] + w["H1Trend"]) >= 2).sum()
    down_count_2plus = ((w["D1Trend"] + w["H4Trend"] + w["H1Trend"]) <= 1).sum()

    print(f"Окно {k+1}: {w.index[0].date()}…{w.index[-1].date()}")
    print(f"  Баров: {len(w)}")
    print(f"  D1=1: {(w['D1Trend']==1).sum()}, H4=1: {(w['H4Trend']==1).sum()}, H1=1: {(w['H1Trend']==1).sum()}")
    print(f"  strict allow_long:  {strict_long}")
    print(f"  strict allow_short: {strict_short}")
    print(f"  2of3 up:  {up_count_2plus}")
    print(f"  2of3 down: {down_count_2plus}")
    print("")