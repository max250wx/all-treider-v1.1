"""Сбор индекса страха RVI с Московской биржи (с задержкой 15 минут)."""

import csv
import os
import time
import requests
from datetime import datetime, timezone


RVI_FILE = "rvi_data.csv"
RVI_URL = "https://iss.moex.com/iss/engines/stock/markets/index/securities.json"


def _ensure_header():
    if not os.path.exists(RVI_FILE):
        with open(RVI_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["timestamp", "rvi_current", "rvi_last",
                                     "change_pct", "updated_at"])


def get_rvi() -> dict:
    """Возвращает текущее значение RVI и его изменение."""
    params = {
        "iss.meta": "off",
        "iss.only": "marketdata",
        "securities": "RVI",
    }

    try:
        r = requests.get(RVI_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return {"error": str(e)}

    md = data.get("marketdata", {})
    cols = md.get("columns", [])
    rows = md.get("data", [])

    if not rows:
        return {"error": "Пустой ответ от MOEX ISS"}

    row = rows[0]

    def val(name):
        if name not in cols:
            return None
        return row[cols.index(name)]

    return {
        "current": val("CURRENTVALUE"),
        "last": val("LASTVALUE"),
        "change_pct": val("LASTCHANGEPRC"),
        "updated_at": val("UPDATETIME") or "",
        "trade_date": val("TRADEDATE") or "",
    }


def save_rvi(ts_iso, r):
    with open(RVI_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            ts_iso,
            r.get("current"),
            r.get("last"),
            r.get("change_pct"),
            r.get("updated_at"),
        ])


def main():
    _ensure_header()
    print("Сбор RVI (с задержкой 15 мин). Ctrl+C для остановки.\n")

    while True:
        ts_iso = datetime.now(timezone.utc).isoformat()
        r = get_rvi()

        if "error" in r:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка: {r['error']}")
        else:
            cur = r["current"]
            last = r["last"]
            ch = r["change_pct"]
            upd = r["updated_at"]

            if cur is None:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] CURRENTVALUE = None (индекс не торгуется?)")
            else:
                ch_str = f"{ch:+.2f}%" if ch is not None else "н/д"
                last_str = f"{last:.2f}" if last is not None else "н/д"
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"RVI = {cur:.2f}  (закр. {last_str}, изм. {ch_str}, обн. {upd})")
                save_rvi(ts_iso, r)

        time.sleep(60)


if __name__ == "__main__":
    main()