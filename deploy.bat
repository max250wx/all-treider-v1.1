@echo off
chcp 65001 >nul
echo ============================================
echo   Развёртывание AI-трейдера MOEX
echo ============================================
echo.

echo [1/4] Установка Python-пакетов...
python -m pip install -r requirements.txt
if errorlevel 1 goto error

echo.
echo [2/4] Проверка Ollama...
where ollama >nul 2>&1
if errorlevel 1 (
    echo   Ollama не найден!
    echo   Скачайте: https://ollama.com/download
    pause
    exit /b 1
)
echo   Ollama найден

echo.
echo [3/4] Скачивание AI-модели...
ollama pull qwen2.5:7b

echo.
echo [4/4] Проверка окружения...
python selfdiag.py

echo.
echo ============================================
echo   ГОТОВО
echo ============================================
echo.
echo Запуск (откройте 3 окна PowerShell):
echo   Окно 1: python keep_awake.py
echo   Окно 2: python watchdog.py
echo   Окно 3: python ai_agent_local.py
echo.
pause
exit /b 0

:error
echo.
echo ОШИБКА при установке. Смотрите вывод выше.
pause
exit /b 1