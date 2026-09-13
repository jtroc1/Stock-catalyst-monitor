import json
from pathlib import Path
import yaml

STORE = Path(__file__).parent / "extra_watchlist.json"
CONFIG = Path(__file__).parent / "config.yaml"
COMMODITY_ETFS = {"GLD", "SLV", "USO", "UNG", "CPER", "DBA", "GDX", "PALL", "PPLT", "UUP"}


def _bucket(sym):
    s = str(sym).upper().strip()
    if s.endswith("-USD") or s.endswith("-USDT"):
        return "crypto"
    if s.endswith("=F") or s in COMMODITY_ETFS:
        return "commodities"
    return "stocks"


def load_extra():
    extra = {"stocks": [], "crypto": [], "commodities": []}
    try:
        if STORE.exists():
            data = json.loads(STORE.read_text())
            extra["stocks"] = [s.upper() for s in data.get("stocks", []) if s]
            extra["crypto"] = [s for s in data.get("crypto", []) if s]
            extra["commodities"] = [s for s in data.get("commodities", []) if s]
    except Exception:
        pass
    return extra


def add_symbols(symbols):
    extra = load_extra()
    for raw in symbols or []:
        if not raw:
            continue
        sym = str(raw).upper().strip()
        bucket = _bucket(sym)
        if sym not in extra[bucket]:
            extra[bucket].append(sym)
    try:
        STORE.write_text(json.dumps(extra, indent=2))
    except Exception:
        pass
    return extra


def merge_watchlist(config_stocks, config_crypto, config_commodities=None):
    extra = load_extra()
    stocks = list(dict.fromkeys(list(config_stocks or []) + extra["stocks"]))
    crypto = list(dict.fromkeys(list(config_crypto or []) + extra["crypto"]))
    commodities = list(dict.fromkeys(list(config_commodities or []) + extra["commodities"]))
    return stocks, crypto, commodities
