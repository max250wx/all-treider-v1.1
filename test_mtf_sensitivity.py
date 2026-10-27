"""
MTF стратегия: D1 направление, H4+H1 подтверждение, M15 вход.
+ Тест чувствительности параметров atr_entry × atr_stop.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy


def load_mtf(path):
    df = pd.read_csv(path, parse_dates=True, index_col=0)
    df = df.rename(columns={
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume",
    })
    return df


def atr(h, l, c, p):
    h, l, c = pd.Series(h), pd.Series(l), pd.Series(c)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / p, adjust=False).mean()


class MTFMeanRev(Strategy):
    ema_period = 20
    atr_period = 14
    atr_entry = 2.5
    atr_stop = 1.5
    size = 500

    def init(self):
        def ema(s, p):
            return pd.Series(s).ewm(span=p, adjust=False).mean()

        self.ema = self.I(ema, self.data.Close, self.ema_period)
        self.atr = self.I(atr, self.data.High, self.data.Low,
                          self.data.Close, self.atr_period)
        self.d1_trend = self.data.D1Trend
        self.h4_trend = self.data.H4Trend
        self.h1_trend = self.data.H1Trend

    def next(self):
        # Выход: возврат к EMA
        if self.position:
            if self.position.is_long and self.data.Close[-1] >= self.ema[-1]:
                self.position.close()
            elif self.position.is_short and self.data.Close[-1] <= self.ema[-1]:
                self.position.close()
            return

        # Фильтр по времени сессии
        hour = self.data.index[-1].hour
        if not ((10 <= hour <= 11) or (14 <= hour <= 15)):
            return

        # HTF фильтр
        d1 = self.d1_trend[-1]
        h4 = self.h4_trend[-1]
        h1 = self.h1_trend[-1]
        allow_long = (d1 == 1 and h4 == 1 and h1 == 1)
        allow_short = (d1 == 0 and h4 == 0 and h1 == 0)
        if not (allow_long or allow_short):
            return

        if pd.isna(self.atr[-1]) or pd.isna(self.ema[-1]):
            return

        price = self.data.Close[-1]
        ema_v = self.ema[-1]
        a = self.atr[-1]

        if allow_long and price < ema_v - self.atr_entry * a:
            self.buy(size=self.size,
                     sl=price - self.atr_stop * a, tp=ema_v)
        elif allow_short and price > ema_v + self.atr_entry * a:
            self.sell(size=self.size,
                      sl=price + self.atr_stop * a, tp=ema_v)


def run_once(data, atr_entry, atr_stop):
    bt = Backtest(data, MTFMeanRev, cash=1_000_000,
                  commission=0.0002, spread=0.0002, margin=0.1,
                  exclusive_orders=True, trade_on_close=False)
    return bt.run(atr_entry=atr_entry, atr_stop=atr_stop)


def sensitivity(data, entries, stops):
    rows = []
    for e in entries:
        for s in stops:
            stats = run_once(data, e, s)
            rows.append({
                "atr_entry": e,
                "atr_stop": s,
                "Trades": int(stats["# Trades"]),
                "WinRate%": round(stats["Win Rate [%]"], 2) if not pd.isna(stats["Win Rate [%]"]) else 0,
                "PF": round(stats["Profit Factor"], 3) if not pd.isna(stats["Profit Factor"]) else 0,
                "Sharpe": round(stats["Sharpe Ratio"], 2) if not pd.isna(stats["Sharpe Ratio"]) else 0,
                "Return%": round(stats["Return [%]"], 3),
                "MaxDD%": round(stats["Max. Drawdown [%]"], 3),
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    entries = [1.5, 2.0, 2.5, 3.0]
    stops = [1.0, 1.5, 2.0]

    for name, file in [
        ("NGU6", "ngu6_mtf.csv"),
        ("NGV6", "ngv6_mtf.csv"),
        ("SBER", "sber_mtf.csv"),
    ]:
        print("")
        print("=" * 100)
        print("  MTF STRATEGY:  " + name + "  (" + file + ")")
        print("=" * 100)
        try:
            data = load_mtf(file)
        except FileNotFoundError:
            print("  Файл не найден — пропускаем")
            continue

        print("Баров: " + str(len(data)))
        print("Период: " + str(data.index[0]) + " — " + str(data.index[-1]))
        print("")

        # Baseline
        print("── Baseline (atr_entry=2.5, atr_stop=1.5) ──")
        s = run_once(data, 2.5, 1.5)
        print(pd.DataFrame([{
            "Trades": int(s["# Trades"]),
            "WinRate%": round(s["Win Rate [%]"], 2) if not pd.isna(s["Win Rate [%]"]) else 0,
            "PF": round(s["Profit Factor"], 3) if not pd.isna(s["Profit Factor"]) else 0,
            "Sharpe": round(s["Sharpe Ratio"], 2) if not pd.isna(s["Sharpe Ratio"]) else 0,
            "Return%": round(s["Return [%]"], 3),
            "MaxDD%": round(s["Max. Drawdown [%]"], 3),
        }]).to_string(index=False))
        print("")

        # Sensitivity grid
        print("── Sensitivity grid ──")
        grid = sensitivity(data, entries, stops)
        print(grid.to_string(index=False))
        print("")

        # Оценка
        good = (grid["PF"] > 1.1).sum()
        print("Ячеек с PF > 1.1: " + str(good) + " из " + str(len(grid)))
        print("Медиана PF: " + str(round(grid["PF"].median(), 3)))