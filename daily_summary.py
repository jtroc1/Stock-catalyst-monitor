"""
Daily / periodic summary generator for Discord.
"""

from datetime import datetime
from typing import List, Dict, Any
from utils.discord_alerts import send_discord_message, create_alert_embed


def build_summary_embed(results: List[Dict[str, Any]], title: str = "Watchlist Summary") -> Dict[str, Any]:
    """Create a rich Discord embed summarizing the current scan."""

    strong = [r for r in results if r.get("candidate_rating") == "Strong"]
    moderate = [r for r in results if r.get("candidate_rating") == "Moderate"]
    weak = [r for r in results if r.get("candidate_rating") == "Weak"]
    with_catalyst = [r for r in results if r.get("catalyst_score", 0) >= 2.5]

    # Top names by score
    sorted_results = sorted(results, key=lambda x: x.get("score", 0), reverse=True)
    top_lines = []
    for r in sorted_results[:8]:
        cat = f" | Cat {r.get('catalyst_score', 0)}" if r.get("catalyst_score", 0) >= 2 else ""
        top_lines.append(
            f"**{r['symbol']}**  {r.get('price')} ({r.get('change_pct', 0):+.1f}%)  "
            f"→ {r.get('candidate_rating')} / {r.get('entry_rating')} ({r.get('score')}){cat}"
        )

    description = (
        f"**Strong:** {len(strong)}  |  **Moderate:** {len(moderate)}  |  **Weak:** {len(weak)}\n"
        f"**With meaningful catalyst:** {len(with_catalyst)}\n\n"
        + ("\n".join(top_lines) if top_lines else "No data")
    )

    color = 0x00AA00 if strong or moderate else 0x3498DB

    embed = {
        "title": f"📊 {title}",
        "description": description,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": "Stock & Catalyst Monitor"}
    }
    return embed


def send_daily_summary(webhook_url: str, results: List[Dict[str, Any]], title: str = "Watchlist Summary") -> bool:
    """Send a clean summary embed to Discord."""
    embed = build_summary_embed(results, title=title)
    return send_discord_message(webhook_url, embeds=[embed])
