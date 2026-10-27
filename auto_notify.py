"""
Авторассылка уведомлений в Telegram.
Работает в фоне, проверяет RVI и новости каждые 2 минуты.
"""

import os
import time
import csv
import asyncio
from datetime import datetime, timezone, timedelta

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties


BOT_TOKEN = "8870582892:AAGiWiCSPt5aZvol7GWzDGMixSCvjaRywa8"
CHAT_ID = 994444680

CHECK_INTERVAL_SEC = 120
RVI_ALERT_THRESHOLD = 40
COOLDOWN_MIN = 60

LOG_FILE = "auto_notify.log"
STATE_FILE = "notify_state.csv"

sent_news = set()


def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def get_rvi():
    if not os.path.exists("rvi_data.csv"):
        return None
    try:
        with open("rvi_data.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return None
        last = rows[-1]
        return {
            "value": float(last["rvi_current"]),
            "change": float(last["change_pct"]),
        }
    except Exception:
        return None


def load_state():
    global sent_news
    if not os.path.exists(STATE_FILE):
        return
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            for row in csv.reader(f):
                if row:
                    sent_news.add(row[0])
    except Exception:
        pass


def save_state(key):
    with open(STATE_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([key])


def get_new_important_news():
    """Возвращает свежие новости за последние 30 минут с явным сентиментом."""
    path = "news_sentiment.csv"
    if not os.path.exists(path):
        return []

    try:
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except Exception:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    result = []

    for r in rows:
        try:
            ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
        except Exception:
            continue

        if ts < cutoff:
            continue

        sent = float(r.get("sentiment", 0))

        # Отправляем только явно позитивные/негативные
        if abs(sent) < 0.7:
            continue

        title = r["title"]
        key = title[:60]

        if key in sent_news:
            continue

        result.append({
            "key": key,
            "title": title,
            "sentiment": sent,
            "timestamp": ts,
        })

    return result


async def send_alert(bot, text):
    try:
        await bot.send_message(CHAT_ID, text, parse_mode=ParseMode.HTML)
        log(f"Отправлено: {text[:60]}...")
    except Exception as e:
        log(f"Ошибка отправки: {e}")


async def main():
    log("AUTO-NOTIFY стартовал")
    load_state()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    last_rvi_alert = None

    try:
        while True:
            now = datetime.now(timezone.utc)

            # ── RVI-алерт ──
            rvi = get_rvi()
            if rvi and rvi["value"] > RVI_ALERT_THRESHOLD:
                should_send = (
                    last_rvi_alert is None
                    or (now - last_rvi_alert).total_seconds() > COOLDOWN_MIN * 60
                )
                if should_send:
                    text = (
                        "🚨 <b>RVI алерт</b>\n\n"
                        f"Индекс страха: <b>{rvi['value']:.2f}</b>\n"
                        f"Изменение: {rvi['change']:+.2f}%\n\n"
                        "Паника на рынке — шорт-сигналы сильнее."
                    )
                    await send_alert(bot, text)
                    last_rvi_alert = now

            # ── Новостные алерты ──
            for item in get_new_important_news():
                emoji = "🟢" if item["sentiment"] > 0.7 else "🔴"
                direction = "ПОЗИТИВНАЯ" if item["sentiment"] > 0 else "НЕГАТИВНАЯ"

                text = (
                    f"{emoji} <b>Важная новость</b>\n\n"
                    f"{item['title']}\n\n"
                    f"Тональность: <b>{direction}</b>\n"
                    f"Sentiment: {item['sentiment']:+.2f}\n"
                    f"Время: {item['timestamp'].strftime('%H:%M')}"
                )
                await send_alert(bot, text)
                sent_news.add(item["key"])
                save_state(item["key"])

            await asyncio.sleep(CHECK_INTERVAL_SEC)

    except KeyboardInterrupt:
        log("Остановлен")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
