"""Стратегия на book_imbalance (без trade).
Вход в топ-квартиле book, выход через 3-6 баров."""

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
    if "book_imbalance" in df.columns:
        df["book_imbalance"] = df["book_imbalance"].fillna(0)
    return df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])


class BookStrategy(Strategy):
    book_high = 0.30  # порог для LONG (top quartile)
    book_low = -0.30  # порог для SHORT
    max_hold_bars = 6  # держим 30 сек
    stop_pct = 0.0015  # 0.15% стоп
    tp_pct = 0.0015  # 0.15% тейк
    size = 100
    use_maker_fees = True  # комиссия 0.015% (maker)

    def init(self):
        bi = self.data.df["book_imbalance"].to_numpy().copy()
        self.book = bi
        self.entry_bar = -1

    def next(self):
        i = len(self.data) - 1

        if self.position:
            if i - self.entry_bar >= self.max_hold_bars:
                self.position.close()
                self.entry_bar = -1
            return

        if i < 1:
            return

        book = self.book[i]
        if pd.isna(book):
            return

        price = self.data.Close[-1]

        if book > self.book_high:
            self.buy(size=self.size, sl=price * (1 - self.stop_pct), tp=price * (1 + self.tp_pct))
            self.entry_bar = i
            return

        if book < self.book_low:
            self.sell(size=self.size, sl=price * (1 + self.stop_pct), tp=price * (1 - self.tp_pct))
            self.entry_bar = i


def run(data, maker=True):
    comm = 0.00015 if maker else 0.0003
    spread = 0.0 if maker else 0.0002

    bt = Backtest(
        data,
        BookStrategy,
        cash=1_000_000,
        commission=comm,
        spread=spread,
        margin=0.2,
        exclusive_orders=True,
        trade_on_close=False,
    )
    return bt.run()


if __name__ == "__main__":
    data = load_combined()
    print(f"Баров: {len(data)}\n")

    print("=" * 70)
    print("  MAKER (комиссия 0.015%, без спреда)")
    print("=" * 70)
    s1 = run(data, maker=True)
    print(s1)
    print()

    print("=" * 70)
    print("  TAKER (комиссия 0.03%, спред 0.02%) — как было раньше")
    print("=" * 70)
    s2 = run(data, maker=False)
    print(s2)
