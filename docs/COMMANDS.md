# Команды управления проектом

## 🚀 Установка (первый раз)

```powershell
# 1. Клонирование
git clone https://github.com/max250wx/all-treider-v1.1.git
cd all-treider-v1.1

# 2. Виртуальное окружение
python -m venv .venv
.venv\Scripts\activate   # Windows

# 3. Зависимости
pip install -r requirements.txt

# 4. Конфиг (секреты)
Copy-Item .env.example .env
notepad .env   # вписать T_INVEST_TOKEN, TELEGRAM_BOT_TOKEN

# Запуск всех тестов
pytest -q

# Один тест
pytest tests/test_config.py -q

# С покрытием
pytest --cov=. --cov-report=html# Проверка (как в CI)
ruff check config.py bot.py tests/
ruff format --check config.py bot.py tests/

# Авто-фикс
ruff check --fix .
ruff format .

# Запуск с конфигом по умолчанию (M1, IMOEXF)
python scalping_framework.py

# Выбор таймфрейма (M1/M5/M10/M15/H1)
python scalping_framework.py --timeframe M5
python scalping_framework.py --timeframe M10

# Выбор инструмента (GAZP/SBER/...)
python scalping_framework.py --instrument GAZP

# Другой конфиг
python scalping_framework.py --config my_config.yaml

# Mean-reversion ATR (M5)
python mean_reversion_atr.py

# Mean-reversion ATR + sessions
python mean_reversion_atr_sessions.py

# Scalping (4 стратегии, IMOEXF)
python scalping.py

# Walk-forward портфель (LKOH + VTBR + ROSN)
python backtest\walkforward_portfolio.py

# Walk-forward портфель с IMOEX-фильтром
python backtest\walkforward_portfolio_imoex.py

# Запуск бота (aiogram 3)
python bot.py

# Остановка: Ctrl+C

# Сбор новостей MOEX ISS
python news_collector.py

# Сбор RSS (РБК, Интерфакс, Ведомости)
python news_rss.py

# Анализ сентимента (RuBERT)
python sentiment_ru.py

# Сбор из Telegram
python tg_parser_web.py
python sentiment_telegram.py

# Обновление новостей (периодически)
python news_updater.py

# Сбор стакана + сделок (T-Invest API)
python orderflow_collector.py

# REST-сборщик (GAZP + RUAL)
python orderflow_rest.py

# Объединение трёх источников
python merge_pipeline.py

# Пайплайн (все этапы)
python run_pipeline.py

# Статус
git status

# История
git log --oneline -10

# Добавить и закоммитить
git add <file>
git commit -m "тип: описание"

# Push
git push origin fix/critical-security-data-pipeline

# Ветки
git branch
git checkout -b new-branch 

# Удалить __pycache__
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

# Удалить .pytest_cache
Remove-Item .pytest_cache -Recurse -Force -ErrorAction SilentlyContinue

# Удалить .ruff_cache
Remove-Item .ruff_cache -Recurse -Force -ErrorAction SilentlyContinue

# Какие данные есть
Get-ChildItem data\history\*.csv | Select-Object Name, @{N='Size_MB';E={[math]::Round($_.Length/1MB,2)}}

# Проверить конкретный файл
Test-Path data\history\imoexf_m1.csv

# Проверить импорт
python -c "import config; print('OK')"

# Проверить YAML
python -c "import yaml; cfg = yaml.safe_load(open('scalping_config.yaml', encoding='utf-8')); print('OK:', len(cfg['strategies']), 'strategies')"

# Проверить токены
Select-String -Path .env -Pattern "TELEGRAM_BOT_TOKEN" | ForEach-Object { $_.Line -replace ':[A-Za-z0-9_-]+$', ':***' }

https://github.com/max250wx/all-treider-v1.1/actions