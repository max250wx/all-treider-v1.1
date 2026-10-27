"""
Mean-Reversion с ATR + фильтр по времени сессии.
Торгуем только в боковые часы МСК: 10-12 и 14-16.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy


def load_csv(path):
    df = pd.read_csv(path, parse_dates=True, index_col=0)
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                             "close": "Close", "volume": "Volume"})
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    return df[df["Volume"] > 0].sort_index()


def atr(h, l, c, p):
    h, l, c = pd.Series(h), pd.Series(l), pd.Series(c)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / p, adjust=False).mean()


class MeanRevATRSessions(Strategy):
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

    def next(self):
        # Выход по возврату к EMA
        if self.position:
            if self.position.is_long and self.data.Close[-1] >= self.ema[-1]:
                self.position.close()
            elif self.position.is_short and self.data.Close[-1] <= self.ema[-1]:
                self.position.close()
            return

        # Фильтр по времени сессии
        hour = self.data.index[-1].hour
        in_good_hours = (10 <= hour <= 11) or (14 <= hour <= 15)
        if not in_good_hours:
            return

        if pd.isna(self.atr[-1]) or pd.isna(self.ema[-1]):
            return

        price = self.data.Close[-1]
        ema_v = self.ema[-1]
        a = self.atr[-1]

        if price < ema_v - self.atr_entry * a:
            self.buy(size=self.size,
                     sl=price - self.atr_stop * a,
                     tp=ema_v)
        elif price > ema_v + self.atr_entry * a:
            self.sell(size=self.size,
                      sl=price + self.atr_stop * a,
                      tp=ema_v)


def run(data):
    bt = Backtest(data, MeanRevATRSessions, cash=1_000_000,
                  commission=0.0002, spread=0.0002, margin=0.1,
                  exclusive_orders=True, trade_on_close=False)
    return bt.run()


def walk_forward(data, n_windows=6):
    total = len(data)
    block_size = total // (n_windows + 1)
    out = []
    for k in range(n_windows):
        test_end = block_size * (k + 2)
        test = data.iloc[block_size * (k + 1):test_end]
        if len(test) < 300:
            break
        s = run(test)
        out.append({
            "Окно": k + 1,
            "Test": str(test.index[0].date()) + "…" + str(test.index[-1].date()),
            "Trades": int(s["# Trades"]),
            "PF": round(s["Profit Factor"], 3) if not pd.isna(s["Profit Factor"]) else 0,
            "Sharpe": round(s["Sharpe Ratio"], 2) if not pd.isna(s["Sharpe Ratio"]) else 0,
            "Return%": round(s["Return [%]"], 3),
            "MaxDD%": round(s["Max. Drawdown [%]"], 3),
        })
    return pd.DataFrame(out)


if __name__ == "__main__":
    for name, file in [
        ("NGU6 M5", "ngu6_m5.csv"),
        ("NGV6 M5", "ng_m5.csv"),
        ("BR M5",   "br_m5.csv"),
    ]:
        print("")
        print("=" * 95)
        print("  MeanRev + Sessions:  " + name + "  (" + file + ")")
        print("=" * 95)
        try:
            data = load_csv(file)
        except FileNotFoundError:
            continue

        print("Баров: " + str(len(data)))

        s_full = run(data)
        print("")
        print("── Полный период ──")
        print(pd.DataFrame([{
            "Trades": int(s_full["# Trades"]),
            "WinRate%": round(s_full["Win Rate [%]"], 2) if not pd.isna(s_full["Win Rate [%]"]) else 0,
            "PF": round(s_full["Profit Factor"], 3) if not pd.isna(s_full["Profit Factor"]) else 0,
            "Sharpe": round(s_full["Sharpe Ratio"], 2) if not pd.isna(s_full["Sharpe Ratio"]) else 0,
            "Return%": round(s_full["Return [%]"], 3),
            "MaxDD%": round(s_full["Max. Drawdown [%]"], 3),
        }]).to_string(index=False))

        res = walk_forward(data, n_windows=6)
        print("")
        print("── Walk-forward ──")
        print(res.to_string(index=False))
        if not res.empty:
            wins = (res["PF"] > 1.0).sum()
            print("")
            print("Окон с PF > 1.0: " + str(wins) + " из " + str(len(res)))
            print("Средний PF: " + str(round(res["PF"].mean(), 3)))
            print("Средний Sharpe: " + str(round(res["Sharpe"].mean(), 3)))