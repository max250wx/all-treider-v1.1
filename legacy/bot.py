import asyncio
import csv
import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import BotCommand, Message
from dotenv import load_dotenv
from t_tech.invest import Client
from t_tech.invest.grpc.instruments import InstrumentType
from t_tech.invest.schemas import GetMarketValuesRequest, MarketValueType

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
T_INVEST_TOKEN = os.getenv("T_INVEST_TOKEN", "").strip()
# ... дальше без изменений

dp = Dispatcher()


def read_csv_tail(path: str, n: int = 5) -> list[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        return rows[-n:]
    except (OSError, csv.Error):
        return []


def get_rvi() -> dict | None:
    rows = read_csv_tail("rvi_data.csv", 1)
    if not rows:
        return None
    try:
        return {
            "value": float(rows[0]["rvi_current"]),
            "change": float(rows[0]["change_pct"]),
        }
    except (KeyError, ValueError, TypeError):
        return None


def get_fresh_news(n: int = 5) -> list[dict]:
    path = "news_sentiment.csv"
    if not os.path.exists(path):
        return []

    try:
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except (OSError, csv.Error):
        return []

    for row in rows:
        try:
            row["_ts"] = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            if row["_ts"].tzinfo is None:
                row["_ts"] = row["_ts"].replace(tzinfo=UTC)
        except (KeyError, ValueError, TypeError):
            row["_ts"] = datetime.min.replace(tzinfo=UTC)

    cutoff = datetime.now(UTC) - timedelta(hours=24)
    rows = [row for row in rows if row["_ts"] >= cutoff]
    rows.sort(key=lambda row: row["_ts"], reverse=True)
    return rows[:n]


def get_data_stats() -> dict[str, int]:
    files = {
        "trades_GAZP": "trades_GAZP.csv",
        "trades_RUAL": "trades_RUAL.csv",
        "rvi": "rvi_data.csv",
        "news": "news_sentiment.csv",
    }
    stats: dict[str, int] = {}

    for name, path in files.items():
        if not os.path.exists(path):
            stats[name] = 0
            continue
        try:
            with open(path, encoding="utf-8") as f:
                stats[name] = max(0, sum(1 for _ in f) - 1)
        except OSError:
            stats[name] = 0

    return stats


INSTRUMENT_TYPES = {
    "share": InstrumentType.INSTRUMENT_TYPE_SHARE,
    "future": InstrumentType.INSTRUMENT_TYPE_FUTURES,
    "etf": InstrumentType.INSTRUMENT_TYPE_ETF,
    "bond": InstrumentType.INSTRUMENT_TYPE_BOND,
}


def quotation_to_decimal(quotation) -> Decimal:
    return Decimal(quotation.units) + Decimal(quotation.nano) / Decimal(1_000_000_000)


def lookup_price(ticker: str, kind: str = "share") -> str:
    instrument_kind = INSTRUMENT_TYPES[kind]

    with Client(T_INVEST_TOKEN) as client:
        result = client.instruments.find_instrument(
            query=ticker,
            instrument_kind=instrument_kind,
        )

        if kind == "future":
            instruments = [
                item
                for item in result.instruments
                if item.ticker.upper().startswith(ticker.upper())
            ]
            available = [
                item for item in instruments if getattr(item, "api_trade_available_flag", False)
            ]
            # У фьючерсов код обычно содержит букву месяца и год;
            # сортировка помогает предпочесть более поздний контракт.
            available.sort(key=lambda item: item.ticker, reverse=True)
        else:
            instruments = [
                item for item in result.instruments if item.ticker.upper() == ticker.upper()
            ]
            available = [
                item for item in instruments if getattr(item, "api_trade_available_flag", False)
            ]

        if not instruments:
            return f"Инструмент {ticker} не найден в категории {kind}."

        if not available:
            return f"Для {ticker} не найден инструмент, доступный через API в категории {kind}."

        instrument = available[0]

        response = client.market_data.get_market_values(
            request=GetMarketValuesRequest(
                instrument_id=[instrument.uid],
                values=[
                    MarketValueType.INSTRUMENT_VALUE_LAST_PRICE,
                    MarketValueType.INSTRUMENT_VALUE_CLOSE_PRICE,
                ],
            )
        )

        if not response.instruments or not response.instruments[0].values:
            return f"{instrument.name} ({instrument.ticker}): цена через API сейчас недоступна."

        values = response.instruments[0].values
        last_price = next(
            (
                value
                for value in values
                if value.type == MarketValueType.INSTRUMENT_VALUE_LAST_PRICE
                and (value.value.units != 0 or value.value.nano != 0)
            ),
            None,
        )

        close_price = next(
            (
                value
                for value in values
                if value.type == MarketValueType.INSTRUMENT_VALUE_CLOSE_PRICE
            ),
            None,
        )

        selected = last_price or close_price

        if selected is None:
            return f"{instrument.name} ({instrument.ticker}): API не вернул ненулевую цену."

        price = quotation_to_decimal(selected.value)
        price_time = selected.time

        return (
            f"📈 {instrument.name} ({instrument.ticker})\n"
            f"Цена: {price} ₽\n"
            f"Время котировки (UTC): {price_time}\n"
            f"Категория: {kind}"
        )


@dp.message(Command("start"))
async def start(message: Message) -> None:
    await message.answer(
        "Бот котировок MOEX работает.\n\n"
        "Примеры запросов:\n"
        "/price GAZP\n"
        "/price Si future\n"
        "/price SBMX etf\n"
        "/price SU26238RMFS4 bond\n\n"
        "Категории: share, future, etf, bond."
    )


@dp.message(Command("price"))
async def price_command(message: Message) -> None:
    parts = (message.text or "").split()

    if len(parts) < 2:
        await message.answer("Укажи тикер, например: /price GAZP")
        return

    ticker = parts[1].upper()
    kind = parts[2].lower() if len(parts) >= 3 else "share"

    if kind not in INSTRUMENT_TYPES:
        await message.answer("Неизвестная категория. Доступны: share, future, etf, bond.")
        return

    if not TELEGRAM_TOKEN or not T_INVEST_TOKEN:
        await message.answer(
            "Не настроены переменные окружения TELEGRAM_BOT_TOKEN и/или T_INVEST_TOKEN."
        )
        return

    await message.answer(f"Ищу котировку {ticker}…")

    try:
        result = await asyncio.to_thread(lookup_price, ticker, kind)
        await message.answer(result)
    except Exception as exc:
        print(
            f"Ошибка запроса котировки: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        await message.answer(
            "Не удалось получить котировку. Проверь права T-Invest API и журнал приложения."
        )


@dp.message(Command("news"))
async def cmd_news(message: Message) -> None:
    news = get_fresh_news(5)

    if not news:
        await message.answer("Новостей за последние 24 часа нет.")
        return

    lines = ["<b>Свежие новости:</b>"]

    for i, item in enumerate(news, 1):
        ts = item["_ts"].strftime("%H:%M UTC")
        try:
            sentiment = float(item.get("sentiment", 0))
        except (ValueError, TypeError):
            sentiment = 0

        emoji = "🟢" if sentiment > 0.3 else ("🔴" if sentiment < -0.3 else "⚪")
        title = item.get("title", "Без заголовка")
        lines.append(f"{i}. {emoji} [{ts}] {title[:150]}")

    await message.answer("\n\n".join(lines), parse_mode="HTML")


@dp.message(Command("rvi"))
async def cmd_rvi(message: Message) -> None:
    r = get_rvi()

    if not r:
        await message.answer("Данные RVI не найдены.")
        return

    value = r["value"]
    change = r["change"]

    if value > 60:
        zone = "🔴 ЭКСТРЕМАЛЬНАЯ ПАНИКА"
    elif value > 40:
        zone = "🟠 ПАНИКА"
    elif value < 20:
        zone = "🟢 СПОКОЙСТВИЕ"
    else:
        zone = "🟡 НЕЙТРАЛЬНО"

    arrow = "↗" if change > 0 else ("↘" if change < 0 else "→")

    await message.answer(
        f"Индекс страха RVI\n\n"
        f"Значение: {value:.2f}\n"
        f"Изменение: {arrow} {change:+.2f}%\n"
        f"Зона: {zone}"
    )


@dp.message(Command("status"))
async def status_handler(message: Message) -> None:
    stats = get_data_stats()
    rvi = get_rvi()

    rvi_text = f"{rvi['value']:.2f} ({rvi['change']:+.2f}%)" if rvi else "нет данных"

    await message.answer(
        "📊 Статус системы\n\n"
        f"GAZP: {stats['trades_GAZP']} строк\n"
        f"RUAL: {stats['trades_RUAL']} строк\n"
        f"RVI: {stats['rvi']} строк — {rvi_text}\n"
        f"Новости: {stats['news']} строк"
    )


async def main() -> None:
    if not TELEGRAM_TOKEN:
        raise RuntimeError("Не задана переменная окружения TELEGRAM_BOT_TOKEN")
    if not T_INVEST_TOKEN:
        raise RuntimeError("Не задана переменная окружения T_INVEST_TOKEN")

    bot = Bot(token=TELEGRAM_TOKEN)
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Запустить бота"),
                BotCommand(command="price", description="Цена инструмента MOEX"),
                BotCommand(command="news", description="Свежие новости"),
                BotCommand(command="rvi", description="Индекс страха RVI"),
                BotCommand(command="status", description="Статус данных"),
            ]
        )
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
