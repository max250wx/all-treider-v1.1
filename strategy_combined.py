"""Стратегия на combined_data.csv: order flow + выход по времени."""

import warnings

import numpy as np
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
    for col in ["book_imbalance", "trade_imbalance", "news_sentiment"]:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    return df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])


class OrderFlowStrategy(Strategy):
    book_threshold = 0.15
    trade_threshold = 0.15
    stop_pct = 0.001  # 0.1% стоп
    tp_pct = 0.002  # 0.2% тейк
    max_hold_bars = 12  # выход по времени: 12 баров = 60 сек
    size = 100
    use_news = False

    def init(self):
        self.book_arr = self.data.df["book_imbalance"].to_numpy().copy()
        self.trade_arr = self.data.df["trade_imbalance"].to_numpy().copy()
        if "news_sentiment" in self.data.df.columns:
            self.news_arr = self.data.df["news_sentiment"].to_numpy().copy()
        else:
            self.news_arr = np.zeros(len(self.data.df))

        self.book_ma = pd.Series(self.book_arr).rolling(3).mean().to_numpy()
        self.trade_ma = pd.Series(self.trade_arr).rolling(3).mean().to_numpy()

        self.entry_bar = -1

    def next(self):
        i = len(self.data) - 1

        # ── Если в позиции — проверяем выход по времени ──
        if self.position:
            bars_held = i - self.entry_bar
            if bars_held >= self.max_hold_bars:
                self.position.close()
                self.entry_bar = -1
            return

        if i < 3:
            return

        book = self.book_ma[i]
        trade = self.trade_ma[i]
        if pd.isna(book) or pd.isna(trade):
            return

        news = self.news_arr[i]
        price = self.data.Close[-1]

        if (
            book > self.book_threshold
            and trade > self.trade_threshold
            and ((not self.use_news) or news >= 0)
        ):
            self.buy(
                size=self.size,
                sl=price * (1 - self.stop_pct),
                tp=price * (1 + self.tp_pct),
            )
            self.entry_bar = i
            return

        if (
            book < -self.book_threshold
            and trade < -self.trade_threshold
            and ((not self.use_news) or news <= 0)
        ):
            self.sell(
                size=self.size,
                sl=price * (1 + self.stop_pct),
                tp=price * (1 - self.tp_pct),
            )
            self.entry_bar = i


def run(data, use_news=False):
    bt = Backtest(
        data,
        OrderFlowStrategy,
        cash=1_000_000,
        commission=0.0003,
        spread=0.0002,
        margin=0.2,
        exclusive_orders=True,
        trade_on_close=False,
    )
    return bt.run(use_news=use_news)


if __name__ == "__main__":
    data = load_combined("combined_data.csv")
    print(f"Баров: {len(data)}")
    print(f"Период: {data.index[0]} — {data.index[-1]}")
    print()

    print("=" * 70)
    print("  OrderFlow + выход по времени")
    print("=" * 70)
    s = run(data, use_news=False)
    print(s)

    print()
    print("─ Сделки ─")
    trades = s["_trades"]
    if len(trades) > 0:
        cols = [
            c
            for c in ["Size", "EntryPrice", "ExitPrice", "PnL", "ReturnPct", "Duration"]
            if c in trades.columns
        ]
        print(trades[cols].to_string())
