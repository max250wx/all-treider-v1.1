"""Тесты для config.py: загрузка из env, падение при отсутствии токена."""

import importlib
import sys

import pytest


def _reload_config():
    sys.modules.pop("config", None)
    return importlib.import_module("config")


def test_config_loads_with_env(monkeypatch):
    monkeypatch.setenv("T_INVEST_TOKEN", "t.test-token")
    cfg = _reload_config()
    assert cfg.TOKEN == "t.test-token"
    assert cfg.MODEL
    assert isinstance(cfg.TICKERS, list)


def test_config_raises_without_token(monkeypatch):
    monkeypatch.delenv("T_INVEST_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="T_INVEST_TOKEN"):
        _reload_config()


def test_config_intervals_positive(monkeypatch):
    monkeypatch.setenv("T_INVEST_TOKEN", "t.test-token")
    cfg = _reload_config()
    assert cfg.POLL_INTERVAL_SEC > 0
    assert cfg.RVI_POLL_SEC > 0
