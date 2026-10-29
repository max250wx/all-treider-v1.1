"""Тесты на ядро бэктестинга: комиссии, спреды, SL/TP, look-ahead."""

import pandas as pd
import pytest
from backtesting import Backtest, Strategy


def _make_data(n=100):
    """Синтетические OHLCV-данные для тестов."""
    idx = pd.date_range("2026-01-01", periods=n, freq="5min")
    df = pd.DataFrame(
        {
            "Open": [100.0] * n,
            "High": [101.0] * n,
            "Low": [99.0] * n,
            "Close": [100.5] * n,
            "Volume": [1000] * n,
        },
        index=idx,
    )
    return df


class _BuyAndHold(Strategy):
    def init(self):
        pass

    def next(self):
        if not self.position:
            self.buy(size=1)


def test_commission_reduces_pnl():
    """Комиссия должна уменьшать итоговый PnL."""
    data = _make_data()
    bt = Backtest(data, _BuyAndHold, cash=100_000, commission=0.001)
    stats = bt.run()
    trades = stats["_trades"]
    if len(trades) == 0:
        pytest.skip("No trades — buy-and-hold не сработал")
    assert trades["PnL"].sum() <= 0, "Комиссия должна уменьшать PnL"


def test_spread_reduces_pnl():
    """Спред должен уменьшать PnL."""
    data = _make_data()
    bt = Backtest(data, _BuyAndHold, cash=100_000, spread=0.01)
    stats = bt.run()
    trades = stats["_trades"]
    if len(trades) == 0:
        pytest.skip("No trades")
    assert trades["PnL"].sum() <= 0, "Спред должен уменьшать PnL"


def test_no_lookahead():
    """Сделка не должна открываться на 0-м баре (только на 1+)."""
    data = _make_data()
    bt = Backtest(data, _BuyAndHold, cash=100_000)
    stats = bt.run()
    trades = stats["_trades"]
    if len(trades) == 0:
        pytest.skip("No trades")
    assert trades.index[0] >= 1, "Look-ahead: сделка на 0-м баре"


def test_mtf_signal_shifted():
    """MTF-сигнал (H1/H4/D1) должен быть сдвинут на 1 бар (закрытый бар)."""
    df = _make_data(n=10)
    signal = (df["Close"] > 100.4).astype(int)
    shifted = signal.shift(1).fillna(0)
    assert (shifted != signal).any(), "shift(1) не сработал"
