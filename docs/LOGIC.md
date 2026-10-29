AI-трейдер MOEX - Логика работы
Версия 1.0 - Октябрь 2026

ЛОГИКА РАБОТЫ AI-ТРЕЙДЕРА MOEX
Версия 1.0 • Октябрь 2026
1. ОБЩАЯ АРХИТЕКТУРА
Система состоит из 4 слоёв:
СЛОЙ 1: СБОР ДАННЫХ (orderflow_rest, rvi_collector, news_rss, sentiment_ru)
СЛОЙ 2: ОБРАБОТКА (merge_pipeline, analyze_signals)
СЛОЙ 3: AI-АНАЛИЗ (ai_agent_local на Qwen 2.5)
СЛОЙ 4: УПРАВЛЕНИЕ (watchdog, keep_awake, selfdiag)
2. СЛОЙ 1: СБОР ДАННЫХ
2.1. Стакан и сделки — orderflow_rest.py
Источник: T-Invest API (боевой read-only токен)
Метод: REST-поллинг каждые 5 секунд
Что собирается:
Стакан (10 уровней) → orderbook_{TICKER}.csv
Сделки за 60 сек → trades_{TICKER}.csv
Тикеры: GAZP, RUAL
Дедупликация: Set из кортежей (timestamp, price, qty, direction)
Формат orderbook:
timestamp,ticker,figi,bid1_price,bid1_qty,...,ask5_price,ask5_qty
Формат trades:
timestamp,figi,price,quantity,direction
direction: 1 = покупка, 2 = продажа
2.2. Индекс страха RVI — rvi_collector.py
Источник: MOEX ISS API
Метод: REST-запрос каждые 60 секунд
Формат rvi_data.csv:
timestamp,rvi_current,rvi_last,change_pct,updated_at
Значения RVI (пункты):
< 20   → Спокойствие, лонг-сигналы сильнее
20-40  → Нейтрально
40-60  → Паника, шорт-сигналы сильнее
> 60   → Экстремальная паника, возможен отскок
2.3. Новости — news_rss.py
Источники RSS:
РБК: https://rssexport.rbc.ru/rbcnews/news/30/full.rss
Интерфакс: https://www.interfax.ru/rss.asp
Ведомости: https://www.vedomosti.ru/rss/news
Метод: запрос каждые 60 минут
Формат: timestamp,title,source
2.4. Сентимент — sentiment_ru.py
Модель: RuBERT seara/rubert-base-cased-russian-sentiment
Метод: классификация [-1, +1]
Дополнительно: keyword-override (санкции, атаки → -0.8; рекорд, рост → +0.8)
Формат: timestamp,title,source,sentiment
3. СЛОЙ 2: ОБРАБОТКА
3.1. Объединение — merge_pipeline.py
Задача: собрать единый датафрейм из трёх источников
Метод: pd.merge_asof по временной метке
Шаги:
1. Загрузка orderbook, trades, news_sentiment
2. Признаки стакана:
mid_price = (bid1 + ask1) / 2
spread = ask1 - bid1
spread_pct = spread / mid_price * 100
book_imbalance = (сумма bid_qty - сумма ask_qty) / (сумма bid_qty + сумма ask_qty)
microprice = (bid1*ask1_qty + ask1*bid1_qty) / (bid1_qty + ask1_qty)
3. Поток сделок за 60 секунд:
buy_volume, sell_volume, trade_count, vwap
trade_imbalance = (buy_vol - sell_vol) / (buy_vol + sell_vol)
4. Привязка последней новости (окно 15 мин):
news_sentiment, news_title, news_age_min
Результат: combined_data.csv (38 колонок)
3.2. Анализ сигналов — analyze_signals.py
Считает корреляцию book_imbalance и trade_imbalance с будущей доходностью на горизонтах 1, 3, 6, 12, 24 бара.
Интерпретация:
|r| < 0.05   → нет связи
|r| 0.05-0.15 → слабая
|r| > 0.15   → значимая
Найденные закономерности:
Вечерняя сессия SBER: r = +0.22 на 1 баре
Утренняя сессия SBER: r = +0.21 на 24 барах
4. СЛОЙ 3: AI-АНАЛИЗ
4.1. AI-агент — ai_agent_local.py
Модель: Qwen 2.5 7B (или 14B, 32B) через Ollama
Вход:
5 последних негативных новостей
3 последних позитивных
Текущий RVI
Приоритет факторов:
1. [GEO] Геополитика (санкции, военные действия, БПЛА, переговоры)
2. [CB] ЦБ РФ (ставка, риторика)
3. [OIL] Цены на нефть/газ
4. [CORP] Корпоративные новости
5. [OTHER] Прочее
Правила:
LONG — если новость позитивна ИЛИ RVI < 20 ИЛИ RVI падает >3%
SHORT — если новость негативна ИЛИ санкции ИЛИ эскалация ИЛИ RVI > 40
NO TRADE — только криминал, спорт, культура или противоречивые новости
Формат ответа:
СИГНАЛ: LONG | SHORT | NO TRADE
ПРИОРИТЕТ: [GEO/CB/OIL/CORP/OTHER]
ОБОСНОВАНИЕ: 2-3 предложения
4.2. Учёт RVI
RVI подаётся в промпт в пунктах (не процентах).
5. СЛОЙ 4: УПРАВЛЕНИЕ
5.1. Watchdog — watchdog.py
Каждые 60 секунд проверяет mtime файлов.
Если файл не менялся > 5 минут — перезапускает процесс.
Раз в час запускает news_rss.py и sentiment_ru.py.
Пишет всё в watchdog.log.
5.2. Keep Awake — keep_awake.py
Не даёт Windows уйти в сон через Win API SetThreadExecutionState.
Флаги: ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED.
5.3. Самодиагностика — selfdiag.py
Проверяет за 10 секунд:
1. Python-пакеты (8 модулей)
2. GPU (nvidia-smi, VRAM)
3. Ollama (список моделей)
4. API (T-Invest, MOEX ISS)
5. Файлы (наличие, размеры, свежесть)
6. Ресурсы (RAM, диск)
7. Процессы Python
6. ПРАВИЛА БЕЗОПАСНОСТИ
AI-агент НЕ имеет права:
Отправлять ордера
Менять размер позиции
Отменять стоп-лосс
Снимать лимит убытка
Увеличивать риск после убытка
Правильный поток: AI → Risk Manager → Execution → T-Invest API
Ограничения:
Риск на сделку ≤ 1% капитала
Максимум позиций: 3
Дневной лимит убытка: 1.5%
Максимальная просадка: 10%
7. ФОРМАТЫ ФАЙЛОВ
orderbook_GAZP.csv  ~720 строк/час
trades_GAZP.csv     ~2700 строк/час
orderbook_RUAL.csv  ~720 строк/час
trades_RUAL.csv     ~600 строк/час
rvi_data.csv        ~60 строк/час
news_rss.csv        ~20 строк/час
news_sentiment.csv  ~20 строк/час
8. ТОЧКИ ОТКАЗА
T-Invest разорвал соединение → watchdog перезапустит
Ollama не отвечает → перезапустить
GPU оффлоадит на CPU → уменьшить модель
Токен просрочен → перевыпустить
Модель галлюцинирует → ужесточить промпт
RVI устарел (>30 мин) → запустить вручную
9. КЛЮЧЕВЫЕ РЕШЕНИЯ
1. REST вместо стрима (стрим рвётся каждые 15-30 мин)
2. Дедупликация сделок через Set
3. Промпт только на русском (Qwen склонна к иероглифам)
4. RVI в пунктах, не в процентах
5. Watchdog + keep_awake = автономность 24/7
6. Sandbox-токен для тестов
10. STOP-LOSS И TAKE-PROFIT
10.1. Принципы
1. SL всегда установлен до входа
2. SL двигается только в сторону прибыли
3. TP может быть частичным (50% на TP1, остаток трейлится)
4. SL и TP выставляются брокером через sl= и tp=
5. Размер позиции рассчитывается от SL
10.2. Формулы
SL_distance = Entry_price * stop_pct
SL_price = Entry - SL_distance (для LONG)
SL_price = Entry + SL_distance (для SHORT)
TP_distance = Entry_price * tp_pct
TP_price = Entry + TP_distance (для LONG)
TP_price = Entry - TP_distance (для SHORT)
R:R = TP_distance / SL_distance
RiskAmount = AccountEquity * risk_per_trade
PositionSize = RiskAmount / SL_distance
10.3. Процентные стопы (скальпинг)
stop_pct: 0.10-0.30%
tp_pct: 0.20-0.50%
max_hold_bars: 6-24
Пример GAZP (125 руб):
Entry: 125.50, SL: 125.37 (0.10%), TP: 125.75 (0.20%)
R:R = 1.92
10.4. ATR-стопы (адаптивные)
SL_price = Entry - ATR * atr_stop_multiplier (LONG)
TP_price = Entry + ATR * atr_tp_multiplier (LONG)
Параметры:
atr_stop_multiplier: 1.5-3.0
atr_tp_multiplier: 2.0-4.5
atr_period: 14
Результаты тестов:
2.0 → PF 1.18 (42 сделки)
2.5 → PF 1.21 (38) — лучший
3.0 → PF 1.15 (35)
10.5. Trailing Stop
Логика:
1. TP1 (1:1) → закрываем 50%, SL в безубыток
2. Трейлинг для остатка (шаг = 2*ATR или 0.1%)
3. Стоп только вверх для LONG, только вниз для SHORT
Код:
if not self.partial_closed and high >= self.tp1_price:
    half = abs(self.position.size) // 2
    if half > 0:
        self.sell(size=half)
    self.partial_closed = True
    self.stop_price = self.entry_price
    return
if self.partial_closed:
    new_stop = price - self.trailing_step * 0.01
    if new_stop > self.stop_price:
        self.stop_price = new_stop
10.6. Параметры для разных стратегий
Скальпинг (5 сек)      : stop 0.10%, tp 0.20%
Mean-Rev M5            : stop 0.40%, tp 0.60%
Mean-Rev M15           : stop 0.30%, tp 0.50%
EMA Cross M5           : ATR x 2.0 / ATR x 3.0
MTF (H4+H1)            : stop 0.40%, tp 0.80%
Order Flow             : stop 0.10%, tp 0.25%
10.7. Расчёт размера позиции
Пример с GAZP:
Капитал: 100 000 руб
Риск на сделку: 1% = 1000 руб
Вход: 125.50
SL: 125.20 (расстояние 0.30 руб)
Размер: 1000 / 0.30 = 3333 акции
Маржа при плече 1:5: 83 653 руб
10.8. Типичные ошибки
Стоп без ордера → убыток растёт
Движение стопа против позиции → убыток растёт
Отмена стопа при отскоке → потеря депозита
TP < SL (R:R < 1) → убыточная стратегия
Один SL на все стратегии → не работает
Слишком узкий стоп (0.05%) → выбивает шумом
Слишком широкий стоп (2%) → риск > 5% депозита
10.9. Правило «сначала стоп, потом вход»
1. Определить Entry: 125.50
2. Определить SL: 125.20 (0.30 руб)
3. RiskAmount: 1% от депозита = 1000 руб
4. Size: 1000 / 0.30 = 3333 акции
5. Отправить ордер с sl=125.20 и tp=125.80
10.10. Стоп для разных инструментов
SBER    : spread 0.007%, stop 0.10-0.20%, tp 0.20-0.40%
GAZP    : spread 0.02%,  stop 0.15-0.30%, tp 0.30-0.60%
RUAL    : spread 0.05%,  stop 0.30-0.50%, tp 0.60-1.00%
RVI фьюч: spread 0.10%,  stop 0.50-1.00%, tp 1.00-2.00%
Правило: SL минимум в 5 раз больше спреда
10.11. Проверка SL/TP в бэктесте
SL > 60% выходов → стоп слишком узкий
TP > 70% выходов → тейк слишком близкий
Выход по времени > 50% → стратегия не работает
Просадка > 15% при риске 1% → стоп слишком широкий
10.12. Шпаргалка формул
sl_price = entry * (1 - stop_pct)        # LONG
tp_price = entry * (1 + tp_pct)          # LONG
sl_price = entry * (1 + stop_pct)        # SHORT
tp_price = entry * (1 - tp_pct)          # SHORT
sl_price = entry - atr * atr_stop_mult   # LONG (ATR)
tp_price = entry + atr * atr_tp_mult     # LONG (ATR)
risk_amount = equity * risk_per_trade
position_size = risk_amount / abs(entry - sl_price)
new_stop = price - trailing_step         # LONG
new_stop = price + trailing_step         # SHORT
____________________________________________________________
Автор: AI-трейдер MOEX
Дата: 14 октября 2026
Версия: 1.0
КОНЕЦ ДОКУМЕНТА