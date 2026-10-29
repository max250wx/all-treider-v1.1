"""Config-driven scalping framework: стратегии + фильтры + таймфрейм + инструмент из YAML."""

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml
from backtesting import Backtest, Strategy


# ─────────────────────────────────────────────
# БАЗОВЫЙ КЛАСС: стратегия + фильтры
# ─────────────────────────────────────────────
class BaseStrategy(Strategy):
    """Базовый класс: стратегия + динамические фильтры."""

    signal = None
    signal_params = {}
    filters = []
    exit_params = {}
    size = 10

    def init(self):
        self.signal_impl = SIGNAL_REGISTRY[self.signal](self.signal_params)
        self.signal_impl.init(self)

        self.filter_impls = [FILTER_REGISTRY[f["type"]](f) for f in self.filters]
        for f in self.filter_impls:
            f.init(self)

    def next(self):
        if not self.signal_impl.ready(self) or self.position:
            return

        if not all(f.allow(self) for f in self.filter_impls):
            return

        action = self.signal_impl.signal(self)
        if action == "long":
            price = self.data.Close[-1]
            self.buy(
                size=self.size,
                sl=price * (1 - self.exit_params["stop_pct"]),
                tp=price * (1 + self.exit_params["tp_pct"]),
            )
        elif action == "short":
            price = self.data.Close[-1]
            self.sell(
                size=self.size,
                sl=price * (1 + self.exit_params["stop_pct"]),
                tp=price * (1 - self.exit_params["tp_pct"]),
            )


# ─────────────────────────────────────────────
# РЕГИСТР: сигналы
# ─────────────────────────────────────────────
class RSISignal:
    def __init__(self, params):
        self.period = params["rsi_period"]
        self.buy = params["rsi_buy"]
        self.sell = params["rsi_sell"]

    def init(self, strategy):
        def rsi(s, p):
            s = pd.Series(s)
            d = s.diff()
            gain = d.where(d > 0, 0.0)
            loss = -d.where(d < 0, 0.0)
            ag = gain.ewm(alpha=1 / p, adjust=False).mean()
            al = loss.ewm(alpha=1 / p, adjust=False).mean()
            rs = ag / al.replace(0, float("nan"))
            return 100 - 100 / (1 + rs)

        strategy.rsi = strategy.I(rsi, strategy.data.Close, self.period)

    def ready(self, strategy):
        return not pd.isna(strategy.rsi[-1])

    def signal(self, strategy):
        r = strategy.rsi[-1]
        if r < self.buy:
            return "long"
        if r > self.sell:
            return "short"
        return None


class EMACrossSignal:
    def __init__(self, params):
        self.fast = params["fast"]
        self.slow = params["slow"]

    def init(self, strategy):
        def ema(s, p):
            return pd.Series(s).ewm(span=p, adjust=False).mean()

        strategy.fast = strategy.I(ema, strategy.data.Close, self.fast)
        strategy.slow = strategy.I(ema, strategy.data.Close, self.slow)

    def ready(self, strategy):
        return len(strategy.fast) >= 2

    def signal(self, strategy):
        if strategy.fast[-2] <= strategy.slow[-2] and strategy.fast[-1] > strategy.slow[-1]:
            return "long"
        if strategy.fast[-2] >= strategy.slow[-2] and strategy.fast[-1] < strategy.slow[-1]:
            return "short"
        return None


# ─────────────────────────────────────────────
# РЕГИСТР: фильтры
# ─────────────────────────────────────────────
class EMATrendFilter:
    def __init__(self, params):
        self.period = params["ema_period"]
        self.direction = params.get("direction", "above")

    def init(self, strategy):
        def ema(s, p):
            return pd.Series(s).ewm(span=p, adjust=False).mean()

        strategy.ema_trend = strategy.I(ema, strategy.data.Close, self.period)

    def allow(self, strategy):
        if self.direction == "above":
            return strategy.data.Close[-1] > strategy.ema_trend[-1]
        if self.direction == "below":
            return strategy.data.Close[-1] < strategy.ema_trend[-1]
        return True


class SessionFilter:
    def __init__(self, params):
        self.hours = params["hours"]

    def init(self, strategy):
        pass

    def allow(self, strategy):
        hour = strategy.data.index[-1].hour
        return self.hours[0] <= hour <= self.hours[1]


class VolumeFilter:
    def __init__(self, params):
        self.period = params["vol_period"]
        self.min_ratio = params.get("min_ratio", 1.0)

    def init(self, strategy):
        strategy.vol_ma = strategy.I(
            lambda s, p: pd.Series(s).rolling(p).mean(),
            strategy.data.Volume,
            self.period,
        )

    def allow(self, strategy):
        if pd.isna(strategy.vol_ma[-1]):
            return False
        return strategy.data.Volume[-1] >= strategy.vol_ma[-1] * self.min_ratio


class VolatilityFilter:
    """Фильтр: ATR% > median (не торгуем в шум)."""

    def __init__(self, params):
        self.period = params.get("atr_period", 14)
        self.min_mult = params.get("min_mult", 1.0)

    def init(self, strategy):
        def atr(h, low, c, p):
            h, low, c = pd.Series(h), pd.Series(low), pd.Series(c)
            tr = pd.concat([h - low, (h - c.shift()).abs(), (low - c.shift()).abs()], axis=1).max(
                axis=1
            )
            return tr.ewm(alpha=1 / p, adjust=False).mean()

        strategy.atr = strategy.I(
            atr, strategy.data.High, strategy.data.Low, strategy.data.Close, self.period
        )
        strategy.atr_pct = strategy.atr / strategy.data.Close * 100

    def allow(self, strategy):
        if pd.isna(strategy.atr_pct[-1]):
            return False
        window = strategy.atr_pct[-100:]
        if len(window) < 20:
            return True
        median = pd.Series(window).median()
        return strategy.atr_pct[-1] >= median * self.min_mult


# ─────────────────────────────────────────────
# РЕГИСТРЫ (словари)
# ─────────────────────────────────────────────
SIGNAL_REGISTRY = {
    "rsi": RSISignal,
    "ema_cross": EMACrossSignal,
}

FILTER_REGISTRY = {
    "ema_trend": EMATrendFilter,
    "session": SessionFilter,
    "volume": VolumeFilter,
    "volatility": VolatilityFilter,
}


# ─────────────────────────────────────────────
# ТАЙМФРЕЙМ: resample M1 → M5 / M10 / M15 / H1
# ─────────────────────────────────────────────
def resample_data(df, timeframe):
    """Агрегирует M1 → M5 / M10 / M15 / H1."""
    if timeframe == "M1":
        return df
    rule = {
        "M5": "5min",
        "M10": "10min",
        "M15": "15min",
        "H1": "1h",
    }.get(timeframe)
    if rule is None:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    resampled = (
        df.resample(rule)
        .agg(
            {
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Volume": "sum",
            }
        )
        .dropna()
    )
    return resampled[resampled["Volume"] > 0]


# ─────────────────────────────────────────────
# ИНСТРУМЕНТ / БИРЖА: метаданные из YAML
# ─────────────────────────────────────────────
EXCHANGE_CONFIG = {
    "MOEX": {
        "commission": 0.0005,  # 0.05% — брокер (акция)
        "spread": 0.0001,  # 0.01%
        "margin": 0.1,
    },
    "MOEX_FUT": {
        "commission": 0.000066,  # 0.0066% — фьючерс
        "spread": 0.00005,  # 0.005%
        "margin": 0.1,
    },
}


def resolve_instrument(config):
    """Возвращает (data_path, commission, spread, margin) из YAML."""
    instrument = config.get("instrument", "IMOEXF")
    exchange = config.get("exchange", "MOEX_FUT")
    if exchange not in EXCHANGE_CONFIG:
        raise ValueError(f"Unknown exchange: {exchange}")
    ex = EXCHANGE_CONFIG[exchange]
    return {
        "instrument": instrument,
        "exchange": exchange,
        "data_path": config["data_path"],
        "commission": config.get("commission", ex["commission"]),
        "spread": config.get("spread", ex["spread"]),
        "margin": config.get("margin", ex["margin"]),
    }


# ─────────────────────────────────────────────
# ЗАГРУЗКА КОНФИГА
# ─────────────────────────────────────────────
def load_config(path):
    path = Path(path)
    if path.suffix in (".yaml", ".yml"):
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    raise ValueError(f"Unsupported config: {path.suffix}")


# ─────────────────────────────────────────────
# ЗАПУСК
# ─────────────────────────────────────────────
def run(config):
    meta = resolve_instrument(config)
    print(
        f"Инструмент: {meta['instrument']} | Биржа: {meta['exchange']} | "
        f"Комиссия: {meta['commission']} | Спред: {meta['spread']}"
    )

    data = pd.read_csv(meta["data_path"], parse_dates=True, index_col=0)
    data = data.rename(
        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    )
    data = data[["Open", "High", "Low", "Close", "Volume"]].dropna()
    data = data[data["Volume"] > 0].sort_index()

    timeframe = config.get("timeframe", "M1")
    data = resample_data(data, timeframe)
    print(f"Таймфрейм: {timeframe} | Баров: {len(data)}\n")

    results = []
    for s_cfg in config["strategies"]:
        cls = type(
            f"Strategy_{s_cfg['name'].replace(' ', '_')}",
            (BaseStrategy,),
            {
                "signal": s_cfg["type"],
                "signal_params": s_cfg["params"],
                "filters": s_cfg.get("filters", []),
                "exit_params": s_cfg["exit"],
                "size": s_cfg.get("size", 10),
            },
        )

        bt = Backtest(
            data,
            cls,
            cash=config["cash"],
            commission=meta["commission"],
            spread=meta["spread"],
            margin=meta["margin"],
            exclusive_orders=True,
            trade_on_close=False,
            finalize_trades=True,
        )
        stats = bt.run()

        results.append(
            {
                "Strategy": s_cfg["name"],
                "Trades": int(stats["# Trades"]),
                "WinRate%": round(stats["Win Rate [%]"], 2),
                "Return%": round(stats["Return [%]"], 3),
                "PF": round(stats["Profit Factor"], 3)
                if stats["Profit Factor"] != float("inf")
                else "inf",
                "Sharpe": round(stats["Sharpe Ratio"], 2)
                if stats["Sharpe Ratio"] != float("inf")
                else "inf",
                "MaxDD%": round(stats["Max. Drawdown [%]"], 3),
            }
        )

    summary = pd.DataFrame(results)
    print(summary.to_string(index=False))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="scalping_config.yaml")
    ap.add_argument("--timeframe", help="Override timeframe (M1/M5/M10/M15/H1)")
    ap.add_argument("--instrument", help="Override instrument (GAZP/SBER/...)")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.timeframe:
        cfg["timeframe"] = args.timeframe
    if args.instrument:
        cfg["instrument"] = args.instrument
        cfg["data_path"] = f"data/history/{args.instrument}_M10.csv"
    run(cfg)
