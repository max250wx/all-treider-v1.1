"""Сбор индекса страха RVI с Московской биржи.
Пишет в data/live/rvi_data.csv. Конфиг: config.yaml.
С retry: MOEX ISS иногда рвёт SSL (блокировка из-за границы).
"""

import csv
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

DATA_DIR = ROOT / CFG["paths"]["data_live"]
DATA_DIR.mkdir(parents=True, exist_ok=True)
RVI_FILE = DATA_DIR / "rvi_data.csv"

POLL_SEC = CFG["collectors"]["rvi_poll_sec"]
RVI_URL = "https://iss.moex.com/iss/engines/stock/markets/index/securities.json"


def _ensure_header():
    if not RVI_FILE.exists():
        with open(RVI_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                [
                    "timestamp",
                    "rvi_current",
                    "rvi_last",
                    "change_pct",
                    "updated_at",
                ]
            )


def get_rvi(retries=3) -> dict:
    """С retry: MOEX ISS иногда рвёт SSL."""
    params = {
        "iss.meta": "off",
        "iss.only": "marketdata",
        "securities": "RVI",
    }
    last_err = None
    data = None
    for attempt in range(retries):
        try:
            r = requests.get(
                RVI_URL,
                params=params,
                timeout=20,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            last_err = str(e)
            if attempt < retries - 1:
                time.sleep(2**attempt)
            continue
    if data is None:
        return {"error": last_err or "unknown"}

    md = data.get("marketdata", {})
    cols = md.get("columns", [])
    rows = md.get("data", [])
    if not rows:
        return {"error": "Пустой ответ от MOEX ISS"}

    row = rows[0]

    def val(name):
        return row[cols.index(name)] if name in cols else None

    return {
        "current": val("CURRENTVALUE"),
        "last": val("LASTVALUE"),
        "change_pct": val("LASTCHANGEPRC"),
        "updated_at": val("UPDATETIME") or "",
        "trade_date": val("TRADEDATE") or "",
    }


def save_rvi(ts_iso, r):
    with open(RVI_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            [
                ts_iso,
                r.get("current"),
                r.get("last"),
                r.get("change_pct"),
                r.get("updated_at"),
            ]
        )


def run(once=False):
    _ensure_header()
    print(f"Сбор RVI. Файл: {RVI_FILE}")
    print("Ctrl+C для остановки.\n")
    try:
        while True:
            ts_iso = datetime.now(UTC).isoformat()
            r = get_rvi()
            if "error" in r:
                print(f"[{datetime.now():%H:%M:%S}] Ошибка: {r['error']}")
            else:
                cur = r["current"]
                if cur is None:
                    print(f"[{datetime.now():%H:%M:%S}] CURRENTVALUE = None")
                else:
                    ch = r["change_pct"]
                    ch_str = f"{ch:+.2f}%" if ch is not None else "н/д"
                    last_str = f"{r['last']:.2f}" if r["last"] is not None else "н/д"
                    print(
                        f"[{datetime.now():%H:%M:%S}] RVI = {cur:.2f}  "
                        f"(закр. {last_str}, изм. {ch_str}, обн. {r['updated_at']})"
                    )
                    save_rvi(ts_iso, r)
            if once:
                break
            time.sleep(POLL_SEC)
    except KeyboardInterrupt:
        print("\nОстановлено.")


if __name__ == "__main__":
    run(once="--once" in sys.argv)
