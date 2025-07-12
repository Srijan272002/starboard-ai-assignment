"""
Data Versioning Service - Manages property data versioning and change tracking
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
import structlog

from app.db.models import Property, PropertyVersion
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)


class DataVersioningService:
    """Service for managing data versioning and change tracking"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_version(
        self,
        property_id: int,
        data: Dict[str, Any],
        change_type: str,
        change_reason: str,
        created_by: str = "system"
    ) -> PropertyVersion:
        """
        Create a new version of a property
        
        Args:
            property_id: ID of the property
            data: Current property data
            change_type: Type of change (update, correction, etc.)
            change_reason: Reason for the change
            created_by: User or system that created this version
            
        Returns:
            New PropertyVersion object
        """
        try:
            # Get property
            property_obj = self.db.query(Property).filter(Property.id == property_id).first()
            if not property_obj:
                raise StarboardException(f"Property with ID {property_id} not found")
                
            # Get latest version number
            latest_version = self.db.query(PropertyVersion)\
                .filter(PropertyVersion.property_id == property_id)\
                .order_by(PropertyVersion.version_number.desc())\
                .first()
                
            new_version_number = 1
            changes = {}
            
            if latest_version:
                new_version_number = latest_version.version_number + 1
                # Calculate changes from previous version
                changes = self._calculate_changes(latest_version.data, data)
            
            # Create new version
            new_version = PropertyVersion(
                property_id=property_id,
                version_number=new_version_number,
                data=data,
                changes=changes,
                change_type=change_type,
                change_reason=change_reason,
                created_by=created_by
            )
            
            # Update property's current version
            property_obj.current_version_id = new_version_number
            
            # Add to database
            self.db.add(new_version)
            self.db.commit()
            
            logger.info("Created new property version", 
                       property_id=property_id,
                       version=new_version_number,
                       change_type=change_type)
            
            return new_version
            
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to create property version", 
                        property_id=property_id,
                        error=str(e))
            raise
    
    def get_version(
        self,
        property_id: int,
        version_number: Optional[int] = None
    ) -> Optional[PropertyVersion]:
        """
        Get a specific version of a property
        
        Args:
            property_id: ID of the property
            version_number: Version number to retrieve (None for latest)
            
        Returns:
            PropertyVersion object or None if not found
        """
        try:
            query = self.db.query(PropertyVersion)\
                .filter(PropertyVersion.property_id == property_id)
                
            if version_number:
                return query.filter(PropertyVersion.version_number == version_number).first()
            else:
                return query.order_by(PropertyVersion.version_number.desc()).first()
                
        except Exception as e:
            logger.error("Failed to get property version", 
                        property_id=property_id,
                        version=version_number,
                        error=str(e))
            return None
    
    def get_version_history(
        self,
        property_id: int,
        limit: int = 10
    ) -> List[PropertyVersion]:
        """
        Get version history for a property
        
        Args:
            property_id: ID of the property
            limit: Maximum number of versions to return
            
        Returns:
            List of PropertyVersion objects
        """
        try:
            versions = self.db.query(PropertyVersion)\
                .filter(PropertyVersion.property_id == property_id)\
                .order_by(PropertyVersion.version_number.desc())\
                .limit(limit)\
                .all()
                
            return versions
            
        except Exception as e:
            logger.error("Failed to get property version history", 
                        property_id=property_id,
                        error=str(e))
            return []
    
    def revert_to_version(
        self,
        property_id: int,
        version_number: int,
        change_reason: str,
        created_by: str = "system"
    ) -> Tuple[bool, Optional[PropertyVersion]]:
        """
        Revert a property to a previous version
        
        Args:
            property_id: ID of the property
            version_number: Version to revert to
            change_reason: Reason for reverting
            created_by: User or system that initiated the revert
            
        Returns:
            Tuple of (success, new_version)
        """
        try:
            # Get target version
            target_version = self.get_version(property_id, version_number)
            if not target_version:
                logger.error("Target version not found", 
                            property_id=property_id,
                            version=version_number)
                return False, None
                
            # Create new version with data from target version
            new_version = self.create_version(
                property_id=property_id,
                data=target_version.data,
                change_type="revert",
                change_reason=f"{change_reason} (Reverted to v{version_number})",
                created_by=created_by
            )
            
            # Update property data
            property_obj = self.db.query(Property).filter(Property.id == property_id).first()
            if property_obj:
                # Update property fields from version data
                for key, value in target_version.data.items():
                    if hasattr(property_obj, key):
                        setattr(property_obj, key, value)
                
                self.db.commit()
                
            logger.info("Reverted property to previous version", 
                       property_id=property_id,
                       target_version=version_number,
                       new_version=new_version.version_number)
                
            return True, new_version
            
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to revert property version", 
                        property_id=property_id,
                        version=version_number,
                        error=str(e))
            return False, None
    
    def _calculate_changes(
        self,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate changes between two versions of data"""
        changes = {}
        
        # Find changed fields
        for key, new_value in new_data.items():
            if key in old_data:
                old_value = old_data[key]
                if old_value != new_value:
                    changes[key] = {
                        "old": old_value,
                        "new": new_value
                    }
            else:
                # New field added
                changes[key] = {
                    "old": None,
                    "new": new_value
                }
        
        # Find removed fields
        for key in old_data:
            if key not in new_data:
                changes[key] = {
                    "old": old_data[key],
                    "new": None
                }
                
        return changes 