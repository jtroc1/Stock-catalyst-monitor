from datetime import datetime, timedelta
import requests

SEC_HEADERS = {
    "User-Agent": "StockCatalystMonitor personal-research contact@example.com",
    "Accept-Encoding": "gzip, deflate",
}


def _finnhub_key():
    try:
        import streamlit as st
        return st.secrets.get("finnhub", {}).get("api_key", "")
    except Exception:
        return ""


def finnhub_earnings(days_ahead=60, api_key=None):
    key = api_key or _finnhub_key()
    if not key:
        return []
    start = datetime.utcnow().date()
    end = start + timedelta(days=days_ahead)
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/calendar/earnings",
            params={"from": start.isoformat(), "to": end.isoformat(), "token": key},
            timeout=15,
        )
        r.raise_for_status()
        rows = (r.json() or {}).get("earningsCalendar") or []
    except Exception:
        return []

    out = []
    for row in rows:
        sym = (row.get("symbol") or "").upper()
        if not sym:
            continue
        date = row.get("date")
        days = None
        try:
            days = (datetime.strptime(date, "%Y-%m-%d").date() - start).days
        except Exception:
            pass
        out.append({
            "symbol": sym,
            "source": "Finnhub",
            "type": "Earnings",
            "when": date,
            "days_until": days,
            "hour": row.get("hour"),
            "eps_estimate": row.get("epsEstimate"),
            "summary": f"Earnings {date} ({row.get('hour') or 'unspecified'})",
        })
    out.sort(key=lambda x: x.get("days_until") if x.get("days_until") is not None else 99)
    return out


def finnhub_news(symbol, days=5, api_key=None):
    key = api_key or _finnhub_key()
    if not key:
        return []
    end = datetime.utcnow().date()
    start = end - timedelta(days=days)
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={
                "symbol": symbol.replace("-USD", ""),
                "from": start.isoformat(),
                "to": end.isoformat(),
                "token": key,
            },
            timeout=15,
        )
        r.raise_for_status()
        items = r.json() or []
    except Exception:
        return []
    news = []
    for item in items[:8]:
        news.append({
            "source": item.get("source") or "Finnhub",
            "headline": item.get("headline"),
            "url": item.get("url"),
            "datetime": item.get("datetime"),
        })
    return news


def _ticker_to_cik(symbol):
    try:
        r = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=SEC_HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None
    symbol = symbol.upper()
    for row in data.values():
        if str(row.get("ticker", "")).upper() == symbol:
            return str(row.get("cik_str")).zfill(10)
    return None


def edgar_recent_filings(symbol, forms=("8-K", "4"), limit=8):
    if str(symbol).endswith("-USD"):
        return []
    cik = _ticker_to_cik(symbol)
    if not cik:
        return []
    try:
        r = requests.get(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            headers=SEC_HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    recent = (data.get("filings") or {}).get("recent") or {}
    forms_list = recent.get("form") or []
    dates = recent.get("filingDate") or []
    acc = recent.get("accessionNumber") or []
    docs = recent.get("primaryDocument") or []
    wanted = set(forms)
    out = []
    for i, form in enumerate(forms_list):
        if form not in wanted:
            continue
        date = dates[i] if i < len(dates) else ""
        accession = acc[i] if i < len(acc) else ""
        doc = docs[i] if i < len(docs) else ""
        acc_nodash = accession.replace("-", "")
        link = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_nodash}/{doc}"
        out.append({
            "symbol": symbol,
            "source": "SEC EDGAR",
            "type": form,
            "when": date,
            "url": link,
            "summary": f"{form} filed {date}",
        })
        if len(out) >= limit:
            break
    return out


def combine_calendar(symbols, days_ahead=60):
    wanted = {s.upper() for s in symbols if not str(s).endswith("-USD")}
    cal = finnhub_earnings(days_ahead=days_ahead)
    filtered = [row for row in cal if row["symbol"] in wanted]
    extra = [row for row in cal if row.get("days_until") is not None and 0 <= row["days_until"] <= 7]
    seen = {row["symbol"] for row in filtered}
    for row in extra:
        if row["symbol"] not in seen:
            filtered.append(row)
            seen.add(row["symbol"])
    return filtered[:40]
