"""
Validation Engine - Comprehensive data validation for extraction framework
"""

import re
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Union, Callable
from enum import Enum
import structlog
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)


class ValidationSeverity(str, Enum):
    """Validation severity levels"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationType(str, Enum):
    """Types of validation rules"""
    DATA_TYPE = "data_type"
    RANGE = "range"
    PATTERN = "pattern"
    LENGTH = "length"
    ENUM = "enum"
    CUSTOM = "custom"
    BUSINESS_RULE = "business_rule"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    REFERENTIAL = "referential"


class ValidationRule(BaseModel):
    """Validation rule definition for extraction framework"""
    name: str
    field_name: str
    rule_type: ValidationType
    severity: ValidationSeverity = ValidationSeverity.ERROR
    
    # Type validation
    expected_type: Optional[str] = None
    allow_null: bool = False
    
    # Range validation
    min_value: Optional[Union[int, float, datetime]] = None
    max_value: Optional[Union[int, float, datetime]] = None
    
    # Pattern validation
    pattern: Optional[str] = None
    flags: int = 0  # Regex flags
    
    # Length validation
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    
    # Enum validation
    allowed_values: Optional[List[Any]] = None
    
    # Custom validation
    custom_function: Optional[str] = None
    custom_params: Dict[str, Any] = Field(default_factory=dict)
    
    # Business rule validation
    business_rule: Optional[str] = None
    depends_on_fields: List[str] = Field(default_factory=list)
    
    # Metadata
    description: Optional[str] = None
    error_message: Optional[str] = None
    suggestion: Optional[str] = None


class ValidationResult(BaseModel):
    """Result of a validation check"""
    rule_name: str
    field_name: str
    is_valid: bool
    severity: ValidationSeverity
    message: str
    value: Any = None
    expected_value: Optional[Any] = None
    suggestion: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ValidationReport(BaseModel):
    """Comprehensive validation report"""
    record_id: str
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warnings: int = 0
    errors: int = 0
    results: List[ValidationResult] = Field(default_factory=list)
    data_quality_score: float = 0.0
    completeness_score: float = 0.0
    is_valid: bool = False
    processing_time_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ValidationEngine:
    """Comprehensive validation engine for extracted data"""
    
    def __init__(self):
        self.rules: Dict[str, List[ValidationRule]] = {}
        self.custom_validators: Dict[str, Callable] = {}
        self.business_rules: Dict[str, Callable] = {}
        
        # Load default validation rules
        self._load_default_rules()
        self._load_property_specific_rules()
        
        logger.info("Validation engine initialized")
    
    def _load_default_rules(self):
        """Load default validation rules"""
        # Property ID validation
        self.add_rule(ValidationRule(
            name="property_id_required",
            field_name="property_id",
            rule_type=ValidationType.COMPLETENESS,
            severity=ValidationSeverity.ERROR,
            allow_null=False,
            description="Property ID is required",
            error_message="Property ID cannot be empty or null"
        ))
        
        self.add_rule(ValidationRule(
            name="property_id_format",
            field_name="property_id",
            rule_type=ValidationType.PATTERN,
            pattern=r'^[A-Za-z0-9\-_]{3,50}$',
            description="Property ID format validation",
            error_message="Property ID must be 3-50 characters, alphanumeric with hyphens/underscores"
        ))
        
        # Address validation
        self.add_rule(ValidationRule(
            name="address_required",
            field_name="address",
            rule_type=ValidationType.COMPLETENESS,
            allow_null=False,
            description="Address is required"
        ))
        
        self.add_rule(ValidationRule(
            name="address_length",
            field_name="address",
            rule_type=ValidationType.LENGTH,
            min_length=5,
            max_length=200,
            description="Address length validation"
        ))
        
        # Coordinates validation
        self.add_rule(ValidationRule(
            name="latitude_range",
            field_name="latitude",
            rule_type=ValidationType.RANGE,
            expected_type="float",
            min_value=-90.0,
            max_value=90.0,
            description="Latitude must be between -90 and 90 degrees"
        ))
        
        self.add_rule(ValidationRule(
            name="longitude_range",
            field_name="longitude",
            rule_type=ValidationType.RANGE,
            expected_type="float",
            min_value=-180.0,
            max_value=180.0,
            description="Longitude must be between -180 and 180 degrees"
        ))
        
        # Phone number validation
        self.add_rule(ValidationRule(
            name="phone_format",
            field_name="phone",
            rule_type=ValidationType.PATTERN,
            pattern=r'^\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}$',
            severity=ValidationSeverity.WARNING,
            description="Phone number format validation"
        ))
        
        # Email validation
        self.add_rule(ValidationRule(
            name="email_format",
            field_name="email",
            rule_type=ValidationType.PATTERN,
            pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            description="Email format validation"
        ))
        
        # Date validation
        self.add_rule(ValidationRule(
            name="date_format",
            field_name="date_listed",
            rule_type=ValidationType.CUSTOM,
            custom_function="validate_date_format",
            description="Date format validation"
        ))
    
    def _load_property_specific_rules(self):
        """Load property-specific validation rules"""
        # Square footage validation
        self.add_rule(ValidationRule(
            name="square_footage_positive",
            field_name="square_footage",
            rule_type=ValidationType.RANGE,
            expected_type="numeric",
            min_value=1,
            max_value=10000000,  # 10M square feet max
            description="Square footage must be positive and reasonable"
        ))
        
        # Lot size validation
        self.add_rule(ValidationRule(
            name="lot_size_positive",
            field_name="lot_size",
            rule_type=ValidationType.RANGE,
            expected_type="numeric",
            min_value=1,
            max_value=1000000000,  # 1B square feet max for very large lots
            description="Lot size must be positive"
        ))
        
        # Year built validation
        current_year = datetime.now().year
        self.add_rule(ValidationRule(
            name="year_built_range",
            field_name="year_built",
            rule_type=ValidationType.RANGE,
            expected_type="integer",
            min_value=1800,
            max_value=current_year + 5,  # Allow future construction
            description="Year built must be reasonable"
        ))
        
        # Price validation
        self.add_rule(ValidationRule(
            name="price_positive",
            field_name="price",
            rule_type=ValidationType.RANGE,
            expected_type="numeric",
            min_value=0,
            max_value=1000000000,  # $1B max
            description="Price must be positive and reasonable"
        ))
        
        # Assessed value validation
        self.add_rule(ValidationRule(
            name="assessed_value_positive",
            field_name="assessed_value",
            rule_type=ValidationType.RANGE,
            expected_type="numeric",
            min_value=0,
            max_value=1000000000,
            description="Assessed value must be positive"
        ))
        
        # Property type validation
        self.add_rule(ValidationRule(
            name="property_type_enum",
            field_name="property_type",
            rule_type=ValidationType.ENUM,
            allowed_values=[
                "industrial", "warehouse", "manufacturing", "distribution",
                "office", "retail", "mixed_use", "land", "other"
            ],
            severity=ValidationSeverity.WARNING,
            description="Property type should be from standard list"
        ))
        
        # Zoning validation
        self.add_rule(ValidationRule(
            name="zoning_format",
            field_name="zoning",
            rule_type=ValidationType.PATTERN,
            pattern=r'^[A-Z0-9\-]{1,10}$',
            severity=ValidationSeverity.WARNING,
            description="Zoning code format validation"
        ))
        
        # Business rule: price per square foot reasonableness
        self.add_rule(ValidationRule(
            name="price_per_sqft_reasonable",
            field_name="price",
            rule_type=ValidationType.BUSINESS_RULE,
            business_rule="validate_price_per_sqft",
            depends_on_fields=["square_footage"],
            severity=ValidationSeverity.WARNING,
            description="Price per square foot should be reasonable"
        ))
        
        # Consistency check: lot size vs square footage
        self.add_rule(ValidationRule(
            name="lot_size_vs_building_size",
            field_name="lot_size",
            rule_type=ValidationType.CONSISTENCY,
            business_rule="validate_lot_vs_building_size",
            depends_on_fields=["square_footage"],
            severity=ValidationSeverity.WARNING,
            description="Lot size should be larger than building size"
        ))
    
    def add_rule(self, rule: ValidationRule):
        """Add a validation rule"""
        if rule.field_name not in self.rules:
            self.rules[rule.field_name] = []
        
        self.rules[rule.field_name].append(rule)
        logger.debug("Validation rule added", 
                    rule_name=rule.name,
                    field_name=rule.field_name,
                    rule_type=rule.rule_type.value)
    
    def register_custom_validator(self, name: str, validator: Callable):
        """Register a custom validation function"""
        self.custom_validators[name] = validator
        logger.debug("Custom validator registered", name=name)
    
    def register_business_rule(self, name: str, rule_function: Callable):
        """Register a business rule validation function"""
        self.business_rules[name] = rule_function
        logger.debug("Business rule registered", name=name)
    
    async def validate_record(
        self,
        data: Dict[str, Any],
        record_id: Optional[str] = None,
        additional_rules: Optional[List[ValidationRule]] = None
    ) -> ValidationReport:
        """
        Validate a single data record
        
        Args:
            data: Data record to validate
            record_id: Optional record identifier
            additional_rules: Additional validation rules to apply
            
        Returns:
            Validation report
        """
        start_time = datetime.utcnow()
        record_id = record_id or data.get("id", "unknown")
        
        report = ValidationReport(record_id=record_id)
        
        try:
            # Get all rules to apply
            rules_to_apply = []
            
            # Add field-specific rules
            for field_name, value in data.items():
                field_rules = self.rules.get(field_name, [])
                rules_to_apply.extend(field_rules)
            
            # Add additional rules
            if additional_rules:
                rules_to_apply.extend(additional_rules)
            
            # Apply validation rules
            for rule in rules_to_apply:
                result = await self._apply_validation_rule(rule, data)
                if result:
                    report.results.append(result)
                    report.total_checks += 1
                    
                    if result.is_valid:
                        report.passed_checks += 1
                    else:
                        report.failed_checks += 1
                        
                        if result.severity == ValidationSeverity.ERROR:
                            report.errors += 1
                        elif result.severity == ValidationSeverity.WARNING:
                            report.warnings += 1
            
            # Calculate scores
            report.data_quality_score = self._calculate_data_quality_score(report, data)
            report.completeness_score = self._calculate_completeness_score(data)
            report.is_valid = report.errors == 0
            
            # Calculate processing time
            end_time = datetime.utcnow()
            report.processing_time_ms = (end_time - start_time).total_seconds() * 1000
            
            logger.debug("Record validation completed", 
                        record_id=record_id,
                        is_valid=report.is_valid,
                        errors=report.errors,
                        warnings=report.warnings,
                        quality_score=report.data_quality_score)
            
        except Exception as e:
            logger.error("Validation failed", 
                        record_id=record_id,
                        error=str(e))
            
            # Add error result
            error_result = ValidationResult(
                rule_name="validation_error",
                field_name="system",
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Validation process failed: {str(e)}",
                value=str(e)
            )
            report.results.append(error_result)
            report.errors += 1
            report.is_valid = False
        
        return report
    
    async def validate_batch(
        self,
        data: List[Dict[str, Any]],
        rules: Optional[List[str]] = None
    ) -> Dict[str, ValidationReport]:
        """
        Validate a batch of records
        
        Args:
            data: List of data records
            rules: Optional list of rule names to apply
            
        Returns:
            Dictionary mapping record IDs to validation reports
        """
        results = {}
        
        # Filter rules if specified
        additional_rules = []
        if rules:
            for rule_name in rules:
                for field_rules in self.rules.values():
                    for rule in field_rules:
                        if rule.name in rules:
                            additional_rules.append(rule)
        
        # Validate each record
        for i, record in enumerate(data):
            record_id = record.get("id", f"record_{i}")
            report = await self.validate_record(
                record, 
                record_id, 
                additional_rules if additional_rules else None
            )
            results[record_id] = report
        
        logger.info("Batch validation completed", 
                   total_records=len(data),
                   valid_records=sum(1 for r in results.values() if r.is_valid))
        
        return results
    
    async def _apply_validation_rule(
        self,
        rule: ValidationRule,
        data: Dict[str, Any]
    ) -> Optional[ValidationResult]:
        """Apply a single validation rule"""
        try:
            field_value = data.get(rule.field_name)
            
            # Handle null values
            if field_value is None:
                if not rule.allow_null and rule.rule_type == ValidationType.COMPLETENESS:
                    return ValidationResult(
                        rule_name=rule.name,
                        field_name=rule.field_name,
                        is_valid=False,
                        severity=rule.severity,
                        message=rule.error_message or f"Field {rule.field_name} is required",
                        value=field_value
                    )
                elif field_value is None and rule.allow_null:
                    return None  # Skip validation for allowed null values
            
            # Apply validation based on rule type
            if rule.rule_type == ValidationType.DATA_TYPE:
                return self._validate_data_type(rule, field_value)
            
            elif rule.rule_type == ValidationType.RANGE:
                return self._validate_range(rule, field_value)
            
            elif rule.rule_type == ValidationType.PATTERN:
                return self._validate_pattern(rule, field_value)
            
            elif rule.rule_type == ValidationType.LENGTH:
                return self._validate_length(rule, field_value)
            
            elif rule.rule_type == ValidationType.ENUM:
                return self._validate_enum(rule, field_value)
            
            elif rule.rule_type == ValidationType.CUSTOM:
                return await self._validate_custom(rule, field_value, data)
            
            elif rule.rule_type == ValidationType.BUSINESS_RULE:
                return await self._validate_business_rule(rule, field_value, data)
            
            elif rule.rule_type == ValidationType.CONSISTENCY:
                return await self._validate_consistency(rule, field_value, data)
            
            return None
            
        except Exception as e:
            logger.warning("Validation rule application failed", 
                          rule_name=rule.name,
                          field_name=rule.field_name,
                          error=str(e))
            
            return ValidationResult(
                rule_name=rule.name,
                field_name=rule.field_name,
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Validation rule failed: {str(e)}",
                value=field_value
            )
    
    def _validate_data_type(self, rule: ValidationRule, value: Any) -> ValidationResult:
        """Validate data type"""
        is_valid = True
        message = "Data type validation passed"
        
        if rule.expected_type:
            if rule.expected_type == "numeric":
                is_valid = isinstance(value, (int, float)) or self._is_numeric_string(value)
            elif rule.expected_type == "integer":
                is_valid = isinstance(value, int) or (isinstance(value, str) and value.isdigit())
            elif rule.expected_type == "float":
                is_valid = isinstance(value, float) or self._is_float_string(value)
            elif rule.expected_type == "string":
                is_valid = isinstance(value, str)
            elif rule.expected_type == "boolean":
                is_valid = isinstance(value, bool)
            elif rule.expected_type == "datetime":
                is_valid = isinstance(value, (datetime, date)) or self._is_date_string(value)
            
            if not is_valid:
                message = f"Expected {rule.expected_type}, got {type(value).__name__}"
        
        return ValidationResult(
            rule_name=rule.name,
            field_name=rule.field_name,
            is_valid=is_valid,
            severity=rule.severity,
            message=message,
            value=value,
            expected_value=rule.expected_type
        )
    
    def _validate_range(self, rule: ValidationRule, value: Any) -> ValidationResult:
        """Validate range constraints"""
        is_valid = True
        message = "Range validation passed"
        
        try:
            # Convert to numeric if needed
            numeric_value = self._to_numeric(value)
            
            if rule.min_value is not None and numeric_value < rule.min_value:
                is_valid = False
                message = f"Value {numeric_value} is below minimum {rule.min_value}"
            
            elif rule.max_value is not None and numeric_value > rule.max_value:
                is_valid = False
                message = f"Value {numeric_value} is above maximum {rule.max_value}"
                
        except (ValueError, TypeError):
            is_valid = False
            message = f"Cannot validate range for non-numeric value: {value}"
        
        return ValidationResult(
            rule_name=rule.name,
            field_name=rule.field_name,
            is_valid=is_valid,
            severity=rule.severity,
            message=message,
            value=value,
            metadata={"min_value": rule.min_value, "max_value": rule.max_value}
        )
    
    def _validate_pattern(self, rule: ValidationRule, value: Any) -> ValidationResult:
        """Validate pattern matching"""
        is_valid = True
        message = "Pattern validation passed"
        
        if rule.pattern:
            str_value = str(value)
            try:
                if not re.match(rule.pattern, str_value, rule.flags):
                    is_valid = False
                    message = f"Value '{str_value}' does not match pattern '{rule.pattern}'"
            except re.error as e:
                is_valid = False
                message = f"Invalid regex pattern: {str(e)}"
        
        return ValidationResult(
            rule_name=rule.name,
            field_name=rule.field_name,
            is_valid=is_valid,
            severity=rule.severity,
            message=message,
            value=value,
            metadata={"pattern": rule.pattern}
        )
    
    def _validate_length(self, rule: ValidationRule, value: Any) -> ValidationResult:
        """Validate length constraints"""
        is_valid = True
        message = "Length validation passed"
        
        try:
            length = len(str(value))
            
            if rule.min_length is not None and length < rule.min_length:
                is_valid = False
                message = f"Length {length} is below minimum {rule.min_length}"
            
            elif rule.max_length is not None and length > rule.max_length:
                is_valid = False
                message = f"Length {length} is above maximum {rule.max_length}"
                
        except TypeError:
            is_valid = False
            message = f"Cannot measure length of value: {value}"
        
        return ValidationResult(
            rule_name=rule.name,
            field_name=rule.field_name,
            is_valid=is_valid,
            severity=rule.severity,
            message=message,
            value=value,
            metadata={"min_length": rule.min_length, "max_length": rule.max_length}
        )
    
    def _validate_enum(self, rule: ValidationRule, value: Any) -> ValidationResult:
        """Validate enumeration constraints"""
        is_valid = True
        message = "Enum validation passed"
        
        if rule.allowed_values and value not in rule.allowed_values:
            is_valid = False
            message = f"Value '{value}' not in allowed values: {rule.allowed_values}"
            
            # Find closest match for suggestion
            if isinstance(value, str):
                suggestions = [v for v in rule.allowed_values if isinstance(v, str)]
                if suggestions:
                    # Simple suggestion based on partial matching
                    closest = min(suggestions, key=lambda x: abs(len(x) - len(value)))
                    message += f". Did you mean '{closest}'?"
        
        return ValidationResult(
            rule_name=rule.name,
            field_name=rule.field_name,
            is_valid=is_valid,
            severity=rule.severity,
            message=message,
            value=value,
            metadata={"allowed_values": rule.allowed_values}
        )
    
    async def _validate_custom(
        self,
        rule: ValidationRule,
        value: Any,
        data: Dict[str, Any]
    ) -> ValidationResult:
        """Apply custom validation function"""
        is_valid = True
        message = "Custom validation passed"
        
        if rule.custom_function and rule.custom_function in self.custom_validators:
            try:
                validator = self.custom_validators[rule.custom_function]
                result = validator(value, rule.custom_params, data)
                
                if isinstance(result, bool):
                    is_valid = result
                    if not is_valid:
                        message = f"Custom validation failed for {rule.custom_function}"
                elif isinstance(result, dict):
                    is_valid = result.get("valid", False)
                    message = result.get("message", message)
                    
            except Exception as e:
                is_valid = False
                message = f"Custom validation error: {str(e)}"
        else:
            is_valid = False
            message = f"Custom validator '{rule.custom_function}' not found"
        
        return ValidationResult(
            rule_name=rule.name,
            field_name=rule.field_name,
            is_valid=is_valid,
            severity=rule.severity,
            message=message,
            value=value
        )
    
    async def _validate_business_rule(
        self,
        rule: ValidationRule,
        value: Any,
        data: Dict[str, Any]
    ) -> ValidationResult:
        """Apply business rule validation"""
        is_valid = True
        message = "Business rule validation passed"
        
        if rule.business_rule and rule.business_rule in self.business_rules:
            try:
                business_rule = self.business_rules[rule.business_rule]
                result = business_rule(value, data, rule.depends_on_fields)
                
                if isinstance(result, bool):
                    is_valid = result
                    if not is_valid:
                        message = f"Business rule '{rule.business_rule}' failed"
                elif isinstance(result, dict):
                    is_valid = result.get("valid", False)
                    message = result.get("message", message)
                    
            except Exception as e:
                is_valid = False
                message = f"Business rule error: {str(e)}"
        else:
            is_valid = False
            message = f"Business rule '{rule.business_rule}' not found"
        
        return ValidationResult(
            rule_name=rule.name,
            field_name=rule.field_name,
            is_valid=is_valid,
            severity=rule.severity,
            message=message,
            value=value
        )
    
    async def _validate_consistency(
        self,
        rule: ValidationRule,
        value: Any,
        data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate data consistency across fields"""
        return await self._validate_business_rule(rule, value, data)
    
    def _calculate_data_quality_score(
        self,
        report: ValidationReport,
        data: Dict[str, Any]
    ) -> float:
        """Calculate overall data quality score"""
        if report.total_checks == 0:
            return 0.0
        
        # Base score from validation results
        base_score = report.passed_checks / report.total_checks
        
        # Penalty for errors vs warnings
        error_penalty = (report.errors * 0.1) / max(report.total_checks, 1)
        warning_penalty = (report.warnings * 0.05) / max(report.total_checks, 1)
        
        # Completeness bonus
        completeness_bonus = self._calculate_completeness_score(data) * 0.2
        
        # Calculate final score
        final_score = base_score - error_penalty - warning_penalty + completeness_bonus
        return max(0.0, min(1.0, final_score))
    
    def _calculate_completeness_score(self, data: Dict[str, Any]) -> float:
        """Calculate data completeness score"""
        essential_fields = ["property_id", "address", "city"]
        important_fields = ["property_type", "square_footage", "assessed_value"]
        optional_fields = ["year_built", "lot_size", "latitude", "longitude"]
        
        total_score = 0.0
        max_score = 0.0
        
        # Essential fields (60% weight)
        for field in essential_fields:
            max_score += 0.6
            if field in data and data[field] is not None and str(data[field]).strip():
                total_score += 0.6
        
        # Important fields (30% weight)
        for field in important_fields:
            max_score += 0.3
            if field in data and data[field] is not None and str(data[field]).strip():
                total_score += 0.3
        
        # Optional fields (10% weight)
        for field in optional_fields:
            max_score += 0.1
            if field in data and data[field] is not None and str(data[field]).strip():
                total_score += 0.1
        
        return total_score / max_score if max_score > 0 else 0.0
    
    def _is_numeric_string(self, value: str) -> bool:
        """Check if string can be converted to number"""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    
    def _is_float_string(self, value: str) -> bool:
        """Check if string can be converted to float"""
        try:
            float(value)
            return '.' in value
        except (ValueError, TypeError):
            return False
    
    def _is_date_string(self, value: str) -> bool:
        """Check if string can be parsed as date"""
        try:
            from dateutil.parser import parse
            parse(value)
            return True
        except:
            return False
    
    def _to_numeric(self, value: Any) -> Union[int, float]:
        """Convert value to numeric"""
        if isinstance(value, (int, float)):
            return value
        elif isinstance(value, str):
            # Clean string value
            clean_value = re.sub(r'[^\d.-]', '', value)
            if '.' in clean_value:
                return float(clean_value)
            else:
                return int(clean_value)
        else:
            raise ValueError(f"Cannot convert {value} to numeric")
    
    def get_rules_summary(self) -> Dict[str, Any]:
        """Get summary of all validation rules"""
        summary = {
            "total_rules": sum(len(rules) for rules in self.rules.values()),
            "rules_by_field": {field: len(rules) for field, rules in self.rules.items()},
            "rules_by_type": {},
            "custom_validators": list(self.custom_validators.keys()),
            "business_rules": list(self.business_rules.keys())
        }
        
        # Count rules by type
        for rules in self.rules.values():
            for rule in rules:
                rule_type = rule.rule_type.value
                summary["rules_by_type"][rule_type] = summary["rules_by_type"].get(rule_type, 0) + 1
        
        return summary 