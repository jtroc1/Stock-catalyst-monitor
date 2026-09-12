from datetime import datetime
import pytz
import yfinance as yf

from discord_alerts import send_price_alert, send_discord_message, can_alert
from alt_sources import combine_calendar


def _webhook():
    try:
        import streamlit as st
        return st.secrets.get("discord", {}).get("webhook_url", "")
    except Exception:
        return ""


def is_quality_setup(row):
    if row.get("timing") != "Early":
        return False
    if row.get("candidate_rating") not in ("Strong", "Moderate"):
        return False
    if row.get("entry_rating") in ("Poor", "Invalid"):
        return False
    return True


def maybe_alert(row):
    webhook = _webhook()
    if not webhook or not is_quality_setup(row):
        return False
    symbol = row.get("symbol")
    if not can_alert(symbol, cooldown_minutes=45):
        return False
    reasons = list(row.get("reasons") or [])
    reasons.insert(0, f"Timing: {row.get('timing')}")
    return send_price_alert(
        webhook_url=webhook,
        symbol=symbol,
        price=float(row.get("price") or 0),
        change_pct=float(row.get("change_pct") or 0),
        rating=f"{row.get('candidate_rating')} | {row.get('entry_rating')} | {row.get('timing')}",
        reasons=reasons,
        catalyst_note=(row.get("catalyst") or {}).get("summary"),
        cooldown_minutes=45,
    )


def build_morning_brief(watchlist_stocks=None):
    oslo = pytz.timezone("Europe/Oslo")
    now = datetime.now(oslo)
    lines = [f"Norway morning brief — {now.strftime('%Y-%m-%d %H:%M')} Oslo"]
    for sym in ["BTC-USD", "ETH-USD", "QQQ", "ES=F"]:
        try:
            h = yf.Ticker(sym).history(period="2d")
            if h is None or h.empty:
                continue
            last = float(h["Close"].iloc[-1])
            prev = float(h["Close"].iloc[-2]) if len(h) > 1 else last
            chg = (last / prev - 1) * 100 if prev else 0
            lines.append(f"{sym}: {last:.2f} ({chg:+.2f}%)")
        except Exception:
            continue
    today = now.date().isoformat()
    cal = combine_calendar(watchlist_stocks or [], days_ahead=2)
    today_rows = [r for r in cal if str(r.get("when")) == today]
    if today_rows:
        names = ", ".join(sorted({r.get("symbol") for r in today_rows if r.get("symbol")})[:12])
        lines.append(f"Reporting today: {names}")
    else:
        lines.append("No Finnhub earnings dated today in the widened calendar.")
    lines.append("Rule: Early + Moderate/Strong + acceptable risk = look. Late = pass.")
    return "\n".join(lines)


def send_morning_brief(watchlist_stocks=None):
    webhook = _webhook()
    if not webhook:
        return False
    return send_discord_message(webhook, content=build_morning_brief(watchlist_stocks))
