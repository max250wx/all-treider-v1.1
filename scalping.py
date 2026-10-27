"""
Сравнение 4 стратегий на IMOEXF (вечный фьючерс Индекса МосБиржи).
Реальные издержки фьючерса: комиссия 0.0066%, спред 0.005%.
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
# 1. RSI MEAN-REVERSION
# ─────────────────────────────────────────────
class RSIReversion(Strategy):
    rsi_period = 14
    rsi_buy = 30
    rsi_sell = 70
    stop_pct = 0.004
    tp_pct = 0.006
    size = 10

    def init(self):
        def rsi(s, p):
            s = pd.Series(s)
            d = s.diff()
            gain = d.where(d > 0, 0.0)
            loss = -d.where(d < 0, 0.0)
            ag = gain.ewm(alpha=1 / p, adjust=False).mean()
            al = loss.ewm(alpha=1 / p, adjust=False).mean()
            rs = ag / al.replace(0, np.nan)
            return 100 - 100 / (1 + rs)
        self.rsi = self.I(rsi, self.data.Close, self.rsi_period)

    def next(self):
        if self.position or pd.isna(self.rsi[-1]):
            return
        price = self.data.Close[-1]
        r = self.rsi[-1]
        if r < self.rsi_buy:
            self.buy(size=self.size,
                     sl=price * (1 - self.stop_pct),
                     tp=price * (1 + self.tp_pct))
        elif r > self.rsi_sell:
            self.sell(size=self.size,
                      sl=price * (1 + self.stop_pct),
                      tp=price * (1 - self.tp_pct))


# ─────────────────────────────────────────────
# 2. RSI + ФИЛЬТРЫ (тренд + время)
# ─────────────────────────────────────────────
class RSIReversionFiltered(Strategy):
    rsi_period = 14
    rsi_buy = 25
    rsi_sell = 75
    ema_trend = 50
    stop_pct = 0.004
    tp_pct = 0.006
    size = 10

    def init(self):
        def rsi(s, p):
            s = pd.Series(s)
            d = s.diff()
            gain = d.where(d > 0, 0.0)
            loss = -d.where(d < 0, 0.0)
            ag = gain.ewm(alpha=1 / p, adjust=False).mean()
            al = loss.ewm(alpha=1 / p, adjust=False).mean()
            rs = ag / al.replace(0, np.nan)
            return 100 - 100 / (1 + rs)
        def ema(s, p):
            return pd.Series(s).ewm(span=p, adjust=False).mean()

        self.rsi = self.I(rsi, self.data.Close, self.rsi_period)
        self.ema = self.I(ema, self.data.Close, self.ema_trend)

    def next(self):
        if self.position or pd.isna(self.rsi[-1]) or pd.isna(self.ema[-1]):
            return

        price = self.data.Close[-1]
        r = self.rsi[-1]
        ema_v = self.ema[-1]

        uptrend = price > ema_v
        downtrend = price < ema_v

        # Фильтр по времени: только активные часы сессии МСК
        now = self.data.index[-1]
        hour = now.hour if hasattr(now, "hour") else 0
        if not (10 <= hour <= 18):
            return

        if r < self.rsi_buy and uptrend:
            self.buy(size=self.size,
                     sl=price * (1 - self.stop_pct),
                     tp=price * (1 + self.tp_pct))
        elif r > self.rsi_sell and downtrend:
            self.sell(size=self.size,
                      sl=price * (1 + self.stop_pct),
                      tp=price * (1 - self.tp_pct))


# ─────────────────────────────────────────────
# 3. EMA CROSSOVER
# ─────────────────────────────────────────────
class EMACross(Strategy):
    fast = 9
    slow = 21
    stop_pct = 0.004
    tp_pct = 0.006
    size = 10

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
# 4. EMA CROSS + фильтр по объёму
# ─────────────────────────────────────────────
class EMACrossFiltered(Strategy):
    fast = 9
    slow = 21
    vol_period = 20
    stop_pct = 0.004
    tp_pct = 0.006
    size = 10

    def init(self):
        def ema(s, p):
            return pd.Series(s).ewm(span=p, adjust=False).mean()
        self.fast = self.I(ema, self.data.Close, self.fast)
        self.slow = self.I(ema, self.data.Close, self.slow)
        self.vol_ma = self.I(
            lambda s, p: pd.Series(s).rolling(p).mean(),
            self.data.Volume, self.vol_period,
        )

    def next(self):
        if self.position or len(self.fast) < 2 or pd.isna(self.vol_ma[-1]):
            return

        # Фильтр объёма: только если текущий объём выше среднего
        if self.data.Volume[-1] < self.vol_ma[-1]:
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
# ЗАПУСК
# ─────────────────────────────────────────────

if __name__ == "__main__":
    data = load_csv("imoexf_m1.csv")
    print(f"Баров: {len(data)}")
    print(f"Период: {data.index[0]} — {data.index[-1]}")
    print(f"Цена: {data['Close'].min():.2f} … {data['Close'].max():.2f}\n")

    strategies = [
        ("RSI Reversion (raw)",       RSIReversion),
        ("RSI Reversion (filtered)",  RSIReversionFiltered),
        ("EMA Cross (raw)",           EMACross),
        ("EMA Cross (filtered)",      EMACrossFiltered),
    ]

    results = []
    for name, cls in strategies:
        bt = Backtest(
            data, cls,
            cash=1_000_000,
            commission=0.000066,   # 0.0066% — реальная комиссия фьючерса MOEX (тейкер)
            spread=0.00005,        # 0.005% — 1 пункт на цене 2200
            margin=0.1,            # ГО фьючерса ≈ 10%
            exclusive_orders=True,
            trade_on_close=False,
        )
        stats = bt.run()

        results.append({
            "Strategy": name,
            "Trades": int(stats["# Trades"]),
            "WinRate%": round(stats["Win Rate [%]"], 2),
            "Return%": round(stats["Return [%]"], 3),
            "AvgTrade%": round(stats["Avg. Trade [%]"], 4),
            "PF": round(stats["Profit Factor"], 3) if stats["Profit Factor"] != np.inf else np.inf,
            "Sharpe": round(stats["Sharpe Ratio"], 2) if stats["Sharpe Ratio"] != np.inf else np.inf,
            "MaxDD%": round(stats["Max. Drawdown [%]"], 3),
        })

    summary = pd.DataFrame(results)
    print("=" * 95)
    print("  СРАВНЕНИЕ 4 СТРАТЕГИЙ НА IMOEXF (комиссия 0.0066%, спред 0.005%)")
    print("=" * 95)
    print(summary.to_string(index=False))
    print("=" * 95)