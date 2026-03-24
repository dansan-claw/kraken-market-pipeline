#!/usr/bin/env python3
"""
View latest market reports or query historical data.
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = os.environ.get("MARKET_DB_PATH", os.path.expanduser("~/kraken-market-data/market.db"))


def get_latest_report():
    """Get the most recent market report."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM market_reports
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        
        if row:
            print(f"Report from {row['timestamp']}")
            print(f"Pair: {row['pair']}")
            print("\n" + "="*60)
            print(row['report'])
            print("="*60)
        else:
            print("No reports found. Run collector.py first.")


def get_recent_snapshots(hours: int = 24):
    """Get recent price history."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM snapshots
            WHERE timestamp > datetime('now', '-{} hours')
            ORDER BY timestamp DESC
        """.format(hours))
        
        rows = cursor.fetchall()
        
        if not rows:
            print(f"No snapshots in last {hours} hours.")
            return
        
        print(f"\nLast {len(rows)} snapshots (past {hours}h):\n")
        print(f"{'Time':>12} {'Price':>12} {'Spread%':>10} {'Vol(24h)':>12}")
        print("-" * 50)
        
        for row in rows:
            print(f"{row['timestamp']:%H:%M} {row['price']:>12.2f} {row['spread_pct']:>10.4f} {row['volume_24h']:>12.2f}")


def get_stats():
    """Show database statistics."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Count snapshots
        cursor.execute("SELECT COUNT(*) FROM snapshots")
        snap_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM market_reports")
        report_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM snapshots")
        min_ts, max_ts = cursor.fetchone()
        
        print(f"\nDatabase Statistics")
        print("="*40)
        print(f"Snapshots: {snap_count}")
        print(f"Reports: {report_count}")
        print(f"Time range: {min_ts} to {max_ts}")


if __name__ == "__main__":
    import sys
    
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        print("Run collector.py first to initialize.")
        exit(1)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "latest":
            get_latest_report()
        elif sys.argv[1] == "history":
            hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
            get_recent_snapshots(hours)
        elif sys.argv[1] == "stats":
            get_stats()
        else:
            print("Usage: view_report.py [latest|history [hours]|stats]")
    else:
        get_latest_report()
