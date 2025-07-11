import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)

@pytest.fixture
def sample_property_data():
    """Sample property data for testing."""
    return {
        "property_id": "TEST001",
        "county": "Cook",
        "address": "123 Industrial Blvd",
        "city": "Chicago",
        "state": "IL",
        "zip_code": "60601",
        "property_type": "Industrial",
        "zoning": "M1",
        "square_footage": 50000.0,
        "lot_size": 100000.0,
        "year_built": 1995,
        "latitude": 41.8781,
        "longitude": -87.6298,
        "assessed_value": 2500000.0,
        "features": {
            "loading_docks": 4,
            "ceiling_height": 24,
            "crane_capacity": 0
        }
    } 