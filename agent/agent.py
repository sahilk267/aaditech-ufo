# agent/agent.py
import platform
import psutil
import uuid
import requests
import json
import time
import os
import subprocess
import socket
import getpass
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

SERVER_URL = "http://192.168.86.152:5000/api/submit_data"
AGENT_API_KEY = os.getenv('AGENT_API_KEY', 'dev-agent-api-key-12345-change-in-production')
REPORT_INTERVAL = 60

def get_system_info():
    try:
        # Get serial number
        serial_number = subprocess.check_output('wmic bios get serialnumber').decode('utf-8').split('\n')[1].strip()
        
        # Get CPU info
        cpu_info = subprocess.check_output('wmic cpu get name').decode('utf-8').split('\n')[1].strip()
        
        # Get system model - try multiple methods
        try:
            model_cmd = subprocess.check_output('wmic csproduct get name').decode('utf-8').split('\n')[1].strip()
            if model_cmd and model_cmd != "To be filled by O.E.M.":
                model_number = model_cmd
            else:
                model_cmd = subprocess.check_output('wmic computersystem get model').decode('utf-8').split('\n')[1].strip()
                model_number = model_cmd if model_cmd else "Unknown Model"
        except:
            model_number = "Unknown Model"
        
        # Get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # Get current logged-in user
        current_user = getpass.getuser()
        
    except Exception as e:
        print(f"Error getting system info: {e}")
        serial_number = "N/A"
        cpu_info = platform.processor()
        model_number = "Unknown Model"
        local_ip = "N/A"
        current_user = "N/A"

    # Get detailed RAM information
    ram = psutil.virtual_memory()
    ram_info = {
        'total': ram.total / (1024**3),  # Convert to GB
        'available': ram.available / (1024**3),
        'used': (ram.total - ram.available) / (1024**3),
        'percent': ram.percent
    }

    return {
        "serial_number": serial_number,
        "hostname": platform.node(),
        "model_number": model_number,  # Updated model number
        "local_ip": local_ip,
        "public_ip": requests.get('https://api.ipify.org').text,
        "cpu_info": cpu_info,
        "cpu_cores": psutil.cpu_count(logical=False),  # Physical cores
        "cpu_threads": psutil.cpu_count(logical=True),  # Logical cores
        "ram_info": ram_info,
        "current_user": current_user
    }

def get_performance_metrics():
    # Get CPU usage with longer interval for accuracy
    cpu_usage = psutil.cpu_percent(interval=2)
    
    # Get per-core CPU usage
    cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
    
    # Get CPU frequency
    cpu_freq = psutil.cpu_freq()
    
    ram_usage = psutil.virtual_memory().percent
    
    # Get all disk partitions
    disk_info = []
    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disk_info.append({
                'device': partition.device,
                'mountpoint': partition.mountpoint,
                'total': usage.total / (1024**3),  # Convert to GB
                'used': usage.used / (1024**3),
                'free': usage.free / (1024**3),
                'percent': usage.percent
            })
        except:
            continue

    return {
        "cpu_usage": cpu_usage,
        "cpu_per_core": cpu_per_core,
        "cpu_frequency": {
            "current": cpu_freq.current if cpu_freq else None,
            "min": cpu_freq.min if cpu_freq else None,
            "max": cpu_freq.max if cpu_freq else None
        },
        "ram_usage": ram_usage,
        "disk_info": disk_info,
    }

def run_benchmark():
    software_benchmark = psutil.cpu_count() * 10
    hardware_benchmark = psutil.virtual_memory().total / (1024 * 1024)
    overall_benchmark = (software_benchmark + hardware_benchmark) / 2
    return {
        "software_benchmark": software_benchmark,
        "hardware_benchmark": hardware_benchmark,
        "overall_benchmark": overall_benchmark,
    }

def send_data(data):
    try:
        headers = {
            'X-API-Key': AGENT_API_KEY,
            'Content-Type': 'application/json'
        }
        response = requests.post(SERVER_URL, json=data, headers=headers, timeout=10)  # Add timeout parameter
        response.raise_for_status()
        print("Data sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Error sending data: {e}")

def main():
    while True:
        system_info = get_system_info()
        performance_metrics = get_performance_metrics()
        benchmark_results = run_benchmark()
        data = {**system_info, **performance_metrics, **benchmark_results}

        # Convert datetime to ISO 8601 string
        timestamp = time.time()
        dt_object = datetime.fromtimestamp(timestamp)
        data["last_update"] = dt_object.isoformat()  # Convert to ISO string

        data["status"] = "active"
        print(data)
        send_data(data)
        time.sleep(REPORT_INTERVAL)

if __name__ == "__main__":
    main()