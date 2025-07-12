'use client';

import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import MainLayout from '../../components/layout/MainLayout';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import PropertyCard, { Property } from '../../components/properties/PropertyCard';
import ComparisonChart from '../../components/charts/ComparisonChart';
import PropertyMap from '../../components/maps/PropertyMap';

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

export default function ComparePage() {
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [properties, setProperties] = useState<Property[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // In a real app, this would fetch data from an API
    setLoading(true);
    setTimeout(() => {
      const ids = searchParams.get('ids')?.split(',') || [];
      
      if (ids.length === 0) {
        setProperties([]);
        setError('No properties selected for comparison');
        setLoading(false);
        return;
      }
      
      const foundProperties = mockProperties.filter(p => ids.includes(p.id));
      
      if (foundProperties.length === 0) {
        setError('No matching properties found');
      } else {
        setProperties(foundProperties);
        setError(null);
      }
      
      setLoading(false);
    }, 500);
  }, [searchParams]);

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(price);
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="h-64 bg-gray-200 rounded"></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="h-40 bg-gray-200 rounded"></div>
            <div className="h-40 bg-gray-200 rounded"></div>
          </div>
        </div>
      </MainLayout>
    );
  }

  if (error && properties.length === 0) {
    return (
      <MainLayout>
        <Card className="p-8 text-center">
          <h2 className="text-2xl font-bold text-red-600 mb-4">Error</h2>
          <p className="text-gray-600 mb-6">{error}</p>
          <Link href="/search">
            <Button>Search Properties</Button>
          </Link>
        </Card>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold mb-2">Compare Properties</h1>
          <p className="text-gray-600">
            {properties.length === 1 
              ? 'Add more properties to compare' 
              : `Comparing ${properties.length} properties`}
          </p>
        </div>

        {/* Property Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {properties.map(property => (
            <div key={property.id} className="relative">
              <PropertyCard property={property} />
              <button 
                className="absolute top-2 right-2 bg-red-600 text-white rounded-full w-6 h-6 flex items-center justify-center hover:bg-red-700"
                onClick={() => {
                  const newProperties = properties.filter(p => p.id !== property.id);
                  setProperties(newProperties);
                  
                  // Update URL
                  const newIds = newProperties.map(p => p.id).join(',');
                  const url = newIds ? `/compare?ids=${newIds}` : '/compare';
                  window.history.pushState({}, '', url);
                }}
              >
                ×
              </button>
            </div>
          ))}
          
          {/* Add Property Card */}
          {properties.length < 3 && (
            <Link href="/search" className="block">
              <Card className="h-full flex items-center justify-center p-6 border-dashed">
                <div className="text-center">
                  <div className="text-5xl text-gray-300 mb-2">+</div>
                  <p className="text-gray-500">Add Property</p>
                </div>
              </Card>
            </Link>
          )}
        </div>

        {properties.length > 1 && (
          <>
            {/* Comparison Chart */}
            <div>
              <h2 className="text-2xl font-bold mb-4">Price Comparison</h2>
              <ComparisonChart properties={properties} />
            </div>

            {/* Comparison Table */}
            <div>
              <h2 className="text-2xl font-bold mb-4">Property Comparison</h2>
              <Card className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Feature
                      </th>
                      {properties.map(property => (
                        <th key={property.id} scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          {property.address.split(',')[0]}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    <tr>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        Price
                      </td>
                      {properties.map(property => (
                        <td key={property.id} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {formatPrice(property.price)}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        Property Type
                      </td>
                      {properties.map(property => (
                        <td key={property.id} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {property.propertyType}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        Bedrooms
                      </td>
                      {properties.map(property => (
                        <td key={property.id} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {property.bedrooms || '-'}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        Bathrooms
                      </td>
                      {properties.map(property => (
                        <td key={property.id} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {property.bathrooms || '-'}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        Square Feet
                      </td>
                      {properties.map(property => (
                        <td key={property.id} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {property.squareFeet ? property.squareFeet.toLocaleString() : '-'}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        Year Built
                      </td>
                      {properties.map(property => (
                        <td key={property.id} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {property.yearBuilt || '-'}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        Location
                      </td>
                      {properties.map(property => (
                        <td key={property.id} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {property.city}, {property.state}
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        County
                      </td>
                      {properties.map(property => (
                        <td key={property.id} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {property.county.charAt(0).toUpperCase() + property.county.slice(1)} County
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </Card>
            </div>

            {/* Map */}
            <div>
              <h2 className="text-2xl font-bold mb-4">Property Locations</h2>
              <PropertyMap properties={properties} height="400px" />
            </div>
          </>
        )}
      </div>
    </MainLayout>
  );
} 