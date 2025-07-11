"""
Data Processor - Smart format handlers and data processing system
"""

from abc import ABC, abstractmethod
import json
from typing import Any, Dict, List, Optional, Union
import jsonschema
import structlog
from pydantic import BaseModel, ValidationError

from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)


class ProcessingResult(BaseModel):
    """Result of data processing operation"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    errors: List[str] = []
    warnings: List[str] = []
    metadata: Dict[str, Any] = {}


class BaseProcessor(ABC):
    """Base class for data processors"""
    
    @abstractmethod
    async def process(self, data: Any) -> ProcessingResult:
        """Process data and return standardized result"""
        pass

    @abstractmethod
    async def validate(self, data: Any) -> bool:
        """Validate data format"""
        pass


class JSONProcessor(BaseProcessor):
    """JSON data processor with schema validation"""
    
    def __init__(self, schema: Optional[Dict[str, Any]] = None):
        self.schema = schema
        
    async def process(self, data: Any) -> ProcessingResult:
        """Process JSON data"""
        try:
            # Parse JSON if string
            if isinstance(data, str):
                try:
                    parsed_data = json.loads(data)
                except json.JSONDecodeError as e:
                    return ProcessingResult(
                        success=False,
                        errors=[f"Invalid JSON format: {str(e)}"]
                    )
            else:
                parsed_data = data
            
            # Validate against schema if provided
            if self.schema:
                try:
                    jsonschema.validate(instance=parsed_data, schema=self.schema)
                except jsonschema.exceptions.ValidationError as e:
                    return ProcessingResult(
                        success=False,
                        errors=[f"Schema validation failed: {str(e)}"]
                    )
            
            # Process nested structures
            processed_data = self._process_nested(parsed_data)
            
            return ProcessingResult(
                success=True,
                data=processed_data,
                metadata={
                    "format": "json",
                    "schema_validated": bool(self.schema)
                }
            )
            
        except Exception as e:
            logger.error("JSON processing failed", error=str(e))
            return ProcessingResult(
                success=False,
                errors=[f"JSON processing failed: {str(e)}"]
            )
    
    async def validate(self, data: Any) -> bool:
        """Validate JSON data"""
        try:
            # Validate JSON format
            if isinstance(data, str):
                json.loads(data)
            
            # Validate against schema if provided
            if self.schema:
                if isinstance(data, str):
                    parsed_data = json.loads(data)
                else:
                    parsed_data = data
                jsonschema.validate(instance=parsed_data, schema=self.schema)
            
            return True
            
        except (json.JSONDecodeError, jsonschema.exceptions.ValidationError):
            return False
    
    def _process_nested(self, data: Any) -> Any:
        """Process nested JSON structures"""
        if isinstance(data, dict):
            return {k: self._process_nested(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._process_nested(item) for item in data]
        else:
            return data 


class CSVProcessor(BaseProcessor):
    """CSV data processor with header detection"""
    
    def __init__(
        self,
        delimiter: str = ",",
        has_header: Optional[bool] = None,
        expected_columns: Optional[List[str]] = None
    ):
        self.delimiter = delimiter
        self.has_header = has_header
        self.expected_columns = expected_columns
    
    async def process(self, data: Any) -> ProcessingResult:
        """Process CSV data"""
        try:
            import csv
            from io import StringIO
            
            # Convert to string if bytes
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            
            # Create CSV reader
            csv_file = StringIO(data)
            reader = csv.reader(csv_file, delimiter=self.delimiter)
            
            # Read all rows
            rows = list(reader)
            if not rows:
                return ProcessingResult(
                    success=False,
                    errors=["Empty CSV data"]
                )
            
            # Detect header
            has_header = self.has_header
            if has_header is None:
                has_header = self._detect_header(rows[0])
            
            # Extract header and data rows
            if has_header:
                header = rows[0]
                data_rows = rows[1:]
            else:
                header = [f"column_{i}" for i in range(len(rows[0]))]
                data_rows = rows
            
            # Validate columns if expected columns provided
            if self.expected_columns:
                missing_columns = set(self.expected_columns) - set(header)
                if missing_columns:
                    return ProcessingResult(
                        success=False,
                        errors=[f"Missing required columns: {', '.join(missing_columns)}"]
                    )
            
            # Convert to list of dictionaries
            processed_data = []
            for row in data_rows:
                if len(row) != len(header):
                    continue  # Skip malformed rows
                processed_data.append(dict(zip(header, row)))
            
            # Generate warnings for any skipped rows
            warnings = []
            if len(data_rows) != len(processed_data):
                warnings.append(
                    f"Skipped {len(data_rows) - len(processed_data)} malformed rows"
                )
            
            return ProcessingResult(
                success=True,
                data={"rows": processed_data, "header": header},
                warnings=warnings,
                metadata={
                    "format": "csv",
                    "delimiter": self.delimiter,
                    "has_header": has_header,
                    "total_rows": len(data_rows),
                    "processed_rows": len(processed_data)
                }
            )
            
        except Exception as e:
            logger.error("CSV processing failed", error=str(e))
            return ProcessingResult(
                success=False,
                errors=[f"CSV processing failed: {str(e)}"]
            )
    
    async def validate(self, data: Any) -> bool:
        """Validate CSV data"""
        try:
            import csv
            from io import StringIO
            
            # Convert to string if bytes
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            
            # Try to read as CSV
            csv_file = StringIO(data)
            reader = csv.reader(csv_file, delimiter=self.delimiter)
            rows = list(reader)
            
            if not rows:
                return False
            
            # Validate structure
            row_length = len(rows[0])
            return all(len(row) == row_length for row in rows)
            
        except Exception:
            return False
    
    def _detect_header(self, first_row: List[str]) -> bool:
        """Detect if first row is likely a header"""
        # Heuristics for header detection:
        # 1. All string values
        # 2. No empty values
        # 3. No numeric values
        # 4. Contains common header keywords
        
        header_keywords = {"id", "name", "date", "type", "code", "description"}
        
        # Check if all values are strings and not empty
        if not all(isinstance(val, str) and val.strip() for val in first_row):
            return False
        
        # Check if any values are numeric
        if any(val.replace(".", "").isdigit() for val in first_row):
            return False
        
        # Check for header keywords
        first_row_lower = [val.lower() for val in first_row]
        if any(keyword in val for keyword in header_keywords for val in first_row_lower):
            return True
        
        # Default to True if all other checks pass
        return True 


class GeoJSONProcessor(BaseProcessor):
    """GeoJSON processor with spatial validation"""
    
    def __init__(self, validate_topology: bool = True):
        self.validate_topology = validate_topology
        self._load_geojson_schema()
    
    def _load_geojson_schema(self):
        """Load GeoJSON schema"""
        self.schema = {
            "type": "object",
            "required": ["type", "features"],
            "properties": {
                "type": {"enum": ["FeatureCollection"]},
                "features": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["type", "geometry", "properties"],
                        "properties": {
                            "type": {"enum": ["Feature"]},
                            "geometry": {
                                "type": "object",
                                "required": ["type", "coordinates"],
                                "properties": {
                                    "type": {
                                        "enum": [
                                            "Point", "MultiPoint",
                                            "LineString", "MultiLineString",
                                            "Polygon", "MultiPolygon"
                                        ]
                                    },
                                    "coordinates": {"type": "array"}
                                }
                            },
                            "properties": {"type": "object"}
                        }
                    }
                }
            }
        }
    
    async def process(self, data: Any) -> ProcessingResult:
        """Process GeoJSON data"""
        try:
            # Parse JSON if string
            if isinstance(data, str):
                try:
                    parsed_data = json.loads(data)
                except json.JSONDecodeError as e:
                    return ProcessingResult(
                        success=False,
                        errors=[f"Invalid JSON format: {str(e)}"]
                    )
            else:
                parsed_data = data
            
            # Validate GeoJSON structure
            try:
                jsonschema.validate(instance=parsed_data, schema=self.schema)
            except jsonschema.exceptions.ValidationError as e:
                return ProcessingResult(
                    success=False,
                    errors=[f"Invalid GeoJSON structure: {str(e)}"]
                )
            
            # Validate spatial data
            validation_results = self._validate_spatial_data(parsed_data)
            if validation_results["errors"]:
                return ProcessingResult(
                    success=False,
                    errors=validation_results["errors"]
                )
            
            # Process and standardize features
            processed_features = []
            warnings = []
            
            for feature in parsed_data["features"]:
                try:
                    processed_feature = self._process_feature(feature)
                    if processed_feature:
                        processed_features.append(processed_feature)
                except Exception as e:
                    warnings.append(f"Failed to process feature: {str(e)}")
            
            return ProcessingResult(
                success=True,
                data={
                    "type": "FeatureCollection",
                    "features": processed_features
                },
                warnings=warnings + validation_results["warnings"],
                metadata={
                    "format": "geojson",
                    "feature_count": len(processed_features),
                    "bounds": self._calculate_bounds(processed_features)
                }
            )
            
        except Exception as e:
            logger.error("GeoJSON processing failed", error=str(e))
            return ProcessingResult(
                success=False,
                errors=[f"GeoJSON processing failed: {str(e)}"]
            )
    
    async def validate(self, data: Any) -> bool:
        """Validate GeoJSON data"""
        try:
            # Parse JSON if string
            if isinstance(data, str):
                parsed_data = json.loads(data)
            else:
                parsed_data = data
            
            # Validate against GeoJSON schema
            jsonschema.validate(instance=parsed_data, schema=self.schema)
            
            # Basic spatial validation
            validation_results = self._validate_spatial_data(parsed_data)
            return not validation_results["errors"]
            
        except Exception:
            return False
    
    def _validate_spatial_data(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate spatial data in GeoJSON"""
        errors = []
        warnings = []
        
        try:
            for feature in data["features"]:
                geometry = feature["geometry"]
                coords = geometry["coordinates"]
                
                # Validate coordinate structure
                if not self._validate_coordinates(geometry["type"], coords):
                    errors.append(
                        f"Invalid coordinates for {geometry['type']}"
                    )
                
                # Validate coordinate values
                if not self._validate_coordinate_values(coords):
                    errors.append(
                        f"Invalid coordinate values in {geometry['type']}"
                    )
                
                # Validate topology if enabled
                if self.validate_topology:
                    topology_errors = self._validate_topology(geometry)
                    errors.extend(topology_errors)
        
        except Exception as e:
            errors.append(f"Spatial validation failed: {str(e)}")
        
        return {
            "errors": errors,
            "warnings": warnings
        }
    
    def _validate_coordinates(self, geom_type: str, coords: List[Any]) -> bool:
        """Validate coordinate structure based on geometry type"""
        try:
            if geom_type == "Point":
                return len(coords) >= 2
            elif geom_type == "MultiPoint":
                return all(len(p) >= 2 for p in coords)
            elif geom_type == "LineString":
                return len(coords) >= 2 and all(len(p) >= 2 for p in coords)
            elif geom_type == "MultiLineString":
                return all(len(line) >= 2 and all(len(p) >= 2 for p in line) for line in coords)
            elif geom_type == "Polygon":
                return all(len(ring) >= 4 and all(len(p) >= 2 for p in ring) for ring in coords)
            elif geom_type == "MultiPolygon":
                return all(all(len(ring) >= 4 and all(len(p) >= 2 for p in ring) for ring in poly) for poly in coords)
            return False
        except Exception:
            return False
    
    def _validate_coordinate_values(self, coords: List[Any]) -> bool:
        """Validate coordinate values are within valid ranges"""
        def check_coord(coord):
            try:
                lon, lat = coord[0], coord[1]
                return -180 <= lon <= 180 and -90 <= lat <= 90
            except Exception:
                return False
        
        def check_nested(nested_coords):
            if isinstance(nested_coords[0], (int, float)):
                return check_coord(nested_coords)
            return all(check_nested(inner) for inner in nested_coords)
        
        return check_nested(coords)
    
    def _validate_topology(self, geometry: Dict[str, Any]) -> List[str]:
        """Validate topology rules for geometries"""
        errors = []
        geom_type = geometry["type"]
        coords = geometry["coordinates"]
        
        if geom_type in ["Polygon", "MultiPolygon"]:
            # Check if rings are closed
            if geom_type == "Polygon":
                rings = coords
            else:  # MultiPolygon
                rings = [ring for poly in coords for ring in poly]
            
            for ring in rings:
                if ring[0] != ring[-1]:
                    errors.append("Polygon ring is not closed")
        
        return errors
    
    def _process_feature(self, feature: Dict[str, Any]) -> Dict[str, Any]:
        """Process and standardize a GeoJSON feature"""
        processed = {
            "type": "Feature",
            "geometry": feature["geometry"],
            "properties": feature["properties"].copy()
        }
        
        # Add calculated properties
        if feature["geometry"]["type"] in ["Polygon", "MultiPolygon"]:
            processed["properties"]["area"] = self._calculate_area(feature["geometry"])
        
        if feature["geometry"]["type"] in ["LineString", "MultiLineString"]:
            processed["properties"]["length"] = self._calculate_length(feature["geometry"])
        
        return processed
    
    def _calculate_bounds(self, features: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate bounding box for features"""
        if not features:
            return {"minX": 0, "minY": 0, "maxX": 0, "maxY": 0}
        
        bounds = {
            "minX": float("inf"),
            "minY": float("inf"),
            "maxX": float("-inf"),
            "maxY": float("-inf")
        }
        
        def update_bounds(coord):
            bounds["minX"] = min(bounds["minX"], coord[0])
            bounds["minY"] = min(bounds["minY"], coord[1])
            bounds["maxX"] = max(bounds["maxX"], coord[0])
            bounds["maxY"] = max(bounds["maxY"], coord[1])
        
        def process_coords(coords):
            if isinstance(coords[0], (int, float)):
                update_bounds(coords)
            else:
                for coord in coords:
                    process_coords(coord)
        
        for feature in features:
            process_coords(feature["geometry"]["coordinates"])
        
        return bounds
    
    def _calculate_area(self, geometry: Dict[str, Any]) -> float:
        """Calculate approximate area for polygon geometries"""
        # Simple planar area calculation - for more accurate results,
        # use a proper GIS library like Shapely
        def polygon_area(coords):
            area = 0
            for i in range(len(coords) - 1):
                area += coords[i][0] * coords[i + 1][1]
                area -= coords[i + 1][0] * coords[i][1]
            return abs(area) / 2
        
        total_area = 0
        if geometry["type"] == "Polygon":
            total_area = polygon_area(geometry["coordinates"][0])
        elif geometry["type"] == "MultiPolygon":
            for poly in geometry["coordinates"]:
                total_area += polygon_area(poly[0])
        
        return total_area
    
    def _calculate_length(self, geometry: Dict[str, Any]) -> float:
        """Calculate approximate length for line geometries"""
        from math import sqrt
        
        def line_length(coords):
            length = 0
            for i in range(len(coords) - 1):
                dx = coords[i + 1][0] - coords[i][0]
                dy = coords[i + 1][1] - coords[i][1]
                length += sqrt(dx * dx + dy * dy)
            return length
        
        total_length = 0
        if geometry["type"] == "LineString":
            total_length = line_length(geometry["coordinates"])
        elif geometry["type"] == "MultiLineString":
            for line in geometry["coordinates"]:
                total_length += line_length(line)
        
        return total_length 