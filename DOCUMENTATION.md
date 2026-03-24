# Kraken Market Data Pipeline — Full Documentation

## Overview

A production-grade cryptocurrency market data collection and analysis pipeline with real-time price data, news sentiment analysis, and LLM-powered insights.

**Purpose:** Automated collection, storage, and LLM-enhanced analysis of Kraken exchange market data (ETH/EUR, BTC/EUR) with news sentiment integration and paper trading simulation.

**Architecture:** systemd services + SQLite + Python analytics + Ollama LLM enrichment + News feeds

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA COLLECTION                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │ Kraken API   │───▶│ collector.py │───▶│ SQLite DB    │    │
│  │ (REST)       │    │ (5 min poll) │    │ market.db    │    │
│  └──────────────┘    └──────────────┘    └──────────────┘    │
│                           │ systemd service                      │
└───────────────────────────┼─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                        ANALYSIS LAYER                            │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │ SQL          │───▶│ Ollama API   │───▶│ SQLite       │    │
│  │ (metrics)    │    │ (kimi-k2.5)  │    │ (reports)    │    │
│  └──────────────┘    └──────────────┘    └──────────────┘    │
│                           │ systemd timer (hourly)             │
└───────────────────────────┼─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                     DECISION & ALERTING                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │ Heartbeat    │    │ OpenClaw     │    │ Paper Trade  │    │
│  │ (5 min)      │    │ Cron         │    │ Log          │    │
│  └──────────────┘    └──────────────┘    └──────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                      NEWS COLLECTION                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│  │ RSS Feeds    │───▶│ news_collector│───▶│ SQLite DB    │    │
│  │ (CoinDesk,   │    │ (15 min)     │    │ news_articles│    │
│  │  Cointelegraph)│   └──────────────┘    └──────────────┘    │
│  └──────────────┘    ┌──────────────┐                         │
│  ┌──────────────┐    │ xurl skill   │                         │
│  │ X/Twitter API│───▶│ (30 min)     │                         │
│  └──────────────┘    └──────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Data Collector (`collector.py`)

**Purpose:** Poll Kraken API every 5 minutes, store raw market data

**What it collects:**
- Current price (last trade)
- Best bid/ask prices
- 24h high/low/volume
- Order book depth (top 10 bids/asks)
- Spread metrics

**Storage:** `market.db` → `snapshots` table

**Service:** `kraken-collector.service` (always running, auto-restart)

---

### 2. RSS News Collector (`news_collector_rss.py`)

**Purpose:** Fetch crypto news from RSS feeds every 15 minutes

**Sources:**
- CoinDesk: `https://www.coindesk.com/arc/outboundfeeds/rss/`
- Cointelegraph: `https://cointelegraph.com/rss`
- The Block: `https://www.theblock.co/rss.xml`

**Sentiment Analysis:**
- Keyword-based scoring
- 🟢 Bullish: surge, rally, moon, pump, breakout, ATH
- 🔴 Bearish: crash, dump, fall, decline, sell-off, fear
- ⚪ Neutral: No strong keywords

**Storage:** `market.db` → `news_articles` table

**Service:** `kraken-news-rss.timer` (every 15 minutes)

---

### 3. X/Twitter News Collector (`news_collector_x.py`)

**Purpose:** Fetch crypto sentiment from X/Twitter API every 30 minutes

**Requirements:**
- xurl skill installed
- Bearer token authentication: `xurl auth app --bearer-token TOKEN`

**Search Queries:**
- "bitcoin BTC"
- "ethereum ETH"
- "crypto bullish"
- "crypto bearish"

**Storage:** `market.db` → `news_articles` table

**Service:** `kraken-news-x.timer` (every 30 minutes)

---

### 4. Analyzer (`analyzer.py`)

**Purpose:** Generate LLM-enhanced market reports every hour WITH news context

**Analysis includes:**
- Price trend detection (rising/falling/neutral)
- Volatility calculation (std dev of price changes)
- Liquidity scoring (bid/ask depth, spread)
- **NEW:** Recent news fetching (last 6h)
- **NEW:** Sentiment analysis integration
- Historical comparison (vs previous analysis)
- LLM narrative generation via Ollama

**LLM Prompt Structure:**
```
PAIR: {pair}
PERIOD: 24h

PRICE METRICS:
- Current: €{price}
- Trend: {trend}
- Volatility: {volatility}

RECENT NEWS (last 6h):
- 🟢 [SOURCE] Headline...
- 🔴 [SOURCE] Headline...
- ⚪ [SOURCE] Headline...

Provide assessment covering:
1. Price action and trend strength
2. Market liquidity and volatility
3. Comparison to previous assessment
4. How recent news sentiment might impact price
5. Brief outlook or risk level
```

**Storage:** `market.db` → `market_reports` + `llm_analyses` tables

**Service:** `kraken-analyzer.timer` (runs at :00 every hour)

---

### 5. Alert Checker (`alert_check.py`)

**Purpose:** Detect significant price movements (>3%)

**Trigger:** Every 5 minutes via OpenClaw cron

**Output:** Alert sent to Metis for evaluation

---

## Database Schema

### snapshots
```sql
id INTEGER PRIMARY KEY
timestamp DATETIME        -- Collection time
pair TEXT                 -- XETHZEUR, XXBTZEUR
price REAL               -- Last trade price
bid REAL                 -- Best bid
ask REAL                 -- Best ask
spread_pct REAL          -- Spread percentage
volume_24h REAL          -- 24h volume
high_24h REAL            -- 24h high
low_24h REAL             -- 24h low
bid_depth_eth REAL       -- Order book bid depth
ask_depth_eth REAL       -- Order book ask depth
bid_ask_ratio REAL       -- Bid/ask ratio
```

### news_articles
```sql
id INTEGER PRIMARY KEY
timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
source TEXT              -- 'coindesk', 'cointelegraph', 'x', etc.
external_id TEXT         -- Original article ID
title TEXT               -- Article headline
content TEXT             -- Article content (truncated)
url TEXT                 -- Article URL
published_at TEXT        -- Original publish time
category TEXT            -- 'news', 'social', etc.
symbols TEXT             -- 'BTC,ETH' - detected symbols
sentiment TEXT           -- 'bullish', 'bearish', 'neutral'
raw_json TEXT            -- Full raw data
```

### llm_analyses
```sql
id INTEGER PRIMARY KEY
timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
pair TEXT                -- XETHZEUR, XXBTZEUR
raw_analysis JSON        -- Structured metrics
llm_insight TEXT         -- LLM-generated narrative
```

---

## Systemd Services

### Installation

```bash
# Copy all services and timers
sudo cp kraken-*.service /etc/systemd/system/
sudo cp kraken-*.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable all services
sudo systemctl enable --now kraken-collector
sudo systemctl enable --now kraken-analyzer.timer
sudo systemctl enable --now kraken-webgui
sudo systemctl enable --now kraken-news-rss.timer
sudo systemctl enable --now kraken-news-x.timer
```

### Timer Schedule

| Timer | Frequency | Purpose |
|-------|-----------|---------|
| kraken-collector | Every 5 min | Price data |
| kraken-analyzer | Every hour | LLM analysis |
| kraken-news-rss | Every 15 min | RSS news |
| kraken-news-x | Every 30 min | X/Twitter |

---

## Configuration

### Environment Variables

```bash
export MARKET_DB_PATH="~/kraken-market-data/market.db"
export OLLAMA_HOST="http://127.0.0.1:11435"
```

### X/Twitter Authentication

```bash
# 1. Get Bearer Token from https://developer.twitter.com
# 2. Authenticate:
xurl auth app --bearer-token YOUR_TOKEN_HERE

# 3. Verify:
xurl auth status
```

---

## Troubleshooting

### Check all timers
```bash
systemctl list-timers kraken-*
```

### View recent news
```bash
sqlite3 market.db "SELECT source, title, sentiment FROM news_articles ORDER BY timestamp DESC LIMIT 10;"
```

### View LLM analyses with news
```bash
sqlite3 market.db "SELECT timestamp, pair, llm_insight FROM llm_analyses ORDER BY timestamp DESC LIMIT 5;"
```

### Test news collectors
```bash
python3 news_collector_rss.py
python3 news_collector_x.py
```

### Check service logs
```bash
sudo journalctl -u kraken-news-rss -f
sudo journalctl -u kraken-news-x -f
sudo journalctl -u kraken-analyzer -f
```

---

## Roadmap

### ✅ Completed

| Feature | Status | Date |
|---------|--------|------|
| Data collection (5 min) | ✅ | 2026-03-24 |
| LLM analysis (hourly) | ✅ | 2026-03-24 |
| Web dashboard (port 8890) | ✅ | 2026-03-24 |
| Paper trading framework | ✅ | 2026-03-24 |
| RSS news integration | ✅ | 2026-03-24 |
| X/Twitter integration | ✅ | 2026-03-24 |
| Sentiment analysis | ✅ | 2026-03-24 |
| News + LLM integration | ✅ | 2026-03-24 |

### 🚧 Planned

| Feature | Status | ETA |
|---------|--------|-----|
| Multi-timeframe analysis | 🚧 | TBD |
| Predictive projections | 🚧 | TBD |
| On-chain data (whale alerts) | 🚧 | TBD |
| News-driven adaptive alerts | 🚧 | TBD |

---

**Last Updated:** 2026-03-24
**Version:** 1.3
**Maintainer:** Metis 🦉
