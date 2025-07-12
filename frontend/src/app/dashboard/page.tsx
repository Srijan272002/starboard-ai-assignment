'use client';

import React, { useState } from 'react';
import MainLayout from '../../components/layout/MainLayout';
import Card from '../../components/ui/Card';
import Select from '../../components/ui/Select';
import PropertyMap from '../../components/maps/PropertyMap';
import PriceHistoryChart from '../../components/charts/PriceHistoryChart';
import ComparisonChart from '../../components/charts/ComparisonChart';
import PropertyTable from '../../components/tables/PropertyTable';
import { Property } from '../../components/properties/PropertyCard';

// Mock data for demonstration
const mockProperties: Property[] = [
  {
    id: '1',
    address: '123 Main St',
    city: 'Chicago',
    state: 'IL',
    zipCode: '60601',
    price: 450000,
    bedrooms: 3,
    bathrooms: 2,
    squareFeet: 1800,
    propertyType: 'Residential',
    yearBuilt: 2005,
    county: 'cook',
  },
  {
    id: '2',
    address: '456 Oak Ave',
    city: 'Chicago',
    state: 'IL',
    zipCode: '60602',
    price: 550000,
    bedrooms: 4,
    bathrooms: 3,
    squareFeet: 2200,
    propertyType: 'Residential',
    yearBuilt: 2010,
    county: 'cook',
  },
  {
    id: '3',
    address: '789 Pine Blvd',
    city: 'Dallas',
    state: 'TX',
    zipCode: '75201',
    price: 650000,
    bedrooms: 4,
    bathrooms: 3.5,
    squareFeet: 2800,
    propertyType: 'Residential',
    yearBuilt: 2015,
    county: 'dallas',
  },
  {
    id: '4',
    address: '101 Cedar St',
    city: 'Los Angeles',
    state: 'CA',
    zipCode: '90001',
    price: 850000,
    bedrooms: 5,
    bathrooms: 4,
    squareFeet: 3200,
    propertyType: 'Residential',
    yearBuilt: 2018,
    county: 'la',
  },
  {
    id: '5',
    address: '202 Commercial Plaza',
    city: 'Chicago',
    state: 'IL',
    zipCode: '60603',
    price: 1200000,
    propertyType: 'Commercial',
    squareFeet: 5000,
    yearBuilt: 2000,
    county: 'cook',
  },
  {
    id: '6',
    address: '303 Industrial Park',
    city: 'Dallas',
    state: 'TX',
    zipCode: '75202',
    price: 1500000,
    propertyType: 'Industrial',
    squareFeet: 8000,
    yearBuilt: 1995,
    county: 'dallas',
  },
];

const countyOptions = [
  { value: 'all', label: 'All Counties' },
  { value: 'cook', label: 'Cook County' },
  { value: 'dallas', label: 'Dallas County' },
  { value: 'la', label: 'LA County' },
];

const propertyTypeOptions = [
  { value: 'all', label: 'All Types' },
  { value: 'residential', label: 'Residential' },
  { value: 'commercial', label: 'Commercial' },
  { value: 'industrial', label: 'Industrial' },
];

export default function DashboardPage() {
  const [selectedCounty, setSelectedCounty] = useState('all');
  const [selectedPropertyType, setSelectedPropertyType] = useState('all');
  const [filteredProperties, setFilteredProperties] = useState(mockProperties);

  // Filter properties based on selections
  React.useEffect(() => {
    let filtered = [...mockProperties];
    
    if (selectedCounty !== 'all') {
      filtered = filtered.filter(p => p.county === selectedCounty);
    }
    
    if (selectedPropertyType !== 'all') {
      filtered = filtered.filter(p => p.propertyType.toLowerCase() === selectedPropertyType);
    }
    
    setFilteredProperties(filtered);
  }, [selectedCounty, selectedPropertyType]);

  // Calculate statistics
  const stats = {
    totalProperties: filteredProperties.length,
    averagePrice: filteredProperties.length > 0 
      ? Math.round(filteredProperties.reduce((sum, p) => sum + p.price, 0) / filteredProperties.length) 
      : 0,
    averageSquareFeet: filteredProperties.length > 0 
      ? Math.round(filteredProperties.reduce((sum, p) => sum + (p.squareFeet || 0), 0) / filteredProperties.length) 
      : 0,
    newestProperty: filteredProperties.length > 0 
      ? Math.max(...filteredProperties.map(p => p.yearBuilt || 0)) 
      : 0,
  };

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(price);
  };

  return (
    <MainLayout>
      <div className="space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold mb-2">Property Dashboard</h1>
          <p className="text-gray-600">
            View and analyze property data across multiple counties
          </p>
        </div>

        {/* Filters */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Select
            id="county"
            name="county"
            label="County"
            options={countyOptions}
            value={selectedCounty}
            onChange={(e) => setSelectedCounty(e.target.value)}
          />
          <Select
            id="propertyType"
            name="propertyType"
            label="Property Type"
            options={propertyTypeOptions}
            value={selectedPropertyType}
            onChange={(e) => setSelectedPropertyType(e.target.value)}
          />
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Total Properties</h3>
            <p className="text-3xl font-bold">{stats.totalProperties}</p>
          </Card>
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Average Price</h3>
            <p className="text-3xl font-bold text-blue-600">{formatPrice(stats.averagePrice)}</p>
          </Card>
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Average Square Feet</h3>
            <p className="text-3xl font-bold">{stats.averageSquareFeet.toLocaleString()}</p>
          </Card>
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Newest Property</h3>
            <p className="text-3xl font-bold">{stats.newestProperty || 'N/A'}</p>
          </Card>
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div>
            <h2 className="text-2xl font-bold mb-4">Property Price Comparison</h2>
            <ComparisonChart properties={filteredProperties} />
          </div>
          <div>
            <h2 className="text-2xl font-bold mb-4">Price History Trends</h2>
            <PriceHistoryChart propertyId="market" title="Market Trends" />
          </div>
        </div>

        {/* Map */}
        <div>
          <h2 className="text-2xl font-bold mb-4">Property Map</h2>
          <PropertyMap properties={filteredProperties} height="400px" />
        </div>

        {/* Property Table */}
        <div>
          <h2 className="text-2xl font-bold mb-4">Property Listings</h2>
          <PropertyTable properties={filteredProperties} />
        </div>
      </div>
    </MainLayout>
  );
} 