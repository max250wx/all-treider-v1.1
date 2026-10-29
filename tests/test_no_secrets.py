"""Защита от повторной утечки токенов в код."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "data",
    "tests",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

PATTERNS = [
    # T-Invest token: t. + base64-ish (реальный токен ~80-100 символов)
    re.compile(r"t\.[A-Za-z0-9_-]{60,}={0,2}"),
    # Telegram bot token
    re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    # api_key / secret / password = "..."
    re.compile(r"(?i)(api[_-]?key|secret|password)\s*=\s*['\"][^'\"]{8,}['\"]"),
]


def _iter_py_files():
    for p in ROOT.rglob("*.py"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def test_no_hardcoded_secrets():
    hits: list[str] = []
    for p in _iter_py_files():
        text = p.read_text(encoding="utf-8", errors="ignore")
        for pat in PATTERNS:
            if pat.search(text):
                hits.append(f"{p.relative_to(ROOT)}: matches {pat.pattern}")
    assert not hits, "Похоже на секреты в коде:\n" + "\n".join(hits)
