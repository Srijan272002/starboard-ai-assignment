"""
Data Update System - Manages data updates, synchronization, and incremental loading
"""

import json
import csv
import os
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Set, Callable
from datetime import datetime, timedelta
import structlog
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from app.db.models import Property, DataUpdateLog
from app.core.config import settings
from app.core.exceptions import StarboardException
from app.db.versioning import DataVersioningService

logger = structlog.get_logger(__name__)


class DataUpdateSystem:
    """System for managing data updates, synchronization, and incremental loading"""
    
    def __init__(self, db: Session):
        self.db = db
        self.versioning_service = DataVersioningService(db)
    
    async def start_update_job(
        self,
        update_type: str,
        source: str
    ) -> DataUpdateLog:
        """
        Start a new data update job
        
        Args:
            update_type: Type of update (full, incremental, correction)
            source: Data source identifier
            
        Returns:
            DataUpdateLog object
        """
        try:
            # Create update log
            update_log = DataUpdateLog(
                update_type=update_type,
                source=source,
                status="pending",
                records_processed=0,
                records_updated=0,
                records_failed=0,
                start_time=datetime.utcnow()
            )
            
            self.db.add(update_log)
            self.db.commit()
            
            logger.info("Started data update job", 
                       job_id=update_log.id,
                       update_type=update_type,
                       source=source)
            
            return update_log
            
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to start update job", 
                        update_type=update_type,
                        source=source,
                        error=str(e))
            raise
    
    async def complete_update_job(
        self,
        job_id: int,
        status: str,
        records_processed: int,
        records_updated: int,
        records_failed: int,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> DataUpdateLog:
        """
        Complete a data update job
        
        Args:
            job_id: ID of the update job
            status: Final status (completed, failed)
            records_processed: Number of records processed
            records_updated: Number of records updated
            records_failed: Number of records that failed
            error_message: Error message if failed
            error_details: Detailed error information
            
        Returns:
            Updated DataUpdateLog object
        """
        try:
            # Get update log
            update_log = self.db.query(DataUpdateLog).filter(DataUpdateLog.id == job_id).first()
            if not update_log:
                raise StarboardException(f"Update job with ID {job_id} not found")
            
            # Update log
            update_log.status = status
            update_log.records_processed = records_processed
            update_log.records_updated = records_updated
            update_log.records_failed = records_failed
            update_log.end_time = datetime.utcnow()
            
            if update_log.start_time:
                update_log.duration_seconds = int((update_log.end_time - update_log.start_time).total_seconds())
            
            if error_message:
                update_log.error_message = error_message
            
            if error_details:
                update_log.error_details = error_details
            
            self.db.commit()
            
            logger.info("Completed data update job", 
                       job_id=job_id,
                       status=status,
                       records_processed=records_processed,
                       records_updated=records_updated,
                       records_failed=records_failed)
            
            return update_log
            
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to complete update job", 
                        job_id=job_id,
                        error=str(e))
            raise
    
    async def update_property(
        self,
        property_id: str,
        data: Dict[str, Any],
        source: str,
        update_type: str = "update",
        change_reason: str = "API data update",
        create_if_missing: bool = True
    ) -> Tuple[Property, bool]:
        """
        Update a property with new data
        
        Args:
            property_id: External property ID
            data: New property data
            source: Data source
            update_type: Type of update
            change_reason: Reason for the change
            create_if_missing: Whether to create the property if it doesn't exist
            
        Returns:
            Tuple of (property, was_created)
        """
        try:
            # Check if property exists
            property_obj = self.db.query(Property).filter(Property.property_id == property_id).first()
            was_created = False
            
            if not property_obj and create_if_missing:
                # Create new property
                property_obj = Property(
                    property_id=property_id,
                    source_api=source,
                    processing_status="new"
                )
                self.db.add(property_obj)
                self.db.flush()  # Get ID without committing
                was_created = True
                
                logger.info("Created new property", 
                           property_id=property_id,
                           source=source)
            elif not property_obj:
                raise StarboardException(f"Property with ID {property_id} not found")
            
            # Update property fields
            for key, value in data.items():
                if hasattr(property_obj, key) and key not in ['id', 'property_id', 'created_at', 'updated_at']:
                    setattr(property_obj, key, value)
            
            # Update status
            if was_created:
                property_obj.processing_status = "processed"
            else:
                property_obj.processing_status = "updated"
            
            # Create version
            property_data = {
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
                "source_api": property_obj.source_api
            }
            
            await self.versioning_service.create_version(
                property_id=property_obj.id,
                data=property_data,
                change_type=update_type,
                change_reason=change_reason,
                created_by=f"system:{source}"
            )
            
            self.db.commit()
            
            return property_obj, was_created
            
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to update property", 
                        property_id=property_id,
                        error=str(e))
            raise
    
    async def bulk_update_properties(
        self,
        properties_data: List[Dict[str, Any]],
        source: str,
        update_type: str = "bulk_update",
        batch_size: int = 100
    ) -> Tuple[int, int, int]:
        """
        Bulk update multiple properties
        
        Args:
            properties_data: List of property data dictionaries
            source: Data source
            update_type: Type of update
            batch_size: Number of properties to process in each batch
            
        Returns:
            Tuple of (processed_count, updated_count, failed_count)
        """
        try:
            # Start update job
            update_log = await self.start_update_job(update_type, source)
            
            processed_count = 0
            updated_count = 0
            failed_count = 0
            errors = []
            
            # Process in batches
            for i in range(0, len(properties_data), batch_size):
                batch = properties_data[i:i+batch_size]
                
                for property_data in batch:
                    try:
                        if "property_id" not in property_data:
                            logger.warning("Property data missing property_id", data=property_data)
                            failed_count += 1
                            continue
                        
                        property_id = property_data["property_id"]
                        change_reason = f"Bulk update from {source}"
                        
                        _, was_created = await self.update_property(
                            property_id=property_id,
                            data=property_data,
                            source=source,
                            update_type=update_type,
                            change_reason=change_reason,
                            create_if_missing=True
                        )
                        
                        processed_count += 1
                        updated_count += 1
                        
                    except Exception as e:
                        logger.error("Failed to update property in bulk operation", 
                                    property_id=property_data.get("property_id", "unknown"),
                                    error=str(e))
                        failed_count += 1
                        errors.append({
                            "property_id": property_data.get("property_id", "unknown"),
                            "error": str(e)
                        })
                
                # Log progress
                logger.info("Bulk update progress", 
                           job_id=update_log.id,
                           processed=processed_count,
                           updated=updated_count,
                           failed=failed_count,
                           total=len(properties_data))
            
            # Complete update job
            status = "completed" if failed_count == 0 else "completed_with_errors"
            await self.complete_update_job(
                job_id=update_log.id,
                status=status,
                records_processed=processed_count,
                records_updated=updated_count,
                records_failed=failed_count,
                error_details={"errors": errors} if errors else None
            )
            
            return processed_count, updated_count, failed_count
            
        except Exception as e:
            logger.error("Failed to perform bulk update", 
                        source=source,
                        error=str(e))
            
            # Try to update job status if it was created
            try:
                if 'update_log' in locals() and update_log.id:
                    await self.complete_update_job(
                        job_id=update_log.id,
                        status="failed",
                        records_processed=processed_count if 'processed_count' in locals() else 0,
                        records_updated=updated_count if 'updated_count' in locals() else 0,
                        records_failed=failed_count if 'failed_count' in locals() else 0,
                        error_message=str(e)
                    )
            except:
                pass
                
            raise
    
    async def import_from_file(
        self,
        file_path: str,
        source: str,
        file_format: str = "json",
        update_type: str = "file_import",
        id_field: str = "property_id",
        batch_size: int = 100
    ) -> Tuple[int, int, int]:
        """
        Import properties from a file
        
        Args:
            file_path: Path to the file
            source: Data source identifier
            file_format: Format of the file (json, csv)
            update_type: Type of update
            id_field: Field to use as property_id
            batch_size: Number of properties to process in each batch
            
        Returns:
            Tuple of (processed_count, updated_count, failed_count)
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                raise StarboardException(f"File not found: {file_path}")
            
            # Load data from file
            data = []
            
            if file_format.lower() == "json":
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Handle both array and object formats
                    if isinstance(data, dict):
                        data = [data]
                        
            elif file_format.lower() == "csv":
                with open(file_path, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.DictReader(f)
                    data = list(reader)
            else:
                raise StarboardException(f"Unsupported file format: {file_format}")
            
            # Ensure id_field is mapped to property_id
            for item in data:
                if id_field in item and id_field != "property_id":
                    item["property_id"] = item[id_field]
            
            # Perform bulk update
            return await self.bulk_update_properties(
                properties_data=data,
                source=f"{source}_file_import",
                update_type=update_type,
                batch_size=batch_size
            )
            
        except Exception as e:
            logger.error("Failed to import from file", 
                        file_path=file_path,
                        source=source,
                        error=str(e))
            raise
    
    async def incremental_update(
        self,
        source: str,
        data_provider: Callable[..., List[Dict[str, Any]]],
        last_update_minutes: int = 1440,  # 24 hours
        batch_size: int = 100,
        **provider_kwargs
    ) -> Tuple[int, int, int]:
        """
        Perform an incremental update using a data provider function
        
        Args:
            source: Data source identifier
            data_provider: Function that returns data to update
            last_update_minutes: Minutes to look back for changes
            batch_size: Number of properties to process in each batch
            provider_kwargs: Additional arguments for the data provider
            
        Returns:
            Tuple of (processed_count, updated_count, failed_count)
        """
        try:
            # Calculate last update time
            last_update_time = datetime.utcnow() - timedelta(minutes=last_update_minutes)
            
            # Add to provider kwargs
            provider_kwargs["last_update_time"] = last_update_time
            
            # Get data from provider
            data = await data_provider(**provider_kwargs)
            
            if not data:
                logger.info("No data to update", 
                           source=source,
                           last_update_minutes=last_update_minutes)
                return 0, 0, 0
            
            # Perform bulk update
            return await self.bulk_update_properties(
                properties_data=data,
                source=source,
                update_type="incremental",
                batch_size=batch_size
            )
            
        except Exception as e:
            logger.error("Failed to perform incremental update", 
                        source=source,
                        error=str(e))
            raise
    
    async def get_update_history(
        self,
        source: Optional[str] = None,
        update_type: Optional[str] = None,
        limit: int = 10
    ) -> List[DataUpdateLog]:
        """
        Get update history
        
        Args:
            source: Filter by source
            update_type: Filter by update type
            limit: Maximum number of records to return
            
        Returns:
            List of DataUpdateLog objects
        """
        try:
            query = self.db.query(DataUpdateLog)
            
            if source:
                query = query.filter(DataUpdateLog.source == source)
                
            if update_type:
                query = query.filter(DataUpdateLog.update_type == update_type)
                
            logs = query.order_by(DataUpdateLog.created_at.desc()).limit(limit).all()
            
            return logs
            
        except Exception as e:
            logger.error("Failed to get update history", error=str(e))
            return [] 