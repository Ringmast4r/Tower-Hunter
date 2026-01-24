#!/usr/bin/env python3
"""
TowerHunter v3.0 - SimTrack
Cell Tower Logger & Anomaly Detector for ClockworkPi
"""

import subprocess
import json
import csv
import sqlite3
import time
import re
import threading
import urllib.request
import math
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

CONFIG = {
    'poll_interval': 6,
    'log_dir': Path('/home/kali/Desktop/TowerHunter/logs'),
    'export_dir': Path('/home/kali/Desktop/TowerHunter/exports'),
    'db_path': Path('/home/kali/Desktop/TowerHunter/towerhunter.db'),
    'web_port': 8888,
    'anomaly_threshold': 3,
}

current_data = {
    'cell': {}, 'gps': {}, 'signal': {}, 'tower_location': {},
    'device_info': {}, 'connection_info': {}, 'history': [], 'alerts': [],
    'stats': {'total_readings': 0, 'unique_towers': set(), 'tower_changes': 0, 'start_time': None}
}
data_lock = threading.Lock()

def haversine_distance(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

class TowerHunter:
    def __init__(self):
        self.db = None
        self.last_cell_id = None
        self.tower_change_times = []
        self.setup_database()
        CONFIG['log_dir'].mkdir(parents=True, exist_ok=True)
        CONFIG['export_dir'].mkdir(parents=True, exist_ok=True)

    def setup_database(self):
        self.db = sqlite3.connect(str(CONFIG['db_path']), check_same_thread=False)
        self.db.execute('''CREATE TABLE IF NOT EXISTS cell_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT,
            mcc TEXT, mnc TEXT, lac TEXT, tac TEXT, cell_id TEXT,
            operator_name TEXT, access_tech TEXT, signal_quality INTEGER,
            rsrp REAL, rsrq REAL, latitude REAL, longitude REAL,
            altitude REAL, speed REAL, heading REAL, satellites INTEGER,
            tower_lat REAL, tower_lon REAL, tower_distance REAL,
            is_anomaly INTEGER DEFAULT 0, notes TEXT)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS towers (
            cell_id TEXT PRIMARY KEY, mcc TEXT, mnc TEXT, lac TEXT,
            operator_name TEXT, first_seen TEXT, last_seen TEXT,
            times_seen INTEGER DEFAULT 1, avg_latitude REAL, avg_longitude REAL,
            tower_lat REAL, tower_lon REAL, tower_source TEXT)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT,
            alert_type TEXT, description TEXT, cell_id TEXT,
            latitude REAL, longitude REAL)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS tower_locations (
            cell_key TEXT PRIMARY KEY, mcc TEXT, mnc TEXT, lac TEXT,
            cell_id TEXT, latitude REAL, longitude REAL, accuracy REAL,
            source TEXT, lookup_time TEXT)''')
        self.db.commit()

    def get_device_info(self):
        info = {'imei': '', 'imsi': '', 'iccid': '', 'phone': '', 'apn': '',
                'sim_operator': '', 'firmware': '', 'manufacturer': '', 'model': ''}
        try:
            result = subprocess.run(['sudo', 'mmcli', '-m', '0'], capture_output=True, text=True, timeout=10)
            for line in result.stdout.split('\n'):
                ll = line.lower()
                if 'equipment id:' in ll:
                    info['imei'] = line.split(':')[-1].strip()
                elif 'own:' in ll:
                    info['phone'] = line.split(':')[-1].strip()
                elif 'firmware revision:' in ll:
                    info['firmware'] = line.split(':')[-1].strip()
                elif 'manufacturer:' in ll:
                    info['manufacturer'] = line.split(':')[-1].strip()
                elif 'model:' in ll and 'modem' not in ll:
                    info['model'] = line.split(':')[-1].strip()
                elif 'initial bearer apn:' in ll:
                    info['apn'] = line.split(':')[-1].strip()
            result = subprocess.run(['sudo', 'mmcli', '-i', '0'], capture_output=True, text=True, timeout=10)
            for line in result.stdout.split('\n'):
                ll = line.lower()
                if 'imsi:' in ll:
                    info['imsi'] = line.split(':')[-1].strip()
                elif 'iccid:' in ll:
                    info['iccid'] = line.split(':')[-1].strip()
                elif 'operator id:' in ll:
                    info['sim_operator'] = line.split(':')[-1].strip()
        except Exception as e:
            print(f"[!] Device info error: {e}")
        return info

    def get_connection_info(self):
        info = {'duration': 0, 'start_time': '', 'registration': '', 'ip_type': '',
                'roaming': '', 'power_state': '', 'packet_state': ''}
        try:
            result = subprocess.run(['sudo', 'mmcli', '-b', '1'], capture_output=True, text=True, timeout=10)
            for line in result.stdout.split('\n'):
                ll = line.lower()
                if 'duration:' in ll:
                    m = re.search(r'(\d+)', line)
                    if m: info['duration'] = int(m.group(1))
                elif 'start date:' in ll:
                    info['start_time'] = line.split(':', 1)[-1].strip()
                elif 'ip type:' in ll:
                    info['ip_type'] = line.split(':')[-1].strip()
                elif 'roaming:' in ll:
                    info['roaming'] = line.split(':')[-1].strip()
            result = subprocess.run(['sudo', 'mmcli', '-m', '0'], capture_output=True, text=True, timeout=10)
            for line in result.stdout.split('\n'):
                ll = line.lower()
                if 'registration:' in ll and 'network-rejection' not in ll:
                    info['registration'] = line.split(':')[-1].strip()
                elif 'power state:' in ll:
                    info['power_state'] = line.split(':')[-1].strip()
                elif 'packet service state:' in ll:
                    info['packet_state'] = line.split(':')[-1].strip()
        except Exception as e:
            print(f"[!] Connection info error: {e}")
        return info

    def get_cell_data(self):
        data = {'mcc': '', 'mnc': '', 'lac': '', 'tac': '', 'cell_id': '',
                'operator_name': '', 'access_tech': '', 'signal_quality': 0,
                'rsrp': None, 'rsrq': None}
        try:
            result = subprocess.run(['sudo', 'mmcli', '-m', '0', '--location-get'],
                                    capture_output=True, text=True, timeout=10)
            for line in result.stdout.split('\n'):
                if 'operator mcc:' in line: data['mcc'] = line.split(':')[1].strip()
                elif 'operator mnc:' in line: data['mnc'] = line.split(':')[1].strip()
                elif 'location area code:' in line: data['lac'] = line.split(':')[1].strip()
                elif 'tracking area code:' in line: data['tac'] = line.split(':')[1].strip()
                elif 'cell id:' in line: data['cell_id'] = line.split(':')[1].strip()
            result = subprocess.run(['sudo', 'mmcli', '-m', '0'], capture_output=True, text=True, timeout=10)
            for line in result.stdout.split('\n'):
                if 'operator name:' in line: data['operator_name'] = line.split(':')[1].strip()
                elif 'access tech:' in line: data['access_tech'] = line.split(':')[1].strip()
                elif 'signal quality:' in line:
                    m = re.search(r'(\d+)%', line)
                    if m: data['signal_quality'] = int(m.group(1))
            result = subprocess.run(['sudo', 'mmcli', '-m', '0', '--signal-get'],
                                    capture_output=True, text=True, timeout=10)
            for line in result.stdout.split('\n'):
                if 'rsrp:' in line:
                    m = re.search(r'(-?\d+\.?\d*)', line)
                    if m: data['rsrp'] = float(m.group(1))
                elif 'rsrq:' in line:
                    m = re.search(r'(-?\d+\.?\d*)', line)
                    if m: data['rsrq'] = float(m.group(1))
        except Exception as e:
            print(f"[!] Cell data error: {e}")
        return data

    def get_gps_data(self):
        data = {'latitude': None, 'longitude': None, 'altitude': None,
                'speed': None, 'heading': None, 'satellites': 0, 'fix': False}
        try:
            result = subprocess.run(['gpspipe', '-w', '-n', '5'],
                                    capture_output=True, text=True, timeout=10)
            for line in result.stdout.split('\n'):
                if line.startswith('{'):
                    try:
                        g = json.loads(line)
                        if g.get('class') == 'TPV':
                            data['latitude'] = g.get('lat')
                            data['longitude'] = g.get('lon')
                            data['altitude'] = g.get('alt')
                            data['speed'] = g.get('speed')
                            data['heading'] = g.get('track')
                            if data['latitude'] and data['longitude']:
                                data['fix'] = True
                        elif g.get('class') == 'SKY':
                            sats = g.get('satellites', [])
                            data['satellites'] = len([s for s in sats if s.get('used')])
                    except: pass
        except Exception as e:
            print(f"[!] GPS error: {e}")
        return data

    def lookup_tower(self, mcc, mnc, lac, cell_id):
        if not all([mcc, mnc, lac, cell_id]): return None
        cell_key = f"{mcc}_{mnc}_{lac}_{cell_id}"
        cursor = self.db.execute('SELECT latitude, longitude, accuracy, source FROM tower_locations WHERE cell_key = ?', (cell_key,))
        row = cursor.fetchone()
        if row: return {'lat': row[0], 'lon': row[1], 'accuracy': row[2], 'source': row[3], 'cached': True}
        try:
            cid = int(cell_id, 16) if cell_id.startswith('0') else int(cell_id)
            url = f"https://opencellid.org/cell/get?key=pk.9e04e901e53ee76046bc53c03718916a&mcc={mcc}&mnc={mnc}&lac={lac}&cellid={cid}&format=json"
            req = urllib.request.Request(url, headers={'User-Agent': 'TowerHunter/3.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                d = json.loads(resp.read().decode())
                if d.get('lat') and d.get('lon'):
                    self.db.execute('INSERT OR REPLACE INTO tower_locations VALUES (?,?,?,?,?,?,?,?,?,?)',
                        (cell_key, mcc, mnc, lac, cell_id, d['lat'], d['lon'], d.get('range', 1000), 'OpenCellID', datetime.now().isoformat()))
                    self.db.commit()
                    return {'lat': d['lat'], 'lon': d['lon'], 'accuracy': d.get('range', 1000), 'source': 'OpenCellID', 'cached': False}
        except: pass
        return None

    def check_anomaly(self, cell_data, gps_data, tower_loc):
        alerts = []
        now = time.time()
        if cell_data['cell_id'] and cell_data['cell_id'] != self.last_cell_id:
            self.tower_change_times.append(now)
            self.tower_change_times = [t for t in self.tower_change_times if now - t < 60]
            if len(self.tower_change_times) >= CONFIG['anomaly_threshold']:
                alerts.append({'type': 'RAPID_TOWER_CHANGE', 'description': f"{len(self.tower_change_times)} changes in 60s", 'severity': 'HIGH'})
            self.last_cell_id = cell_data['cell_id']
            current_data['stats']['tower_changes'] += 1
        if cell_data['mcc'] and cell_data['mcc'] not in ['310', '311', '312']:
            alerts.append({'type': 'UNUSUAL_MCC', 'description': f"Non-US MCC: {cell_data['mcc']}", 'severity': 'MEDIUM'})
        if cell_data['rsrp'] and cell_data['rsrp'] > -80:
            alerts.append({'type': 'STRONG_SIGNAL', 'description': f"Unusual signal: {cell_data['rsrp']} dBm", 'severity': 'LOW'})
        return alerts

    def log_reading(self, cell_data, gps_data, tower_loc, alerts):
        ts = datetime.now().isoformat()
        tower_lat = tower_loc['lat'] if tower_loc else None
        tower_lon = tower_loc['lon'] if tower_loc else None
        tower_dist = haversine_distance(gps_data['latitude'], gps_data['longitude'], tower_lat, tower_lon) if tower_loc and gps_data.get('fix') else None
        self.db.execute('''INSERT INTO cell_logs (timestamp, mcc, mnc, lac, tac, cell_id, operator_name, access_tech,
            signal_quality, rsrp, rsrq, latitude, longitude, altitude, speed, heading, satellites,
            tower_lat, tower_lon, tower_distance, is_anomaly) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (ts, cell_data['mcc'], cell_data['mnc'], cell_data['lac'], cell_data['tac'], cell_data['cell_id'],
             cell_data['operator_name'], cell_data['access_tech'], cell_data['signal_quality'],
             cell_data['rsrp'], cell_data['rsrq'], gps_data['latitude'], gps_data['longitude'],
             gps_data['altitude'], gps_data['speed'], gps_data['heading'], gps_data['satellites'],
             tower_lat, tower_lon, tower_dist, 1 if alerts else 0))
        if cell_data['cell_id']:
            self.db.execute('''INSERT INTO towers (cell_id, mcc, mnc, lac, operator_name, first_seen, last_seen, times_seen, avg_latitude, avg_longitude)
                VALUES (?,?,?,?,?,?,?,1,?,?) ON CONFLICT(cell_id) DO UPDATE SET last_seen=?, times_seen=times_seen+1,
                avg_latitude=(avg_latitude*times_seen+?)/(times_seen+1), avg_longitude=(avg_longitude*times_seen+?)/(times_seen+1)''',
                (cell_data['cell_id'], cell_data['mcc'], cell_data['mnc'], cell_data['lac'], cell_data['operator_name'],
                 ts, ts, gps_data['latitude'], gps_data['longitude'], ts, gps_data['latitude'], gps_data['longitude']))
            current_data['stats']['unique_towers'].add(cell_data['cell_id'])
        for a in alerts:
            self.db.execute('INSERT INTO alerts (timestamp, alert_type, description, cell_id, latitude, longitude) VALUES (?,?,?,?,?,?)',
                (ts, a['type'], a['description'], cell_data['cell_id'], gps_data['latitude'], gps_data['longitude']))
        self.db.commit()
        current_data['stats']['total_readings'] += 1
        csv_path = CONFIG['log_dir'] / f"towerhunter_{datetime.now().strftime('%Y%m%d')}.csv"
        exists = csv_path.exists()
        with open(csv_path, 'a', newline='') as f:
            w = csv.writer(f)
            if not exists:
                w.writerow(['timestamp','mcc','mnc','lac','tac','cell_id','operator','tech','signal','rsrp','rsrq',
                           'lat','lon','alt','speed','heading','sats','tower_lat','tower_lon','tower_dist','anomaly'])
            w.writerow([ts, cell_data['mcc'], cell_data['mnc'], cell_data['lac'], cell_data['tac'], cell_data['cell_id'],
                       cell_data['operator_name'], cell_data['access_tech'], cell_data['signal_quality'],
                       cell_data['rsrp'], cell_data['rsrq'], gps_data['latitude'], gps_data['longitude'],
                       gps_data['altitude'], gps_data['speed'], gps_data['heading'], gps_data['satellites'],
                       tower_lat, tower_lon, tower_dist, 1 if alerts else 0])

    def collect_once(self):
        cell = self.get_cell_data()
        gps = self.get_gps_data()
        tower = self.lookup_tower(cell['mcc'], cell['mnc'], cell['lac'], cell['cell_id'])
        alerts = self.check_anomaly(cell, gps, tower)
        conn = self.get_connection_info()
        dist = haversine_distance(gps['latitude'], gps['longitude'], tower['lat'], tower['lon']) if tower and gps.get('fix') else None
        with data_lock:
            current_data['cell'] = cell
            current_data['gps'] = gps
            current_data['signal'] = {'quality': cell['signal_quality'], 'rsrp': cell['rsrp'], 'rsrq': cell['rsrq']}
            current_data['tower_location'] = {'lat': tower['lat'] if tower else None, 'lon': tower['lon'] if tower else None,
                'accuracy': tower.get('accuracy') if tower else None, 'source': tower.get('source') if tower else None, 'distance': dist}
            current_data['connection_info'] = conn
            current_data['alerts'].extend(alerts)
            current_data['alerts'] = current_data['alerts'][-50:]
            current_data['history'].append({'timestamp': datetime.now().isoformat(), 'cell_id': cell['cell_id'],
                'signal': cell['signal_quality'], 'lat': gps['latitude'], 'lon': gps['longitude'], 'tower_distance': dist})
            current_data['history'] = current_data['history'][-100:]
        self.log_reading(cell, gps, tower, alerts)
        return cell, gps, tower, alerts

    def run(self):
        current_data['stats']['start_time'] = datetime.now().isoformat()
        dev = self.get_device_info()
        with data_lock:
            current_data['device_info'] = dev
        print(f"\n{'='*60}\n  TOWERHUNTER v3.0 - SimTrack\n  {dev['manufacturer']} {dev['model']}\n  IMEI: {dev['imei']} | Phone: {dev['phone']}\n  Dashboard: http://0.0.0.0:{CONFIG['web_port']}\n{'='*60}\n")
        try:
            while True:
                cell, gps, tower, alerts = self.collect_once()
                gps_str = f"{gps['latitude']:.6f}, {gps['longitude']:.6f}" if gps['fix'] else "No Fix"
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Cell: {cell['cell_id'] or 'N/A'} | Signal: {cell['signal_quality']}% | GPS: {gps_str}")
                for a in alerts:
                    print(f"  ! {a['type']}: {a['description']}")
                time.sleep(CONFIG['poll_interval'])
        except KeyboardInterrupt:
            print("\n[*] Stopping...")

class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('/home/kali/Desktop/TowerHunter/dashboard.html', 'r') as f:
                self.wfile.write(f.read().encode())
        elif self.path == '/api/data':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            with data_lock:
                resp = {'cell': current_data['cell'], 'gps': current_data['gps'], 'signal': current_data['signal'],
                    'tower_location': current_data['tower_location'], 'device_info': current_data['device_info'],
                    'connection_info': current_data['connection_info'], 'alerts': current_data['alerts'][-10:],
                    'history': current_data['history'][-50:],
                    'stats': {'total_readings': current_data['stats']['total_readings'],
                        'unique_towers': len(current_data['stats']['unique_towers']),
                        'tower_changes': current_data['stats']['tower_changes'],
                        'start_time': current_data['stats']['start_time']}}
            self.wfile.write(json.dumps(resp).encode())
        elif self.path == '/api/towers':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            db = sqlite3.connect(str(CONFIG['db_path']))
            cursor = db.execute('SELECT cell_id, mcc, mnc, lac, operator_name, first_seen, last_seen, times_seen, avg_latitude, avg_longitude FROM towers ORDER BY last_seen DESC')
            towers = [{'cell_id': r[0], 'mcc': r[1], 'mnc': r[2], 'lac': r[3], 'operator': r[4], 'first_seen': r[5], 'last_seen': r[6], 'times_seen': r[7], 'lat': r[8], 'lon': r[9]} for r in cursor]
            db.close()
            self.wfile.write(json.dumps(towers).encode())
        elif self.path.startswith('/api/logs'):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            db = sqlite3.connect(str(CONFIG['db_path']))
            cursor = db.execute('''SELECT timestamp, mcc, mnc, lac, tac, cell_id, operator_name, access_tech,
                signal_quality, rsrp, latitude, longitude, tower_distance, is_anomaly
                FROM cell_logs ORDER BY timestamp DESC LIMIT 500''')
            logs = [{'timestamp': r[0], 'mcc': r[1], 'mnc': r[2], 'lac': r[3], 'tac': r[4], 'cell_id': r[5],
                'operator': r[6], 'tech': r[7], 'signal': r[8], 'rsrp': r[9], 'lat': r[10], 'lon': r[11],
                'tower_dist': r[12], 'anomaly': r[13]} for r in cursor]
            db.close()
            self.wfile.write(json.dumps(logs).encode())
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *args): pass

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer): pass

if __name__ == '__main__':
    hunter = TowerHunter()
    server = ThreadedHTTPServer(('0.0.0.0', CONFIG['web_port']), DashboardHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    hunter.run()
