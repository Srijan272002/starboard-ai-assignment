from typing import List, Dict, Optional
from datetime import datetime
from .validation import (
    ValidatedProperty,
    ValidationResult,
    PropertyType,
    ZoningType
)
from .logger import setup_logger
from .data_analysis import DataAnalysis

logger = setup_logger("filters")

class PropertyFilter:
    def __init__(self):
        self.logger = logger
        self.data_analysis = DataAnalysis()

    def filter_industrial_properties(
        self,
        properties: List[ValidatedProperty],
        min_size: Optional[float] = 10000,
        min_ceiling_height: Optional[float] = 14,
        max_age: Optional[int] = None,
        required_features: Optional[List[str]] = None
    ) -> List[ValidatedProperty]:
        """
        Filters properties based on industrial criteria
        """
        filtered = []
        current_year = datetime.now().year

        for prop in properties:
            try:
                if self._meets_industrial_criteria(
                    prop,
                    min_size,
                    min_ceiling_height,
                    max_age,
                    required_features,
                    current_year
                ):
                    filtered.append(prop)
            except Exception as e:
                self.logger.error(f"Error filtering property {prop.id}: {str(e)}")

        return filtered

    def _meets_industrial_criteria(
        self,
        prop: ValidatedProperty,
        min_size: Optional[float],
        min_ceiling_height: Optional[float],
        max_age: Optional[int],
        required_features: Optional[List[str]],
        current_year: int
    ) -> bool:
        """
        Checks if a property meets industrial criteria
        """
        # Check property type
        if prop.property_type not in [
            PropertyType.INDUSTRIAL,
            PropertyType.WAREHOUSE,
            PropertyType.MANUFACTURING,
            PropertyType.FLEX
        ]:
            return False

        # Check zoning
        if prop.zoning_type not in [
            ZoningType.M1,
            ZoningType.M2,
            ZoningType.I1,
            ZoningType.I2
        ]:
            return False

        # Check size
        if min_size and prop.metrics.total_square_feet < min_size:
            return False

        # Check ceiling height
        if (min_ceiling_height and prop.metrics.ceiling_height and 
            prop.metrics.ceiling_height < min_ceiling_height):
            return False

        # Check age
        if max_age and prop.metrics.year_built:
            age = current_year - prop.metrics.year_built
            if age > max_age:
                return False

        # Check required features
        if required_features:
            for feature in required_features:
                if not self._has_feature(prop, feature):
                    return False

        return True

    def _has_feature(self, prop: ValidatedProperty, feature: str) -> bool:
        """
        Checks if a property has a specific feature
        """
        feature = feature.lower()
        
        if feature == 'loading_docks':
            return bool(prop.metrics.loading_docks)
        elif feature == 'drive_in_doors':
            return bool(prop.metrics.drive_in_doors)
        elif feature == 'high_ceiling':
            return bool(prop.metrics.ceiling_height and prop.metrics.ceiling_height >= 14)
        elif feature == 'office_space':
            return bool(prop.metrics.office_square_feet)
        elif feature == 'manufacturing_space':
            return bool(prop.metrics.manufacturing_square_feet)
        elif feature == 'warehouse_space':
            return bool(prop.metrics.warehouse_square_feet)
        
        return False

    def filter_by_location(
        self,
        properties: List[ValidatedProperty],
        latitude: float,
        longitude: float,
        radius_km: float
    ) -> List[ValidatedProperty]:
        """
        Filters properties within a radius of a point
        """
        filtered = []
        
        for prop in properties:
            try:
                distance = self.data_analysis.calculate_distance(
                    latitude,
                    longitude,
                    prop.latitude,
                    prop.longitude
                )
                if distance <= radius_km:
                    filtered.append(prop)
            except Exception as e:
                self.logger.error(f"Error calculating distance for property {prop.id}: {str(e)}")
                
        return filtered

    def filter_by_financials(
        self,
        properties: List[ValidatedProperty],
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_price_per_sqft: Optional[float] = None,
        max_price_per_sqft: Optional[float] = None,
        min_cap_rate: Optional[float] = None,
        min_occupancy: Optional[float] = None
    ) -> List[ValidatedProperty]:
        """
        Filters properties based on financial criteria
        """
        filtered = []
        
        for prop in properties:
            try:
                if self._meets_financial_criteria(
                    prop,
                    min_price,
                    max_price,
                    min_price_per_sqft,
                    max_price_per_sqft,
                    min_cap_rate,
                    min_occupancy
                ):
                    filtered.append(prop)
            except Exception as e:
                self.logger.error(f"Error filtering financials for property {prop.id}: {str(e)}")
                
        return filtered

    def _meets_financial_criteria(
        self,
        prop: ValidatedProperty,
        min_price: Optional[float],
        max_price: Optional[float],
        min_price_per_sqft: Optional[float],
        max_price_per_sqft: Optional[float],
        min_cap_rate: Optional[float],
        min_occupancy: Optional[float]
    ) -> bool:
        """
        Checks if a property meets financial criteria
        """
        fin = prop.financials
        
        if min_price and (not fin.current_value or fin.current_value < min_price):
            return False
            
        if max_price and (not fin.current_value or fin.current_value > max_price):
            return False
            
        if min_price_per_sqft and (not fin.price_per_square_foot or 
                                  fin.price_per_square_foot < min_price_per_sqft):
            return False
            
        if max_price_per_sqft and (not fin.price_per_square_foot or 
                                  fin.price_per_square_foot > max_price_per_sqft):
            return False
            
        if min_cap_rate and (not fin.cap_rate or fin.cap_rate < min_cap_rate):
            return False
            
        if min_occupancy and (not fin.occupancy_rate or fin.occupancy_rate < min_occupancy):
            return False
            
        return True

# Global filter instance
property_filter = PropertyFilter() 