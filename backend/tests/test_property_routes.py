import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import json
from backend.main import app
from backend.utils.cache import Cache
from backend.models.property import Property

client = TestClient(app)

@pytest.fixture
def mock_cache(mocker):
    cache_mock = mocker.patch('backend.routes.properties.cache', autospec=True)
    return cache_mock

@pytest.fixture
def mock_db_session(mocker):
    # Mock SQLAlchemy session and query results
    session_mock = mocker.MagicMock()
    
    # Mock property data
    mock_properties = [
        Property(
            id='prop1',
            propertyType='industrial',
            address={
                'street': '123 Test St',
                'city': 'Test City',
                'state': 'TS',
                'zipCode': '12345'
            },
            location={
                'latitude': 41.8781,
                'longitude': -87.6298
            },
            financials={
                'price': 1000000,
                'taxes': 10000,
                'insurance': 5000
            },
            metrics={
                'totalSquareFeet': 50000,
                'yearBuilt': 2000,
                'lotSize': 100000
            },
            updatedAt=datetime.now().isoformat()
        ),
        Property(
            id='prop2',
            propertyType='warehouse',
            address={
                'street': '456 Test Ave',
                'city': 'Test City',
                'state': 'TS',
                'zipCode': '12345'
            },
            location={
                'latitude': 41.8782,
                'longitude': -87.6299
            },
            financials={
                'price': 2000000,
                'taxes': 20000,
                'insurance': 10000
            },
            metrics={
                'totalSquareFeet': 100000,
                'yearBuilt': 2010,
                'lotSize': 200000
            },
            updatedAt=datetime.now().isoformat()
        )
    ]
    
    # Mock query execution
    result_mock = mocker.MagicMock()
    result_mock.scalars.return_value.all.return_value = mock_properties
    session_mock.execute.return_value = result_mock
    
    # Mock session context manager
    mocker.patch('backend.routes.properties.get_db_session', return_value=session_mock)
    
    return session_mock

def test_get_property_updates_fresh_data(mock_cache, mock_db_session):
    # Mock cache miss
    mock_cache.get.return_value = None
    
    response = client.get('/api/properties/updates')
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert 'properties' in data
    assert 'timestamp' in data
    assert 'total' in data
    assert 'limit' in data
    assert 'offset' in data
    assert 'version' in data
    
    # Check properties data
    assert len(data['properties']) == 2
    assert data['properties'][0]['id'] == 'prop1'
    assert data['properties'][1]['id'] == 'prop2'
    
    # Check ETag header
    assert 'etag' in response.headers
    
    # Verify cache was set
    mock_cache.set.assert_called_once()

def test_get_property_updates_cached_data(mock_cache, mock_db_session):
    # Mock cached data
    cached_data = {
        'properties': [],
        'timestamp': datetime.now().isoformat(),
        'total': 0,
        'limit': 100,
        'offset': 0,
        'version': 'test-version'
    }
    mock_cache.get.return_value = cached_data
    
    response = client.get('/api/properties/updates')
    
    assert response.status_code == 200
    assert response.json() == cached_data
    
    # Verify DB was not queried
    assert not mock_db_session.execute.called

def test_get_property_updates_not_modified(mock_cache, mock_db_session):
    # Mock cached data
    cached_data = {
        'properties': [],
        'timestamp': datetime.now().isoformat(),
        'total': 0,
        'limit': 100,
        'offset': 0,
        'version': 'test-version'
    }
    mock_cache.get.return_value = cached_data
    
    # Send request with matching ETag
    response = client.get(
        '/api/properties/updates',
        headers={'If-None-Match': 'test-version'}
    )
    
    assert response.status_code == 304

def test_get_property_updates_with_last_update(mock_cache, mock_db_session):
    # Mock cache miss
    mock_cache.get.return_value = None
    
    # Request with last_update parameter
    last_update = datetime.now().isoformat()
    response = client.get(f'/api/properties/updates?last_update={last_update}')
    
    assert response.status_code == 200
    
    # Verify query included last_update filter
    query_args = mock_db_session.execute.call_args[0][0]
    assert 'Property.updated_at >' in str(query_args)

def test_get_property_updates_invalid_last_update(mock_cache, mock_db_session):
    response = client.get('/api/properties/updates?last_update=invalid-date')
    
    assert response.status_code == 400
    assert 'invalid' in response.json()['detail'].lower()

def test_get_property_by_id_fresh_data(mock_cache, mock_db_session):
    # Mock cache miss
    mock_cache.get.return_value = None
    
    # Mock single property query
    property = Property(
        id='prop1',
        propertyType='industrial',
        address={
            'street': '123 Test St',
            'city': 'Test City',
            'state': 'TS',
            'zipCode': '12345'
        },
        location={
            'latitude': 41.8781,
            'longitude': -87.6298
        },
        financials={
            'price': 1000000,
            'taxes': 10000,
            'insurance': 5000
        },
        metrics={
            'totalSquareFeet': 50000,
            'yearBuilt': 2000,
            'lotSize': 100000
        },
        updatedAt=datetime.now().isoformat()
    )
    result_mock = mock_db_session.execute.return_value
    result_mock.scalar_one_or_none.return_value = property
    
    response = client.get('/api/properties/prop1')
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert 'property' in data
    assert 'timestamp' in data
    assert 'version' in data
    
    # Check property data
    assert data['property']['id'] == 'prop1'
    
    # Check ETag header
    assert 'etag' in response.headers
    
    # Verify cache was set
    mock_cache.set.assert_called_once()

def test_get_property_by_id_not_found(mock_cache, mock_db_session):
    # Mock property not found
    result_mock = mock_db_session.execute.return_value
    result_mock.scalar_one_or_none.return_value = None
    
    response = client.get('/api/properties/nonexistent')
    
    assert response.status_code == 404
    assert 'not found' in response.json()['detail'].lower() 