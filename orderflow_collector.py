"""Сборщик с heartbeat и автопереподключением."""

import csv
import os
import time
from datetime import datetime, timezone

from t_tech.invest import Client
from t_tech.invest.schemas import OrderBookInstrument


TOKEN = "t.ftq9FmrqQbILuhhqvE0t4YBkCsWJjRpuFqXBVu3mqViwX89DezqliMHxjcgbzkgri4mbHK3A37xlWaqSHeIWSQ"
INSTRUMENT_ID = "SBER"
ORDERBOOK_DEPTH = 10
ORDERBOOK_INTERVAL_SEC = 5
HEARTBEAT_TIMEOUT = 60        # если нет событий 60 сек — переподключиться

ORDERBOOK_FILE = "orderbook_raw.csv"
TRADES_FILE = "trades_raw.csv"

FIGI_MAP = {
    "SBER": "BBG004730N88",
    "GAZP": "BBG004730RP0",
    "LKOH": "BBG004731032",
}


def _ensure_csv_header(filename, headers):
    if not os.path.exists(filename):
        with open(filename, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(headers)


def _price_to_float(price):
    if price is None:
        return None
    return price.units + price.nano / 1e9


def save_orderbook(orderbook):
    ts = datetime.now(timezone.utc).isoformat()
    row = [ts, INSTRUMENT_ID, orderbook.figi]

    for i in range(5):
        if i < len(orderbook.bids):
            b = orderbook.bids[i]
            row.extend([_price_to_float(b.price), b.quantity])
        else:
            row.extend(["", ""])

    for i in range(5):
        if i < len(orderbook.asks):
            a = orderbook.asks[i]
            row.extend([_price_to_float(a.price), a.quantity])
        else:
            row.extend(["", ""])

    with open(ORDERBOOK_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)


def save_trade(trade):
    ts = trade.date_time.isoformat() if trade.date_time else datetime.now(timezone.utc).isoformat()
    row = [
        ts,
        getattr(trade, "figi", INSTRUMENT_ID),
        _price_to_float(trade.price),
        trade.quantity,
        int(trade.direction) if trade.direction is not None else "",
    ]
    with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)


def stream_once(client, figi):
    """Один сеанс подписки. Возвращает False, если нужно переподключиться."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Открываем стрим...")

    stream = client.create_market_data_stream()
    stream.order_book.subscribe([OrderBookInstrument(figi=figi, depth=ORDERBOOK_DEPTH)])
    stream.trades.subscribe([figi])

    last_event = time.time()
    last_ob = 0
    t_start = time.time()

    for md in stream:
        now_ts = time.time()
        last_event = now_ts

        if md.orderbook is not None:
            if now_ts - last_ob >= ORDERBOOK_INTERVAL_SEC:
                save_orderbook(md.orderbook)
                last_ob = now_ts
                print(f"[{datetime.now().strftime('%H:%M:%S')}] стакан сохранён")

        if md.trade is not None:
            save_trade(md.trade)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"сделка {_price_to_float(md.trade.price)} x {md.trade.quantity}")

        # Heartbeat-контроль: если давно нет событий — выйти
        if now_ts - last_event > HEARTBEAT_TIMEOUT:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] нет событий {HEARTBEAT_TIMEOUT} сек — переподключение")
            return False

    return False


def main():
    ob_headers = ["timestamp", "ticker", "figi"]
    for i in range(1, 6):
        ob_headers.extend([f"bid{i}_price", f"bid{i}_qty"])
    for i in range(1, 6):
        ob_headers.extend([f"ask{i}_price", f"ask{i}_qty"])
    _ensure_csv_header(ORDERBOOK_FILE, ob_headers)

    tr_headers = ["timestamp", "figi", "price", "quantity", "direction"]
    _ensure_csv_header(TRADES_FILE, tr_headers)

    figi = FIGI_MAP.get(INSTRUMENT_ID, INSTRUMENT_ID)
    print(f"Старт: {INSTRUMENT_ID}  FIGI: {figi}")

    while True:
        try:
            with Client(TOKEN) as client:
                while True:
                    try:
                        stream_once(client, figi)
                    except KeyboardInterrupt:
                        print("\nПрервано пользователем.")
                        return
                    except Exception as e:
                        print(f"Ошибка стрима: {e}")
                        time.sleep(3)
        except Exception as e:
            print(f"Ошибка клиента: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()