"""
Out-of-sample: mean-reversion + sessions (NO FILTER) на NGX6 и NGZ6 M15.
Критическая проверка: подтверждается ли edge на других контрактах.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy


def m1_to_m15(in_csv):
    df = pd.read_csv(in_csv, parse_dates=True, index_col=0)
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                             "close": "Close", "volume": "Volume"})
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df = df[df["Volume"] > 0].sort_index()
    df_m15 = df.resample("15min").agg({
        "Open": "first", "High": "max", "Low": "min",
        "Close": "last", "Volume": "sum",
    }).dropna()
    return df_m15[df_m15["Volume"] > 0]


def atr(h, l, c, p):
    h, l, c = pd.Series(h), pd.Series(l), pd.Series(c)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / p, adjust=False).mean()


class MeanRevNoFilter(Strategy):
    ema_period = 20
    atr_period = 14
    atr_entry = 2.0
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
            self.buy(size=self.size, sl=price - self.atr_stop * a, tp=ema_v)
        elif price > ema_v + self.atr_entry * a:
            self.sell(size=self.size, sl=price + self.atr_stop * a, tp=ema_v)


def run(data):
    bt = Backtest(data, MeanRevNoFilter, cash=1_000_000,
                  commission=0.0002, spread=0.0002, margin=0.1,
                  exclusive_orders=True, trade_on_close=False)
    return bt.run()


def walk_forward(data, n_windows=5):
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
            "WinRate%": round(s["Win Rate [%]"], 2) if not pd.isna(s["Win Rate [%]"]) else 0,
            "PF": round(s["Profit Factor"], 3) if not pd.isna(s["Profit Factor"]) else 0,
            "Sharpe": round(s["Sharpe Ratio"], 2) if not pd.isna(s["Sharpe Ratio"]) else 0,
            "Return%": round(s["Return [%]"], 3),
        })
    return pd.DataFrame(out)


if __name__ == "__main__":
    for name, file in [
        ("NGX6 (NG-11.26)", "ngx6_m1.csv"),
        ("NGZ6 (NG-12.26)", "ngz6_m1.csv"),
    ]:
        print("")
        print("=" * 95)
        print("  OUT-OF-SAMPLE: " + name + " M15")
        print("=" * 95)
        try:
            data = m1_to_m15(file)
        except FileNotFoundError:
            print("  Файл " + file + " не найден — пропускаем")
            continue

        print("Баров M15: " + str(len(data)))
        print("Период: " + str(data.index[0]) + " — " + str(data.index[-1]))
        print("")

        # Полный период
        s_full = run(data)
        print("── Полный период ──")
        print(pd.DataFrame([{
            "Trades": int(s_full["# Trades"]),
            "WinRate%": round(s_full["Win Rate [%]"], 2) if not pd.isna(s_full["Win Rate [%]"]) else 0,
            "PF": round(s_full["Profit Factor"], 3) if not pd.isna(s_full["Profit Factor"]) else 0,
            "Sharpe": round(s_full["Sharpe Ratio"], 2) if not pd.isna(s_full["Sharpe Ratio"]) else 0,
            "Return%": round(s_full["Return [%]"], 3),
            "MaxDD%": round(s_full["Max. Drawdown [%]"], 3),
        }]).to_string(index=False))
        print("")

        # Walk-forward
        res = walk_forward(data, n_windows=4)
        print("── Walk-forward ──")
        print(res.to_string(index=False))
        if not res.empty:
            wins = (res["PF"] > 1.0).sum()
            print("")
            print("Окон с PF > 1.0: " + str(wins) + " из " + str(len(res)))
            print("Средний PF: " + str(round(res["PF"].mean(), 3)))
            print("Средний Sharpe: " + str(round(res["Sharpe"].mean(), 3)))
        print("")