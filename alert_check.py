#!/usr/bin/env python3
"""
Market Alert Checker
Runs every 5 minutes, checks for significant price moves,
outputs alert only if threshold breached.
"""

import sqlite3
import os
import json
from datetime import datetime, timedelta

DB_PATH = os.environ.get("MARKET_DB_PATH", os.path.expanduser("~/kraken-market-data/market.db"))
THRESHOLD_PCT = 3.0  # Alert if price moves >3%


def check_alerts():
    """Check for significant price movements."""
    if not os.path.exists(DB_PATH):
        return None
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    alerts = []
    
    for pair in ["XETHZEUR", "XXBTZEUR"]:
        # Get latest two snapshots
        cursor.execute("""
            SELECT price, timestamp FROM snapshots
            WHERE pair = ?
            ORDER BY timestamp DESC
            LIMIT 2
        """, (pair,))
        
        rows = cursor.fetchall()
        if len(rows) < 2:
            continue
        
        latest_price, latest_ts = rows[0]
        prev_price, prev_ts = rows[1]
        
        if prev_price == 0:
            continue
        
        change_pct = ((latest_price - prev_price) / prev_price) * 100
        
        if abs(change_pct) >= THRESHOLD_PCT:
            direction = "📈 UP" if change_pct > 0 else "📉 DOWN"
            alerts.append({
                "pair": pair,
                "direction": direction,
                "change_pct": abs(change_pct),
                "latest_price": latest_price,
                "prev_price": prev_price,
                "timestamp": latest_ts
            })
    
    conn.close()
    return alerts


def main():
    """Main entry point."""
    alerts = check_alerts()
    
    if alerts:
        for alert in alerts:
            pair_clean = alert["pair"].replace("X", "").replace("Z", "/")
            print(f"🚨 MARKET ALERT: {pair_clean} {alert['direction']} {alert['change_pct']:.2f}%")
            print(f"   Price: €{alert['prev_price']:.2f} → €{alert['latest_price']:.2f}")
            print(f"   Time: {alert['timestamp']}")
            print(f"   Action: Evaluate paper trade entry per HEARTBEAT.md criteria")
            print(f"   Log to: memory/market-paper-trades.md")
        # Exit with code 0 but output the alert
        return 0
    else:
        # Silent - no significant moves
        return 0


if __name__ == "__main__":
    exit(main())
