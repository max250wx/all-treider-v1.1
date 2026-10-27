"""Смотрим, какие поля есть у объекта Trade."""

from datetime import datetime, timedelta, timezone
from t_tech.invest import Client

TOKEN = "t.ftq9FmrqQbILuhhqvE0t4YBkCsWJjRpuFqXBVu3mqViwX89DezqliMHxjcgbzkgri4mbHK3A37xlWaqSHeIWSQ"
FIGI = "BBG004730N88"

with Client(TOKEN) as client:
    now = datetime.now(timezone.utc)
    resp = client.market_data.get_last_trades(
        figi=FIGI,
        from_=now - timedelta(seconds=60),
        to=now,
    )

    print("Сделок:", len(resp.trades))
    if not resp.trades:
        raise SystemExit

    t = resp.trades[0]
    print()
    print("Тип объекта:", type(t))
    print()
    print("Все атрибуты:")
    for a in dir(t):
        if a.startswith("_"):
            continue
        try:
            val = getattr(t, a)
            if callable(val):
                continue
            print(f"  {a:30s} = {val}")
        except Exception as e:
            print(f"  {a:30s} = <ошибка: {e}>")