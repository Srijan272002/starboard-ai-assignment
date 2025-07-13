'use client'

import { useEffect, useRef, useState, useCallback } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { Property } from '@/lib/api/types';
import { usePropertyStore } from '@/lib/store/propertyStore';
import { configureMapbox, getDefaultMapboxOptions } from '@/lib/mapbox-config';
import { MapboxErrorBoundary } from './MapboxErrorBoundary';

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

// Configure Mapbox to prevent ad blocker issues
configureMapbox();

interface PropertyFilter {
  propertyType?: string;
  minPrice?: number;
  maxPrice?: number;
  minSize?: number;
  maxSize?: number;
}

// MOCK DATA for demo
const mockProperties = [
  {
    id: '1',
    updatedAt: new Date().toISOString(),
    severity: 'normal',
    address: { street: '123 Main St', city: 'Chicago', state: 'IL', zipCode: '60601' },
    propertyType: 'Warehouse',
    financials: { price: 500000, taxes: 5000, insurance: 1200 },
    metrics: { totalSquareFeet: 2000, yearBuilt: 1990, lotSize: 5000 },
    location: { latitude: 41.881832, longitude: -87.623177 },
  },
  {
    id: '2',
    updatedAt: new Date().toISOString(),
    severity: 'normal',
    address: { street: '456 Oak Ave', city: 'Chicago', state: 'IL', zipCode: '60602' },
    propertyType: 'Industrial',
    financials: { price: 750000, taxes: 8000, insurance: 1500 },
    metrics: { totalSquareFeet: 3500, yearBuilt: 1985, lotSize: 8000 },
    location: { latitude: 41.885, longitude: -87.62 },
  },
  {
    id: '3',
    updatedAt: new Date().toISOString(),
    severity: 'normal',
    address: { street: '789 Pine Rd', city: 'Chicago', state: 'IL', zipCode: '60603' },
    propertyType: 'Manufacturing',
    financials: { price: 900000, taxes: 10000, insurance: 2000 },
    metrics: { totalSquareFeet: 5000, yearBuilt: 2000, lotSize: 12000 },
    location: { latitude: 41.89, longitude: -87.63 },
  },
];

export default function PropertyMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const markers = useRef<mapboxgl.Marker[]>([]);
  const [selectedProperty, setSelectedProperty] = useState<Property | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<PropertyFilter>({});
  
  // Function to apply filters
  const filterProperties = (props: Property[] | null) => {
    if (!props || !Array.isArray(props)) return [];
    return props.filter(p => {
      if (filters.propertyType && p.propertyType !== filters.propertyType) return false;
      if (filters.minPrice && p.financials.price < filters.minPrice) return false;
      if (filters.maxPrice && p.financials.price > filters.maxPrice) return false;
      if (filters.minSize && p.metrics.totalSquareFeet < filters.minSize) return false;
      if (filters.maxSize && p.metrics.totalSquareFeet > filters.maxSize) return false;
      return true;
    });
  };

  // Initialize map
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    // Check for Mapbox token
    if (!MAPBOX_TOKEN) {
      setError('Mapbox access token is required. Please check your environment configuration.');
      return;
    }

    // Set the access token
    mapboxgl.accessToken = MAPBOX_TOKEN;

    try {
      map.current = new mapboxgl.Map({
        container: mapContainer.current,
        style: 'mapbox://styles/mapbox/light-v11',
        center: [-87.6298, 41.8781], // Chicago coordinates as default
        zoom: 10,
        ...getDefaultMapboxOptions()
      });

      // Add navigation controls
      map.current.addControl(new mapboxgl.NavigationControl(), 'top-right');

      // Handle map load error
      map.current.on('error', () => {
        setError('Failed to load map. Please try again later.');
      });

    } catch (err) {
      setError('An error occurred while initializing the map.');
    }

    // Cleanup
    return () => {
      if (map.current) {
        markers.current.forEach(marker => marker.remove());
        markers.current = [];
        map.current.remove();
        map.current = null;
      }
    };
  }, []);

  // Update markers when mockProperties or filters change
  useEffect(() => {
    if (!map.current) return;

    // Remove existing markers
    markers.current.forEach(marker => marker.remove());
    markers.current = [];

    // Filter properties
    const filteredProperties = filterProperties(mockProperties);

    // Add new markers
    filteredProperties.forEach(property => {
      const { latitude, longitude } = property.location;
      
      // Create marker element
      const el = document.createElement('div');
      el.className = 'marker';
      el.style.backgroundColor = 'steelblue';
      el.style.width = '20px';
      el.style.height = '20px';
      el.style.borderRadius = '50%';
      el.style.cursor = 'pointer';
      
      // Create popup
      const popup = new mapboxgl.Popup({ offset: 25 }).setHTML(`
        <div class="p-2">
          <h3 class="font-semibold">${property.address.street}</h3>
          <p class="text-sm">${property.propertyType}</p>
          <p class="text-sm">$${property.financials.price.toLocaleString()}</p>
        </div>
      `);
      
      // Create and add marker
      const marker = new mapboxgl.Marker(el)
        .setLngLat([longitude, latitude])
        .setPopup(popup)
        .addTo(map.current!);
      
      // Add click handler
      el.addEventListener('click', () => {
        setSelectedProperty(property);
      });
      
      // Store marker reference
      markers.current.push(marker);
    });

    // Fit bounds if we have markers
    if (markers.current.length > 0) {
      const bounds = new mapboxgl.LngLatBounds();
      filteredProperties.forEach(property => {
        bounds.extend([property.location.longitude, property.location.latitude]);
      });
      map.current.fitBounds(bounds, { padding: 50 });
    }

  }, [filters]);

  return (
    <MapboxErrorBoundary>
      <div className="relative h-[calc(100vh-4rem)]">
        <div ref={mapContainer} className="absolute inset-0" />
      
      {/* Error display */}
      {error && (
        <div className="absolute top-4 left-4 right-4 bg-destructive/90 text-destructive-foreground p-4 rounded-lg shadow-lg">
          <p>{error}</p>
        </div>
      )}
      
      {/* Selected property details */}
      {selectedProperty && (
        <div className="absolute bottom-4 left-4 bg-card p-4 rounded-lg shadow-lg max-w-md">
          <h3 className="font-semibold mb-2">{selectedProperty.address.street}</h3>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <p className="text-muted-foreground">Price</p>
              <p className="font-medium">${selectedProperty.financials.price.toLocaleString()}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Type</p>
              <p className="font-medium">{selectedProperty.propertyType}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Size</p>
              <p className="font-medium">{selectedProperty.metrics.totalSquareFeet.toLocaleString()} sqft</p>
            </div>
            <div>
              <p className="text-muted-foreground">Year Built</p>
              <p className="font-medium">{selectedProperty.metrics.yearBuilt}</p>
            </div>
          </div>
          <button
            onClick={() => setSelectedProperty(null)}
            className="mt-4 w-full px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
          >
            Close
          </button>
        </div>
      )}
      
      {/* Status indicator */}
      <div className="absolute bottom-4 right-4 bg-background/80 backdrop-blur-sm p-2 rounded-lg shadow text-xs">
        {/* Removed polling status indicator */}
      </div>
      </div>
    </MapboxErrorBoundary>
  );
} 