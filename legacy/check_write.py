import os
"""Мини-тест: API → запись → проверка."""

from datetime import datetime, timedelta, timezone
from t_tech.invest import Client

TOKEN = os.getenv("T_INVEST_TOKEN", "").strip()
FIGI = "BBG004730N88"

with Client(TOKEN) as client:
    now = datetime.now(timezone.utc)
    print("Сейчас UTC:", now)
    print()

    resp = client.market_data.get_last_trades(
        figi=FIGI,
        from_=now - timedelta(seconds=60),
        to=now,
    )

    print("Получено сделок:", len(resp.trades))
    print()

    if resp.trades:
        t = resp.trades[0]
        print("Первая сделка:")
        print("  date_time :", t.date_time)
        print("  price     :", t.price.units, t.price.nano)
        print("  quantity  :", t.quantity)
        print("  direction :", t.direction)
        print("  есть figi? :", hasattr(t, "figi"))
        if hasattr(t, "figi"):
            print("  figi       :", t.figi)
        print("  все поля  :", [a for a in dir(t) if not a.startswith("_")])
        print()

        print("Пробуем записать 3 сделки в trades_test.csv...")
        try:
            with open("trades_test.csv", "w", encoding="utf-8") as f:
                for tr in resp.trades[:3]:
                    price = tr.price.units + tr.price.nano / 1e9
                    figi_val = getattr(tr, "figi", "NO_FIGI")
                    f.write(f"{tr.date_time},{figi_val},{price},{tr.quantity},{tr.direction}\n")
            print("OK, файл записан. Читаем обратно:")
            with open("trades_test.csv", "r", encoding="utf-8") as f:
                for line in f:
                    print("  >", line.strip())
        except Exception as e:
            print("ОШИБКА записи:", e)
    else:
        print("Сделок нет. Возможно, рынок закрыт.")