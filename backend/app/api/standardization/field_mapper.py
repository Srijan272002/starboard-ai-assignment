"""
Field Mapper - Unified field mapping system
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import structlog
from fuzzywuzzy import fuzz, process

from app.core.config import settings
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)


class FieldMappingConfig:
    """Configuration for field mappings"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or settings.FIELD_MAPPING_CONFIG_PATH
        self.config_data = {}
        self._load_config()
    
    def _load_config(self):
        """Load field mapping configuration from YAML file"""
        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    self.config_data = yaml.safe_load(f)
                logger.info("Field mapping config loaded", path=self.config_path)
            else:
                logger.warning("Field mapping config not found", path=self.config_path)
                self._create_default_config()
        except Exception as e:
            logger.error("Failed to load field mapping config", error=str(e))
            self._create_default_config()
    
    def _create_default_config(self):
        """Create default configuration if file doesn't exist"""
        self.config_data = {
            "version": "1.0",
            "standard_fields": {},
            "county_mappings": {},
            "normalization_rules": {},
            "validation_rules": {},
            "transformation_rules": {},
            "fuzzy_matching": {
                "threshold": settings.FUZZY_MATCH_THRESHOLD,
                "algorithms": ["levenshtein"]
            }
        }
    
    def get_standard_fields(self) -> Dict[str, Any]:
        """Get standard field definitions"""
        return self.config_data.get("standard_fields", {})
    
    def get_county_mappings(self, county: str) -> Dict[str, List[str]]:
        """Get field mappings for a specific county"""
        county_mappings = self.config_data.get("county_mappings", {})
        return county_mappings.get(county.lower(), {})
    
    def get_normalization_rules(self) -> Dict[str, Any]:
        """Get field normalization rules"""
        return self.config_data.get("normalization_rules", {})
    
    def get_validation_rules(self) -> Dict[str, Any]:
        """Get data validation rules"""
        return self.config_data.get("validation_rules", {})
    
    def get_transformation_rules(self) -> Dict[str, Any]:
        """Get data transformation rules"""
        return self.config_data.get("transformation_rules", {})
    
    def get_fuzzy_matching_config(self) -> Dict[str, Any]:
        """Get fuzzy matching configuration"""
        return self.config_data.get("fuzzy_matching", {})


class FieldMapper:
    """Unified field mapping system with intelligent field name normalization"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = FieldMappingConfig(config_path)
        self.mapping_cache: Dict[str, Dict[str, str]] = {}
        self._build_mapping_cache()
        
        logger.info("Field mapper initialized")
    
    def _build_mapping_cache(self):
        """Build mapping cache for fast lookups"""
        county_mappings = self.config.config_data.get("county_mappings", {})
        
        for county, mappings in county_mappings.items():
            self.mapping_cache[county] = {}
            
            for standard_field, variations in mappings.items():
                # Add exact matches
                for variation in variations:
                    self.mapping_cache[county][variation.lower()] = standard_field
                
                # Add the standard field itself
                self.mapping_cache[county][standard_field.lower()] = standard_field
        
        logger.info("Field mapping cache built", counties=list(self.mapping_cache.keys()))
    
    def map_fields(
        self,
        raw_data: Dict[str, Any],
        county: str,
        enable_fuzzy_matching: bool = True
    ) -> Dict[str, Any]:
        """
        Map raw field names to standardized field names
        
        Args:
            raw_data: Raw data with original field names
            county: County name for specific mappings
            enable_fuzzy_matching: Enable fuzzy matching for unknown fields
            
        Returns:
            Dictionary with standardized field names
        """
        mapped_data = {}
        unmapped_fields = []
        
        county_lower = county.lower()
        county_cache = self.mapping_cache.get(county_lower, {})
        
        for raw_field, value in raw_data.items():
            raw_field_lower = raw_field.lower()
            
            # Try exact match first
            if raw_field_lower in county_cache:
                standard_field = county_cache[raw_field_lower]
                mapped_data[standard_field] = value
                continue
            
            # Try fuzzy matching if enabled
            if enable_fuzzy_matching:
                standard_field = self._fuzzy_match_field(raw_field, county_lower)
                if standard_field:
                    mapped_data[standard_field] = value
                    # Cache the match for future use
                    county_cache[raw_field_lower] = standard_field
                    continue
            
            # No mapping found
            unmapped_fields.append(raw_field)
            # Keep original field name with prefix to indicate it's unmapped
            mapped_data[f"raw_{raw_field}"] = value
        
        if unmapped_fields:
            logger.debug("Unmapped fields found", 
                        county=county,
                        unmapped_fields=unmapped_fields)
        
        return mapped_data
    
    def _fuzzy_match_field(self, raw_field: str, county: str) -> Optional[str]:
        """
        Use fuzzy matching to find the best matching standard field
        
        Args:
            raw_field: Raw field name to match
            county: County name
            
        Returns:
            Best matching standard field or None
        """
        fuzzy_config = self.config.get_fuzzy_matching_config()
        threshold = fuzzy_config.get("threshold", 0.8) * 100  # Convert to percentage
        
        # Get all possible field variations for this county
        county_mappings = self.config.get_county_mappings(county)
        all_variations = []
        variation_to_standard = {}
        
        for standard_field, variations in county_mappings.items():
            for variation in variations:
                all_variations.append(variation)
                variation_to_standard[variation] = standard_field
        
        if not all_variations:
            return None
        
        # Find best match using fuzzy string matching
        best_match = process.extractOne(
            raw_field,
            all_variations,
            scorer=fuzz.token_sort_ratio
        )
        
        if best_match and best_match[1] >= threshold:
            matched_variation = best_match[0]
            standard_field = variation_to_standard[matched_variation]
            
            logger.debug("Fuzzy match found", 
                        raw_field=raw_field,
                        matched_variation=matched_variation,
                        standard_field=standard_field,
                        score=best_match[1])
            
            return standard_field
        
        return None
    
    def get_field_mapping_dictionary(self, county: str) -> Dict[str, str]:
        """
        Get complete field mapping dictionary for a county
        
        Args:
            county: County name
            
        Returns:
            Dictionary mapping raw field names to standard field names
        """
        return self.mapping_cache.get(county.lower(), {})
    
    def add_field_mapping(
        self,
        county: str,
        raw_field_name: str,
        standard_field_name: str
    ):
        """
        Add a new field mapping
        
        Args:
            county: County name
            raw_field_name: Raw field name from API
            standard_field_name: Standard field name
        """
        county_lower = county.lower()
        
        if county_lower not in self.mapping_cache:
            self.mapping_cache[county_lower] = {}
        
        self.mapping_cache[county_lower][raw_field_name.lower()] = standard_field_name
        
        logger.info("Field mapping added", 
                   county=county,
                   raw_field=raw_field_name,
                   standard_field=standard_field_name)
    
    def discover_new_mappings(
        self,
        raw_data_samples: List[Dict[str, Any]],
        county: str
    ) -> Dict[str, List[str]]:
        """
        Discover potential new field mappings from sample data
        
        Args:
            raw_data_samples: List of raw data samples
            county: County name
            
        Returns:
            Dictionary of potential mappings
        """
        # Collect all field names from samples
        all_fields = set()
        for sample in raw_data_samples:
            all_fields.update(sample.keys())
        
        # Get current mappings
        county_cache = self.mapping_cache.get(county.lower(), {})
        
        # Find unmapped fields
        unmapped_fields = [
            field for field in all_fields
            if field.lower() not in county_cache
        ]
        
        # Suggest mappings using fuzzy matching
        suggested_mappings = {}
        standard_fields = list(self.config.get_standard_fields().keys())
        
        for unmapped_field in unmapped_fields:
            # Try to match with standard field names
            best_match = process.extractOne(
                unmapped_field,
                standard_fields,
                scorer=fuzz.token_sort_ratio
            )
            
            if best_match and best_match[1] >= 60:  # Lower threshold for suggestions
                standard_field = best_match[0]
                if standard_field not in suggested_mappings:
                    suggested_mappings[standard_field] = []
                suggested_mappings[standard_field].append(unmapped_field)
        
        return suggested_mappings
    
    def validate_mapping(
        self,
        raw_field_name: str,
        standard_field_name: str,
        sample_data: List[Any]
    ) -> Dict[str, Any]:
        """
        Validate a field mapping based on sample data
        
        Args:
            raw_field_name: Raw field name
            standard_field_name: Proposed standard field name
            sample_data: Sample values for validation
            
        Returns:
            Validation results
        """
        validation_result = {
            "valid": True,
            "confidence": 0.0,
            "issues": [],
            "data_type_consistency": True,
            "value_range_valid": True
        }
        
        if not sample_data:
            validation_result["valid"] = False
            validation_result["issues"].append("No sample data provided")
            return validation_result
        
        # Check data type consistency
        data_types = set()
        for value in sample_data:
            if value is not None:
                data_types.add(type(value).__name__)
        
        if len(data_types) > 2:  # Allow for some variation (e.g., int/float)
            validation_result["data_type_consistency"] = False
            validation_result["issues"].append(f"Inconsistent data types: {data_types}")
        
        # Check against validation rules if available
        validation_rules = self.config.get_validation_rules()
        if standard_field_name in validation_rules:
            rules = validation_rules[standard_field_name]
            
            numeric_values = []
            for value in sample_data:
                try:
                    numeric_values.append(float(value))
                except (ValueError, TypeError):
                    continue
            
            if numeric_values:
                min_val = min(numeric_values)
                max_val = max(numeric_values)
                
                rule_min = rules.get("min_value")
                rule_max = rules.get("max_value")
                
                if rule_min is not None and min_val < rule_min:
                    validation_result["value_range_valid"] = False
                    validation_result["issues"].append(f"Values below minimum: {min_val} < {rule_min}")
                
                if rule_max is not None and max_val > rule_max:
                    validation_result["value_range_valid"] = False
                    validation_result["issues"].append(f"Values above maximum: {max_val} > {rule_max}")
        
        # Calculate confidence score
        confidence_factors = []
        
        # Field name similarity
        name_similarity = fuzz.token_sort_ratio(raw_field_name, standard_field_name) / 100
        confidence_factors.append(name_similarity * 0.4)
        
        # Data type consistency
        if validation_result["data_type_consistency"]:
            confidence_factors.append(0.3)
        
        # Value range validity
        if validation_result["value_range_valid"]:
            confidence_factors.append(0.3)
        
        validation_result["confidence"] = sum(confidence_factors)
        validation_result["valid"] = (
            validation_result["data_type_consistency"] and
            validation_result["value_range_valid"] and
            validation_result["confidence"] > 0.5
        )
        
        return validation_result
    
    def get_mapping_statistics(self) -> Dict[str, Any]:
        """Get statistics about current field mappings"""
        stats = {
            "total_counties": len(self.mapping_cache),
            "counties": {},
            "standard_fields_coverage": {}
        }
        
        standard_fields = set(self.config.get_standard_fields().keys())
        
        for county, mappings in self.mapping_cache.items():
            county_standard_fields = set(mappings.values())
            stats["counties"][county] = {
                "total_mappings": len(mappings),
                "standard_fields_mapped": len(county_standard_fields),
                "coverage_percentage": len(county_standard_fields) / len(standard_fields) * 100
            }
        
        # Calculate overall coverage for each standard field
        for standard_field in standard_fields:
            counties_with_mapping = sum(
                1 for mappings in self.mapping_cache.values()
                if standard_field in mappings.values()
            )
            stats["standard_fields_coverage"][standard_field] = {
                "counties_mapped": counties_with_mapping,
                "coverage_percentage": counties_with_mapping / len(self.mapping_cache) * 100 if self.mapping_cache else 0
            }
        
        return stats 