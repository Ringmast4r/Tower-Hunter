<div align="center">

<img width="100%" alt="TOWER HUNTER" src="https://capsule-render.vercel.app/api?type=waving&color=0:000000,100:1C6879&height=220&section=header&text=TOWER%20HUNTER&fontSize=60&fontColor=ffffff&animation=twinkling&fontAlignY=35&desc=Linux%20%7C%20Python%20%7C%20Cellular%20%7C%20Monitoring&descSize=16&descAlignY=58"/>

`Linux` [`Python`](https://www.python.org/) `Cellular` `Monitoring` - Cell tower logger and anomaly detector for Linux mobile devices. Monitors cellular connections, logs tower data with GPS, and detects suspicious activity.

[![Typing SVG](https://readme-typing-svg.herokuapp.com?font=Fira+Code&weight=600&size=20&pause=1000&color=1C6879&center=true&vCenter=true&multiline=true&repeat=true&width=950&height=90&lines=Cell+tower+logger+and+anomaly+detector+for+Linux+mobile+devices%3BLinux+%2F+Python+%2F+Cellular+%2F+Monitoring)](https://git.io/typing-svg)

<br>

[![Project](https://img.shields.io/badge/Project-Tower--Hunter-1C6879?style=for-the-badge&logo=github&logoColor=white)](https://github.com/Ringmast4r/Tower-Hunter)
[![Format](https://img.shields.io/badge/Format-Python-000000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/Ringmast4r/Tower-Hunter/tree/main)

[![Stars](https://img.shields.io/github/stars/Ringmast4r/Tower-Hunter?style=flat-square&color=1C6879)](https://github.com/Ringmast4r/Tower-Hunter/stargazers)
[![Forks](https://img.shields.io/github/forks/Ringmast4r/Tower-Hunter?style=flat-square&color=1C6879)](https://github.com/Ringmast4r/Tower-Hunter/network/members)
[![Repo Size](https://img.shields.io/github/repo-size/Ringmast4r/Tower-Hunter?style=flat-square&color=1C6879)](https://github.com/Ringmast4r/Tower-Hunter)
[![Last Commit](https://img.shields.io/github/last-commit/Ringmast4r/Tower-Hunter?style=flat-square&color=1C6879)](https://github.com/Ringmast4r/Tower-Hunter/commits/main)

</div>

---

# TowerHunter v3.0 - SimTrack

![License](https://img.shields.io/badge/license-Proprietary-0066ff?style=flat-square)
![Profile Views](https://komarev.com/ghpvc/?username=Ringmast4r&color=0066ff&style=flat-square&label=Profile+Views)

A cell tower logger and anomaly detector designed for mobile security research on Linux-based portable devices.

<a id="what-this-is"></a>
## `> what_this_is`

TowerHunter is a field tool that continuously monitors and logs cellular network connections in real-time. It captures detailed information about cell towers your device connects to, correlates this with GPS location data, and can detect potentially suspicious cellular activity.

**Primary Use Cases:**
- Security research and IMSI catcher/Stingray detection
- Cell tower mapping and coverage analysis
- Mobile network research and education
- Understanding cellular handoff behavior while traveling

<a id="what-this-is-not"></a>
## `> what_this_is_not`

- **Not a hacking tool** - TowerHunter passively monitors your own device's cellular connection
- **Not cross-platform** - This only runs on Linux with ModemManager and gpsd
- **Not a consumer app** - Requires specific hardware (cellular modem, GPS) and Linux knowledge
- **Not for Windows/macOS** - The viewer can display historical data but core functionality requires Linux

<a id="features"></a>
## `> features`

### Cell Tower Logging
- Captures MCC, MNC, LAC, TAC, and Cell ID from your cellular modem
- Records operator name, access technology (LTE, 3G, etc.), and signal metrics
- Logs RSRP and RSRQ values for signal quality analysis
- Stores data in SQLite database and daily CSV files

### GPS Integration
- Correlates cell tower connections with your physical location
- Calculates distance to connected tower using OpenCellID lookups
- Tracks speed, heading, and altitude via gpsd

### Anomaly Detection
Alerts are generated for potentially suspicious activity:

| Alert Type | Trigger | Severity |
|------------|---------|----------|
| `RAPID_TOWER_CHANGE` | 3+ tower changes within 60 seconds | HIGH |
| `UNUSUAL_MCC` | Non-US Mobile Country Code detected | MEDIUM |
| `STRONG_SIGNAL` | RSRP stronger than -80 dBm (unusually close tower) | LOW |

### Web Dashboard
- Real-time monitoring interface accessible via browser
- Historical data viewer for analyzing past sessions
- Export functionality (JSON, CSV)

<a id="hardware-requirements"></a>
## `> hardware_requirements`

- **Linux device** - Tested on ClockworkPi DevTerm running Kali Linux
- **Cellular modem** - Must be supported by ModemManager (mmcli)
- **GPS receiver** - Must work with gpsd

<a id="software-dependencies"></a>
## `> software_dependencies`

```bash
# Required packages
sudo apt install modemmanager gpsd gpsd-clients python3

# For remote mode only
sudo apt install sshpass
```

<a id="files"></a>
## `> files`

| File | Description |
|------|-------------|
| `towerhunter.py` | Main application - runs directly on the device with modem/GPS |
| `towerhunter-remote.py` | Remote mode - runs on a separate machine, pulls data via SSH |
| `viewer.py` | Standalone viewer - browse historical data without active collection |
| `start-towerhunter.sh` | Launch script for main application |
| `start-viewer.sh` | Launch script for viewer |
| `start-remote.sh` | Launch script for remote mode |

<a id="usage"></a>
## `> usage`

### Direct Mode (on device with modem)

```bash
# Ensure ModemManager and gpsd are running
sudo systemctl start ModemManager
sudo systemctl start gpsd

# Run TowerHunter
python3 towerhunter.py
```

Access the dashboard at `http://localhost:8888`

### Remote Mode (from another machine)

Edit `towerhunter-remote.py` to set your ClockworkPi's IP address:
```python
REMOTE_HOST = "10.0.0.15"  # Your device's IP
REMOTE_USER = "kali"
REMOTE_PASS = "kali"
```

```bash
python3 towerhunter-remote.py
```

### Viewer Only (browse historical data)

```bash
python3 viewer.py
```

Access at `http://localhost:8889`

<a id="web-interface"></a>
## `> web_interface`

### Live Dashboard (port 8888)
- Real-time cell tower and GPS data
- Signal strength graphs
- Alert notifications
- Tower history

### Data Viewer (port 8889)
- Overview statistics
- Recent readings log
- Discovered towers list
- Alert history
- Data export (JSON/CSV)

<a id="database-schema"></a>
## `> database_schema`

### `cell_logs` - Individual readings
- Timestamp, cell identifiers (MCC/MNC/LAC/TAC/Cell ID)
- Operator, access technology, signal metrics
- GPS coordinates, altitude, speed, heading
- Tower location (from OpenCellID), distance to tower
- Anomaly flag

### `towers` - Unique towers discovered
- Cell ID, operator info
- First/last seen timestamps
- Times seen count
- Average GPS position when connected

### `alerts` - Anomaly events
- Timestamp, alert type, description
- Associated cell ID and location

### `tower_locations` - OpenCellID cache
- Cached tower coordinates to reduce API calls

<a id="configuration"></a>
## `> configuration`

Edit the `CONFIG` dictionary in the Python files:

```python
CONFIG = {
    'poll_interval': 6,           # Seconds between readings
    'log_dir': Path('...'),       # CSV log directory
    'export_dir': Path('...'),    # Export directory
    'db_path': Path('...'),       # SQLite database path
    'web_port': 8888,             # Dashboard port
    'anomaly_threshold': 3,       # Tower changes before alert
}
```

<a id="api-endpoints"></a>
## `> api_endpoints`

| Endpoint | Description |
|----------|-------------|
| `GET /` | Web dashboard |
| `GET /api/data` | Current readings (live mode) |
| `GET /api/stats` | Database statistics |
| `GET /api/recent` | Recent log entries |
| `GET /api/towers` | Discovered towers |
| `GET /api/alerts` | Alert history |
| `GET /api/logs` | Full log query |
| `GET /api/export/json` | Export as JSON |
| `GET /api/export/csv` | Export as CSV |

<a id="understanding-the-data"></a>
## `> understanding_the_data`

### Cell Identifiers
- **MCC** (Mobile Country Code) - Country identifier (310-316 = USA)
- **MNC** (Mobile Network Code) - Carrier identifier
- **LAC** (Location Area Code) - Geographic grouping of cells
- **TAC** (Tracking Area Code) - LTE equivalent of LAC
- **Cell ID** - Unique identifier for the specific cell/sector

### Signal Metrics
- **Signal Quality** - Percentage (0-100%)
- **RSRP** (Reference Signal Received Power) - Typical: -80 to -120 dBm
- **RSRQ** (Reference Signal Received Quality) - Typical: -10 to -20 dB

### Anomaly Indicators
Rapid tower switching or unusually strong signals *could* indicate an IMSI catcher, but can also be caused by:
- Driving through areas with dense tower coverage
- Being near a small cell or DAS (Distributed Antenna System)
- Network congestion causing load balancing
- Building interference causing frequent handoffs

**Always investigate alerts in context before drawing conclusions.**

<a id="limitations"></a>
## `> limitations`

- Requires root/sudo for modemmanager access
- OpenCellID API has rate limits (uses free public key)
- GPS fix required for location correlation
- Tower location accuracy varies (OpenCellID is crowdsourced)
- Only detects anomalies based on simple heuristics

<a id="license"></a>
## `> license`

**Copyright (c) 2025 Ringmast4r. All Rights Reserved.**

This software is proprietary and confidential. Unauthorized copying, distribution, modification, public display, or public performance of this software, via any medium, is strictly prohibited.

- You may **view** this code for educational purposes only
- You may **not** copy, fork, modify, or redistribute this code
- You may **not** use this code in any commercial or personal projects
- You may **not** claim this work as your own

For licensing inquiries, contact the repository owner.

<a id="acknowledgments"></a>
## `> acknowledgments`

- [OpenCellID](https://opencellid.org/) for cell tower location data
- [ModemManager](https://www.freedesktop.org/wiki/Software/ModemManager/) for modem abstraction
- [gpsd](https://gpsd.gitlab.io/gpsd/) for GPS handling

---

*This project is the result of independent security research. All code is original work by Ringmast4r.*

---

<div align="center">

<img width="100%" alt="TOWER HUNTER footer" src="https://capsule-render.vercel.app/api?type=waving&color=0:1C6879,100:000000&height=120&section=footer&text=RINGMAST4R%20%2F%2F%20MONITORING&fontSize=18&fontColor=ffffff&fontAlignY=65"/>

</div>
