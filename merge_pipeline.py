"""
Объединение трёх источников в единый датафрейм:
  orderbook_raw.csv  — снимки стакана (каждые N секунд)
  trades_raw.csv     — поток сделок (реальное время)
  news_sentiment.csv — новости с тональностью

Для каждого снимка стакана считаем:
  - поток сделок за предыдущие TRADE_WINDOW_SEC секунд
  - последнюю новость в окне NEWS_WINDOW_MIN минут
  - производные признаки (imbalance, microprice, spread)

Результат → combined_data.csv
"""

import pandas as pd
import numpy as np


# ── НАСТРОЙКИ ──
ORDERBOOK_FILE = "orderbook_raw.csv"
TRADES_FILE = "trades_raw.csv"
NEWS_FILE = "news_sentiment.csv"
OUTPUT_FILE = "combined_data.csv"

TRADE_WINDOW_SEC = 60      # окно агрегации сделок (секунды)
NEWS_WINDOW_MIN = 15       # окно поиска последней новости (минуты)


# ─────────────────────────────────────────────
# Загрузка
# ─────────────────────────────────────────────

def load_csv(path, name):
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        print(f"  {name}: файл {path} не найден")
        return pd.DataFrame()

    if df.empty:
        print(f"  {name}: файл пустой (только заголовок)")
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    print(f"  {name}: загружено {len(df)} строк")
    return df


# ─────────────────────────────────────────────
# Производные признаки стакана
# ─────────────────────────────────────────────

def add_orderbook_features(ob):
    ob = ob.copy()

    ob["mid_price"] = (ob["bid1_price"] + ob["ask1_price"]) / 2
    ob["spread"] = ob["ask1_price"] - ob["bid1_price"]
    ob["spread_pct"] = ob["spread"] / ob["mid_price"] * 100

    bid_cols = [f"bid{i}_qty" for i in range(1, 6)]
    ask_cols = [f"ask{i}_qty" for i in range(1, 6)]
    ob["bid_volume"] = ob[bid_cols].sum(axis=1)
    ob["ask_volume"] = ob[ask_cols].sum(axis=1)

    total = ob["bid_volume"] + ob["ask_volume"]
    ob["book_imbalance"] = (ob["bid_volume"] - ob["ask_volume"]) / total.replace(0, np.nan)

    # Microprice: средневзвешенная по объёмам на лучших уровнях
    denom = (ob["bid1_qty"] + ob["ask1_qty"]).replace(0, np.nan)
    ob["microprice"] = (
        ob["bid1_price"] * ob["ask1_qty"] + ob["ask1_price"] * ob["bid1_qty"]
    ) / denom

    return ob


# ─────────────────────────────────────────────
# Поток сделок в окне
# ─────────────────────────────────────────────

def add_trade_flow(ob, trades):
    if trades.empty:
        print("  Сделки отсутствуют — поток обнуляется")
        ob["buy_volume"] = 0.0
        ob["sell_volume"] = 0.0
        ob["trade_count"] = 0
        ob["vwap"] = np.nan
        ob["trade_imbalance"] = 0.0
        return ob

    tr = trades.copy()
    tr["is_buy"] = (tr["direction"] == 1)
    tr["is_sell"] = (tr["direction"] == 2)
    tr["buy_vol"] = tr["quantity"] * tr["is_buy"].astype(int)
    tr["sell_vol"] = tr["quantity"] * tr["is_sell"].astype(int)
    tr["notional"] = tr["price"] * tr["quantity"]
    tr = tr.set_index("timestamp").sort_index()

    buy_volume, sell_volume, trade_count, vwap, trade_imb = [], [], [], [], []

    for ts in ob["timestamp"]:
        ws = ts - pd.Timedelta(seconds=TRADE_WINDOW_SEC)
        w = tr.loc[(tr.index > ws) & (tr.index <= ts)]
        if len(w) == 0:
            buy_volume.append(0)
            sell_volume.append(0)
            trade_count.append(0)
            vwap.append(np.nan)
            trade_imb.append(0.0)
        else:
            bv = float(w["buy_vol"].sum())
            sv = float(w["sell_vol"].sum())
            tot = bv + sv
            buy_volume.append(bv)
            sell_volume.append(sv)
            trade_count.append(len(w))
            vwap.append(float(w["notional"].sum() / w["quantity"].sum()))
            trade_imb.append((bv - sv) / tot if tot > 0 else 0.0)

    ob = ob.copy()
    ob["buy_volume"] = buy_volume
    ob["sell_volume"] = sell_volume
    ob["trade_count"] = trade_count
    ob["vwap"] = vwap
    ob["trade_imbalance"] = trade_imb

    return ob


# ─────────────────────────────────────────────
# Прикрепление новостей
# ─────────────────────────────────────────────

def merge_news(ob, news):
    if news.empty:
        print("  Новости отсутствуют — sentiment = 0")
        ob["news_sentiment"] = 0.0
        ob["news_title"] = ""
        ob["news_age_min"] = np.nan
        return ob

    news_slim = news[["timestamp", "title", "sentiment"]].rename(
        columns={"title": "news_title", "sentiment": "news_sentiment"}
    ).sort_values("timestamp")

    # merge_asof: для каждой строки ob берём ближайшую новость ПЕРЕД ней
    ob = pd.merge_asof(
        ob.sort_values("timestamp"),
        news_slim,
        on="timestamp",
        direction="backward",
        tolerance=pd.Timedelta(minutes=NEWS_WINDOW_MIN),
    )

    ob["news_age_min"] = (ob["timestamp"] - ob["_news_ts"]) if "_news_ts" in ob.columns else np.nan

    ob["news_sentiment"] = ob["news_sentiment"].fillna(0.0)
    ob["news_title"] = ob["news_title"].fillna("")

    return ob


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  MERGE PIPELINE")
    print("=" * 60)

    print("\n1. Загрузка файлов:")
    ob = load_csv(ORDERBOOK_FILE, "orderbook")
    trades = load_csv(TRADES_FILE, "trades")
    news = load_csv(NEWS_FILE, "news")

    if ob.empty:
        print("\nСтакан пуст — объединять нечего. Запустите сбор в часы торгов.")
        return

    print("\n2. Признаки стакана:")
    ob = add_orderbook_features(ob)
    print("  mid_price, spread, spread_pct, book_imbalance, microprice — добавлены")

    print(f"\n3. Поток сделок (окно {TRADE_WINDOW_SEC} сек):")
    ob = add_trade_flow(ob, trades)
    print("  buy_volume, sell_volume, trade_count, vwap, trade_imbalance — добавлены")

    print(f"\n4. Новостной фон (окно {NEWS_WINDOW_MIN} мин):")
    ob = merge_news(ob, news)
    print("  news_sentiment, news_title — добавлены")

    # ── Сохранение ──
    ob = ob.sort_values("timestamp").reset_index(drop=True)
    ob.to_csv(OUTPUT_FILE, index=False)

    print(f"\n5. Сохранено: {OUTPUT_FILE}")
    print(f"   Строк: {len(ob)}")
    print(f"   Период: {ob['timestamp'].iloc[0]} — {ob['timestamp'].iloc[-1]}")
    print(f"   Колонок: {len(ob.columns)}")

    print("\n─ Первые 3 строки (ключевые колонки) ─")
    cols_show = [
        "timestamp", "mid_price", "spread_pct",
        "book_imbalance", "buy_volume", "sell_volume",
        "trade_imbalance", "news_sentiment",
    ]
    cols_show = [c for c in cols_show if c in ob.columns]
    print(ob[cols_show].head(3).to_string(index=False))

    # ── Быстрая статистика ──
    print("\n─ Распределение ─")
    print(f"  Сделок в среднем на снимок: {ob['trade_count'].mean():.1f}")
    print(f"  Buy/Sell imbalance (сред.): {ob['trade_imbalance'].mean():.3f}")
    print(f"  Book imbalance (сред.):     {ob['book_imbalance'].mean():.3f}")
    print(f"  Снимков с новостью:         {(ob['news_sentiment'] != 0).sum()}")


if __name__ == "__main__":
    main()