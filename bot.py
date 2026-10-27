import yfinance as yf
from datetime import datetime
import pytz
import time
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextProcessor, CommandHandler, MessageHandler

# ==========================================================
# НАСТРОЙКИ (Замените на свои данные)
# ==========================================================
BOT_TOKEN=8870582892:AAEWaxrTOKc9PhYJtWSGbirBzxNyt0SNWuM
CHAT_ID=994444680
TICKERS = [
    "AAPL",        # Apple Inc.
    "GOOGL",       # Alphabet Inc.
    "BTC-USD",     # Bitcoin
    "ETH-USD",     # Ethereum
]

API_URL_STOCKS = "https://query1.finance.yahoo.com/v8/finance/chart" 
API_URL_CRYPTO = "https://api.coingecko.com/api/v3/simple/price"

# ==========================================================
# ЛОГИКА (Внутренняя часть, не трогай для начала)
# ==========================================================

def get_stock_price(ticker):
    ticker_full = f"{ticker}.US" # Для акций нужен .US обычно
    try:
        stock = yf.Ticker(ticker_full)
        hist = stock.history(period="1d")
        if len(hist) > 0:
            current_price = hist['Close'].iloc[-1]
            return float(current_price), "stock"
    except Exception as e:
        print(f"Ошибка получения {ticker}: {e}")
        return None, "error"

def get_crypto_price(ticker):
    # CoinGecko иногда требует API key для частых запросов
    try:
        response = requests.get(API_URL_CRYPTO, params={"ids": ticker, "vs_currencies": ["USD"]})
        data = response.json()
        if ticker in data and "USD" in data[ticker]:
            current_price = data[ticker]["USD"]
            return float(current_price), "crypto"
    except Exception as e:
        print(f"Ошибка получения {ticker}: {e}")
        return None, "error"

def send_to_telegram(message):
    try:
        bot = ApplicationBuilder().token(BOT_TOKEN).build()
        # Если нужно отправлять сразу без запуска сервера
        import telegram.ext
        from telegram.ext import ContextProcessor
        
        async def process(update: Update, context: ContextProcessor):
            await update.message.reply_text(f"Данные за {message} загружены.")
            
    except Exception as e:
        print(f"Ошибка Telegram отправки: {e}")

def send_market_update(bot, message):
    """Функция для отправки сообщения в канал/чат"""
    try:
        await bot.send_message(
            chat_id=TELEGRAM_USER_ID, 
            text=message
        )
    except Exception as e:
        print(f"Ошибка Telegram: {e}")

def format_price(price_type, price, symbol):
    return f"{price} USD" if price > 0 else "N/A"

async def start(update: Update, context: ContextProcessor):
    await update.message.reply_text("Бот запущен. Выберите тикер для отслеживания (например: AAPL).")

# ==========================================================
# ОСНОВНОЙ ЦИКЛ (В реальном проекте это будет в loop)
# ==========================================================

async def main_loop(bot):
    while True:
        now = datetime.now(pytz.UTC) # UTC для стабильности
        for ticker in TICKERS:
            price_info = None
            
            # Определяем тип тикера (упрощено, можно через список символов)
            if "-" in ticker or "." in ticker:
                # Крипта
                price, type_ = await get_crypto_price(ticker)
            else:
                # Акция или монета
                price, type_ = await get_stock_price(ticker)

            if price is not None:
                formatted_msg = f"💰 **{ticker}:** {format_price(type_, price, ticker)}\n*Получено в реальном времени*\n"
                
                # Отправляем сообщение (в реальной версии здесь используется телеграм-бот API через async)
                send_market_update(bot, formatted_msg)
            else:
                send_market_update(bot, f"⚠️ Не удалось получить данные для {ticker}.")

        time.sleep(60) # Проверка каждые 60 секунд (можно уменьшить для более частых обновлений)

def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    print("Бот запущен...")
    
    # Обработка событий телеграма, если нужно взаимодействие с пользователями
    # Для авто-запуска по таймеру можно использовать только основной цикл
    
    # Запуск основного цикла сбора данных
    asyncio.create_task(main_loop(app))
    
    app.run_polling() # Устаревший метод для простоты

if __name__ == '__main__':
    run_bot()
