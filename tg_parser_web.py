"""Парсер Telegram-каналов через веб-превью t.me/s/<channel>."""

import os
import csv
import time
import requests
from bs4 import BeautifulSoup


CHANNELS = [
    "markettwits",
    "Div_millioner",
    "divonline",
    "trader_chernyh",
]

OUTPUT_FILE = "news_telegram.csv"
SEEN_FILE = "tg_seen.csv"


def _ensure_header():
    if not os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["timestamp", "channel", "text", "views"])


def load_seen():
    seen = set()
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, encoding="utf-8") as f:
                for row in csv.reader(f):
                    if row:
                        seen.add(row[0])
        except Exception:
            pass
    return seen


def save_seen(seen):
    with open(SEEN_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for h in seen:
            w.writerow([h])


def parse_channel(channel, retries=3):
    url = f"https://t.me/s/{channel}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=20)
            r.raise_for_status()
            break
        except Exception as e:
            if attempt < retries - 1:
                print(f"  {channel}: попытка {attempt+1} — {e}, повтор...")
                time.sleep(3)
            else:
                print(f"  {channel}: ошибка после {retries} попыток — {e}")
                return []

    soup = BeautifulSoup(r.text, "html.parser")
    messages = soup.find_all("div", class_="tgme_widget_message")

    posts = []
    for msg in messages[-30:]:
        text_el = msg.find("div", class_="tgme_widget_message_text")
        if not text_el:
            continue
        text = text_el.get_text(separator=" ", strip=True)
        if not text or len(text) < 20:
            continue

        time_el = msg.find("time", class_="time")
        if not time_el or not time_el.get("datetime"):
            continue
        ts_str = time_el["datetime"]

        views_el = msg.find("span", class_="tgme_widget_message_views")
        views = views_el.get_text(strip=True) if views_el else "0"

        lower = text.lower()
        if any(w in lower for w in ["реклама", "erid", "купить рекламу"]):
            continue

        posts.append({
            "timestamp": ts_str,
            "channel": channel,
            "text": text[:500].replace("\n", " "),
            "views": views,
        })

    return posts


def msg_hash(post):
    return f"{post['channel']}|{post['timestamp']}|{post['text'][:50]}"


def main():
    _ensure_header()
    seen = load_seen()

    print(f"Мониторинг {len(CHANNELS)} каналов...\n")

    all_new = []
    for ch in CHANNELS:
        posts = parse_channel(ch)
        new_posts = [p for p in posts if msg_hash(p) not in seen]
        for p in new_posts:
            seen.add(msg_hash(p))
        print(f"  {ch}: всего {len(posts)}, новых {len(new_posts)}")
        all_new.extend(new_posts)
        time.sleep(0.5)

    if all_new:
        with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            for p in all_new:
                w.writerow([p["timestamp"], p["channel"], p["text"], p["views"]])
        save_seen(seen)
        print(f"\nСохранено {len(all_new)} новых сообщений → {OUTPUT_FILE}")
    else:
        print("\nНовых сообщений нет")


if __name__ == "__main__":
    main()
