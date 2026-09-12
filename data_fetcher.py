"""
Data fetching for stocks and crypto using yfinance.
Also provides basic technical indicators and relative strength.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pytz


def get_current_price(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch latest price and basic info for a symbol."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        
        price = getattr(info, "last_price", None) or getattr(info, "lastPrice", None)
        prev_close = getattr(info, "previous_close", None) or getattr(info, "previousClose", None)
        
        if price is None:
            hist = ticker.history(period="2d")
            if hist.empty:
                return None
            price = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price

        change = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        return {
            "symbol": symbol,
            "price": round(float(price), 4 if price < 10 else 2),
            "prev_close": round(float(prev_close), 4 if prev_close < 10 else 2) if prev_close else None,
            "change": round(change, 4),
            "change_pct": round(change_pct, 2),
            "timestamp": datetime.now(pytz.UTC).isoformat()
        }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None


def get_history(symbol: str, period: str = "3mo", interval: str = "1d") -> Optional[pd.DataFrame]:
    """Get historical OHLCV data."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return None
        return df
    except Exception as e:
        print(f"History error {symbol}: {e}")
        return None


def _rsi(series: pd.Series, length: int = 14) -> float:
    """Simple RSI calculation without pandas_ta."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=length).mean()
    avg_loss = loss.rolling(window=length).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not rsi.empty else None


def calculate_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate common technical indicators using pure pandas."""
    if df is None or len(df) < 20:
        return {}

    try:
        close = df["Close"]
        
        current_rsi = _rsi(close, 14)

        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        sma200 = close.rolling(200).mean() if len(df) >= 200 else None

        current_sma20 = float(sma20.iloc[-1]) if not sma20.empty else None
        current_sma50 = float(sma50.iloc[-1]) if not sma50.empty else None
        current_sma200 = float(sma200.iloc[-1]) if sma200 is not None and not sma200.empty else None

        avg_volume = float(df["Volume"].tail(20).mean()) if "Volume" in df else None
        current_volume = float(df["Volume"].iloc[-1]) if "Volume" in df else None
        rvol = (current_volume / avg_volume) if avg_volume and current_volume else None

        price = float(close.iloc[-1])
        above_sma20 = price > current_sma20 if current_sma20 else None
        above_sma50 = price > current_sma50 if current_sma50 else None

        return {
            "rsi": round(current_rsi, 1) if current_rsi else None,
            "sma20": round(current_sma20, 2) if current_sma20 else None,
            "sma50": round(current_sma50, 2) if current_sma50 else None,
            "sma200": round(current_sma200, 2) if current_sma200 else None,
            "rvol": round(rvol, 2) if rvol else None,
            "above_sma20": above_sma20,
            "above_sma50": above_sma50,
            "price": round(price, 2)
        }
    except Exception as e:
        print(f"Indicator calculation error: {e}")
        return {}


def get_relative_strength(symbol: str, benchmark: str = "QQQ", period: str = "1mo") -> Optional[float]:
    """Calculate relative strength vs benchmark (simple % outperformance)."""
    try:
        stock_hist = get_history(symbol, period=period)
        bench_hist = get_history(benchmark, period=period)
        
        if stock_hist is None or bench_hist is None or len(stock_hist) < 5 or len(bench_hist) < 5:
            return None

        stock_ret = (stock_hist["Close"].iloc[-1] / stock_hist["Close"].iloc[0] - 1) * 100
        bench_ret = (bench_hist["Close"].iloc[-1] / bench_hist["Close"].iloc[0] - 1) * 100
        
        return round(stock_ret - bench_ret, 2)
    except Exception:
        return None


def is_market_open() -> bool:
    """Simple US market hours check (9:30–16:00 ET, Mon–Fri)."""
    et = pytz.timezone("US/Eastern")
    now = datetime.now(et)
    
    if now.weekday() >= 5:
        return False
    
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    return market_open <= now <= market_close
