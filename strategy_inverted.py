"""Тест ИНВЕРТИРОВАННОЙ логики: продажи → LONG, покупки → SHORT."""

import warnings

import pandas as pd
from backtesting import Backtest, Strategy

warnings.filterwarnings("ignore")


def load_combined(path="combined_data.csv"):
    df = pd.read_csv(path, parse_dates=True, index_col="timestamp")
    df = df.sort_index()
    df["Open"] = df["mid_price"]
    df["High"] = df["mid_price"] * 1.0002
    df["Low"] = df["mid_price"] * 0.9998
    df["Close"] = df["mid_price"]
    df["Volume"] = df["buy_volume"] + df["sell_volume"]
    for col in ["book_imbalance", "trade_imbalance"]:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    return df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])


class InvertedFlow(Strategy):
    book_threshold = 0.15
    trade_threshold = 0.15
    stop_pct = 0.003
    tp_pct = 0.005
    max_hold_bars = 24
    size = 100

    def init(self):
        bi = self.data.df["book_imbalance"].to_numpy().copy()
        ti = self.data.df["trade_imbalance"].to_numpy().copy()
        self.book_ma = pd.Series(bi).rolling(3).mean().to_numpy()
        self.trade_ma = pd.Series(ti).rolling(3).mean().to_numpy()
        self.entry_bar = -1

    def next(self):
        i = len(self.data) - 1
        if self.position:
            if i - self.entry_bar >= self.max_hold_bars:
                self.position.close()
                self.entry_bar = -1
            return

        if i < 3:
            return

        book = self.book_ma[i]
        trade = self.trade_ma[i]
        if pd.isna(book) or pd.isna(trade):
            return

        price = self.data.Close[-1]

        # ИНВЕРСИЯ: сигнал SHORT → открываем LONG
        if book < -self.book_threshold and trade < -self.trade_threshold:
            self.buy(
                size=self.size,
                sl=price * (1 - self.stop_pct),
                tp=price * (1 + self.tp_pct),
            )
            self.entry_bar = i
            return

        if book > self.book_threshold and trade > self.trade_threshold:
            self.sell(
                size=self.size,
                sl=price * (1 + self.stop_pct),
                tp=price * (1 - self.tp_pct),
            )
            self.entry_bar = i


if __name__ == "__main__":
    data = load_combined()
    print(f"Баров: {len(data)}\n")
    bt = Backtest(
        data,
        InvertedFlow,
        cash=1_000_000,
        commission=0.0003,
        spread=0.0002,
        margin=0.2,
        exclusive_orders=True,
        trade_on_close=False,
    )
    s = bt.run()
    print(s)
    print()
    print("─ Сделки ─")
    trades = s["_trades"]
    if len(trades) > 0:
        cols = [
            c
            for c in ["Size", "EntryPrice", "ExitPrice", "PnL", "ReturnPct"]
            if c in trades.columns
        ]
        print(trades[cols].to_string())
