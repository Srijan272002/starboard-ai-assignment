"""
Data update system utilities
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import and_
from .db import get_db_session
from .versioning import VersionManager
from ..models.property import Property
from ..models.financials import PropertyFinancials
from ..models.metrics import PropertyMetrics
from ..models.address import Address

logger = logging.getLogger(__name__)
version_manager = VersionManager()

class UpdateManager:
    def __init__(self):
        self.session = None
    
    def update_property(
        self,
        property_id: str,
        data: Dict[str, Any],
        user: Optional[str] = None
    ) -> Tuple[Property, bool]:
        """
        Update a property and related data
        Returns tuple of (updated_property, was_modified)
        """
        with get_db_session() as session:
            property = session.query(Property).get(property_id)
            if not property:
                raise ValueError(f"Property {property_id} not found")
            
            # Track if any changes were made
            modified = False
            changes = {}
            
            # Update main property attributes
            property_attrs = ['property_type', 'zoning_type', 'latitude', 'longitude']
            for attr in property_attrs:
                if attr in data and getattr(property, attr) != data[attr]:
                    changes[attr] = {
                        'old': getattr(property, attr),
                        'new': data[attr]
                    }
                    setattr(property, attr, data[attr])
                    modified = True
            
            # Update address if provided
            if 'address' in data:
                addr_changes = self._update_address(property.address, data['address'])
                if addr_changes:
                    changes['address'] = addr_changes
                    modified = True
            
            # Update metrics if provided
            if 'metrics' in data:
                metrics_changes = self._update_metrics(property.metrics, data['metrics'])
                if metrics_changes:
                    changes['metrics'] = metrics_changes
                    modified = True
            
            # Update financials if provided
            if 'financials' in data:
                financial_changes = self._update_financials(property.financials, data['financials'])
                if financial_changes:
                    changes['financials'] = financial_changes
                    modified = True
            
            # Create version if modified
            if modified:
                version_manager.create_version(
                    entity_type='property',
                    entity_id=property_id,
                    changes=changes,
                    user=user,
                    comment="Property update"
                )
                logger.info(f"Updated property {property_id}")
            
            return property, modified
    
    def _update_address(
        self,
        address: Address,
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update address and return changes if any"""
        changes = {}
        for attr in ['street', 'city', 'state', 'postal_code', 'country']:
            if attr in data and getattr(address, attr) != data[attr]:
                changes[attr] = {
                    'old': getattr(address, attr),
                    'new': data[attr]
                }
                setattr(address, attr, data[attr])
        return changes if changes else None
    
    def _update_metrics(
        self,
        metrics: PropertyMetrics,
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update metrics and return changes if any"""
        changes = {}
        for attr in ['square_footage', 'lot_size', 'year_built', 'bedrooms', 'bathrooms', 'parking_spaces']:
            if attr in data and getattr(metrics, attr) != data[attr]:
                changes[attr] = {
                    'old': getattr(metrics, attr),
                    'new': data[attr]
                }
                setattr(metrics, attr, data[attr])
        
        # Handle additional_features separately as it's JSON
        if 'additional_features' in data:
            old_features = metrics.additional_features or {}
            if old_features != data['additional_features']:
                changes['additional_features'] = {
                    'old': old_features,
                    'new': data['additional_features']
                }
                metrics.additional_features = data['additional_features']
        
        return changes if changes else None
    
    def _update_financials(
        self,
        financials: PropertyFinancials,
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update financials and return changes if any"""
        changes = {}
        for attr in ['list_price', 'sale_price', 'estimated_value', 'annual_tax', 'monthly_hoa', 'rental_estimate']:
            if attr in data and getattr(financials, attr) != data[attr]:
                changes[attr] = {
                    'old': getattr(financials, attr),
                    'new': data[attr]
                }
                setattr(financials, attr, data[attr])
        
        # Handle dates
        if 'last_sale_date' in data:
            old_date = financials.last_sale_date
            new_date = datetime.strptime(data['last_sale_date'], '%Y-%m-%d').date() if data['last_sale_date'] else None
            if old_date != new_date:
                changes['last_sale_date'] = {
                    'old': old_date.isoformat() if old_date else None,
                    'new': new_date.isoformat() if new_date else None
                }
                financials.last_sale_date = new_date
        
        # Handle additional_fees separately as it's JSON
        if 'additional_fees' in data:
            old_fees = financials.additional_fees or {}
            if old_fees != data['additional_fees']:
                changes['additional_fees'] = {
                    'old': old_fees,
                    'new': data['additional_fees']
                }
                financials.additional_fees = data['additional_fees']
        
        return changes if changes else None
    
    def bulk_update_properties(
        self,
        updates: List[Dict[str, Any]],
        user: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Bulk update multiple properties
        Returns dict of property_id: was_modified
        """
        results = {}
        for update in updates:
            property_id = update.pop('id')
            try:
                _, modified = self.update_property(property_id, update, user)
                results[property_id] = modified
            except Exception as e:
                logger.error(f"Failed to update property {property_id}: {str(e)}")
                results[property_id] = False
        return results 