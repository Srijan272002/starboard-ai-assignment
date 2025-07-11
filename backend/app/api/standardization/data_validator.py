"""
Data Validator - Data validation and quality assessment system
"""

import re
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime
from enum import Enum
import structlog
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)


class ValidationSeverity(str, Enum):
    """Validation error severity levels"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationResult(BaseModel):
    """Result of a validation check"""
    field_name: str
    is_valid: bool
    severity: ValidationSeverity
    message: str
    value: Any = None
    expected_type: Optional[str] = None
    suggestions: List[str] = []


class ValidationRule(BaseModel):
    """Validation rule definition"""
    field_name: str
    rule_type: str  # "type", "range", "pattern", "length", "enum", "custom"
    required: bool = False
    data_type: Optional[str] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    pattern: Optional[str] = None
    allowed_values: Optional[List[Any]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    custom_validator: Optional[str] = None


class DataValidator:
    """Data validation and quality assessment"""
    
    def __init__(self):
        self.validation_rules: Dict[str, List[ValidationRule]] = {}
        self._load_default_rules()
        logger.info("Data validator initialized")
    
    def _load_default_rules(self):
        """Load default validation rules"""
        # Property ID validation
        self.add_rule("property_id", ValidationRule(
            field_name="property_id",
            rule_type="type",
            required=True,
            data_type="string",
            min_length=1
        ))
        
        # Address validation
        self.add_rule("address", ValidationRule(
            field_name="address",
            rule_type="length",
            required=True,
            min_length=5,
            max_length=200
        ))
        
        # Price validation
        self.add_rule("price", ValidationRule(
            field_name="price",
            rule_type="range",
            data_type="numeric",
            min_value=0,
            max_value=1000000000
        ))
        
        # Square footage validation
        self.add_rule("square_feet", ValidationRule(
            field_name="square_feet",
            rule_type="range",
            data_type="numeric",
            min_value=1,
            max_value=10000000
        ))
        
        # Zip code validation
        self.add_rule("zip_code", ValidationRule(
            field_name="zip_code",
            rule_type="pattern",
            pattern=r'^\d{5}(-\d{4})?$'
        ))
        
        # Email validation
        self.add_rule("email", ValidationRule(
            field_name="email",
            rule_type="pattern",
            pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        ))
        
        # Phone validation
        self.add_rule("phone", ValidationRule(
            field_name="phone",
            rule_type="pattern",
            pattern=r'^\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}$'
        ))
        
        # Coordinates validation
        self.add_rule("latitude", ValidationRule(
            field_name="latitude",
            rule_type="range",
            data_type="numeric",
            min_value=-90,
            max_value=90
        ))
        
        self.add_rule("longitude", ValidationRule(
            field_name="longitude",
            rule_type="range",
            data_type="numeric",
            min_value=-180,
            max_value=180
        ))
    
    def add_rule(self, field_name: str, rule: ValidationRule):
        """Add a validation rule for a field"""
        if field_name not in self.validation_rules:
            self.validation_rules[field_name] = []
        self.validation_rules[field_name].append(rule)
    
    def validate_value(
        self,
        field_name: str,
        value: Any,
        custom_rules: Optional[List[ValidationRule]] = None
    ) -> List[ValidationResult]:
        """
        Validate a single field value
        
        Args:
            field_name: Name of the field
            value: Value to validate
            custom_rules: Optional custom rules to apply
            
        Returns:
            List of validation results
        """
        results = []
        
        # Get rules to apply
        rules_to_apply = []
        if custom_rules:
            rules_to_apply.extend(custom_rules)
        rules_to_apply.extend(self.validation_rules.get(field_name, []))
        
        if not rules_to_apply:
            # No rules defined, consider it valid
            results.append(ValidationResult(
                field_name=field_name,
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="No validation rules defined",
                value=value
            ))
            return results
        
        # Apply each rule
        for rule in rules_to_apply:
            result = self._apply_validation_rule(field_name, value, rule)
            if result:
                results.append(result)
        
        return results
    
    def _apply_validation_rule(
        self,
        field_name: str,
        value: Any,
        rule: ValidationRule
    ) -> Optional[ValidationResult]:
        """Apply a single validation rule"""
        try:
            # Check if required
            if rule.required and (value is None or value == ""):
                return ValidationResult(
                    field_name=field_name,
                    is_valid=False,
                    severity=ValidationSeverity.ERROR,
                    message="Field is required but missing or empty",
                    value=value
                )
            
            # Skip validation if value is None/empty and not required
            if value is None or value == "":
                return None
            
            # Type validation
            if rule.rule_type == "type" and rule.data_type:
                if not self._validate_type(value, rule.data_type):
                    return ValidationResult(
                        field_name=field_name,
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message=f"Expected type {rule.data_type} but got {type(value).__name__}",
                        value=value,
                        expected_type=rule.data_type
                    )
            
            # Range validation
            elif rule.rule_type == "range":
                numeric_value = self._convert_to_numeric(value)
                if numeric_value is not None:
                    if rule.min_value is not None and numeric_value < rule.min_value:
                        return ValidationResult(
                            field_name=field_name,
                            is_valid=False,
                            severity=ValidationSeverity.ERROR,
                            message=f"Value {numeric_value} is below minimum {rule.min_value}",
                            value=value
                        )
                    if rule.max_value is not None and numeric_value > rule.max_value:
                        return ValidationResult(
                            field_name=field_name,
                            is_valid=False,
                            severity=ValidationSeverity.ERROR,
                            message=f"Value {numeric_value} is above maximum {rule.max_value}",
                            value=value
                        )
                else:
                    return ValidationResult(
                        field_name=field_name,
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message="Expected numeric value for range validation",
                        value=value
                    )
            
            # Pattern validation
            elif rule.rule_type == "pattern" and rule.pattern:
                str_value = str(value)
                if not re.match(rule.pattern, str_value):
                    return ValidationResult(
                        field_name=field_name,
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message=f"Value does not match required pattern: {rule.pattern}",
                        value=value
                    )
            
            # Length validation
            elif rule.rule_type == "length":
                length = len(str(value))
                if rule.min_length is not None and length < rule.min_length:
                    return ValidationResult(
                        field_name=field_name,
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message=f"Length {length} is below minimum {rule.min_length}",
                        value=value
                    )
                if rule.max_length is not None and length > rule.max_length:
                    return ValidationResult(
                        field_name=field_name,
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message=f"Length {length} is above maximum {rule.max_length}",
                        value=value
                    )
            
            # Enum validation
            elif rule.rule_type == "enum" and rule.allowed_values:
                if value not in rule.allowed_values:
                    return ValidationResult(
                        field_name=field_name,
                        is_valid=False,
                        severity=ValidationSeverity.ERROR,
                        message=f"Value not in allowed values: {rule.allowed_values}",
                        value=value,
                        suggestions=rule.allowed_values[:5]  # First 5 suggestions
                    )
            
            # Custom validation
            elif rule.rule_type == "custom" and rule.custom_validator:
                # This would need to be implemented based on specific custom validators
                pass
            
        except Exception as e:
            logger.warning("Validation rule application failed", 
                          field_name=field_name,
                          rule_type=rule.rule_type,
                          error=str(e))
            return ValidationResult(
                field_name=field_name,
                is_valid=False,
                severity=ValidationSeverity.WARNING,
                message=f"Validation error: {str(e)}",
                value=value
            )
        
        return None  # No validation errors
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate data type"""
        type_map = {
            "string": str,
            "integer": int,
            "float": float,
            "numeric": (int, float),
            "boolean": bool,
            "datetime": datetime,
            "list": list,
            "dict": dict
        }
        
        if expected_type == "numeric":
            return isinstance(value, (int, float)) or self._convert_to_numeric(value) is not None
        
        expected_python_type = type_map.get(expected_type)
        if expected_python_type:
            return isinstance(value, expected_python_type)
        
        return True  # Unknown type, assume valid
    
    def _convert_to_numeric(self, value: Any) -> Optional[Union[int, float]]:
        """Convert value to numeric if possible"""
        try:
            if isinstance(value, (int, float)):
                return value
            # Try to convert string to number
            str_value = str(value).strip()
            if '.' in str_value:
                return float(str_value)
            else:
                return int(str_value)
        except (ValueError, TypeError):
            return None
    
    def validate_data(
        self,
        data: Dict[str, Any],
        stop_on_first_error: bool = False
    ) -> Dict[str, List[ValidationResult]]:
        """
        Validate all fields in a data dictionary
        
        Args:
            data: Data to validate
            stop_on_first_error: Stop validation on first error
            
        Returns:
            Dictionary of field names to validation results
        """
        validation_results = {}
        
        for field_name, value in data.items():
            results = self.validate_value(field_name, value)
            if results:
                validation_results[field_name] = results
                
                # Stop on first error if requested
                if stop_on_first_error and any(not r.is_valid for r in results):
                    break
        
        return validation_results
    
    def get_validation_summary(
        self,
        validation_results: Dict[str, List[ValidationResult]]
    ) -> Dict[str, Any]:
        """Get summary of validation results"""
        total_fields = len(validation_results)
        total_errors = 0
        total_warnings = 0
        fields_with_errors = []
        fields_with_warnings = []
        
        for field_name, results in validation_results.items():
            has_error = False
            has_warning = False
            
            for result in results:
                if not result.is_valid:
                    if result.severity == ValidationSeverity.ERROR:
                        total_errors += 1
                        has_error = True
                    elif result.severity == ValidationSeverity.WARNING:
                        total_warnings += 1
                        has_warning = True
            
            if has_error:
                fields_with_errors.append(field_name)
            elif has_warning:
                fields_with_warnings.append(field_name)
        
        return {
            "total_fields": total_fields,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "fields_with_errors": fields_with_errors,
            "fields_with_warnings": fields_with_warnings,
            "validation_passed": total_errors == 0
        }
    
    def get_data_quality_score(
        self,
        validation_results: Dict[str, List[ValidationResult]]
    ) -> float:
        """Calculate data quality score (0.0 to 1.0)"""
        if not validation_results:
            return 1.0
        
        total_checks = sum(len(results) for results in validation_results.values())
        if total_checks == 0:
            return 1.0
        
        failed_checks = sum(
            1 for results in validation_results.values()
            for result in results
            if not result.is_valid and result.severity == ValidationSeverity.ERROR
        )
        
        warning_checks = sum(
            1 for results in validation_results.values()
            for result in results
            if not result.is_valid and result.severity == ValidationSeverity.WARNING
        )
        
        # Errors have more weight than warnings
        quality_score = 1.0 - (failed_checks + warning_checks * 0.5) / total_checks
        return max(0.0, quality_score) 