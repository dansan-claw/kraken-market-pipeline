#!/usr/bin/env python3
"""
Kraken Market Data Collector
Polls Kraken API every 5 minutes, stores ticker + order book data,
generates LLM-ready market reports.
"""

import sqlite3
import json
import time
import os
import urllib.request
from datetime import datetime
from typing import Dict, Optional

# Database path
DB_PATH = os.environ.get("MARKET_DB_PATH", os.path.expanduser("~/kraken-market-data/market.db"))

# Pairs to track
PAIRS = ["XETHZEUR", "XXBTZEUR"]  # ETH/EUR and BTC/EUR


def init_database():
    """Initialize SQLite database with schema."""
    with sqlite3.connect(DB_PATH) as conn:
        with open(os.path.join(os.path.dirname(__file__), 'schema.sql'), 'r') as f:
            conn.executescript(f.read())
    print(f"Database initialized at {DB_PATH}")


def fetch_ticker(pair: str) -> Optional[Dict]:
    """Fetch ticker data from Kraken public API."""
    try:
        url = f"https://api.kraken.com/0/public/Ticker?pair={pair}"
        response = urllib.request.urlopen(url, timeout=10)
        data = json.loads(response.read().decode())
        
        if 'result' in data and pair in data['result']:
            return data['result'][pair]
        return None
    except Exception as e:
        print(f"Error fetching ticker for {pair}: {e}")
        return None


def fetch_order_book(pair: str, count: int = 10) -> Optional[Dict]:
    """Fetch order book depth from Kraken."""
    try:
        url = f"https://api.kraken.com/0/public/Depth?pair={pair}&count={count}"
        response = urllib.request.urlopen(url, timeout=10)
        data = json.loads(response.read().decode())
        
        if 'result' in data and pair in data['result']:
            return data['result'][pair]
        return None
    except Exception as e:
        print(f"Error fetching order book for {pair}: {e}")
        return None


def analyze_order_book(book: Dict) -> Dict:
    """Calculate metrics from order book data."""
    bids = book.get('bids', [])
    asks = book.get('asks', [])
    
    # Calculate depth (top 10 levels)
    bid_volume = sum(float(b[1]) for b in bids[:10]) if bids else 0
    ask_volume = sum(float(a[1]) for a in asks[:10]) if asks else 0
    
    best_bid = float(bids[0][0]) if bids else 0
    best_ask = float(asks[0][0]) if asks else 0
    
    return {
        'bid_depth_eth': bid_volume,
        'ask_depth_eth': ask_volume,
        'bid_count': len(bids),
        'ask_count': len(asks),
        'best_bid': best_bid,
        'best_ask': best_ask,
        'spread': best_ask - best_bid if best_ask and best_bid else 0,
    }


def collect_snapshot(pair: str) -> Optional[Dict]:
    """Collect complete market snapshot for a pair."""
    ticker = fetch_ticker(pair)
    book = fetch_order_book(pair, count=10)
    
    if not ticker:
        print(f"No ticker data for {pair}")
        return None
    
    # Parse ticker fields
    price = float(ticker['c'][0])  # Current price (last trade)
    bid = float(ticker['b'][0])    # Best bid
    ask = float(ticker['a'][0])    # Best ask
    volume = float(ticker['v'][1]) # 24h volume
    high = float(ticker['h'][1])   # 24h high
    low = float(ticker['l'][1])    # 24h low
    
    spread = ask - bid
    spread_pct = (spread / bid * 100) if bid else 0
    
    # Order book analysis
    book_metrics = analyze_order_book(book) if book else {
        'bid_depth_eth': 0, 'ask_depth_eth': 0,
        'bid_count': 0, 'ask_count': 0
    }
    
    snapshot = {
        'pair': pair,
        'price': price,
        'bid': bid,
        'ask': ask,
        'spread': spread,
        'spread_pct': spread_pct,
        'volume_24h': volume,
        'high_24h': high,
        'low_24h': low,
        'bid_depth_eth': book_metrics['bid_depth_eth'],
        'ask_depth_eth': book_metrics['ask_depth_eth'],
        'bid_count': book_metrics['bid_count'],
        'ask_count': book_metrics['ask_count'],
    }
    
    return snapshot


def store_snapshot(snapshot: Dict):
    """Store snapshot in database."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO snapshots 
            (pair, price, bid, ask, spread, spread_pct, volume_24h, 
             high_24h, low_24h, bid_depth_eth, ask_depth_eth, bid_count, ask_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot['pair'], snapshot['price'], snapshot['bid'], snapshot['ask'],
            snapshot['spread'], snapshot['spread_pct'], snapshot['volume_24h'],
            snapshot['high_24h'], snapshot['low_24h'], snapshot['bid_depth_eth'],
            snapshot['ask_depth_eth'], snapshot['bid_count'], snapshot['ask_count']
        ))
        conn.commit()
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Stored snapshot for {snapshot['pair']}: €{snapshot['price']:.2f}")


def generate_market_report(snapshot: Dict) -> str:
    """Generate LLM-readable market report."""
    pair = snapshot['pair'].replace('XETHZ', '').replace('ZEUR', 'EUR')
    
    # Calculate some context
    price_range = snapshot['high_24h'] - snapshot['low_24h']
    price_position = (snapshot['price'] - snapshot['low_24h']) / price_range * 100 if price_range > 0 else 50
    
    # Order book imbalance (positive = more bids = buying pressure)
    total_depth = snapshot['bid_depth_eth'] + snapshot['ask_depth_eth']
    bid_ratio = snapshot['bid_depth_eth'] / total_depth if total_depth > 0 else 0.5
    
    report = f"""MARKET SNAPSHOT — {datetime.now().strftime('%Y-%m-%d %H:%M CET')}

{pair}: €{snapshot['price']:.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRICE ACTION
• Current: €{snapshot['price']:.2f}
• 24h Range: €{snapshot['low_24h']:.2f} — €{snapshot['high_24h']:.2f}
• Position in range: {price_position:.1f}% (0% = bottom, 100% = top)
• 24h Volume: {snapshot['volume_24h']:,.2f} ETH

ORDER BOOK
• Best Bid: €{snapshot['bid']:.2f} ({snapshot['bid_depth_eth']:.2f} ETH waiting)
• Best Ask: €{snapshot['ask']:.2f} ({snapshot['ask_depth_eth']:.2f} ETH offered)
• Spread: €{snapshot['spread']:.2f} ({snapshot['spread_pct']:.4f}%)
• Bid/Ask Ratio: {bid_ratio:.2f} ({'buying pressure' if bid_ratio > 0.55 else 'selling pressure' if bid_ratio < 0.45 else 'balanced'})

CONTEXT
• Market is {'liquid' if snapshot['spread_pct'] < 0.1 else 'moderately liquid' if snapshot['spread_pct'] < 0.5 else 'illiquid'} (tight spread)
• Price is {'near support' if price_position < 25 else 'near resistance' if price_position > 75 else 'mid-range'}
• Order book shows {'accumulation' if bid_ratio > 0.6 else 'distribution' if bid_ratio < 0.4 else 'choppy activity'}

RAW METRICS (for LLM analysis):
{{"price": {snapshot['price']}, "spread_bps": {snapshot['spread_pct']*100:.2f}, "volume": {snapshot['volume_24h']:.2f}, "bid_ask_ratio": {bid_ratio:.3f}, "range_position": {price_position:.1f}}}
"""
    
    return report


def store_report(snapshot: Dict, report: str):
    """Store LLM-readable report."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO market_reports (pair, report, raw_data)
            VALUES (?, ?, ?)
        """, (snapshot['pair'], report, json.dumps(snapshot)))
        conn.commit()


def run_single_cycle():
    """Run one collection cycle."""
    for pair in PAIRS:
        snapshot = collect_snapshot(pair)
        if snapshot:
            store_snapshot(snapshot)
            report = generate_market_report(snapshot)
            store_report(snapshot, report)
            print(f"\n{report}\n")


def main():
    """Main loop - collect data every 5 minutes."""
    import sys
    
    # Initialize DB if needed
    if not os.path.exists(DB_PATH):
        init_database()
    
    # Check for single-run mode
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        print("Running single collection cycle...")
        run_single_cycle()
        return
    
    print(f"Starting market data collector for {PAIRS}")
    print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            run_single_cycle()
            print("Next poll in 5 minutes...\n")
            time.sleep(300)  # 5 minutes
    except KeyboardInterrupt:
        print("\nStopping collector.")


if __name__ == "__main__":
    main()
