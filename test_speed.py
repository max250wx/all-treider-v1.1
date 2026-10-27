"""Тест скорости локальной модели RusMind."""

import ollama
import time

MODEL = "hf.co/DICPlay/RusMind-3.5.1-Momentum:latest"

print(f"Загружаем модель {MODEL}...")
t0 = time.time()

response = ollama.chat(
    model=MODEL,
    messages=[
        {"role": "system", "content": "Ты трейдер. Отвечай кратко."},
        {"role": "user", "content": "Сбербанк объявил рекордную прибыль. Сигнал LONG/SHORT/NO TRADE?"},
    ],
)

elapsed = time.time() - t0

eval_count = response.get("eval_count", 0)
eval_duration = response.get("eval_duration", 0) / 1e9
prompt_count = response.get("prompt_eval_count", 0)
prompt_duration = response.get("prompt_eval_duration", 0) / 1e9

print()
print("=" * 70)
print("ОТВЕТ МОДЕЛИ:")
print("=" * 70)
print(response["message"]["content"])
print()
print("=" * 70)
print("СТАТИСТИКА:")
print("=" * 70)
print(f"  Общее время:           {elapsed:.2f} сек")
print(f"  Сгенерировано токенов: {eval_count}")
print(f"  Время генерации:       {eval_duration:.2f} сек")
if eval_duration > 0:
    speed = eval_count / eval_duration
    print(f"  Скорость генерации:    {speed:.1f} токенов/сек")
    print()
    if speed > 50:
        print("[OK] GPU работает отлично")
    elif speed > 20:
        print("[WARN] GPU медленно (возможно, оффлоад на CPU)")
    else:
        print("[FAIL] Работает на CPU — надо настроить GPU")