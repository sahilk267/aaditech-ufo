# AadiTech UFO - Infrastructure Monitoring & Benchmarking Platform

**Project Status**: 🚀 Active Development  
**Latest Version**: 1.0.0-pre-alpha  
**Last Updated**: March 16, 2026

---

## 🎯 IMPORTANT: START HERE!

### For Implementation Planning:
👉 **[MASTER_ROADMAP.md](MASTER_ROADMAP.md)** ← Single source of truth for 25-week platform development

**Quick Navigation**:
- 📅 **Weekly Tasks**: [WEEK_BY_WEEK_CHECKLIST.md](WEEK_BY_WEEK_CHECKLIST.md)
- ⚡ **Quick Start**: [QUICK_START_GUIDE.md](QUICK_START_GUIDE.md)
- 🏗️ **Architecture**: [UPDATED_ARCHITECTURE.md](UPDATED_ARCHITECTURE.md)
- 🪟 **Windows Features**: [ADVANCED_WINDOWS_TROUBLESHOOTING.md](ADVANCED_WINDOWS_TROUBLESHOOTING.md)
- 📊 **Feature Map**: [FEATURE_COVERAGE_MAP.md](FEATURE_COVERAGE_MAP.md)
- 📚 **Reference Docs**: [ARCHIVE/](ARCHIVE/) (detailed analysis & history)

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Tech Stack](#tech-stack)
5. [Quick Start](#quick-start)
6. [Installation](#installation)
7. [Configuration](#configuration)
8. [Usage](#usage)
9. [API Documentation](#api-documentation)
10. [Deployment](#deployment)
11. [Contributing](#contributing)
12. [License](#license)
13. [Troubleshooting](#troubleshooting)
14. [Support](#support)

---

## Overview

**AadiTech UFO** (Codename: **ToolBoxGalaxy**) is an **Infrastructure Monitoring and Benchmarking Platform** designed for real-time system performance monitoring, data collection, and analysis.

The platform consists of:
- **Fleet of Monitoring Agents** - Lightweight Windows/Linux agents that collect system telemetry
- **Central Dashboard Server** - Flask-based web server for data aggregation and visualization
- **Web Interface** - Modern Bootstrap UI for system monitoring and administration

### Primary Use Cases
- ✅ Real-time infrastructure monitoring
- ✅ System performance benchmarking
- ✅ Historical performance analysis
- ✅ Centralized system management
- ✅ Multi-system performance comparison

---

## Features

### ✅ Currently Implemented

#### Agent Capabilities
- Cross-platform system information collection (Windows/Linux)
- Real-time CPU, memory, and disk metrics
- Network topology detection (Local IP, Public IP)
- Periodic data submission (configurable intervals)
- Automatic benchmark calculation
- Per-core CPU utilization monitoring
- Advanced RAM utilization tracking

#### Server Capabilities
- Centralized data aggregation
- Multi-system dashboard
- Real-time status monitoring
- Historical data tracking
- Performance benchmarking
- Database backup/restore functionality
- Responsive web interface

#### Dashboard Features
- **Admin Panel**: Complete system overview with filtering and sorting
- **User Panel**: Detailed system information and historical trends
- **History View**: Time-series performance metrics
- **Backup Management**: Create and restore database backups
- **Advanced Filtering**: Search, status filtering, benchmark categorization

### 🔄 Planned Features (Future Releases)

- **Authentication System**: User login and role-based access control
- **API Authentication**: JWT-based API security
- **Real-time Updates**: WebSocket support for live dashboards
- **Data Export**: CSV/PDF export functionality
- **AI Analytics**: Machine learning-based anomaly detection
- **Alert System**: Configurable alerts for performance thresholds
- **API Documentation**: OpenAPI/Swagger documentation
- **Containerization**: Docker/Kubernetes support
- **Automated Reporting**: Scheduled email reports
- **Advanced Analytics**: Trend analysis and forecasting

### ❌ Not Implemented (Removed from Documentation)

The following features mentioned in historical documentation are **NOT currently implemented** and should not be expected:
- ❌ Local AI Engine (Ollama Integration)
- ❌ Intelligent Alerting System
- ❌ Automation Engine
- ❌ Self-Healing Infrastructure
- ❌ Multi-Tenant SaaS Architecture
- ❌ Role-Based Access Control

**Note**: These features may be added in future enterprise versions.

---

## Architecture

### System Architecture Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                   AADITECH UFO MONITORING SYSTEM               │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐         ┌──────────────────┐              │
│  │  AGENT SYSTEMS  │         │   FLASK SERVER   │              │
│  ├─────────────────┤         ├──────────────────┤              │
│  │ • Windows VM 1  │ ─JSON─→ │  /api/submit_data│              │
│  │ • Windows VM 2  │ (60s)   │                  │              │
│  │ • Linux Server  │         │  REST Endpoints: │              │
│  │ • Server Rack   │─────────│  • /admin        │   ┌────────┐│
│  │                 │         │  • /user/<id>    │   │ SQLite ││
│  │ Every 60 secs:  │         │  • /backup       │   │ Database
│  │ • CPU metrics   │         │  • /manual_submit│   │ (tool...││
│  │ • RAM metrics   │         │                  │   └────────┘│
│  │ • Disk metrics  │         └──────────────────┘              │
│  │ • Network info  │               ↓                           │
│  │ • System info   │         ┌──────────────────┐              │
│  │                 │         │   WEB INTERFACE  │              │
│  │ Benchmark calc: │         ├──────────────────┤              │
│  │ (CPU×10 + RAM)/2│         │ • Admin Dashboard│              │
│  │                 │         │ • User Panels    │              │
│  │ Uses WMIC on    │         │ • History Graphs │              │
│  │ Windows, nsutil │         │ • Backup Manager │              │
│  │ on Linux        │         │ Bootstrap 4.5.2  │              │
│  │                 │         └──────────────────┘              │
│  └─────────────────┘                                          │
│                                                                 │
└────────────────────────────────────────────────────────────────┘

Data Flow:
  Agent Systems → (JSON over HTTP POST) → Flask Server
                                              ↓
                                          SQLAlchemy ORM
                                              ↓
                                          SQLite Database
                                              ↓
                                         Web Interface
```

### Component Details

#### 1. Monitoring Agents (`agent/agent.py`)
- **Purpose**: Collect system telemetry from monitored machines
- **Frequency**: Every 60 seconds (configurable)
- **Data**: CPU, RAM, Disk, Network, System Info
- **Transport**: HTTP POST to `/api/submit_data` endpoint
- **Current Support**: Windows (uses WMI), partial Linux support

#### 2. Flask Server (`server/app.py`)
- **Purpose**: Central aggregation, storage, and API endpoint
- **Database**: SQLite for persistent storage
- **Endpoints**: 10 REST endpoints for data access
- **Features**: Data normalization, backup/restore, IST timezone conversion

#### 3. Web Interface (`server/templates/`)
- **Framework**: Bootstrap 4.5.2 for responsive design
- **Rendering**: Jinja2 templating
- **Javascript**: Vanilla JS for interactivity
- **Pages**: 5 main views (Admin, User, History, Backup, Base)

---

## Tech Stack

### Backend
```
Python 3.x
├── Flask 3.0.0                  # Web framework
├── Flask-SQLAlchemy 3.1.1       # ORM integration
├── Flask-Migrate 4.0.5          # Database migrations
├── SQLAlchemy 2.0.25            # Object-Relational Mapping
├── Werkzeug 3.0.1               # WSGI utilities
├── requests 2.31.0              # HTTP client
├── psutil 5.9.8                 # System metrics
├── pytz 2024.1                  # Timezone handling
└── python-dateutil 2.8.2        # Date utilities
```

### Frontend
```
HTML5 / CSS3 / JavaScript
├── Bootstrap 4.5.2              # CSS framework
├── jQuery 3.5.1                 # JS utilities
├── Jinja2 3.1.3                 # Template engine
└── Vanilla JS                   # Custom interactions
```

### Database
```
SQLite 3.x                        # Embedded relational database
├── Single file: toolboxgalaxy.db
├── 24 columns for system metrics
└── ~220 KB per 1000 records
```

### Infrastructure (Not Yet Implemented)
```
Planned for future releases:
├── Docker & docker-compose
├── Gunicorn WSGI server
├── Nginx reverse proxy
├── Kubernetes orchestration
└── PostgreSQL/MySQL support
```

---

## Quick Start

### For Users (Running the Server)

```bash
# 1. Clone repository
git clone https://github.com/sahilk267/aaditech-ufo.git
cd aaditech-ufo

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
python server/app.py

# 4. Access dashboard
# Open browser: http://localhost:5000/admin
```

### For Agents (Sending Data)

```bash
# 1. On a Windows machine:
# Edit agent/agent.py and update SERVER_URL to your server IP:
SERVER_URL = "http://YOUR_SERVER_IP:5000/api/submit_data"

# 2. Run the agent
python agent/agent.py

# 3. Data will be submitted every 60 seconds
# Check server dashboard to see incoming data
```

---

## Installation

### Prerequisites
- **Python 3.8+** (tested on 3.11)
- **pip** (Python package manager)
- **SQLite3** (usually pre-installed)
- **Network access** between agents and server (port 5000)

### Step 1: Clone Repository

```bash
git clone https://github.com/sahilk267/aaditech-ufo.git
cd aaditech-ufo
```

### Step 2: Create Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Initialize Database

The database is automatically created on first run. The SQLite file will be created at:
```
server/toolboxgalaxy.db
```

### Step 5: Run Server

```bash
cd server
python app.py
```

**Output:**
```
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://0.0.0.0:5000
```

Access the web interface at: **http://localhost:5000**

---

## Configuration

### Server Configuration

**File**: `server/app.py` (Lines 47-51)

```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///toolboxgalaxy.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'Andh3r1@m1dc#000'  # ⚠️ Change for production!
```

**⚠️ IMPORTANT SECURITY NOTES:**
- `SECRET_KEY` is exposed. For production, use environment variable:
  ```python
  app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
  ```
- Database path can be changed by modifying the URI
- For production, use PostgreSQL or MySQL instead of SQLite

### Agent Configuration

**File**: `agent/agent.py` (Lines 14-15)

```python
SERVER_URL = "http://192.168.86.152:5000/api/submit_data"  # ⚠️ Update this!
REPORT_INTERVAL = 60  # Seconds between submissions
```

**Configuration Options:**
```python
# Change server IP/hostname
SERVER_URL = "http://192.168.1.100:5000/api/submit_data"
SERVER_URL = "http://monitoring.example.com:5000/api/submit_data"

# Change reporting frequency (seconds)
REPORT_INTERVAL = 30   # Every 30 seconds (increases network traffic)
REPORT_INTERVAL = 300  # Every 5 minutes (reduces network traffic)
```

### Timezone Configuration

**Default**: Asia/Kolkata (IST)  
**File**: `server/app.py` (Line 22)

```python
def get_current_time():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)
```

**To change timezone:**
```python
# Examples:
ist = pytz.timezone('US/Eastern')      # Eastern Time
ist = pytz.timezone('Europe/London')   # GMT
ist = pytz.timezone('Asia/Tokyo')      # Japan Standard Time
ist = pytz.timezone('UTC')             # UTC

# Full list: pytz.all_timezones
```

---

## Usage

### Admin Dashboard

**URL**: `http://localhost:5000/admin`

**Features**:
- View all registered systems
- Filter by status (Active/Inactive)
- Filter by benchmark level (High/Medium/Low)
- Search by hostname, serial number, IP
- Click to expand system details
- Sort by any column
- View last update timestamp

**System Status:**
- 🟢 **Active**: Last update < 5 minutes ago
- 🔴 **Inactive**: Last update > 5 minutes ago

### User Panel

**URL**: `http://localhost:5000/user/<serial_number>`

**Displays**:
- System information (Serial, Model, User, Hostname)
- CPU metrics (Usage %, Cores, Threads, Frequency, Per-core utilization)
- Memory information (Total, Used, Available RAM)
- Storage devices (Capacity, Usage, Free space)
- Network info (Local IP, Public IP)
- Benchmark scores (Software, Hardware, Overall)
- System status and last update time

**Color Coding**:
- 🟢 Green: Low usage (< 50%)
- 🟠 Orange: Medium usage (50-75%)
- 🔴 Red: High usage (> 75%)
- Benchmark colors: Green (High) / Orange (Medium) / Red (Low)

### System History

**URL**: `http://localhost:5000/user/<serial_number>/history`

**Features**:
- Time-series performance data
- Filter by time period (1h, 24h, 7 days, All time)
- Filter by status (Active/Inactive/All)
- Search across historical data
- View all historical metrics in table format

**Columns**:
- Timestamp, Local IP, Public IP
- CPU Usage, RAM Usage, Storage Usage
- RAM details (Total/Used/Free)
- Benchmark scores (Software/Hardware/Overall)
- Status

### Backup & Restore

**URL**: `http://localhost:5000/backup`

**Features**:
- Create database backup (ZIP format)
- View all available backups (with timestamp and size)
- Restore from any backup

**Backup Details**:
- Includes: Database + configuration files
- Format: ZIP archive with timestamp
- Stored in: `server/backups/` directory
- Size: ~200 KB per month of data (varies)

**Example Backup Filename**: `backup_20260316_122345.zip`

### Manual Data Submission

**URL**: `http://localhost:5000/manual_submit`
**Method**: POST (via user.html button)

**Purpose**: Manually trigger a metrics update on the local system
**Useful for**: Testing, immediate data refresh

---

## API Documentation

### Base URL
```
http://server-ip:5000
```

### Endpoints

#### 1. Get Admin Dashboard
```http
GET /admin
```
**Response**: HTML page with system list  
**Auth**: None (should be protected in production)

---

#### 2. Get User Panel (Latest System Data)
```http
GET /user/<serial_number>
```
**Parameters**:
- `serial_number`: System serial number (string)

**Response**: HTML page with system details  
**Example**:
```
GET /user/ABC123XYZ
```

---

#### 3. Get System History
```http
GET /user/<serial_number>/history
```
**Parameters**:
- `serial_number`: System serial number (string)

**Response**: HTML page with historical metrics  
**Default Limit**: All records (⚠️ Performance issue for large datasets)

---

#### 4. Submit System Data (Agent Endpoint)
```http
POST /api/submit_data
Content-Type: application/json
```

**Request Body**:
```json
{
  "serial_number": "DELL-12345XYZ",
  "hostname": "WORKSTATION-01",
  "model_number": "OptiPlex 7090",
  "local_ip": "192.168.1.100",
  "public_ip": "203.0.113.45",
  "cpu_info": "Intel Core i7-10700K",
  "cpu_cores": 8,
  "cpu_threads": 16,
  "cpu_usage": 45.2,
  "cpu_per_core": [10.1, 20.3, 15.5, ...],
  "cpu_frequency": {
    "current": 3600,
    "min": 800,
    "max": 5300
  },
  "ram_usage": 65.5,
  "ram_info": {
    "total": 32.0,
    "used": 21.0,
    "available": 11.0,
    "percent": 65.5
  },
  "disk_info": [
    {
      "device": "C:",
      "mountpoint": "/",
      "total": 500.0,
      "used": 250.0,
      "free": 250.0,
      "percent": 50.0
    }
  ],
  "storage_usage": 50.0,
  "software_benchmark": 80,
  "hardware_benchmark": 32000,
  "overall_benchmark": 16040,
  "current_user": "administrator",
  "status": "active",
  "last_update": "2026-03-16T17:22:40"
}
```

**Response**:
```
Status: 200 OK
Body: "System data received successfully."
```

**Error Response**:
```json
Status: 500 Internal Server Error
Body: "Error processing data: [error details]"
```

---

#### 5. Manual Data Submission
```http
POST /manual_submit
Content-Type: application/json
```

**Purpose**: Manually submit or update local system data  
**Response**:
```
Status: 200 OK
Body: "Local system data submitted successfully."
     or "Local system data updated successfully."
```

---

#### 6. Create Backup
```http
POST /backup/create
```

**Response**:
```json
{
  "status": "success",
  "message": "Backup created: backup_20260316_172240.zip"
}
```

---

#### 7. Restore Backup
```http
POST /backup/restore/<filename>
```

**Parameters**:
- `filename`: Backup filename (e.g., `backup_20260316_172240.zip`)

**Response** (Success):
```json
{
  "status": "success",
  "message": "Backup restored successfully"
}
```

**Response** (Error):
```json
{
  "status": "error",
  "message": "Error restoring backup"
}
```

---

### Database Schema

#### SystemData Table

```sql
CREATE TABLE system_data (
  id                    INTEGER PRIMARY KEY,
  serial_number         VARCHAR(255) NOT NULL,
  hostname              VARCHAR(255) NOT NULL,
  model_number          VARCHAR(255),
  ip_address            VARCHAR(20),
  local_ip              VARCHAR(20),
  public_ip             VARCHAR(20),
  disk_info             JSON,
  cpu_usage             FLOAT,
  ram_usage             FLOAT,
  storage_usage         FLOAT,
  software_benchmark    FLOAT,
  hardware_benchmark    FLOAT,
  overall_benchmark     FLOAT,
  last_update           DATETIME DEFAULT CURRENT_TIMESTAMP,
  status                VARCHAR(20) DEFAULT 'active',
  deleted               BOOLEAN DEFAULT FALSE,
  cpu_info              VARCHAR(255),
  cpu_cores             INTEGER,
  cpu_threads           INTEGER,
  ram_info              JSON,
  current_user          VARCHAR(255),
  cpu_per_core          JSON,
  cpu_frequency         JSON
);
```

**⚠️ Schema Issues**:
- No unique constraint on serial_number (allows duplicates)
- No foreign key relationships
- Timezone confusion (UTC stored, IST displayed)
- See AUDIT_REPORT.md for detailed analysis

---

## Deployment

### Development Mode (Current)

**Setup**:
```bash
python server/app.py
```

**Characteristics**:
- ✅ Debug mode enabled (shows stack traces)
- ❌ Not suitable for production
- ❌ Single process, slow
- ❌ Exposes sensitive information

**Access**: http://localhost:5000

---

### Production Mode (Plan)

**Recommended Setup** (Not yet implemented):
```
Nginx (Reverse Proxy)
    ↓
Gunicorn (WSGI Server)
    ↓
Flask App (Multiple workers)
    ↓
PostgreSQL Database
    ↓
Redis Cache
```

**Deployment Steps** (To Be Implemented):
1. Create Dockerfile
2. Setup docker-compose.yml
3. Configure Gunicorn
4. Setup Nginx
5. Configure SSL/HTTPS
6. Setup monitoring and logging
7. Implement database migrations
8. Setup backup automation

**See**: Deployment section in AUDIT_REPORT.md

---

### Docker Deployment (Future)

```dockerfile
# Dockerfile (To be created)
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY server/ .
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
```

```yaml
# docker-compose.yml (To be created)
version: '3'
services:
  server:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=${SECRET_KEY}
```

---

## Contributing

### Code Standards
- Python style guide: PEP 8
- Naming: snake_case for functions/variables
- Comments: Document complex logic
- Tests: Write tests for new features

### Workflow
1. Fork repository
2. Create feature branch (`feature/your-feature`)
3. Commit changes with clear messages
4. Push to your fork
5. Create Pull Request with description

### Areas Needing Contributors
- ✅ Frontend improvements (UI/UX)
- ✅ Performance optimization
- ✅ Documentation
- ✅ Test coverage
- ✅ Docker deployment
- ✅ API authentication
- ✅ Database schema improvements

---

## License

This project is proprietary software by AadiTech.

**Usage Rights**:
- ✅ Internal use
- ✅ Development and testing
- ❌ Commercial distribution without license
- ❌ Sublicensing

For licensing inquiries, contact: `development@aaditech.com`

---

## Troubleshooting

### Server Issues

#### Problem: "Address already in use"
```
Error: Address already in use on port 5000
```
**Solution**:
```bash
# Find process using port 5000
lsof -i :5000

# Kill the process
kill -9 <PID>

# Or use a different port (edit app.py)
app.run(port=8000)
```

#### Problem: "No module named 'flask'"
```
ModuleNotFoundError: No module named 'flask'
```
**Solution**:
```bash
pip install -r requirements.txt
```

#### Problem: Database locked
```
sqlite3.OperationalError: database is locked
```
**Solution**:
```
1. Ensure only one app instance is running
2. Check for abandoned processes
3. Delete server/toolboxgalaxy.db-wal files
```

#### Problem: "Permission denied" on database
```
PermissionError: [Errno 13] Permission denied: 'toolboxgalaxy.db'
```
**Solution**:
```bash
# Fix permissions
chmod 666 server/toolboxgalaxy.db
chmod 755 server/
```

### Agent Issues

#### Problem: "Connection refused" when submitting data
```
ConnectionRefusedError: [Errno 111] Connection refused
```
**Solution**:
1. Verify server is running
2. Check SERVER_URL in agent.py
3. Verify network connectivity:
   ```bash
   ping <server-ip>
   curl http://<server-ip>:5000/admin
   ```
4. Check firewall rules

#### Problem: Agent collects data but server doesn't show it
**Solution**:
1. Check agent console for errors
2. Verify SERVER_URL includes full path: `/api/submit_data`
3. Check server logs
4. Ensure agent IP can reach server

#### Problem: "WMIC" errors on Windows agent
```
ERROR: [Errno 5] Access is denied
```
**Solution**:
- Run PowerShell as Administrator
- Try Linux compatibility mode if not Windows
- Update Windows Management Instrumentation

### Frontend Issues

#### Problem: Dashboard loads but shows no systems
**Solution**:
1. Ensure agents are running and submitting data
2. Check if data is in database:
   ```bash
   sqlite3 server/toolboxgalaxy.db
   sqlite> SELECT COUNT(*) FROM system_data;
   ```
3. Check server logs for data submission errors
4. Refresh browser page (F5)

#### Problem: Time displays incorrectly
**Solution**:
- Check timezone configuration in server/app.py
- Verify agent and server have correct system time
- Check database for UTC vs IST timestamps

### Database Issues

#### Backup creation fails
**Solution**:
1. Check write permissions on `server/backups/` directory
2. Ensure disk space available (need ~1-5 MB)
3. Check for corrupted database:
   ```bash
   sqlite3 server/toolboxgalaxy.db ".check"
   ```

#### Restore fails
**Solution**:
1. Verify backup file exists and is valid ZIP
2. Stop the server before restore
3. Check file permissions
4. Verify disk space

---

## Support

### Getting Help

**For Bugs**:
1. Check GitHub Issues: https://github.com/sahilk267/aaditech-ufo/issues
2. Create detailed bug report with steps to reproduce
3. Include error logs and system information

**For Questions**:
1. Check Troubleshooting section above
2. Review AUDIT_REPORT.md for architecture details
3. Contact team lead for enterprise support

**Documentation**:
- README.md (This file)
- AUDIT_REPORT.md (Detailed technical analysis)
- API Documentation (above)
- Code comments (in source files)

### Contact

- **Development Team**: development@aaditech.com
- **Project Lead**: [Lead info]
- **Issues/Bugs**: GitHub Issues

### Reporting Security Issues

⚠️ **DO NOT** create public issues for security vulnerabilities.

**Send to**: security@aaditech.com

Include:
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (optional)

---

## Acknowledgments

- Flask framework and extensions
- Bootstrap CSS framework
- psutil library for system metrics
- SQLAlchemy ORM
- The open-source community

---

## Changelog

### Version 1.0.0-pre-alpha (March 16, 2026)
- Initial development release
- Core monitoring functionality
- Web dashboard
- Backup/restore features
- Windows agent support
- See AUDIT_REPORT.md for known issues

---

## Appendix: Performance Benchmarks

### Benchmark Calculation

The platform calculates three benchmark scores:

```
Software Benchmark = Number of CPU Cores × 10
Hardware Benchmark = Total RAM in MB
Overall Benchmark = (Software Benchmark + Hardware Benchmark) / 2

Example:
- System: 8 cores, 32 GB RAM
- Software: 8 × 10 = 80
- Hardware: 32 × 1024 = 32,768
- Overall: (80 + 32,768) / 2 = 16,424
```

### Benchmark Interpretation

| Overall Score | Performance | Use Case |
|---------------|-------------|----------|
| < 4,000 | Low | Basic Office Work |
| 4,000-8,000 | Medium | Development |
| 8,000-16,000 | High | Workstation |
| > 16,000 | Very High | Server/Specialized |

---

## FAQ

**Q: How often does the agent collect data?**  
A: Every 60 seconds by default. Change `REPORT_INTERVAL` in agent.py

**Q: Can I use this with non-Windows systems?**  
A: Partial support for Linux. WMI queries are Windows-only; fallback uses psutil.

**Q: What if the server goes down?**  
A: Agent will log errors but keep retrying. Data can be resubmitted manual when server is back.

**Q: How long is data retained?**  
A: Indefinitely (until manually deleted). Plan archival strategy for production.

**Q: Can multiple servers monitor the same system?**  
A: No. Each system submits to one server. Multiple servers require separate configurations.

**Q: Is this suitable for production?**  
A: NOT in current state. See AUDIT_REPORT.md for production readiness assessment.

---

## Related Documentation

- **AUDIT_REPORT.md** - Comprehensive technical audit and implementation roadmap
- **GitHub Repository** - https://github.com/sahilk267/aaditech-ufo
- **Issue Tracker** - https://github.com/sahilk267/aaditech-ufo/issues

---

**Last Updated**: March 16, 2026  
**Documentation Version**: 1.0.0  
**Project Status**: Active Development
