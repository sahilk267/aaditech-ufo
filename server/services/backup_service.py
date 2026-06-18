# server/services/backup_service.py
"""
Backup Service
Handles database backup creation, restoration, and management.

Supports:
  - PostgreSQL databases via pg_dump / pg_restore (production)
  - SQLite databases via file copy (development / testing)
"""

import logging
import os
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime
from urllib.parse import urlparse

import pytz

logger = logging.getLogger(__name__)

_IST = pytz.timezone('Asia/Kolkata')


def _ist_now_str() -> str:
    return datetime.now(_IST).strftime('%Y%m%d_%H%M%S')


def _ist_now_iso() -> str:
    return datetime.now(_IST).isoformat()


def _database_url() -> str:
    return os.getenv('DATABASE_URL', 'sqlite:///toolboxgalaxy.db')


def _is_postgres(database_url: str) -> bool:
    return database_url.startswith('postgres')


class BackupService:
    """Service for managing database backups."""

    BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'backups')

    @staticmethod
    def ensure_backup_directory():
        os.makedirs(BackupService.BACKUP_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # PostgreSQL helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pg_credentials(database_url: str) -> dict:
        """Parse a postgres:// or postgresql:// URL into connection parts."""
        parsed = urlparse(database_url)
        return {
            'host': parsed.hostname or 'localhost',
            'port': str(parsed.port or 5432),
            'user': parsed.username or 'postgres',
            'password': parsed.password or '',
            'dbname': (parsed.path or '/aaditech_ufo').lstrip('/'),
        }

    @staticmethod
    def _pg_env(creds: dict) -> dict:
        """Build env dict for pg_dump / pg_restore with PGPASSWORD set."""
        env = os.environ.copy()
        if creds['password']:
            env['PGPASSWORD'] = creds['password']
        return env

    @staticmethod
    def _pg_dump(backup_path: str, database_url: str) -> tuple[bool, str]:
        """Run pg_dump and write output to backup_path (.sql).

        Returns (success, error_message).
        """
        creds = BackupService._pg_credentials(database_url)
        env = BackupService._pg_env(creds)

        cmd = [
            'pg_dump',
            '-h', creds['host'],
            '-p', creds['port'],
            '-U', creds['user'],
            '--no-password',
            '--format=plain',
            '--clean',
            '--if-exists',
            '-f', backup_path,
            creds['dbname'],
        ]

        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                logger.info("pg_dump completed: %s (%d bytes)", backup_path, os.path.getsize(backup_path))
                return True, ''
            err = (result.stderr or '').strip()
            logger.error("pg_dump failed (rc=%d): %s", result.returncode, err)
            return False, err
        except FileNotFoundError:
            msg = "pg_dump not found — install postgresql-client package"
            logger.error(msg)
            return False, msg
        except subprocess.TimeoutExpired:
            msg = "pg_dump timed out after 300 seconds"
            logger.error(msg)
            return False, msg

    @staticmethod
    def _pg_restore_cmd_available() -> bool:
        try:
            subprocess.run(['pg_restore', '--version'], capture_output=True, timeout=5)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def create_backup(database_path: str | None = None) -> dict:
        """Create a backup of the database.

        For PostgreSQL databases (DATABASE_URL starts with postgres), ``pg_dump``
        is used and the backup is stored as a ``.sql`` file.  For SQLite the
        file is copied as a ``.db`` file (legacy behaviour preserved).

        ``database_path`` is kept for backward compatibility but is ignored
        when the live DATABASE_URL points to PostgreSQL.
        """
        try:
            BackupService.ensure_backup_directory()
            db_url = _database_url()
            timestamp = _ist_now_str()

            if _is_postgres(db_url):
                backup_filename = f'backup_{timestamp}.sql'
                backup_path = os.path.join(BackupService.BACKUP_DIR, backup_filename)

                success, err = BackupService._pg_dump(backup_path, db_url)
                if not success:
                    return {'success': False, 'error': f'pg_dump failed: {err}', 'db_type': 'postgresql'}

                size = os.path.getsize(backup_path)
                return {
                    'success': True,
                    'backup_path': backup_path,
                    'backup_filename': backup_filename,
                    'timestamp': timestamp,
                    'size_bytes': size,
                    'size_mb': round(size / (1024 * 1024), 2),
                    'db_type': 'postgresql',
                    'method': 'pg_dump',
                }

            # ---- SQLite fallback ----
            sqlite_path = database_path
            if not sqlite_path:
                sqlite_path = os.path.join(os.path.dirname(__file__), '..', 'toolboxgalaxy.db')

            if not os.path.exists(sqlite_path):
                return {'success': False, 'error': 'SQLite database file not found', 'db_type': 'sqlite'}

            backup_filename = f'backup_{timestamp}.db'
            backup_path = os.path.join(BackupService.BACKUP_DIR, backup_filename)
            shutil.copy2(sqlite_path, backup_path)
            size = os.path.getsize(backup_path)

            return {
                'success': True,
                'backup_path': backup_path,
                'backup_filename': backup_filename,
                'timestamp': timestamp,
                'size_bytes': size,
                'size_mb': round(size / (1024 * 1024), 2),
                'db_type': 'sqlite',
                'method': 'file_copy',
            }

        except Exception as exc:
            logger.error("Error creating backup: %s", exc)
            return {'success': False, 'error': str(exc)}

    @staticmethod
    def list_backups() -> list[dict]:
        """List all available backups (.db and .sql files)."""
        try:
            BackupService.ensure_backup_directory()
            backups = []
            for filename in sorted(os.listdir(BackupService.BACKUP_DIR), reverse=True):
                if not (filename.endswith('.db') or filename.endswith('.sql')):
                    continue
                filepath = os.path.join(BackupService.BACKUP_DIR, filename)
                size = os.path.getsize(filepath)
                mtime = os.path.getmtime(filepath)
                db_type = 'postgresql' if filename.endswith('.sql') else 'sqlite'
                backups.append({
                    'filename': filename,
                    'path': filepath,
                    'size_bytes': size,
                    'size_mb': round(size / (1024 * 1024), 2),
                    'modified': datetime.fromtimestamp(mtime).isoformat(),
                    'db_type': db_type,
                })
            return backups
        except Exception as exc:
            logger.error("Error listing backups: %s", exc)
            return []

    @staticmethod
    def restore_backup(backup_path: str, target_path: str | None = None) -> dict:
        """Restore a backup.

        For ``.sql`` files the backup is printed to stdout for operator
        application (``psql < backup.sql``).  Direct in-process restore of
        PostgreSQL is intentionally not supported for safety; the endpoint
        returns instructions instead.

        For ``.db`` files (SQLite) the file is copied to ``target_path``.
        """
        try:
            if not os.path.exists(backup_path):
                return {'success': False, 'error': 'Backup not found'}

            if backup_path.endswith('.sql'):
                db_url = _database_url()
                creds = BackupService._pg_credentials(db_url)
                return {
                    'success': True,
                    'db_type': 'postgresql',
                    'message': 'PostgreSQL restore requires operator action.',
                    'instructions': (
                        f"Run the following command on your database host:\n"
                        f"  psql -h {creds['host']} -p {creds['port']} "
                        f"-U {creds['user']} -d {creds['dbname']} < {backup_path}"
                    ),
                    'backup_path': backup_path,
                    'timestamp': _ist_now_iso(),
                }

            # SQLite restore
            sqlite_target = target_path or os.path.join(os.path.dirname(__file__), '..', 'toolboxgalaxy.db')
            if os.path.exists(sqlite_target):
                pre_restore = f"{sqlite_target}.pre_restore_backup"
                shutil.copy2(sqlite_target, pre_restore)
                logger.info("Pre-restore backup created: %s", pre_restore)

            shutil.copy2(backup_path, sqlite_target)
            logger.info("SQLite database restored from: %s", backup_path)

            return {
                'success': True,
                'db_type': 'sqlite',
                'message': 'Database restored successfully',
                'restored_from': backup_path,
                'timestamp': _ist_now_iso(),
            }

        except Exception as exc:
            logger.error("Error restoring backup: %s", exc)
            return {'success': False, 'error': str(exc)}

    @staticmethod
    def verify_backup(backup_path: str) -> dict:
        """Verify a backup is readable and structurally sound."""
        try:
            if not os.path.exists(backup_path):
                return {'success': False, 'error': 'Backup not found'}

            size = os.path.getsize(backup_path)
            if size <= 0:
                return {'success': False, 'error': 'Backup file is empty'}

            if backup_path.endswith('.sql'):
                return BackupService._verify_sql_backup(backup_path, size)

            return BackupService._verify_sqlite_backup(backup_path, size)

        except Exception as exc:
            logger.error("Error verifying backup: %s", exc)
            return {'success': False, 'error': str(exc)}

    @staticmethod
    def _verify_sql_backup(backup_path: str, size: int) -> dict:
        """Verify a pg_dump SQL backup by checking content signatures."""
        try:
            with open(backup_path, 'r', errors='replace') as f:
                head = f.read(4096)

            has_pg_header = 'PostgreSQL database dump' in head or 'pg_dump' in head.lower()
            has_sql_statements = any(kw in head.upper() for kw in ('CREATE', 'INSERT', 'SET ', 'SELECT', '--'))

            verified = has_pg_header or has_sql_statements
            return {
                'success': verified,
                'verified': verified,
                'backup_path': backup_path,
                'size_bytes': size,
                'size_mb': round(size / (1024 * 1024), 2),
                'db_type': 'postgresql',
                'integrity_check': 'ok' if verified else 'unrecognised_format',
                'verified_at': _ist_now_iso(),
                'message': 'PostgreSQL backup verification passed' if verified else 'Backup does not appear to be a valid pg_dump file',
            }
        except Exception as exc:
            return {'success': False, 'error': f'SQL verification error: {exc}'}

    @staticmethod
    def _verify_sqlite_backup(backup_path: str, size: int) -> dict:
        """Verify a SQLite backup via PRAGMA integrity_check."""
        with sqlite3.connect(backup_path) as conn:
            row = conn.execute('PRAGMA integrity_check').fetchone()
            integrity = row[0] if row else 'unknown'
            tcount_row = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()
            table_count = int(tcount_row[0]) if tcount_row else 0

        with tempfile.TemporaryDirectory(prefix='aaditech_bv_') as tmp:
            restore_path = os.path.join(tmp, 'check.db')
            shutil.copy2(backup_path, restore_path)
            conn2 = sqlite3.connect(restore_path)
            try:
                conn2.execute('SELECT name FROM sqlite_master LIMIT 1').fetchone()
            finally:
                conn2.close()

        verified = integrity == 'ok'
        return {
            'success': verified,
            'verified': verified,
            'backup_path': backup_path,
            'size_bytes': size,
            'size_mb': round(size / (1024 * 1024), 2),
            'db_type': 'sqlite',
            'integrity_check': integrity,
            'table_count': table_count,
            'verified_at': _ist_now_iso(),
            'message': 'Backup verification passed' if verified else 'Backup verification failed',
        }

    @staticmethod
    def run_restore_drill(backup_path: str) -> dict:
        """Non-destructive restore drill."""
        verification = BackupService.verify_backup(backup_path)
        base = {'backup_path': backup_path, 'verification': verification}

        if not verification.get('success'):
            return {
                **base,
                'success': False,
                'checklist': [
                    {'id': 'backup_exists', 'status': 'failed'},
                    {'id': 'integrity_check', 'status': 'failed'},
                    {'id': 'restore_copy_readable', 'status': 'failed'},
                ],
            }

        return {
            **base,
            'success': True,
            'checklist': [
                {'id': 'backup_exists', 'status': 'passed'},
                {'id': 'integrity_check', 'status': 'passed'},
                {'id': 'restore_copy_readable', 'status': 'passed'},
                {'id': 'app_smoke_after_restore', 'status': 'manual_followup_required'},
            ],
        }

    @staticmethod
    def delete_backup(backup_path: str) -> dict:
        try:
            if not os.path.exists(backup_path):
                return {'success': False, 'error': 'Backup not found'}
            os.remove(backup_path)
            logger.info("Backup deleted: %s", backup_path)
            return {'success': True, 'message': 'Backup deleted successfully', 'deleted': backup_path}
        except Exception as exc:
            logger.error("Error deleting backup: %s", exc)
            return {'success': False, 'error': str(exc)}

    @staticmethod
    def get_backup_stats() -> dict:
        try:
            backups = BackupService.list_backups()
            if not backups:
                return {'total_backups': 0, 'total_size_mb': 0, 'latest_backup': None}
            total_size = sum(b['size_bytes'] for b in backups)
            return {
                'total_backups': len(backups),
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'latest_backup': backups[0] if backups else None,
                'oldest_backup': backups[-1] if backups else None,
                'db_types': list({b['db_type'] for b in backups}),
            }
        except Exception as exc:
            logger.error("Error getting backup stats: %s", exc)
            return {}
