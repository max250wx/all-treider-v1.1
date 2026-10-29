import os, yaml, logging
from pathlib import Path

CFG_PATH = Path(os.getenv("STRATEGY_CONFIG", "config/strategy_config.yaml"))

_DEFAULTS = {
    "ema": {"fast": 20, "slow": 50, "trend": 200},
    "atr": {"min": 0.005, "max": 0.060, "stop_mult_low_rvi": 1.5,
            "stop_mult_high_rvi": 2.5, "rvi_high": 60},
    "volume": {"sma_period": 20, "min_ratio": 1.0},
    "obv": {"lookback": 5},
    "rvi": {"panic": 80, "high": 60, "low_risk_threshold": 55},
    "risk": {
        "per_trade": 0.003,
        "per_trade_high_rvi": 0.0015,
        "max_positions": 3,
        "max_exposure": 0.30,
        "daily_loss_limit": 0.015,
        "max_drawdown": 0.10,
    },
    "partial_tp": {"first_r": 1.0, "size": 0.5},
    "imoex": {"filter": True},
}

def load_config():
    cfg = _DEFAULTS.copy()
    if CFG_PATH.exists():
        with open(CFG_PATH, encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        for k, v in user_cfg.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k] = {**cfg[k], **v}
            else:
                cfg[k] = v
    return cfg

def setup_logging(level=logging.INFO):
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler("logs/strategy.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
