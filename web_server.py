#!/usr/bin/env python3
"""
Kraken Market Data Pipeline - Web GUI
Port: 8890
Features: Price charts, LLM analysis history, paper wallet activity log
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler

DB_PATH = os.environ.get("MARKET_DB_PATH", os.path.expanduser("~/kraken-market-data/market.db"))

class KrakenHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        if path == '/':
            self.serve_dashboard()
        elif path == '/api/prices':
            self.serve_prices(query)
        elif path == '/api/analyses':
            self.serve_analyses(query)
        elif path == '/api/paper-trades':
            self.serve_paper_trades()
        elif path == '/api/stats':
            self.serve_stats()
        else:
            self.send_error(404)
    
    def query_db(self, query, params=()):
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def serve_dashboard(self):
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kraken Market Data Pipeline</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5rem;
            background: linear-gradient(90deg, #00d4aa, #00a8e8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
        }
        .card h2 {
            font-size: 1.2rem;
            margin-bottom: 15px;
            color: #00d4aa;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .price-display {
            display: flex;
            justify-content: space-around;
            margin-bottom: 20px;
        }
        .price-box {
            text-align: center;
            padding: 15px;
            background: rgba(0,0,0,0.2);
            border-radius: 12px;
            min-width: 150px;
        }
        .price-box .label {
            font-size: 0.85rem;
            color: #888;
            margin-bottom: 5px;
        }
        .price-box .value {
            font-size: 1.8rem;
            font-weight: bold;
        }
        .price-box .change {
            font-size: 0.9rem;
            margin-top: 5px;
        }
        .positive { color: #00d4aa; }
        .negative { color: #ff6b6b; }
        .neutral { color: #888; }
        .chart-container {
            height: 300px;
            position: relative;
        }
        .analysis-item {
            padding: 15px;
            margin-bottom: 10px;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            border-left: 3px solid #00d4aa;
        }
        .analysis-item.btc { border-left-color: #f7931a; }
        .analysis-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.85rem;
            color: #888;
        }
        .analysis-content {
            font-size: 0.95rem;
            line-height: 1.5;
        }
        .analysis-item:hover {
            background: rgba(0, 212, 170, 0.1);
            cursor: pointer;
        }
        #analyses-container::-webkit-scrollbar {
            width: 8px;
        }
        #analyses-container::-webkit-scrollbar-track {
            background: rgba(0,0,0,0.2);
            border-radius: 4px;
        }
        #analyses-container::-webkit-scrollbar-thumb {
            background: #00d4aa;
            border-radius: 4px;
        }
        #analyses-container::-webkit-scrollbar-thumb:hover {
            background: #00a8e8;
        }
        .paper-trade-item {
            padding: 12px;
            margin-bottom: 8px;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .paper-trade-item.action {
            border-left: 3px solid #00d4aa;
        }
        .paper-trade-item.no-action {
            border-left: 3px solid #666;
        }
        .trade-time {
            font-size: 0.8rem;
            color: #888;
        }
        .trade-pair {
            font-weight: bold;
            color: #00a8e8;
        }
        .trade-status {
            font-size: 0.85rem;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            text-align: center;
        }
        .stat-box {
            padding: 15px;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
        }
        .stat-value {
            font-size: 1.5rem;
            font-weight: bold;
            color: #00d4aa;
        }
        .stat-label {
            font-size: 0.8rem;
            color: #888;
            margin-top: 5px;
        }
        .refresh-indicator {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 20px;
            background: rgba(0,212,170,0.2);
            border: 1px solid #00d4aa;
            border-radius: 8px;
            font-size: 0.85rem;
        }
        .wallet-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 20px;
            text-align: center;
        }
        .wallet-stat {
            padding: 20px;
            background: rgba(0,0,0,0.2);
            border-radius: 12px;
        }
        .wallet-label {
            font-size: 0.85rem;
            color: #888;
            margin-bottom: 8px;
        }
        .wallet-value {
            font-size: 1.8rem;
            font-weight: bold;
            color: #00d4aa;
        }
        .wallet-value.neutral { color: #888; }
        .wallet-value.negative { color: #ff6b6b; }
        .wallet-activity-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 0;
            margin-top: 15px;
            border-top: 1px solid rgba(255,255,255,0.1);
            font-weight: bold;
            color: #00d4aa;
        }
        .wallet-activity {
            max-height: 200px;
            overflow-y: auto;
            background: rgba(0,0,0,0.1);
            border-radius: 8px;
            padding: 10px;
        }
        .activity-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 12px;
            margin-bottom: 8px;
            background: rgba(0,0,0,0.15);
            border-radius: 6px;
            border-left: 3px solid #00d4aa;
        }
        .activity-item.no-action {
            border-left-color: #666;
        }
        .activity-item.entry {
            border-left-color: #00d4aa;
            background: rgba(0, 212, 170, 0.1);
        }
        .activity-item.exit {
            border-left-color: #f7931a;
            background: rgba(247, 147, 26, 0.1);
        }
        .activity-info {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .activity-time {
            font-size: 0.75rem;
            color: #888;
        }
        .activity-action {
            font-weight: bold;
            font-size: 0.9rem;
        }
        .activity-reason {
            font-size: 0.85rem;
            color: #aaa;
            text-align: right;
            max-width: 60%;
        }
        .wallet-activity::-webkit-scrollbar {
            width: 6px;
        }
        .wallet-activity::-webkit-scrollbar-track {
            background: rgba(0,0,0,0.2);
            border-radius: 3px;
        }
        .wallet-activity::-webkit-scrollbar-thumb {
            background: #00d4aa;
            border-radius: 3px;
        }
        .wallet-activity::-webkit-scrollbar-thumb:hover {
            background: #00a8e8;
        }
        .wallet-assets {
            display: flex;
            flex-direction: column;
            gap: 10px;
            padding-top: 15px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }
        .asset-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 15px;
            background: rgba(0,0,0,0.15);
            border-radius: 8px;
        }
        .asset-name {
            font-weight: bold;
            color: #00a8e8;
            min-width: 60px;
        }
        .asset-amount {
            flex: 1;
            text-align: center;
            font-family: monospace;
        }
        .asset-percent {
            color: #888;
            min-width: 50px;
            text-align: right;
        }
        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .wallet-grid { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🦉 Kraken Market Intelligence</h1>
        
        <div class="refresh-indicator">
            Auto-refresh: <span id="countdown">30</span>s
        </div>
        
        <!-- Stats Overview -->
        <div class="card">
            <h2>📊 Pipeline Stats</h2>
            <div class="stats-grid" id="stats-container">
                <div class="stat-box">
                    <div class="stat-value" id="total-snapshots">-</div>
                    <div class="stat-label">Total Snapshots</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="total-analyses">-</div>
                    <div class="stat-label">LLM Analyses</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="paper-trades">-</div>
                    <div class="stat-label">Paper Trades</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="uptime">-</div>
                    <div class="stat-label">Hours Running</div>
                </div>
            </div>
        </div>
        
        <!-- Live Prices -->
        <div class="card">
            <h2>💰 Live Prices</h2>
            <div class="price-display" id="prices-container">
                <div class="price-box">
                    <div class="label">BTC/EUR</div>
                    <div class="value" id="btc-price">-</div>
                    <div class="change" id="btc-change">-</div>
                </div>
                <div class="price-box">
                    <div class="label">ETH/EUR</div>
                    <div class="value" id="eth-price">-</div>
                    <div class="change" id="eth-change">-</div>
                </div>
            </div>
        </div>
        
        <!-- Paper Wallet -->
        <div class="card">
            <h2>💼 Paper Wallet</h2>
            <div class="wallet-grid">
                <div class="wallet-stat">
                    <div class="wallet-label">Starting Balance</div>
                    <div class="wallet-value" id="wallet-start">€9.37</div>
                </div>
                <div class="wallet-stat">
                    <div class="wallet-label">Current Value</div>
                    <div class="wallet-value" id="wallet-current">€9.37</div>
                </div>
                <div class="wallet-stat">
                    <div class="wallet-label">Unrealized P&L</div>
                    <div class="wallet-value neutral" id="wallet-pnl">€0.00 (0.00%)</div>
                </div>
                <div class="wallet-stat">
                    <div class="wallet-label">Trades Made</div>
                    <div class="wallet-value" id="wallet-trades">0</div>
                </div>
            </div>
            <div class="wallet-assets">
                <div class="asset-item">
                    <span class="asset-name">EUR</span>
                    <span class="asset-amount">€9.37</span>
                    <span class="asset-percent">100%</span>
                </div>
                <div class="asset-item">
                    <span class="asset-name">BTC</span>
                    <span class="asset-amount">0.00000</span>
                    <span class="asset-percent">0%</span>
                </div>
                <div class="asset-item">
                    <span class="asset-name">ETH</span>
                    <span class="asset-amount">0.00000</span>
                    <span class="asset-percent">0%</span>
                </div>
            </div>
            <div class="wallet-activity-header">
                <span>📝 Activity Log</span>
                <span style="color: #888; font-size: 0.8rem;">Scroll for history →</span>
            </div>
            <div class="wallet-activity" id="paper-trades-container">
                <div class="activity-item no-action">
                    <div class="activity-info">
                        <span class="activity-time">09:00 CET</span>
                        <span class="activity-action">NO_ACTION</span>
                    </div>
                    <span class="activity-reason">No &gt;3% move detected</span>
                </div>
                <p style="text-align:center;color:#888;padding:20px;">Waiting for &gt;3% moves to trigger paper trades...</p>
            </div>
        </div>
        
        <div class="grid">
            <!-- Price Charts -->
            <div class="card">
                <h2>📈 Price History (24h)</h2>
                <div class="chart-container">
                    <canvas id="priceChart"></canvas>
                </div>
            </div>
            
            <!-- LLM Analyses -->
            <div class="card" style="max-height: 400px; display: flex; flex-direction: column;">
                <h2>🤖 LLM Analyses History</h2>
                <div id="analyses-container" style="flex: 1; overflow-y: auto; max-height: 320px;">
                    <p style="text-align:center;color:#888;padding:20px;">Loading analyses...</p>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let priceChart;
        
        function formatPrice(price) {
            return '€' + price.toLocaleString('de-DE', {minimumFractionDigits: 2, maximumFractionDigits: 2});
        }
        
        function formatChange(change) {
            const sign = change >= 0 ? '+' : '';
            return `<span class="${change >= 0 ? 'positive' : 'negative'}">${sign}${change.toFixed(2)}%</span>`;
        }
        
        async function fetchStats() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                
                document.getElementById('total-snapshots').textContent = stats.total_snapshots.toLocaleString();
                document.getElementById('total-analyses').textContent = stats.total_analyses.toLocaleString();
                document.getElementById('paper-trades').textContent = stats.paper_trades.toLocaleString();
                document.getElementById('uptime').textContent = stats.uptime_hours.toFixed(1);
            } catch (e) {
                console.error('Failed to fetch stats:', e);
            }
        }
        
        async function fetchPrices() {
            try {
                const response = await fetch('/api/prices?hours=24');
                const data = await response.json();
                
                // Update current prices
                const btc = data.btc[data.btc.length - 1];
                const eth = data.eth[data.eth.length - 1];
                
                document.getElementById('btc-price').textContent = formatPrice(btc.price);
                document.getElementById('eth-price').textContent = formatPrice(eth.price);
                
                // Calculate 24h change
                const btc24h = data.btc[0];
                const eth24h = data.eth[0];
                
                const btcChange = ((btc.price - btc24h.price) / btc24h.price) * 100;
                const ethChange = ((eth.price - eth24h.price) / eth24h.price) * 100;
                
                document.getElementById('btc-change').innerHTML = formatChange(btcChange);
                document.getElementById('eth-change').innerHTML = formatChange(ethChange);
                
                // Update chart
                updateChart(data);
            } catch (e) {
                console.error('Failed to fetch prices:', e);
            }
        }
        
        function updateChart(data) {
            const ctx = document.getElementById('priceChart').getContext('2d');
            
            const labels = data.btc.map(d => new Date(d.timestamp).toLocaleTimeString('de-DE', {hour: '2-digit', minute: '2-digit'}));
            
            // Normalize prices for dual-axis display
            const btcPrices = data.btc.map(d => d.price);
            const ethPrices = data.eth.map(d => d.price);
            
            if (priceChart) {
                priceChart.destroy();
            }
            
            priceChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'BTC/EUR',
                            data: btcPrices,
                            borderColor: '#f7931a',
                            backgroundColor: 'rgba(247, 147, 26, 0.1)',
                            tension: 0.4,
                            yAxisID: 'y-btc'
                        },
                        {
                            label: 'ETH/EUR',
                            data: ethPrices,
                            borderColor: '#00d4aa',
                            backgroundColor: 'rgba(0, 212, 170, 0.1)',
                            tension: 0.4,
                            yAxisID: 'y-eth'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    plugins: {
                        legend: {
                            labels: { color: '#e0e0e0' }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#888', maxTicksLimit: 8 }
                        },
                        'y-btc': {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            ticks: { color: '#f7931a' },
                            title: { display: true, text: 'BTC Price', color: '#f7931a' }
                        },
                        'y-eth': {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            ticks: { color: '#00d4aa' },
                            title: { display: true, text: 'ETH Price', color: '#00d4aa' },
                            grid: { drawOnChartArea: false }
                        }
                    }
                }
            });
        }
        
        async function fetchAnalyses() {
            try {
                const response = await fetch('/api/analyses?limit=100');
                const analyses = await response.json();
                
                const container = document.getElementById('analyses-container');
                container.innerHTML = '';
                
                if (analyses.length === 0) {
                    container.innerHTML = '<p style="text-align:center;color:#888;padding:20px;">No analyses yet. Running hourly...</p>';
                    return;
                }
                
                analyses.forEach(a => {
                    const div = document.createElement('div');
                    div.className = `analysis-item ${a.pair.includes('BTC') ? 'btc' : ''}`;
                    div.innerHTML = `
                        <div class="analysis-header">
                            <span>${a.pair.replace('X', '').replace('Z', '/')}</span>
                            <span>${new Date(a.timestamp).toLocaleString('de-DE')}</span>
                        </div>
                        <div class="analysis-content">${a.insight}</div>
                    `;
                    container.appendChild(div);
                });
            } catch (e) {
                console.error('Failed to fetch analyses:', e);
            }
        }
        
        async function fetchPaperTrades() {
            try {
                const response = await fetch('/api/paper-trades');
                const trades = await response.json();
                
                const container = document.getElementById('paper-trades-container');
                container.innerHTML = '';
                
                if (trades.length === 0) {
                    container.innerHTML = '<p style="text-align:center;color:#888;padding:20px;">No paper trades yet. Waiting for >3% moves or clear signals...</p>';
                    return;
                }
                
                trades.forEach(t => {
                    const div = document.createElement('div');
                    div.className = `paper-trade-item ${t.action === 'NO_ACTION' ? 'no-action' : 'action'}`;
                    div.innerHTML = `
                        <div>
                            <span class="trade-time">${new Date(t.timestamp).toLocaleString('de-DE')}</span>
                            <div><span class="trade-pair">${t.pair}</span> — ${t.action}</div>
                        </div>
                        <div class="trade-status">${t.reason}</div>
                    `;
                    container.appendChild(div);
                });
            } catch (e) {
                console.error('Failed to fetch paper trades:', e);
            }
        }
        
        function refreshAll() {
            fetchStats();
            fetchPrices();
            fetchAnalyses();
            fetchPaperTrades();
        }
        
        // Countdown timer
        let countdown = 30;
        setInterval(() => {
            countdown--;
            if (countdown <= 0) {
                countdown = 30;
                refreshAll();
            }
            document.getElementById('countdown').textContent = countdown;
        }, 1000);
        
        // Initial load
        refreshAll();
    </script>
</body>
</html>"""
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def serve_prices(self, query):
        hours = int(query.get('hours', ['24'])[0])
        since = datetime.now() - timedelta(hours=hours)
        
        btc_data = self.query_db("""
            SELECT price, timestamp FROM snapshots 
            WHERE pair = 'XXBTZEUR' AND timestamp > ?
            ORDER BY timestamp ASC
        """, (since.isoformat(),))
        
        eth_data = self.query_db("""
            SELECT price, timestamp FROM snapshots 
            WHERE pair = 'XETHZEUR' AND timestamp > ?
            ORDER BY timestamp ASC
        """, (since.isoformat(),))
        
        self.send_json({'btc': btc_data, 'eth': eth_data})
    
    def serve_analyses(self, query):
        limit = int(query.get('limit', ['5'])[0])
        
        analyses = self.query_db("""
            SELECT pair, timestamp, llm_insight as insight
            FROM llm_analyses
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        self.send_json(analyses)
    
    def serve_paper_trades(self):
        # For now, return empty or read from heartbeat log if available
        # This would need a table in the DB to store heartbeat decisions
        trades = []  # Placeholder - would query paper_trades table
        self.send_json(trades)
    
    def serve_stats(self):
        snapshots = self.query_db("SELECT COUNT(*) as count FROM snapshots")[0]['count']
        analyses = self.query_db("SELECT COUNT(*) as count FROM llm_analyses")[0]['count']
        
        # Calculate uptime from first snapshot
        first = self.query_db("SELECT MIN(timestamp) as first FROM snapshots")
        if first[0]['first']:
            first_time = datetime.fromisoformat(first[0]['first'])
            uptime_hours = (datetime.now() - first_time).total_seconds() / 3600
        else:
            uptime_hours = 0
        
        stats = {
            'total_snapshots': snapshots,
            'total_analyses': analyses,
            'paper_trades': 0,  # Would query paper_trades table
            'uptime_hours': uptime_hours
        }
        
        self.send_json(stats)
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass

def run_server(port=8890):
    server = HTTPServer(('0.0.0.0', port), KrakenHandler)
    print(f"🦉 Kraken Market Web GUI running at http://localhost:{port}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()

if __name__ == '__main__':
    run_server()
