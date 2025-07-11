"""
Field Normalizer - Data normalization and cleaning system
"""

import re
from typing import Any, Dict, Optional, Union, List
from datetime import datetime
import structlog
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)


class NormalizationRule(BaseModel):
    """Rule for field normalization"""
    field_name: str
    rule_type: str  # "regex", "format", "case", "numeric"
    pattern: Optional[str] = None
    replacement: Optional[str] = None
    format_string: Optional[str] = None
    case_type: Optional[str] = None  # "upper", "lower", "title"


class FieldNormalizer:
    """Field data normalization and cleaning"""
    
    def __init__(self):
        self.normalization_rules: Dict[str, List[NormalizationRule]] = {}
        self._load_default_rules()
        logger.info("Field normalizer initialized")
    
    def _load_default_rules(self):
        """Load default normalization rules"""
        # Address normalization
        self.add_rule("address", NormalizationRule(
            field_name="address",
            rule_type="regex",
            pattern=r'\s+',
            replacement=' '
        ))
        
        # Phone number normalization
        self.add_rule("phone", NormalizationRule(
            field_name="phone",
            rule_type="regex",
            pattern=r'[^\d]',
            replacement=''
        ))
        
        # Email normalization
        self.add_rule("email", NormalizationRule(
            field_name="email",
            rule_type="case",
            case_type="lower"
        ))
        
        # Zip code normalization
        self.add_rule("zip_code", NormalizationRule(
            field_name="zip_code",
            rule_type="regex",
            pattern=r'^(\d{5}).*',
            replacement=r'\1'
        ))
    
    def add_rule(self, field_name: str, rule: NormalizationRule):
        """Add a normalization rule for a field"""
        if field_name not in self.normalization_rules:
            self.normalization_rules[field_name] = []
        self.normalization_rules[field_name].append(rule)
    
    def normalize_value(
        self,
        field_name: str,
        value: Any,
        custom_rules: Optional[List[NormalizationRule]] = None
    ) -> Any:
        """
        Normalize a single field value
        
        Args:
            field_name: Name of the field
            value: Value to normalize
            custom_rules: Optional custom rules to apply
            
        Returns:
            Normalized value
        """
        if value is None:
            return None
        
        try:
            # Convert to string for processing
            str_value = str(value)
            
            # Apply custom rules first
            if custom_rules:
                for rule in custom_rules:
                    str_value = self._apply_rule(str_value, rule)
            
            # Apply default rules
            rules = self.normalization_rules.get(field_name, [])
            for rule in rules:
                str_value = self._apply_rule(str_value, rule)
            
            # Try to convert back to original type if possible
            if isinstance(value, (int, float)):
                try:
                    return type(value)(str_value)
                except ValueError:
                    return str_value
            
            return str_value
            
        except Exception as e:
            logger.warning("Normalization failed", 
                          field_name=field_name,
                          value=value,
                          error=str(e))
            return value
    
    def _apply_rule(self, value: str, rule: NormalizationRule) -> str:
        """Apply a single normalization rule"""
        try:
            if rule.rule_type == "regex":
                if rule.pattern and rule.replacement is not None:
                    return re.sub(rule.pattern, rule.replacement, value)
                    
            elif rule.rule_type == "case":
                if rule.case_type == "upper":
                    return value.upper()
                elif rule.case_type == "lower":
                    return value.lower()
                elif rule.case_type == "title":
                    return value.title()
                    
            elif rule.rule_type == "format":
                if rule.format_string:
                    return rule.format_string.format(value)
                    
            elif rule.rule_type == "numeric":
                # Extract numeric value
                numeric_match = re.search(r'[\d.]+', value)
                if numeric_match:
                    return numeric_match.group()
                    
        except Exception as e:
            logger.warning("Rule application failed", 
                          rule_type=rule.rule_type,
                          error=str(e))
        
        return value
    
    def normalize_data(
        self,
        data: Dict[str, Any],
        field_mapping: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Normalize all fields in a data dictionary
        
        Args:
            data: Data to normalize
            field_mapping: Optional mapping of field names to standard names
            
        Returns:
            Normalized data dictionary
        """
        normalized_data = {}
        
        for field_name, value in data.items():
            # Use mapped field name if available
            normalized_field_name = field_mapping.get(field_name, field_name) if field_mapping else field_name
            
            # Normalize the value
            normalized_value = self.normalize_value(normalized_field_name, value)
            normalized_data[normalized_field_name] = normalized_value
        
        return normalized_data
    
    def get_normalization_preview(
        self,
        field_name: str,
        sample_values: List[Any]
    ) -> Dict[str, Any]:
        """
        Preview normalization results for sample values
        
        Args:
            field_name: Name of the field
            sample_values: Sample values to preview
            
        Returns:
            Preview results
        """
        preview = {
            "field_name": field_name,
            "samples": [],
            "rules_applied": len(self.normalization_rules.get(field_name, []))
        }
        
        for original_value in sample_values[:10]:  # Limit to 10 samples
            normalized_value = self.normalize_value(field_name, original_value)
            preview["samples"].append({
                "original": original_value,
                "normalized": normalized_value,
                "changed": original_value != normalized_value
            })
        
        return preview 