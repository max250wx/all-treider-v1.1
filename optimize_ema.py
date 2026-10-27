"""
Out-of-sample + оптимизация EMA Cross на фьючерсах BR и NG.
Цель: убедиться, что результат не переоптимизирован, и подобрать fast/slow.
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


class EMACross(Strategy):
    fast = 9
    slow = 21
    stop_pct = 0.010
    tp_pct = 0.015
    size = 10          # ← увеличили с 1 до 10, чтобы Returns были значимее

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


def run_bt(data, fast=9, slow=21, cash=1_000_000):
    bt = Backtest(
        data, EMACross,
        cash=cash,
        commission=0.0002,
        spread=0.0002,
        margin=0.1,
        exclusive_orders=True,
        trade_on_close=False,
    )
    return bt.run(fast=fast, slow=slow)


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
    for name, file in [("BR (Brent)", "br_m1.csv"), ("NG (Gas)", "ng_m1.csv")]:
        print(f"\n{'='*95}")
        print(f"  {name}  ({file})")
        print(f"{'='*95}")
        data = load_csv(file)
        split = int(len(data) * 0.7)
        train = data.iloc[:split]
        test  = data.iloc[split:]
        print(f"Train: {len(train)} баров ({train.index[0]} — {train.index[-1]})")
        print(f"Test:  {len(test)} баров ({test.index[0]} — {test.index[-1]})\n")

        # ── 1. Базовая проверка на train ──
        print("── In-sample (train) ──")
        s_train = run_bt(train, fast=9, slow=21)
        print(pd.DataFrame([pretty(s_train)]).to_string(index=False))

        # ── 2. Оптимизация fast/slow на train ──
        print("\n── Оптимизация fast/slow на train ──")
        best_params = None
        best_sharpe = -np.inf
        results = []
        for fast in [5, 8, 9, 12, 15]:
            for slow in [20, 21, 26, 30, 40]:
                if fast >= slow:
                    continue
                s = run_bt(train, fast=fast, slow=slow)
                sharpe = s["Sharpe Ratio"]
                if pd.isna(sharpe) or sharpe == np.inf:
                    continue
                results.append({
                    "fast": fast, "slow": slow,
                    "Trades": int(s["# Trades"]),
                    "PF": round(s["Profit Factor"], 3) if not pd.isna(s["Profit Factor"]) else 0,
                    "Sharpe": round(sharpe, 2),
                    "Return%": round(s["Return [%]"], 3),
                })
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_params = (fast, slow)

        df_opt = pd.DataFrame(results).sort_values("Sharpe", ascending=False)
        print(df_opt.head(10).to_string(index=False))
        print(f"\nЛучшие параметры на train: fast={best_params[0]}, slow={best_params[1]}")

        # ── 3. Out-of-sample на test ──
        print(f"\n── Out-of-sample (test) с fast={best_params[0]}, slow={best_params[1]} ──")
        s_test = run_bt(test, fast=best_params[0], slow=best_params[1])
        print(pd.DataFrame([pretty(s_test)]).to_string(index=False))