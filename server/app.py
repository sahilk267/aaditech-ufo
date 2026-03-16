# server/app.py
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta
import logging
import platform
import requests
import psutil
import socket
import pytz
import subprocess
import getpass
import os
from dotenv import load_dotenv
from backup import create_backup, restore_backup, list_backups
from werkzeug.utils import secure_filename
from auth import require_api_key

# Load environment variables from .env file
load_dotenv()

def get_current_time():
    """Get current time in IST (India/Kolkata)"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def convert_to_ist(utc_dt):
    """Convert any datetime to IST"""
    if not utc_dt:
        return None
    ist = pytz.timezone('Asia/Kolkata')
    
    # If it's a string, convert to datetime
    if isinstance(utc_dt, str):
        try:
            utc_dt = datetime.fromisoformat(utc_dt.replace('Z', '+00:00'))
        except:
            try:
                # Try parsing without timezone
                utc_dt = datetime.fromisoformat(utc_dt)
            except:
                return None
    
    # If datetime has no timezone, assume it's already in IST
    if utc_dt.tzinfo is None:
        return ist.localize(utc_dt)
    
    return utc_dt.astimezone(ist)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///toolboxgalaxy.db'  # Or your chosen database
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Suppress a warning
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-change-in-production')  # Load from .env
# Configure logging
logging.basicConfig(level=logging.DEBUG)  # Set the logging level

db = SQLAlchemy(app)
migrate = Migrate(app, db)  # Initialize Flask-Migrate

# Define the data model
class SystemData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(255), nullable=False)
    hostname = db.Column(db.String(255), nullable=False)
    model_number = db.Column(db.String(255))
    ip_address = db.Column(db.String(20))
    local_ip = db.Column(db.String(20))
    public_ip = db.Column(db.String(20))
    disk_info = db.Column(db.JSON)  # Store disk information as JSON
    cpu_usage = db.Column(db.Float)
    ram_usage = db.Column(db.Float)
    storage_usage = db.Column(db.Float)  # Add storage usage field
    software_benchmark = db.Column(db.Float)
    hardware_benchmark = db.Column(db.Float)
    overall_benchmark = db.Column(db.Float)
    last_update = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='active')
    deleted = db.Column(db.Boolean, default=False)
    cpu_info = db.Column(db.String(255))
    cpu_cores = db.Column(db.Integer)
    cpu_threads = db.Column(db.Integer)
    ram_info = db.Column(db.JSON)
    current_user = db.Column(db.String(255))
    cpu_per_core = db.Column(db.JSON)
    cpu_frequency = db.Column(db.JSON)

# Create the database tables (run this once)
with app.app_context():
    db.create_all()

@app.template_filter('ist_format')
def ist_format(value):
    """Format datetime to IST string"""
    ist_time = convert_to_ist(value)
    if ist_time is None:
        return 'N/A'
    return ist_time.strftime('%d-%m-%Y %I:%M:%S %p')  # Removed extra IST

def check_active(last_update, now):
    """Check if a system is active based on its last update time"""
    if last_update is None:
        return False
    
    ist = pytz.timezone('Asia/Kolkata')
    now = now if now.tzinfo else ist.localize(now)
    
    last_update_ist = convert_to_ist(last_update)
    if last_update_ist is None:
        return False
        
    return (now - last_update_ist).total_seconds() < 300

# Add template global
@app.context_processor
def utility_processor():
    return {
        'is_active': check_active,
        'current_time': get_current_time
    }

@app.route('/')
def index():
    return redirect(url_for('admin_panel')) # Redirect to the admin panel

@app.route('/admin')
def admin_panel():
    system_data = SystemData.query.order_by(SystemData.last_update.desc()).all()
    now = get_current_time()  # Use the new function
    return render_template('admin.html', system_data=system_data, now=now)

@app.route('/user', defaults={'serial_number': None})
@app.route('/user/<serial_number>')
def user_panel(serial_number):
    if serial_number:
        logging.debug(f"Fetching data for serial number: {serial_number}")
        system_data = SystemData.query.filter_by(serial_number=serial_number).first()
    else:
        logging.debug("Fetching local system data")
        system_data = get_local_system_data()
    
    if system_data:
        logging.debug(f"System data found: {system_data}")
        return render_template('user.html', system_data=system_data)
    else:
        logging.debug("System not found")
        return "System not found", 404

@app.route('/user/<serial_number>/history')
def user_history(serial_number):
    system_data = SystemData.query.filter_by(serial_number=serial_number).order_by(SystemData.last_update.desc()).all()
    if system_data:
        now = get_current_time()  # Use the new function
        return render_template('user_history.html', system_data=system_data, now=now)
    else:
        return "System not found", 404

def get_local_system_data():
    # Get serial number
    try:
        serial_cmd = subprocess.check_output('wmic bios get serialnumber').decode('utf-8').split('\n')[1].strip()
        serial_number = serial_cmd if serial_cmd and serial_cmd != "To be filled by O.E.M." else "Unknown"
    except:
        try:
            systeminfo = subprocess.check_output('systeminfo').decode('utf-8')
            for line in systeminfo.split('\n'):
                if "BIOS Version" in line:
                    serial_number = line.split(':')[1].strip()
                    break
            else:
                serial_number = platform.node()
        except:
            serial_number = platform.node()

    # Get model number
    try:
        model_cmd = subprocess.check_output('wmic csproduct get name').decode('utf-8').split('\n')[1].strip()
        if model_cmd and model_cmd != "To be filled by O.E.M.":
            model_number = model_cmd
        else:
            model_cmd = subprocess.check_output('wmic computersystem get model').decode('utf-8').split('\n')[1].strip()
            model_number = model_cmd if model_cmd else "Unknown Model"
    except:
        model_number = "Unknown Model"

    # Get disk information
    disk_info = []
    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disk_info.append({
                'device': partition.device,
                'mountpoint': partition.mountpoint,
                'total': usage.total / (1024**3),
                'used': usage.used / (1024**3),
                'free': usage.free / (1024**3),
                'percent': usage.percent
            })
        except:
            continue

    # Get RAM information
    ram = psutil.virtual_memory()
    ram_info = {
        'total': ram.total / (1024**3),
        'available': ram.available / (1024**3),
        'used': (ram.total - ram.available) / (1024**3),
        'percent': ram.percent
    }

    # Get IP addresses
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        public_ip = requests.get('https://api.ipify.org').text
    except:
        local_ip = "Unknown"
        public_ip = "Unknown"

    # Get CPU information
    try:
        cpu_info = subprocess.check_output('wmic cpu get name').decode('utf-8').split('\n')[1].strip()
    except:
        cpu_info = platform.processor()

    # Get current user
    current_user = getpass.getuser()
    
    # Get accurate CPU metrics
    cpu_usage = psutil.cpu_percent(interval=2)
    cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
    cpu_freq = psutil.cpu_freq()

    current_time = get_current_time()
    
    return {
        "serial_number": serial_number,
        "hostname": platform.node(),
        "model_number": model_number,
        "ip_address": public_ip,
        "local_ip": local_ip,
        "public_ip": public_ip,
        "disk_info": disk_info,
        "cpu_usage": cpu_usage,
        "ram_usage": ram.percent,
        "ram_info": ram_info,
        "storage_usage": psutil.disk_usage('/').percent,
        "cpu_info": cpu_info,
        "cpu_cores": psutil.cpu_count(logical=False),
        "cpu_threads": psutil.cpu_count(logical=True),
        "software_benchmark": psutil.cpu_count() * 10,
        "hardware_benchmark": psutil.virtual_memory().total / (1024 * 1024),
        "overall_benchmark": (psutil.cpu_count() * 10 + psutil.virtual_memory().total / (1024 * 1024)) / 2,
        "last_update": current_time,  # Store the datetime object directly
        "status": "active",
        "current_user": current_user,
        "cpu_per_core": cpu_per_core,
        "cpu_frequency": {
            "current": cpu_freq.current if cpu_freq else None,
            "min": cpu_freq.min if cpu_freq else None,
            "max": cpu_freq.max if cpu_freq else None
        }
    }

@app.route('/manual_submit', methods=['POST'])
def manual_submit():
    try:
        data = get_local_system_data()
        logging.debug(f"Manually submitting local system data: {data}")
        
        # No need to convert last_update as it's already a datetime object
        
        existing_system = SystemData.query.filter_by(serial_number=data.get('serial_number')).first()
        if existing_system:
            existing_system.hostname = data.get('hostname')
            existing_system.model_number = data.get('model_number')
            existing_system.ip_address = data.get('ip_address')
            existing_system.local_ip = data.get('local_ip')
            existing_system.public_ip = data.get('public_ip')
            existing_system.disk_info = data.get('disk_info')
            existing_system.cpu_usage = data.get('cpu_usage')
            existing_system.ram_usage = data.get('ram_usage')
            existing_system.storage_usage = data.get('storage_usage')
            existing_system.software_benchmark = data.get('software_benchmark')
            existing_system.hardware_benchmark = data.get('hardware_benchmark')
            existing_system.overall_benchmark = data.get('overall_benchmark')
            existing_system.last_update = data.get('last_update')
            existing_system.current_user = data.get('current_user')
            existing_system.cpu_per_core = data.get('cpu_per_core')
            existing_system.cpu_frequency = data.get('cpu_frequency')
            db.session.commit()
            return "Local system data updated successfully."
        else:
            new_system = SystemData(**data)
            db.session.add(new_system)
            db.session.commit()
            return "Local system data submitted successfully."
    except Exception as e:
        logging.error(f"Error processing manual submission: {e}")
        return str(e), 500

@app.route('/api/submit_data', methods=['POST'])
@require_api_key
def submit_data():
    try:
        data = request.get_json()
        logging.debug(f"Received data from agent: {data}")
        # Create a new record for each submission instead of updating
        data['last_update'] = datetime.fromisoformat(data['last_update'])
        new_system = SystemData(**data)
        db.session.add(new_system)
        db.session.commit()
        return "System data received successfully."
    except Exception as e:
        logging.error(f"Error processing data: {e}")
        return str(e), 500

@app.route('/backup')
def backup_panel():
    backups = list_backups()
    return render_template('backup.html', backups=backups)

@app.route('/backup/create', methods=['POST'])
def create_backup_route():
    try:
        backup_file = create_backup()
        return jsonify({'status': 'success', 'message': f'Backup created: {os.path.basename(backup_file)}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/backup/restore/<filename>', methods=['POST'])
def restore_backup_route(filename):
    try:
        backup_path = os.path.join(BACKUP_DIR, secure_filename(filename))
        restore_backup(backup_path)
        return jsonify({'status': 'success', 'message': 'Backup restored successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

BACKUP_DIR = os.path.join(os.path.dirname(__file__), 'backups')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)  # Ensure the server is listening on all interfaces