# T-Invest Research Project

[![CI](https://github.com/max250wx/all-treider-v1.1/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/max250wx/all-treider-v1.1/actions/workflows/ci.yml)

Исследовательский проект по созданию торговой стратегии с использованием
технических индикаторов, новостного сентимента и потока ордеров.
Telegram-бот и локальный ИИ (Ollama).

## 📋 Что уже сделано

### 1. Инфраструктура бэктестинга
- Python: `backtesting.py` + `pandas` + `numpy`
- Комиссии, спреды, SL/TP-ордера, walk-forward — настроены корректно
- Готовые скрипты: от простой RSI до MTF-стратегий

### 2. Данные
- **SBER M1**: 35 676 баров (сентябрь–октябрь 2026)
- **Brent (BRX6) M1**: 32 878 баров
- **Газ (NGU6, NGV6, NGX6, NGZ6) M1**: 30 000+ баров каждый
- **IMOEXF M1**: 35 115 баров
- Агрегация M1 → M5, M15, H1, H4, D1

### 3. Тестированные стратегии

| Стратегия | Лучший результат | Вердикт |
|---|---|---|
| RSI mean-reversion M1/M5 | PF ~1.0 | Нет устойчивого edge |
| EMA Cross M1/M5 | PF 1.43 (NGV6) | Не подтверждён на OOS |
| EMA + свечные паттерны | PF 1.59 (NGV6) | Walk-forward развалил |
| ATR Breakout | PF 0.51 | Провал |
| MTF D1+H4+H1 (strict) | PF 1.21 | Только 2/5 окон |
| **MTF 2of3** | **PF 1.21** | **5/5 окон** ✓ |
| **Mean-Rev + Sessions M15 NO FILTER** | **PF 1.40** | Слабый OOS: NGX6 1.08, NGZ6 0.81 |

### 🏆 Лучший результат (M1, IMOEXF)

| Стратегия | Trades | WinRate% | Return% | PF | Sharpe | MaxDD% |
|-----------|--------|----------|---------|----|--------|--------|
| **RSI 15/85 + session + volatility** | 16 | 31.25 | +0.059 | **2.043** | **3.00** | −0.052 |

**Вывод:** `RSI 15/85` (экстремальный RSI) + `session` (10–18) + `volatility` (ATR > median) — **прибыльная** на M1 IMOEXF. **PF 2.043** (2 рубля прибыли на 1 рубль убытка), **Sharpe 3.00** (отличный риск-профиль).

> ⚠️ **16 сделок** — **мало** для статистики (2 недели данных). **Нужно** **1–2 года** (см. «Ограничения»).

### 4. Новостной пайплайн
- Сбор новостей MOEX ISS (`news_collector.py`)
- Сбор RSS: РБК, Интерфакс, Ведомости (`news_rss.py`)
- Анализ сентимента RuBERT + keyword-override (`sentiment_ru.py`)
- `news_sentiment.csv` — 255 новостей с оценками

### 5. Поток ордеров
- Сборщик стакана + сделок через T-Invest API (`orderflow_collector.py`)
- Объединитель трёх источников в единый датафрейм (`merge_pipeline.py`)

---

## 🚀 Quickstart

### 1. Клонирование и установка

```bash
git clone https://github.com/max250wx/all-treider-v1.1.git
cd all-treider-v1.1

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt