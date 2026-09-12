"""
Stock & Catalyst Monitor — full app
Watchlist, market scan, meme scan, calendar, early/late, continuation, 5m charts
"""

import streamlit as st
import yaml
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from pathlib import Path
import sys
from datetime import datetime

sys.path.append(str(Path(__file__).parent))

from data_fetcher import (
    get_current_price, get_history, calculate_indicators,
    get_relative_strength, is_market_open
)
from scoring import score_setup
from catalysts import analyze_catalysts
from catalyst_memory import get_memory_boost
from penny_flags import get_penny_flags
from scanner import run_market_scan, DEFAULT_STOCK_UNIVERSE, scan_meme_smallcaps
from edge_tools import (
    tag_early_or_late, calendar_watch,
    remember_continuation, get_continuation_list
)

st.set_page_config(
    page_title="Stock & Catalyst Monitor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

CONFIG_PATH = Path(__file__).parent / "config.yaml"


@st.cache_data(ttl=120)
def load_config():
    with open(CONFIG_PATH, "r") as f:
        cfg = yaml.safe_load(f)
    try:
        if "discord" in st.secrets and "webhook_url" in st.secrets["discord"]:
            cfg["discord"]["webhook_url"] = st.secrets["discord"]["webhook_url"]
    except Exception:
        pass
    return cfg


@st.cache_data(ttl=60)
def get_five_min_candles(symbol: str):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d", interval="5m")
        if df is None or df.empty:
            df = ticker.history(period="1d", interval="5m")
        if df is None or df.empty:
            return None
        return df.tail(120)
    except Exception:
        return None


def draw_candle_chart(symbol: str, df: pd.DataFrame):
    fig = go.Figure(
        data=[go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name=symbol
        )]
    )
    fig.update_layout(
        title=f"{symbol} — 5 minute candles",
        xaxis_rangeslider_visible=False,
        height=420,
        margin=dict(l=10, r=10, t=40, b=10),
        template="plotly_dark"
    )
    return fig


def fetch_symbol_data(symbol: str, benchmark: str = "QQQ"):
    price_data = get_current_price(symbol)
    if not price_data:
        return None
    hist = get_history(symbol, period="3mo")
    indicators = calculate_indicators(hist) if hist is not None else {}
    rs_benchmark = "BTC-USD" if str(symbol).endswith("-USD") else benchmark
    rs = get_relative_strength(symbol, benchmark=rs_benchmark)
    catalyst = analyze_catalysts(symbol)
    catalyst_score = catalyst.get("catalyst_score", 0.0)
    mem = get_memory_boost(symbol)
    penny = get_penny_flags(symbol, price_data.get("price"), indicators)
    scored = score_setup(
        price_data=price_data,
        indicators=indicators,
        relative_strength=rs,
        catalyst_score=catalyst_score,
        catalyst_note=catalyst.get("summary") if catalyst_score >= 2 else None,
        catalyst_quality=catalyst.get("quality"),
        penny_flags=penny,
        memory_boost=mem.get("boost", 0.0),
        memory_note=mem.get("note")
    )
    out = {**price_data, **indicators, "relative_strength": rs, **scored,
           "catalyst": catalyst, "penny": penny, "memory": mem}
    out["timing"] = tag_early_or_late(out)
    return out


def scored_table(rows):
    table = []
    for r in rows:
        table.append({
            "Symbol": r.get("symbol"),
            "Price": r.get("price"),
            "Change %": r.get("change_pct"),
            "RSI": r.get("rsi", "—"),
            "RVOL": r.get("rvol", "—"),
            "Rel Str": r.get("relative_strength", "—"),
            "Cat": r.get("catalyst_score", 0),
            "Timing": r.get("timing"),
            "Candidate": r.get("candidate_rating"),
            "Entry": r.get("entry_rating"),
            "Score": r.get("score"),
            "Penny": (r.get("penny") or {}).get("risk_level", "Low"),
        })
    if not table:
        return pd.DataFrame()
    return pd.DataFrame(table).sort_values("Score", ascending=False)


def score_hits(hits, benchmark):
    scored_rows = []
    for hit in hits or []:
        symbol = hit.get("symbol")
        if not symbol:
            continue
        data = fetch_symbol_data(symbol, benchmark)
        if not data:
            continue
        if data.get("catalyst_score", 0) >= 4 or data.get("candidate_rating") in ("Strong", "Moderate"):
            remember_continuation(
                data["symbol"],
                (data.get("catalyst") or {}).get("summary", ""),
                data.get("catalyst_quality") or data.get("candidate_rating"),
                float(data.get("catalyst_score") or data.get("score") or 0),
            )
        scored_rows.append(data)
    return scored_rows


def color_candidate(val):
    return {
        "Strong": "background-color: #16a34a; color: white; font-weight: bold",
        "Moderate": "background-color: #ca8a04; color: black; font-weight: bold",
        "Weak": "background-color: #ea580c; color: white",
        "Reject": "background-color: #dc2626; color: white",
        "Early": "background-color: #16a34a; color: white",
        "Late": "background-color: #dc2626; color: white",
        "Watch": "background-color: #ca8a04; color: black",
    }.get(val, "")


def color_change(val):
    try:
        v = float(val)
        if v > 0:
            return "color: #16a34a; font-weight: 600"
        if v < 0:
            return "color: #dc2626; font-weight: 600"
    except Exception:
        pass
    return ""


def main():
    config = load_config()
    stocks = config["watchlist"].get("stocks", [])
    crypto = config["watchlist"].get("crypto", [])
    all_symbols = stocks + crypto
    benchmark = config["settings"].get("relative_strength_benchmark", "QQQ")

    st.title("📈 Stock & Catalyst Monitor")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("US Market", "🟢 Open" if is_market_open() else "🔴 Closed")
    c2.metric("Stocks", len(stocks))
    c3.metric("Crypto", len(crypto))
    c4.metric("Interval", f"{config['settings'].get('check_interval_minutes', 5)} min")

    st.markdown("---")
    page = st.radio("Page", ["Watchlist", "Market Scan"], horizontal=True, key="page_select")

    if page == "Market Scan":
        st.subheader("Missed-opportunity scan")
        st.caption("Same scoring as the watchlist. Broad scan, not every ticker on earth.")

        st.markdown("### Calendar first")
        cal_universe = list(dict.fromkeys(stocks + crypto + DEFAULT_STOCK_UNIVERSE[:25]))
        if st.button("Check upcoming catalysts", key="btn_calendar"):
            with st.spinner("Checking calendar..."):
                st.session_state["calendar_hits"] = calendar_watch(cal_universe, days_ahead=60)
        cal_hits = st.session_state.get("calendar_hits")
        if cal_hits:
            st.dataframe(pd.DataFrame(cal_hits), use_container_width=True)
        elif cal_hits is not None:
            st.caption("No upcoming catalysts found in the next 60 days.")

        cont = get_continuation_list()
        if cont:
            st.markdown("### 3-day continuation watch")
            st.dataframe(pd.DataFrame(cont), use_container_width=True)

        b1, b2 = st.columns(2)
        with b1:
            run_main = st.button("Run market scan", type="primary", key="btn_market")
        with b2:
            run_meme = st.button("Run meme / small-cap scan", key="btn_meme")

        if run_main:
            with st.spinner("Scanning and scoring liquid names..."):
                raw = run_market_scan(
                    stock_universe=DEFAULT_STOCK_UNIVERSE,
                    watchlist_stocks=stocks,
                    watchlist_crypto=crypto,
                    stock_top_n=12,
                    crypto_top_n=12,
                )
                st.session_state["scan_stock_scored"] = score_hits(raw.get("stocks"), benchmark)
                st.session_state["scan_crypto_scored"] = score_hits(raw.get("crypto"), benchmark)
        if run_meme:
            with st.spinner("Scanning and scoring meme / small-caps..."):
                st.session_state["meme_scored"] = score_hits(
                    scan_meme_smallcaps(exclude=stocks), benchmark
                )

        stock_scored = st.session_state.get("scan_stock_scored")
        crypto_scored = st.session_state.get("scan_crypto_scored")
        meme_scored = st.session_state.get("meme_scored")

        if not stock_scored and not crypto_scored and not meme_scored:
            st.info("Tap a scan button.")
            return

        if stock_scored:
            st.markdown("### Stocks not on your watchlist")
            st.dataframe(scored_table(stock_scored), use_container_width=True)
        if crypto_scored:
            st.markdown("### Crypto not on your watchlist")
            st.dataframe(scored_table(crypto_scored), use_container_width=True)
        if meme_scored:
            st.markdown("### Meme / small-cap scan")
            st.dataframe(scored_table(meme_scored), use_container_width=True)

        st.caption("Early + Moderate/Strong = investigate. Late + vertical candle = pass.")
        return

    v1, v2, v3 = st.columns([2, 1, 1])
    with v1:
        view = st.radio(
            "View",
            ["All", "Stocks only", "Crypto only", "Moderate+ only"],
            horizontal=True,
            key="view_select"
        )
    with v2:
        if st.button("🔄 Refresh Data", type="primary", use_container_width=True, key="btn_refresh"):
            st.cache_data.clear()
            st.rerun()
    with v3:
        show_details = st.checkbox("Show details", value=False, key="chk_details")

    if view == "Stocks only":
        symbols_to_load = stocks
    elif view == "Crypto only":
        symbols_to_load = crypto
    else:
        symbols_to_load = all_symbols

    rows = []
    progress = st.progress(0)
    status = st.empty()
    for i, symbol in enumerate(symbols_to_load):
        status.text(f"Loading {symbol}...")
        progress.progress((i + 1) / max(len(symbols_to_load), 1))
        data = fetch_symbol_data(symbol, benchmark)
        if data:
            rows.append(data)
    progress.empty()
    status.empty()

    if not rows:
        st.warning("No data returned right now. Try refreshing in a minute.")
        return

    if view == "Moderate+ only":
        rows = [r for r in rows if r.get("candidate_rating") in ("Strong", "Moderate")]

    df = scored_table(rows)
    st.subheader("Watchlist Overview")
    styled = df.style.map(color_candidate, subset=["Candidate"]).map(color_change, subset=["Change %"])
    if "Timing" in df.columns:
        styled = styled.map(color_candidate, subset=["Timing"])
    st.dataframe(styled, use_container_width=True, height=420)

    st.markdown("---")
    st.subheader("5-minute chart")
    selected = st.selectbox("Choose a stock or crypto", df["Symbol"].tolist(), key="chart_select")
    if selected:
        candle_df = get_five_min_candles(selected)
        if candle_df is None or candle_df.empty:
            st.info(f"No 5-minute data available for {selected} right now.")
        else:
            last_close = float(candle_df["Close"].iloc[-1])
            prev_close = float(candle_df["Close"].iloc[-2]) if len(candle_df) > 1 else last_close
            st.caption(f"Last 5m close: {last_close:.4f} ({last_close-prev_close:+.4f})")
            st.plotly_chart(draw_candle_chart(selected, candle_df), use_container_width=True)

    if show_details:
        st.markdown("---")
        st.subheader("Detailed View")
        for r in sorted(rows, key=lambda x: x.get("score", 0), reverse=True):
            rating = r.get("candidate_rating", "—")
            mark = {"Strong": "🟢", "Moderate": "🟡", "Weak": "🟠", "Reject": "🔴"}.get(rating, "⚪")
            with st.expander(f"{mark} **{r['symbol']}** — {rating} / {r.get('entry_rating')} ({r.get('score')}) {r.get('timing')}"):
                st.write(f"Price {r.get('price')}  |  Change {r.get('change_pct', 0):+.2f}%")
                st.write(f"RSI {r.get('rsi')}  |  RVOL {r.get('rvol')}  |  RS {r.get('relative_strength')}")
                for reason in r.get("reasons") or []:
                    st.write(f"• {reason}")

    with st.sidebar:
        st.header("Watchlist")
        for s in stocks:
            st.write(f"• {s}")
        for c in crypto:
            st.write(f"• {c}")


main()
