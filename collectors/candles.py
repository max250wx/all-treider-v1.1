"""Сбор M10 свечей через T-Invest каждые 10 минут."""
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv
from t_tech.invest import Client, CandleInterval

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)
with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

TOKEN = os.environ["T_INVEST_TOKEN"]
DATA_DIR = ROOT / CFG["paths"]["data_live"]
DATA_DIR.mkdir(parents=True, exist_ok=True)

TICKERS = CFG["collectors"]["tickers"]
POLL_MIN = CFG["collectors"].get("candles_interval_min", 10)
INTERVAL = CandleInterval.CANDLE_INTERVAL_10_MIN
DAYS_BACK = 7


def get_uid(client, ticker):
    try:
        r = client.instruments.find_instrument(query=ticker)
        matches = [i for i in r.instruments if i.ticker == ticker and i.api_trade_available_flag]
        if not matches:
            matches = [i for i in r.instruments if i.ticker == ticker]
        return matches[0].uid if matches else None
    except Exception as e:
        print(f"  {ticker}: {e}")
        return None


def fetch(client, uid):
    now = datetime.now(timezone.utc)
    try:
        r = client.market_data.get_candles(
            instrument_id=uid, from_=now - timedelta(days=DAYS_BACK),
            to=now, interval=INTERVAL,
        )
        return r.candles
    except Exception as e:
        print(f"  get_candles: {e}")
        return []


def to_df(candles):
    rows = [{
        "timestamp": c.time,
        "open": c.open.units + c.open.nano / 1e9,
        "high": c.high.units + c.high.nano / 1e9,
        "low": c.low.units + c.low.nano / 1e9,
        "close": c.close.units + c.close.nano / 1e9,
        "volume": c.volume,
    } for c in candles]
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.set_index("timestamp").sort_index()


def run(once=False):
    print(f"Сбор M10 свечей: {TICKERS}")
    print(f"Каждые {POLL_MIN} мин, история {DAYS_BACK} дней\n")
    while True:
        with Client(TOKEN) as client:
            for ticker in TICKERS:
                uid = get_uid(client, ticker)
                if not uid:
                    print(f"  {ticker}: uid не найден")
                    continue
                candles = fetch(client, uid)
                if not candles:
                    print(f"  {ticker}: 0 свечей")
                    continue
                df = to_df(candles)
                out = DATA_DIR / f"candles_{ticker}.csv"
                df.to_csv(out)
                print(f"[{datetime.now():%H:%M:%S}] {ticker}: {len(df)} баров, "
                      f"последний {df.index[-1]:%Y-%m-%d %H:%M}")
        if once:
            break
        time.sleep(POLL_MIN * 60)


if __name__ == "__main__":
    import sys
    run(once="--once" in sys.argv)