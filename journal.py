import json
from datetime import datetime
from pathlib import Path

JOURNAL = Path(__file__).parent / "trade_journal.json"

def load_journal():
    try:
        if JOURNAL.exists():
            return json.loads(JOURNAL.read_text())
    except Exception:
        pass
    return []

def add_entry(symbol, problem, note):
    data = load_journal()
    data.insert(0, {
        "time": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "symbol": str(symbol or "").upper(),
        "problem": problem,
        "note": note or "",
    })
    JOURNAL.write_text(json.dumps(data[:100], indent=2))
    return data
