"""
Тестирование 3 стратегий на фьючерсах Brent (BRX6) и Gas (NGV6).
Стопы и тейки расширены под высокую волатильность сырья.
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


class RSIBase(Strategy):
    """RSI mean-reversion. Широкие стопы под сырьё."""
    rsi_period = 14
    rsi_buy = 30
    rsi_sell = 70
    stop_pct = 0.010       # 1.0%
    tp_pct = 0.015         # 1.5%
    size = 1

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


class RSIFiltered(Strategy):
    """RSI + фильтр тренда EMA(50)."""
    rsi_period = 14
    rsi_buy = 25
    rsi_sell = 75
    ema_period = 50
    stop_pct = 0.010
    tp_pct = 0.015
    size = 1

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
        self.ema = self.I(ema, self.data.Close, self.ema_period)

    def next(self):
        if self.position or pd.isna(self.rsi[-1]) or pd.isna(self.ema[-1]):
            return
        price = self.data.Close[-1]
        r = self.rsi[-1]
        ema_v = self.ema[-1]
        if r < self.rsi_buy and price > ema_v:
            self.buy(size=self.size,
                     sl=price * (1 - self.stop_pct),
                     tp=price * (1 + self.tp_pct))
        elif r > self.rsi_sell and price < ema_v:
            self.sell(size=self.size,
                      sl=price * (1 + self.stop_pct),
                      tp=price * (1 - self.tp_pct))


class EMACross(Strategy):
    """EMA 9/21 crossover — трендовая стратегия."""
    fast = 9
    slow = 21
    stop_pct = 0.010
    tp_pct = 0.015
    size = 1

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


if __name__ == "__main__":
    datasets = [
        ("BR (Brent)", "br_m1.csv"),
        ("NG (Gas)",   "ng_m1.csv"),
    ]
    strategies = [
        ("RSI base",         RSIBase),
        ("RSI + EMA filter", RSIFiltered),
        ("EMA Cross",        EMACross),
    ]

    for data_name, file in datasets:
        print(f"\n{'='*95}")
        print(f"  ИНСТРУМЕНТ: {data_name}  ({file})")
        print(f"{'='*95}")
        try:
            data = load_csv(file)
        except FileNotFoundError:
            print(f"  Файл {file} не найден — пропускаем")
            continue

        print(f"Баров: {len(data)}")
        print(f"Цена: {data['Close'].min():.3f} … {data['Close'].max():.3f}\n")

        results = []
        for name, cls in strategies:
            bt = Backtest(
                data, cls,
                cash=1_000_000,
                commission=0.0002,   # 0.02% — фьючерсная комиссия (тейкер)
                spread=0.0002,       # 0.02% — 1-2 шага цены на BR/NG
                margin=0.1,          # ГО ~10%
                exclusive_orders=True,
                trade_on_close=False,
            )
            stats = bt.run()

            results.append({
                "Strategy":   name,
                "Trades":     int(stats["# Trades"]),
                "WinRate%":   round(stats["Win Rate [%]"], 2) if not pd.isna(stats["Win Rate [%]"]) else 0,
                "Return%":    round(stats["Return [%]"], 3),
                "AvgTrade%":  round(stats["Avg. Trade [%]"], 4) if not pd.isna(stats["Avg. Trade [%]"]) else 0,
                "PF":         round(stats["Profit Factor"], 3) if stats["Profit Factor"] not in (np.inf,) and not pd.isna(stats["Profit Factor"]) else 0,
                "Sharpe":     round(stats["Sharpe Ratio"], 2) if stats["Sharpe Ratio"] not in (np.inf,) and not pd.isna(stats["Sharpe Ratio"]) else 0,
                "MaxDD%":     round(stats["Max. Drawdown [%]"], 3),
            })

        summary = pd.DataFrame(results)
        print(summary.to_string(index=False))