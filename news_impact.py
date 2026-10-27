"""
Анализ влияния новостей на цену GAZP и RUAL.
Для каждой новости считаем изменение цены через 5/15/30/60 минут.
"""

import os
import pandas as pd
from datetime import timedelta


def load_news():
    if not os.path.exists("news_sentiment.csv"):
        return pd.DataFrame()
    df = pd.read_csv("news_sentiment.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def load_prices(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["mid"] = (df["bid1_price"] + df["ask1_price"]) / 2
    return df[["timestamp", "mid"]]


def analyze_impact(news, prices, ticker, horizons=(5, 15, 30, 60)):
    if news.empty or prices.empty:
        return pd.DataFrame()

    prices = prices.set_index("timestamp")
    results = []

    for _, row in news.iterrows():
        ts = row["timestamp"]
        sent = row["sentiment"]

        # Цена в момент новости (ближайшая до)
        before = prices[prices.index <= ts]
        if before.empty:
            continue
        price_before = before["mid"].iloc[-1]

        for h in horizons:
            after = prices[prices.index >= ts + timedelta(minutes=h)]
            if after.empty:
                continue
            price_after = after["mid"].iloc[0]
            change_pct = (price_after / price_before - 1) * 100

            results.append({
                "timestamp": ts,
                "ticker": ticker,
                "sentiment": sent,
                "horizon_min": h,
                "change_pct": change_pct,
                "title": str(row["title"])[:80],
            })

    return pd.DataFrame(results)


def print_report(df, ticker):
    if df.empty:
        print(f"  {ticker}: недостаточно данных для анализа")
        return

    print()
    print(f"  ── {ticker} ──")
    print()

    # Корреляции
    print(f"  Корреляция sentiment vs change_pct:")
    for h in sorted(df["horizon_min"].unique()):
        sub = df[df["horizon_min"] == h]
        if len(sub) < 5:
            print(f"    {h:>3} мин:  мало данных (N={len(sub)})")
            continue
        r = sub["sentiment"].corr(sub["change_pct"])
        mark = ""
        if abs(r) > 0.15:
            mark = "  ← ЗНАЧИМАЯ"
        elif abs(r) > 0.05:
            mark = "  ← слабая"
        print(f"    {h:>3} мин:  r = {r:+.4f}  (N={len(sub)}){mark}")

    # Средний результат по знаку
    print()
    print(f"  Среднее изменение цены:")
    for h in sorted(df["horizon_min"].unique()):
        sub = df[df["horizon_min"] == h]
        pos = sub[sub["sentiment"] > 0.5]["change_pct"]
        neg = sub[sub["sentiment"] < -0.5]["change_pct"]
        pos_str = f"{pos.mean():+.4f}% (N={len(pos)})" if len(pos) > 0 else "—"
        neg_str = f"{neg.mean():+.4f}% (N={len(neg)})" if len(neg) > 0 else "—"
        print(f"    {h:>3} мин:  позитивные {pos_str:>22}  |  негативные {neg_str:>22}")

    # Топ-5 новостей
    print()
    print(f"  Топ-5 новостей с наибольшим влиянием (через 15 мин):")
    sub = df[df["horizon_min"] == 15].copy()
    if len(sub) < 5:
        sub = df[df["horizon_min"] == df["horizon_min"].max()].copy()
    if not sub.empty:
        sub["abs_change"] = sub["change_pct"].abs()
        top = sub.nlargest(5, "abs_change")
        for _, row in top.iterrows():
            ts = row["timestamp"].strftime("%d.%m %H:%M")
            print(f"    [{ts}] s={row['sentiment']:+.2f} → {row['change_pct']:+.4f}%  {row['title']}")


def main():
    print("=" * 78)
    print("  АНАЛИЗ ВЛИЯНИЯ НОВОСТЕЙ НА ЦЕНУ")
    print("=" * 78)

    news = load_news()
    if news.empty:
        print("news_sentiment.csv пуст или не найден")
        return

    print(f"\nЗагружено новостей: {len(news)}")
    print(f"Период: {news['timestamp'].min()} — {news['timestamp'].max()}")

    # Анализируем для каждого тикера
    for ticker in ["GAZP", "RUAL"]:
        prices = load_prices(f"orderbook_{ticker}.csv")
        if prices.empty:
            print(f"\n  {ticker}: нет файла orderbook_{ticker}.csv")
            continue
        print(f"\n  {ticker}: {len(prices)} снимков цены")
        df = analyze_impact(news, prices, ticker)
        print_report(df, ticker)

    print()
    print("=" * 78)
    print("  ИНТЕРПРЕТАЦИЯ")
    print("=" * 78)
    print()
    print("  r > +0.15  → позитивные новости предсказывают рост")
    print("  r < -0.15  → обратная связь (новости отыграны заранее)")
    print("  |r| < 0.05 → новости не влияют на цену напрямую")


if __name__ == "__main__":
    main()