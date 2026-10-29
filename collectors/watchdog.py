"""Watchdog v3: следит за сборщиками. Перезапускает при падении или
отсутствии активности файлов. Не блокирует цикл scheduled.
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

DATA_DIR = ROOT / CFG["paths"]["data_live"]
LOG_FILE = ROOT / "logs" / "watchdog.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

STALL_MIN = CFG["watchdog"]["stall_minutes"]
CHECK_SEC = CFG["watchdog"]["check_interval_sec"]
RESTART_LIMIT = CFG["watchdog"]["restart_limit"]
RESTART_WINDOW = CFG["watchdog"]["restart_window_sec"]

TARGETS = [
    {
        "name": "orderflow",
        "script": "collectors/orderflow.py",
        "files": [DATA_DIR / f"orderbook_{t}.csv" for t in CFG["collectors"]["tickers"]],
    },
    {
        "name": "rvi",
        "script": "collectors/rvi.py",
        "files": [DATA_DIR / "rvi_data.csv"],
    },
]


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def last_activity(files):
    mtimes = [os.path.getmtime(f) for f in files if f.exists()]
    return max(mtimes) if mtimes else 0


def launch(script):
    try:
        return subprocess.Popen(
            [sys.executable, str(ROOT / script)],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
        )
    except Exception as e:
        log(f"  ОШИБКА запуска {script}: {e}")
        return None


def kill(proc):
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        pass


def main():
    log("=" * 70)
    log("WATCHDOG v3 стартовал")
    log("=" * 70)

    processes = {t["name"]: launch(t["script"]) for t in TARGETS}
    time.sleep(3)

    last_mtime = {t["name"]: last_activity(t["files"]) for t in TARGETS}
    last_seen = {t["name"]: time.time() for t in TARGETS}
    restarts = {t["name"]: [] for t in TARGETS}

    try:
        while True:
            time.sleep(CHECK_SEC)
            now = time.time()
            for t in TARGETS:
                name = t["name"]
                mtime = last_activity(t["files"])

                if mtime > last_mtime[name]:
                    last_mtime[name] = mtime
                    last_seen[name] = now

                proc = processes.get(name)
                alive = proc is not None and proc.poll() is None
                stall_min = (now - last_seen[name]) / 60

                reason = None
                if not alive:
                    reason = "процесс упал"
                elif stall_min >= STALL_MIN:
                    reason = f"нет данных {stall_min:.1f} мин"

                if reason:
                    restarts[name] = [ts for ts in restarts[name] if now - ts < RESTART_WINDOW]
                    if len(restarts[name]) >= RESTART_LIMIT:
                        log(
                            f"[!!] {name}: {RESTART_LIMIT} рестартов за "
                            f"{RESTART_WINDOW // 60} мин — пауза"
                        )
                        last_seen[name] = now
                        continue
                    log(f"[!] {name}: {reason} — перезапуск")
                    kill(proc)
                    processes[name] = launch(t["script"])
                    last_seen[name] = now
                    restarts[name].append(now)
                else:
                    log(f"[OK] {name}: активен {stall_min:.1f} мин назад")

    except KeyboardInterrupt:
        log("Watchdog остановлен")
        for proc in processes.values():
            kill(proc)


if __name__ == "__main__":
    main()
