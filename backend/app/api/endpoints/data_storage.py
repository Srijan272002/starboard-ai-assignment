"""
Data Storage Endpoints - API endpoints for Phase 3.4 Data Storage
"""

from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query, File, UploadFile
from pydantic import BaseModel, Field
from datetime import datetime
import structlog
import os
import json

from app.core.logging import get_logger
from app.db.versioning import DataVersioningService
from app.db.backup import BackupService
from app.db.archival import ArchivalService
from app.db.data_update import DataUpdateSystem
from app.db.models import (
    Property, PropertyVersion, PropertyBackup, PropertyArchive, 
    DataUpdateLog, BackupJob, PropertyVersionInfo, BackupInfo
)
from app.db.base import SessionLocal

logger = get_logger(__name__)
router = APIRouter()


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# API Models
class VersionCreateRequest(BaseModel):
    """Request to create a new version"""
    property_id: int
    change_type: str
    change_reason: str
    created_by: str = "api"


class BackupCreateRequest(BaseModel):
    """Request to create a backup"""
    property_id: int
    backup_type: str = "daily"


class ArchiveCreateRequest(BaseModel):
    """Request to archive a property"""
    property_id: int
    archive_reason: str
    compress: bool = True


class RestoreRequest(BaseModel):
    """Request to restore from backup or archive"""
    id: int


class DataUpdateRequest(BaseModel):
    """Request to update property data"""
    property_id: str
    data: Dict[str, Any]
    source: str
    update_type: str = "update"
    change_reason: str = "API data update"
    create_if_missing: bool = True


class BulkUpdateRequest(BaseModel):
    """Request for bulk update"""
    properties_data: List[Dict[str, Any]]
    source: str
    update_type: str = "bulk_update"
    batch_size: int = 100


class FileImportRequest(BaseModel):
    """Request to import from file"""
    source: str
    file_format: str = "json"
    update_type: str = "file_import"
    id_field: str = "property_id"
    batch_size: int = 100


class APIResponse(BaseModel):
    """Standard API response"""
    success: bool
    message: str
    data: Optional[Any] = None


# Version endpoints
@router.post("/versions", response_model=APIResponse)
async def create_version(
    request: VersionCreateRequest,
    db: SessionLocal = Depends(get_db)
):
    """Create a new version of a property"""
    try:
        # Get property
        property_obj = db.query(Property).filter(Property.id == request.property_id).first()
        if not property_obj:
            raise HTTPException(status_code=404, detail=f"Property with ID {request.property_id} not found")
        
        # Create property data dictionary
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
        
        # Create version
        versioning_service = DataVersioningService(db)
        version = await versioning_service.create_version(
            property_id=request.property_id,
            data=property_data,
            change_type=request.change_type,
            change_reason=request.change_reason,
            created_by=request.created_by
        )
        
        return APIResponse(
            success=True,
            message=f"Created version {version.version_number} for property {request.property_id}",
            data={"version_id": version.id, "version_number": version.version_number}
        )
        
    except Exception as e:
        logger.error("Failed to create version", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/{property_id}", response_model=APIResponse)
async def get_version_history(
    property_id: int,
    limit: int = Query(10, ge=1, le=100),
    db: SessionLocal = Depends(get_db)
):
    """Get version history for a property"""
    try:
        # Check if property exists
        property_obj = db.query(Property).filter(Property.id == property_id).first()
        if not property_obj:
            raise HTTPException(status_code=404, detail=f"Property with ID {property_id} not found")
        
        # Get version history
        versioning_service = DataVersioningService(db)
        versions = versioning_service.get_version_history(property_id, limit)
        
        # Convert to response format
        version_history = []
        for version in versions:
            version_history.append({
                "version_number": version.version_number,
                "created_at": version.created_at,
                "created_by": version.created_by,
                "change_type": version.change_type,
                "change_reason": version.change_reason,
                "changes": version.changes
            })
        
        return APIResponse(
            success=True,
            message=f"Retrieved {len(version_history)} versions for property {property_id}",
            data={"versions": version_history}
        )
        
    except Exception as e:
        logger.error("Failed to get version history", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/versions/{property_id}/revert/{version_number}", response_model=APIResponse)
async def revert_to_version(
    property_id: int,
    version_number: int,
    change_reason: str = Query(..., min_length=3),
    created_by: str = Query("api"),
    db: SessionLocal = Depends(get_db)
):
    """Revert a property to a previous version"""
    try:
        # Check if property exists
        property_obj = db.query(Property).filter(Property.id == property_id).first()
        if not property_obj:
            raise HTTPException(status_code=404, detail=f"Property with ID {property_id} not found")
        
        # Revert to version
        versioning_service = DataVersioningService(db)
        success, new_version = versioning_service.revert_to_version(
            property_id=property_id,
            version_number=version_number,
            change_reason=change_reason,
            created_by=created_by
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=f"Failed to revert to version {version_number}")
        
        return APIResponse(
            success=True,
            message=f"Reverted property {property_id} to version {version_number}",
            data={
                "new_version_number": new_version.version_number,
                "created_at": new_version.created_at
            }
        )
        
    except Exception as e:
        logger.error("Failed to revert to version", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Backup endpoints
@router.post("/backups", response_model=APIResponse)
async def create_backup(
    request: BackupCreateRequest,
    db: SessionLocal = Depends(get_db)
):
    """Create a backup of a property"""
    try:
        # Check if property exists
        property_obj = db.query(Property).filter(Property.id == request.property_id).first()
        if not property_obj:
            raise HTTPException(status_code=404, detail=f"Property with ID {request.property_id} not found")
        
        # Create backup
        backup_service = BackupService(db)
        backup = await backup_service.create_property_backup(
            property_id=request.property_id,
            backup_type=request.backup_type
        )
        
        if not backup:
            raise HTTPException(status_code=500, detail="Failed to create backup")
        
        return APIResponse(
            success=True,
            message=f"Created {request.backup_type} backup for property {request.property_id}",
            data={
                "backup_id": backup.id,
                "backup_type": backup.backup_type,
                "expires_at": backup.expires_at,
                "storage_path": backup.storage_path
            }
        )
        
    except Exception as e:
        logger.error("Failed to create backup", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backups/full", response_model=APIResponse)
async def create_full_backup(
    backup_type: str = Query("full"),
    include_archives: bool = Query(False),
    db: SessionLocal = Depends(get_db)
):
    """Create a full database backup"""
    try:
        # Create backup
        backup_service = BackupService(db)
        job = await backup_service.create_full_backup(
            backup_type=backup_type,
            include_archives=include_archives
        )
        
        if not job:
            raise HTTPException(status_code=500, detail="Failed to create full backup")
        
        return APIResponse(
            success=True,
            message=f"Created full backup job (ID: {job.id})",
            data={
                "job_id": job.id,
                "backup_type": job.backup_type,
                "status": job.status,
                "file_name": job.file_name,
                "target_path": job.target_path
            }
        )
        
    except Exception as e:
        logger.error("Failed to create full backup", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backups/restore/{backup_id}", response_model=APIResponse)
async def restore_from_backup(
    backup_id: int,
    db: SessionLocal = Depends(get_db)
):
    """Restore a property from backup"""
    try:
        # Restore from backup
        backup_service = BackupService(db)
        success = await backup_service.restore_property_from_backup(backup_id)
        
        if not success:
            raise HTTPException(status_code=400, detail=f"Failed to restore from backup {backup_id}")
        
        return APIResponse(
            success=True,
            message=f"Restored property from backup {backup_id}",
            data={"backup_id": backup_id}
        )
        
    except Exception as e:
        logger.error("Failed to restore from backup", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backups/cleanup", response_model=APIResponse)
async def cleanup_expired_backups(
    db: SessionLocal = Depends(get_db)
):
    """Clean up expired backups"""
    try:
        # Clean up expired backups
        backup_service = BackupService(db)
        count = await backup_service.cleanup_expired_backups()
        
        return APIResponse(
            success=True,
            message=f"Cleaned up {count} expired backups",
            data={"count": count}
        )
        
    except Exception as e:
        logger.error("Failed to clean up expired backups", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Archive endpoints
@router.post("/archives", response_model=APIResponse)
async def archive_property(
    request: ArchiveCreateRequest,
    db: SessionLocal = Depends(get_db)
):
    """Archive a property"""
    try:
        # Check if property exists
        property_obj = db.query(Property).filter(Property.id == request.property_id).first()
        if not property_obj:
            raise HTTPException(status_code=404, detail=f"Property with ID {request.property_id} not found")
        
        # Archive property
        archival_service = ArchivalService(db)
        archive = await archival_service.archive_property(
            property_id=request.property_id,
            archive_reason=request.archive_reason,
            compress=request.compress
        )
        
        if not archive:
            raise HTTPException(status_code=500, detail="Failed to archive property")
        
        return APIResponse(
            success=True,
            message=f"Archived property {request.property_id}",
            data={
                "archive_id": archive.id,
                "archive_reason": archive.archive_reason,
                "archived_at": archive.archived_at,
                "retention_period_days": archive.retention_period_days
            }
        )
        
    except Exception as e:
        logger.error("Failed to archive property", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/archives/restore/{archive_id}", response_model=APIResponse)
async def restore_from_archive(
    archive_id: int,
    db: SessionLocal = Depends(get_db)
):
    """Restore a property from archive"""
    try:
        # Restore from archive
        archival_service = ArchivalService(db)
        property_obj = await archival_service.restore_from_archive(archive_id)
        
        if not property_obj:
            raise HTTPException(status_code=400, detail=f"Failed to restore from archive {archive_id}")
        
        return APIResponse(
            success=True,
            message=f"Restored property {property_obj.id} from archive {archive_id}",
            data={"property_id": property_obj.id, "archive_id": archive_id}
        )
        
    except Exception as e:
        logger.error("Failed to restore from archive", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/archives/cleanup", response_model=APIResponse)
async def cleanup_expired_archives(
    db: SessionLocal = Depends(get_db)
):
    """Clean up expired archives"""
    try:
        # Clean up expired archives
        archival_service = ArchivalService(db)
        count = await archival_service.cleanup_expired_archives()
        
        return APIResponse(
            success=True,
            message=f"Cleaned up {count} expired archives",
            data={"count": count}
        )
        
    except Exception as e:
        logger.error("Failed to clean up expired archives", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/archives/inactive", response_model=APIResponse)
async def archive_inactive_properties(
    days_inactive: int = Query(365, ge=30),
    batch_size: int = Query(100, ge=1, le=1000),
    db: SessionLocal = Depends(get_db)
):
    """Archive inactive properties"""
    try:
        # Archive inactive properties
        archival_service = ArchivalService(db)
        count = await archival_service.archive_inactive_properties(
            days_inactive=days_inactive,
            batch_size=batch_size
        )
        
        return APIResponse(
            success=True,
            message=f"Archived {count} inactive properties",
            data={"count": count, "days_inactive": days_inactive}
        )
        
    except Exception as e:
        logger.error("Failed to archive inactive properties", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Data update endpoints
@router.post("/update", response_model=APIResponse)
async def update_property_data(
    request: DataUpdateRequest,
    db: SessionLocal = Depends(get_db)
):
    """Update a property with new data"""
    try:
        # Update property
        data_update_system = DataUpdateSystem(db)
        property_obj, was_created = await data_update_system.update_property(
            property_id=request.property_id,
            data=request.data,
            source=request.source,
            update_type=request.update_type,
            change_reason=request.change_reason,
            create_if_missing=request.create_if_missing
        )
        
        action = "Created" if was_created else "Updated"
        return APIResponse(
            success=True,
            message=f"{action} property {request.property_id}",
            data={
                "property_id": property_obj.id,
                "was_created": was_created,
                "processing_status": property_obj.processing_status
            }
        )
        
    except Exception as e:
        logger.error("Failed to update property", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update/bulk", response_model=APIResponse)
async def bulk_update_properties(
    request: BulkUpdateRequest,
    background_tasks: BackgroundTasks,
    db: SessionLocal = Depends(get_db)
):
    """Bulk update multiple properties"""
    try:
        # Start update job
        data_update_system = DataUpdateSystem(db)
        update_log = await data_update_system.start_update_job(
            update_type=request.update_type,
            source=request.source
        )
        
        # Run bulk update in background
        background_tasks.add_task(
            data_update_system.bulk_update_properties,
            properties_data=request.properties_data,
            source=request.source,
            update_type=request.update_type,
            batch_size=request.batch_size
        )
        
        return APIResponse(
            success=True,
            message=f"Started bulk update job for {len(request.properties_data)} properties",
            data={
                "job_id": update_log.id,
                "update_type": update_log.update_type,
                "source": update_log.source,
                "properties_count": len(request.properties_data)
            }
        )
        
    except Exception as e:
        logger.error("Failed to start bulk update", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update/file", response_model=APIResponse)
async def import_from_file(
    file: UploadFile = File(...),
    source: str = Query(...),
    file_format: str = Query("json"),
    update_type: str = Query("file_import"),
    id_field: str = Query("property_id"),
    batch_size: int = Query(100),
    background_tasks: BackgroundTasks = None,
    db: SessionLocal = Depends(get_db)
):
    """Import properties from a file"""
    try:
        # Save uploaded file
        temp_file_path = f"temp_{file.filename}"
        with open(temp_file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Start data update system
        data_update_system = DataUpdateSystem(db)
        
        # Start update job
        update_log = await data_update_system.start_update_job(
            update_type=update_type,
            source=f"{source}_file_import"
        )
        
        # Run import in background
        background_tasks.add_task(
            data_update_system.import_from_file,
            file_path=temp_file_path,
            source=source,
            file_format=file_format,
            update_type=update_type,
            id_field=id_field,
            batch_size=batch_size
        )
        
        return APIResponse(
            success=True,
            message=f"Started file import job from {file.filename}",
            data={
                "job_id": update_log.id,
                "file_name": file.filename,
                "source": source,
                "file_format": file_format
            }
        )
        
    except Exception as e:
        logger.error("Failed to import from file", error=str(e))
        # Clean up temp file if it exists
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/update/history", response_model=APIResponse)
async def get_update_history(
    source: Optional[str] = None,
    update_type: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
    db: SessionLocal = Depends(get_db)
):
    """Get update history"""
    try:
        # Get update history
        data_update_system = DataUpdateSystem(db)
        logs = await data_update_system.get_update_history(
            source=source,
            update_type=update_type,
            limit=limit
        )
        
        # Convert to response format
        history = []
        for log in logs:
            history.append({
                "id": log.id,
                "update_type": log.update_type,
                "source": log.source,
                "status": log.status,
                "records_processed": log.records_processed,
                "records_updated": log.records_updated,
                "records_failed": log.records_failed,
                "start_time": log.start_time,
                "end_time": log.end_time,
                "duration_seconds": log.duration_seconds
            })
        
        return APIResponse(
            success=True,
            message=f"Retrieved {len(history)} update history records",
            data={"history": history}
        )
        
    except Exception as e:
        logger.error("Failed to get update history", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) 