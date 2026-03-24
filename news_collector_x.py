#!/usr/bin/env python3
"""
X/Twitter News Collector for Kraken Pipeline
Uses xurl skill with Bearer Token authentication
"""

import subprocess
import json
import sqlite3
import os
from datetime import datetime
from typing import List, Dict

DB_PATH = os.environ.get('MARKET_DB_PATH', os.path.expanduser('~/.openclaw/workspace/kraken-market-data/market.db'))

# Search queries for crypto sentiment
CRYPTO_QUERIES = [
    "bitcoin BTC",
    "ethereum ETH",
    "crypto bullish",
    "crypto bearish",
    "crypto crash",
    "crypto moon",
    "altseason"
]

def init_news_tables():
    """Initialize news tables in database."""
    schema = '''
    CREATE TABLE IF NOT EXISTS news_articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        source TEXT NOT NULL,
        external_id TEXT,
        title TEXT,
        content TEXT,
        url TEXT,
        published_at DATETIME,
        category TEXT,
        symbols TEXT,
        sentiment TEXT,
        raw_json TEXT
    );
    
    CREATE INDEX IF NOT EXISTS idx_news_time ON news_articles(timestamp);
    CREATE INDEX IF NOT EXISTS idx_news_symbols ON news_articles(symbols);
    '''
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(schema)

def fetch_x_posts(query: str, count: int = 10) -> List[Dict]:
    """Fetch posts from X using xurl."""
    try:
        result = subprocess.run(
            ['xurl', 'search', query, '-n', str(count)],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get('data', [])
        else:
            print(f"xurl error: {result.stderr}")
            return []
    except Exception as e:
        print(f"Failed to fetch from X: {e}")
        return []

def analyze_sentiment(text: str) -> str:
    """Simple keyword-based sentiment analysis."""
    text_lower = text.lower()
    
    bullish_keywords = ['bull', 'moon', 'pump', 'rise', 'up', 'green', 'breakout', 'ath']
    bearish_keywords = ['bear', 'crash', 'dump', 'fall', 'down', 'red', 'correction', 'bearish']
    
    bullish_score = sum(1 for kw in bullish_keywords if kw in text_lower)
    bearish_score = sum(1 for kw in bearish_keywords if kw in text_lower)
    
    if bullish_score > bearish_score:
        return 'bullish'
    elif bearish_score > bullish_score:
        return 'bearish'
    else:
        return 'neutral'

def store_article(article: Dict, query: str):
    """Store article in database."""
    text = article.get('text', '')
    sentiment = analyze_sentiment(text)
    
    # Detect symbols mentioned
    symbols = []
    if 'bitcoin' in text.lower() or 'btc' in text.lower():
        symbols.append('BTC')
    if 'ethereum' in text.lower() or 'eth' in text.lower():
        symbols.append('ETH')
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO news_articles 
            (source, external_id, content, published_at, category, symbols, sentiment, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'x',
            article.get('id'),
            text[:500],  # Truncate for storage
            article.get('created_at'),
            'social',
            ','.join(symbols) if symbols else '',
            sentiment,
            json.dumps(article)
        ))
        conn.commit()

def collect_news():
    """Main collection loop."""
    print("🐦 Collecting X/Twitter posts for sentiment analysis...")
    init_news_tables()
    
    total_collected = 0
    for query in CRYPTO_QUERIES:
        print(f"  Searching: {query}")
        posts = fetch_x_posts(query, count=10)
        for post in posts:
            store_article(post, query)
            total_collected += 1
    
    print(f"✓ Collected {total_collected} posts")

if __name__ == '__main__':
    collect_news()
