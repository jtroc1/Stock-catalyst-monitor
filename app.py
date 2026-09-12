"""
Visual dashboard for Stock & Catalyst Monitor.
Deployable to Streamlit Community Cloud.
"""

import streamlit as st
import yaml
import pandas as pd
from pathlib import Path
import sys
from datetime import datetime

sys.path.append(str(Path(__file__).parent))

from utils.data_fetcher import (
    get_current_price, get_history, calculate_indicators,
    get_relative_strength, is_market_open
)
from utils.scoring import score_setup
from utils.catalysts import analyze_catalysts
from utils.catalyst_memory import get_memory_boost, get_active_catalysts
from utils.penny_flags import get_penny_flags

st.set_page_config(
    page_title="Stock & Catalyst Monitor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


@st.cache_data(ttl=120)
def load_config():
    with open(CONFIG_PATH, "r") as f:
        cfg = yaml.safe_load(f)
    # Prefer Streamlit secrets for webhook if available
    try:
        if "discord" in st.secrets and "webhook_url" in st.secrets["discord"]:
            cfg["discord"]["webhook_url"] = st.secrets["discord"]["webhook_url"]
    except Exception:
        pass
    return cfg


def fetch_symbol_data(symbol: str, benchmark: str = "QQQ"):
    price_data = get_current_price(symbol)
    if not price_data:
        return None

    hist = get_history(symbol, period="3mo")
    indicators = calculate_indicators(hist) if hist is not None else {}

    rs_benchmark = "BTC-USD" if symbol.endswith("-USD") else benchmark
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
        elif v < 0:
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
        market_status = "🟢 Open" if is_market_open() else "🔴 Closed"
        st.metric("US Market", market_status)
    with col2:
        st.metric("Stocks", len(stocks))
    with col3:
        st.metric("Crypto", len(crypto))
    with col4:
        st.metric("Interval", f"{config['settings'].get('check_interval_minutes', 5)} min")

    st.markdown("---")

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        view = st.radio("View", ["All", "Stocks only", "Crypto only", "Moderate+ only"], horizontal=True)
    with c2:
        if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    with c3:
        show_details = st.checkbox("Show details", value=False)

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
        st.warning("No data returned right now. Try refreshing in a minute (data source can rate-limit).")
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
            "Penny": r.get("penny", {}).get("risk_level", "Low")
        })

    df = pd.DataFrame(table_data)
    df = df.sort_values("Score", ascending=False).reset_index(drop=True)

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

    if show_details and rows:
        st.markdown("---")
        st.subheader("Detailed View")
        sorted_rows = sorted(rows, key=lambda x: x.get("score", 0), reverse=True)

        for r in sorted_rows:
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

                cat = r.get("catalyst", {})
                if cat.get("summary") and cat.get("catalyst_score", 0) >= 1.5:
                    st.info(f"Catalyst: {cat['summary']}")

                mem = r.get("memory", {})
                if mem.get("note"):
                    st.caption(f"🧠 {mem['note']}")

    with st.sidebar:
        st.header("Watchlist")
        st.write("**Stocks**")
        for s in stocks:
            st.write(f"• {s}")
        st.write("**Crypto**")
        for c in crypto:
            st.write(f"• {c}")

        st.markdown("---")
        st.caption("Edit config.yaml in the GitHub repo to change tickers.")
        st.caption(f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")

        active = get_active_catalysts()
        if active:
            st.markdown("---")
            st.subheader("🧠 Active Catalyst Memory")
            for a in active[:6]:
                st.caption(f"**{a['symbol']}** ({a.get('quality')}) — {a.get('summary', '')[:50]}")


if __name__ == "__main__":
    main()
