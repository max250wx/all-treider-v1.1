"""Скачиваем NGU6 (NG-9.26) отдельно и тестируем EMA Cross на нём.
Это чистый out-of-sample период: другой контракт, другой рынок.
"""

import time
import pandas as pd
import requests
from backtesting import Backtest, Strategy
import warnings
warnings.filterwarnings("ignore")


def download(ticker, start, end, out_csv):
    base_url = ("https://iss.moex.com/iss/engines/futures/markets/forts/"
                f"securities/{ticker}/candles.json")
    rows, columns, s = [], None, 0
    while True:
        r = requests.get(base_url,
                         params={"from": start, "till": end, "interval": 1, "start": s},
                         timeout=30)
        r.raise_for_status()
        c = r.json()["candles"]
        if columns is None:
            columns = c["columns"]
        if not c["data"]:
            break
        rows.extend(c["data"])
        print(f"  {ticker}: {len(rows)} свечей...")
        if len(c["data"]) < 500:
            break
        s += len(c["data"])
        time.sleep(0.3)
    df = pd.DataFrame(rows, columns=columns)
    df["begin"] = pd.to_datetime(df["begin"])
    df = df.set_index("begin").sort_index()
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                             "close": "Close", "volume": "Volume"})
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df = df[df["Volume"] > 0]
    df.to_csv(out_csv)
    print(f"\nСохранено: {out_csv}")
    print(f"Баров: {len(df)}")
    print(f"Период: {df.index[0]} — {df.index[-1]}")
    print(f"Цена: {df['Close'].min():.3f} … {df['Close'].max():.3f}")
    return df


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


if __name__ == "__main__":
    print("Качаем NGU6 (NG-9.26) отдельно — чистый период июль–сентябрь...")
    df = download("NGU6", "2026-07-01", "2026-09-25", "ngu6_m1.csv")

    print(f"\nТестируем EMA Cross на NGU6 ({len(df)} баров)...")
    bt = Backtest(df, EMACross, cash=1_000_000,
                  commission=0.0002, spread=0.0002, margin=0.1,
                  exclusive_orders=True, trade_on_close=False)
    stats = bt.run()
    print(stats)