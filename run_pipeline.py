"""Автоматический запуск REST-пайплайна."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

WORK_DIR = Path(__file__).resolve().parent
LOG_FILE = WORK_DIR / "pipeline_log.txt"
COLLECT_SECONDS = 3600  # 60 минут


def log(message):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_step(name, script, timeout=None):
    script_path = WORK_DIR / script
    log(f"-- {name} --")

    if not script_path.is_file():
        raise FileNotFoundError(f"Не найден скрипт: {script_path}")

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(WORK_DIR),
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Этап «{name}» превысил лимит {timeout} секунд"
        ) from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"Этап «{name}» завершился с кодом {result.returncode}"
        )

    log(f"OK: {name}")


def run_collector(seconds):
    script_path = WORK_DIR / "orderflow_rest.py"
    log(f"-- Сбор потока ордеров ({seconds} сек) --")

    if not script_path.is_file():
        raise FileNotFoundError(f"Не найден сборщик: {script_path}")

    proc = subprocess.Popen(
        [sys.executable, str(script_path)],
        cwd=str(WORK_DIR),
    )
    log(f"Сборщик запущен, PID={proc.pid}")

    try:
        proc.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        log("Время сбора истекло; останавливаем сборщик")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
        log("Сборщик остановлен по окончании времени сбора")
        return

    if proc.returncode != 0:
        raise RuntimeError(
            f"Сборщик завершился с кодом {proc.returncode}"
        )

    raise RuntimeError(
        "Сборщик завершился раньше заданного времени; "
        "проверьте журнал и данные"
    )


def main():
    with LOG_FILE.open("w", encoding="utf-8") as f:
        f.write(f"Pipeline started at {datetime.now()}\n")

    try:
        log("=" * 60)
        log("T-INVEST PIPELINE (REST)")
        log(f"Рабочая папка: {WORK_DIR}")

        run_step("Сбор новостей", "news_rss.py", timeout=120)
        run_step("Анализ сентимента", "sentiment_ru.py", timeout=600)
        run_collector(COLLECT_SECONDS)

        for filename in ("orderbook_raw_rest.csv", "trades_raw_rest.csv"):
            path = WORK_DIR / filename
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(
                    f"Нет входных данных или файл пуст: {filename}"
                )

        output = WORK_DIR / "combined_data.csv"
        old_mtime = output.stat().st_mtime_ns if output.exists() else None

        run_step("Объединение данных", "merge_pipeline.py", timeout=300)

        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError("combined_data.csv не создан или пуст")

        new_mtime = output.stat().st_mtime_ns
        if old_mtime is not None and new_mtime <= old_mtime:
            raise RuntimeError(
                "combined_data.csv не обновился; "
                "результат может быть устаревшим"
            )

        log("=" * 60)
        log("ПАЙПЛАЙН УСПЕШНО ЗАВЕРШЁН")
        log(f"Результат: {output}")

    except Exception as exc:
        log(f"ОШИБКА: {exc}")
        log("ПАЙПЛАЙН ЗАВЕРШИЛСЯ С ОШИБКОЙ")
        raise SystemExit(1) from None


def check_only():
    required_scripts = (
        "news_rss.py",
        "sentiment_ru.py",
        "orderflow_rest.py",
        "merge_pipeline.py",
    )
    missing = [
        name for name in required_scripts
        if not (WORK_DIR / name).is_file()
    ]

    required_inputs = ("news_sentiment.csv",)
    missing_inputs = [
        name for name in required_inputs
        if not (WORK_DIR / name).is_file()
    ]

    if missing or missing_inputs:
        if missing:
            print("Не найдены скрипты:", ", ".join(missing))
        if missing_inputs:
            print("Не найдены входные файлы:", ", ".join(missing_inputs))
        raise SystemExit(1)

    print("Проверка завершена. Сбор данных и объединение не запускались.")
    print("combined_data.csv не изменялся.")


if __name__ == "__main__":
    if "--check-only" in sys.argv[1:]:
        check_only()
    else:
        main()
