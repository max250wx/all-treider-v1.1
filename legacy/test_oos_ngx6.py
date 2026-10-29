"""Out-of-sample: Mean-Rev + Sessions на NGX6 и NGZ6."""

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
        if self.position:
            if self.position.is_long and self.data.Close[-1] >= self.ema[-1]:
                self.position.close()
            elif self.position.is_short and self.data.Close[-1] <= self.ema[-1]:
                self.position.close()
            return

        hour = self.data.index[-1].hour
        if not ((10 <= hour <= 11) or (14 <= hour <= 15)):
            return

        if pd.isna(self.atr[-1]) or pd.isna(self.ema[-1]):
            return

        price = self.data.Close[-1]
        ema_v = self.ema[-1]
        a = self.atr[-1]

        if price < ema_v - self.atr_entry * a:
            self.buy(size=self.size,
                     sl=price - self.atr_stop * a, tp=ema_v)
        elif price > ema_v + self.atr_entry * a:
            self.sell(size=self.size,
                      sl=price + self.atr_stop * a, tp=ema_v)


def run(data):
    bt = Backtest(data, MeanRevATRSessions, cash=1_000_000,
                  commission=0.0002, spread=0.0002, margin=0.1,
                  exclusive_orders=True, trade_on_close=False)
    return bt.run()


if __name__ == "__main__":
    for name, file in [
        ("NGX6 (NG-11.26) M5", "ngx6_m5.csv"),
        ("NGZ6 (NG-12.26) M5", "ngz6_m5.csv"),
    ]:
        print("")
        print("=" * 95)
        print("  OUT-OF-SAMPLE:  " + name)
        print("=" * 95)
        try:
            data = load_csv(file)
        except FileNotFoundError:
            print("  Файл " + file + " не найден — пропускаем")
            continue

        print("Баров: " + str(len(data)))
        print("Период: " + str(data.index[0]) + " — " + str(data.index[-1]))

        s = run(data)
        print("")
        print(pd.DataFrame([{
            "Trades": int(s["# Trades"]),
            "WinRate%": round(s["Win Rate [%]"], 2) if not pd.isna(s["Win Rate [%]"]) else 0,
            "PF": round(s["Profit Factor"], 3) if not pd.isna(s["Profit Factor"]) else 0,
            "Sharpe": round(s["Sharpe Ratio"], 2) if not pd.isna(s["Sharpe Ratio"]) else 0,
            "Return%": round(s["Return [%]"], 3),
            "MaxDD%": round(s["Max. Drawdown [%]"], 3),
        }]).to_string(index=False))