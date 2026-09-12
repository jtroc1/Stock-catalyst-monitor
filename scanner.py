from typing import Dict, List, Any
import requests
import pandas as pd
import yfinance as yf

DEFAULT_STOCK_UNIVERSE = [
    "SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
    "META", "TSLA", "AVGO", "BRK-B",
    "AMD", "QCOM", "TSM", "MU", "ARM", "SMCI", "ASML", "INTC", "AMAT", "LRCX",
    "PLTR", "CRM", "NOW", "SNOW", "PANW", "DDOG", "NET", "SHOP", "UBER", "ABNB",
    "PYPL", "SQ", "COIN", "HOOD", "SOFI", "V", "MA",
    "XLE", "XLF", "SMH", "VST", "CEG", "GEV", "BE", "GLW", "CAT",
    "LLY", "UNH", "MRNA", "VRTX", "ROIV",
    "COST", "WMT", "NFLX", "DIS", "BA", "F", "GM",
    "GME", "AMC", "RIVN", "NIO", "SOUN", "IONQ", "RKLB", "MSTR", "MARA", "RIOT",
    "DUOL", "SEI", "SIG", "VASO", "CHYM",
]


def scan_stocks(universe, exclude=None, top_n=15):
    exclude = set(exclude or [])
    tickers = [t for t in universe if t and t not in exclude]
    if not tickers:
        return []
    try:
        data = yf.download(tickers, period="5d", interval="1d", group_by="ticker",
                           threads=True, progress=False, auto_adjust=True)
    except Exception:
        return []

    rows = []
    for symbol in tickers:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if symbol not in data.columns.get_level_values(0):
                    continue
                df = data[symbol].dropna()
            else:
                df = data.dropna()
            if df.empty or "Close" not in df.columns:
                continue
            close = df["Close"].dropna()
            vol = df["Volume"].dropna() if "Volume" in df.columns else None
            if len(close) < 2:
                continue
            price = float(close.iloc[-1])
            prev = float(close.iloc[-2])
            change_pct = ((price / prev) - 1) * 100 if prev else 0
            rvol = None
            if vol is not None and len(vol) >= 3:
                avg = float(vol.iloc[:-1].mean())
                last = float(vol.iloc[-1])
                if avg > 0:
                    rvol = last / avg
            week_change = ((price / float(close.iloc[0])) - 1) * 100
            rank = abs(change_pct)
            if rvol:
                rank += min(rvol, 4) * 1.2
            if abs(week_change) > 8:
                rank += 1.5
            rows.append({
                "symbol": symbol,
                "asset": "stock",
                "price": round(price, 2 if price >= 10 else 4),
                "change_pct": round(change_pct, 2),
                "week_change_pct": round(week_change, 2),
                "rvol": round(rvol, 2) if rvol else None,
                "scan_rank": round(rank, 2),
            })
        except Exception:
            continue
    rows.sort(key=lambda x: x["scan_rank"], reverse=True)
    return rows[:top_n]


def scan_crypto(exclude=None, top_n=15, min_volume_usd=5000000):
    exclude = set(exclude or [])
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "volume_desc",
        "per_page": 80,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        coins = r.json()
    except Exception:
        return []

    rows = []
    for c in coins:
        try:
            symbol = (c.get("symbol") or "").upper()
            yahoo = f"{symbol}-USD"
            if yahoo in exclude or symbol in exclude:
                continue
            price = float(c.get("current_price") or 0)
            change = float(c.get("price_change_percentage_24h") or 0)
            volume = float(c.get("total_volume") or 0)
            mcap = float(c.get("market_cap") or 0)
            if volume < min_volume_usd or abs(change) < 3:
                continue
            rank = abs(change)
            if volume > 50000000:
                rank += 1.0
            if mcap and mcap < 500000000 and abs(change) > 8:
                rank += 1.5
            rows.append({
                "symbol": yahoo,
                "name": c.get("name"),
                "asset": "crypto",
                "price": price,
                "change_pct": round(change, 2),
                "scan_rank": round(rank, 2),
            })
        except Exception:
            continue
    rows.sort(key=lambda x: x["scan_rank"], reverse=True)
    return rows[:top_n]


def run_market_scan(stock_universe=None, watchlist_stocks=None, watchlist_crypto=None,
                    stock_top_n=12, crypto_top_n=12):
    watchlist_stocks = watchlist_stocks or []
    watchlist_crypto = watchlist_crypto or []
    universe = stock_universe or DEFAULT_STOCK_UNIVERSE
    stock_hits = scan_stocks(universe, exclude=watchlist_stocks, top_n=stock_top_n)
    crypto_hits = scan_crypto(exclude=watchlist_crypto, top_n=crypto_top_n)
    return {"stocks": stock_hits, "crypto": crypto_hits, "all": stock_hits + crypto_hits}
MEME_SMALLCAP_UNIVERSE = [
    "GME", "AMC", "BBBYQ", "FFIE", "MULN", "SABS", "GV",
    "SOUN", "IONQ", "RKLB", "RIVN", "NIO", "LCID",
    "MARA", "RIOT", "CLSK", "HUT", "BITF",
    "OPEN", "CVNA", "UPST", "AFRM", "HOOD",
    "CHYM", "VASO", "SEI", "SIG",
]


def scan_meme_smallcaps(exclude=None, top_n=12):
    """Riskier scan with extra penny-stock scrutiny."""
    exclude = set(exclude or [])
    tickers = [t for t in MEME_SMALLCAP_UNIVERSE if t not in exclude]
    hits = scan_stocks(tickers, exclude=[], top_n=40)

    filtered = []
    for row in hits:
        price = row.get("price") or 0
        change = abs(row.get("change_pct") or 0)
        rvol = row.get("rvol")

        flags = []
        if price < 1:
            flags.append("Sub-$1")
        elif price < 5:
            flags.append("Under $5")
        elif price < 10:
            flags.append("Under $10")

        # Extra scrutiny: skip dead names with no volume participation
        if rvol is not None and rvol < 0.8 and change < 5:
            continue

        row = dict(row)
        row["asset"] = "meme_smallcap"
        row["penny_flags"] = ", ".join(flags) if flags else "Low"
        filtered.append(row)

    filtered.sort(key=lambda x: x.get("scan_rank", 0), reverse=True)
    return filtered[:top_n]
