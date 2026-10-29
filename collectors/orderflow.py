"""Сборщик стакана и сделок через T-Invest API.
Пишет в data/live/orderbook_<TICKER>.csv и data/live/trades_<TICKER>.csv.
"""

import csv
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv
from t_tech.invest import Client

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
load_dotenv(ROOT / ".env", override=True)

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

TOKEN = os.environ.get("T_INVEST_TOKEN")
if not TOKEN:
    print("ОШИБКА: T_INVEST_TOKEN не задан в .env", file=sys.stderr)
    sys.exit(1)

TICKERS = CFG["collectors"]["tickers"]
POLL_INTERVAL_SEC = CFG["collectors"]["poll_interval_sec"]
TRADES_LOOKBACK_SEC = CFG["collectors"]["trades_lookback_sec"]
DATA_DIR = ROOT / CFG["paths"]["data_live"]
DATA_DIR.mkdir(parents=True, exist_ok=True)

KNOWN_FIGI = {
    "SBER": "BBG004730N88",
    "GAZP": "BBG004730RP0",
    "LKOH": "BBG004731032",
    "VTBR": "BBG004730ZJ9",
    # RUAL, MTLR и другие — ищутся через API, чтобы не ошибиться
}

SEEN_TRADES = {t: set() for t in TICKERS}


def ob_file(t):
    return DATA_DIR / f"orderbook_{t}.csv"


def tr_file(t):
    return DATA_DIR / f"trades_{t}.csv"


def _ensure_header(path, headers):
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(headers)


def _price(p):
    if p is None:
        return None
    return p.units + p.nano / 1e9


def save_orderbook(ticker, ob, ts_iso):
    row = [ts_iso, ticker, ob.figi]
    for i in range(5):
        if i < len(ob.bids):
            row.extend([_price(ob.bids[i].price), ob.bids[i].quantity])
        else:
            row.extend(["", ""])
    for i in range(5):
        if i < len(ob.asks):
            row.extend([_price(ob.asks[i].price), ob.asks[i].quantity])
        else:
            row.extend(["", ""])
    with open(ob_file(ticker), "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)


def save_trades(ticker, trades_list):
    n = 0
    with open(tr_file(ticker), "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for t in trades_list:
            ts = t.time.isoformat() if t.time else datetime.now(UTC).isoformat()
            price = _price(t.price)
            qty = t.quantity
            direction = int(t.direction) if t.direction is not None else 0
            key = (ts, price, qty, direction)
            if key in SEEN_TRADES[ticker]:
                continue
            SEEN_TRADES[ticker].add(key)
            w.writerow([ts, t.figi, price, qty, direction])
            n += 1
    return n


def find_instrument(client, ticker):
    """Возвращает (instrument_uid, figi, name) через instrument_by."""
    figi = KNOWN_FIGI.get(ticker)
    try:
        if figi:
            r = client.instruments.get_instrument_by(
                id_type=1,  # INSTRUMENT_ID_TYPE_FIGI
                id=figi,
            )
        else:
            r = client.instruments.get_instrument_by(
                id_type=2,  # INSTRUMENT_ID_TYPE_TICKER
                id=ticker,
                class_code="TQBR",
            )
        inst = r.instrument
        return inst.uid, inst.figi, inst.name
    except Exception as e:
        print(f"  {ticker}: ошибка поиска ({e})")
        return None, None, None


def run(once=False):
    ob_headers = ["timestamp", "ticker", "figi"]
    for i in range(1, 6):
        ob_headers += [f"bid{i}_price", f"bid{i}_qty"]
    for i in range(1, 6):
        ob_headers += [f"ask{i}_price", f"ask{i}_qty"]
    tr_headers = ["timestamp", "figi", "price", "quantity", "direction"]

    for t in TICKERS:
        _ensure_header(ob_file(t), ob_headers)
        _ensure_header(tr_file(t), tr_headers)

    print(f"Подключаемся к T-Invest API. Тикеры: {TICKERS}")
    with Client(TOKEN) as client:
        instruments = {}
        for t in TICKERS:
            uid, figi, name = find_instrument(client, t)
            if uid:
                instruments[t] = (uid, figi, name)
                print(f"  {t}: {name}  uid={uid[:12]}... figi={figi}")
            else:
                print(f"  {t}: НЕ НАЙДЕН")

        if not instruments:
            print("Ни одного инструмента не найдено")
            return

        print("\nCtrl+C для остановки.\n")
        cycle = 0
        totals = dict.fromkeys(instruments, 0)
        try:
            while True:
                cycle += 1
                now = datetime.now(UTC)
                status = []
                for ticker, (uid, _figi, _) in instruments.items():
                    # Стакан
                    try:
                        ob = client.market_data.get_order_book(
                            instrument_id=uid,
                            depth=10,
                        )
                        save_orderbook(ticker, ob, now.isoformat())
                        status.append(f"{ticker}:OB_ok")
                    except Exception as e:
                        status.append(f"{ticker}:OB_err({str(e)[:30]})")

                    # Сделки
                    try:
                        tr = client.market_data.get_last_trades(
                            instrument_id=uid,
                            from_=now - timedelta(seconds=TRADES_LOOKBACK_SEC),
                            to=now,
                        )
                        n = save_trades(ticker, tr.trades)
                        totals[ticker] += n
                        status.append(f"{ticker}+{n}")
                    except Exception as e:
                        status.append(f"{ticker}:TR_err({str(e)[:30]})")

                print(
                    f"[{datetime.now():%H:%M:%S}] цикл {cycle}: {' | '.join(status)} "
                    f"| totals: {totals}"
                )
                if once:
                    break
                time.sleep(POLL_INTERVAL_SEC)
        except KeyboardInterrupt:
            print(f"\nОстановлено. Итого: {totals}")


if __name__ == "__main__":
    run(once="--once" in sys.argv)
