import json
from pathlib import Path

STORE = Path(__file__).parent / "extra_watchlist.json"


def load_extra():
    try:
        if STORE.exists():
            data = json.loads(STORE.read_text())
            stocks = [s.upper() for s in data.get("stocks", []) if s]
            crypto = [s for s in data.get("crypto", []) if s]
            return {"stocks": stocks, "crypto": crypto}
    except Exception:
        pass
    return {"stocks": [], "crypto": []}


def add_symbols(symbols):
    extra = load_extra()
    for raw in symbols or []:
        if not raw:
            continue
        sym = str(raw).upper().strip()
        if sym.endswith("-USD") or sym.endswith("-USDT"):
            if sym not in extra["crypto"]:
                extra["crypto"].append(sym)
        else:
            if sym not in extra["stocks"]:
                extra["stocks"].append(sym)
    try:
        STORE.write_text(json.dumps(extra, indent=2))
    except Exception:
        pass
    return extra


def merge_watchlist(config_stocks, config_crypto):
    extra = load_extra()
    stocks = list(dict.fromkeys(list(config_stocks or []) + extra["stocks"]))
    crypto = list(dict.fromkeys(list(config_crypto or []) + extra["crypto"]))
    return stocks, crypto
