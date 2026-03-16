# server/services/backup_service.py
"""
Backup Service
Handles database backup creation, restoration, and management
"""

import logging
import os
import shutil
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)


class BackupService:
    """Service for managing database backups"""
    
    # Backup directory path
    BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'backups')
    
    @staticmethod
    def ensure_backup_directory():
        """Ensure backup directory exists"""
        if not os.path.exists(BackupService.BACKUP_DIR):
            os.makedirs(BackupService.BACKUP_DIR)
            logger.info(f"Created backup directory: {BackupService.BACKUP_DIR}")
    
    @staticmethod
    def create_backup(database_path):
        """
        Create a backup of the database.
        
        Args:
            database_path (str): Path to the database file
        
        Returns:
            dict: Backup information including path, timestamp, and size
        """
        try:
            BackupService.ensure_backup_directory()
            
            if not os.path.exists(database_path):
                logger.error(f"Database not found: {database_path}")
                return {'success': False, 'error': 'Database not found'}
            
            # Create backup filename with timestamp
            ist = pytz.timezone('Asia/Kolkata')
            timestamp = datetime.now(ist).strftime('%Y%m%d_%H%M%S')
            backup_filename = f'backup_{timestamp}.db'
            backup_path = os.path.join(BackupService.BACKUP_DIR, backup_filename)
            
            # Copy database file
            shutil.copy2(database_path, backup_path)
            
            # Get backup file size
            backup_size = os.path.getsize(backup_path)
            
            logger.info(f"Backup created: {backup_path}")
            
            return {
                'success': True,
                'backup_path': backup_path,
                'backup_filename': backup_filename,
                'timestamp': timestamp,
                'size_bytes': backup_size,
                'size_mb': round(backup_size / (1024 * 1024), 2)
            }
        
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def list_backups():
        """
        List all available backups.
        
        Returns:
            list: List of backup files with details
        """
        try:
            BackupService.ensure_backup_directory()
            
            backups = []
            for filename in sorted(os.listdir(BackupService.BACKUP_DIR), reverse=True):
                if filename.endswith('.db'):
                    filepath = os.path.join(BackupService.BACKUP_DIR, filename)
                    size = os.path.getsize(filepath)
                    timestamp = os.path.getmtime(filepath)
                    
                    backups.append({
                        'filename': filename,
                        'path': filepath,
                        'size_bytes': size,
                        'size_mb': round(size / (1024 * 1024), 2),
                        'modified': datetime.fromtimestamp(timestamp).isoformat(),
                        'created': filename.split('_')[1:3]  # Extract date and time from filename
                    })
            
            return backups
        
        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            return []
    
    @staticmethod
    def restore_backup(backup_path, target_path):
        """
        Restore a backup to the database.
        
        Args:
            backup_path (str): Path to backup file
            target_path (str): Path to restore to
        
        Returns:
            dict: Restoration result
        """
        try:
            if not os.path.exists(backup_path):
                logger.error(f"Backup not found: {backup_path}")
                return {'success': False, 'error': 'Backup not found'}
            
            # Create backup of current database before restoration
            if os.path.exists(target_path):
                backup_before_restore = f"{target_path}.pre_restore_backup"
                shutil.copy2(target_path, backup_before_restore)
                logger.info(f"Backup of current database: {backup_before_restore}")
            
            # Restore database
            shutil.copy2(backup_path, target_path)
            
            logger.info(f"Database restored from: {backup_path}")
            
            return {
                'success': True,
                'message': 'Database restored successfully',
                'restored_from': backup_path,
                'timestamp': datetime.now(pytz.timezone('Asia/Kolkata')).isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error restoring backup: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def delete_backup(backup_path):
        """
        Delete a backup file.
        
        Args:
            backup_path (str): Path to backup file
        
        Returns:
            dict: Deletion result
        """
        try:
            if not os.path.exists(backup_path):
                logger.error(f"Backup not found: {backup_path}")
                return {'success': False, 'error': 'Backup not found'}
            
            os.remove(backup_path)
            logger.info(f"Backup deleted: {backup_path}")
            
            return {
                'success': True,
                'message': 'Backup deleted successfully',
                'deleted': backup_path
            }
        
        except Exception as e:
            logger.error(f"Error deleting backup: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_backup_stats():
        """
        Get backup statistics.
        
        Returns:
            dict: Backup statistics
        """
        try:
            backups = BackupService.list_backups()
            
            if not backups:
                return {
                    'total_backups': 0,
                    'total_size_mb': 0,
                    'latest_backup': None
                }
            
            total_size = sum(b['size_bytes'] for b in backups)
            
            return {
                'total_backups': len(backups),
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'latest_backup': backups[0] if backups else None,
                'oldest_backup': backups[-1] if backups else None
            }
        
        except Exception as e:
            logger.error(f"Error getting backup stats: {e}")
            return {}
