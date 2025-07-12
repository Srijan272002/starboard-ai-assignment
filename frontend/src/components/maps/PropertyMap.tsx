'use client';

import React from 'react';
import dynamic from 'next/dynamic';
import { Property } from '../properties/PropertyCard';
import type { MapContainerProps } from 'react-leaflet';
import type { LatLngExpression } from 'leaflet';
import type { MapComponentProps } from '.';

// Import type for MapComponent
const MapComponent = dynamic<MapComponentProps>(
  () => import('./MapComponent'),
  { 
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center w-full h-full bg-gray-100 rounded-lg">
        <p className="text-gray-500">Loading map...</p>
      </div>
    )
  }
);

export const PropertyMap = (props: MapComponentProps) => {
  return <MapComponent {...props} />;
};

export default PropertyMap; 