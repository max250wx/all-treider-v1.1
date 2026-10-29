"""FastAPI backend — торговый терминал MOEX."""

import io
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from datetime import datetime, timedelta

import pandas as pd
import requests
from fastapi import FastAPI, HTTPException, Query, Depends, Header
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path

DATA_LIVE = Path(__file__).resolve().parent.parent.parent / "data" / "live"

AUTH_LOGIN = os.environ.get("APP_LOGIN", "admin")
AUTH_PASSWORD = os.environ.get("APP_PASSWORD", "moex2026")
ACTIVE_TOKENS = set()

app = FastAPI(title="AI-Trader MOEX")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

INSTRUMENTS = {
    "stocks": {
        "label": "Акции",
        "items": [
            {"ticker": "SBER", "name": "Сбербанк", "board": "TQBR"},
            {"ticker": "GAZP", "name": "Газпром", "board": "TQBR"},
            {"ticker": "LKOH", "name": "ЛУКОЙЛ", "board": "TQBR"},
            {"ticker": "VTBR", "name": "ВТБ", "board": "TQBR"},
            {"ticker": "ROSN", "name": "Роснефть", "board": "TQBR"},
            {"ticker": "GMKN", "name": "Норникель", "board": "TQBR"},
            {"ticker": "NVTK", "name": "НОВАТЭК", "board": "TQBR"},
            {"ticker": "TATN", "name": "Татнефть", "board": "TQBR"},
            {"ticker": "YDEX", "name": "Яндекс", "board": "TQBR"},
            {"ticker": "MTSS", "name": "МТС", "board": "TQBR"},
            {"ticker": "MGNT", "name": "Магнит", "board": "TQBR"},
            {"ticker": "PLZL", "name": "Полюс", "board": "TQBR"},
        ],
    },
    "bonds": {
        "label": "Облигации",
        "items": [
            {"ticker": "RU000A0JQAM6", "name": "ДОМ.РФ15об", "board": "TQCB"},
            {"ticker": "RU000A0JR4U9", "name": "ГлДорога 3", "board": "TQCB"},
            {"ticker": "RU000A0JRJB8", "name": "ЗСД 01", "board": "TQCB"},
            {"ticker": "RU000A0JRJL7", "name": "ЗСД 02", "board": "TQCB"},
            {"ticker": "RU000A0JRU20", "name": "СЗКК 03", "board": "TQCB"},
        ],
    },
    "ofz": {
        "label": "ОФЗ",
        "items": [
            {"ticker": "SU26238RMFS4", "name": "ОФЗ 26238", "board": "TQOB"},
            {"ticker": "SU26243RMFS4", "name": "ОФЗ 26243", "board": "TQOB"},
            {"ticker": "SU26248RMFS4", "name": "ОФЗ 26248", "board": "TQOB"},
            {"ticker": "SU26247RMFS5", "name": "ОФЗ 26247", "board": "TQOB"},
            {"ticker": "SU26244RMFS2", "name": "ОФЗ 26244", "board": "TQOB"},
        ],
    },
    "funds": {
        "label": "Фонды",
        "items": [
            {"ticker": "TMOS", "name": "Тинькофф iMOEX", "board": "TQBR"},
            {"ticker": "SBMX", "name": "Сбер Индекс МосБиржи", "board": "TQBR"},
            {"ticker": "SBMM", "name": "Сбер Индекс МосБиржи", "board": "TQBR"},
            {"ticker": "EQMX", "name": "ВИМ Ликвидность", "board": "TQBR"},
            {"ticker": "AKGD", "name": "АК Доступное золото", "board": "TQBR"},
        ],
    },  # _funds_tqbr
    "futures": {
        "label": "Фьючерсы",
        "items": [
            {"ticker": "BRZ6", "name": "Brent 12.26", "board": "RFUD"},
            {"ticker": "BRX6", "name": "Brent 11.26", "board": "RFUD"},
            {"ticker": "NGZ6", "name": "Газ 12.26", "board": "RFUD"},
            {"ticker": "NGX6", "name": "Газ 11.26", "board": "RFUD"},
            {"ticker": "SRZ6", "name": "Сбер 12.26", "board": "RFUD"},
            {"ticker": "GZZ6", "name": "Газпром 12.26", "board": "RFUD"},
            {"ticker": "RIZ6", "name": "RTS 12.26", "board": "RFUD"},
            {"ticker": "MXZ6", "name": "MIX 12.26", "board": "RFUD"},
            {"ticker": "GDZ6", "name": "Золото 12.26", "board": "RFUD"},
            {"ticker": "SVZ6", "name": "Серебро 12.26", "board": "RFUD"},
        ],
    },
}


def fetch_csv(filename):
    p = DATA_LIVE / filename
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p)
    except Exception:
        return pd.DataFrame()



def market_for_board(board):
    if board == "TQBR":
        return "shares"
    if board in ("TQCB", "TQOB"):
        return "bonds"
    if board == "TQTF":
        return "shares"
    if board == "RFUD":
        return "futures"
    return "shares"


def fetch_moex_candles(ticker, board, interval, count=200):
    if board == "RFUD":
        url = f"https://iss.moex.com/iss/engines/futures/markets/forts/securities/{ticker}/candles.json"
    else:
        market = market_for_board(board)
        url = f"https://iss.moex.com/iss/engines/stock/markets/{market}/boards/{board}/securities/{ticker}/candles.json"
    params = {
        "interval": interval,
        "iss.meta": "off",
        "limit": count,
        "from": (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d"),
    }  # _from_patch
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()["candles"]
        return pd.DataFrame(data["data"], columns=data["columns"])
    except Exception:
        return pd.DataFrame()


class LoginRequest(BaseModel):
    login: str
    password: str


def require_auth(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(401, "Authorization required")
    token = authorization.replace("Bearer ", "").strip()
    if token not in ACTIVE_TOKENS:
        raise HTTPException(401, "Invalid token")
    return token


@app.post("/api/login")
def login(req: LoginRequest):
    if req.login == AUTH_LOGIN and req.password == AUTH_PASSWORD:
        token = secrets.token_urlsafe(32)
        ACTIVE_TOKENS.add(token)
        return {"token": token}
    raise HTTPException(401, "Неверный логин или пароль")


@app.post("/api/logout")
def logout(token: str = Depends(require_auth)):
    ACTIVE_TOKENS.discard(token)
    return {"ok": True}


@app.get("/api/me")
def me(token: str = Depends(require_auth)):
    return {"login": AUTH_LOGIN}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/instruments")
def get_instruments():
    return {"categories": INSTRUMENTS}


@app.get("/api/quote/{board}/{ticker}")
def get_quote(board: str, ticker: str):
    if board == "RFUD":
        url = f"https://iss.moex.com/iss/engines/futures/markets/forts/securities/{ticker}.json"
    else:
        market = market_for_board(board)
        url = f"https://iss.moex.com/iss/engines/stock/markets/{market}/boards/{board}/securities/{ticker}.json"
    try:
        r = requests.get(url, params={"iss.meta": "off", "iss.only": "marketdata"}, timeout=10)
        data = r.json()["marketdata"]
        cols = data["columns"]
        rows = data["data"]
        if not rows:
            raise HTTPException(404, "Нет данных")
        row = rows[0]
        idx = {c: i for i, c in enumerate(cols)}
        return {
            "ticker": ticker,
            "last": row[idx.get("LAST")] if "LAST" in idx else None,
            "change_pct": row[idx.get("LASTCHANGEPRC")] if "LASTCHANGEPRC" in idx else None,
            "volume": row[idx.get("VOLTODAY")] if "VOLTODAY" in idx else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"MOEX error: {e}")


@app.get("/api/candles/{board}/{ticker}")
def get_candles(board: str, ticker: str, timeframe: str = "M5", count: int = 200):
    tf_map = {"M1": 1, "M5": 5, "M10": 10, "M15": 15, "H1": 60, "D1": 24}
    if timeframe not in tf_map:
        raise HTTPException(400, "Unknown timeframe")

    moex_interval = 1 if timeframe in ["M1", "M5", "M15"] else tf_map[timeframe]
    df = fetch_moex_candles(ticker, board, moex_interval, count * (5 if timeframe in ["M5", "M15"] else 1))
    if df.empty:
        return {"ticker": ticker, "timeframe": timeframe, "candles": []}

    df["begin"] = pd.to_datetime(df["begin"])
    df = df.set_index("begin")

    if timeframe == "M5":
        df = df.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    elif timeframe == "M15":
        df = df.resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()

    df = df.tail(count)

    return {
        "ticker": ticker,
        "timeframe": timeframe,
        "candles": [
            {
                "time": idx.isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
            }
            for idx, row in df.iterrows()
        ],
    }




@app.get("/api/rvi")
def get_rvi():
    df = fetch_csv("rvi_data.csv")
    if df.empty:
        raise HTTPException(404, "RVI не найден")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])
    last = df.iloc[-1]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent = df[df["timestamp"] >= cutoff]
    return {
        "current": float(last["rvi_current"]),
        "change": float(last["change_pct"]),
        "history": [
            {"time": r["timestamp"].isoformat(), "value": float(r["rvi_current"])}
            for _, r in recent.iterrows()
        ],
    }


@app.get("/api/news")
def get_news(limit: int = 30):
    df = fetch_csv("news_sentiment.csv")
    if df.empty:
        return {"news": []}
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp", ascending=False).head(limit)
    return {
        "news": [
            {
                "time": r["timestamp"].isoformat(),
                "title": r["title"],
                "source": str(r.get("source", "?")),
                "sentiment": float(r.get("sentiment", 0)),
            }
            for _, r in df.iterrows()
        ]
    }


@app.get("/api/telegram")
def get_telegram(limit: int = 30):
    df = fetch_csv("news_telegram_sentiment.csv")
    if df.empty:
        return {"news": []}
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp", ascending=False).head(limit)
    return {
        "news": [
            {
                "time": r["timestamp"].isoformat(),
                "channel": str(r.get("channel", "?")),
                "text": str(r.get("text", ""))[:300],
                "sentiment": float(r.get("sentiment", 0)),
            }
            for _, r in df.iterrows()
        ]
    }


@app.get("/api/signals")
def get_signals():
    df = fetch_csv("news_sentiment.csv")
    if df.empty:
        return {"signals": []}
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])
    strong = df[df["sentiment"].abs() > 0.7].sort_values("timestamp", ascending=False).head(20)
    return {
        "signals": [
            {
                "time": r["timestamp"].isoformat(),
                "title": r["title"],
                "sentiment": float(r["sentiment"]),
                "signal": "LONG" if r["sentiment"] > 0 else "SHORT",
            }
            for _, r in strong.iterrows()
        ]
    }


@app.get("/api/status")
def get_status():
    rss = fetch_csv("news_sentiment.csv")
    tg = fetch_csv("news_telegram_sentiment.csv")
    rvi = fetch_csv("rvi_data.csv")
    return {
        "rss_count": len(rss),
        "telegram_count": len(tg),
        "rvi_count": len(rvi),
        "server_time": datetime.now(timezone.utc).isoformat(),
    }




@app.get("/api/scan")
def scan_all(category: str = None):
    """Массовое сканирование всех тикеров из INSTRUMENTS."""
    import time as _t
    out = []
    cats = [category] if category else list(INSTRUMENTS.keys())
    for cat in cats:
        cat_data = INSTRUMENTS.get(cat, {})
        for it in cat_data.get("items", []):
            ticker = it["ticker"]
            board = it["board"]
            t0 = _t.monotonic()
            try:
                q = get_quote(board, ticker) or {}
                out.append({
                    "category": cat, "ticker": ticker, "board": board,
                    "name": it.get("name", ticker), "ok": True,
                    "last": q.get("last"), "change": q.get("change_pct"),
                    "volume": q.get("volume"),
                    "elapsed_ms": int((_t.monotonic() - t0) * 1000),
                })
            except Exception as e:
                out.append({
                    "category": cat, "ticker": ticker, "board": board,
                    "name": it.get("name", ticker), "ok": False,
                    "error": str(e)[:120],
                    "elapsed_ms": int((_t.monotonic() - t0) * 1000),
                })
    ok = sum(1 for r in out if r["ok"])
    return {"total": len(out), "ok": ok, "failed": len(out) - ok, "results": out}


@app.get("/api/portfolio/prices")
def get_portfolio_prices(tickers: str = Query("")):
    result = {}
    for t in tickers.split(","):
        t = t.strip().upper()
        if not t:
            continue
        for board in ["TQBR", "TQTF", "TQCB", "TQOB", "RFUD"]:
            if board == "RFUD":
                url = f"https://iss.moex.com/iss/engines/futures/markets/forts/securities/{t}.json"
            else:
                market = market_for_board(board)
                url = f"https://iss.moex.com/iss/engines/stock/markets/{market}/boards/{board}/securities/{t}.json"
            try:
                r = requests.get(url, params={"iss.meta": "off", "iss.only": "marketdata"}, timeout=5)
                data = r.json()["marketdata"]
                if data["data"] and data["data"][0]:
                    cols = data["columns"]
                    row = data["data"][0]
                    idx = {c: i for i, c in enumerate(cols)}
                    last = row[idx.get("LAST")] if "LAST" in idx else None
                    if last:
                        result[t] = float(last)
                        break
            except Exception:
                continue
    return {"prices": result}


@app.get("/api/export/news")
def export_news(token: str = Depends(require_auth)):
    df = fetch_csv("news_sentiment.csv")
    if df.empty:
        raise HTTPException(404, "No data")
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=news_export.csv"},
    )


FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    # app.mount("/static", ...) удалён: см. mount("/") в конце файла

    @app.get("/")
    def index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))



# --- статика (должна идти ПОСЛЕ всех @app.get("/api/...")) ---
# --- массовое сканирование всех тикеров ---

def scan_all(category: str = None):
    import time as _t
    out = []
    cats = [category] if category else list(INSTRUMENTS.keys())
    for cat in cats:
        cat_data = INSTRUMENTS.get(cat, {})
        for it in cat_data.get("items", []):
            ticker = it["ticker"]
            board = it["board"]
            t0 = _t.monotonic()
            try:
                q = get_quote(board, ticker) or {}
                out.append({
                    "category": cat,
                    "ticker": ticker,
                    "board": board,
                    "name": it.get("name", ticker),
                    "ok": True,
                    "last": q.get("last"),
                    "change": q.get("change_pct"),
                    "volume": q.get("volume"),
                    "elapsed_ms": int((_t.monotonic() - t0) * 1000),
                })
            except Exception as e:
                out.append({
                    "category": cat, "ticker": ticker, "board": board,
                    "name": it.get("name", ticker), "ok": False,
                    "error": str(e)[:120],
                    "elapsed_ms": int((_t.monotonic() - t0) * 1000),
                })
    ok = sum(1 for r in out if r["ok"])
    return {"total": len(out), "ok": ok, "failed": len(out) - ok, "results": out}





def _board_for_ticker(ticker: str) -> str:
    t = ticker.upper()
    for cat in INSTRUMENTS.values():
        for it in cat.get("items", []):
            if it["ticker"].upper() == t:
                return it["board"]
    return "TQBR"



@app.get("/api/orderbook/{ticker}")
def get_orderbook(ticker: str, depth: int = 8):
    """Стакан из локального CSV (собирает collectors/orderflow.py)."""
    t = ticker.upper()
    p = DATA_LIVE / f"orderbook_{t}.csv"
    if not p.exists():
        return {"ticker": t, "bids": [], "asks": [], "source": "no_data"}
    try:
        df = pd.read_csv(p)
        if df.empty:
            return {"ticker": t, "bids": [], "asks": [], "source": "empty"}
        last = df.iloc[-1]
        bids, asks = [], []
        for i in range(1, 6):
            bp = last.get(f"bid{i}_price")
            bq = last.get(f"bid{i}_qty")
            ap = last.get(f"ask{i}_price")
            aq = last.get(f"ask{i}_qty")
            if pd.notna(bp) and pd.notna(bq):
                bids.append({"price": float(bp), "quantity": int(bq)})
            if pd.notna(ap) and pd.notna(aq):
                asks.append({"price": float(ap), "quantity": int(aq)})
        return {"ticker": t, "bids": bids[:depth], "asks": asks[:depth],
                "time": str(last.get("timestamp", "")), "source": "live"}
    except Exception as e:
        raise HTTPException(500, f"orderbook csv error: {e}")


@app.get("/api/trades/{ticker}")
def get_trades(ticker: str, limit: int = 50):
    """Сделки из локального CSV (собирает collectors/orderflow.py)."""
    t = ticker.upper()
    p = DATA_LIVE / f"trades_{t}.csv"
    if not p.exists():
        return {"ticker": t, "trades": [], "source": "no_data"}
    try:
        df = pd.read_csv(p)
        if df.empty:
            return {"ticker": t, "trades": [], "source": "empty"}
        df = df.tail(limit).iloc[::-1]
        trades = []
        for _, row in df.iterrows():
            d = int(row.get("direction", 0) or 0)
            trades.append({
                "time": str(row.get("timestamp", ""))[11:19],
                "price": float(row["price"]) if pd.notna(row.get("price")) else None,
                "quantity": int(row.get("quantity", 0) or 0),
                "side": "BUY" if d == 1 else "SELL" if d == 2 else "?",
            })
        return {"ticker": t, "trades": trades, "source": "live"}
    except Exception as e:
        raise HTTPException(500, f"trades csv error: {e}")


# --- расширение списка для тестирования ---
_EXTRA_TICKERS = {
    "stocks": [
        {"ticker": "SNGSP", "name": "Сургутнефтегаз ап",   "board": "TQBR"},
        {"ticker": "SNGS",  "name": "Сургутнефтегаз",      "board": "TQBR"},
        {"ticker": "HYDR",  "name": "РусГидро",            "board": "TQBR"},
        {"ticker": "FEES",  "name": "Россети",             "board": "TQBR"},
        {"ticker": "AFKS",  "name": "АФК Система",         "board": "TQBR"},
        {"ticker": "CHMF",  "name": "Северсталь",          "board": "TQBR"},
        {"ticker": "NLMK",  "name": "НЛМК",                "board": "TQBR"},
        {"ticker": "PHOR",  "name": "ФосАгро",             "board": "TQBR"},
        {"ticker": "IRAO",  "name": "Интер РАО",           "board": "TQBR"},
        {"ticker": "RTKM",  "name": "Ростелеком",          "board": "TQBR"},
        {"ticker": "MTLR",  "name": "Мечел",               "board": "TQBR"},
        {"ticker": "PIKK",  "name": "ПИК",                 "board": "TQBR"},
        {"ticker": "FLOT",  "name": "Совкомфлот",          "board": "TQBR"},
        {"ticker": "CBOM",  "name": "МКБ",                 "board": "TQBR"},
        {"ticker": "BSPB",  "name": "Банк СПб",            "board": "TQBR"},
        {"ticker": "SIBN",  "name": "Газпром нефть",       "board": "TQBR"},
        {"ticker": "TRNFP", "name": "Транснефть ап",       "board": "TQBR"},
        {"ticker": "ALRS",  "name": "АЛРОСА",              "board": "TQBR"},
        {"ticker": "AFLT",  "name": "Аэрофлот",            "board": "TQBR"},
        {"ticker": "MAGN",  "name": "ММК",                 "board": "TQBR"},
        {"ticker": "MOEX",  "name": "Московская биржа",    "board": "TQBR"},
    ],
    "futures": [
        {"ticker": "W4Z6",  "name": "Wheat 12.26",         "board": "RFUD"},
        {"ticker": "CRZ6",  "name": "Юань 12.26",          "board": "RFUD"},
        {"ticker": "EDZ6",  "name": "EUR/USD 12.26",       "board": "RFUD"},
    ],
    "funds": [
        {"ticker": "SBMM",  "name": "Сбер Индекс МосБиржи", "board": "TQTF"},
        {"ticker": "TBRU",  "name": "Т-Банк Рубль",         "board": "TQTF"},
    ],
}

for _cat, _items in _EXTRA_TICKERS.items():
    INSTRUMENTS.setdefault(_cat, {"label": _cat, "items": []})
    INSTRUMENTS[_cat].setdefault("items", [])
    _have = {x["ticker"] for x in INSTRUMENTS[_cat]["items"]}
    for _it in _items:
        if _it["ticker"] not in _have:
            INSTRUMENTS[_cat]["items"].append(_it)


# --- СТАТИКА (в самом конце файла) ---


# --- СТАТИКА (в самом конце) ---
from fastapi.staticfiles import StaticFiles as _SF_FINAL
app.mount("/", _SF_FINAL(directory=r"C:\\trader\\web\\frontend", html=True), name="static_root")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
