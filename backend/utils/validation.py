from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum
from .logger import setup_logger

logger = setup_logger("validation")

class PropertyType(str, Enum):
    INDUSTRIAL = "industrial"
    COMMERCIAL = "commercial"
    RETAIL = "retail"
    OFFICE = "office"
    MIXED_USE = "mixed_use"
    WAREHOUSE = "warehouse"
    MANUFACTURING = "manufacturing"
    FLEX = "flex"

class ZoningType(str, Enum):
    M1 = "M1"  # Light Manufacturing
    M2 = "M2"  # Heavy Manufacturing
    I1 = "I-1"  # Light Industrial
    I2 = "I-2"  # Heavy Industrial
    C1 = "C-1"  # Light Commercial
    C2 = "C-2"  # Heavy Commercial
    MU = "MU"   # Mixed Use

class Address(BaseModel):
    street: str
    city: str
    state: str
    zip_code: str
    formatted: Optional[str] = None

    @validator('zip_code')
    def validate_zip_code(cls, v):
        if not v.isdigit() or len(v) not in [5, 9]:
            raise ValueError('Invalid ZIP code format')
        return v

    @validator('formatted', always=True)
    def set_formatted_address(cls, v, values):
        if v is None and all(key in values for key in ['street', 'city', 'state', 'zip_code']):
            return f"{values['street']}, {values['city']}, {values['state']} {values['zip_code']}"
        return v

class PropertyMetrics(BaseModel):
    total_square_feet: float = Field(gt=0)
    office_square_feet: Optional[float] = Field(default=None, ge=0)
    warehouse_square_feet: Optional[float] = Field(default=None, ge=0)
    manufacturing_square_feet: Optional[float] = Field(default=None, ge=0)
    ceiling_height: Optional[float] = Field(default=None, ge=0)
    loading_docks: Optional[int] = Field(default=None, ge=0)
    drive_in_doors: Optional[int] = Field(default=None, ge=0)
    year_built: Optional[int] = Field(default=None)
    year_renovated: Optional[int] = Field(default=None)
    lot_size: Optional[float] = Field(default=None, ge=0)

    @validator('year_built', 'year_renovated')
    def validate_year(cls, v):
        if v is not None:
            current_year = datetime.now().year
            if v < 1800 or v > current_year:
                raise ValueError(f'Year must be between 1800 and {current_year}')
        return v

    @validator('warehouse_square_feet', 'manufacturing_square_feet', 'office_square_feet')
    def validate_component_square_feet(cls, v, values):
        if v is not None:
            total = values.get('total_square_feet', 0)
            if v > total:
                raise ValueError('Component square footage cannot exceed total square footage')
        return v

class PropertyFinancials(BaseModel):
    last_sale_price: Optional[float] = Field(default=None, ge=0)
    last_sale_date: Optional[datetime] = None
    current_value: Optional[float] = Field(default=None, ge=0)
    price_per_square_foot: Optional[float] = Field(default=None, ge=0)
    noi: Optional[float] = Field(default=None)
    cap_rate: Optional[float] = Field(default=None, ge=0, le=100)
    occupancy_rate: Optional[float] = Field(default=None, ge=0, le=100)

class ValidatedProperty(BaseModel):
    id: str
    property_type: PropertyType
    zoning_type: ZoningType
    address: Address
    metrics: PropertyMetrics
    financials: PropertyFinancials
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    raw_data: Dict = Field(default_factory=dict)

    class Config:
        validate_assignment = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    property: Optional[ValidatedProperty] = None

class DataValidator:
    def __init__(self):
        self.logger = logger

    async def validate_property(self, data: Dict) -> ValidationResult:
        """
        Validates property data and returns a ValidationResult
        """
        try:
            # Convert raw data to ValidatedProperty
            property = ValidatedProperty(**data)
            return ValidationResult(
                is_valid=True,
                property=property
            )
        except Exception as e:
            self.logger.error(f"Validation error: {str(e)}")
            return ValidationResult(
                is_valid=False,
                errors=[str(e)]
            )

    def validate_industrial_criteria(self, property: ValidatedProperty) -> ValidationResult:
        """
        Validates if a property meets industrial property criteria
        """
        warnings = []
        errors = []

        # Check property type
        if property.property_type not in [
            PropertyType.INDUSTRIAL,
            PropertyType.WAREHOUSE,
            PropertyType.MANUFACTURING,
            PropertyType.FLEX
        ]:
            errors.append(f"Property type {property.property_type} is not industrial")

        # Check zoning
        if property.zoning_type not in [
            ZoningType.M1,
            ZoningType.M2,
            ZoningType.I1,
            ZoningType.I2
        ]:
            errors.append(f"Zoning type {property.zoning_type} is not industrial")

        # Check size requirements
        if property.metrics.total_square_feet < 10000:
            warnings.append("Property may be too small for industrial use")

        # Check ceiling height if available
        if property.metrics.ceiling_height is not None:
            if property.metrics.ceiling_height < 14:
                warnings.append("Ceiling height may be too low for industrial use")

        # Check loading facilities
        if (property.metrics.loading_docks is None and 
            property.metrics.drive_in_doors is None):
            warnings.append("No loading facility information available")
        elif (property.metrics.loading_docks == 0 and 
              property.metrics.drive_in_doors == 0):
            warnings.append("Property has no loading facilities")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            property=property
        )

# Global validator instance
validator = DataValidator() 