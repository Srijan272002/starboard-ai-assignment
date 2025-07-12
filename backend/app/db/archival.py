"""
Data Archival Service - Manages archiving and retrieval of historical property data
"""

import json
import gzip
import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import structlog
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import Property, PropertyArchive
from app.core.config import settings
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)


class ArchivalService:
    """Service for managing data archiving and retrieval"""
    
    def __init__(self, db: Session):
        self.db = db
        self.archive_dir = Path(settings.ARCHIVE_DIRECTORY)
        self._ensure_archive_directory()
    
    def _ensure_archive_directory(self):
        """Ensure the archive directory exists"""
        if not self.archive_dir.exists():
            self.archive_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Created archive directory", path=str(self.archive_dir))
    
    async def archive_property(
        self,
        property_id: int,
        archive_reason: str,
        compress: bool = True
    ) -> Optional[PropertyArchive]:
        """
        Archive a property
        
        Args:
            property_id: ID of the property to archive
            archive_reason: Reason for archiving
            compress: Whether to compress the archived data
            
        Returns:
            PropertyArchive object or None if failed
        """
        try:
            # Get property
            property_obj = self.db.query(Property).filter(Property.id == property_id).first()
            if not property_obj:
                logger.error("Property not found", property_id=property_id)
                return None
            
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
                "archive_date": datetime.utcnow().isoformat()
            }
            
            # Generate archive filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"property_{property_id}_archive_{timestamp}.json"
            if compress:
                filename += ".gz"
            
            storage_path = str(self.archive_dir / filename)
            
            # Save archive file
            if compress:
                with gzip.open(storage_path, 'wt', encoding='utf-8') as f:
                    json.dump(property_data, f, indent=2)
            else:
                with open(storage_path, 'w', encoding='utf-8') as f:
                    json.dump(property_data, f, indent=2)
            
            # Create archive record
            archive = PropertyArchive(
                property_id=property_id,
                archive_reason=archive_reason,
                data=property_data,
                is_compressed=compress,
                retention_period_days=settings.ARCHIVE_RETENTION_DAYS
            )
            
            self.db.add(archive)
            
            # Update property status
            property_obj.processing_status = "archived"
            
            self.db.commit()
            
            logger.info("Archived property", 
                       property_id=property_id,
                       archive_id=archive.id,
                       archive_reason=archive_reason)
            
            return archive
            
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to archive property", 
                        property_id=property_id,
                        error=str(e))
            return None
    
    async def restore_from_archive(
        self,
        archive_id: int
    ) -> Optional[Property]:
        """
        Restore a property from archive
        
        Args:
            archive_id: ID of the archive to restore from
            
        Returns:
            Restored Property object or None if failed
        """
        try:
            # Get archive
            archive = self.db.query(PropertyArchive).filter(PropertyArchive.id == archive_id).first()
            if not archive:
                logger.error("Archive not found", archive_id=archive_id)
                return None
            
            # Get property
            property_id = archive.property_id
            property_obj = self.db.query(Property).filter(Property.id == property_id).first()
            
            # Restore data from archive
            archive_data = archive.data
            
            if property_obj:
                # Update existing property
                for key, value in archive_data.items():
                    if hasattr(property_obj, key) and key not in ['id', 'created_at', 'updated_at']:
                        setattr(property_obj, key, value)
                
                # Mark as restored from archive
                property_obj.processing_status = "restored_from_archive"
                
                logger.info("Restored property from archive (updated existing)", 
                           property_id=property_id,
                           archive_id=archive_id)
            else:
                # Create new property
                property_obj = Property()
                
                for key, value in archive_data.items():
                    if hasattr(property_obj, key) and key not in ['created_at', 'updated_at']:
                        setattr(property_obj, key, value)
                
                # Mark as restored from archive
                property_obj.processing_status = "restored_from_archive"
                
                self.db.add(property_obj)
                
                logger.info("Restored property from archive (created new)", 
                           property_id=property_id,
                           archive_id=archive_id)
            
            self.db.commit()
            return property_obj
            
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to restore from archive", 
                        archive_id=archive_id,
                        error=str(e))
            return None
    
    async def get_archives_for_property(
        self,
        property_id: int,
        limit: int = 10
    ) -> List[PropertyArchive]:
        """
        Get archives for a property
        
        Args:
            property_id: ID of the property
            limit: Maximum number of archives to return
            
        Returns:
            List of PropertyArchive objects
        """
        try:
            archives = self.db.query(PropertyArchive)\
                .filter(PropertyArchive.property_id == property_id)\
                .order_by(PropertyArchive.archived_at.desc())\
                .limit(limit)\
                .all()
                
            return archives
            
        except Exception as e:
            logger.error("Failed to get property archives", 
                        property_id=property_id,
                        error=str(e))
            return []
    
    async def cleanup_expired_archives(self) -> int:
        """
        Remove expired archives
        
        Returns:
            Number of archives removed
        """
        try:
            # Find expired archives
            now = datetime.utcnow()
            expired_archives = self.db.query(PropertyArchive)\
                .filter(func.date_add(PropertyArchive.archived_at, 
                                     func.interval(PropertyArchive.retention_period_days, 'day')) < now)\
                .all()
            
            count = 0
            for archive in expired_archives:
                # Delete archive file if it exists
                if archive.data and 'storage_path' in archive.data:
                    storage_path = archive.data['storage_path']
                    if os.path.exists(storage_path):
                        os.remove(storage_path)
                
                # Delete from database
                self.db.delete(archive)
                count += 1
            
            self.db.commit()
            
            logger.info("Cleaned up expired archives", count=count)
            return count
            
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to clean up expired archives", error=str(e))
            return 0
    
    async def archive_inactive_properties(
        self,
        days_inactive: int = 365,
        batch_size: int = 100
    ) -> int:
        """
        Archive properties that haven't been updated for a specific period
        
        Args:
            days_inactive: Number of days since last update
            batch_size: Number of properties to process in each batch
            
        Returns:
            Number of properties archived
        """
        try:
            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)
            
            # Find inactive properties
            inactive_properties = self.db.query(Property)\
                .filter(Property.updated_at < cutoff_date)\
                .filter(Property.processing_status != "archived")\
                .limit(batch_size)\
                .all()
            
            count = 0
            for property_obj in inactive_properties:
                # Archive property
                archive_reason = f"Inactive for {days_inactive} days"
                await self.archive_property(property_obj.id, archive_reason)
                count += 1
            
            logger.info("Archived inactive properties", 
                       count=count,
                       days_inactive=days_inactive)
            
            return count
            
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to archive inactive properties", 
                        days_inactive=days_inactive,
                        error=str(e))
            return 0 