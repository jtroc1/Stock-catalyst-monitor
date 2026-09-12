"""
Keep-catalyst-alive memory.

Tracks significant catalysts for several sessions so delayed / second-stage
repricing can still be noticed (per trading rule 6).
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional


MEMORY_FILE = Path(__file__).parent.parent / "data" / "catalyst_memory.json"


def _load_memory() -> Dict[str, Any]:
    if not MEMORY_FILE.exists():
        return {"catalysts": {}}
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"catalysts": {}}


def _save_memory(data: Dict[str, Any]):
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def remember_catalyst(symbol: str, catalyst_score: float, summary: str, quality: str, days_to_keep: int = 5):
    """Store a meaningful catalyst so it stays on the radar."""
    if catalyst_score < 2.5 and quality in ("None", "Weak"):
        return  # don't clutter memory with noise

    data = _load_memory()
    catalysts = data.setdefault("catalysts", {})

    entry = {
        "symbol": symbol,
        "score": catalyst_score,
        "quality": quality,
        "summary": summary,
        "first_seen": datetime.utcnow().isoformat(),
        "last_seen": datetime.utcnow().isoformat(),
        "expires": (datetime.utcnow() + timedelta(days=days_to_keep)).isoformat(),
        "hits": 1
    }

    # If already exists, refresh and increment
    if symbol in catalysts:
        existing = catalysts[symbol]
        existing["last_seen"] = datetime.utcnow().isoformat()
        existing["hits"] = existing.get("hits", 1) + 1
        # Keep the higher score / better summary
        if catalyst_score > existing.get("score", 0):
            existing["score"] = catalyst_score
            existing["quality"] = quality
            existing["summary"] = summary
        catalysts[symbol] = existing
    else:
        catalysts[symbol] = entry

    _save_memory(data)


def get_active_catalysts(symbol: str = None) -> List[Dict[str, Any]]:
    """Return still-alive catalysts (optionally filtered by symbol)."""
    data = _load_memory()
    catalysts = data.get("catalysts", {})
    now = datetime.utcnow()

    active = []
    expired_keys = []

    for sym, entry in catalysts.items():
        try:
            expires = datetime.fromisoformat(entry["expires"])
            if expires < now:
                expired_keys.append(sym)
                continue
            if symbol is None or sym == symbol:
                active.append(entry)
        except Exception:
            expired_keys.append(sym)

    # Clean expired
    if expired_keys:
        for k in expired_keys:
            catalysts.pop(k, None)
        _save_memory(data)

    return active


def get_memory_boost(symbol: str) -> Dict[str, Any]:
    """
    Return a small score boost + note if this symbol has an active remembered catalyst.
    """
    active = get_active_catalysts(symbol)
    if not active:
        return {"boost": 0.0, "note": None}

    # Take the strongest remembered one
    best = max(active, key=lambda x: x.get("score", 0))
    boost = min(best.get("score", 0) * 0.25, 1.5)  # modest boost
    note = f"Remembered catalyst still active ({best.get('quality')}): {best.get('summary', '')[:60]}"
    return {"boost": round(boost, 1), "note": note, "original": best}
