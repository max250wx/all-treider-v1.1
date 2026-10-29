"""
Анализ тональности русских новостей: RuBERT + keyword-override.
RuBERT даёт общую оценку, keyword-правила усиливают сигнал на явных новостях.
"""

import pandas as pd
from transformers import pipeline

# ─────────────────────────────────────────────
# Ключевые слова для override
# ─────────────────────────────────────────────

STRONG_NEGATIVE = [
    "санкц",
    "атак",
    "удар",
    "войн",
    "конфликт",
    "банкрот",
    "иск о",
    "штраф",
    "запрет",
    "ограничен",
    "обвал",
    "кризис",
    "катастроф",
    "убийств",
    "теракт",
    "разрушен",
    "потер",
    "угроз",
    "обвинен",
    "провал",
    "шок",
    "сорвал",
    "претензии",
    "авари",
]
STRONG_POSITIVE = [
    "рекорд",
    "прибыл",
    "рост ",
    "вырос",
    "соглашен",
    "перемир",
    "сотрудничеств",
    "подписа",
    "успех",
    "прорыв",
    "восстановлен",
    "поддержк",
    "укреплен",
    "позитив",
    "договор",
    "мирн",
]


def keyword_override(text):
    """Возвращает число, если текст явно негативный/позитивный, иначе None."""
    t = str(text).lower()
    neg = sum(1 for w in STRONG_NEGATIVE if w in t)
    pos = sum(1 for w in STRONG_POSITIVE if w in t)

    if neg > pos:
        return -0.8
    if pos > neg:
        return 0.8
    return None  # нейтрально, решает модель


def score_to_number(label, score):
    """Преобразует метку RuBERT в число от -1 до +1."""
    sign = {
        "NEGATIVE": -1,
        "NEUTRAL": 0,
        "POSITIVE": 1,
        "negative": -1,
        "neutral": 0,
        "positive": 1,
    }
    return sign.get(label, 0) * score


# ─────────────────────────────────────────────
# Запуск
# ─────────────────────────────────────────────

if __name__ == "__main__":
    try:
        df = pd.read_csv("news_rss.csv")
        print("Загружено " + str(len(df)) + " новостей из news_rss.csv")
    except FileNotFoundError:
        print("Сначала запустите news_rss.py")
        raise SystemExit from None

    print("Загружаем модель RuBERT...")
    clf = pipeline(
        "sentiment-analysis",
        model="seara/rubert-base-cased-russian-sentiment",
        tokenizer="seara/rubert-base-cased-russian-sentiment",
    )

    print("Анализ (RuBERT + keyword-override)...")
    results = []
    for title in df["title"].astype(str):
        # Сначала проверяем keywords
        override = keyword_override(title)
        if override is not None:
            results.append(override)
            continue

        # Иначе — модель
        try:
            r = clf(title[:200])[0]
            results.append(score_to_number(r["label"], r["score"]))
        except Exception:
            results.append(0.0)

    df["sentiment"] = results
    df.to_csv("news_sentiment.csv", index=False)

    print("")
    print("Готово. Статистика:")
    print("  Средний сентимент: " + str(round(df["sentiment"].mean(), 3)))
    print("  Позитивных:        " + str((df["sentiment"] > 0.1).sum()))
    print("  Негативных:        " + str((df["sentiment"] < -0.1).sum()))
    print("  Нейтральных:       " + str((df["sentiment"].abs() <= 0.1).sum()))
    print("")
    print("── ТОП-10 негативных ──")
    print(df.nsmallest(10, "sentiment")[["timestamp", "title", "sentiment"]].to_string(index=False))
    print("")
    print("── ТОП-10 позитивных ──")
    print(df.nlargest(10, "sentiment")[["timestamp", "title", "sentiment"]].to_string(index=False))
    print("")
    print("Сохранено в news_sentiment.csv")
