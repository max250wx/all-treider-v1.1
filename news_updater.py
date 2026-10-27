"""
Автономное обновление новостей.
Каждые NEWS_INTERVAL_MIN минут:
  1. Собирает свежие новости из RSS
  2. Прогоняет через RuBERT-сентимент
  3. Логирует результат

Работает бесконечно, Ctrl+C для остановки.
"""

import os
import time
import subprocess
import sys
from datetime import datetime


WORK_DIR = r"C:\trading"
LOG_FILE = os.path.join(WORK_DIR, "news_updater.log")
os.chdir(WORK_DIR)

NEWS_INTERVAL_MIN = 5    # как часто обновлять (минут)


def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def count_lines(path):
    if not os.path.exists(path):
        return 0
    try:
        with open(path, encoding="utf-8") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def run_script(script, timeout=600):
    """Запускает дочерний скрипт, ждёт завершения."""
    log(f"  → {script}")
    try:
        result = subprocess.run(
            [sys.executable, script],
            cwd=WORK_DIR,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            log(f"  ← {script} OK")
            return True
        else:
            log(f"  ← {script} код {result.returncode}")
            if result.stderr:
                for line in result.stderr.strip().split("\n")[:5]:
                    log(f"     STDERR: {line}")
            return False
    except subprocess.TimeoutExpired:
        log(f"  ⏱ {script} — timeout {timeout}s")
        return False
    except Exception as e:
        log(f"  ОШИБКА {script}: {e}")
        return False


def update_news():
    """Собирает RSS + Telegram + сентимент."""
    log("Начинаю обновление новостей...")

    # 1. RSS
    log("  [RSS]")
    run_script("news_rss.py", timeout=180)
    run_script("sentiment_ru.py", timeout=900)

    # 2. Telegram
    log("  [Telegram]")
    ok_tg = run_script("tg_parser_web.py", timeout=180)
    if ok_tg:
        run_script("sentiment_telegram.py", timeout=600)

    # Итоги
    after_rss = count_lines("news_rss.csv")
    after_sent = count_lines("news_sentiment.csv")
    after_tg = count_lines("news_telegram.csv")
    after_tg_sent = count_lines("news_telegram_sentiment.csv")

    log(f"  RSS:              {after_rss}")
    log(f"  RSS sentiment:    {after_sent}")
    log(f"  Telegram:         {after_tg}")
    log(f"  TG sentiment:     {after_tg_sent}")
    log("Обновление завершено")


def main():
    log("=" * 60)
    log("NEWS UPDATER стартовал")
    log(f"Интервал обновления: {NEWS_INTERVAL_MIN} мин")
    log("=" * 60)

    # Первичный запуск сразу
    update_news()

    while True:
        try:
            log(f"Следующее обновление через {NEWS_INTERVAL_MIN} мин...")
            time.sleep(NEWS_INTERVAL_MIN * 60)
            update_news()
        except KeyboardInterrupt:
            log("Остановлен пользователем")
            break
        except Exception as e:
            log(f"ОШИБКА в цикле: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()