"""Отправка сигналов в Telegram."""
import os
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()


def enabled() -> bool:
    return bool(TOKEN and CHAT_ID)


def send(text: str):
    if not enabled():
        return False, "TG_BOT_TOKEN/TG_CHAT_ID не заданы в .env"
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if r.status_code == 200:
            return True, "ok"
        return False, f"HTTP {r.status_code}: {r.text[:150]}"
    except Exception as e:
        return False, str(e)


def send_signal(ticker: str, side: str, score: int, price=None):
    emoji = {"LONG": "🟢", "SHORT": "🔴"}.get(side, "⚪")
    lines = [f"{emoji} <b>{side} {ticker}</b>", f"score: {score:+d}"]
    if price is not None:
        lines.append(f"цена: {price}")
    lines.append(f"время: {datetime.now():%H:%M:%S}")
    return send("\n".join(lines))


def send_test():
    return send(f"✅ Тест от AI-Trader MOEX\nВремя: {datetime.now():%H:%M:%S}")


if __name__ == "__main__":
    ok, msg = send_test()
    print("OK" if ok else "ОШИБКА:", msg)
