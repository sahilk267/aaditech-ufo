# server/services/system_service.py
"""
System Service
Handles system monitoring, data collection, and management
"""

import logging
import platform
import subprocess
import socket
import getpass
import psutil
import requests
import pytz
from datetime import datetime

logger = logging.getLogger(__name__)


class SystemService:
    """Service for managing system data and metrics"""
    
    @staticmethod
    def get_system_info():
        """
        Collect comprehensive system information.
        
        Returns:
            dict: System information including serial number, hardware details
        """
        try:
            # Get serial number
            serial_number = SystemService._get_serial_number()
            
            # Get model number
            model_number = SystemService._get_model_number()
            
            # Get IP addresses
            local_ip, public_ip = SystemService._get_ip_addresses()
            
            # Get CPU information
            cpu_info = SystemService._get_cpu_info()
            
            # Get current user
            current_user = getpass.getuser()
            
            return {
                "serial_number": serial_number,
                "hostname": platform.node(),
                "model_number": model_number,
                "local_ip": local_ip,
                "public_ip": public_ip,
                "cpu_info": cpu_info,
                "cpu_cores": psutil.cpu_count(logical=False),
                "cpu_threads": psutil.cpu_count(logical=True),
                "current_user": current_user
            }
        except Exception as e:
            logger.error(f"Error collecting system info: {e}")
            return {}
    
    @staticmethod
    def _get_serial_number():
        """Get system serial number"""
        try:
            return subprocess.check_output('wmic bios get serialnumber').decode('utf-8').split('\n')[1].strip()
        except:
            try:
                return platform.node()
            except:
                return "Unknown"
    
    @staticmethod
    def _get_model_number():
        """Get system model number"""
        try:
            model_cmd = subprocess.check_output('wmic csproduct get name').decode('utf-8').split('\n')[1].strip()
            if model_cmd and model_cmd != "To be filled by O.E.M.":
                return model_cmd
            model_cmd = subprocess.check_output('wmic computersystem get model').decode('utf-8').split('\n')[1].strip()
            return model_cmd if model_cmd else "Unknown Model"
        except:
            return "Unknown Model"
    
    @staticmethod
    def _get_ip_addresses():
        """Get local and public IP addresses"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            public_ip = requests.get('https://api.ipify.org').text
            return local_ip, public_ip
        except:
            return "Unknown", "Unknown"
    
    @staticmethod
    def _get_cpu_info():
        """Get CPU information"""
        try:
            return subprocess.check_output('wmic cpu get name').decode('utf-8').split('\n')[1].strip()
        except:
            return platform.processor()
    
    @staticmethod
    def get_performance_metrics():
        """
        Collect current performance metrics.
        
        Returns:
            dict: CPU, memory, disk, and network metrics
        """
        try:
            cpu_usage = psutil.cpu_percent(interval=2)
            cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
            cpu_freq = psutil.cpu_freq()
            ram = psutil.virtual_memory()
            disk_info = SystemService._get_disk_info()
            
            return {
                "cpu_usage": cpu_usage,
                "cpu_per_core": cpu_per_core,
                "cpu_frequency": {
                    "current": cpu_freq.current if cpu_freq else None,
                    "min": cpu_freq.min if cpu_freq else None,
                    "max": cpu_freq.max if cpu_freq else None
                },
                "ram_usage": ram.percent,
                "ram_info": {
                    'total': ram.total / (1024**3),
                    'available': ram.available / (1024**3),
                    'used': (ram.total - ram.available) / (1024**3),
                    'percent': ram.percent
                },
                "disk_info": disk_info,
                "storage_usage": psutil.disk_usage('/').percent
            }
        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
            return {}
    
    @staticmethod
    def _get_disk_info():
        """Get disk partition information"""
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
        return disk_info
    
    @staticmethod
    def get_benchmark_results():
        """
        Calculate benchmark results.
        
        Returns:
            dict: Software, hardware, and overall benchmark scores
        """
        software_benchmark = psutil.cpu_count() * 10
        hardware_benchmark = psutil.virtual_memory().total / (1024 * 1024)
        overall_benchmark = (software_benchmark + hardware_benchmark) / 2
        
        return {
            "software_benchmark": software_benchmark,
            "hardware_benchmark": hardware_benchmark,
            "overall_benchmark": overall_benchmark
        }
    
    @staticmethod
    def get_current_time():
        """Get current time in IST"""
        ist = pytz.timezone('Asia/Kolkata')
        return datetime.now(ist)
    
    @staticmethod
    def is_active(last_update, now):
        """
        Check if system is active based on last update time.
        
        Args:
            last_update: Last update datetime
            now: Current datetime
        
        Returns:
            bool: True if last update was within 5 minutes
        """
        if last_update is None:
            return False
        
        ist = pytz.timezone('Asia/Kolkata')
        now = now if now.tzinfo else ist.localize(now)
        
        # Convert last_update to IST if needed
        if last_update.tzinfo is None:
            last_update_ist = ist.localize(last_update)
        else:
            last_update_ist = last_update.astimezone(ist)
        
        return (now - last_update_ist).total_seconds() < 300
