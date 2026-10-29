"""
AI-агент v4: тональность + тема + важность + влияние на каждый тикер.
Qwen классифицирует, Python формирует рекомендации.
"""

import ollama
import pandas as pd
import os
import time
from datetime import datetime, timezone, timedelta

MODEL = "qwen2.5:7b"
NEWS_MAX_AGE_HOURS = 24
MIN_PRIORITY = 3  # показывать только новости с важностью ≥3


def get_current_rvi():
    if not os.path.exists("rvi_data.csv"):
        return None, None
    try:
        df = pd.read_csv("rvi_data.csv")
        if df.empty:
            return None, None
        last = df.iloc[-1]
        return float(last["rvi_current"]), float(last["change_pct"])
    except Exception:
        return None, None


def load_fresh_news(path="news_sentiment.csv", hours=24):
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    fresh = df[df["timestamp"] >= cutoff].copy()
    print(f"Всего новостей: {len(df)}")
    print(f"Свежих за {hours}ч: {len(fresh)}")
    if len(fresh) < 20:
        fresh = df.nlargest(30, "timestamp")
    return fresh


def classify_news(title):
    """Qwen возвращает 6 полей одним запросом."""
    prompt = (
        "Ты — аналитик российского фондового рынка.\n"
        "Проанализируй новость и ответь РОВНО 6 строк:\n"
        "\n"
        "ТОНАЛЬНОСТЬ: POSITIVE | NEGATIVE | NEUTRAL\n"
        "ТЕМА: GEO | CB | OIL | CORP | OTHER\n"
        "ВАЖНОСТЬ: 1 | 2 | 3 | 4 | 5\n"
        "SBER: UP | DOWN | NEUTRAL\n"
        "GAZP: UP | DOWN | NEUTRAL\n"
        "RUAL: UP | DOWN | NEUTRAL\n"
        "\n"
        "ШКАЛА ВАЖНОСТИ:\n"
        "5 — КРИТИЧНО: санкции, война, ставка ЦБ, крупные геополитические сдвиги\n"
        "4 — ВАЖНО: корпоративные отчёты крупных, ОПЕК+, решения правительства\n"
        "3 — СРЕДНЕ: региональные события, отраслевые новости, отчёты средних\n"
        "2 — НИЗКО: локальные события, статистика, погода\n"
        "1 — ШУМ: криминал, спорт, культура, развлечения\n"
        "\n"
        "ПРИМЕРЫ:\n"
        "«США ввели санкции против Газпрома» → NEGATIVE, GEO, 5, DOWN, DOWN, DOWN\n"
        "«ЦБ повысил ставку до 20%» → NEGATIVE, CB, 5, DOWN, DOWN, DOWN\n"
        "«Сбербанк рекордная прибыль» → POSITIVE, CORP, 4, UP, NEUTRAL, NEUTRAL\n"
        "«Нефть Brent выросла на 3%» → POSITIVE, OIL, 4, NEUTRAL, UP, NEUTRAL\n"
        "«Белгород под атакой БПЛА» → NEGATIVE, GEO, 3, NEUTRAL, NEUTRAL, NEUTRAL\n"
        "«Ограничения в аэропортах Екатеринбурга» → NEUTRAL, GEO, 2, NEUTRAL, NEUTRAL, NEUTRAL\n"
        "«Мошенники угрожают родителям» → NEUTRAL, OTHER, 1, NEUTRAL, NEUTRAL, NEUTRAL\n"
        "«ДТП в Свердловске» → NEUTRAL, OTHER, 1, NEUTRAL, NEUTRAL, NEUTRAL"
    )

    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Новость: " + title},
        ],
        options={"temperature": 0.0, "num_predict": 100},
    )
    text = response["message"]["content"].strip().upper()

    def find_value(keys, allowed, default):
        for k in keys:
            # Ищем строку с ключом
            for line in text.split("\n"):
                if k in line:
                    for v in allowed:
                        if v in line:
                            return v
        # Fallback — ищем во всём тексте
        for v in allowed:
            if v in text:
                return v
        return default

    ton = find_value(["ТОНАЛЬНОСТЬ", "TONALITY"], ["POSITIVE", "NEGATIVE", "NEUTRAL"], "NEUTRAL")
    theme = find_value(["ТЕМА", "THEME"], ["GEO", "CB", "OIL", "CORP", "OTHER"], "OTHER")
    sber = find_value(["SBER"], ["UP", "DOWN"], "NEUTRAL")
    gazp = find_value(["GAZP"], ["UP", "DOWN"], "NEUTRAL")
    rual = find_value(["RUAL"], ["UP", "DOWN"], "NEUTRAL")

    # Важность — ищем число 1-5 после ВАЖНОСТЬ
    priority = 1
    for line in text.split("\n"):
        if "ВАЖНОСТЬ" in line:
            for c in line:
                if c in "12345":
                    priority = int(c)
                    break
            break

    return {
        "ton": ton, "theme": theme, "priority": priority,
        "sber": sber, "gazp": gazp, "rual": rual,
    }


def decide_signal(ton, theme, target, rvi, rvi_change):
    """Сигнал по конкретному тикеру."""
    reasons = []

    rvi_high = rvi is not None and rvi > 40
    rvi_low = rvi is not None and rvi < 20
    rvi_falling = rvi_change is not None and rvi_change < -3
    rvi_rising = rvi_change is not None and rvi_change > 5

    if target == "UP":
        base = "LONG"
        reasons.append("новость подталкивает цену вверх")
    elif target == "DOWN":
        base = "SHORT"
        reasons.append("новость давит на цену")
    else:
        base = "NO TRADE"
        reasons.append("влияния на тикер нет")
        return base, "; ".join(reasons)

    # RVI-корректировка
    if rvi_high and base == "LONG":
        reasons.append(f"RVI={rvi:.2f} > 40 — паника")
        base = "NO TRADE"
    elif rvi_rising and base == "LONG":
        reasons.append(f"RVI растёт на {rvi_change:.2f}%")
        base = "NO TRADE"
    elif rvi_low and base == "SHORT":
        reasons.append(f"RVI={rvi:.2f} < 20 — спокойствие")
        base = "NO TRADE"

    return base, "; ".join(reasons)


def analyze_news(item, rvi, rvi_change):
    """Обрабатывает одну новость."""
    t0 = time.time()
    c = classify_news(item["title"])
    elapsed = time.time() - t0

    # Собираем строку с сигналами по тикерам
    lines = [
        f"ВАЖНОСТЬ: {c['priority']}/5",
        f"ТОНАЛЬНОСТЬ: {c['ton']}",
        f"ТЕМА: {c['theme']}",
    ]

    for ticker, key in [("SBER", "sber"), ("GAZP", "gazp"), ("RUAL", "rual")]:
        signal, reason = decide_signal(c["ton"], c["theme"], c[key], rvi, rvi_change)
        if signal == "NO TRADE":
            lines.append(f"{ticker}: NO TRADE ({c[key]})")
        else:
            lines.append(f"{ticker}: {signal} — {reason}")

    lines.append(f"[{elapsed:.1f}s]")
    return "\n".join(lines)


if __name__ == "__main__":
    rvi, rvi_ch = get_current_rvi()
    if rvi is not None:
        print(f"Текущий RVI: {rvi:.2f} ({rvi_ch:+.2f}%)\n")
    else:
        print("RVI не найден\n")

    df = load_fresh_news(hours=NEWS_MAX_AGE_HOURS)
    print()

    if len(df) == 0:
        print("Свежих новостей нет")
        raise SystemExit

    # Сортируем по времени (свежие сначала)
    df = df.sort_values("timestamp", ascending=False).head(15)

    print(f"Анализирую {len(df)} свежих новостей (сначала свежие)\n")

    for _, row in df.iterrows():
        ts = row["timestamp"].strftime("%H:%M")
        title = str(row["title"])[:110]
        sent = row["sentiment"]

        print("=" * 70)
        print(f"[{ts}] {title}")
        print(f"RuBERT sentiment: {sent:+.3f}")
        print("-" * 70)
        print(analyze_news(row, rvi, rvi_ch))
        print()