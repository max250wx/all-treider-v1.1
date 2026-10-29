"""Сбор новостей RSS + анализ тональности RuBERT.
Пишет в data/live/news_sentiment.csv.
Флаг --once — один цикл.
"""

import sys
import time
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

DATA_DIR = ROOT / CFG["paths"]["data_live"]
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = DATA_DIR / "news_sentiment.csv"

RSS_FEEDS = [
    ("RBC", "https://rssexport.rbc.ru/rbcnews/news/30/full.rss"),
    ("Interfax", "https://www.interfax.ru/rss.asp"),
    ("Vedomosti", "https://www.vedomosti.ru/rss/news"),
]

STRONG_NEGATIVE = [
    "санкц",
    "атак",
    "удар",
    "войн",
    "конфликт",
    "банкрот",
    "иск о",
    "штраф",
    "запрет",
    "ограничен",
    "обвал",
    "кризис",
    "катастроф",
    "убийств",
    "теракт",
    "разрушен",
    "потер",
    "угроз",
    "обвинен",
    "провал",
    "шок",
    "сорвал",
    "претензии",
    "авари",
]
STRONG_POSITIVE = [
    "рекорд",
    "прибыл",
    "рост ",
    "вырос",
    "соглашен",
    "перемир",
    "сотрудничеств",
    "подписа",
    "успех",
    "прорыв",
    "восстановлен",
    "поддержк",
    "укреплен",
    "позитив",
    "договор",
    "мирн",
]


def keyword_override(text):
    t = str(text).lower()
    neg = sum(1 for w in STRONG_NEGATIVE if w in t)
    pos = sum(1 for w in STRONG_POSITIVE if w in t)
    if neg > pos:
        return -0.8
    if pos > neg:
        return 0.8
    return None


def fetch_rss(source, url):
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = []
        for item in root.iter("item"):
            title_el = item.find("title")
            pub_el = item.find("pubDate")
            if title_el is None:
                continue
            items.append(
                {
                    "timestamp": pub_el.text if pub_el is not None else None,
                    "title": title_el.text.strip() if title_el.text else "",
                    "source": source,
                }
            )
        return items
    except Exception as e:
        print(f"{source}: ошибка — {e}")
        return []


def score_news(clf, titles):
    """RuBERT + keyword-override. clf может быть None — тогда только keywords."""
    scores = []
    for title in titles:
        override = keyword_override(title)
        if override is not None:
            scores.append(override)
            continue
        if clf is None:
            scores.append(0.0)
            continue
        try:
            r = clf(title[:200])[0]
            label = r["label"].lower()
            sign = 1 if "pos" in label else -1 if "neg" in label else 0
            scores.append(sign * r["score"])
        except Exception:
            scores.append(0.0)
    return scores


def run(once=False, use_model=True):
    clf = None
    if use_model:
        try:
            from transformers import pipeline

            print("Загружаем RuBERT...")
            clf = pipeline(
                "sentiment-analysis",
                model="seara/rubert-base-cased-russian-sentiment",
                tokenizer="seara/rubert-base-cased-russian-sentiment",
            )
        except Exception as e:
            print(f"RuBERT недоступен ({e}), работаю только на keywords")

    print(f"Сбор новостей RSS. Файл: {OUT_FILE}\n")
    try:
        while True:
            all_news = []
            for src, url in RSS_FEEDS:
                items = fetch_rss(src, url)
                all_news.extend(items)
                print(f"  {src}: {len(items)}")

            if all_news:
                df_new = pd.DataFrame(all_news)
                df_new["timestamp"] = pd.to_datetime(df_new["timestamp"], utc=True, errors="coerce")
                df_new = df_new.dropna(subset=["timestamp"])

                df_new["sentiment"] = score_news(clf, df_new["title"].tolist())

                if OUT_FILE.exists():
                    try:
                        old = pd.read_csv(OUT_FILE)
                        if "timestamp" in old.columns:
                            old["timestamp"] = pd.to_datetime(
                                old["timestamp"], utc=True, errors="coerce"
                            )
                        df = pd.concat([old, df_new]).drop_duplicates(subset=["title"])
                    except Exception:
                        df = df_new
                else:
                    df = df_new

                df = df.sort_values("timestamp", ascending=False)
                df.to_csv(OUT_FILE, index=False)
                print(
                    f"[{datetime.now():%H:%M:%S}] всего: {len(df)}, "
                    f"средний сентимент: {df['sentiment'].mean():+.3f}"
                )

            if once:
                break
            time.sleep(CFG["collectors"]["news_update_min"] * 60)
    except KeyboardInterrupt:
        print("\nОстановлено.")


if __name__ == "__main__":
    once = "--once" in sys.argv
    no_model = "--no-model" in sys.argv
    run(once=once, use_model=not no_model)
