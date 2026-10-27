"""DEBUG: печатает, что происходит в next() на каждом сигнале."""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy


def load_combined(path="combined_data.csv"):
    df = pd.read_csv(path, parse_dates=True, index_col="timestamp")
    df = df.sort_index()
    df["Open"] = df["mid_price"]
    df["High"] = df["mid_price"] * 1.0005
    df["Low"] = df["mid_price"] * 0.9995
    df["Close"] = df["mid_price"]
    df["Volume"] = df["buy_volume"] + df["sell_volume"]
    for col in ["book_imbalance", "trade_imbalance", "news_sentiment"]:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    return df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])


class DebugStrategy(Strategy):
    book_threshold = 0.15
    trade_threshold = 0.15
    stop_pct = 0.003
    tp_pct = 0.005
    size = 100

    def init(self):
        self.book_arr = self.data.df["book_imbalance"].to_numpy().copy()
        self.trade_arr = self.data.df["trade_imbalance"].to_numpy().copy()
        self.book_ma = pd.Series(self.book_arr).rolling(3).mean().to_numpy()
        self.trade_ma = pd.Series(self.trade_arr).rolling(3).mean().to_numpy()

        print()
        print("=== INIT ===")
        print(f"  len(book_ma) = {len(self.book_ma)}")
        print(f"  book_ma[0:5] = {self.book_ma[0:5]}")
        print(f"  book_ma[100] = {self.book_ma[100]}")
        print(f"  book_ma[-1] = {self.book_ma[-1]}")
        print(f"  len(self.data) at init = {len(self.data)}")
        print(f"  columns = {list(self.data.df.columns)}")
        print()

    def next(self):
        i = len(self.data) - 1

        if i in (3, 50, 100, 200, 297):
            try:
                book = self.book_ma[i] if i < len(self.book_ma) else None
                trade = self.trade_ma[i] if i < len(self.trade_ma) else None
                print(f"next: i={i} len(data)={len(self.data)} "
                      f"book={book} trade={trade} "
                      f"pos={bool(self.position)}")
            except Exception as e:
                print(f"next: i={i} ERROR {e}")

        if self.position:
            return
        if i < 3:
            return

        try:
            book = self.book_ma[i]
            trade = self.trade_ma[i]
        except IndexError:
            return

        if pd.isna(book) or pd.isna(trade):
            return

        price = self.data.Close[-1]

        if book > self.book_threshold and trade > self.trade_threshold:
            print(f"  >>> BUY at i={i}: book={book:.4f} trade={trade:.4f} price={price:.2f}")
            self.buy(size=self.size,
                     sl=price * (1 - self.stop_pct),
                     tp=price * (1 + self.tp_pct))
            return

        if book < -self.book_threshold and trade < -self.trade_threshold:
            print(f"  >>> SELL at i={i}: book={book:.4f} trade={trade:.4f} price={price:.2f}")
            self.sell(size=self.size,
                      sl=price * (1 + self.stop_pct),
                      tp=price * (1 - self.tp_pct))


if __name__ == "__main__":
    data = load_combined("combined_data.csv")
    print(f"Всего баров: {len(data)}")
    bt = Backtest(data, DebugStrategy, cash=1_000_000,
                  commission=0.0003, spread=0.0002, margin=0.2,
                  exclusive_orders=True, trade_on_close=False)
    stats = bt.run()
    print()
    print("Сделок:", stats["# Trades"])