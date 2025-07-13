from typing import List, Dict, Optional
from statistics import mean, median, stdev
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime
from backend.agents.data_extraction import Property

class DataAnalysis:
    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two points using Haversine formula
        """
        R = 6371  # Earth's radius in kilometers

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c

        return distance

    @staticmethod
    def calculate_statistics(values: List[float]) -> Dict[str, float]:
        """
        Calculate basic statistics for a list of values
        """
        if not values:
            return {
                "mean": 0,
                "median": 0,
                "std_dev": 0,
                "min": 0,
                "max": 0
            }

        return {
            "mean": mean(values),
            "median": median(values),
            "std_dev": stdev(values) if len(values) > 1 else 0,
            "min": min(values),
            "max": max(values)
        }

    @staticmethod
    def detect_outliers(values: List[float], threshold: float = 2.0) -> List[int]:
        """
        Detect outliers using Z-score method
        """
        if len(values) < 2:
            return []

        avg = mean(values)
        std = stdev(values)
        
        return [i for i, x in enumerate(values) if abs((x - avg) / std) > threshold]

    @staticmethod
    def calculate_property_age(property: Property) -> Optional[float]:
        """
        Calculate property age in years
        """
        if not property.year_built:
            return None
            
        current_year = datetime.now().year
        return current_year - property.year_built

    @staticmethod
    def normalize_value(
        value: float,
        min_val: float,
        max_val: float,
        scale: float = 1.0
    ) -> float:
        """
        Normalize a value to a 0-1 scale
        """
        if max_val == min_val:
            return 0.5 * scale
        return ((value - min_val) / (max_val - min_val)) * scale

    @classmethod
    def calculate_similarity_score(
        cls,
        target: Property,
        comparable: Property,
        weights: Dict[str, float]
    ) -> float:
        """
        Calculate weighted similarity score between two properties
        """
        scores = []
        
        # Location similarity (inverse of distance)
        distance = cls.calculate_distance(
            target.latitude, target.longitude,
            comparable.latitude, comparable.longitude
        )
        location_score = 1 / (1 + distance)  # Normalize to 0-1
        scores.append(location_score * weights.get("location", 0.3))
        
        # Size similarity
        size_diff = abs(target.square_feet - comparable.square_feet)
        size_score = 1 / (1 + size_diff/1000)  # Normalize to 0-1
        scores.append(size_score * weights.get("size", 0.25))
        
        # Age similarity
        target_age = cls.calculate_property_age(target)
        comp_age = cls.calculate_property_age(comparable)
        if target_age and comp_age:
            age_diff = abs(target_age - comp_age)
            age_score = 1 / (1 + age_diff/5)  # Normalize to 0-1
            scores.append(age_score * weights.get("age", 0.2))
        
        # Type similarity (binary)
        type_score = 1.0 if target.property_type == comparable.property_type else 0.0
        scores.append(type_score * weights.get("type", 0.15))
        
        return sum(scores) 