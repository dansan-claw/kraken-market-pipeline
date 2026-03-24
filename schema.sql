-- Kraken Market Data Schema
-- SQLite database for storing market snapshots

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    pair TEXT NOT NULL,
    price REAL NOT NULL,
    bid REAL NOT NULL,
    ask REAL NOT NULL,
    spread REAL NOT NULL,
    spread_pct REAL NOT NULL,
    volume_24h REAL NOT NULL,
    high_24h REAL NOT NULL,
    low_24h REAL NOT NULL,
    bid_depth_eth REAL,      -- Total ETH in top 10 bids
    ask_depth_eth REAL,      -- Total ETH in top 10 asks
    bid_count INTEGER,       -- Number of bid levels
    ask_count INTEGER        -- Number of ask levels
);

CREATE INDEX IF NOT EXISTS idx_snapshots_pair_time ON snapshots(pair, timestamp);

CREATE TABLE IF NOT EXISTS market_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    pair TEXT NOT NULL,
    report TEXT NOT NULL,     -- LLM-generated narrative
    raw_data JSON             -- Structured data snapshot
);

CREATE INDEX IF NOT EXISTS idx_reports_pair_time ON market_reports(pair, timestamp);
