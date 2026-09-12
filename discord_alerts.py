"""
Discord alert sender using webhook.
Includes per-ticker cooldown to avoid spam.
"""

import json
import time
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

COOLDOWN_FILE = Path(__file__).parent / "alert_cooldowns.json"
DEFAULT_COOLDOWN_MINUTES = 45


def _load_cooldowns() -> Dict[str, float]:
    try:
        if COOLDOWN_FILE.exists():
            with open(COOLDOWN_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_cooldowns(data: Dict[str, float]):
    try:
        with open(COOLDOWN_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def can_alert(symbol: str, cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES) -> bool:
    cooldowns = _load_cooldowns()
    last = cooldowns.get(symbol)
    if last is None:
        return True
    return (time.time() - float(last)) >= cooldown_minutes * 60


def mark_alerted(symbol: str):
    cooldowns = _load_cooldowns()
    cooldowns[symbol] = time.time()
    _save_cooldowns(cooldowns)


def send_discord_message(webhook_url: str, content: str = None, embeds: list = None) -> bool:
    if not webhook_url:
        return False

    payload = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 429:
            print("Discord rate limited — skipping this send")
            return False
        return response.status_code in (200, 204)
    except Exception as e:
        print(f"Discord send error: {e}")
        return False


def create_alert_embed(
    symbol: str,
    title: str,
    description: str,
    color: int = 0x00FF00,
    fields: Optional[list] = None,
    footer: str = "Stock & Catalyst Monitor"
) -> Dict[str, Any]:
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
    catalyst_note: str = None,
    cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES
) -> bool:
    if not webhook_url:
        return False
    if not can_alert(symbol, cooldown_minutes=cooldown_minutes):
        print(f"Skipping {symbol} — still in cooldown")
        return False

    color_map = {
        "Strong": 0x00FF00,
        "Moderate": 0xFFFF00,
        "Weak": 0xFFA500,
        "Reject": 0xFF0000,
        "Ready": 0x00FF00,
        "Near": 0xFFFF00,
        "Poor": 0xFFA500,
        "Invalid": 0xFF0000,
    }
    color = 0x3498DB
    for key, value in color_map.items():
        if key in str(rating):
            color = value
            break

    change_str = f"+{change_pct:.2f}%" if change_pct >= 0 else f"{change_pct:.2f}%"
    description = f"**Price:** ${price:.4f}  ({change_str})\n**Rating:** {rating}"
    if catalyst_note:
        description += f"\n\n**Catalyst:** {catalyst_note[:180]}"

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

    ok = send_discord_message(webhook_url, embeds=[embed])
    if ok:
        mark_alerted(symbol)
    return ok


def send_status_message(webhook_url: str, message: str) -> bool:
    return send_discord_message(webhook_url, content=f"ℹ️ {message}")
