"""Сбор новостей из RSS-лент РБК, Интерфакса, Ведомостей."""

from xml.etree import ElementTree as ET

import pandas as pd
import requests

RSS_FEEDS = [
    ("RBC", "https://rssexport.rbc.ru/rbcnews/news/30/full.rss"),
    ("Interfax", "https://www.interfax.ru/rss.asp"),
    ("Vedomosti", "https://www.vedomosti.ru/rss/news"),
]


def fetch_rss(source, url):
    """Скачивает и парсит RSS-ленту."""
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        items = []
        # Стандартная структура RSS: channel/item
        for item in root.iter("item"):
            title_el = item.find("title")
            pub_el = item.find("pubDate")
            if title_el is None:
                continue
            items.append(
                {
                    "timestamp": pub_el.text if pub_el is not None else None,
                    "title": title_el.text.strip(),
                    "source": source,
                }
            )
        return items
    except Exception as e:
        print(f"{source}: ошибка — {e}")
        return []


def parse_pubdate(s):
    """RSS-дата в формате 'Mon, 13 Oct 2026 15:30:00 +0300'."""
    if not s:
        return None
    try:
        return pd.to_datetime(s, utc=True, errors="coerce")
    except Exception:
        return None


if __name__ == "__main__":
    print("Сбор новостей из RSS...")
    all_news = []
    for source, url in RSS_FEEDS:
        print(f"  {source}...")
        items = fetch_rss(source, url)
        all_news.extend(items)
        print(f"    получено: {len(items)}")

    if not all_news:
        print("Новостей не получено.")
    else:
        df = pd.DataFrame(all_news)
        df["timestamp"] = df["timestamp"].apply(parse_pubdate)
        df = df.dropna(subset=["timestamp"])
        df = df.sort_values("timestamp", ascending=False)

        print(f"\nВсего собрано: {len(df)}")
        print(df.head(10))

        try:
            old = pd.read_csv("news_rss.csv")
            if "timestamp" in old.columns:
                old["timestamp"] = pd.to_datetime(old["timestamp"], utc=True, errors="coerce")
            df = pd.concat([old, df]).drop_duplicates(subset=["title"])
        except FileNotFoundError:
            pass

        df.to_csv("news_rss.csv", index=False)
        print("\nСохранено в news_rss.csv")
