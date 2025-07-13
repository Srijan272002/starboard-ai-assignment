from typing import Dict, List, Optional
from datetime import datetime
from backend.utils.validation import (
    ValidatedProperty,
    ValidationResult,
    validator,
    PropertyType,
    ZoningType,
    Address,
    PropertyMetrics,
    PropertyFinancials
)
from backend.utils.logger import setup_logger

logger = setup_logger("data_extraction")

class DataExtractionAgent:
    def __init__(self):
        self.logger = logger
        
    async def extract_properties(self, raw_data: List[Dict]) -> List[ValidationResult]:
        """
        Extracts and validates industrial property data
        """
        results = []
        for data in raw_data:
            try:
                # Transform raw data into our schema
                property_data = self._transform_raw_data(data)
                
                # Validate the property data
                validation_result = await validator.validate_property(property_data)
                
                # If valid, check industrial criteria
                if validation_result.is_valid:
                    validation_result = validator.validate_industrial_criteria(
                        validation_result.property
                    )
                
                results.append(validation_result)
                
            except Exception as e:
                self.logger.error(f"Error extracting property: {str(e)}")
                results.append(ValidationResult(
                    is_valid=False,
                    errors=[f"Extraction error: {str(e)}"]
                ))
                
        return results
    
    def _transform_raw_data(self, data: Dict) -> Dict:
        """
        Transforms raw property data into our schema format
        """
        # Extract address components
        address_parts = data.get('address', '').split(',')
        street = address_parts[0].strip() if len(address_parts) > 0 else ''
        city = address_parts[1].strip() if len(address_parts) > 1 else ''
        state_zip = address_parts[2].strip().split() if len(address_parts) > 2 else ['', '']
        state = state_zip[0] if len(state_zip) > 0 else ''
        zip_code = state_zip[1] if len(state_zip) > 1 else ''

        # Create property metrics
        metrics = {
            'total_square_feet': float(data.get('square_feet', 0)),
            'year_built': int(data.get('year_built')) if data.get('year_built') else None,
            'ceiling_height': float(data.get('ceiling_height', 0)) or None,
            'loading_docks': int(data.get('loading_docks', 0)) or None,
            'drive_in_doors': int(data.get('drive_in_doors', 0)) or None,
            'lot_size': float(data.get('lot_size', 0)) or None
        }

        # Create property financials
        financials = {
            'last_sale_price': float(data.get('last_sale_price', 0)) or None,
            'last_sale_date': datetime.fromisoformat(data['last_sale_date']) 
                            if data.get('last_sale_date') else None,
            'current_value': float(data.get('current_value', 0)) or None,
            'price_per_square_foot': float(data.get('price_per_sqft', 0)) or None,
            'noi': float(data.get('noi', 0)) or None,
            'cap_rate': float(data.get('cap_rate', 0)) or None,
            'occupancy_rate': float(data.get('occupancy_rate', 0)) or None
        }

        return {
            'id': str(data.get('id', '')),
            'property_type': data.get('property_type', 'industrial').lower(),
            'zoning_type': data.get('zoning_code', 'M1'),
            'address': {
                'street': street,
                'city': city,
                'state': state,
                'zip_code': zip_code
            },
            'metrics': metrics,
            'financials': financials,
            'latitude': float(data.get('latitude', 0)),
            'longitude': float(data.get('longitude', 0)),
            'raw_data': data
        } 