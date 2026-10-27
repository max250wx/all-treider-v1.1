"""Сентимент для Telegram-новостей через RuBERT."""
import os
import pandas as pd
from transformers import pipeline

INPUT_FILE = "news_telegram.csv"
OUTPUT_FILE = "news_telegram_sentiment.csv"

def main():
    if not os.path.exists(INPUT_FILE):
        print(INPUT_FILE + " не найден")
        return
    df = pd.read_csv(INPUT_FILE)
    print("Загружено", len(df), "сообщений")
    df = df.drop_duplicates(subset=["text"]).reset_index(drop=True)
    print("После дедупликации:", len(df))
    clf = pipeline("sentiment-analysis", model="seara/rubert-base-cased-russian-sentiment", tokenizer="seara/rubert-base-cased-russian-sentiment")
    results = []
    for text in df["text"].astype(str):
        try:
            r = clf(text[:200])[0]
            sign = {"NEGATIVE": -1, "NEUTRAL": 0, "POSITIVE": 1}
            results.append(sign.get(r["label"].upper(), 0) * r["score"])
        except Exception:
            results.append(0.0)
    df["sentiment"] = results
    df.to_csv(OUTPUT_FILE, index=False)
    print("Сохранено →", OUTPUT_FILE)
    print("Средний сентимент:", round(df["sentiment"].mean(), 3))

if __name__ == "__main__":
    main()
