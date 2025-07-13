"""
Database backup utilities
"""

import logging
import subprocess
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
import shutil
import gzip
from ..config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class BackupManager:
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        
    def create_backup(self) -> Optional[Path]:
        """
        Create a database backup
        Returns the path to the backup file if successful, None otherwise
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"backup_{timestamp}.sql.gz"
            
            # Parse database URL
            db_url = settings.DATABASE_URL
            if db_url.startswith("postgresql://"):
                db_params = self._parse_postgres_url(db_url)
                
                # Create pg_dump command
                cmd = [
                    "pg_dump",
                    "-h", db_params["host"],
                    "-p", db_params["port"],
                    "-U", db_params["user"],
                    "-d", db_params["database"],
                    "-F", "p",  # plain text format
                    "-w"  # no password prompt
                ]
                
                # Set PGPASSWORD environment variable
                env = os.environ.copy()
                env["PGPASSWORD"] = db_params["password"]
                
                # Execute pg_dump and compress output
                with gzip.open(backup_file, 'wb') as gz:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env
                    )
                    stdout, stderr = process.communicate()
                    
                    if process.returncode != 0:
                        logger.error(f"Backup failed: {stderr.decode()}")
                        return None
                    
                    gz.write(stdout)
                
                logger.info(f"Backup created successfully: {backup_file}")
                return backup_file
            else:
                logger.error("Only PostgreSQL backups are supported")
                return None
                
        except Exception as e:
            logger.error(f"Backup failed: {str(e)}")
            return None
    
    def restore_backup(self, backup_file: Path) -> bool:
        """
        Restore database from a backup file
        Returns True if successful, False otherwise
        """
        try:
            if not backup_file.exists():
                logger.error(f"Backup file not found: {backup_file}")
                return False
            
            # Parse database URL
            db_url = settings.DATABASE_URL
            if db_url.startswith("postgresql://"):
                db_params = self._parse_postgres_url(db_url)
                
                # Create psql command
                cmd = [
                    "psql",
                    "-h", db_params["host"],
                    "-p", db_params["port"],
                    "-U", db_params["user"],
                    "-d", db_params["database"],
                    "-w"  # no password prompt
                ]
                
                # Set PGPASSWORD environment variable
                env = os.environ.copy()
                env["PGPASSWORD"] = db_params["password"]
                
                # Decompress and restore
                with gzip.open(backup_file, 'rb') as gz:
                    process = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env
                    )
                    _, stderr = process.communicate(gz.read())
                    
                    if process.returncode != 0:
                        logger.error(f"Restore failed: {stderr.decode()}")
                        return False
                
                logger.info("Database restored successfully")
                return True
            else:
                logger.error("Only PostgreSQL restores are supported")
                return False
                
        except Exception as e:
            logger.error(f"Restore failed: {str(e)}")
            return False
    
    def cleanup_old_backups(self, keep_days: int = 7) -> None:
        """
        Remove backup files older than specified days
        """
        try:
            cutoff_date = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)
            
            for backup_file in self.backup_dir.glob("*.sql.gz"):
                if backup_file.stat().st_mtime < cutoff_date:
                    backup_file.unlink()
                    logger.info(f"Removed old backup: {backup_file}")
                    
        except Exception as e:
            logger.error(f"Backup cleanup failed: {str(e)}")
    
    def _parse_postgres_url(self, url: str) -> dict:
        """Parse PostgreSQL URL into components"""
        # Remove postgresql:// prefix
        url = url.replace("postgresql://", "")
        
        # Split credentials and host info
        if "@" in url:
            credentials, host_info = url.split("@")
        else:
            credentials, host_info = "", url
            
        # Get username and password
        if ":" in credentials:
            user, password = credentials.split(":")
        else:
            user, password = credentials, ""
            
        # Get host, port, and database
        if "/" in host_info:
            host_port, database = host_info.split("/")
        else:
            host_port, database = host_info, ""
            
        # Get host and port
        if ":" in host_port:
            host, port = host_port.split(":")
        else:
            host, port = host_port, "5432"
            
        return {
            "user": user,
            "password": password,
            "host": host,
            "port": port,
            "database": database
        } 