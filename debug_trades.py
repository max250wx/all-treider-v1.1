"""Диагностика: что приходит в стриме от T-Invest."""

import time
from t_tech.invest import Client
from t_tech.invest.schemas import OrderBookInstrument

TOKEN = "t.ftq9FmrqQbILuhhqvE0t4YBkCsWJjRpuFqXBVu3mqViwX89DezqliMHxjcgbzkgri4mbHK3A37xlWaqSHeIWSQ"
FIGI = "BBG004730N88"


def main():
    print("Запуск диагностики...")
    with Client(TOKEN) as client:
        stream = client.create_market_data_stream()
        stream.order_book.subscribe([OrderBookInstrument(figi=FIGI, depth=5)])
        stream.trades.subscribe([FIGI])

        print("Подписки: order_book, trades")
        print("Ждём 25 секунд...\n")

        counts = {"orderbook": 0, "trade": 0, "last_price": 0, "candle": 0, "other": 0}
        shown_trade = 0
        shown_lp = 0
        t0 = time.time()

        for md in stream:
            has_ob = md.orderbook is not None
            has_trade = md.trade is not None
            has_lp = getattr(md, "last_price", None) is not None
            has_cd = getattr(md, "candle", None) is not None

            if has_ob:
                counts["orderbook"] += 1

            if has_trade:
                counts["trade"] += 1
                if shown_trade < 5:
                    shown_trade += 1
                    print("TRADE:", md.trade)
                    print("  поля:", [a for a in dir(md.trade) if not a.startswith("_")])
                    print()

            if has_lp:
                counts["last_price"] += 1
                if shown_lp < 3:
                    shown_lp += 1
                    print("LAST_PRICE:", md.last_price, "\n")

            if has_cd:
                counts["candle"] += 1

            if not (has_ob or has_trade or has_lp or has_cd):
                counts["other"] += 1

            if time.time() - t0 > 25:
                break

        print("=" * 50)
        print("Счётчики за 25 секунд:")
        for k, v in counts.items():
            print(f"  {k:12s}: {v}")
        print("=" * 50)


if __name__ == "__main__":
    main()