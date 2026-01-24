#!/usr/bin/env python3
"""
TowerHunter Static Viewer
View historical data even when TowerHunter isn't actively collecting.
Access from laptop: http://10.0.0.15:8889
"""

import sqlite3
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path
from datetime import datetime

DB_PATH = Path.home() / 'Desktop' / 'TowerHunter' / 'towerhunter.db'
PORT = 8889

class ViewerHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(self.get_viewer_html().encode())
        elif self.path == '/api/stats':
            self.send_json(self.get_stats())
        elif self.path == '/api/recent':
            self.send_json(self.get_recent_logs(100))
        elif self.path == '/api/towers':
            self.send_json(self.get_towers())
        elif self.path == '/api/alerts':
            self.send_json(self.get_alerts())
        elif self.path.startswith('/api/export/'):
            fmt = self.path.split('/')[-1]
            self.handle_export(fmt)
        else:
            self.send_error(404)
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def get_db(self):
        if not DB_PATH.exists():
            return None
        return sqlite3.connect(str(DB_PATH))
    
    def get_stats(self):
        db = self.get_db()
        if not db:
            return {'error': 'No database found. Run TowerHunter first.'}
        
        try:
            cur = db.cursor()
            cur.execute('SELECT COUNT(*) FROM cell_logs')
            total = cur.fetchone()[0]
            cur.execute('SELECT COUNT(DISTINCT cell_id) FROM cell_logs WHERE cell_id != ""')
            towers = cur.fetchone()[0]
            cur.execute('SELECT COUNT(*) FROM alerts')
            alerts = cur.fetchone()[0]
            cur.execute('SELECT MIN(timestamp), MAX(timestamp) FROM cell_logs')
            times = cur.fetchone()
            cur.execute('SELECT * FROM cell_logs ORDER BY id DESC LIMIT 1')
            cols = [d[0] for d in cur.description]
            last = cur.fetchone()
            last_reading = dict(zip(cols, last)) if last else None
            
            return {
                'total_readings': total,
                'unique_towers': towers,
                'total_alerts': alerts,
                'first_reading': times[0],
                'last_reading': times[1],
                'latest': last_reading
            }
        finally:
            db.close()
    
    def get_recent_logs(self, limit=100):
        db = self.get_db()
        if not db:
            return []
        try:
            cur = db.cursor()
            cur.execute(f'SELECT * FROM cell_logs ORDER BY id DESC LIMIT {limit}')
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            db.close()
    
    def get_towers(self):
        db = self.get_db()
        if not db:
            return []
        try:
            cur = db.cursor()
            cur.execute('SELECT * FROM towers ORDER BY times_seen DESC')
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            db.close()
    
    def get_alerts(self):
        db = self.get_db()
        if not db:
            return []
        try:
            cur = db.cursor()
            cur.execute('SELECT * FROM alerts ORDER BY id DESC LIMIT 100')
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            db.close()
    
    def handle_export(self, fmt):
        if fmt == 'json':
            data = self.get_recent_logs(10000)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-Disposition', f'attachment; filename="towerhunter_export_{datetime.now().strftime("%Y%m%d")}.json"')
            self.end_headers()
            self.wfile.write(json.dumps(data, indent=2).encode())
        elif fmt == 'csv':
            data = self.get_recent_logs(10000)
            if not data:
                self.send_error(404, 'No data')
                return
            self.send_response(200)
            self.send_header('Content-type', 'text/csv')
            self.send_header('Content-Disposition', f'attachment; filename="towerhunter_export_{datetime.now().strftime("%Y%m%d")}.csv"')
            self.end_headers()
            import csv
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
            self.wfile.write(output.getvalue().encode())
        else:
            self.send_error(400, 'Unknown format')
    
    def log_message(self, format, *args):
        pass
    
    def get_viewer_html(self):
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TowerHunter - Data Viewer</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Courier New', monospace;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
            color: #00ff88;
            min-height: 100vh;
            padding: 15px;
        }
        .header {
            text-align: center;
            padding: 20px;
            border-bottom: 2px solid #00ff88;
            margin-bottom: 20px;
        }
        .header h1 { font-size: 2em; }
        .header .subtitle { color: #888; margin-top: 5px; }
        .header .mode { 
            display: inline-block;
            background: #333;
            color: #00d4ff;
            padding: 5px 15px;
            border-radius: 20px;
            margin-top: 10px;
        }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .tab {
            padding: 10px 20px;
            background: #222;
            border: 1px solid #333;
            border-radius: 5px;
            cursor: pointer;
            color: #888;
        }
        .tab.active { background: #00ff88; color: #000; }
        .tab:hover { border-color: #00ff88; }
        .panel { display: none; }
        .panel.active { display: block; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: rgba(0,0,0,0.5);
            border: 1px solid #333;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }
        .stat-card .value { font-size: 2em; color: #00ff88; }
        .stat-card .label { color: #666; font-size: 0.8em; margin-top: 5px; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 0.85em;
        }
        th, td {
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #222;
        }
        th { color: #00d4ff; background: #111; }
        tr:hover { background: rgba(0,255,136,0.1); }
        .anomaly { color: #ff6b6b; }
        .export-btns {
            display: flex;
            gap: 10px;
            margin: 15px 0;
        }
        .btn {
            padding: 10px 20px;
            background: #222;
            border: 1px solid #00ff88;
            color: #00ff88;
            border-radius: 5px;
            cursor: pointer;
            text-decoration: none;
        }
        .btn:hover { background: #00ff88; color: #000; }
        .latest-box {
            background: #111;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 15px;
            margin: 15px 0;
        }
        .latest-box h3 { color: #00d4ff; margin-bottom: 10px; }
        .latest-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
        }
        .latest-item { 
            background: #0a0a0a;
            padding: 8px;
            border-radius: 4px;
        }
        .latest-item .label { color: #666; font-size: 0.8em; }
        .latest-item .value { color: #00ff88; }
        .error { color: #ff6b6b; text-align: center; padding: 40px; }
        .timestamp { color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🗼 TOWERHUNTER</h1>
        <div class="subtitle">SimTrack - Cell Tower Data Viewer</div>
        <div class="mode">📊 Historical Data Mode</div>
    </div>
    
    <div class="tabs">
        <div class="tab active" onclick="showPanel('overview')">Overview</div>
        <div class="tab" onclick="showPanel('logs')">Recent Logs</div>
        <div class="tab" onclick="showPanel('towers')">Towers</div>
        <div class="tab" onclick="showPanel('alerts')">Alerts</div>
        <div class="tab" onclick="showPanel('export')">Export</div>
    </div>
    
    <div id="overview" class="panel active">
        <div class="stats-grid" id="stats-grid"></div>
        <div class="latest-box" id="latest-reading"></div>
    </div>
    
    <div id="logs" class="panel">
        <h3>Recent Readings</h3>
        <table id="logs-table">
            <thead><tr><th>Time</th><th>Cell ID</th><th>MCC/MNC</th><th>Signal</th><th>Lat</th><th>Lon</th><th>Anomaly</th></tr></thead>
            <tbody></tbody>
        </table>
    </div>
    
    <div id="towers" class="panel">
        <h3>Discovered Towers</h3>
        <table id="towers-table">
            <thead><tr><th>Cell ID</th><th>MCC</th><th>MNC</th><th>Operator</th><th>Times Seen</th><th>First Seen</th><th>Last Seen</th></tr></thead>
            <tbody></tbody>
        </table>
    </div>
    
    <div id="alerts" class="panel">
        <h3>Alert History</h3>
        <table id="alerts-table">
            <thead><tr><th>Time</th><th>Type</th><th>Description</th><th>Cell ID</th><th>Location</th></tr></thead>
            <tbody></tbody>
        </table>
    </div>
    
    <div id="export" class="panel">
        <h3>Export Data</h3>
        <p style="margin: 15px 0; color: #888;">Download collected cell tower data in various formats:</p>
        <div class="export-btns">
            <a href="/api/export/json" class="btn">📄 Export JSON</a>
            <a href="/api/export/csv" class="btn">📊 Export CSV</a>
        </div>
        <p style="margin-top: 20px; color: #666; font-size: 0.9em;">
            For KML export (Google Earth), run: <code style="background:#111;padding:2px 6px;">python3 towerhunter.py --export-only</code>
        </p>
    </div>
    
    <script>
        function showPanel(id) {
            document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById(id).classList.add('active');
            event.target.classList.add('active');
        }
        
        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                
                if (data.error) {
                    document.getElementById('stats-grid').innerHTML = `<div class="error">${data.error}</div>`;
                    return;
                }
                
                document.getElementById('stats-grid').innerHTML = `
                    <div class="stat-card"><div class="value">${data.total_readings}</div><div class="label">Total Readings</div></div>
                    <div class="stat-card"><div class="value">${data.unique_towers}</div><div class="label">Unique Towers</div></div>
                    <div class="stat-card"><div class="value">${data.total_alerts}</div><div class="label">Alerts</div></div>
                `;
                
                if (data.latest) {
                    const l = data.latest;
                    document.getElementById('latest-reading').innerHTML = `
                        <h3>Latest Reading</h3>
                        <div class="timestamp">${l.timestamp}</div>
                        <div class="latest-grid">
                            <div class="latest-item"><div class="label">Cell ID</div><div class="value">${l.cell_id || '--'}</div></div>
                            <div class="latest-item"><div class="label">MCC/MNC</div><div class="value">${l.mcc}/${l.mnc}</div></div>
                            <div class="latest-item"><div class="label">Operator</div><div class="value">${l.operator_name || '--'}</div></div>
                            <div class="latest-item"><div class="label">Signal</div><div class="value">${l.signal_quality}%</div></div>
                            <div class="latest-item"><div class="label">RSRP</div><div class="value">${l.rsrp || '--'} dBm</div></div>
                            <div class="latest-item"><div class="label">Position</div><div class="value">${l.latitude?.toFixed(5) || '--'}, ${l.longitude?.toFixed(5) || '--'}</div></div>
                        </div>
                    `;
                }
            } catch (e) {
                document.getElementById('stats-grid').innerHTML = '<div class="error">Failed to load data. Is the database available?</div>';
            }
        }
        
        async function loadLogs() {
            try {
                const res = await fetch('/api/recent');
                const data = await res.json();
                const tbody = document.querySelector('#logs-table tbody');
                tbody.innerHTML = data.map(r => `
                    <tr class="${r.is_anomaly ? 'anomaly' : ''}">
                        <td>${new Date(r.timestamp).toLocaleString()}</td>
                        <td>${r.cell_id || '--'}</td>
                        <td>${r.mcc}/${r.mnc}</td>
                        <td>${r.signal_quality}%</td>
                        <td>${r.latitude?.toFixed(5) || '--'}</td>
                        <td>${r.longitude?.toFixed(5) || '--'}</td>
                        <td>${r.is_anomaly ? '⚠️' : ''}</td>
                    </tr>
                `).join('');
            } catch (e) {}
        }
        
        async function loadTowers() {
            try {
                const res = await fetch('/api/towers');
                const data = await res.json();
                const tbody = document.querySelector('#towers-table tbody');
                tbody.innerHTML = data.map(t => `
                    <tr>
                        <td>${t.cell_id}</td>
                        <td>${t.mcc}</td>
                        <td>${t.mnc}</td>
                        <td>${t.operator_name || '--'}</td>
                        <td>${t.times_seen}</td>
                        <td>${t.first_seen?.split('T')[0] || '--'}</td>
                        <td>${t.last_seen?.split('T')[0] || '--'}</td>
                    </tr>
                `).join('');
            } catch (e) {}
        }
        
        async function loadAlerts() {
            try {
                const res = await fetch('/api/alerts');
                const data = await res.json();
                const tbody = document.querySelector('#alerts-table tbody');
                tbody.innerHTML = data.length ? data.map(a => `
                    <tr>
                        <td>${new Date(a.timestamp).toLocaleString()}</td>
                        <td style="color:#ff6b6b">${a.alert_type}</td>
                        <td>${a.description}</td>
                        <td>${a.cell_id || '--'}</td>
                        <td>${a.latitude?.toFixed(4) || '--'}, ${a.longitude?.toFixed(4) || '--'}</td>
                    </tr>
                `).join('') : '<tr><td colspan="5" style="text-align:center;color:#666">No alerts recorded</td></tr>';
            } catch (e) {}
        }
        
        loadStats();
        loadLogs();
        loadTowers();
        loadAlerts();
    </script>
</body>
</html>'''


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass


if __name__ == '__main__':
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║              TOWERHUNTER DATA VIEWER                         ║
║                    ~ SimTrack ~                              ║
╠══════════════════════════════════════════════════════════════╣
║  Local:  http://localhost:{PORT}                               ║
║  Remote: http://10.0.0.15:{PORT}                               ║
╚══════════════════════════════════════════════════════════════╝
    """)
    server = ThreadedHTTPServer(('0.0.0.0', PORT), ViewerHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Viewer stopped.")
