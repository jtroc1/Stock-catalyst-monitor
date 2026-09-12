"""
Stock & Catalyst Monitor
Watchlist + market scan + 5-minute charts
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
from catalyst_memory import get_memory_boost, get_active_catalysts
from penny_flags import get_penny_flags
from scanner import run_market_scan, DEFAULT_STOCK_UNIVERSE, scan_meme_smallcaps
from edge_tools import tag_early_or_late, calendar_watch, remember_continuation, get_continuation_list

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
        data=[
            go.Candlestick(
                x=df.index,
                open=df["Open"],
                high=df["High"],
                low=df["Low"],
                close=df["Close"],
                name=symbol
            )
        ]
    )
    fig.update_layout(
        title=f"{symbol} — 5 minute candles",
        xaxis_title="Time",
        yaxis_title="Price",
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
    catalyst_note = catalyst.get("summary")
    catalyst_quality = catalyst.get("quality")

    mem = get_memory_boost(symbol)
    penny = get_penny_flags(symbol, price_data.get("price"), indicators)

    scored = score_setup(
        price_data=price_data,
        indicators=indicators,
        relative_strength=rs,
        catalyst_score=catalyst_score,
        catalyst_note=catalyst_note if catalyst_score >= 2 else None,
        catalyst_quality=catalyst_quality,
        penny_flags=penny,
        memory_boost=mem.get("boost", 0.0),
        memory_note=mem.get("note")
    )

    return {
        **price_data,
        **indicators,
        "relative_strength": rs,
        **scored,
        "catalyst": catalyst,
        "penny": penny,
        "memory": mem
    }


def color_candidate(val):
    colors = {
        "Strong": "background-color: #16a34a; color: white; font-weight: bold",
        "Moderate": "background-color: #ca8a04; color: black; font-weight: bold",
        "Weak": "background-color: #ea580c; color: white",
        "Reject": "background-color: #dc2626; color: white"
    }
    return colors.get(val, "")


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

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("US Market", "🟢 Open" if is_market_open() else "🔴 Closed")
    with col2:
        st.metric("Stocks", len(stocks))
    with col3:
        st.metric("Crypto", len(crypto))
    with col4:
        st.metric("Interval", f"{config['settings'].get('check_interval_minutes', 5)} min")

    st.markdown("---")
    page = st.radio("Page", ["Watchlist", "Market Scan"], horizontal=True, key="page_select")

    if page == "Market Scan":
        st.subheader("Missed-opportunity scan")
        st.caption("Same scoring as the watchlist: RS, RSI, RVOL, catalyst, penny flags, Candidate / Entry.")

        st.markdown("### Calendar first")
        cal_universe = list(dict.fromkeys(stocks + crypto + DEFAULT_STOCK_UNIVERSE[:25]))
        if st.button("Check upcoming catalysts", key="btn_calendar"):
            with st.spinner("Checking calendar..."):
                st.session_state["calendar_hits"] = calendar_watch(cal_universe, days_ahead=10)
        cal_hits = st.session_state.get("calendar_hits")
        if cal_hits:
            st.dataframe(pd.DataFrame(cal_hits), use_container_width=True)

        cont = get_continuation_list()
        if cont:
            st.markdown("### 3-day continuation watch")
            st.caption("Verified catalysts kept alive for delayed / second-session moves.")
            st.dataframe(pd.DataFrame(cont), use_container_width=True)

        b1, b2 = st.columns(2)
        with b1:
            run_main = st.button("Run market scan", type="primary", key="btn_market")
        with b2:
            run_meme = st.button("Run meme / small-cap scan", key="btn_meme")

        def score_hits(hits):
            scored_rows = []
            for hit in hits or []:
                symbol = hit.get("symbol")
                if not symbol:
                    continue
                data = fetch_symbol_data(symbol, benchmark)
                if not data:
                    continue
                data["scan_rank"] = hit.get("scan_rank")
                data["name"] = hit.get("name")
                data["timing"] = tag_early_or_late(data)
                if data.get("catalyst_score", 0) >= 4 or data.get("candidate_rating") in ("Strong", "Moderate"):
                    remember_continuation(
                        data["symbol"],
                        (data.get("catalyst") or {}).get("summary", ""),
                        data.get("catalyst_quality") or data.get("candidate_rating"),
                        float(data.get("catalyst_score") or data.get("score") or 0),
                    )
                scored_rows.append(data)
            return scored_rows

        def hits_table(scored_rows):
            if not scored_rows:
                return pd.DataFrame()
            table = []
            for r in scored_rows:
                table.append({
                    "Symbol": r.get("symbol"),
                    "Price": r.get("price"),
                    "Change %": r.get("change_pct"),
                    "RSI": r.get("rsi", "—"),
                    "RVOL": r.get("rvol", "—"),
                    "Rel Str": r.get("relative_strength", "—"),
                    "Cat": r.get("catalyst_score", 0),
                    "Candidate": r.get("candidate_rating"),
                    "Entry": r.get("entry_rating"),
                    "Score": r.get("score"),
                    "Penny": r.get("penny", {}).get("risk_level", "Low"),
                })
            return pd.DataFrame(table).sort_values("Score", ascending=False)

        if run_main:
            with st.spinner("Scanning and scoring liquid names..."):
                raw = run_market_scan(
                    stock_universe=DEFAULT_STOCK_UNIVERSE,
                    watchlist_stocks=stocks,
                    watchlist_crypto=crypto,
                    stock_top_n=12,
                    crypto_top_n=12,
                )
                st.session_state["scan_stock_scored"] = score_hits(raw.get("stocks"))
                st.session_state["scan_crypto_scored"] = score_hits(raw.get("crypto"))

        if run_meme:
            with st.spinner("Scanning and scoring meme / small-caps..."):
                raw_meme = scan_meme_smallcaps(exclude=stocks)
                st.session_state["meme_scored"] = score_hits(raw_meme)

        stock_scored = st.session_state.get("scan_stock_scored")
        crypto_scored = st.session_state.get("scan_crypto_scored")
        meme_scored = st.session_state.get("meme_scored")

        if not stock_scored and not crypto_scored and not meme_scored:
            st.info("Tap a scan button.")
            return

        if stock_scored:
            st.markdown("### Stocks not on your watchlist")
            st.dataframe(hits_table(stock_scored), use_container_width=True)

        if crypto_scored:
            st.markdown("### Crypto not on your watchlist")
            st.dataframe(hits_table(crypto_scored), use_container_width=True)

        if meme_scored:
            st.markdown("### Meme / small-cap scan")
            st.caption("Same rules, plus extra penny-stock scrutiny.")
            st.dataframe(hits_table(meme_scored), use_container_width=True)

        st.caption("Still a candidate list. Strong + Ready + acceptable risk = trade. Anything less = wait.")
        return

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        view = st.radio(
            "View",
            ["All", "Stocks only", "Crypto only", "Moderate+ only"],
            horizontal=True,
            key="view_select"
        )
    with c2:
        if st.button("🔄 Refresh Data", type="primary", use_container_width=True, key="btn_refresh"):
            st.cache_data.clear()
            st.rerun()
    with c3:
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

    table_data = []
    for r in rows:
        table_data.append({
            "Symbol": r["symbol"],
            "Price": r.get("price"),
            "Change %": r.get("change_pct"),
            "RSI": r.get("rsi", "—"),
            "RVOL": r.get("rvol", "—"),
            "Rel Str": r.get("relative_strength", "—"),
            "Cat": r.get("catalyst_score", 0),
            "Candidate": r.get("candidate_rating"),
            "Entry": r.get("entry_rating"),
            "Score": r.get("score"),
                    "Timing": r.get("timing"),
                    "Penny": r.get("penny", {}).get("risk_level", "Low"),
        })

    df = pd.DataFrame(table_data).sort_values("Score", ascending=False).reset_index(drop=True)

    st.subheader("Watchlist Overview")
    styled = (
        df.style
        .map(color_candidate, subset=["Candidate"])
        .map(color_change, subset=["Change %"])
    )
    st.dataframe(styled, use_container_width=True, height=420)

    strong = len([r for r in rows if r.get("candidate_rating") == "Strong"])
    moderate = len([r for r in rows if r.get("candidate_rating") == "Moderate"])
    weak = len([r for r in rows if r.get("candidate_rating") == "Weak"])
    st.caption(f"Strong: {strong}  •  Moderate: {moderate}  •  Weak: {weak}  •  Total shown: {len(rows)}")

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
            change = last_close - prev_close
            st.caption(f"Last 5m close: {last_close:.4f} ({change:+.4f})")
            st.plotly_chart(draw_candle_chart(selected, candle_df), use_container_width=True)

    if show_details and rows:
        st.markdown("---")
        st.subheader("Detailed View")
        for r in sorted(rows, key=lambda x: x.get("score", 0), reverse=True):
            rating = r.get("candidate_rating", "—")
            color = {"Strong": "🟢", "Moderate": "🟡", "Weak": "🟠", "Reject": "🔴"}.get(rating, "⚪")
            with st.expander(f"{color} **{r['symbol']}** — {rating} / {r.get('entry_rating')}  (Score {r.get('score')})"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Price", f"{r.get('price')}")
                    st.write(f"Change: **{r.get('change_pct', 0):+.2f}%**")
                with c2:
                    st.write(f"RSI: {r.get('rsi', '—')}")
                    st.write(f"RVOL: {r.get('rvol', '—')}")
                    st.write(f"Rel Strength: {r.get('relative_strength', '—')}")
                with c3:
                    st.write(f"Catalyst: **{r.get('catalyst_score', 0)}** ({r.get('catalyst_quality', 'None')})")
                    st.write(f"Penny risk: **{r.get('penny', {}).get('risk_level', 'Low')}**")
                reasons = r.get("reasons", [])
                if reasons:
                    st.markdown("**Key reasons:**")
                    for reason in reasons:
                        st.write(f"• {reason}")

    with st.sidebar:
        st.header("Watchlist")
        st.write("**Stocks**")
        for s in stocks:
            st.write(f"• {s}")
        st.write("**Crypto**")
        for c in crypto:
            st.write(f"• {c}")
        st.caption(f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")


main()
