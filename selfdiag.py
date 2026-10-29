"""
Самодиагностика системы.
Проверяет:
  - Окружение (Python, пакеты)
  - GPU (nvidia-smi, Ollama)
  - API (T-Invest, MOEX ISS)
  - Файлы (наличие, свежесть, размеры)
  - Ресурсы (RAM, диск)
"""

import os
import sys
import subprocess
import shutil
from datetime import datetime, timezone
import time

WORK_DIR = r"C:\trading"
os.chdir(WORK_DIR)


def ok(msg):
    print(f"  [OK]   {msg}")


def warn(msg):
    print(f"  [WARN] {msg}")


def fail(msg):
    print(f"  [FAIL] {msg}")


def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


# ─────────────────────────────────────────────
# 1. Python и пакеты
# ─────────────────────────────────────────────
def check_python():
    section("1. PYTHON И ПАКЕТЫ")
    print(f"  Python: {sys.version.split()[0]}")
    print(f"  Путь:   {sys.executable}")

    packages = {
        "pandas": "pandas",
        "numpy": "numpy",
        "requests": "requests",
        "t_tech": "t-tech-investments",
        "ollama": "ollama",
        "transformers": "transformers",
        "torch": "torch",
        "aiogram": "aiogram",
    }
    for mod, pip_name in packages.items():
        try:
            __import__(mod)
            ok(f"{mod:15s} ({pip_name})")
        except ImportError:
            warn(f"{mod:15s} не установлен → pip install {pip_name}")


# ─────────────────────────────────────────────
# 2. GPU и Ollama
# ─────────────────────────────────────────────
def check_gpu():
    section("2. GPU И OLLAMA")

    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            out = subprocess.run(
                [nvidia_smi, "--query-gpu=name,memory.total,memory.used",
                 "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10,
            )
            print(f"  nvidia-smi: {out.stdout.strip()}")
            ok("GPU доступен")
        except Exception as e:
            warn(f"nvidia-smi error: {e}")
    else:
        warn("nvidia-smi не найден в PATH (возможно, GPU недоступен)")

    # Ollama
    ollama_path = shutil.which("ollama")
    if not ollama_path:
        default = r"C:\Users\Max\AppData\Local\Programs\Ollama\ollama.exe"
        if os.path.exists(default):
            ollama_path = default
    if ollama_path:
        try:
            out = subprocess.run([ollama_path, "list"],
                                 capture_output=True, text=True, timeout=10)
            lines = out.stdout.strip().split("\n")
            ok(f"Ollama: {len(lines) - 1} моделей")
            for line in lines[1:]:
                print(f"    {line}")
        except Exception as e:
            warn(f"Ollama error: {e}")
    else:
        warn("Ollama не найден")


# ─────────────────────────────────────────────
# 3. API
# ─────────────────────────────────────────────
def check_apis():
    section("3. API (T-Invest, MOEX ISS)")

    # T-Invest
    try:
        from t_tech.invest import Client
        TOKEN = os.getenv("T_INVEST_TOKEN", "").strip()
        with Client(TOKEN) as client:
            from datetime import timedelta
            now = datetime.now(timezone.utc)
            trades = client.market_data.get_last_trades(
                figi="BBG004730RP0",  # GAZP
                from_=now - timedelta(minutes=5),
                to=now,
            )
            ok(f"T-Invest API: получено {len(trades.trades)} сделок GAZP за 5 мин")
    except Exception as e:
        fail(f"T-Invest API: {e}")

    # MOEX ISS
    try:
        import requests
        r = requests.get(
            "https://iss.moex.com/iss/engines/stock/markets/index/securities.json",
            params={"iss.meta": "off", "iss.only": "marketdata", "securities": "RVI"},
            timeout=10,
        )
        r.raise_for_status()
        ok("MOEX ISS: доступен")
    except Exception as e:
        fail(f"MOEX ISS: {e}")


# ─────────────────────────────────────────────
# 4. Файлы данных
# ─────────────────────────────────────────────
def check_files():
    section("4. ФАЙЛЫ ДАННЫХ")

    files = [
        ("orderbook_GAZP.csv", "стакан GAZP"),
        ("trades_GAZP.csv", "сделки GAZP"),
        ("orderbook_RUAL.csv", "стакан RUAL"),
        ("trades_RUAL.csv", "сделки RUAL"),
        ("rvi_data.csv", "RVI"),
        ("news_rss.csv", "новости RSS"),
        ("news_sentiment.csv", "сентимент"),
    ]

    now = time.time()
    for name, desc in files:
        path = os.path.join(WORK_DIR, name)
        if not os.path.exists(path):
            fail(f"{name:25s} ({desc}) — не найден")
            continue
        size = os.path.getsize(path)
        if size == 0:
            warn(f"{name:25s} ({desc}) — пустой")
            continue
        with open(path) as f:
            lines = sum(1 for _ in f)
        mtime = os.path.getmtime(path)
        age_min = (now - mtime) / 60

        status = "OK"
        if age_min > 30:
            status = "WARN (устарел)"
        print(f"  [{status:15s}] {name:25s} {lines:>8} строк, {age_min:6.1f} мин назад")

    # Логи
    log_files = ["watchdog.log", "pipeline_log.txt"]
    for name in log_files:
        path = os.path.join(WORK_DIR, name)
        if os.path.exists(path):
            size_kb = os.path.getsize(path) / 1024
            print(f"  [LOG] {name:25s} {size_kb:.1f} KB")


# ─────────────────────────────────────────────
# 5. Ресурсы
# ─────────────────────────────────────────────
def check_resources():
    section("5. РЕСУРСЫ (RAM, диск)")

    try:
        r = subprocess.run(
            ["powershell", "-Command",
             "Get-CimInstance Win32_OperatingSystem | "
             "Select-Object @{N='Total';E={[math]::Round($_.TotalVisibleMemorySize/1MB,2)}},"
             "@{N='Free';E={[math]::Round($_.FreePhysicalMemory/1MB,2)}} | "
             "ConvertTo-Csv -NoTypeInformation"],
            capture_output=True, text=True, timeout=10,
        )
        print(r.stdout.strip())
    except Exception as e:
        warn(f"RAM info: {e}")

    try:
        total, used, free = shutil.disk_usage("C:\\")
        print(f"  Диск C: free={free // (2**30)} GB / total={total // (2**30)} GB")
    except Exception as e:
        warn(f"Disk info: {e}")


# ─────────────────────────────────────────────
# 6. Процессы Python
# ─────────────────────────────────────────────
def check_processes():
    section("6. АКТИВНЫЕ ПРОЦЕССЫ PYTHON")

    try:
        r = subprocess.run(
            ["powershell", "-Command",
             "Get-Process python -ErrorAction SilentlyContinue | "
             "Select-Object Id, CPU, WS | ConvertTo-Csv -NoTypeInformation"],
            capture_output=True, text=True, timeout=10,
        )
        out = r.stdout.strip()
        if out and len(out.split("\n")) > 1:
            print(out)
            ok(f"Процессов python: {len(out.split(chr(10))) - 1}")
        else:
            warn("Активных процессов python нет")
    except Exception as e:
        warn(f"process check: {e}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print(f"  САМОДИАГНОСТИКА  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    check_python()
    check_gpu()
    check_apis()
    check_files()
    check_resources()
    check_processes()

    print()
    print("=" * 70)
    print("  ДИАГНОСТИКА ЗАВЕРШЕНА")
    print("=" * 70)
