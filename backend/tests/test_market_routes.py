import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import json
from backend.main import app
from backend.utils.cache import Cache

client = TestClient(app)

@pytest.fixture
def mock_cache(mocker):
    cache_mock = mocker.patch('backend.routes.market.cache', autospec=True)
    return cache_mock

@pytest.fixture
def mock_market_analysis(mocker):
    mocker.patch('backend.utils.market_analysis.get_market_trends', return_value={
        'median_prices': [
            {'date': '2024-01-01', 'value': 100000},
            {'date': '2024-01-02', 'value': 110000}
        ]
    })
    mocker.patch('backend.utils.market_analysis.get_price_distribution', return_value={
        'bins': [
            {'minPrice': 0, 'maxPrice': 100000, 'count': 10},
            {'minPrice': 100000, 'maxPrice': 200000, 'count': 20}
        ],
        'mean': 150000,
        'median': 160000,
        'standardDeviation': 50000
    })

def test_get_market_updates_fresh_data(mock_cache, mock_market_analysis):
    # Mock cache miss
    mock_cache.get.return_value = None
    
    response = client.get('/api/market/updates?timeframe=6M')
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert 'trends' in data
    assert 'distribution' in data
    assert 'timestamp' in data
    assert 'version' in data
    
    # Check trends data
    assert len(data['trends']['median_prices']) == 2
    assert data['trends']['median_prices'][0]['value'] == 100000
    
    # Check distribution data
    assert len(data['distribution']['bins']) == 2
    assert data['distribution']['mean'] == 150000
    
    # Check ETag header
    assert 'etag' in response.headers
    
    # Verify cache was set
    mock_cache.set.assert_called_once()

def test_get_market_updates_cached_data(mock_cache, mock_market_analysis):
    # Mock cached data
    cached_data = {
        'trends': {'median_prices': []},
        'distribution': {'bins': []},
        'timestamp': datetime.now().isoformat(),
        'version': 'test-version'
    }
    mock_cache.get.return_value = cached_data
    
    response = client.get('/api/market/updates?timeframe=6M')
    
    assert response.status_code == 200
    assert response.json() == cached_data
    
    # Verify market analysis functions were not called
    assert not mock_market_analysis.called

def test_get_market_updates_not_modified(mock_cache, mock_market_analysis):
    # Mock cached data
    cached_data = {
        'trends': {'median_prices': []},
        'distribution': {'bins': []},
        'timestamp': datetime.now().isoformat(),
        'version': 'test-version'
    }
    mock_cache.get.return_value = cached_data
    
    # Send request with matching ETag
    response = client.get(
        '/api/market/updates?timeframe=6M',
        headers={'If-None-Match': 'test-version'}
    )
    
    assert response.status_code == 304

def test_get_market_updates_error_handling(mock_cache, mock_market_analysis):
    # Mock cache error
    mock_cache.get.side_effect = Exception('Cache error')
    
    response = client.get('/api/market/updates?timeframe=6M')
    
    assert response.status_code == 500
    assert 'error' in response.json()['detail'].lower()

def test_get_market_updates_invalid_timeframe(mock_cache, mock_market_analysis):
    response = client.get('/api/market/updates?timeframe=invalid')
    
    assert response.status_code == 200  # Falls back to default (6M)
    data = response.json()
    assert 'trends' in data
    assert 'distribution' in data 