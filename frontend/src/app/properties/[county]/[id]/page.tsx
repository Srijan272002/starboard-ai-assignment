'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';
import MainLayout from '../../../../components/layout/MainLayout';
import Card from '../../../../components/ui/Card';
import Badge from '../../../../components/ui/Badge';
import Button from '../../../../components/ui/Button';
import PropertyMap from '../../../../components/maps/PropertyMap';
import PriceHistoryChart from '../../../../components/charts/PriceHistoryChart';
import { Property } from '../../../../components/properties/PropertyCard';
import { apiService } from '../../../../lib/api';

export default function PropertyDetailPage() {
  const params = useParams();
  const [property, setProperty] = useState<Property | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadProperty = async () => {
      if (!params.id || typeof params.id !== 'string' || !params.county || typeof params.county !== 'string') {
        setError('Invalid property ID or county');
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);
      
      try {
        const propertyData = await apiService.getProperty(params.id, params.county);
        setProperty(propertyData);
      } catch (err) {
        console.error('Failed to load property:', err);
        setError('Property not found');
      } finally {
        setLoading(false);
      }
    };

    loadProperty();
  }, [params.id, params.county]);

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

  if (error || !property) {
    return (
      <MainLayout>
        <Card className="p-8 text-center">
          <h2 className="text-2xl font-bold text-red-600 mb-4">Error</h2>
          <p className="text-gray-600 mb-6">{error || 'An error occurred'}</p>
          <Link href="/search">
            <Button>Back to Search</Button>
          </Link>
        </Card>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-8">
        {/* Breadcrumb */}
        <div className="text-sm text-gray-500">
          <Link href="/" className="hover:text-blue-600">Home</Link>
          <span className="mx-2">/</span>
          <Link href="/search" className="hover:text-blue-600">Search</Link>
          <span className="mx-2">/</span>
          <span className="text-gray-700">Property Details</span>
        </div>

        {/* Property Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-bold mb-1">{property.address}</h1>
            <p className="text-xl text-gray-600">
              {property.city}, {property.state} {property.zipCode}
            </p>
          </div>
          <div className="mt-4 md:mt-0">
            <p className="text-3xl font-bold text-blue-600">{formatPrice(property.price)}</p>
          </div>
        </div>

        {/* Property Image and Map */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <Card className="overflow-hidden">
            <div className="h-80 relative">
              {property.imageUrl ? (
                <Image
                  src={property.imageUrl}
                  alt={property.address}
                  fill
                  className="object-cover"
                />
              ) : (
                <div className="w-full h-full bg-gray-200 flex items-center justify-center">
                  <span className="text-gray-400">Property image not available</span>
                </div>
              )}
            </div>
          </Card>
          <PropertyMap properties={[property]} height="320px" />
        </div>

        {/* Property Details */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <Card className="lg:col-span-2 p-6">
            <h2 className="text-2xl font-bold mb-6">Property Details</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-y-6">
              <div>
                <p className="text-gray-500 text-sm">Property Type</p>
                <p className="font-medium">{property.propertyType}</p>
              </div>
              {property.bedrooms && (
                <div>
                  <p className="text-gray-500 text-sm">Bedrooms</p>
                  <p className="font-medium">{property.bedrooms}</p>
                </div>
              )}
              {property.bathrooms && (
                <div>
                  <p className="text-gray-500 text-sm">Bathrooms</p>
                  <p className="font-medium">{property.bathrooms}</p>
                </div>
              )}
              {property.squareFeet && (
                <div>
                  <p className="text-gray-500 text-sm">Square Feet</p>
                  <p className="font-medium">{property.squareFeet.toLocaleString()}</p>
                </div>
              )}
              {property.yearBuilt && (
                <div>
                  <p className="text-gray-500 text-sm">Year Built</p>
                  <p className="font-medium">{property.yearBuilt}</p>
                </div>
              )}
              <div>
                <p className="text-gray-500 text-sm">County</p>
                <p className="font-medium">{property.county.charAt(0).toUpperCase() + property.county.slice(1)} County</p>
              </div>
            </div>

            <div className="mt-8">
              <h3 className="text-xl font-bold mb-4">Description</h3>
              <p className="text-gray-600">
                This property at {property.address} is located in {property.city}, {property.state}. 
                It is a {property.propertyType.toLowerCase()} property
                {property.bedrooms && property.bathrooms ? ` with ${property.bedrooms} bedrooms and ${property.bathrooms} bathrooms` : ''}
                {property.squareFeet ? ` spanning ${property.squareFeet.toLocaleString()} square feet` : ''}
                {property.yearBuilt ? ` and was built in ${property.yearBuilt}` : ''}.
              </p>
            </div>
          </Card>

          <Card className="p-6">
            <h2 className="text-xl font-bold mb-4">Actions</h2>
            <div className="space-y-3">
              <Button fullWidth>Contact Agent</Button>
              <Button variant="outline" fullWidth>Schedule Viewing</Button>
              <Link href={`/compare?ids=${property.id}`}>
                <Button variant="outline" fullWidth>Compare Property</Button>
              </Link>
              <Button variant="outline" fullWidth>Share Property</Button>
            </div>
          </Card>
        </div>

        {/* Price History Chart */}
        <div>
          <h2 className="text-2xl font-bold mb-4">Price History</h2>
          <PriceHistoryChart propertyId={property.id} />
        </div>

        {/* Similar Properties */}
        <div>
          <h2 className="text-2xl font-bold mb-4">Similar Properties</h2>
          <p className="text-gray-600">
            Similar properties feature coming soon.
          </p>
        </div>
      </div>
    </MainLayout>
  );
} 