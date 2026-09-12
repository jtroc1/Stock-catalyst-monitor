"""
Discord alert sender using webhook.
Supports rich embeds for better readability on mobile.
"""

import requests
from datetime import datetime
from typing import Optional, Dict, Any


def send_discord_message(webhook_url: str, content: str = None, embeds: list = None) -> bool:
    """Send a message or embed to Discord webhook."""
    payload = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.status_code in (200, 204)
    except Exception as e:
        print(f"Discord send error: {e}")
        return False


def create_alert_embed(
    symbol: str,
    title: str,
    description: str,
    color: int = 0x00FF00,  # Green by default
    fields: Optional[list] = None,
    footer: str = "Stock & Catalyst Monitor"
) -> Dict[str, Any]:
    """Create a rich Discord embed for alerts."""
    embed = {
        "title": f"{symbol} — {title}",
        "description": description,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": footer}
    }
    if fields:
        embed["fields"] = fields
    return embed


def send_price_alert(
    webhook_url: str,
    symbol: str,
    price: float,
    change_pct: float,
    rating: str,
    reasons: list,
    catalyst_note: str = None
) -> bool:
    """Send a structured price/catalyst alert."""
    
    # Color based on rating
    color_map = {
        "Strong": 0x00FF00,      # Bright green
        "Moderate": 0xFFFF00,    # Yellow
        "Weak": 0xFFA500,        # Orange
        "Reject": 0xFF0000,      # Red
        "Ready": 0x00FF00,
        "Near": 0xFFFF00,
        "Poor": 0xFFA500,
        "Invalid": 0xFF0000,
    }
    color = color_map.get(rating, 0x3498DB)

    change_str = f"+{change_pct:.2f}%" if change_pct >= 0 else f"{change_pct:.2f}%"
    
    description = f"**Price:** ${price:.2f}  ({change_str})\n**Rating:** {rating}"
    if catalyst_note:
        description += f"\n\n**Catalyst:** {catalyst_note}"

    fields = []
    if reasons:
        fields.append({
            "name": "Key Reasons",
            "value": "\n".join(f"• {r}" for r in reasons[:6]),
            "inline": False
        })

    embed = create_alert_embed(
        symbol=symbol,
        title=f"Alert — {rating}",
        description=description,
        color=color,
        fields=fields
    )

    return send_discord_message(webhook_url, embeds=[embed])


def send_status_message(webhook_url: str, message: str) -> bool:
    """Send a simple status/update message."""
    return send_discord_message(webhook_url, content=f"ℹ️ {message}")
