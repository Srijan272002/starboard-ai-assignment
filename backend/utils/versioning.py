"""
Data versioning utilities
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import Table, Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from ..models.base import Base, TimestampMixin
from .db import get_db_session

logger = logging.getLogger(__name__)

class DataVersion(Base, TimestampMixin):
    """Model for tracking data versions"""
    __tablename__ = 'data_versions'

    id = Column(Integer, primary_key=True)
    entity_type = Column(String, nullable=False)  # e.g., 'property', 'financials'
    entity_id = Column(String, nullable=False)
    version = Column(Integer, nullable=False)
    changes = Column(JSON, nullable=False)  # Store the changes made in this version
    user = Column(String, nullable=True)  # User who made the change
    comment = Column(String, nullable=True)  # Optional comment about the change

    def __repr__(self):
        return f"<DataVersion(entity={self.entity_type}:{self.entity_id}, version={self.version})>"

class VersionManager:
    def __init__(self):
        self.session = None
    
    def create_version(
        self,
        entity_type: str,
        entity_id: str,
        changes: Dict[str, Any],
        user: Optional[str] = None,
        comment: Optional[str] = None
    ) -> DataVersion:
        """
        Create a new version for an entity
        """
        with get_db_session() as session:
            # Get the latest version number
            latest_version = session.query(DataVersion).filter(
                DataVersion.entity_type == entity_type,
                DataVersion.entity_id == entity_id
            ).order_by(DataVersion.version.desc()).first()
            
            new_version_num = (latest_version.version + 1) if latest_version else 1
            
            # Create new version
            version = DataVersion(
                entity_type=entity_type,
                entity_id=entity_id,
                version=new_version_num,
                changes=changes,
                user=user,
                comment=comment
            )
            
            session.add(version)
            logger.info(f"Created version {new_version_num} for {entity_type}:{entity_id}")
            
            return version
    
    def get_version_history(
        self,
        entity_type: str,
        entity_id: str,
        limit: Optional[int] = None
    ) -> List[DataVersion]:
        """
        Get version history for an entity
        """
        with get_db_session() as session:
            query = session.query(DataVersion).filter(
                DataVersion.entity_type == entity_type,
                DataVersion.entity_id == entity_id
            ).order_by(DataVersion.version.desc())
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
    
    def get_version(
        self,
        entity_type: str,
        entity_id: str,
        version: int
    ) -> Optional[DataVersion]:
        """
        Get a specific version of an entity
        """
        with get_db_session() as session:
            return session.query(DataVersion).filter(
                DataVersion.entity_type == entity_type,
                DataVersion.entity_id == entity_id,
                DataVersion.version == version
            ).first()
    
    def compare_versions(
        self,
        entity_type: str,
        entity_id: str,
        version1: int,
        version2: int
    ) -> Dict[str, Any]:
        """
        Compare two versions of an entity
        Returns a dict of differences
        """
        v1 = self.get_version(entity_type, entity_id, version1)
        v2 = self.get_version(entity_type, entity_id, version2)
        
        if not v1 or not v2:
            raise ValueError("One or both versions not found")
        
        # Compare changes
        diffs = {
            'added': {},
            'removed': {},
            'modified': {}
        }
        
        all_keys = set(v1.changes.keys()) | set(v2.changes.keys())
        
        for key in all_keys:
            if key not in v1.changes:
                diffs['added'][key] = v2.changes[key]
            elif key not in v2.changes:
                diffs['removed'][key] = v1.changes[key]
            elif v1.changes[key] != v2.changes[key]:
                diffs['modified'][key] = {
                    'from': v1.changes[key],
                    'to': v2.changes[key]
                }
        
        return diffs
    
    def revert_to_version(
        self,
        entity_type: str,
        entity_id: str,
        version: int,
        user: Optional[str] = None,
        comment: str = "Reverted to previous version"
    ) -> DataVersion:
        """
        Revert to a specific version
        Creates a new version with the reverted data
        """
        target_version = self.get_version(entity_type, entity_id, version)
        if not target_version:
            raise ValueError(f"Version {version} not found")
        
        return self.create_version(
            entity_type=entity_type,
            entity_id=entity_id,
            changes=target_version.changes,
            user=user,
            comment=comment
        ) 