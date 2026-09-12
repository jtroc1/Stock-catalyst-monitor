# Stock & Catalyst Monitor

Personal monitoring tool aligned with your trading rules.

## Features

- Watchlist of stocks + crypto
- Multi-factor scoring (relative strength, RSI, MAs, volume, catalysts)
- Candidate rating: Strong / Moderate / Weak / Reject
- Entry rating: Ready / Near / Poor / Invalid
- Catalyst engine (earnings + news + impact scoring)
- Keep-catalyst-alive memory
- Penny-stock extra scrutiny
- Discord rich alerts + periodic summaries
- Visual Streamlit dashboard (iPhone-friendly)

## How to Run

### 1. Install dependencies
```bash
cd stock_monitor
pip install yfinance pandas pyyaml requests pytz streamlit
```

### 2. Run the monitor (background checks + Discord)
```bash
python monitor.py
```

### 3. Run the visual dashboard
```bash
streamlit run dashboard/app.py
```

Then open the local URL (usually http://localhost:8501) on your computer or phone (same Wi-Fi).

On iPhone you can also use the network URL shown by Streamlit and add it to your Home Screen.

## Configuration

Edit `config.yaml` to:
- Add/remove tickers
- Change check interval
- Update Discord webhook

## Current Watchlist

**Stocks:** TSLA, VASO, PYPL, QQQ, DUOL, SEI, QCOM, GLW, BE, ROIV, CHYM, META, SIG  
**Crypto:** BTC, ETH, SOL, XRP, DOGE, AVAX, LINK, DOT, ADA, NEAR, INJ
