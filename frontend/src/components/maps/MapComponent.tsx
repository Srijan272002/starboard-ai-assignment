'use client';

import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import type { Property } from '../properties/PropertyCard';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

export interface MapComponentProps {
  properties: Property[];
  height?: string;
  className?: string;
  center?: [number, number];
  zoom?: number;
}

const MapComponent = ({
  properties,
  height = '500px',
  className = '',
  center = [41.8781, -87.6298], // Default to Chicago
  zoom = 10,
}: MapComponentProps) => {
  useEffect(() => {
    // Fix for Leaflet marker icon issue in Next.js
    const L = require('leaflet');
    delete (L.Icon.Default.prototype as any)._getIconUrl;
    
    L.Icon.Default.mergeOptions({
      iconRetinaUrl: '/leaflet/marker-icon-2x.png',
      iconUrl: '/leaflet/marker-icon.png',
      shadowUrl: '/leaflet/marker-shadow.png',
    });
  }, []);

  return (
    <div className={className} style={{ height }}>
      <MapContainer
        center={center}
        zoom={zoom}
        style={{ height: '100%', width: '100%' }}
        scrollWheelZoom={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {properties.map((property) => {
          // For this example, we're generating random coordinates near the center
          // In a real app, you'd use actual coordinates from your property data
          const lat = center[0] + (Math.random() - 0.5) * 0.1;
          const lng = center[1] + (Math.random() - 0.5) * 0.1;
          
          return (
            <Marker key={property.id} position={[lat, lng]}>
              <Popup>
                <div className="text-sm">
                  <p className="font-medium">{property.address}</p>
                  <p>{property.city}, {property.state} {property.zipCode}</p>
                  <p className="font-semibold text-blue-600">
                    {new Intl.NumberFormat('en-US', {
                      style: 'currency',
                      currency: 'USD',
                      maximumFractionDigits: 0,
                    }).format(property.price)}
                  </p>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
};

export default MapComponent; 