"""Автоматический запуск всего пайплайна (REST-версия)."""

import subprocess
import sys
import time
import signal
import os
from datetime import datetime


COLLECT_SECONDS = 3600        # 30 минут
WORK_DIR = r"C:\trading"
LOG_FILE = "pipeline_log.txt"


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_step(name, command, timeout=None):
    log(f"-- {name} --")
    try:
        result = subprocess.run(
            [sys.executable, command],
            cwd=WORK_DIR,
            timeout=timeout,
            check=False,
        )
        if result.returncode == 0:
            log(f"OK: {name}")
        else:
            log(f"WARN: {name} returncode={result.returncode}")
    except subprocess.TimeoutExpired:
        log(f"TIMEOUT: {name} (>{timeout}s)")
    except Exception as e:
        log(f"ERROR в {name}: {e}")


def run_collector(seconds):
    log(f"-- Сбор потока ордеров ({seconds} сек) --")
    proc = subprocess.Popen(
        [sys.executable, "orderflow_rest.py"],
        cwd=WORK_DIR,
    )
    log(f"Сборщик запущен, PID={proc.pid}")
    log(f"Ждём {seconds} секунд...")

    try:
        proc.wait(timeout=seconds)
        log("Сборщик завершился сам")
    except subprocess.TimeoutExpired:
        log("Останавливаем сборщик...")
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
            )
        else:
            proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log("Сборщик остановлен")


def main():
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"Pipeline started at {datetime.now()}\n")

    log("=" * 60)
    log("  T-INVEST PIPELINE (REST)")
    log("=" * 60)

    run_step("Сбор новостей", "news_rss.py", timeout=120)
    run_step("Анализ сентимента", "sentiment_ru.py", timeout=600)
    run_collector(COLLECT_SECONDS)
    run_step("Объединение данных", "merge_pipeline.py", timeout=300)

    log("=" * 60)
    log("  ГОТОВО")
    log("=" * 60)
    log(f"Результат: {os.path.join(WORK_DIR, 'combined_data.csv')}")


if __name__ == "__main__":
    main()
