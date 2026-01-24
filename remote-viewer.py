#!/usr/bin/env python3
"""
TowerHunter Remote Viewer
Connects to ClockworkPi and displays live dashboard locally
"""

import threading
import json
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

REMOTE_HOST = "10.0.0.15"
REMOTE_PORT = 8888
LOCAL_PORT = 8888

class RemoteProxyHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open(Path(__file__).parent / 'dashboard.html', 'r') as f:
                self.wfile.write(f.read().encode())
        elif self.path.startswith('/api/'):
            # Proxy API requests to ClockworkPi
            try:
                url = f"http://{REMOTE_HOST}:{REMOTE_PORT}{self.path}"
                req = urllib.request.Request(url, headers={'User-Agent': 'TowerHunter-Remote/1.0'})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = resp.read()
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(data)
            except Exception as e:
                self.send_response(503)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e), 'message': 'Cannot connect to ClockworkPi'}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, *args):
        pass

if __name__ == '__main__':
    print(f"""
============================================================
  TOWERHUNTER Remote Viewer
  Connecting to ClockworkPi at {REMOTE_HOST}:{REMOTE_PORT}
  Local Dashboard: http://localhost:{LOCAL_PORT}
============================================================
""")
    server = HTTPServer(('0.0.0.0', LOCAL_PORT), RemoteProxyHandler)
    print(f"[*] Dashboard running at http://localhost:{LOCAL_PORT}")
    print("[*] Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Stopped")
