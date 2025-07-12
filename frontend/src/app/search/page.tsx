'use client';

import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import MainLayout from '../../components/layout/MainLayout';
import SearchForm from '../../components/search/SearchForm';
import FilterPanel from '../../components/filters/FilterPanel';
import PropertyList from '../../components/properties/PropertyList';
import PropertyTable from '../../components/tables/PropertyTable';
import PropertyMap from '../../components/maps/PropertyMap';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import { Property } from '../../components/properties/PropertyCard';
import { apiService, PropertySearchParams } from '../../lib/api';

// This will be removed as we're now using real API data

enum ViewMode {
  GRID = 'grid',
  TABLE = 'table',
  MAP = 'map',
}

export default function SearchPage() {
  const searchParams = useSearchParams();
  const [viewMode, setViewMode] = useState<ViewMode>(ViewMode.GRID);
  const [loading, setLoading] = useState(false);
  const [properties, setProperties] = useState<Property[]>([]);
  const [filteredProperties, setFilteredProperties] = useState<Property[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [totalProperties, setTotalProperties] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [limit] = useState(20);



  // Load properties from API based on URL search params
  useEffect(() => {
    const loadProperties = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const county = searchParams.get('county') || 'cook'; // Default to cook county if none specified
        const propertyType = searchParams.get('propertyType');
        const address = searchParams.get('address');
        const minPrice = searchParams.get('minPrice');
        const maxPrice = searchParams.get('maxPrice');

        const searchParamsObj: PropertySearchParams = {
          county: county, // Always include county parameter
          page: currentPage,
          limit: limit,
        };

        if (propertyType) searchParamsObj.property_type = propertyType;
        if (address) searchParamsObj.address = address;
        if (minPrice) searchParamsObj.min_price = parseInt(minPrice);
        if (maxPrice) searchParamsObj.max_price = parseInt(maxPrice);

        const response = await apiService.searchProperties(searchParamsObj);
        
        // Check if we got a valid response with properties
        if (response && Array.isArray(response.properties)) {
          setProperties(response.properties);
          setFilteredProperties(response.properties);
          setTotalProperties(response.total || 0);
        } else {
          // Handle empty or malformed response
          setProperties([]);
          setFilteredProperties([]);
          setTotalProperties(0);
          setError("No properties found or invalid response format. The API may be unavailable or misconfigured.");
        }
      } catch (err: any) {
        console.error('Error searching properties:', err);
        
        // Provide more specific error messages based on common issues
        if (err.message && err.message.includes('404')) {
          setError(`No properties found. The county API endpoint may not be available.`);
        } else if (err.message && err.message.includes('401')) {
          setError(`Authentication failed. API key is missing or invalid. Please configure valid API keys in the backend.`);
        } else if (err.message && err.message.includes('403')) {
          setError(`Access denied. Check API permissions and ensure your API key has the necessary access rights.`);
        } else if (err.message && err.message.includes('API key')) {
          setError(`API key configuration error. Please add valid API keys in the backend .env file.`);
        } else if (err.message && err.message.includes('Real API')) {
          setError(`Real API access is required but failed. Please check your API key configuration or set ALLOW_MOCK_DATA=true in development.`);
        } else {
          setError(`Failed to load properties: ${err.message || 'Unknown error'}`);
        }
        
        setProperties([]);
        setFilteredProperties([]);
      } finally {
        setLoading(false);
      }
    };

    loadProperties();
  }, [searchParams, currentPage, limit]);

  const handleSearch = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const county = searchParams.get('county') || 'cook'; // Default to cook county
      const response = await apiService.searchProperties({
        county: county,
        page: 1,
        limit: limit,
      });
      
      if (response && Array.isArray(response.properties)) {
        setProperties(response.properties);
        setFilteredProperties(response.properties);
        setTotalProperties(response.total || 0);
        setCurrentPage(1);
      } else {
        setProperties([]);
        setFilteredProperties([]);
        setTotalProperties(0);
        setError("No properties found or invalid response format. The API may be unavailable or misconfigured.");
      }
    } catch (err: any) {
      console.error('Failed to search properties:', err);
      
      // Provide more specific error messages based on common issues
      if (err.message && err.message.includes('404')) {
        setError(`No properties found. The county API endpoint may not be available.`);
      } else if (err.message && err.message.includes('401')) {
        setError(`Authentication failed. API key is missing or invalid. Please configure valid API keys in the backend.`);
      } else if (err.message && err.message.includes('403')) {
        setError(`Access denied. Check API permissions and ensure your API key has the necessary access rights.`);
      } else if (err.message && err.message.includes('API key')) {
        setError(`API key configuration error. Please add valid API keys in the backend .env file.`);
      } else if (err.message && err.message.includes('Real API')) {
        setError(`Real API access is required but failed. Please check your API key configuration or set ALLOW_MOCK_DATA=true in development.`);
      } else {
        setError(`Failed to search properties: ${err.message || 'Unknown error'}`);
      }
      
      setProperties([]);
      setFilteredProperties([]);
    } finally {
      setLoading(false);
    }
  };

  const handleApplyFilters = async (filters: any) => {
    setLoading(true);
    setError(null);
    
    try {
      const county = searchParams.get('county') || 'cook'; // Default to cook county
      const searchParamsObj: PropertySearchParams = {
        county: county,
        page: 1,
        limit: limit,
      };

      if (filters.propertyType) {
        searchParamsObj.property_type = filters.propertyType;
      }
      
      if (filters.priceRange?.min) {
        searchParamsObj.min_price = parseInt(filters.priceRange.min);
      }
      
      if (filters.priceRange?.max) {
        searchParamsObj.max_price = parseInt(filters.priceRange.max);
      }
      
      if (filters.squareFeet?.min) {
        searchParamsObj.min_sqft = parseInt(filters.squareFeet.min);
      }
      
      if (filters.squareFeet?.max) {
        searchParamsObj.max_sqft = parseInt(filters.squareFeet.max);
      }

      const response = await apiService.searchProperties(searchParamsObj);
      
      if (response && Array.isArray(response.properties)) {
        setProperties(response.properties);
        setFilteredProperties(response.properties);
        setTotalProperties(response.total || 0);
        setCurrentPage(1);
      } else {
        setProperties([]);
        setFilteredProperties([]);
        setTotalProperties(0);
        setError("No properties found or invalid response format. The API may be unavailable or misconfigured.");
      }
    } catch (err: any) {
      console.error('Failed to apply filters:', err);
      
      // Provide more specific error messages based on common issues
      if (err.message && err.message.includes('404')) {
        setError(`No properties found. The county API endpoint may not be available.`);
      } else if (err.message && err.message.includes('401')) {
        setError(`Authentication failed. API key is missing or invalid. Please configure valid API keys in the backend.`);
      } else if (err.message && err.message.includes('403')) {
        setError(`Access denied. Check API permissions and ensure your API key has the necessary access rights.`);
      } else if (err.message && err.message.includes('API key')) {
        setError(`API key configuration error. Please add valid API keys in the backend .env file.`);
      } else if (err.message && err.message.includes('Real API')) {
        setError(`Real API access is required but failed. Please check your API key configuration or set ALLOW_MOCK_DATA=true in development.`);
      } else {
        setError(`Failed to apply filters: ${err.message || 'Unknown error'}`);
      }
      
      setProperties([]);
      setFilteredProperties([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <MainLayout>
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold mb-6">Search Properties</h1>
          <Card className="p-6">
            <SearchForm onSearch={handleSearch} />
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Filters */}
          <div className="lg:col-span-1">
            <FilterPanel onApplyFilters={handleApplyFilters} />
          </div>

          {/* Results */}
          <div className="lg:col-span-3 space-y-4">
            {error && (
              <Card className="p-4 bg-red-50 border-red-200">
                <p className="text-red-600">{error}</p>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="mt-2"
                  onClick={() => window.location.reload()}
                >
                  Retry
                </Button>
              </Card>
            )}
            
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-semibold">
                {loading ? 'Loading...' : `${filteredProperties.length} Properties Found`}
              </h2>
              <div className="flex space-x-2">
                <Button 
                  variant={viewMode === ViewMode.GRID ? 'primary' : 'outline'} 
                  size="sm" 
                  onClick={() => setViewMode(ViewMode.GRID)}
                >
                  Grid
                </Button>
                <Button 
                  variant={viewMode === ViewMode.TABLE ? 'primary' : 'outline'} 
                  size="sm" 
                  onClick={() => setViewMode(ViewMode.TABLE)}
                >
                  Table
                </Button>
                <Button 
                  variant={viewMode === ViewMode.MAP ? 'primary' : 'outline'} 
                  size="sm" 
                  onClick={() => setViewMode(ViewMode.MAP)}
                >
                  Map
                </Button>
              </div>
            </div>

            {viewMode === ViewMode.GRID && (
              <PropertyList 
                properties={filteredProperties} 
                loading={loading} 
              />
            )}

            {viewMode === ViewMode.TABLE && (
              <PropertyTable 
                properties={filteredProperties} 
                loading={loading} 
              />
            )}

            {viewMode === ViewMode.MAP && (
              <PropertyMap 
                properties={filteredProperties} 
                height="600px" 
              />
            )}
          </div>
        </div>
      </div>
    </MainLayout>
  );
} 