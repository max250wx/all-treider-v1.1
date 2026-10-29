"""
Out-of-sample: Mean-Rev + Sessions на NGX6 (октябрь-ноябрь 2026).
Проверяем, воспроизводится ли результат NGV6 на независимом периоде.
"""

import time
import pandas as pd
import requests
import warnings
warnings.filterwarnings("ignore")

import numpy as np
from backtesting import Backtest, Strategy


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
    print(f"Баров M1: {len(df)}")
    print(f"Период: {df.index[0]} — {df.index[-1]}")

    # Сразу агрегируем в M5
    df_m5 = df.resample("5min").agg({
        "Open": "first", "High": "max", "Low": "min",
        "Close": "last", "Volume": "sum",
    }).dropna()
    df_m5 = df_m5[df_m5["Volume"] > 0]
    out_m5 = out_csv.replace("_m1", "_m5")
    df_m5.to_csv(out_m5)
    print(f"Сохранено: {out_m5}")
    print(f"Баров M5: {len(df_m5)}")
    return df_m5


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
        })
    return pd.DataFrame(out)


if __name__ == "__main__":
    print("Качаем NGX6 (ноябрьский контракт)...")
    data = download("NGX6", "2026-10-13", "2026-11-20", "ngx6_m1.csv")

    print("")
    print("=" * 95)
    print("  OUT-OF-SAMPLE: NGX6 M5 (октябрь-ноябрь 2026)")
    print("=" * 95)
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

    res = walk_forward(data, n_windows=5)
    print("")
    print("── Walk-forward ──")
    print(res.to_string(index=False))
    if not res.empty:
        wins = (res["PF"] > 1.0).sum()
        print("")
        print("Окон с PF > 1.0: " + str(wins) + " из " + str(len(res)))
        print("Средний PF: " + str(round(res["PF"].mean(), 3)))
        print("Средний Sharpe: " + str(round(res["Sharpe"].mean(), 3)))