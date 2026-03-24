# Kraken Market Data Pipeline

Production-grade cryptocurrency market intelligence system with real-time price data, news sentiment analysis, and LLM-powered insights.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Kraken API     │────▶│  collector.py    │────▶│    SQLite DB    │
│  (REST)         │     │  (5 min poll)    │     │    market.db    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                                               │
         │         ┌──────────────────┐                   │
         └────────▶│  analyzer.py     │◀──────────────────┘
                   │  (hourly LLM)    │
                   └──────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
┌─────────────────┐  ┌──────────────┐  ┌─────────────────┐
│  Web GUI        │  │  Heartbeat   │  │  Paper Trading  │
│  Port 8890      │  │  (5 min)     │  │  Log            │
└─────────────────┘  └──────────────┘  └─────────────────┘

┌─────────────────┐     ┌──────────────────┐
│  RSS Feeds      │────▶│  news_collector  │
│  (CoinDesk,     │     │  (15 min poll)   │
│   Cointelegraph)│     └──────────────────┘
└─────────────────┘

┌─────────────────┐     ┌──────────────────┐
│  X/Twitter API  │────▶│  news_collector_x│
│  (xurl skill)   │     │  (30 min poll)   │
└─────────────────┘     └──────────────────┘
```

## Features

### Data Collection
- **Price Data**: Kraken API every 5 minutes (BTC/EUR, ETH/EUR)
- **RSS News**: CoinDesk, Cointelegraph, The Block every 15 minutes
- **X/Twitter**: Crypto sentiment via xurl skill every 30 minutes
- **Sentiment Analysis**: Automatic bullish/bearish/neutral tagging

### LLM Analysis
- **Hourly Reports**: LLM model via Ollama/OpenAI-compatible API
- **News Integration**: Recent headlines fed into LLM prompt
- **Combined Insights**: Price trends + news sentiment = better predictions
- **Historical Context**: Compares to previous analyses

### Alerts & Trading
- **Price Alerts**: >3% moves trigger notifications
- **Paper Trading**: Virtual portfolio for strategy testing
- **Risk Management**: Position sizing, stop losses, fee calculations

### Web Dashboard
- **Live Charts**: 24h dual-axis price history
- **News Feed**: Recent headlines with sentiment badges
- **LLM History**: Scrollable analysis archive
- **Portfolio Tracking**: Paper wallet P&L

## Quick Start

### Prerequisites

- Python 3.8+
- SQLite
- Ollama (for LLM analysis) or OpenAI-compatible API
- xurl (for X/Twitter integration, optional)

### Installation

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/kraken-market-pipeline.git
cd kraken-market-pipeline

# Set environment variable (optional)
export MARKET_DB_PATH="~/kraken-market-data/market.db"

# Initialize database
python3 -c "import sqlite3; conn = sqlite3.connect(os.environ.get('MARKET_DB_PATH', '~/kraken-market-data/market.db')); conn.executescript(open('schema.sql').read())"
```

### Manual Run

```bash
# Data collector (5 min intervals)
python3 collector.py

# News collection (run once to test)
python3 news_collector_rss.py
python3 news_collector_x.py  # Requires xurl auth

# LLM analysis with news context
python3 analyzer.py analyze XETHZEUR

# Web GUI (port 8890)
python3 web_server.py
```

### Systemd Services (Recommended)

```bash
# Edit service files to set USER_PLACEHOLDER and WORKDIR_PLACEHOLDER
# Then install:
sudo cp kraken-*.service /etc/systemd/system/
sudo cp kraken-*.timer /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start all services
sudo systemctl enable --now kraken-collector
sudo systemctl enable --now kraken-analyzer.timer
sudo systemctl enable --now kraken-webgui
sudo systemctl enable --now kraken-news-rss.timer
sudo systemctl enable --now kraken-news-x.timer

# Check status
systemctl list-timers kraken-*
```

## Web Dashboard

**URL:** http://localhost:8890

**Features:**
- Live prices with 24h change
- Dual-axis price charts
- LLM analysis history (scrollable)
- News feed panel
- Paper wallet tracking
- Activity log

Auto-refreshes every 30 seconds.

## News Collection

### RSS Feeds (Auto-configured)

| Source | URL | Frequency |
|--------|-----|-----------|
| CoinDesk | coindesk.com/rss | 15 min |
| Cointelegraph | cointelegraph.com/rss | 15 min |
| The Block | theblock.co/rss.xml | 15 min |

### X/Twitter (Requires Auth)

```bash
# 1. Get Bearer Token from https://developer.twitter.com
# 2. Install xurl: https://github.com/xdevplatform/xurl
# 3. Authenticate:
xurl auth app --bearer-token YOUR_TOKEN_HERE

# 4. Test:
xurl search "bitcoin" -n 5

# 5. The collector runs automatically every 30 min
```

### Sentiment Scoring

Articles are automatically tagged:
- 🟢 **Bullish**: surge, rally, moon, pump, breakout, ATH
- 🔴 **Bearish**: crash, dump, fall, decline, sell-off, fear
- ⚪ **Neutral**: No strong sentiment keywords

## Components

### collector.py
- Polls Kraken API every 5 minutes
- Stores ticker + order book depth in SQLite
- Systemd service with auto-restart

### news_collector_rss.py
- Fetches RSS feeds every 15 minutes
- Parses XML with built-in libraries (no dependencies)
- Sentiment analysis via keyword matching
- Stores in `news_articles` table

### news_collector_x.py
- Uses xurl skill for X/Twitter API
- Searches crypto-related queries
- Runs every 30 minutes via systemd timer
- Same sentiment analysis as RSS

### analyzer.py
- SQL aggregations (trends, volatility, liquidity)
- Fetches recent news for LLM context
- LLM integration via Ollama/OpenAI-compatible API
- Runs hourly via systemd timer
- Combined price + news assessment

### alert_check.py
- Detects >3% price movements
- Triggers alerts every 5 minutes
- Routes to notification system

### web_server.py
- HTTP server on port 8890
- REST API endpoints
- Real-time dashboard
- Auto-refresh every 30 seconds

## Data Schema

### snapshots
```sql
timestamp, pair, price, bid, ask, spread_pct,
volume_24h, high_24h, low_24h,
bid_depth_eth, ask_depth_eth, bid_ask_ratio
```

### news_articles
```sql
timestamp, source, external_id, title, content,
url, published_at, category, symbols, sentiment
```

### llm_analyses
```sql
timestamp, pair, raw_analysis_json, llm_insight
```

## LLM Prompt with News

The analyzer generates prompts like:

```
PAIR: ETH/EUR
PERIOD: 24h

PRICE METRICS:
- Current: €1859.82
- Trend: falling (-0.33%)
- Volatility: 0.2783

RECENT NEWS (last 6h):
- 🟢 [COINTELEGRAPH] Aave DAO backs V4 mainnet plan...
- ⚪ [COINTELEGRAPH] Senator Warren questions crypto...
- 🔴 [THEBLOCK] Balancer Labs to shut down after exploit...

Provide assessment covering:
1. Price action and trend strength
2. Market liquidity and volatility
3. Comparison to previous assessment
4. How recent news sentiment might impact price
5. Brief outlook or risk level
```

## Paper Trading Framework

- **Starting Balance:** Configurable (default: €10.00)
- **Max Position:** 20% per trade
- **Fees:** 0.26% per trade (0.52% roundtrip)
- **Break-even:** >1% price move
- **Entry Signals:** >3% move OR news-driven breakout

## Systemd Timers

| Timer | Frequency | Purpose |
|-------|-----------|---------|
| kraken-collector | Every 5 min | Price data |
| kraken-analyzer | Every hour | LLM analysis |
| kraken-news-rss | Every 15 min | RSS news |
| kraken-news-x | Every 30 min | X/Twitter |

## Troubleshooting

### Check all timers
```bash
systemctl list-timers kraken-*
```

### View news in database
```bash
sqlite3 market.db "SELECT source, title, sentiment FROM news_articles ORDER BY timestamp DESC LIMIT 10;"
```

### Test news collectors
```bash
python3 news_collector_rss.py
python3 news_collector_x.py
```

### View service logs
```bash
sudo journalctl -u kraken-news-rss -f
sudo journalctl -u kraken-news-x -f
```

## Configuration

### Environment Variables

```bash
export MARKET_DB_PATH="~/kraken-market-data/market.db"
export OLLAMA_HOST="http://127.0.0.1:11435"
```

### Service File Placeholders

Edit service files to replace:
- `USER_PLACEHOLDER` → your username
- `WORKDIR_PLACEHOLDER` → full path to installation directory

## Roadmap

- [x] Multi-timeframe analysis
- [x] News & sentiment integration (RSS, X/Twitter)
- [ ] Predictive price projections
- [ ] On-chain data (whale alerts, exchange flows)
- [ ] News-driven adaptive alert thresholds

## Documentation

- `README.md` — This file
- `DOCUMENTATION.md` — Full technical reference
- `docs/NEWS_INTEGRATION_PLAN.md` — Implementation details

## License

MIT

---
**Version:** 1.3  
**Last Updated:** 2026-03-24
