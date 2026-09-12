"""
Penny stock & low-quality name extra scrutiny.
Aligned with trading rule 18.
"""

from typing import Dict, Any, List, Optional


def get_penny_flags(symbol: str, price: float, indicators: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Return extra scrutiny flags for low-priced or potentially risky names.
    """
    flags = []
    risk_score = 0.0  # higher = more caution

    # Price-based
    if price is not None:
        if price < 1.0:
            flags.append("Sub-$1 price — extreme penny risk")
            risk_score += 3.0
        elif price < 5.0:
            flags.append("Under $5 — elevated penny scrutiny")
            risk_score += 1.5
        elif price < 10.0:
            flags.append("Under $10 — extra due diligence advised")
            risk_score += 0.7

    # Volume / liquidity proxy
    rvol = indicators.get("rvol") if indicators else None
    # We don't have dollar volume easily, but very low absolute volume is a red flag
    # (handled lightly here)

    # Name-based heuristics (common dilution / microcap patterns)
    symbol_upper = symbol.upper().replace("-USD", "")
    risky_suffixes = []  # can expand later

    # Simple risk rating
    if risk_score >= 3.0:
        risk_level = "High"
    elif risk_score >= 1.5:
        risk_level = "Elevated"
    elif risk_score >= 0.5:
        risk_level = "Moderate"
    else:
        risk_level = "Low"

    return {
        "flags": flags,
        "risk_score": round(risk_score, 1),
        "risk_level": risk_level,
        "is_penny_or_micro": price is not None and price < 5.0
    }
