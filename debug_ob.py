"""Минимальная диагностика: только стакан."""

import time
from t_tech.invest import Client
from t_tech.invest.schemas import OrderBookInstrument

TOKEN = "t.ftq9FmrqQbILuhhqvE0t4YBkCsWJjRpuFqXBVu3mqViwX89DezqliMHxjcgbzkgri4mbHK3A37xlWaqSHeIWSQ"
FIGI = "BBG004730N88"

with Client(TOKEN) as client:
    stream = client.create_market_data_stream()
    stream.order_book.subscribe([OrderBookInstrument(figi=FIGI, depth=5)])

    print("Подписка на стакан. Ждём 20 сек...")
    t0 = time.time()
    count = 0

    for md in stream:
        if md.orderbook is not None:
            count += 1
            if count <= 3:
                print(f"[{count}] bid1={md.orderbook.bids[0].price.units} ask1={md.orderbook.asks[0].price.units}")
        if time.time() - t0 > 20:
            break

    print(f"Всего событий: {count}")