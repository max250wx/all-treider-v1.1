"""
Тест ATR Breakout vs EMA Cross на BR и NG.
Breakout: пробой хая/лоу за N баров + ATR-стоп.
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


def atr_calc(h, l, c, p):
    h, l, c = pd.Series(h), pd.Series(l), pd.Series(c)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / p, adjust=False).mean()


class ATRBreakout(Strategy):
    lookback = 20
    atr_period = 14
    atr_mult_stop = 2.0
    atr_mult_tp = 3.0
    size = 50

    def init(self):
        self.high_n = self.I(
            lambda s, lb: pd.Series(s).rolling(lb).max(),
            self.data.High, self.lookback,
        )
        self.low_n = self.I(
            lambda s, lb: pd.Series(s).rolling(lb).min(),
            self.data.Low, self.lookback,
        )
        self.atr = self.I(
            atr_calc,
            self.data.High, self.data.Low, self.data.Close, self.atr_period,
        )

    def next(self):
        if self.position or pd.isna(self.atr[-1]):
            return
        price = self.data.Close[-1]
        a = self.atr[-1]
        if price > self.high_n[-2]:
            self.buy(size=self.size,
                     sl=price - a * self.atr_mult_stop,
                     tp=price + a * self.atr_mult_tp)
        elif price < self.low_n[-2]:
            self.sell(size=self.size,
                      sl=price + a * self.atr_mult_stop,
                      tp=price - a * self.atr_mult_tp)


class EMACross(Strategy):
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


def pretty(stats):
    return {
        "Trades":    int(stats["# Trades"]),
        "WinRate%":  round(stats["Win Rate [%]"], 2) if not pd.isna(stats["Win Rate [%]"]) else 0,
        "Return%":   round(stats["Return [%]"], 3),
        "AvgTrade%": round(stats["Avg. Trade [%]"], 4) if not pd.isna(stats["Avg. Trade [%]"]) else 0,
        "PF":        round(stats["Profit Factor"], 3) if not pd.isna(stats["Profit Factor"]) else 0,
        "Sharpe":    round(stats["Sharpe Ratio"], 2) if not pd.isna(stats["Sharpe Ratio"]) else 0,
        "MaxDD%":    round(stats["Max. Drawdown [%]"], 3),
    }


if __name__ == "__main__":
    files = [
        ("NG (Gas)", "ng_m1.csv"),
        ("BR (Brent)", "br_m1.csv"),
    ]
    strategies = [
        ("ATR Breakout", ATRBreakout),
        ("EMA Cross",    EMACross),
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