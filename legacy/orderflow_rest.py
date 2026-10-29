"""REST-сборщик стакана и сделок для нескольких тикеров (GAZP + RUAL)."""

import csv
from pathlib import Path
import os
import time
from datetime import datetime, timedelta, timezone

from t_tech.invest import Client


TOKEN = os.getenv("T_INVEST_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("Не задана переменная окружения T_INVEST_TOKEN")

WORK_DIR = Path(__file__).resolve().parent

TICKERS = ["GAZP", "RUAL"]

POLL_INTERVAL_SEC = 5
TRADES_LOOKBACK_SEC = 60

SEEN_TRADES = {t: set() for t in TICKERS}


def load_seen_trades(ticker):
    """Восстанавливает ключи дедупликации атомарно из CSV при запуске."""
    filename = Path(tr_file(ticker))
    if not filename.exists() or filename.stat().st_size == 0:
        return 0

    pending = set()
    with filename.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"timestamp", "ticker", "figi", "price", "quantity", "direction"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise RuntimeError(
                f"Невозможно восстановить дедупликацию: неверная схема {filename}"
            )

        for row in reader:
            if row.get("ticker", "").strip().upper() != ticker.upper():
                continue
            try:
                key = (
                    str(row["figi"]),
                    row["timestamp"],
                    float(row["price"]),
                    int(row["quantity"]),
                    int(row["direction"]),
                )
            except (ValueError, TypeError, KeyError):
                raise RuntimeError(
                    f"Некорректная строка в {filename}; "
                    "файл не изменён, проверьте CSV вручную."
                )
            pending.add(key)

    new_keys = pending - SEEN_TRADES[ticker]
    SEEN_TRADES[ticker].update(pending)
    return len(new_keys)


def ob_file(ticker):
    return str(WORK_DIR / "orderbook_raw_rest.csv")


def tr_file(ticker):
    return str(WORK_DIR / "trades_raw_rest.csv")


def _ensure_header(filename, headers):
    path = Path(filename)
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(headers)
        return

    with path.open("r", newline="", encoding="utf-8-sig") as f:
        actual = next(csv.reader(f), [])

    if actual != headers:
        raise RuntimeError(
            f"Несовместимый заголовок CSV: {path}. "
            f"Ожидался: {headers}; найден: {actual}. "
            "Файл не изменён; сохраните резервную копию и "
            "проверьте схему вручную."
        )


def _price_to_float(p):
    if p is None:
        return None
    return p.units + p.nano / 1e9


def save_orderbook(ticker, ob, ts_iso):
    row = [ts_iso, ticker, ob.figi]
    for i in range(5):
        if i < len(ob.bids):
            b = ob.bids[i]
            row.extend([_price_to_float(b.price), b.quantity])
        else:
            row.extend(["", ""])
    for i in range(5):
        if i < len(ob.asks):
            a = ob.asks[i]
            row.extend([_price_to_float(a.price), a.quantity])
        else:
            row.extend(["", ""])
    with open(ob_file(ticker), "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)


def save_new_trades(ticker, trades_list):
    new_count = 0
    with open(tr_file(ticker), "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for t in trades_list:
            ts = t.time.isoformat() if t.time else datetime.now(timezone.utc).isoformat()
            price = _price_to_float(t.price)
            qty = t.quantity
            direction = int(t.direction) if t.direction is not None else 0
            key = (str(t.figi), ts, price, qty, direction)
            if key in SEEN_TRADES[ticker]:
                continue
            w.writerow([ts, ticker, t.figi, price, qty, direction])
            SEEN_TRADES[ticker].add(key)
            new_count += 1
    return new_count

KNOWN_FIGI = {
    "SBER": "BBG004730N88",
    "GAZP": "BBG004730RP0",
    "RUAL": "BBG004S68B31",
    "LKOH": "BBG004731032",
    "VTBR": "BBG004730ZJ9",
    "MTLR": "BBG004S68CG2",
}


def find_figi(client, ticker):
    """Использует известные BBG-FIGI, чтобы избежать внутренних TCS-форматов."""
    if ticker in KNOWN_FIGI:
        return KNOWN_FIGI[ticker], ticker
    # fallback — через API
    try:
        resp = client.instruments.find_instrument(query=ticker)
        matches = [i for i in resp.instruments if i.ticker == ticker]
        if not matches:
            matches = resp.instruments
        if not matches:
            return None, None
        return matches[0].figi, matches[0].name
    except Exception as e:
        print(f"Ошибка поиска {ticker}: {e}")
        return None, None



def main():
    # Заголовки файлов
    ob_headers = ["timestamp", "ticker", "figi"]
    for i in range(1, 6):
        ob_headers.extend([f"bid{i}_price", f"bid{i}_qty"])
    for i in range(1, 6):
        ob_headers.extend([f"ask{i}_price", f"ask{i}_qty"])

    tr_headers = ["timestamp", "ticker", "figi", "price", "quantity", "direction"]

    for t in TICKERS:
        _ensure_header(ob_file(t), ob_headers)
        _ensure_header(tr_file(t), tr_headers)

    for t in TICKERS:
        loaded = load_seen_trades(t)
        print(f"{t}: восстановлено ключей сделок: {loaded}")

    print("Подключаемся к T-Invest API...")

    with Client(TOKEN) as client:
        # Находим FIGI для всех тикеров
        instruments = {}
        for t in TICKERS:
            figi, name = find_figi(client, t)
            if figi:
                instruments[t] = figi
                print(f"  {t}: {name}  FIGI={figi}")
            else:
                print(f"  {t}: НЕ НАЙДЕН — пропускаем")

        if not instruments:
            raise RuntimeError(
                "Ни одного инструмента не найдено. "
                "Проверьте доступ к API и идентификаторы инструментов."
            )

        print("\nCtrl+C для остановки.\n")

        cycle = 0
        totals = {t: 0 for t in instruments}

        try:
            while True:
                cycle += 1
                now = datetime.now(timezone.utc)
                now_iso = now.isoformat()
                status_parts = []

                for ticker, figi in instruments.items():
                    # Стакан
                    try:
                        ob_resp = client.market_data.get_order_book(figi=figi, depth=10)
                        save_orderbook(ticker, ob_resp, now_iso)
                    except Exception as e:
                        print(f"ОШИБКА стакана {ticker}: {type(e).__name__}: {e}",
                              flush=True)
                        status_parts.append(f"{ticker}:OB_err")

                    # Сделки
                    try:
                        trades_resp = client.market_data.get_last_trades(
                            figi=figi,
                            from_=now - timedelta(seconds=TRADES_LOOKBACK_SEC),
                            to=now,
                        )
                        new_t = save_new_trades(ticker, trades_resp.trades)
                        totals[ticker] += new_t
                    except Exception as e:
                        print(f"ОШИБКА сделок {ticker}: {type(e).__name__}: {e}",
                              flush=True)
                        new_t = 0
                        status_parts.append(f"{ticker}:TR_err")
                    else:
                        status_parts.append(f"{ticker}+{new_t}")

                print("[" + datetime.now().strftime('%H:%M:%S') + "] цикл",
                      cycle, ":", " | ".join(status_parts),
                      "| totals:", {t: totals[t] for t in instruments})

                time.sleep(POLL_INTERVAL_SEC)

        except KeyboardInterrupt:
            print("\nОстановлено. Итого сделок:", totals)


if __name__ == "__main__":
    main()

