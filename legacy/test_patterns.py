"""
EMA Cross + свечные паттерны на газе (NG) и Brent (BR).
Сравниваем: базовую EMA Cross и EMA Cross + фильтр по паттернам.

Паттерны (ручная реализация, без внешних библиотек):
  - Bullish Engulfing  (бычье поглощение)
  - Hammer             (молот)
  - Bearish Engulfing  (медвежье поглощение)
  - Shooting Star      (падающая звезда)
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy


def load_csv(path):
    df = pd.read_csv(path, parse_dates=True, index_col=0)
    df = df.rename(columns={
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume",
    })
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df = df[df["Volume"] > 0].sort_index()
    return df


# ─────────────────────────────────────────────
# ФУНКЦИИ ПАТТЕРНОВ (возвращают +1, -1 или 0)
# ─────────────────────────────────────────────

def bullish_engulfing(o, h, l, c):
    """Бычье поглощение: текущая бычья свеча полностью накрывает предыдущую медвежью."""
    o, c, po, pc = pd.Series(o), pd.Series(c), pd.Series(o).shift(1), pd.Series(c).shift(1)
    prev_bear = pc < po
    curr_bull = c > o
    engulf = (o <= pc) & (c >= po)
    return ((prev_bear & curr_bull & engulf).astype(int)).values


def bearish_engulfing(o, h, l, c):
    """Медвежье поглощение."""
    o, c, po, pc = pd.Series(o), pd.Series(c), pd.Series(o).shift(1), pd.Series(c).shift(1)
    prev_bull = pc > po
    curr_bear = c < o
    engulf = (o >= pc) & (c <= po)
    return ((prev_bull & curr_bear & engulf).astype(int)).values


def hammer(o, h, l, c):
    """Молот: маленькое тело сверху, длинная нижняя тень."""
    o, h, l, c = pd.Series(o), pd.Series(h), pd.Series(l), pd.Series(c)
    body = (c - o).abs()
    lower_wick = pd.concat([o, c], axis=1).min(axis=1) - l
    upper_wick = h - pd.concat([o, c], axis=1).max(axis=1)
    return ((lower_wick > 2 * body) & (upper_wick < body) & (body > 0)).astype(int).values


def shooting_star(o, h, l, c):
    """Падающая звезда: длинная верхняя тень, маленькое тело снизу."""
    o, h, l, c = pd.Series(o), pd.Series(h), pd.Series(l), pd.Series(c)
    body = (c - o).abs()
    upper_wick = h - pd.concat([o, c], axis=1).max(axis=1)
    lower_wick = pd.concat([o, c], axis=1).min(axis=1) - l
    return ((upper_wick > 2 * body) & (lower_wick < body) & (body > 0)).astype(int).values


# ─────────────────────────────────────────────
# СТРАТЕГИЯ 1: чистая EMA Cross (baseline)
# ─────────────────────────────────────────────

class EMACrossPure(Strategy):
    fast = 9
    slow = 21
    stop_pct = 0.010
    tp_pct = 0.015
    size = 50

    def init(self):
        def ema(s, p):
            return pd.Series(s).ewm(span=p, adjust=False).mean()
        self.fast = self.I(ema, self.data.Close, self.fast)
        self.slow = self.I(ema, self.data.Close, self.slow)

    def next(self):
        if self.position or len(self.fast) < 2:
            return
        price = self.data.Close[-1]
        if self.fast[-2] <= self.slow[-2] and self.fast[-1] > self.slow[-1]:
            self.buy(size=self.size,
                     sl=price * (1 - self.stop_pct),
                     tp=price * (1 + self.tp_pct))
        elif self.fast[-2] >= self.slow[-2] and self.fast[-1] < self.slow[-1]:
            self.sell(size=self.size,
                      sl=price * (1 + self.stop_pct),
                      tp=price * (1 - self.tp_pct))


# ─────────────────────────────────────────────
# СТРАТЕГИЯ 2: EMA Cross + подтверждение свечным паттерном
# ─────────────────────────────────────────────

class EMACrossWithPatterns(Strategy):
    fast = 9
    slow = 21
    stop_pct = 0.010
    tp_pct = 0.015
    size = 50

    def init(self):
        def ema(s, p):
            return pd.Series(s).ewm(span=p, adjust=False).mean()
        self.fast = self.I(ema, self.data.Close, self.fast)
        self.slow = self.I(ema, self.data.Close, self.slow)

        self.bull_engulf = self.I(bullish_engulfing,
                                  self.data.Open, self.data.High,
                                  self.data.Low, self.data.Close)
        self.bear_engulf = self.I(bearish_engulfing,
                                  self.data.Open, self.data.High,
                                  self.data.Low, self.data.Close)
        self.hammer = self.I(hammer,
                             self.data.Open, self.data.High,
                             self.data.Low, self.data.Close)
        self.shooting = self.I(shooting_star,
                               self.data.Open, self.data.High,
                               self.data.Low, self.data.Close)

    def next(self):
        if self.position or len(self.fast) < 2:
            return
        price = self.data.Close[-1]

        cross_long = (self.fast[-2] <= self.slow[-2] and self.fast[-1] > self.slow[-1])
        cross_short = (self.fast[-2] >= self.slow[-2] and self.fast[-1] < self.slow[-1])

        bullish_pattern = (self.bull_engulf[-1] > 0 or self.hammer[-1] > 0)
        bearish_pattern = (self.bear_engulf[-1] > 0 or self.shooting[-1] > 0)

        # Лонг: пересечение EMA + подтверждение бычьим паттерном
        if cross_long and bullish_pattern:
            self.buy(size=self.size,
                     sl=price * (1 - self.stop_pct),
                     tp=price * (1 + self.tp_pct))
        # Шорт: пересечение EMA + подтверждение медвежьим паттерном
        elif cross_short and bearish_pattern:
            self.sell(size=self.size,
                      sl=price * (1 + self.stop_pct),
                      tp=price * (1 - self.tp_pct))


# ─────────────────────────────────────────────
# ЗАПУСК
# ─────────────────────────────────────────────

def pretty(stats):
    return {
        "Trades":   int(stats["# Trades"]),
        "WinRate%": round(stats["Win Rate [%]"], 2) if not pd.isna(stats["Win Rate [%]"]) else 0,
        "Return%":  round(stats["Return [%]"], 3),
        "AvgTrade%": round(stats["Avg. Trade [%]"], 4) if not pd.isna(stats["Avg. Trade [%]"]) else 0,
        "PF":       round(stats["Profit Factor"], 3) if not pd.isna(stats["Profit Factor"]) else 0,
        "Sharpe":   round(stats["Sharpe Ratio"], 2) if not pd.isna(stats["Sharpe Ratio"]) else 0,
        "MaxDD%":   round(stats["Max. Drawdown [%]"], 3),
    }


if __name__ == "__main__":
    files = [
        ("NG (Gas)", "ng_m1.csv"),
        ("BR (Brent)", "br_m1.csv"),
    ]
    strategies = [
        ("EMA pure",       EMACrossPure),
        ("EMA + patterns", EMACrossWithPatterns),
    ]

    for data_name, file in files:
        print("")
        print("=" * 95)
        print("  " + data_name + "  (" + file + ")")
        print("=" * 95)
        try:
            data = load_csv(file)
        except FileNotFoundError:
            print("  Файл " + file + " не найден — пропускаем")
            continue

        print("Баров: " + str(len(data)))
        print("Цена: " + str(round(data["Close"].min(), 3)) + " … " + str(round(data["Close"].max(), 3)))
        print("")

        results = []
        for name, cls in strategies:
            bt = Backtest(
                data, cls,
                cash=1_000_000,
                commission=0.0002,
                spread=0.0002,
                margin=0.1,
                exclusive_orders=True,
                trade_on_close=False,
            )
            stats = bt.run()
            row = {"Strategy": name}
            row.update(pretty(stats))
            results.append(row)

        print(pd.DataFrame(results).to_string(index=False))