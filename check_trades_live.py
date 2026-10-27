"""Проверка: возвращает ли API сделки прямо сейчас."""

from datetime import datetime, timedelta, timezone
from t_tech.invest import Client

TOKEN = "t.ftq9FmrqQbILuhhqvE0t4YBkCsWJjRpuFqXBVu3mqViwX89DezqliMHxjcgbzkgri4mbHK3A37xlWaqSHeIWSQ"
FIGI = "BBG004730N88"

with Client(TOKEN) as client:
    now = datetime.now(timezone.utc)
    print("Сейчас UTC:", now)
    print("Запрос trades за последние 60 секунд...")

    resp = client.market_data.get_last_trades(
        figi=FIGI,
        from_=now - timedelta(seconds=60),
        to=now,
    )

    print("Получено сделок:", len(resp.trades))
    print()

    for t in resp.trades[:5]:
        print(f"  date_time={t.date_time}  price={t.price.units}.{t.price.nano}  qty={t.quantity}  dir={t.direction}")

    if not resp.trades:
        print("Сделок нет. Возможные причины:")
        print("  - Сейчас перерыв между сессиями (18:40-19:00 МСК)")
        print("  - Сейчас ночь (МСК после 23:50)")
        print("  - Проблема с токеном")