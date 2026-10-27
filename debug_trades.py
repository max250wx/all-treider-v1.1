"""
Диагностика: что именно приходит в стриме.
Показывает все события — orderbook, trade, last_price, candle.
"""

import time
from datetime import datetime
from t_tech.invest import Client


TOKEN = "t.ftq9FmrqQbILuhhqvE0t4YBkCsWJjRpuFqXBVu3mqViwX89DezqliMHxjcgbzkgri4mbHK3A37xlWaqSHeIWSQ"
INSTRUMENT_ID = "SBER"
FIGI = "BBG004730N88"


def main():
    print("Запуск диагностики потока данных...")

    with Client(TOKEN) as client:
        stream = client.create_market_data_stream()

        # Подписки
        from t_tech.invest.schemas import OrderBookInstrument
        stream.order_book.subscribe([OrderBookInstrument(figi=FIGI, depth=5)])
        stream.trades.subscribe([FIGI])

        print("Подписка оформлена. Ждём событий 20 секунд...")

        counter = {"orderbook": 0, "trade": 0, "last_price": 0, "candle": 0, "other": 0}
        t0 = time.time()

        try:
            for md in stream:
                # Определяем, какие поля не None
                has_ob = md.orderbook is not None
                has_tr = md.trade is not None
                has_lp = getattr(md, "last_price", None) is not None
                has_cd = getattr(md, "candle", None) is not None

                if has_ob:
                    counter["orderbook"] += 1
                    if counter["orderbook"] <= 2:
                        print(f"\n[ORDERBOOK] {md.orderbook}")

                if has_tr:
                    counter["trade"] += 1
                    if counter["trade"] <= 5:
                        print(f"\n[TRADE] {md.trade}")
                        print("  поля:", [a for a in dir(md.trade) if not a.startswith("_")])

                if has_lp:
                    counter["last_price"] += 1
                    if counter["last_price"] <= 3:
                        print(f"\n[LAST_PRICE] {md.last_price}")

                if has_cd:
                    counter["candle"] += 1
                    if counter["candle"] <= 2:
                        print(f"\n[CANDLE] {md.candle}")

                if not (has_ob or has_tr or has_lp or has_cd):
                    counter["other"] += 1
                    if counter["other"] <= 3:
                        print(f"\n[OTHER] {md}")

                # Остановиться через 20 секунд
                if time.time() - t0 > 20:
                    break

        except KeyboardInterrupt:
            print("\nПрервано")
        except Exception as e:
            print(f"\nОшибка: {e}")

        print("\n" + "=" * 50)
        print("Счётчики событий за 20 секунд:")
        for k, v in counter.items():
            print(f"  {k:12s}: {v}")
        print("=" * 50)


if __name__ == "__main__":
    main()