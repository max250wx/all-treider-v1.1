"""
Анализ влияния новостей на цену (v2).
Фильтр: только явно позитивные/негативные новости (|sent| > 0.5).
"""

import os
from datetime import timedelta

import numpy as np
import pandas as pd

MIN_ABS_SENTIMENT = 0.5  # игнорируем нейтральные
MIN_SAMPLES = 10  # минимум наблюдений в группе


def load_news():
    df = pd.read_csv("news_sentiment.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])
    df = df[df["sentiment"].abs() >= MIN_ABS_SENTIMENT]  # ← ФИЛЬТР
    return df.sort_values("timestamp").reset_index(drop=True)


def load_prices(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["mid"] = (df["bid1_price"] + df["ask1_price"]) / 2
    return df[["timestamp", "mid"]].set_index("timestamp")


def analyze(news, prices, ticker, horizons=(5, 15, 30)):
    results = []
    for _, row in news.iterrows():
        ts = row["timestamp"]
        sent = row["sentiment"]

        before = prices[prices.index <= ts]
        if before.empty:
            continue
        p0 = before["mid"].iloc[-1]

        for h in horizons:
            after = prices[prices.index >= ts + timedelta(minutes=h)]
            if after.empty:
                continue
            p1 = after["mid"].iloc[0]
            results.append(
                {
                    "ticker": ticker,
                    "sentiment": sent,
                    "horizon": h,
                    "change_pct": (p1 / p0 - 1) * 100,
                }
            )

    return pd.DataFrame(results)


def bootstrap_mean(values, n_iter=1000):
    """95% доверительный интервал для среднего."""
    if len(values) < 5:
        return None, None
    rng = np.random.default_rng(42)
    means = [rng.choice(values, size=len(values), replace=True).mean() for _ in range(n_iter)]
    return np.percentile(means, 2.5), np.percentile(means, 97.5)


def report(df, ticker):
    if df.empty:
        print(f"  {ticker}: нет данных")
        return

    print()
    print(f"  ── {ticker} ──")
    print(f"  Всего новостей: {len(df)} (|sent| >= {MIN_ABS_SENTIMENT})")
    print()

    for h in sorted(df["horizon"].unique()):
        sub = df[df["horizon"] == h]
        pos = sub[sub["sentiment"] > 0]["change_pct"].values
        neg = sub[sub["sentiment"] < 0]["change_pct"].values

        print(f"  Горизонт {h:>3} мин:")

        if len(pos) >= MIN_SAMPLES:
            m = pos.mean()
            lo, hi = bootstrap_mean(pos)
            mark = (
                " ✓" if lo is not None and lo > 0 else (" ✗" if hi is not None and hi < 0 else "")
            )
            print(
                f"    позитивные (N={len(pos):>3}): {m:+.4f}%  [95% CI: {lo:+.4f}..{hi:+.4f}]{mark}"
            )
        else:
            print(f"    позитивные: мало данных (N={len(pos)})")

        if len(neg) >= MIN_SAMPLES:
            m = neg.mean()
            lo, hi = bootstrap_mean(neg)
            mark = (
                " ✓" if lo is not None and lo > 0 else (" ✗" if hi is not None and hi < 0 else "")
            )
            print(
                f"    негативные (N={len(neg):>3}): {m:+.4f}%  [95% CI: {lo:+.4f}..{hi:+.4f}]{mark}"
            )
        else:
            print(f"    негативные: мало данных (N={len(neg)})")

        print()


if __name__ == "__main__":
    print("=" * 78)
    print("  АНАЛИЗ ВЛИЯНИЯ НОВОСТЕЙ v2 (только |sent| >= 0.5)")
    print("=" * 78)

    news = load_news()
    print(f"\nНовостей после фильтра: {len(news)}")

    for ticker in ["GAZP", "RUAL"]:
        prices = load_prices(f"orderbook_{ticker}.csv")
        if prices.empty:
            print(f"  {ticker}: нет prices")
            continue
        df = analyze(news, prices, ticker)
        report(df, ticker)

    print("=" * 78)
    print("  ИНТЕРПРЕТАЦИЯ:")
    print("  ✓ — доверительный интервал не содержит нуля → сигнал значим")
    print("  ✗ — обратный сигнал значим")
    print("  без метки — статистически не значимо")
    print("=" * 78)
