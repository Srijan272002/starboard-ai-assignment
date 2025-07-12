"""
Backup Service - Manages database backups and restoration
"""

import os
import json
import gzip
import shutil
import tempfile
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import asyncio
import structlog
from sqlalchemy.orm import Session
import sqlalchemy as sa

from app.db.models import Property, PropertyBackup, BackupJob
from app.core.config import settings
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)


class BackupService:
    """Service for managing database backups and restoration"""
    
    def __init__(self, db: Session):
        self.db = db
        self.backup_dir = Path(settings.BACKUP_DIRECTORY)
        self._ensure_backup_directory()
    
    def _ensure_backup_directory(self):
        """Ensure the backup directory exists"""
        if not self.backup_dir.exists():
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Created backup directory", path=str(self.backup_dir))
    
    async def create_property_backup(
        self,
        property_id: int,
        backup_type: str = "daily"
    ) -> Optional[PropertyBackup]:
        """
        Create a backup of a property
        
        Args:
            property_id: ID of the property
            backup_type: Type of backup (daily, weekly, monthly)
            
        Returns:
            PropertyBackup object or None if failed
        """
        try:
            # Get property
            property_obj = self.db.query(Property).filter(Property.id == property_id).first()
            if not property_obj:
                logger.error("Property not found", property_id=property_id)
                return None
            
            # Determine expiration date based on backup type
            expires_at = datetime.utcnow()
            if backup_type == "daily":
                expires_at += timedelta(days=7)  # Keep daily backups for 1 week
            elif backup_type == "weekly":
                expires_at += timedelta(days=30)  # Keep weekly backups for 1 month
            elif backup_type == "monthly":
                expires_at += timedelta(days=365)  # Keep monthly backups for 1 year
            else:
                expires_at += timedelta(days=7)  # Default
            
            # Create property data dictionary
            property_data = {
                "id": property_obj.id,
                "property_id": property_obj.property_id,
                "county": property_obj.county,
                "address": property_obj.address,
                "city": property_obj.city,
                "state": property_obj.state,
                "zip_code": property_obj.zip_code,
                "property_type": property_obj.property_type,
                "zoning": property_obj.zoning,
                "square_footage": property_obj.square_footage,
                "lot_size": property_obj.lot_size,
                "year_built": property_obj.year_built,
                "latitude": property_obj.latitude,
                "longitude": property_obj.longitude,
                "assessed_value": property_obj.assessed_value,
                "market_value": property_obj.market_value,
                "tax_amount": property_obj.tax_amount,
                "features": property_obj.features,
                "data_quality_score": property_obj.data_quality_score,
                "confidence_score": property_obj.confidence_score,
                "processing_status": property_obj.processing_status,
                "raw_data": property_obj.raw_data,
                "source_api": property_obj.source_api,
                "created_at": property_obj.created_at.isoformat() if property_obj.created_at else None,
                "updated_at": property_obj.updated_at.isoformat() if property_obj.updated_at else None,
                "current_version_id": property_obj.current_version_id,
                "backup_date": datetime.utcnow().isoformat()
            }
            
            # Generate backup filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"property_{property_id}_{backup_type}_{timestamp}.json.gz"
            storage_path = str(self.backup_dir / filename)
            
            # Save compressed backup file
            with gzip.open(storage_path, 'wt', encoding='utf-8') as f:
                json.dump(property_data, f, indent=2)
            
            # Create backup record
            backup = PropertyBackup(
                property_id=property_id,
                backup_type=backup_type,
                data=property_data,
                storage_path=storage_path,
                expires_at=expires_at
            )
            
            self.db.add(backup)
            self.db.commit()
            
            logger.info("Created property backup", 
                       property_id=property_id,
                       backup_id=backup.id,
                       backup_type=backup_type,
                       storage_path=storage_path)
            
            return backup
            
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to create property backup", 
                        property_id=property_id,
                        error=str(e))
            return None
    
    async def create_full_backup(
        self,
        backup_type: str = "full",
        include_archives: bool = False
    ) -> Optional[BackupJob]:
        """
        Create a full database backup
        
        Args:
            backup_type: Type of backup (full, incremental, differential)
            include_archives: Whether to include archived data
            
        Returns:
            BackupJob object or None if failed
        """
        try:
            # Create backup job record
            job = BackupJob(
                backup_type=backup_type,
                status="in_progress",
                start_time=datetime.utcnow(),
                is_compressed=True
            )
            self.db.add(job)
            self.db.commit()
            
            # Generate backup filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"full_backup_{backup_type}_{timestamp}.sql.gz"
            target_path = str(self.backup_dir / filename)
            
            # Update job with file info
            job.file_name = filename
            job.target_path = target_path
            self.db.commit()
            
            # Execute backup
            success = await self._execute_database_backup(target_path)
            
            # Update job status
            end_time = datetime.utcnow()
            job.end_time = end_time
            job.duration_seconds = int((end_time - job.start_time).total_seconds())
            
            if success:
                job.status = "completed"
                job.file_size_bytes = os.path.getsize(target_path)
                logger.info("Full backup completed successfully", 
                           job_id=job.id,
                           target_path=target_path,
                           size_bytes=job.file_size_bytes)
            else:
                job.status = "failed"
                job.error_message = "Database backup command failed"
                logger.error("Full backup failed", job_id=job.id)
            
            self.db.commit()
            return job
            
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to create full backup", error=str(e))
            
            # Update job status if it was created
            try:
                if 'job' in locals() and job.id:
                    job.status = "failed"
                    job.error_message = str(e)
                    job.end_time = datetime.utcnow()
                    if job.start_time:
                        job.duration_seconds = int((job.end_time - job.start_time).total_seconds())
                    self.db.commit()
            except:
                pass
                
            return None
    
    async def restore_property_from_backup(
        self,
        backup_id: int
    ) -> bool:
        """
        Restore a property from backup
        
        Args:
            backup_id: ID of the backup to restore from
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get backup
            backup = self.db.query(PropertyBackup).filter(PropertyBackup.id == backup_id).first()
            if not backup:
                logger.error("Backup not found", backup_id=backup_id)
                return False
            
            # Get property
            property_id = backup.property_id
            property_obj = self.db.query(Property).filter(Property.id == property_id).first()
            
            if not property_obj:
                logger.error("Property not found", property_id=property_id)
                return False
            
            # Restore data from backup
            backup_data = backup.data
            
            # Update property fields from backup data
            for key, value in backup_data.items():
                if hasattr(property_obj, key) and key not in ['id', 'created_at', 'updated_at']:
                    setattr(property_obj, key, value)
            
            # Mark as restored from backup
            property_obj.processing_status = "restored_from_backup"
            
            self.db.commit()
            
            logger.info("Restored property from backup", 
                       property_id=property_id,
                       backup_id=backup_id)
            
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to restore property from backup", 
                        backup_id=backup_id,
                        error=str(e))
            return False
    
    async def restore_from_full_backup(
        self,
        backup_job_id: int
    ) -> bool:
        """
        Restore database from a full backup
        
        Args:
            backup_job_id: ID of the backup job to restore from
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get backup job
            job = self.db.query(BackupJob).filter(BackupJob.id == backup_job_id).first()
            if not job:
                logger.error("Backup job not found", job_id=backup_job_id)
                return False
            
            # Check if backup file exists
            backup_file = job.target_path
            if not os.path.exists(backup_file):
                logger.error("Backup file not found", path=backup_file)
                return False
            
            # Execute restore
            success = await self._execute_database_restore(backup_file)
            
            if success:
                logger.info("Database restored successfully from backup", 
                           job_id=backup_job_id,
                           file=backup_file)
            else:
                logger.error("Failed to restore database from backup", 
                            job_id=backup_job_id)
            
            return success
            
        except Exception as e:
            logger.error("Failed to restore from full backup", 
                        job_id=backup_job_id,
                        error=str(e))
            return False
    
    async def cleanup_expired_backups(self) -> int:
        """
        Remove expired backups
        
        Returns:
            Number of backups removed
        """
        try:
            # Find expired backups
            now = datetime.utcnow()
            expired_backups = self.db.query(PropertyBackup)\
                .filter(PropertyBackup.expires_at < now)\
                .all()
            
            count = 0
            for backup in expired_backups:
                # Delete backup file if it exists
                if backup.storage_path and os.path.exists(backup.storage_path):
                    os.remove(backup.storage_path)
                
                # Delete from database
                self.db.delete(backup)
                count += 1
            
            self.db.commit()
            
            logger.info("Cleaned up expired backups", count=count)
            return count
            
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to clean up expired backups", error=str(e))
            return 0
    
    async def _execute_database_backup(self, target_path: str) -> bool:
        """Execute database backup using appropriate method based on database type"""
        try:
            # Determine database type from connection URL
            db_url = settings.DATABASE_URL.lower()
            
            if 'sqlite' in db_url:
                return await self._backup_sqlite(target_path)
            elif 'postgresql' in db_url or 'postgres' in db_url:
                return await self._backup_postgres(target_path)
            else:
                logger.error("Unsupported database type for backup")
                return False
        except Exception as e:
            logger.error("Database backup execution failed", error=str(e))
            return False
    
    async def _execute_database_restore(self, source_path: str) -> bool:
        """Execute database restore using appropriate method based on database type"""
        try:
            # Determine database type from connection URL
            db_url = settings.DATABASE_URL.lower()
            
            if 'sqlite' in db_url:
                return await self._restore_sqlite(source_path)
            elif 'postgresql' in db_url or 'postgres' in db_url:
                return await self._restore_postgres(source_path)
            else:
                logger.error("Unsupported database type for restore")
                return False
        except Exception as e:
            logger.error("Database restore execution failed", error=str(e))
            return False
    
    async def _backup_sqlite(self, target_path: str) -> bool:
        """Backup SQLite database"""
        try:
            # Extract database file path from connection URL
            db_url = settings.DATABASE_URL
            db_path = db_url.replace('sqlite:///', '')
            
            if not os.path.exists(db_path):
                logger.error("SQLite database file not found", path=db_path)
                return False
            
            # Create a copy of the database file
            with open(db_path, 'rb') as src, gzip.open(target_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            
            return True
        except Exception as e:
            logger.error("SQLite backup failed", error=str(e))
            return False
    
    async def _backup_postgres(self, target_path: str) -> bool:
        """Backup PostgreSQL database using pg_dump"""
        try:
            # Extract connection details
            db_url = settings.DATABASE_URL
            db_name = settings.POSTGRES_DB
            db_user = settings.POSTGRES_USER
            db_password = settings.POSTGRES_PASSWORD
            db_host = settings.POSTGRES_SERVER
            
            # Create pg_dump command
            cmd = [
                'pg_dump',
                '-h', db_host,
                '-U', db_user,
                '-d', db_name,
                '-F', 'c',  # Custom format
                '-Z', '9',  # Maximum compression
                '-f', target_path
            ]
            
            # Set password environment variable
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password
            
            # Execute pg_dump
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error("pg_dump failed", 
                            returncode=process.returncode,
                            stderr=stderr.decode())
                return False
            
            return True
        except Exception as e:
            logger.error("PostgreSQL backup failed", error=str(e))
            return False
    
    async def _restore_sqlite(self, source_path: str) -> bool:
        """Restore SQLite database"""
        try:
            # Extract database file path from connection URL
            db_url = settings.DATABASE_URL
            db_path = db_url.replace('sqlite:///', '')
            
            # Close database connection
            self.db.close()
            
            # Create backup of current database
            backup_path = f"{db_path}.bak.{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            shutil.copy2(db_path, backup_path)
            
            # Restore from backup
            with gzip.open(source_path, 'rb') as src, open(db_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            
            return True
        except Exception as e:
            logger.error("SQLite restore failed", error=str(e))
            return False
    
    async def _restore_postgres(self, source_path: str) -> bool:
        """Restore PostgreSQL database using pg_restore"""
        try:
            # Extract connection details
            db_url = settings.DATABASE_URL
            db_name = settings.POSTGRES_DB
            db_user = settings.POSTGRES_USER
            db_password = settings.POSTGRES_PASSWORD
            db_host = settings.POSTGRES_SERVER
            
            # Close database connection
            self.db.close()
            
            # Create pg_restore command
            cmd = [
                'pg_restore',
                '-h', db_host,
                '-U', db_user,
                '-d', db_name,
                '-c',  # Clean (drop) database objects before recreating
                source_path
            ]
            
            # Set password environment variable
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password
            
            # Execute pg_restore
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error("pg_restore failed", 
                            returncode=process.returncode,
                            stderr=stderr.decode())
                return False
            
            return True
        except Exception as e:
            logger.error("PostgreSQL restore failed", error=str(e))
            return False 