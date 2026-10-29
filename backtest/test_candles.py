"""Диагностика get_candles: выбираем TQBR-инструмент."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from t_tech.invest import Client, CandleInterval

load_dotenv(Path(r"C:\trader\.env"), override=True)
TOKEN = os.environ["T_INVEST_TOKEN"]
print(f"token: {TOKEN[:6]}...{TOKEN[-4:]} (len={len(TOKEN)})\n")

with Client(TOKEN) as c:
    print("=== find_instrument SBER ===")
    r = c.instruments.find_instrument(query="SBER")
    for inst in r.instruments:
        print(f"  {inst.ticker} / {inst.class_code} / api_ok={inst.api_trade_available_flag} / uid={inst.uid[:12]}...")

    # Выбираем TQBR
    sber = [
        i for i in r.instruments
        if i.ticker == "SBER"
        and i.class_code == "TQBR"
        and i.api_trade_available_flag
    ]
    if not sber:
        print("SBER TQBR не найден")
        exit()
    inst = sber[0]
    print(f"\nВыбран: uid={inst.uid}, class_code={inst.class_code}, api_ok={inst.api_trade_available_flag}")

    uid = inst.uid

    print("\n=== get_candles тесты ===")
    intervals = {
        "M1":  CandleInterval.CANDLE_INTERVAL_1_MIN,
        "M5":  CandleInterval.CANDLE_INTERVAL_5_MIN,
        "M15": CandleInterval.CANDLE_INTERVAL_15_MIN,
        "H1":  CandleInterval.CANDLE_INTERVAL_HOUR,
        "D1":  CandleInterval.CANDLE_INTERVAL_DAY,
    }
    days_options = [1, 7, 30, 365]

    for name, interval in intervals.items():
        for days in days_options:
            now = datetime.now(timezone.utc)
            try:
                resp = c.market_data.get_candles(
                    instrument_id=uid,
                    from_=now - timedelta(days=days),
                    to=now,
                    interval=interval,
                )
                n = len(resp.candles)
                status = "OK" if n > 0 else "empty"
                print(f"  {name:>3} {days:>4}д: {n:>6} свечей  [{status}]")
                if n > 0:
                    print(f"       первая: {resp.candles[0].time}")
                    print(f"       последняя: {resp.candles[-1].time}")
            except Exception as e:
                print(f"  {name:>3} {days:>4}д: ОШИБКА {str(e)[:100]}")