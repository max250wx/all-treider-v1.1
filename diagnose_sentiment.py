"""Диагностика: что возвращает RuBERT для трёх тестовых фраз."""

from transformers import pipeline

print("Загружаем модель...")
clf = pipeline(
    "sentiment-analysis",
    model="seara/rubert-base-cased-russian-sentiment",
    tokenizer="seara/rubert-base-cased-russian-sentiment",
)

print("\nID2LABEL модели:")
print(clf.model.config.id2label)
print("\nLABEL2ID модели:")
print(clf.model.config.label2id)

test_texts = [
    "Болгария запросила помощь ЕС и НАТО после атаки на суда в Черном море",
    "Сбербанк подал иск о признании банкротом ПАО Евротранс",
    "Трамп заявил, что Путин и Зеленский поддерживают идею энергетического перемирия",
    "Мосбиржа зафиксировала рекордный объем торгов в выходные",
    "Компания X показала рекордную прибыль и рост выручки",
]

print("\nРезультаты:")
for t in test_texts:
    r = clf(t[:200])[0]
    print(f"\nТекст: {t[:80]}...")
    print(f"  label={r['label']}, score={r['score']:.4f}")