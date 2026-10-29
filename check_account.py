import os
"""Проверка: доступен ли аккаунт и маркет-данные."""

from t_tech.invest import Client

TOKEN = os.getenv("T_INVEST_TOKEN", "").strip()

with Client(TOKEN) as client:
    print("1. Проверка аккаунтов...")
    try:
        accounts = client.users.get_accounts()
        print(f"   OK. Аккаунтов: {len(accounts.accounts)}")
        for a in accounts.accounts:
            print(f"     - {a.id[:8]}... status={a.status} type={a.type} name={a.name}")
    except Exception as e:
        print(f"   ОШИБКА: {e}")

    print("\n2. Проверка доступа к инструментам...")
    try:
        instruments = client.instruments.get_instrument_by(
            id_type=1,  # 1 = FIGI
            id="BBG004730N88",
        )
        print(f"   OK. Инструмент: {instruments.instrument.ticker} / {instruments.instrument.name}")
    except Exception as e:
        print(f"   ОШИБКА: {e}")

    print("\n3. Проверка котировок (get_last_trades)...")
    try:
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        trades = client.market_data.get_last_trades(
            figi="BBG004730N88",
            from_=now - timedelta(minutes=10),
            to=now,
        )
        print(f"   OK. Последних сделок за 10 мин: {len(trades.trades)}")
        for t in trades.trades[:3]:
            print(f"     - price={t.price.units}.{t.price.nano}, qty={t.quantity}")
    except Exception as e:
        print(f"   ОШИБКА: {e}")
