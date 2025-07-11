"""
Data Transformer - Data transformation and standardization system
"""

import re
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime
from decimal import Decimal
import structlog
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)


class TransformationRule(BaseModel):
    """Rule for data transformation"""
    field_name: str
    rule_type: str  # "unit_convert", "format", "calculate", "lookup", "custom"
    source_unit: Optional[str] = None
    target_unit: Optional[str] = None
    format_string: Optional[str] = None
    calculation: Optional[str] = None
    lookup_table: Optional[Dict[str, Any]] = None
    custom_function: Optional[str] = None
    dependencies: List[str] = []  # Other fields this transformation depends on


class DataTransformer:
    """Data transformation and standardization"""
    
    def __init__(self):
        self.transformation_rules: Dict[str, List[TransformationRule]] = {}
        self.unit_conversion_factors: Dict[str, Dict[str, float]] = {}
        self._load_default_rules()
        self._load_unit_conversions()
        logger.info("Data transformer initialized")
    
    def _load_default_rules(self):
        """Load default transformation rules"""
        # Price normalization - convert to dollars
        self.add_rule("price", TransformationRule(
            field_name="price",
            rule_type="unit_convert",
            source_unit="auto",
            target_unit="usd"
        ))
        
        # Area conversion - convert to square feet
        self.add_rule("square_feet", TransformationRule(
            field_name="square_feet",
            rule_type="unit_convert",
            source_unit="auto",
            target_unit="sqft"
        ))
        
        # Date standardization
        self.add_rule("date_listed", TransformationRule(
            field_name="date_listed",
            rule_type="format",
            format_string="iso"
        ))
        
        # Address standardization
        self.add_rule("address", TransformationRule(
            field_name="address",
            rule_type="format",
            format_string="title_case"
        ))
        
        # Property type standardization
        self.add_rule("property_type", TransformationRule(
            field_name="property_type",
            rule_type="lookup",
            lookup_table={
                # Industrial types
                "warehouse": "industrial_warehouse",
                "warehouses": "industrial_warehouse",
                "distribution": "industrial_distribution",
                "distribution center": "industrial_distribution",
                "manufacturing": "industrial_manufacturing",
                "factory": "industrial_manufacturing",
                "industrial": "industrial_manufacturing",
                "flex": "industrial_flex",
                "flex space": "industrial_flex",
                "r&d": "industrial_r_and_d",
                "research": "industrial_r_and_d",
                "data center": "industrial_data_center",
                "cold storage": "industrial_cold_storage",
                "refrigerated": "industrial_cold_storage",
                # Mixed-use types
                "mixed use industrial": "mixed_use_industrial",
                "mixed use commercial": "mixed_use_commercial"
            }
        ))
    
    def _load_unit_conversions(self):
        """Load unit conversion factors"""
        # Area conversions (to square feet)
        self.unit_conversion_factors["area"] = {
            "sqft": 1.0,
            "sq_ft": 1.0,
            "square_feet": 1.0,
            "sqm": 10.764,  # square meters to sqft
            "sq_m": 10.764,
            "square_meters": 10.764,
            "acre": 43560.0,  # acres to sqft
            "acres": 43560.0
        }
        
        # Currency conversions (to USD)
        self.unit_conversion_factors["currency"] = {
            "usd": 1.0,
            "dollars": 1.0,
            "cad": 0.75,  # Approximate - would use real-time rates in production
            "eur": 1.10,
            "gbp": 1.25
        }
        
        # Length conversions (to feet)
        self.unit_conversion_factors["length"] = {
            "ft": 1.0,
            "feet": 1.0,
            "foot": 1.0,
            "m": 3.281,  # meters to feet
            "meter": 3.281,
            "meters": 3.281,
            "in": 0.0833,  # inches to feet
            "inch": 0.0833,
            "inches": 0.0833,
            "yd": 3.0,  # yards to feet
            "yard": 3.0,
            "yards": 3.0
        }
    
    def add_rule(self, field_name: str, rule: TransformationRule):
        """Add a transformation rule for a field"""
        if field_name not in self.transformation_rules:
            self.transformation_rules[field_name] = []
        self.transformation_rules[field_name].append(rule)
    
    def transform_value(
        self,
        field_name: str,
        value: Any,
        context_data: Optional[Dict[str, Any]] = None,
        custom_rules: Optional[List[TransformationRule]] = None
    ) -> Any:
        """
        Transform a single field value
        
        Args:
            field_name: Name of the field
            value: Value to transform
            context_data: Other field data that might be needed for transformation
            custom_rules: Optional custom rules to apply
            
        Returns:
            Transformed value
        """
        if value is None:
            return None
        
        try:
            current_value = value
            
            # Apply custom rules first
            if custom_rules:
                for rule in custom_rules:
                    current_value = self._apply_transformation_rule(
                        current_value, rule, context_data or {}
                    )
            
            # Apply default rules
            rules = self.transformation_rules.get(field_name, [])
            for rule in rules:
                current_value = self._apply_transformation_rule(
                    current_value, rule, context_data or {}
                )
            
            return current_value
            
        except Exception as e:
            logger.warning("Transformation failed", 
                          field_name=field_name,
                          value=value,
                          error=str(e))
            return value  # Return original value on error
    
    def _apply_transformation_rule(
        self,
        value: Any,
        rule: TransformationRule,
        context_data: Dict[str, Any]
    ) -> Any:
        """Apply a single transformation rule"""
        try:
            if rule.rule_type == "unit_convert":
                return self._convert_units(value, rule)
                
            elif rule.rule_type == "format":
                return self._format_value(value, rule)
                
            elif rule.rule_type == "calculate":
                return self._calculate_value(value, rule, context_data)
                
            elif rule.rule_type == "lookup":
                return self._lookup_value(value, rule)
                
            elif rule.rule_type == "custom":
                return self._apply_custom_transformation(value, rule, context_data)
                
        except Exception as e:
            logger.warning("Rule application failed", 
                          rule_type=rule.rule_type,
                          error=str(e))
        
        return value
    
    def _convert_units(self, value: Any, rule: TransformationRule) -> Any:
        """Convert units of measurement"""
        try:
            # Extract numeric value
            numeric_value = self._extract_numeric(value)
            if numeric_value is None:
                return value
            
            # Detect source unit if auto
            source_unit = rule.source_unit
            if source_unit == "auto":
                source_unit = self._detect_unit(str(value))
            
            if not source_unit or not rule.target_unit:
                return value
            
            # Determine conversion category
            category = self._get_unit_category(source_unit, rule.target_unit)
            if not category:
                return value
            
            # Get conversion factor
            conversion_factors = self.unit_conversion_factors.get(category, {})
            source_factor = conversion_factors.get(source_unit.lower())
            target_factor = conversion_factors.get(rule.target_unit.lower())
            
            if source_factor is None or target_factor is None:
                return value
            
            # Convert: value * source_factor / target_factor
            converted_value = numeric_value * source_factor / target_factor
            
            # Return as appropriate type
            if isinstance(numeric_value, int) and converted_value.is_integer():
                return int(converted_value)
            else:
                return round(converted_value, 2)
                
        except Exception as e:
            logger.warning("Unit conversion failed", error=str(e))
            return value
    
    def _format_value(self, value: Any, rule: TransformationRule) -> Any:
        """Format value according to rule"""
        try:
            if rule.format_string == "iso" and isinstance(value, str):
                # Try to parse and format as ISO date
                return self._parse_and_format_date(value)
                
            elif rule.format_string == "title_case":
                return str(value).title()
                
            elif rule.format_string == "upper_case":
                return str(value).upper()
                
            elif rule.format_string == "lower_case":
                return str(value).lower()
                
            elif rule.format_string and "{}" in rule.format_string:
                return rule.format_string.format(value)
                
        except Exception as e:
            logger.warning("Value formatting failed", error=str(e))
        
        return value
    
    def _calculate_value(
        self,
        value: Any,
        rule: TransformationRule,
        context_data: Dict[str, Any]
    ) -> Any:
        """Calculate derived value"""
        try:
            if not rule.calculation:
                return value
            
            # Simple calculation examples
            if rule.calculation == "price_per_sqft":
                price = self._extract_numeric(context_data.get("price", 0))
                sqft = self._extract_numeric(context_data.get("square_feet", 1))
                if price and sqft and sqft > 0:
                    return round(price / sqft, 2)
                    
            elif rule.calculation == "total_area":
                # Sum multiple area fields
                total = 0
                for field in rule.dependencies:
                    area_value = self._extract_numeric(context_data.get(field, 0))
                    if area_value:
                        total += area_value
                return total
                
        except Exception as e:
            logger.warning("Value calculation failed", error=str(e))
        
        return value
    
    def _lookup_value(self, value: Any, rule: TransformationRule) -> Any:
        """Lookup value in mapping table"""
        try:
            if not rule.lookup_table:
                return value
            
            # Try exact match first
            lookup_key = str(value).lower().strip()
            if lookup_key in rule.lookup_table:
                return rule.lookup_table[lookup_key]
            
            # Try partial matches
            for key, mapped_value in rule.lookup_table.items():
                if key in lookup_key or lookup_key in key:
                    return mapped_value
                    
        except Exception as e:
            logger.warning("Value lookup failed", error=str(e))
        
        return value
    
    def _apply_custom_transformation(
        self,
        value: Any,
        rule: TransformationRule,
        context_data: Dict[str, Any]
    ) -> Any:
        """Apply custom transformation function"""
        # This would be implemented based on specific custom functions
        # For now, return the original value
        return value
    
    def _extract_numeric(self, value: Any) -> Optional[float]:
        """Extract numeric value from various formats"""
        try:
            if isinstance(value, (int, float)):
                return float(value)
            
            if isinstance(value, Decimal):
                return float(value)
            
            # Clean string value
            str_value = str(value).strip()
            
            # Remove common currency symbols and commas
            str_value = re.sub(r'[$,€£¥]', '', str_value)
            
            # Extract first number found
            match = re.search(r'[\d,]+\.?\d*', str_value)
            if match:
                clean_number = match.group().replace(',', '')
                return float(clean_number)
                
        except (ValueError, TypeError):
            pass
        
        return None
    
    def _detect_unit(self, value_str: str) -> Optional[str]:
        """Detect unit from string value"""
        value_lower = value_str.lower()
        
        # Area units
        area_patterns = {
            r'sq\.?\s*ft|square\s*feet|sqft': 'sqft',
            r'sq\.?\s*m|square\s*meters?|sqm': 'sqm',
            r'acres?': 'acre'
        }
        
        # Currency units
        currency_patterns = {
            r'\$|usd|dollars?': 'usd',
            r'€|eur|euros?': 'eur',
            r'£|gbp|pounds?': 'gbp'
        }
        
        # Check patterns
        all_patterns = {**area_patterns, **currency_patterns}
        for pattern, unit in all_patterns.items():
            if re.search(pattern, value_lower):
                return unit
        
        return None
    
    def _get_unit_category(self, unit1: str, unit2: str) -> Optional[str]:
        """Determine the category of units for conversion"""
        all_categories = {
            "area": ["sqft", "sq_ft", "square_feet", "sqm", "sq_m", "square_meters", "acre", "acres"],
            "currency": ["usd", "dollars", "cad", "eur", "gbp"],
            "length": ["ft", "feet", "foot", "m", "meter", "meters", "in", "inch", "inches", "yd", "yard", "yards"]
        }
        
        for category, units in all_categories.items():
            if unit1.lower() in units and unit2.lower() in units:
                return category
        
        return None
    
    def _parse_and_format_date(self, date_str: str) -> str:
        """Parse various date formats and return ISO format"""
        try:
            # Common date patterns
            patterns = [
                "%Y-%m-%d",
                "%m/%d/%Y",
                "%d/%m/%Y",
                "%Y-%m-%d %H:%M:%S",
                "%m/%d/%Y %H:%M:%S"
            ]
            
            for pattern in patterns:
                try:
                    dt = datetime.strptime(date_str.strip(), pattern)
                    return dt.isoformat()
                except ValueError:
                    continue
                    
        except Exception as e:
            logger.warning("Date parsing failed", date_str=date_str, error=str(e))
        
        return date_str  # Return original if parsing fails
    
    def transform_data(
        self,
        data: Dict[str, Any],
        field_mapping: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Transform all fields in a data dictionary
        
        Args:
            data: Data to transform
            field_mapping: Optional mapping of field names to standard names
            
        Returns:
            Transformed data dictionary
        """
        transformed_data = {}
        
        for field_name, value in data.items():
            # Use mapped field name if available
            standard_field_name = field_mapping.get(field_name, field_name) if field_mapping else field_name
            
            # Transform the value
            transformed_value = self.transform_value(standard_field_name, value, data)
            transformed_data[standard_field_name] = transformed_value
        
        # Apply calculated fields that depend on multiple inputs
        self._apply_calculated_fields(transformed_data)
        
        return transformed_data
    
    def _apply_calculated_fields(self, data: Dict[str, Any]):
        """Apply calculated fields that depend on multiple inputs"""
        # Calculate price per square foot if both price and area are available
        if "price" in data and "square_feet" in data:
            price = self._extract_numeric(data["price"])
            sqft = self._extract_numeric(data["square_feet"])
            if price and sqft and sqft > 0:
                data["price_per_sqft"] = round(price / sqft, 2)
    
    def get_transformation_preview(
        self,
        field_name: str,
        sample_values: List[Any],
        context_samples: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Preview transformation results for sample values
        
        Args:
            field_name: Name of the field
            sample_values: Sample values to preview
            context_samples: Sample context data for each value
            
        Returns:
            Preview results
        """
        preview = {
            "field_name": field_name,
            "samples": [],
            "rules_applied": len(self.transformation_rules.get(field_name, []))
        }
        
        for i, original_value in enumerate(sample_values[:10]):  # Limit to 10 samples
            context_data = context_samples[i] if context_samples and i < len(context_samples) else {}
            transformed_value = self.transform_value(field_name, original_value, context_data)
            
            preview["samples"].append({
                "original": original_value,
                "transformed": transformed_value,
                "changed": original_value != transformed_value
            })
        
        return preview 