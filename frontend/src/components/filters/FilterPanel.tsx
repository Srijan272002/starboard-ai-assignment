'use client';

import React, { useState } from 'react';
import Button from '../ui/Button';
import Input from '../ui/Input';
import Select from '../ui/Select';
import Card from '../ui/Card';

interface FilterPanelProps {
  onApplyFilters: (filters: FilterOptions) => void;
  className?: string;
}

export interface FilterOptions {
  propertyType: string;
  priceRange: {
    min: string;
    max: string;
  };
  bedrooms: string;
  bathrooms: string;
  squareFeet: {
    min: string;
    max: string;
  };
  yearBuilt: {
    min: string;
    max: string;
  };
}

const propertyTypes = [
  { value: '', label: 'All Types' },
  { value: 'residential', label: 'Residential' },
  { value: 'commercial', label: 'Commercial' },
  { value: 'industrial', label: 'Industrial' },
  { value: 'land', label: 'Land' },
];

const bedroomOptions = [
  { value: '', label: 'Any' },
  { value: '1', label: '1+' },
  { value: '2', label: '2+' },
  { value: '3', label: '3+' },
  { value: '4', label: '4+' },
  { value: '5', label: '5+' },
];

const bathroomOptions = [
  { value: '', label: 'Any' },
  { value: '1', label: '1+' },
  { value: '2', label: '2+' },
  { value: '3', label: '3+' },
  { value: '4', label: '4+' },
];

export const FilterPanel = ({ onApplyFilters, className = '' }: FilterPanelProps) => {
  const [filters, setFilters] = useState<FilterOptions>({
    propertyType: '',
    priceRange: { min: '', max: '' },
    bedrooms: '',
    bathrooms: '',
    squareFeet: { min: '', max: '' },
    yearBuilt: { min: '', max: '' },
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    
    if (name.includes('.')) {
      const [parent, child] = name.split('.');
      
      if (parent === 'priceRange') {
        setFilters((prev) => ({
          ...prev,
          priceRange: {
            ...prev.priceRange,
            [child]: value,
          },
        }));
      } else if (parent === 'squareFeet') {
        setFilters((prev) => ({
          ...prev,
          squareFeet: {
            ...prev.squareFeet,
            [child]: value,
          },
        }));
      } else if (parent === 'yearBuilt') {
        setFilters((prev) => ({
          ...prev,
          yearBuilt: {
            ...prev.yearBuilt,
            [child]: value,
          },
        }));
      }
    } else {
      setFilters((prev) => ({
        ...prev,
        [name]: value,
      }));
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onApplyFilters(filters);
  };

  const handleReset = () => {
    setFilters({
      propertyType: '',
      priceRange: { min: '', max: '' },
      bedrooms: '',
      bathrooms: '',
      squareFeet: { min: '', max: '' },
      yearBuilt: { min: '', max: '' },
    });
    onApplyFilters({
      propertyType: '',
      priceRange: { min: '', max: '' },
      bedrooms: '',
      bathrooms: '',
      squareFeet: { min: '', max: '' },
      yearBuilt: { min: '', max: '' },
    });
  };

  return (
    <Card className={className}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Filter Properties</h3>
        
        <Select
          id="propertyType"
          name="propertyType"
          label="Property Type"
          options={propertyTypes}
          value={filters.propertyType}
          onChange={handleChange}
        />
        
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">Price Range</label>
          <div className="grid grid-cols-2 gap-2">
            <Input
              id="priceRange.min"
              name="priceRange.min"
              placeholder="Min"
              type="number"
              value={filters.priceRange.min}
              onChange={handleChange}
            />
            <Input
              id="priceRange.max"
              name="priceRange.max"
              placeholder="Max"
              type="number"
              value={filters.priceRange.max}
              onChange={handleChange}
            />
          </div>
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <Select
            id="bedrooms"
            name="bedrooms"
            label="Bedrooms"
            options={bedroomOptions}
            value={filters.bedrooms}
            onChange={handleChange}
          />
          <Select
            id="bathrooms"
            name="bathrooms"
            label="Bathrooms"
            options={bathroomOptions}
            value={filters.bathrooms}
            onChange={handleChange}
          />
        </div>
        
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">Square Feet</label>
          <div className="grid grid-cols-2 gap-2">
            <Input
              id="squareFeet.min"
              name="squareFeet.min"
              placeholder="Min"
              type="number"
              value={filters.squareFeet.min}
              onChange={handleChange}
            />
            <Input
              id="squareFeet.max"
              name="squareFeet.max"
              placeholder="Max"
              type="number"
              value={filters.squareFeet.max}
              onChange={handleChange}
            />
          </div>
        </div>
        
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">Year Built</label>
          <div className="grid grid-cols-2 gap-2">
            <Input
              id="yearBuilt.min"
              name="yearBuilt.min"
              placeholder="Min"
              type="number"
              value={filters.yearBuilt.min}
              onChange={handleChange}
            />
            <Input
              id="yearBuilt.max"
              name="yearBuilt.max"
              placeholder="Max"
              type="number"
              value={filters.yearBuilt.max}
              onChange={handleChange}
            />
          </div>
        </div>
        
        <div className="flex space-x-4 pt-2">
          <Button type="submit" variant="primary" fullWidth>
            Apply Filters
          </Button>
          <Button type="button" variant="outline" onClick={handleReset} fullWidth>
            Reset
          </Button>
        </div>
      </form>
    </Card>
  );
};

export default FilterPanel; 