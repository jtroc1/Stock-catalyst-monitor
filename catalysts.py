"""
Catalyst monitoring module — improved version.

Covers:
- Upcoming & recent earnings
- Recent news headlines with better impact scoring
- Keyword-based impact scoring (0–10)
- Quality rating of catalyst

Aligned with trading rules:
- Check the calendar first
- Verify the catalyst
- Keep catalysts alive for several sessions
- Prefer higher-quality signals
"""

import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any


# High-impact event keywords
HIGH_IMPACT_KEYWORDS = [
    "earnings", "beats", "misses", "guidance", "raises guidance", "cuts guidance",
    "fda", "approval", "approved", "rejected", "phase 3", "phase iii", "clinical", "trial results",
    "acquisition", "acquire", "acquired", "merger", "buyout", "takeover",
    "contract", "award", "awarded", "deal worth", "partnership", "agreement",
    "upgrade", "downgrade", "initiates coverage", "price target raised", "price target cut",
    "insider buying", "insider sold", "form 4",
    "offering", "dilution", "atm offering", "secondary offering", "warrant exercise",
    "bankruptcy", "going concern", "delisting", "chapter 11",
    "sec investigation", "doj", "lawsuit", "settlement", "class action"
]

MEDIUM_IMPACT_KEYWORDS = [
    "launch", "product launch", "expands", "expansion", "opens new",
    "revenue", "profit", "net loss", "forecast", "outlook",
    "analyst", "rating", "reiterates", "maintains",
    "shareholder", "buyback", "dividend increase",
    "ceo", "cfo", "appoints", "resigns", "steps down",
    "crypto", "etf", "approval expected", "sec filing"
]

# Extra weight for very strong phrases
BOOST_PHRASES = [
    "beats estimates", "beats expectations", "raises full-year", "cuts full-year",
    "fda approval", "fda clears", "phase 3 success", "positive data",
    "definitive agreement", "all-cash deal", "premium to", 
    "significant insider buying", "cluster buying"
]


def get_earnings_info(symbol: str) -> Optional[Dict[str, Any]]:
    """Get next earnings date and related info."""
    try:
        # Skip pure crypto (no traditional earnings)
        if symbol.endswith("-USD") and symbol not in ("BTC-USD", "ETH-USD"):  # still try majors sometimes
            # Most altcoins have no meaningful earnings calendar
            pass

        ticker = yf.Ticker(symbol)
        cal = ticker.calendar

        if cal is None or (hasattr(cal, "empty") and cal.empty):
            return None

        earnings_date = None
        if isinstance(cal, dict):
            earnings_date = cal.get("Earnings Date")
            if isinstance(earnings_date, list) and earnings_date:
                earnings_date = earnings_date[0]
        elif hasattr(cal, "get"):
            earnings_date = cal.get("Earnings Date")

        if earnings_date is None:
            return None

        if hasattr(earnings_date, "date"):
            earnings_date = earnings_date.date()
        elif isinstance(earnings_date, str):
            try:
                earnings_date = datetime.strptime(earnings_date[:10], "%Y-%m-%d").date()
            except Exception:
                return None

        today = datetime.utcnow().date()
        days_until = (earnings_date - today).days

        return {
            "symbol": symbol,
            "earnings_date": str(earnings_date),
            "days_until": days_until,
            "is_upcoming": 0 <= days_until <= 21,
            "is_very_soon": 0 <= days_until <= 5,
            "is_recent": -7 <= days_until < 0,
            "is_this_week": 0 <= days_until <= 7
        }
    except Exception:
        return None


def get_recent_news(symbol: str, max_items: int = 8) -> List[Dict[str, Any]]:
    """Fetch recent news headlines."""
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news or []

        results = []
        for item in news[:max_items]:
            title = (
                item.get("title")
                or item.get("content", {}).get("title")
                or ""
            )
            publisher = (
                item.get("publisher")
                or item.get("content", {}).get("provider", {}).get("displayName")
                or "Unknown"
            )
            link = (
                item.get("link")
                or item.get("content", {}).get("canonicalUrl", {}).get("url")
                or ""
            )

            ts = item.get("providerPublishTime") or item.get("content", {}).get("pubDate")
            published = None
            if ts:
                try:
                    if isinstance(ts, (int, float)):
                        published = datetime.utcfromtimestamp(ts).isoformat()
                    else:
                        published = str(ts)
                except Exception:
                    published = str(ts)

            if title:
                results.append({
                    "title": title.strip(),
                    "publisher": publisher,
                    "link": link,
                    "published": published
                })
        return results
    except Exception:
        return []


def score_news_item(title: str) -> float:
    """Improved keyword + phrase based impact score (0–10)."""
    if not title:
        return 0.0

    title_lower = title.lower()
    score = 0.8  # baseline for any real headline

    for kw in HIGH_IMPACT_KEYWORDS:
        if kw in title_lower:
            score += 2.2

    for kw in MEDIUM_IMPACT_KEYWORDS:
        if kw in title_lower:
            score += 1.0

    for phrase in BOOST_PHRASES:
        if phrase in title_lower:
            score += 1.8

    # Small penalty for very generic titles
    if len(title) < 25:
        score *= 0.7

    return round(min(score, 10.0), 1)


def analyze_catalysts(symbol: str) -> Dict[str, Any]:
    """
    Analyze catalysts for a symbol.
    Returns structured report with overall score and human-readable notes.
    """
    earnings = get_earnings_info(symbol)
    news_items = get_recent_news(symbol, max_items=8)

    scored_news = []
    max_news_score = 0.0
    top_headline = None

    for item in news_items:
        s = score_news_item(item["title"])
        scored_news.append({**item, "impact_score": s})
        if s > max_news_score:
            max_news_score = s
            top_headline = item["title"]

    catalyst_score = 0.0
    notes = []

    # Earnings contribution (calendar first — per your rules)
    if earnings:
        if earnings.get("is_very_soon"):
            catalyst_score += 4.5
            notes.append(f"Earnings in {earnings['days_until']} day(s) ({earnings['earnings_date']})")
        elif earnings.get("is_this_week"):
            catalyst_score += 3.2
            notes.append(f"Earnings this week ({earnings['earnings_date']})")
        elif earnings.get("is_upcoming"):
            catalyst_score += 2.0
            notes.append(f"Earnings in {earnings['days_until']} days ({earnings['earnings_date']})")
        elif earnings.get("is_recent"):
            catalyst_score += 1.8
            notes.append(f"Recent earnings ({earnings['earnings_date']}) — still in post-event window")

    # News contribution
    if max_news_score >= 7:
        catalyst_score += 3.8
        notes.append(f"High-impact news: {top_headline[:85]}")
    elif max_news_score >= 4.5:
        catalyst_score += 2.3
        notes.append(f"Notable news: {top_headline[:85]}" if top_headline else "Notable news")
    elif max_news_score >= 2.5:
        catalyst_score += 1.0
        if top_headline:
            notes.append(f"News: {top_headline[:70]}")

    catalyst_score = min(round(catalyst_score, 1), 10.0)

    if catalyst_score >= 7.0:
        quality = "Strong"
    elif catalyst_score >= 4.5:
        quality = "Moderate"
    elif catalyst_score >= 2.0:
        quality = "Weak"
    else:
        quality = "None"

    return {
        "symbol": symbol,
        "catalyst_score": catalyst_score,
        "quality": quality,
        "notes": notes,
        "earnings": earnings,
        "top_news": scored_news[:4],
        "summary": " | ".join(notes) if notes else "No significant catalysts detected"
    }
