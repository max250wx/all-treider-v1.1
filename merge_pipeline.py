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

import os
import pandas as pd
import numpy as np


# ── НАСТРОЙКИ ──
ORDERBOOK_FILE = "orderbook_raw_rest.csv"
TRADES_FILE = "trades_raw_rest.csv"
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



def validate_input_schema(ob, trades):
    """Проверяет схему, идентификаторы и числовые значения входных данных."""
    ob_required = {
        "timestamp", "ticker", "figi",
        *[f"bid{i}_price" for i in range(1, 6)],
        *[f"bid{i}_qty" for i in range(1, 6)],
        *[f"ask{i}_price" for i in range(1, 6)],
        *[f"ask{i}_qty" for i in range(1, 6)],
    }
    trade_required = {
        "timestamp", "ticker", "figi", "price", "quantity", "direction",
    }

    missing_ob = ob_required - set(ob.columns)
    missing_tr = trade_required - set(trades.columns)
    if missing_ob:
        raise ValueError(f"В стакане отсутствуют колонки: {sorted(missing_ob)}")
    if missing_tr:
        raise ValueError(f"В сделках отсутствуют колонки: {sorted(missing_tr)}")

    ob = ob.copy()
    trades = trades.copy()

    for df, name in ((ob, "стакане"), (trades, "сделках")):
        df["ticker"] = df["ticker"].astype("string").str.strip().str.upper()
        df["figi"] = df["figi"].astype("string").str.strip().replace("", pd.NA)
        if df["ticker"].isna().any() or df["ticker"].eq("").any():
            raise ValueError(f"Обнаружен пустой ticker в данных: {name}")

    ob_numeric = [
        *[f"bid{i}_price" for i in range(1, 6)],
        *[f"bid{i}_qty" for i in range(1, 6)],
        *[f"ask{i}_price" for i in range(1, 6)],
        *[f"ask{i}_qty" for i in range(1, 6)],
    ]
    trade_numeric = ["price", "quantity", "direction"]

    for col in ob_numeric:
        ob[col] = pd.to_numeric(ob[col], errors="coerce")
    for col in trade_numeric:
        trades[col] = pd.to_numeric(trades[col], errors="coerce")

    if ob[ob_numeric].isna().any().any():
        raise ValueError("В уровнях стакана есть пустые или нечисловые значения.")
    if trades[trade_numeric].isna().any().any():
        raise ValueError("В числовых полях сделок есть пустые или нечисловые значения.")

    if not np.isfinite(ob[ob_numeric].to_numpy(dtype=float)).all():
        raise ValueError("В уровнях стакана обнаружены бесконечные значения.")
    if not np.isfinite(trades[trade_numeric].to_numpy(dtype=float)).all():
        raise ValueError("В сделках обнаружены бесконечные числовые значения.")

    price_cols = [
        *[f"bid{i}_price" for i in range(1, 6)],
        *[f"ask{i}_price" for i in range(1, 6)],
    ]
    qty_cols = [
        *[f"bid{i}_qty" for i in range(1, 6)],
        *[f"ask{i}_qty" for i in range(1, 6)],
    ]

    if (ob[price_cols] <= 0).any().any():
        raise ValueError("Цены уровней стакана должны быть положительными.")
    if (ob[qty_cols] < 0).any().any():
        raise ValueError("Объёмы уровней стакана не могут быть отрицательными.")
    if (ob["bid1_price"] > ob["ask1_price"]).any():
        raise ValueError("Обнаружен стакан с bid1_price выше ask1_price.")
    if (trades["price"] <= 0).any() or (trades["quantity"] <= 0).any():
        raise ValueError("Цена и количество сделки должны быть положительными.")
    if not trades["direction"].isin([0, 1, 2]).all():
        raise ValueError("direction сделки должен быть 0, 1 или 2.")

    return ob, trades

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
        ob = ob.copy()
        ob["buy_volume"] = 0.0
        ob["sell_volume"] = 0.0
        ob["trade_count"] = 0
        ob["vwap"] = np.nan
        ob["trade_imbalance"] = 0.0
        return ob

    required = {"timestamp", "price", "quantity", "direction"}
    missing = required - set(trades.columns)
    if missing:
        raise ValueError(
            f"В данных сделок отсутствуют колонки: {sorted(missing)}"
        )
    if "timestamp" not in ob.columns:
        raise ValueError("В стакане отсутствует колонка timestamp")

    ob = ob.copy()
    tr = trades.copy()

    ob["timestamp"] = pd.to_datetime(ob["timestamp"], utc=True, errors="coerce")
    tr["timestamp"] = pd.to_datetime(tr["timestamp"], utc=True, errors="coerce")

    if ob["timestamp"].isna().any():
        raise ValueError("В стакане обнаружены некорректные timestamp")
    if tr["timestamp"].isna().any():
        raise ValueError("В сделках обнаружены некорректные timestamp")

    tr["direction"] = pd.to_numeric(tr["direction"], errors="coerce")
    tr["price"] = pd.to_numeric(tr["price"], errors="coerce")
    tr["quantity"] = pd.to_numeric(tr["quantity"], errors="coerce")

    if tr[["direction", "price", "quantity"]].isna().any().any():
        raise ValueError("В сделках обнаружены пустые или нечисловые значения")
    if (tr["price"] <= 0).any() or (tr["quantity"] <= 0).any():
        raise ValueError("Цена и количество сделки должны быть положительными")
    if not tr["direction"].isin([0, 1, 2]).all():
        raise ValueError("Неизвестное направление сделки: ожидается 0, 1 или 2")

    tr["is_buy"] = tr["direction"] == 1
    tr["is_sell"] = tr["direction"] == 2
    tr["buy_vol"] = tr["quantity"] * tr["is_buy"].astype(int)
    tr["sell_vol"] = tr["quantity"] * tr["is_sell"].astype(int)
    tr["notional"] = tr["price"] * tr["quantity"]
    tr = tr.set_index("timestamp").sort_index()

    buy_volume, sell_volume, trade_count, vwap, trade_imb = [], [], [], [], []

    has_tr_figi = "figi" in tr.columns
    has_ob_figi = "figi" in ob.columns
    has_tr_ticker = "ticker" in tr.columns
    has_ob_ticker = "ticker" in ob.columns

    for _, ob_row in ob.iterrows():
        ts = ob_row["timestamp"]
        ws = ts - pd.Timedelta(seconds=TRADE_WINDOW_SEC)
        w = tr.loc[(tr.index > ws) & (tr.index <= ts)]

        if not w.empty:
            ob_figi = ob_row.get("figi")
            ob_ticker = ob_row.get("ticker")

            if has_tr_figi and has_ob_figi and pd.notna(ob_figi):
                w = w[
                    w["figi"].astype("string").str.strip()
                    == str(ob_figi).strip()
                ]
                if w.empty:
                    print(
                        f"  Предупреждение: сделки не найдены по figi "
                        f"{str(ob_figi).strip()} для "
                        f"{ob_ticker if pd.notna(ob_ticker) else 'неизвестного тикера'}"
                    )
            elif has_tr_ticker and has_ob_ticker and pd.notna(ob_ticker):
                w = w[
                    w["ticker"].astype("string").str.strip().str.upper()
                    == str(ob_ticker).strip().upper()
                ]
            elif has_tr_figi or has_tr_ticker:
                raise ValueError(
                    "Невозможно надёжно сопоставить сделки со стаканом: "
                    "идентификатор инструмента отсутствует"
                )
            else:
                raise ValueError(
                    "В данных нет figi или ticker для проверки инструмента"
                )

        if w.empty:
            buy_volume.append(0.0)
            sell_volume.append(0.0)
            trade_count.append(0)
            vwap.append(np.nan)
            trade_imb.append(0.0)
            continue

        bv = float(w["buy_vol"].sum())
        sv = float(w["sell_vol"].sum())
        directional_volume = bv + sv
        total_quantity = float(w["quantity"].sum())

        buy_volume.append(bv)
        sell_volume.append(sv)
        trade_count.append(len(w))
        vwap.append(
            float(w["notional"].sum() / total_quantity)
            if total_quantity > 0 else np.nan
        )
        trade_imb.append(
            (bv - sv) / directional_volume
            if directional_volume > 0 else 0.0
        )

    ob = ob.copy()
    ob["buy_volume"] = buy_volume
    ob["sell_volume"] = sell_volume
    ob["trade_count"] = trade_count
    ob["vwap"] = vwap
    ob["trade_imbalance"] = trade_imb

    return ob


def merge_news(ob, news):
    ob = ob.copy()

    if news.empty:
        print("  Новости отсутствуют — sentiment = 0")
        ob["news_sentiment"] = 0.0
        ob["news_title"] = ""
        ob["news_age_min"] = np.nan
        return ob

    required = {"timestamp", "title", "sentiment"}
    missing = required - set(news.columns)
    if missing:
        raise ValueError(
            f"В файле новостей отсутствуют колонки: {sorted(missing)}"
        )

    if "timestamp" not in ob.columns:
        raise ValueError("В стакане отсутствует колонка timestamp")

    news_slim = news[
        ["timestamp", "title", "sentiment"]
    ].copy()

    news_slim = news_slim.rename(columns={
        "timestamp": "_news_ts",
        "title": "news_title",
        "sentiment": "news_sentiment",
    })

    ob["timestamp"] = pd.to_datetime(
        ob["timestamp"], utc=True, errors="coerce"
    )
    news_slim["_news_ts"] = pd.to_datetime(
        news_slim["_news_ts"], utc=True, errors="coerce"
    )

    ob = ob.dropna(subset=["timestamp"]).sort_values("timestamp")
    news_slim = (
        news_slim
        .dropna(subset=["_news_ts"])
        .sort_values("_news_ts")
    )

    ob = pd.merge_asof(
        ob,
        news_slim,
        left_on="timestamp",
        right_on="_news_ts",
        direction="backward",
        tolerance=pd.Timedelta(minutes=NEWS_WINDOW_MIN),
    )

    ob["news_age_min"] = (
        (ob["timestamp"] - ob["_news_ts"]).dt.total_seconds() / 60.0
    )

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
        raise RuntimeError(
            f"Стакан пуст или отсутствует ({ORDERBOOK_FILE}). "
            "Сначала запустите сборщик и проверьте входные данные."
        )

    if trades.empty:
        raise RuntimeError(
            f"Сделки пусты или отсутствуют ({TRADES_FILE}). "
            "Отказ от создания неполного combined_data.csv."
        )

    if news.empty:
        print(
            f"  ПРЕДУПРЕЖДЕНИЕ: новости отсутствуют ({NEWS_FILE}); "
            "news_sentiment будет заполнен нулями."
        )

    ob, trades = validate_input_schema(ob, trades)
    print("  Проверка схемы и числовых данных пройдена.")

    print("\n2. Признаки стакана:")
    ob = add_orderbook_features(ob)
    print("  mid_price, spread, spread_pct, book_imbalance, microprice — добавлены")

    print(f"\n3. Поток сделок (окно {TRADE_WINDOW_SEC} сек):")
    ob = add_trade_flow(ob, trades)
    print("  buy_volume, sell_volume, trade_count, vwap, trade_imbalance — добавлены")

    print(f"\n4. Новостной фон (окно {NEWS_WINDOW_MIN} мин):")
    ob = merge_news(ob, news)
    print("  news_sentiment, news_title — добавлены")

    # ── Проверка качества результата перед сохранением ──
    ob = ob.sort_values("timestamp").reset_index(drop=True)

    if ob.empty:
        raise RuntimeError("Итоговый DataFrame пуст; существующий результат сохранён.")

    required_output = {
        "timestamp", "ticker", "figi",
        "mid_price", "spread", "spread_pct",
        "book_imbalance", "microprice",
        "buy_volume", "sell_volume", "trade_count",
        "vwap", "trade_imbalance",
        "news_sentiment", "news_age_min",
    }
    missing_output = required_output.difference(ob.columns)
    if missing_output:
        raise RuntimeError(
            "В итоговых данных отсутствуют колонки: "
            + ", ".join(sorted(missing_output))
        )

    if ob["timestamp"].isna().any():
        raise RuntimeError("В итоговых данных есть некорректные timestamp.")

    core_numeric = [
        "mid_price", "spread", "spread_pct",
        "book_imbalance", "microprice",
        "buy_volume", "sell_volume", "trade_count",
        "trade_imbalance", "news_sentiment",
    ]

    core_values = ob[core_numeric].apply(
        pd.to_numeric, errors="coerce"
    )

    if (
        core_values.isna().any().any()
        or not np.isfinite(core_values.to_numpy(dtype=float)).all()
    ):
        raise RuntimeError(
            "В основных числовых признаках есть пропуски, "
            "нечисловые или бесконечные значения."
        )

    # VWAP может отсутствовать, если в окне нет сделок.
    vwap = pd.to_numeric(ob["vwap"], errors="coerce")
    trade_count = pd.to_numeric(ob["trade_count"], errors="coerce")

    if (ob["vwap"].notna() & vwap.isna()).any():
        raise RuntimeError("В vwap есть нечисловые значения.")

    if (trade_count < 0).any():
        raise RuntimeError("trade_count не может быть отрицательным.")

    has_trades = trade_count > 0

    if vwap[has_trades].isna().any():
        raise RuntimeError(
            "Для строк с сделками отсутствует vwap."
        )

    if not np.isfinite(vwap.dropna().to_numpy(dtype=float)).all():
        raise RuntimeError("В vwap есть бесконечные значения.")

    # Возраст новости может отсутствовать, если подходящей новости нет.
    news_age = pd.to_numeric(ob["news_age_min"], errors="coerce")

    if (ob["news_age_min"].notna() & news_age.isna()).any():
        raise RuntimeError("В news_age_min есть нечисловые значения.")

    valid_news_age = news_age.dropna()

    if not np.isfinite(valid_news_age.to_numpy(dtype=float)).all():
        raise RuntimeError("В news_age_min есть бесконечные значения.")

    if (
        (valid_news_age < 0).any()
        or (valid_news_age > NEWS_WINDOW_MIN).any()
    ):
        raise RuntimeError(
            f"news_age_min выходит за диапазон 0–{NEWS_WINDOW_MIN} минут."
        )

    print("  Проверка качества итоговых данных пройдена.")
    temp_output = OUTPUT_FILE + ".tmp"
    try:
        ob.to_csv(temp_output, index=False)
        os.replace(temp_output, OUTPUT_FILE)
    finally:
        if os.path.exists(temp_output):
            os.remove(temp_output)

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
