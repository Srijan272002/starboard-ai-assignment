"""
Property Matcher - Implements comprehensive property comparison and matching
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import math
from sqlalchemy.orm import Session
from sqlalchemy import func
import structlog

from app.db.models import Property, PropertyComparable
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)

class PropertyMatcher:
    """Service for matching and comparing properties"""
    
    def __init__(self, db: Session):
        self.db = db
        self.analysis_version = "1.0.0"
    
    def _calculate_size_similarity(self, prop1: Property, prop2: Property) -> float:
        """Calculate similarity score based on property size"""
        if not prop1.square_footage or not prop2.square_footage:
            return 0.0
            
        # Calculate difference percentage
        larger = max(prop1.square_footage, prop2.square_footage)
        smaller = min(prop1.square_footage, prop2.square_footage)
        diff_percent = (larger - smaller) / larger
        
        # Convert to similarity score (0-1)
        similarity = 1 - min(diff_percent, 1.0)
        
        # Apply lot size comparison if available
        if prop1.lot_size and prop2.lot_size:
            larger_lot = max(prop1.lot_size, prop2.lot_size)
            smaller_lot = min(prop1.lot_size, prop2.lot_size)
            lot_diff_percent = (larger_lot - smaller_lot) / larger_lot
            lot_similarity = 1 - min(lot_diff_percent, 1.0)
            
            # Combine scores (60% building size, 40% lot size)
            similarity = (similarity * 0.6) + (lot_similarity * 0.4)
        
        return similarity
    
    def _calculate_location_similarity(self, prop1: Property, prop2: Property) -> Tuple[float, float]:
        """Calculate similarity score based on location and distance"""
        if not all([prop1.latitude, prop1.longitude, prop2.latitude, prop2.longitude]):
            return 0.0, 0.0
            
        # Calculate distance using Haversine formula
        R = 3959.87433  # Earth's radius in miles
        
        lat1, lon1 = math.radians(prop1.latitude), math.radians(prop1.longitude)
        lat2, lon2 = math.radians(prop2.latitude), math.radians(prop2.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        distance = R * c
        
        # Convert distance to similarity score
        # Properties within 1 mile = 1.0
        # Properties over 50 miles = 0.0
        # Linear scale between
        if distance <= 1:
            similarity = 1.0
        elif distance >= 50:
            similarity = 0.0
        else:
            similarity = 1 - ((distance - 1) / 49)
            
        # Additional market area analysis
        market_similarity = 1.0
        if prop1.zip_code != prop2.zip_code:
            market_similarity *= 0.9
        if prop1.city != prop2.city:
            market_similarity *= 0.8
        if prop1.county != prop2.county:
            market_similarity *= 0.7
            
        # Combine distance and market scores
        location_similarity = (similarity * 0.7) + (market_similarity * 0.3)
        
        return location_similarity, distance
    
    def _calculate_age_similarity(self, prop1: Property, prop2: Property) -> float:
        """Calculate similarity score based on property age and condition"""
        if not prop1.year_built or not prop2.year_built:
            return 0.0
            
        # Calculate age difference
        age_diff = abs(prop1.year_built - prop2.year_built)
        
        # Convert to similarity score
        # Same year = 1.0
        # 50+ years difference = 0.0
        # Linear scale between
        if age_diff == 0:
            similarity = 1.0
        elif age_diff >= 50:
            similarity = 0.0
        else:
            similarity = 1 - (age_diff / 50)
            
        return similarity
    
    def _calculate_type_similarity(self, prop1: Property, prop2: Property) -> float:
        """Calculate similarity score based on property type and features"""
        base_similarity = 0.0
        
        # Compare property types
        if prop1.property_type == prop2.property_type:
            base_similarity = 1.0
        elif not prop1.property_type or not prop2.property_type:
            base_similarity = 0.0
        else:
            # Partial matches based on property type hierarchy
            industrial_types = {
                'warehouse': 0.8,
                'manufacturing': 0.7,
                'distribution': 0.8,
                'flex': 0.6,
                'r&d': 0.5,
                'industrial': 0.9
            }
            
            type1 = prop1.property_type.lower()
            type2 = prop2.property_type.lower()
            
            if type1 in industrial_types and type2 in industrial_types:
                base_similarity = 0.5  # Base similarity for industrial properties
            
        # Compare zoning if available
        zoning_similarity = 1.0
        if prop1.zoning and prop2.zoning:
            if prop1.zoning != prop2.zoning:
                zoning_similarity = 0.7
                
        return base_similarity * zoning_similarity
    
    def _calculate_features_similarity(self, prop1: Property, prop2: Property) -> float:
        """Calculate similarity score based on property features"""
        if not prop1.features or not prop2.features:
            return 0.0
            
        features1 = prop1.features
        features2 = prop2.features
        
        # Define feature weights
        feature_weights = {
            'loading_docks': 0.2,
            'ceiling_height': 0.2,
            'crane_capacity': 0.15,
            'power_capacity': 0.15,
            'parking_ratio': 0.1,
            'office_percentage': 0.1,
            'construction_type': 0.1
        }
        
        total_weight = 0
        weighted_similarity = 0
        
        for feature, weight in feature_weights.items():
            if feature in features1 and feature in features2:
                # Calculate feature-specific similarity
                if isinstance(features1[feature], (int, float)) and isinstance(features2[feature], (int, float)):
                    # Numeric comparison
                    larger = max(features1[feature], features2[feature])
                    smaller = min(features1[feature], features2[feature])
                    if larger == 0:
                        similarity = 1.0
                    else:
                        diff_percent = (larger - smaller) / larger
                        similarity = 1 - min(diff_percent, 1.0)
                else:
                    # String comparison
                    similarity = 1.0 if features1[feature] == features2[feature] else 0.0
                
                weighted_similarity += similarity * weight
                total_weight += weight
        
        if total_weight == 0:
            return 0.0
            
        return weighted_similarity / total_weight
    
    async def find_comparables(
        self,
        property_id: int,
        min_similarity: float = 0.5,
        max_distance: float = 50.0,
        limit: int = 10
    ) -> List[PropertyComparable]:
        """
        Find comparable properties for a given property
        
        Args:
            property_id: ID of the reference property
            min_similarity: Minimum overall similarity score (0-1)
            max_distance: Maximum distance in miles
            limit: Maximum number of comparables to return
            
        Returns:
            List of PropertyComparable objects
        """
        try:
            # Get reference property
            reference_property = self.db.query(Property).filter(Property.id == property_id).first()
            if not reference_property:
                raise StarboardException(f"Property with ID {property_id} not found")
            
            # Get potential comparables (basic filtering)
            potential_comparables = self.db.query(Property).filter(
                Property.id != property_id,
                Property.county == reference_property.county,  # Start with same county
                Property.is_latest == True,  # Only consider latest versions
                Property.processing_status != 'archived'  # Exclude archived properties
            ).all()
            
            comparables = []
            
            for comp_property in potential_comparables:
                # Calculate similarity scores
                size_similarity = self._calculate_size_similarity(reference_property, comp_property)
                location_similarity, distance = self._calculate_location_similarity(reference_property, comp_property)
                age_similarity = self._calculate_age_similarity(reference_property, comp_property)
                type_similarity = self._calculate_type_similarity(reference_property, comp_property)
                features_similarity = self._calculate_features_similarity(reference_property, comp_property)
                
                # Skip if too far
                if distance > max_distance:
                    continue
                
                # Calculate overall similarity
                # Weights: Size (25%), Location (25%), Type (20%), Age (15%), Features (15%)
                overall_similarity = (
                    size_similarity * 0.25 +
                    location_similarity * 0.25 +
                    type_similarity * 0.20 +
                    age_similarity * 0.15 +
                    features_similarity * 0.15
                )
                
                # Skip if below minimum similarity
                if overall_similarity < min_similarity:
                    continue
                
                # Calculate confidence score based on data completeness
                confidence_factors = [
                    1.0 if comp_property.square_footage else 0.0,
                    1.0 if comp_property.lot_size else 0.0,
                    1.0 if comp_property.year_built else 0.0,
                    1.0 if comp_property.latitude and comp_property.longitude else 0.0,
                    1.0 if comp_property.features else 0.0
                ]
                confidence_score = sum(confidence_factors) / len(confidence_factors)
                
                # Create comparable record
                comparable = PropertyComparable(
                    property_id=property_id,
                    comparable_property_id=comp_property.id,
                    overall_similarity_score=overall_similarity,
                    size_similarity=size_similarity,
                    location_similarity=location_similarity,
                    type_similarity=type_similarity,
                    age_similarity=age_similarity,
                    features_similarity=features_similarity,
                    distance_miles=distance,
                    confidence_score=confidence_score,
                    analysis_version=self.analysis_version
                )
                
                comparables.append(comparable)
            
            # Sort by overall similarity and limit results
            comparables.sort(key=lambda x: x.overall_similarity_score, reverse=True)
            comparables = comparables[:limit]
            
            # Save to database
            for comp in comparables:
                self.db.add(comp)
            self.db.commit()
            
            logger.info("Found comparable properties",
                       property_id=property_id,
                       count=len(comparables),
                       min_similarity=min_similarity,
                       max_distance=max_distance)
            
            return comparables
            
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to find comparables",
                        property_id=property_id,
                        error=str(e))
            raise 