#!/usr/bin/env python3
"""
RSS News Collector for Kraken Pipeline
Fetches crypto news from RSS feeds without external dependencies
"""

import urllib.request
import xml.etree.ElementTree as ET
import sqlite3
import os
from datetime import datetime
from typing import List, Dict

DB_PATH = os.environ.get('MARKET_DB_PATH', os.path.expanduser('~/.openclaw/workspace/kraken-market-data/market.db'))

# RSS Feed URLs
RSS_FEEDS = {
    'coindesk': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
    'cointelegraph': 'https://cointelegraph.com/rss',
    'theblock': 'https://www.theblock.co/rss.xml'
}

def fetch_rss(url: str) -> str:
    """Fetch RSS feed content."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; Bot/0.1)'
        }
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None

def parse_rss(xml_content: str, source: str) -> List[Dict]:
    """Parse RSS XML into article list."""
    articles = []
    try:
        root = ET.fromstring(xml_content)
        
        # Find channel/item structure
        channel = root.find('.//channel')
        if channel is None:
            channel = root
            
        for item in channel.findall('.//item'):
            title = item.findtext('title', '')
            link = item.findtext('link', '')
            description = item.findtext('description', '')
            pub_date = item.findtext('pubDate', '')
            
            articles.append({
                'source': source,
                'title': title,
                'url': link,
                'content': description[:500] if description else '',
                'published_at': pub_date,
                'external_id': link  # Use URL as ID
            })
    except Exception as e:
        print(f"  Error parsing {source}: {e}")
    
    return articles

def analyze_sentiment(text: str) -> str:
    """Simple keyword-based sentiment analysis."""
    text_lower = text.lower()
    
    bullish_keywords = ['bull', 'surge', 'rally', 'moon', 'pump', 'rise', 'up', 'gain', 'breakout', 'ath', 'record', 'soar']
    bearish_keywords = ['bear', 'crash', 'dump', 'fall', 'down', 'decline', 'drop', 'plunge', 'tumble', 'sell-off', 'fear']
    
    bullish_score = sum(1 for kw in bullish_keywords if kw in text_lower)
    bearish_score = sum(1 for kw in bearish_keywords if kw in text_lower)
    
    if bullish_score > bearish_score:
        return 'bullish'
    elif bearish_score > bullish_score:
        return 'bearish'
    else:
        return 'neutral'

def store_articles(articles: List[Dict]):
    """Store articles in database."""
    schema = '''
    CREATE TABLE IF NOT EXISTS news_articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        source TEXT NOT NULL,
        external_id TEXT UNIQUE,
        title TEXT,
        content TEXT,
        url TEXT,
        published_at TEXT,
        category TEXT,
        symbols TEXT,
        sentiment TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_news_source ON news_articles(source);
    CREATE INDEX IF NOT EXISTS idx_news_time ON news_articles(timestamp);
    '''
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(schema)
        
        cursor = conn.cursor()
        for article in articles:
            sentiment = analyze_sentiment(article['title'] + ' ' + article['content'])
            
            # Detect symbols
            text = (article['title'] + ' ' + article['content']).lower()
            symbols = []
            if 'bitcoin' in text or 'btc' in text:
                symbols.append('BTC')
            if 'ethereum' in text or 'eth' in text:
                symbols.append('ETH')
            
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO news_articles 
                    (source, external_id, title, content, url, published_at, category, symbols, sentiment)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    article['source'],
                    article['external_id'],
                    article['title'],
                    article['content'],
                    article['url'],
                    article['published_at'],
                    'news',
                    ','.join(symbols),
                    sentiment
                ))
            except Exception as e:
                print(f"  Error storing article: {e}")
        
        conn.commit()

def collect_rss_news():
    """Main collection loop."""
    print("📰 Collecting RSS news from crypto sources...")
    
    all_articles = []
    for source, url in RSS_FEEDS.items():
        print(f"  Fetching {source}...")
        xml_content = fetch_rss(url)
        if xml_content:
            articles = parse_rss(xml_content, source)
            print(f"    ✓ Found {len(articles)} articles")
            all_articles.extend(articles)
    
    if all_articles:
        store_articles(all_articles)
        print(f"\n✓ Stored {len(all_articles)} articles")
        
        # Show sample
        print("\n📋 Sample articles:")
        for i, article in enumerate(all_articles[:5], 1):
            sentiment_emoji = {'bullish': '🟢', 'bearish': '🔴', 'neutral': '⚪'}[article.get('sentiment', 'neutral')]
            print(f"\n{i}. {sentiment_emoji} [{article['source'].upper()}] {article['title'][:80]}...")
            print(f"   {article['url'][:70]}...")
    else:
        print("\n✗ No articles fetched")

if __name__ == '__main__':
    collect_rss_news()
