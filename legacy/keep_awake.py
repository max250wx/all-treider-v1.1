"""
Предотвращает переход Windows в спящий режим, пока скрипт запущен.
Для остановки нажмите Ctrl+C.
"""
import ctypes
import sys
import time
from datetime import datetime

# Константы из Windows API
ES_CONTINUOUS       = 0x80000000
ES_SYSTEM_REQUIRED  = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

def prevent_sleep():
    """Включает блокировку сна."""
    # Предотвращает и сон системы, и выключение дисплея
    ctypes.windll.kernel32.SetThreadExecutionState(
        ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
    )
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Блокировка сна ВКЛЮЧЕНА. Нажмите Ctrl+C для остановки.")

def allow_sleep():
    """Возвращает систему в обычный режим."""
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Блокировка сна ВЫКЛЮЧЕНА.")

if __name__ == "__main__":
    prevent_sleep()
    try:
        while True:
            # Просто ждём, скрипт работает в фоне
            time.sleep(60)
    except KeyboardInterrupt:
        allow_sleep()