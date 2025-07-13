"""
Task scheduler for automated database maintenance
"""

import logging
import schedule
import time
import threading
from datetime import datetime
from typing import Callable
from .backup import BackupManager
from .cleanup import cleanup_stale_data, cleanup_invalid_financials, vacuum_database
from ..config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class MaintenanceScheduler:
    def __init__(self):
        self.backup_manager = BackupManager(settings.BACKUP_DIR)
        self.stop_flag = threading.Event()
    
    def start(self):
        """Start the scheduler"""
        # Schedule daily backup at 2 AM
        if settings.ENABLE_AUTO_BACKUP:
            schedule.every().day.at("02:00").do(self._run_backup)
            logger.info("Scheduled daily backups at 2 AM")
        
        # Schedule weekly cleanup on Sunday at 3 AM
        if settings.ENABLE_AUTO_CLEANUP:
            schedule.every().sunday.at("03:00").do(self._run_cleanup)
            logger.info("Scheduled weekly cleanup on Sunday at 3 AM")
        
        # Start the scheduler in a separate thread
        thread = threading.Thread(target=self._run_scheduler)
        thread.daemon = True
        thread.start()
        logger.info("Maintenance scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.stop_flag.set()
        logger.info("Maintenance scheduler stopped")
    
    def _run_scheduler(self):
        """Run the scheduler loop"""
        while not self.stop_flag.is_set():
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def _run_backup(self):
        """Run database backup"""
        try:
            logger.info("Starting scheduled backup")
            backup_file = self.backup_manager.create_backup()
            if backup_file:
                logger.info(f"Scheduled backup completed: {backup_file}")
                # Cleanup old backups
                self.backup_manager.cleanup_old_backups(settings.BACKUP_RETENTION_DAYS)
            else:
                logger.error("Scheduled backup failed")
        except Exception as e:
            logger.error(f"Error during scheduled backup: {str(e)}")
    
    def _run_cleanup(self):
        """Run database cleanup"""
        try:
            logger.info("Starting scheduled cleanup")
            
            # Clean up stale data
            cleanup_stale_data(settings.STALE_DATA_THRESHOLD_DAYS)
            
            # Clean up invalid financial data
            cleaned_ids = cleanup_invalid_financials()
            if cleaned_ids:
                logger.info(f"Cleaned up invalid financial data for {len(cleaned_ids)} properties")
            
            # Vacuum database
            vacuum_database()
            
            logger.info("Scheduled cleanup completed")
        except Exception as e:
            logger.error(f"Error during scheduled cleanup: {str(e)}")

# Global scheduler instance
scheduler = MaintenanceScheduler()

def start_scheduler():
    """Start the maintenance scheduler"""
    scheduler.start()

def stop_scheduler():
    """Stop the maintenance scheduler"""
    scheduler.stop() 