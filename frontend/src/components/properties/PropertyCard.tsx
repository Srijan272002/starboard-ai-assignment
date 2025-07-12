import React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import Card from '../ui/Card';
import Badge from '../ui/Badge';

export interface Property {
  id: string;
  address: string;
  city: string;
  state: string;
  zipCode: string;
  price: number;
  bedrooms?: number;
  bathrooms?: number;
  squareFeet?: number;
  propertyType: string;
  yearBuilt?: number;
  imageUrl?: string;
  county: string;
}

interface PropertyCardProps {
  property: Property;
  className?: string;
}

export const PropertyCard = ({ property, className = '' }: PropertyCardProps) => {
  const formattedPrice = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(property.price);

  return (
    <Card 
      className={`overflow-hidden transition-transform hover:scale-[1.02] hover:shadow-md ${className}`}
      hoverable
    >
      <div className="-mx-6 -mt-4 mb-4 h-48 relative">
        {property.imageUrl ? (
          <Image
            src={property.imageUrl}
            alt={property.address}
            fill
            className="object-cover"
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            priority={false}
            loading="lazy"
            quality={75}
          />
        ) : (
          <div className="w-full h-full bg-gray-200 flex items-center justify-center">
            <span className="text-gray-600">No image available</span>
          </div>
        )}
        <Badge 
          variant="info" 
          className="absolute top-2 left-2"
        >
          {property.propertyType}
        </Badge>
      </div>
      
      <h3 className="text-lg font-medium text-gray-900 truncate">
        {property.address}
      </h3>
      <p className="text-gray-700">
        {property.city}, {property.state} {property.zipCode}
      </p>
      <p className="text-xl font-semibold text-blue-700">
        {formattedPrice}
      </p>
      
      <div className="flex items-center justify-between text-sm text-gray-700">
        {property.bedrooms && (
          <div className="flex items-center">
            <span className="font-medium">{property.bedrooms}</span>
            <span className="ml-1">Beds</span>
          </div>
        )}
        {property.bathrooms && (
          <div className="flex items-center">
            <span className="font-medium">{property.bathrooms}</span>
            <span className="ml-1">Baths</span>
          </div>
        )}
        {property.squareFeet && (
          <div className="flex items-center">
            <span className="font-medium">{property.squareFeet.toLocaleString()}</span>
            <span className="ml-1">Sq Ft</span>
          </div>
        )}
      </div>
      
      <div className="pt-4">
        <Link 
          href={`/properties/${property.county}/${property.id}`}
          className="text-blue-700 hover:text-blue-900 font-medium"
        >
          View Details
        </Link>
      </div>
    </Card>
  );
};

export default PropertyCard; 