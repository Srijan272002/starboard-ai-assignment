import pytest
from fastapi.testclient import TestClient

def test_root_health_check(client: TestClient):
    """Test the root health check endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Starboard AI Property Analysis System"}

def test_health_endpoint(client: TestClient):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_api_health_check(client: TestClient):
    """Test the API health check endpoint."""
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Starboard AI Property Analysis"

def test_detailed_health_check(client: TestClient):
    """Test the detailed health check endpoint."""
    response = client.get("/api/v1/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"
    assert "components" in data 