"""Центральная конфигурация проекта."""

import os

# ─── AI-модель ───
MODEL = "qwen2.5:7b"
# Для 12+ ГБ VRAM: "qwen2.5:14b"
# Для 24+ ГБ VRAM: "qwen2.5:32b"

# ─── T-Invest API ───
TOKEN = os.getenv("T_INVEST_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("Не задана переменная окружения T_INVEST_TOKEN")
# ─── Тикеры для сбора ───
TICKERS = ["GAZP", "RUAL"]

# ─── Интервалы ───
POLL_INTERVAL_SEC = 5
TRADES_LOOKBACK_SEC = 60
NEWS_UPDATE_MIN = 60
WATCHDOG_CHECK_SEC = 60
STALL_MINUTES = 5

# ─── RVI ───
RVI_POLL_SEC = 60
