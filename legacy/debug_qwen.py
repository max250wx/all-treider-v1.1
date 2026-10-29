"""Смотрим, что РЕАЛЬНО возвращает Qwen 7B."""

import ollama

MODEL = "qwen2.5:7b"

prompt = (
    "Ты — аналитик российского фондового рынка.\n"
    "Верни РОВНО 2 строки, без объяснений.\n"
    "\n"
    "Формат:\n"
    "ТОНАЛЬНОСТЬ: POSITIVE | NEGATIVE | NEUTRAL\n"
    "ТЕМА: GEO | CB | OIL | CORP | OTHER\n"
    "\n"
    "ПРИМЕРЫ:\n"
    "«Сбербанк рекордная прибыль» → POSITIVE, CORP\n"
    "«США новые санкции против Газпрома» → NEGATIVE, GEO\n"
    "«Мошенники угрожают родителям» → NEUTRAL, OTHER"
)

test_news = [
    "Белгородский губернатор сообщил о 55 атаках на регион за сутки",
    "США ввели новые санкции против Газпрома",
    "Сбербанк объявил рекордную прибыль",
]

for title in test_news:
    print("=" * 70)
    print("НОВОСТЬ:", title)
    print("-" * 70)

    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Новость: " + title},
        ],
        options={"temperature": 0.0, "num_predict": 50},
    )

    text = response["message"]["content"]
    print("RAW ОТВЕТ МОДЕЛИ:")
    print(repr(text))  # repr покажет невидимые символы
    print()

    print("КАК ЕСТЬ:")
    print(text)
    print()

    # Эмулируем парсер
    ton = "NEUTRAL"
    theme = "OTHER"
    for line in text.upper().split("\n"):
        if "ТОНАЛЬНОСТЬ" in line:
            for v in ["POSITIVE", "NEGATIVE", "NEUTRAL"]:
                if v in line:
                    ton = v
                    break
        if "ТЕМА" in line:
            for v in ["GEO", "CB", "OIL", "CORP", "OTHER"]:
                if v in line:
                    theme = v
                    break

    print(f"ПАРСЕР РАСПОЗНАЛ: ton={ton}, theme={theme}")
    print()