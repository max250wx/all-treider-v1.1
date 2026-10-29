"""Единая точка входа."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()


def start(name, script, *args):
    path = ROOT / script
    if not path.exists():
        print(f"[run] пропуск {name}: нет {script}")
        return None
    print(f"[run] {name}: {script}")
    return subprocess.Popen([sys.executable, str(path), *args], cwd=ROOT)


def wait_all(procs):
    procs = [p for p in procs if p is not None]
    if not procs:
        return
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        print("\n[run] Ctrl+C — останавливаю...")
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


def cmd_collect():
    wait_all(
        [
            start("orderflow", "collectors/orderflow.py"),
            start("candles", "collectors/candles.py"),
            start("imoex", "collectors/imoex.py"),
            start("rvi", "collectors/rvi.py"),
        ]
    )


def cmd_live():
    wait_all(
        [
            start("orderflow", "collectors/orderflow.py"),
            start("candles", "collectors/candles.py"),
            start("imoex", "collectors/imoex.py"),
            start("rvi", "collectors/rvi.py"),
            start("scalper", "live/scalper.py"),
        ]
    )


def cmd_web():
    p = start("web", "web/backend/main.py")
    if p:
        p.wait()


def cmd_backtest():
    for s in ("backtest/walkforward_portfolio_imoex.py", "backtest/walkforward_rsi.py"):
        if (ROOT / s).exists():
            subprocess.run([sys.executable, str(ROOT / s)], cwd=ROOT)


def cmd_all():
    wait_all(
        [
            start("orderflow", "collectors/orderflow.py"),
            start("candles", "collectors/candles.py"),
            start("imoex", "collectors/imoex.py"),
            start("rvi", "collectors/rvi.py"),
            start("scalper", "live/scalper.py"),
            start("web", "web/backend/main.py"),
        ]
    )


COMMANDS = {
    "collect": cmd_collect,
    "live": cmd_live,
    "web": cmd_web,
    "backtest": cmd_backtest,
    "all": cmd_all,
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=COMMANDS.keys())
    a = ap.parse_args()
    COMMANDS[a.cmd]()
