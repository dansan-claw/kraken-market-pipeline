#!/usr/bin/env python3
"""
LLM-Enhanced Market Analyzer
Uses pandas + Ollama models to analyze trends and generate insights.
"""

import sqlite3
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import subprocess

DB_PATH = os.environ.get("MARKET_DB_PATH", os.path.expanduser("~/kraken-market-data/market.db"))


def query_with_pandas(query: str, params: tuple = ()) -> List[Dict]:
    """Execute SQL and return list of dicts."""
    import sqlite3
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def analyze_pair(pair: str, hours: int = 24) -> Dict:
    """Analyze market data using pandas-like aggregations."""
    
    # Price statistics
    price_stats = query_with_pandas("""
        SELECT 
            COUNT(*) as sample_count,
            MIN(price) as min_price,
            MAX(price) as max_price,
            AVG(price) as avg_price,
            AVG(volume_24h) as avg_volume,
            MIN(spread_pct) as min_spread,
            MAX(spread_pct) as max_spread,
            AVG(bid_depth_eth) as avg_bid_depth,
            AVG(ask_depth_eth) as avg_ask_depth
        FROM snapshots
        WHERE pair = ? AND timestamp > datetime('now', '-{} hours')
    """.format(hours), (pair,))
    
    if not price_stats:
        return {"error": "No data found"}
    
    stats = price_stats[0]
    
    # Recent trend (last hour vs hour before)
    recent = query_with_pandas("""
        SELECT price FROM snapshots 
        WHERE pair = ? AND timestamp > datetime('now', '-1 hours')
        ORDER BY timestamp DESC
        LIMIT 1
    """, (pair,))
    
    previous = query_with_pandas("""
        SELECT price FROM snapshots 
        WHERE pair = ? AND timestamp BETWEEN datetime('now', '-2 hours') AND datetime('now', '-1 hours')
        ORDER BY timestamp DESC
        LIMIT 1
    """, (pair,))
    
    trend = "neutral"
    if recent and previous:
        change = (recent[0]['price'] - previous[0]['price']) / previous[0]['price'] * 100
        if abs(change) < 0.1:
            trend = "neutral"
        elif change > 0:
            trend = f"rising (+{change:.2f}%)"
        else:
            trend = f"falling ({change:.2f}%)"
    
    # Volatility (std dev of price changes)
    prices = query_with_pandas("""
        SELECT price, timestamp FROM snapshots
        WHERE pair = ? AND timestamp > datetime('now', '-{} hours')
        ORDER BY timestamp
    """.format(hours), (pair,))
    
    volatility = 0
    if len(prices) > 1:
        changes = []
        for i in range(1, len(prices)):
            pct_change = (prices[i]['price'] - prices[i-1]['price']) / prices[i-1]['price'] * 100
            changes.append(pct_change)
        volatility = sum(c**2 for c in changes) / len(changes) ** 0.5 if changes else 0
    
    # Current snapshot
    current = query_with_pandas("""
        SELECT * FROM snapshots
        WHERE pair = ?
        ORDER BY timestamp DESC
        LIMIT 1
    """, (pair,))
    
    return {
        "pair": pair,
        "analysis_period": f"{hours}h",
        "samples": stats['sample_count'],
        "current_price": current[0]['price'] if current else None,
        "price_range": {
            "min": stats['min_price'],
            "max": stats['max_price'],
            "avg": round(stats['avg_price'], 2) if stats['avg_price'] else None
        },
        "trend": trend,
        "volatility_index": round(volatility, 4),
        "liquidity": {
            "avg_spread_bps": round(stats['min_spread'] * 100, 2) if stats['min_spread'] else None,
            "bid_depth_avg": round(stats['avg_bid_depth'], 2) if stats['avg_bid_depth'] else None,
            "ask_depth_avg": round(stats['avg_ask_depth'], 2) if stats['avg_ask_depth'] else None
        },
        "volume_24h_avg": round(stats['avg_volume'], 2) if stats['avg_volume'] else None
    }


def get_previous_analysis(pair: str) -> Optional[Dict]:
    """Get the previous LLM analysis for this pair."""
    results = query_with_pandas("""
        SELECT timestamp, llm_insight, raw_analysis 
        FROM llm_analyses 
        WHERE pair = ? 
        ORDER BY timestamp DESC 
        LIMIT 2
    """, (pair,))
    
    if len(results) >= 2:
        return results[1]  # Second most recent (skip the latest)
    return None


def get_recent_news(pair: str, hours: int = 6) -> List[Dict]:
    """Fetch recent news affecting the pair."""
    symbol = pair.replace('X', '').replace('Z', '').replace('EUR', '')
    return query_with_pandas("""
        SELECT source, title, content, sentiment, timestamp 
        FROM news_articles
        WHERE symbols LIKE ?
          AND timestamp > datetime('now', '-{} hours')
        ORDER BY timestamp DESC
        LIMIT 5
    """.format(hours), (f'%{symbol}%',))


def generate_llm_prompt(analysis: Dict, previous: Optional[Dict] = None) -> str:
    """Generate prompt for LLM analysis with historical context and news."""
    pair = analysis['pair'].replace('X', '').replace('Z', '/')
    
    # Build previous analysis context if available
    previous_context = ""
    if previous:
        prev_time = previous['timestamp']
        prev_raw = json.loads(previous['raw_analysis']) if isinstance(previous['raw_analysis'], str) else previous['raw_analysis']
        prev_price = prev_raw.get('current_price', 'unknown')
        # Shorter excerpt to keep prompt small
        prev_insight = previous['llm_insight'][:100] + "..." if len(previous['llm_insight']) > 100 else previous['llm_insight']
        previous_context = f"""

PREVIOUS ({prev_time}): €{prev_price} — {prev_insight}

Compare: what's changed?"""
    
    # Fetch recent news
    news = get_recent_news(analysis['pair'], hours=6)
    news_context = ""
    if news:
        news_context = "\n\nRECENT NEWS (last 6h):\n"
        for n in news:
            sentiment_emoji = {'bullish': '🟢', 'bearish': '🔴', 'neutral': '⚪'}.get(n.get('sentiment', 'neutral'), '⚪')
            news_context += f"- {sentiment_emoji} [{n['source'].upper()}] {n['title'][:80]}...\n"
    
    return f"""Analyze this cryptocurrency market data and provide a brief trading assessment:

PAIR: {pair}
PERIOD: {analysis['analysis_period']}

PRICE METRICS:
- Current: €{analysis['current_price']}
- Range: €{analysis['price_range']['min']} - €{analysis['price_range']['max']}
- Average: €{analysis['price_range']['avg']}
- Trend: {analysis['trend']}

MARKET HEALTH:
- Volatility Index: {analysis['volatility_index']} (lower = more stable)
- Avg Spread: {analysis['liquidity']['avg_spread_bps']} bps (lower = more liquid)
- 24h Volume: {analysis['volume_24h_avg']} {pair.split('/')[0]}
{previous_context}{news_context}

Provide a 2-3 sentence assessment covering:
1. Price action and trend strength
2. Market liquidity and volatility
3. How this compares to the previous assessment (if shown above)
4. How the recent news sentiment might impact price direction
5. Brief outlook or risk level

Respond in a direct, professional tone suitable for a trader."""


def query_ollama(prompt: str, model: str = "kimi-k2.5:cloud") -> str:
    """Query Ollama API for analysis."""
    try:
        curl_cmd = [
            "curl", "-s", "-X", "POST",
            "http://127.0.0.1:11435/api/generate",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3}
            })
        ]
        
        result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=60)
        response = json.loads(result.stdout)
        return response.get('response', 'Error: No response from model')
    except Exception as e:
        return f"Error querying Ollama: {e}"


def store_llm_analysis(pair: str, analysis: Dict, llm_insight: str):
    """Store enriched analysis with LLM insight."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llm_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                pair TEXT NOT NULL,
                raw_analysis JSON,
                llm_insight TEXT
            )
        """)
        cursor.execute("""
            INSERT INTO llm_analyses (pair, raw_analysis, llm_insight)
            VALUES (?, ?, ?)
        """, (pair, json.dumps(analysis), llm_insight))
        conn.commit()


def run_analysis(pair: str = "XETHZEUR", use_llm: bool = True):
    """Run full analysis pipeline."""
    print(f"\n{'='*60}")
    print(f"MARKET ANALYSIS: {pair}")
    print('='*60)
    
    # Pandas-style analysis
    analysis = analyze_pair(pair)
    
    if "error" in analysis:
        print(f"Error: {analysis['error']}")
        return
    
    # Display raw metrics
    print(f"\n📊 RAW METRICS:")
    print(f"  Current Price: €{analysis['current_price']}")
    price_min = analysis['price_range']['min']
    price_max = analysis['price_range']['max']
    if price_min and price_max:
        print(f"  24h Range: €{price_min:.2f} - €{price_max:.2f}")
    else:
        print(f"  24h Range: (insufficient data)")
    print(f"  Trend: {analysis['trend']}")
    print(f"  Volatility: {analysis['volatility_index']}")
    spread_bps = analysis['liquidity']['avg_spread_bps']
    print(f"  Liquidity Score: {spread_bps:.2f} bps" if spread_bps else "  Liquidity Score: N/A")
    
    # Display news context if available
    recent_news = get_recent_news(pair, hours=6)
    if recent_news:
        print(f"\n📰 RECENT NEWS:")
        for n in recent_news[:3]:
            sentiment_emoji = {'bullish': '🟢', 'bearish': '🔴', 'neutral': '⚪'}.get(n.get('sentiment', 'neutral'), '⚪')
            print(f"  {sentiment_emoji} [{n['source'].upper()}] {n['title'][:60]}...")
    else:
        print(f"\n📰 RECENT NEWS: No news in last 6h")
    
    if use_llm:
        print(f"\n🤖 Querying Ollama for LLM insights...")
        
        # Get previous analysis for context
        previous = get_previous_analysis(pair)
        if previous:
            print(f"  (Comparing with previous analysis from {previous['timestamp']})")
        
        prompt = generate_llm_prompt(analysis, previous)
        insight = query_ollama(prompt)
        
        print(f"\n💡 LLM ANALYSIS:")
        print(insight)
        
        # Store for later
        store_llm_analysis(pair, analysis, insight)
        print(f"\n✓ Analysis stored in database")
    
    print(f"\n{'='*60}\n")


def view_llm_history(pair: str = None, limit: int = 5):
    """View recent LLM analyses."""
    query = """
        SELECT timestamp, pair, llm_insight 
        FROM llm_analyses
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT ?
    """.format(where_clause=f"WHERE pair = '{pair}'" if pair else "")
    
    results = query_with_pandas(query, (limit,))
    
    if not results:
        print("No LLM analyses found.")
        return
    
    print(f"\n📜 RECENT LLM ANALYSES ({len(results)} total):\n")
    for r in results:
        clean_pair = r['pair'].replace('X', '').replace('Z', '/')
        print(f"{r['timestamp']} | {clean_pair}")
        print(f"{'-'*50}")
        print(r['llm_insight'][:200] + "..." if len(r['llm_insight']) > 200 else r['llm_insight'])
        print()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "analyze":
            pair = sys.argv[2] if len(sys.argv) > 2 else "XETHZEUR"
            run_analysis(pair)
        elif sys.argv[1] == "history":
            pair = sys.argv[2] if len(sys.argv) > 2 else None
            view_llm_history(pair)
        else:
            print("Usage: analyzer.py [analyze [pair]|history [pair]]")
    else:
        # Default: analyze both pairs
        for p in ["XETHZEUR", "XXBTZEUR"]:
            run_analysis(p)
