"""
Main monitoring loop with:
- Catalyst analysis
- Keep-catalyst-alive memory
- Penny-stock scrutiny
- Daily / periodic summary
"""

import yaml
import time
from datetime import datetime
from pathlib import Path

from utils.data_fetcher import (
    get_current_price, get_history, calculate_indicators,
    get_relative_strength, is_market_open
)
from utils.scoring import score_setup
from utils.discord_alerts import send_price_alert, send_status_message
from utils.catalysts import analyze_catalysts
from utils.catalyst_memory import remember_catalyst, get_memory_boost
from utils.penny_flags import get_penny_flags
from utils.daily_summary import send_daily_summary


CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def run_check(config: dict, send_summary: bool = False):
    """Run one full check cycle."""
    webhook = config["discord"]["webhook_url"]
    stocks = config["watchlist"].get("stocks", [])
    crypto = config["watchlist"].get("crypto", [])
    benchmark = config["settings"].get("relative_strength_benchmark", "QQQ")
    market_hours_only = config["settings"].get("market_hours_only_stocks", True)

    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running check...")

    check_stocks = True
    if market_hours_only and not is_market_open():
        check_stocks = False
        print("  US market closed — skipping stocks (crypto still checked)")

    symbols_to_check = []
    if check_stocks:
        symbols_to_check.extend(stocks)
    symbols_to_check.extend(crypto)

    if not symbols_to_check:
        print("  Nothing to check this cycle")
        return []

    results = []

    for symbol in symbols_to_check:
        print(f"  Checking {symbol}...")
        price_data = get_current_price(symbol)
        if not price_data:
            print(f"    → Failed to get price")
            continue

        hist = get_history(symbol, period="3mo")
        indicators = calculate_indicators(hist) if hist is not None else {}

        rs_benchmark = "BTC-USD" if symbol.endswith("-USD") else benchmark
        rs = get_relative_strength(symbol, benchmark=rs_benchmark)

        catalyst = analyze_catalysts(symbol)
        catalyst_score = catalyst.get("catalyst_score", 0.0)
        catalyst_note = catalyst.get("summary")
        catalyst_quality = catalyst.get("quality")

        if catalyst_score >= 2.5:
            remember_catalyst(symbol, catalyst_score, catalyst_note, catalyst_quality)

        mem = get_memory_boost(symbol)
        memory_boost = mem.get("boost", 0.0)
        memory_note = mem.get("note")

        penny = get_penny_flags(symbol, price_data.get("price"), indicators)

        scored = score_setup(
            price_data=price_data,
            indicators=indicators,
            relative_strength=rs,
            catalyst_score=catalyst_score,
            catalyst_note=catalyst_note if catalyst_score >= 2 else None,
            catalyst_quality=catalyst_quality,
            penny_flags=penny,
            memory_boost=memory_boost,
            memory_note=memory_note
        )

        result = {
            **price_data,
            **indicators,
            "relative_strength": rs,
            **scored,
            "catalyst": catalyst,
            "penny": penny
        }
        results.append(result)

        if scored["candidate_rating"] in ("Strong", "Moderate"):
            print(f"    → {scored['candidate_rating']} / {scored['entry_rating']} (score {scored['score']}) → ALERT")
            send_price_alert(
                webhook_url=webhook,
                symbol=symbol,
                price=price_data["price"],
                change_pct=price_data["change_pct"],
                rating=f"{scored['candidate_rating']} | {scored['entry_rating']}",
                reasons=scored["reasons"],
                catalyst_note=catalyst_note if catalyst_score >= 2 else None
            )
        else:
            extra = []
            if catalyst_score > 0:
                extra.append(f"Cat {catalyst_score}")
            if penny.get("risk_level") in ("Elevated", "High"):
                extra.append(f"Penny:{penny['risk_level']}")
            extra_str = f" | {' '.join(extra)}" if extra else ""
            print(f"    → {scored['candidate_rating']} (score {scored['score']}{extra_str})")

    print(f"  Checked {len(results)} symbols")

    if send_summary and results:
        send_daily_summary(webhook, results, title="Watchlist Summary")
        print("  Summary sent to Discord")

    return results


def main():
    config = load_config()
    interval = config["settings"].get("check_interval_minutes", 5)
    webhook = config["discord"]["webhook_url"]

    print("=" * 60)
    print("Stock & Catalyst Monitor (Full Feature Set)")
    print(f"Interval: {interval} min")
    print(f"Stocks: {config['watchlist'].get('stocks', [])}")
    print(f"Crypto: {config['watchlist'].get('crypto', [])}")
    print("=" * 60)

    send_status_message(
        webhook,
        f"Monitor started with full features:\n"
        f"• Catalyst engine + memory\n"
        f"• Penny-stock scrutiny\n"
        f"• Periodic summaries\n"
        f"Watching {len(config['watchlist'].get('stocks', []))} stocks + "
        f"{len(config['watchlist'].get('crypto', []))} crypto."
    )

    run_check(config, send_summary=True)

    print(f"\nEntering loop — checking every {interval} minutes...")
    cycle = 0
    while True:
        time.sleep(interval * 60)
        cycle += 1
        send_sum = (cycle % 12 == 0)
        run_check(config, send_summary=send_sum)


if __name__ == "__main__":
    main()
