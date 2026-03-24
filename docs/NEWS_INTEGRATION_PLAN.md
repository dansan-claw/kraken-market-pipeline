# News & Sentiment Integration Plan

## Overview

Feed real-time news and sentiment data into the LLM analyst to improve market predictions and enable news-driven alerts.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  News Sources   │────▶│  News Collector  │────▶│  SQLite DB      │
│  (RSS/APIs)     │     │  (5 min poll)    │     │  news table     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                              │                            │
                              ▼                            ▼
                       ┌──────────────┐            ┌──────────────┐
                       │  Sentiment   │            │  LLM Context │
                       │  Scorer      │            │  Injection   │
                       └──────────────┘            └──────────────┘
                                                             │
                                                             ▼
                                                  ┌─────────────────┐
                                                  │  Analyzer       │
                                                  │  (enhanced)     │
                                                  └─────────────────┘
```

## Phase 1: News Collection (Week 1)

### 1.1 Data Sources

**RSS Feeds (Free, reliable):**
- CoinDesk: `https://www.coindesk.com/arc/outboundfeeds/rss/`
- Cointelegraph: `https://cointelegraph.com/rss`
- The Block: `https://www.theblock.co/rss.xml`

**Twitter/X API (Optional, requires API key):**
- Crypto influencers list
- Whale alerts
- Exchange announcements

**Economic Calendar (ForexFactory/Investing.com):**
- Macro events affecting crypto
- Fed decisions, inflation data

### 1.2 Database Schema

```sql
-- News articles table
CREATE TABLE news_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    source TEXT NOT NULL,           -- 'coindesk', 'twitter', etc.
    external_id TEXT,               -- Original ID from source
    title TEXT,
    content TEXT,
    url TEXT,
    published_at DATETIME,          -- Original publish time
    category TEXT,                  -- 'regulation', 'technology', 'market', etc.
    symbols TEXT,                   -- Comma-separated: 'BTC,ETH'
    raw_json TEXT
);

-- Sentiment scores
CREATE TABLE sentiment_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    sentiment TEXT,                 -- 'bullish', 'bearish', 'neutral'
    confidence REAL,                -- 0.0 to 1.0
    score REAL,                   -- -1.0 to +1.0
    method TEXT,                    -- 'keyword', 'llm', 'hybrid'
    FOREIGN KEY (article_id) REFERENCES news_articles(id)
);

-- News impact on prices (for training/evaluation)
CREATE TABLE news_impact (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER,
    pair TEXT,
    price_before REAL,
    price_after_1h REAL,
    price_after_4h REAL,
    price_after_24h REAL,
    impact_score REAL,              -- Calculated correlation
    FOREIGN KEY (article_id) REFERENCES news_articles(id)
);
```

### 1.3 Implementation

**news_collector.py:**
- Poll RSS feeds every 5 minutes
- Parse XML, extract title/content/url
- Deduplicate by URL or external_id
- Store in `news_articles` table
- Tag with relevant symbols (BTC, ETH)

**sentiment_scorer.py:**
- Keyword-based: +1 for "bullish", "moon", "adoption"
- Keyword-based: -1 for "bearish", "crash", "ban"
- LLM-based: Send article to LLM for sentiment classification
- Hybrid: Combine both scores weighted by confidence

## Phase 2: LLM Integration (Week 2)

### 2.1 Enhanced Prompt

Modify `analyzer.py` to fetch recent news and include in prompt:

```python
def get_recent_news(pair: str, hours: int = 6) -> List[Dict]:
    """Fetch recent news affecting the pair."""
    symbol = pair.replace('X', '').replace('Z', '').replace('EUR', '')
    return query_db("""
        SELECT a.title, a.content, s.sentiment, s.confidence
        FROM news_articles a
        JOIN sentiment_scores s ON a.id = s.article_id
        WHERE a.symbols LIKE ?
          AND a.published_at > datetime('now', '-{} hours')
        ORDER BY s.confidence DESC
        LIMIT 5
    """.format(hours), (f'%{symbol}%',))

def generate_llm_prompt(analysis: Dict, news: List[Dict]) -> str:
    """Enhanced prompt with news context."""
    news_context = ""
    if news:
        news_context = "\n\nRECENT NEWS:\n"
        for n in news:
            news_context += f"- [{n['sentiment'].upper()}] {n['title'][:80]}...\n"
    
    return f"""...existing prompt...{news_context}

Consider: How might the above news impact price action?"""
```

### 2.2 News-Price Correlation

Track which news articles precede price moves:
- If article sentiment = 'bullish' and price rises >2% in 1h → high impact
- If article sentiment = 'bearish' and price drops >2% in 1h → high impact
- Store in `news_impact` table for model training

## Phase 3: News-Driven Alerts (Week 3)

### 3.1 Breaking News Alerts

**alert_check.py enhancement:**

```python
def check_news_alerts():
    """Check for breaking news that might trigger immediate action."""
    recent_major_news = query_db("""
        SELECT * FROM news_articles a
        JOIN sentiment_scores s ON a.id = s.article_id
        WHERE s.confidence > 0.8
          AND a.published_at > datetime('now', '-10 minutes')
        ORDER BY s.confidence DESC
        LIMIT 1
    """)
    
    if recent_major_news:
        # Trigger immediate heartbeat alert
        return {
            'type': 'NEWS_ALERT',
            'headline': recent_major_news['title'],
            'sentiment': recent_major_news['sentiment'],
            'action': 'EVALUATE_PAPER_TRADE'
        }
```

### 3.2 Adaptive Thresholds

- Normal conditions: >3% move triggers paper trade
- News-active conditions: >1.5% move triggers paper trade
- Breaking news: Immediate evaluation regardless of price move

## Phase 4: Web Dashboard Integration (Week 4)

### 4.1 New UI Components

Add to web GUI:
- **News Feed Panel**: Latest headlines with sentiment badges
- **Sentiment Gauge**: Bullish/bearish meter for last 6h
- **News Impact Chart**: Correlation between news and price moves

### 4.2 API Endpoints

```python
# New endpoints in web_server.py
@app.route('/api/news')
def get_news():
    """Get recent news with sentiment."""
    
@app.route('/api/sentiment')
def get_sentiment():
    """Get aggregate sentiment for timeframe."""
```

## Configuration

Add to `config/settings.json`:

```json
{
  "news": {
    "enabled": true,
    "sources": [
      {
        "name": "coindesk",
        "type": "rss",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "poll_interval_minutes": 5
      }
    ],
    "sentiment": {
      "method": "hybrid",
      "llm_model": "gpt-3.5-turbo",
      "confidence_threshold": 0.7
    },
    "alerts": {
      "breaking_news_enabled": true,
      "high_confidence_only": true
    }
  }
}
```

## Dependencies

```bash
pip install feedparser beautifulsoup4 requests
```

## Testing Plan

1. **Unit Tests:**
   - RSS parsing
   - Sentiment scoring accuracy
   - Database insertion/retrieval

2. **Integration Tests:**
   - Full pipeline: RSS → sentiment → LLM prompt
   - Alert triggering on breaking news

3. **Backtesting:**
   - Collect 1 week of news + price data
   - Evaluate: Did bullish news precede price rises?

## Success Metrics

- News latency: < 5 minutes from publish to analysis
- Sentiment accuracy: >70% correlation with 1h price direction
- Alert relevance: <10% false positive rate

## Future Enhancements

- **Whale Alerts**: Large transaction monitoring
- **Social Sentiment**: Reddit/Twitter volume tracking
- **On-Chain Data**: Exchange inflows/outflows
- **Multi-Language**: Non-English news sources
