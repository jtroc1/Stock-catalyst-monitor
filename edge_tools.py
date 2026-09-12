import json
from datetime import datetime, timedelta
from pathlib import Path

from catalysts import get_earnings_info, analyze_catalysts

MEMORY_FILE = Path(__file__).parent / "continuation_memory.json"


def tag_early_or_late(row):
    change = abs(float(row.get("change_pct") or 0))
    rsi = row.get("rsi")
    rvol = row.get("rvol")
    cat = float(row.get("catalyst_score") or 0)
    candidate = row.get("candidate_rating")

    if change >= 8 and (rsi is None or rsi >= 70):
        return "Late"
    if change >= 12:
        return "Late"
    if 1.5 <= change <= 7.5 and (rvol is None or rvol >= 1.15) and (rsi is None or rsi < 68):
        if candidate in ("Strong", "Moderate") or cat >= 2:
            return "Early"
        return "Watch"
    if cat >= 3 and change < 8:
        return "Early"
    return "Watch"


def calendar_watch(symbols, days_ahead=10):
    hits = []
    for symbol in symbols:
        try:
            earnings = get_earnings_info(symbol)
            cat = analyze_catalysts(symbol)
            if earnings and earnings.get("days_until") is not None:
                days = earnings["days_until"]
                if 0 <= days <= days_ahead:
                    hits.append({
                        "symbol": symbol,
                        "type": "Earnings",
                        "when": earnings.get("earnings_date"),
                        "days_until": days,
                        "catalyst_score": cat.get("catalyst_score", 0),
                        "quality": cat.get("quality"),
                        "summary": cat.get("summary"),
                    })
            elif cat.get("catalyst_score", 0) >= 4.5:
                hits.append({
                    "symbol": symbol,
                    "type": "News/catalyst",
                    "when": "now",
                    "days_until": 0,
                    "catalyst_score": cat.get("catalyst_score", 0),
                    "quality": cat.get("quality"),
                    "summary": cat.get("summary"),
                })
        except Exception:
            continue
    hits.sort(key=lambda x: (x.get("days_until", 99), -float(x.get("catalyst_score") or 0)))
    return hits


def _load_cont():
    if not MEMORY_FILE.exists():
        return {}
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cont(data):
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception:
        pass


def remember_continuation(symbol, summary, quality, score, days=3):
    if score < 4.0 and quality not in ("Moderate", "Strong"):
        return
    data = _load_cont()
    data[symbol] = {
        "symbol": symbol,
        "summary": summary,
        "quality": quality,
        "score": score,
        "first_seen": data.get(symbol, {}).get("first_seen") or datetime.utcnow().isoformat(),
        "last_seen": datetime.utcnow().isoformat(),
        "expires": (datetime.utcnow() + timedelta(days=days)).isoformat(),
    }
    _save_cont(data)


def get_continuation_list():
    data = _load_cont()
    now = datetime.utcnow()
    alive = []
    expired = []
    for sym, row in data.items():
        try:
            if datetime.fromisoformat(row["expires"]) < now:
                expired.append(sym)
            else:
                alive.append(row)
        except Exception:
            expired.append(sym)
    if expired:
        for sym in expired:
            data.pop(sym, None)
        _save_cont(data)
    alive.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
