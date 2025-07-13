from typing import Dict, List
from pydantic import BaseModel
from math import radians, sin, cos, sqrt, atan2
from backend.utils.validation import ValidatedProperty

class ComparableProperty(BaseModel):
    property: ValidatedProperty
    similarity_score: float
    confidence_score: float
    matching_factors: Dict[str, float]

    model_config = {"arbitrary_types_allowed": True}

class ComparableDiscoveryAgent:
    def __init__(self):
        self.weight_factors = {
            "location": 0.3,
            "size": 0.25,
            "age": 0.2,
            "type": 0.15,
            "price": 0.1
        }
    
    async def find_comparables(
        self, 
        target_property: ValidatedProperty, 
        all_properties: List[ValidatedProperty],
        limit: int = 5
    ) -> List[ComparableProperty]:
        """
        Finds comparable properties based on similarity
        
        Args:
            target_property: The property to find comparables for
            all_properties: List of all available properties
            limit: Maximum number of comparables to return
            
        Returns:
            List of comparable properties sorted by similarity score
        """
        comparables = []
        
        for property in all_properties:
            if property.id == target_property.id:
                continue
                
            comparable = self.calculate_similarity(target_property, property)
            comparable.confidence_score = self.calculate_confidence(comparable)
            comparables.append(comparable)
        
        # Sort by similarity score and return top matches
        comparables.sort(key=lambda x: x.similarity_score, reverse=True)
        return comparables[:limit]
    
    def calculate_similarity(
        self, 
        target: ValidatedProperty, 
        candidate: ValidatedProperty
    ) -> ComparableProperty:
        """
        Calculates similarity between properties using multiple factors
        """
        matching_factors = {}
        
        # Calculate location similarity using Haversine formula
        location_score = self._calculate_location_similarity(
            target.latitude, target.longitude,
            candidate.latitude, candidate.longitude
        )
        matching_factors["location"] = location_score
        
        # Calculate size similarity
        size_score = self._calculate_size_similarity(
            target.metrics.total_square_feet,
            candidate.metrics.total_square_feet
        )
        matching_factors["size"] = size_score
        
        # Calculate age similarity if both properties have year_built
        if target.metrics.year_built and candidate.metrics.year_built:
            age_score = self._calculate_age_similarity(
                target.metrics.year_built,
                candidate.metrics.year_built
            )
            matching_factors["age"] = age_score
        else:
            matching_factors["age"] = 0.5  # Neutral score if we can't compare ages
        
        # Calculate property type similarity
        type_score = 1.0 if target.property_type == candidate.property_type else 0.0
        matching_factors["type"] = type_score
        
        # Calculate price similarity if both properties have current_value
        if target.financials.current_value and candidate.financials.current_value:
            price_score = self._calculate_price_similarity(
                target.financials.current_value,
                candidate.financials.current_value
            )
            matching_factors["price"] = price_score
        else:
            matching_factors["price"] = 0.5  # Neutral score if we can't compare prices
        
        # Calculate weighted similarity score
        similarity_score = sum(
            score * self.weight_factors[factor]
            for factor, score in matching_factors.items()
        )
        
        return ComparableProperty(
            property=candidate,
            similarity_score=similarity_score,
            confidence_score=0.0,  # Will be calculated separately
            matching_factors=matching_factors
        )
    
    def calculate_confidence(
        self, 
        comparable: ComparableProperty
    ) -> float:
        """
        Calculates confidence score based on data completeness and similarity thresholds
        """
        # Base confidence on data completeness
        completeness_factors = {
            "location": comparable.property.latitude != 0 and comparable.property.longitude != 0,
            "size": comparable.property.metrics.total_square_feet > 0,
            "age": comparable.property.metrics.year_built is not None,
            "type": comparable.property.property_type is not None,
            "price": comparable.property.financials.current_value is not None
        }
        
        # Calculate confidence based on completeness and similarity thresholds
        confidence_score = sum(
            self.weight_factors[factor] * float(completeness)
            for factor, completeness in completeness_factors.items()
        )
        
        # Adjust confidence based on similarity thresholds
        for factor, score in comparable.matching_factors.items():
            if score < 0.5:  # If any factor has very low similarity
                confidence_score *= 0.8  # Reduce confidence
        
        return confidence_score
    
    def _calculate_location_similarity(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculates location similarity using Haversine formula
        Returns a score between 0 and 1, where 1 means locations are identical
        """
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = 6371 * c  # Radius of Earth in km
        
        # Convert distance to similarity score
        # Assuming properties within 5km are highly similar
        return max(0, 1 - (distance / 5))
    
    def _calculate_size_similarity(
        self,
        size1: float,
        size2: float
    ) -> float:
        """
        Calculates size similarity
        Returns a score between 0 and 1
        """
        if size1 <= 0 or size2 <= 0:
            return 0
            
        # Calculate percentage difference
        size_diff = abs(size1 - size2) / max(size1, size2)
        return max(0, 1 - size_diff)
    
    def _calculate_age_similarity(
        self,
        year1: int,
        year2: int
    ) -> float:
        """
        Calculates age similarity
        Returns a score between 0 and 1
        """
        if not year1 or not year2:
            return 0
            
        # Calculate age difference
        age_diff = abs(year1 - year2)
        # Assuming properties within 10 years are similar
        return max(0, 1 - (age_diff / 10))
    
    def _calculate_type_similarity(
        self,
        type1: str,
        type2: str,
        zoning1: str,
        zoning2: str
    ) -> float:
        """
        Calculates property type similarity
        Returns a score between 0 and 1
        """
        # Equal weight for property type and zoning
        type_match = 1.0 if type1.lower() == type2.lower() else 0.0
        zoning_match = 1.0 if zoning1 == zoning2 else 0.0
        
        return (type_match + zoning_match) / 2
    
    def _calculate_price_similarity(
        self,
        price1: float,
        price2: float
    ) -> float:
        """
        Calculates price similarity
        Returns a score between 0 and 1
        """
        if not price1 or not price2:
            return 0
            
        # Calculate percentage difference
        price_diff = abs(price1 - price2) / max(price1, price2)
        return max(0, 1 - price_diff) 