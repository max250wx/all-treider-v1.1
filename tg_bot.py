import asyncio
import os
import csv
from datetime import datetime, timezone, timedelta

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("Не задана переменная окружения TELEGRAM_BOT_TOKEN")
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


def read_csv_tail(path, n=5):
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            return rows[-n:]
    except Exception:
        return []


def get_rvi():
    rows = read_csv_tail("rvi_data.csv", 1)
    if not rows:
        return None
    try:
        return {"value": float(rows[0]["rvi_current"]), "change": float(rows[0]["change_pct"])}
    except Exception:
        return None


def get_fresh_news(n=5):
    path = "news_sentiment.csv"
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except Exception:
        return []
    for r in rows:
        try:
            r["_ts"] = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
        except Exception:
            r["_ts"] = datetime.min.replace(tzinfo=timezone.utc)
    rows.sort(key=lambda r: r["_ts"], reverse=True)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    rows = [r for r in rows if r["_ts"] >= cutoff]
    return rows[:n]


def get_data_stats():
    files = {"trades_GAZP": "trades_GAZP.csv", "trades_RUAL": "trades_RUAL.csv", "rvi": "rvi_data.csv", "news": "news_sentiment.csv"}
    stats = {}
    for name, path in files.items():
        if not os.path.exists(path):
            stats[name] = 0
            continue
        try:
            with open(path) as f:
                stats[name] = sum(1 for _ in f) - 1
        except Exception:
            stats[name] = 0
    return stats


@dp.message(Command("start"))
async def cmd_start(msg: Message):
    text = ("<b>AI-трейдер MOEX</b>\n\n"
            "Команды:\n"
            "/news - 5 свежих новостей\n"
            "/rvi - индекс страха\n"
            "/signal GAZP - сводка по тикеру\n"
            "/status - состояние системы\n"
            "/analyze текст - анализ новости AI\n\n"
            "Ваш Chat ID: <code>" + str(msg.chat.id) + "</code>")
    await msg.answer(text)


@dp.message(Command("news"))
async def cmd_news(msg: Message):
    news = get_fresh_news(5)
    if not news:
        await msg.answer("Новостей за 24 часа нет.")
        return
    lines = ["<b>Свежие новости:</b>\n"]
    for i, n in enumerate(news, 1):
        try:
            ts = n["_ts"].strftime("%H:%M")
        except Exception:
            ts = "??:??"
        sent = float(n.get("sentiment", 0))
        emoji = "🟢" if sent > 0.3 else ("🔴" if sent < -0.3 else "⚪")
        lines.append(str(i) + ". " + emoji + " [" + ts + "] " + n["title"][:150])
    await msg.answer("\n\n".join(lines))


@dp.message(Command("rvi"))
async def cmd_rvi(msg: Message):
    r = get_rvi()
    if not r:
        await msg.answer("RVI не найден")
        return
    v = r["value"]; ch = r["change"]
    if v > 60: zone = "🔴 ЭКСТРЕМАЛЬНАЯ ПАНИКА"
    elif v > 40: zone = "🟠 ПАНИКА"
    elif v < 20: zone = "🟢 СПОКОЙСТВИЕ"
    else: zone = "🟡 НЕЙТРАЛЬНО"
    arrow = "↗" if ch > 0 else ("↘" if ch < 0 else "→")
    await msg.answer("<b>Индекс страха RVI</b>\n\nЗначение: <b>" + f"{v:.2f}" + "</b>\nИзменение: " + arrow + f" {ch:+.2f}%\nЗона: " + zone)


@dp.message(Command("signal"))
async def cmd_signal(msg: Message):
    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Использование: /signal GAZP")
        return
    ticker = args[1].upper()
    stats = get_data_stats()
    r = get_rvi()
    text = "<b>Сводка по " + ticker + "</b>\n\n"
    if r:
        text += "RVI: " + f"{r['value']:.2f}" + " (" + f"{r['change']:+.2f}" + "%)\n"
    if ticker == "GAZP":
        text += "Сделок GAZP: " + f"{stats.get('trades_GAZP', 0):,}" + "\n"
    elif ticker == "RUAL":
        text += "Сделок RUAL: " + f"{stats.get('trades_RUAL', 0):,}" + "\n"
    else:
        text += "Данных по тикеру нет\n"
    await msg.answer(text)


@dp.message(Command("status"))
async def cmd_status(msg: Message):
    stats = get_data_stats()
    r = get_rvi()
    text = "<b>Состояние системы</b>\n\n"
    if r: text += "RVI: " + f"{r['value']:.2f}" + "\n\n"
    text += "<b>Данные:</b>\n"
    text += "Сделок GAZP: " + f"{stats.get('trades_GAZP', 0):,}" + "\n"
    text += "Сделок RUAL: " + f"{stats.get('trades_RUAL', 0):,}" + "\n"
    text += "Новостей: " + f"{stats.get('news', 0):,}" + "\n"
    text += "Записей RVI: " + f"{stats.get('rvi', 0):,}" + "\n"
    await msg.answer(text)


@dp.message(Command("analyze"))
async def cmd_analyze(msg: Message):
    args = msg.text.replace("/analyze", "").strip()
    if not args:
        await msg.answer("Использование: /analyze текст новости")
        return
    await msg.answer("Анализирую...")
    try:
        import ollama
        prompt = ("Ты аналитик российского фондового рынка. "
                  "Ответь одной строкой: ТОНАЛЬНОСТЬ, ТЕМА, ВАЖНОСТЬ. "
                  "ТОНАЛЬНОСТЬ: POSITIVE или NEGATIVE или NEUTRAL. "
                  "ТЕМА: GEO или CB или OIL или CORP или OTHER. "
                  "ВАЖНОСТЬ: 1 до 5.")
        resp = ollama.chat(model="qwen2.5:7b", messages=[{"role": "system", "content": prompt}, {"role": "user", "content": "Новость: " + args}], options={"temperature": 0.0, "num_predict": 30})
        ans = resp["message"]["content"].strip().upper()
        await msg.answer("<b>Анализ:</b>\n\n<code>" + ans + "</code>\n\n<i>" + args[:200] + "</i>")
    except Exception as e:
        await msg.answer("Ошибка AI: " + str(e))


async def main():
    print("Запуск бота...")
    print("Отправьте боту в Telegram команду /start")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
