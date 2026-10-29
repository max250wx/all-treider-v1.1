"""Сборщик новостей с МосБиржи (ISS sitenews) — версия 2."""

import pandas as pd
import requests


def fetch_moex_news():
    """Собирает новости с сайта МосБиржи, ищет колонки по имени."""
    url = "https://iss.moex.com/iss/sitenews.json"
    params = {"iss.meta": "off", "limit": 50}

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        columns = data["sitenews"]["columns"]
        rows = data["sitenews"]["data"]

        idx_title = columns.index("title")
        idx_time = columns.index("published_at")

        news_list = []
        for item in rows:
            news_list.append(
                {
                    "timestamp": item[idx_time],
                    "title": item[idx_title],
                    "source": "MOEX",
                }
            )
        return news_list
    except Exception as e:
        print("Ошибка: " + str(e))
        return []


if __name__ == "__main__":
    print("Запуск сбора новостей...")
    news = fetch_moex_news()

    if news:
        df = pd.DataFrame(news)
        df["timestamp"] = pd.to_datetime(
            df["timestamp"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
        )
        df = df.dropna(subset=["timestamp"])
        df = df.sort_values("timestamp", ascending=False)

        print("Собрано " + str(len(df)) + " новостей")
        print(df.head())

        try:
            old = pd.read_csv("news_raw.csv")
            df = pd.concat([old, df]).drop_duplicates(subset=["title", "timestamp"])
        except FileNotFoundError:
            pass

        df.to_csv("news_raw.csv", index=False)
        print("Сохранено в news_raw.csv")
    else:
        print("Новостей не получено.")
