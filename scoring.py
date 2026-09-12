"""
Scoring & Rating engine aligned with the user's trading rules.

Produces:
- Candidate rating: Strong / Moderate / Weak / Reject
- Entry rating: Ready / Near / Poor / Invalid
"""

from typing import Dict, Any, List, Optional


def score_setup(
    price_data: Dict[str, Any],
    indicators: Dict[str, Any],
    relative_strength: float = None,
    catalyst_score: float = 0.0,
    catalyst_note: str = None,
    catalyst_quality: str = None,
    penny_flags: Dict[str, Any] = None,
    memory_boost: float = 0.0,
    memory_note: str = None
) -> Dict[str, Any]:
    """
    Score a setup based on multiple factors.
    Returns ratings + reasons.
    """
    score = 0.0
    reasons = []
    max_score = 10.0

    price = price_data.get("price")
    change_pct = price_data.get("change_pct", 0)

    # --- 1. Relative Strength ---
    if relative_strength is not None:
        if relative_strength > 5:
            score += 2.0
            reasons.append(f"Strong relative strength (+{relative_strength}%)")
        elif relative_strength > 0:
            score += 1.0
            reasons.append(f"Positive relative strength (+{relative_strength}%)")
        elif relative_strength < -5:
            score -= 1.5
            reasons.append(f"Weak relative strength ({relative_strength}%)")

    # --- 2. RSI ---
    rsi = indicators.get("rsi")
    if rsi is not None:
        if 30 <= rsi <= 45:
            score += 1.5
            reasons.append(f"RSI constructive ({rsi})")
        elif rsi < 30:
            score += 1.0
            reasons.append(f"RSI oversold ({rsi})")
        elif rsi > 70:
            score -= 0.5
            reasons.append(f"RSI overbought ({rsi})")

    # --- 3. Moving averages ---
    if indicators.get("above_sma20"):
        score += 0.8
        reasons.append("Above 20-SMA")
    if indicators.get("above_sma50"):
        score += 1.0
        reasons.append("Above 50-SMA")

    # --- 4. Volume ---
    rvol = indicators.get("rvol")
    if rvol is not None:
        if rvol >= 1.5:
            score += 1.5
            reasons.append(f"Elevated volume (RVOL {rvol}x)")
        elif rvol >= 1.1:
            score += 0.7
            reasons.append(f"Above-avg volume (RVOL {rvol}x)")

    # --- 5. Catalyst ---
    if catalyst_score > 0:
        contribution = min(catalyst_score * 0.55, 3.5)
        score += contribution
        if catalyst_note:
            reasons.append(f"Catalyst ({catalyst_quality or 'detected'}): {catalyst_note[:70]}")
        elif catalyst_quality and catalyst_quality != "None":
            reasons.append(f"Catalyst quality: {catalyst_quality}")

    # --- 6. Memory boost (keep catalyst alive) ---
    if memory_boost > 0:
        score += memory_boost
        if memory_note:
            reasons.append(memory_note)

    # --- 7. Penny / micro scrutiny (rule 18) ---
    if penny_flags and penny_flags.get("risk_level") in ("Elevated", "High"):
        penalty = 1.0 if penny_flags["risk_level"] == "Elevated" else 2.0
        score -= penalty
        for flag in penny_flags.get("flags", [])[:2]:
            reasons.append(f"⚠ {flag}")

    # --- 8. Avoid pure chase ---
    if change_pct > 6 and (rvol is None or rvol < 1.2) and catalyst_score < 4:
        score -= 1.5
        reasons.append("Large move with limited confirmation — chase risk")

    score = max(0.0, min(score, max_score))

    # Candidate rating
    if score >= 7.0:
        candidate = "Strong"
    elif score >= 5.0:
        candidate = "Moderate"
    elif score >= 3.0:
        candidate = "Weak"
    else:
        candidate = "Reject"

    # Entry rating
    if candidate in ("Strong", "Moderate") and (rvol is None or rvol >= 1.0):
        entry = "Ready" if score >= 6.5 else "Near"
    elif candidate == "Weak":
        entry = "Poor"
    else:
        entry = "Invalid"

    return {
        "score": round(score, 1),
        "candidate_rating": candidate,
        "entry_rating": entry,
        "reasons": reasons,
        "catalyst_note": catalyst_note,
        "catalyst_score": catalyst_score,
        "catalyst_quality": catalyst_quality,
        "penny_risk": penny_flags.get("risk_level") if penny_flags else None
    }
