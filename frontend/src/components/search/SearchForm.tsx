'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Button from '../ui/Button';
import Input from '../ui/Input';
import Select from '../ui/Select';
import apiService, { SearchParams } from '../../lib/api';

const counties = [
  { value: 'cook', label: 'Cook County' },
  { value: 'dallas', label: 'Dallas County' },
  { value: 'la', label: 'LA County' },
];

const propertyTypes = [
  { value: 'residential', label: 'Residential' },
  { value: 'commercial', label: 'Commercial' },
  { value: 'industrial', label: 'Industrial' },
  { value: 'land', label: 'Land' },
];

interface SearchFormProps {
  onSearch?: (searchParams: SearchParams) => void;
  className?: string;
}

export const SearchForm = ({ onSearch, className = '' }: SearchFormProps) => {
  const router = useRouter();
  const [searchParams, setSearchParams] = useState<SearchParams>({
    county: '',
    propertyType: '',
    address: '',
    minPrice: undefined,
    maxPrice: undefined,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setSearchParams((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    
    try {
      if (onSearch) {
        onSearch(searchParams);
      } else {
        // Call API and navigate to results
        const response = await apiService.searchProperties(searchParams);
        const queryParams = new URLSearchParams();
        Object.entries(searchParams).forEach(([key, value]) => {
          if (value) {
            queryParams.append(key, value.toString());
          }
        });
        router.push(`/search?${queryParams.toString()}`);
      }
    } catch (err) {
      setError('Failed to search properties. Please try again.');
      console.error('Search error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className={`space-y-4 ${className}`}>
      {error && (
        <div className="bg-red-50 text-red-600 p-3 rounded-md text-sm">
          {error}
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Select
          id="county"
          name="county"
          label="County"
          options={counties}
          value={searchParams.county}
          onChange={handleChange}
          placeholder="Select a county"
        />
        <Select
          id="propertyType"
          name="propertyType"
          label="Property Type"
          options={propertyTypes}
          value={searchParams.propertyType}
          onChange={handleChange}
          placeholder="Select property type"
        />
      </div>
      <Input
        id="address"
        name="address"
        label="Address"
        placeholder="Enter address, city, or ZIP code"
        value={searchParams.address}
        onChange={handleChange}
      />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input
          id="minPrice"
          name="minPrice"
          label="Min Price"
          type="number"
          placeholder="Minimum price"
          value={searchParams.minPrice?.toString() || ''}
          onChange={handleChange}
        />
        <Input
          id="maxPrice"
          name="maxPrice"
          label="Max Price"
          type="number"
          placeholder="Maximum price"
          value={searchParams.maxPrice?.toString() || ''}
          onChange={handleChange}
        />
      </div>
      <div className="flex justify-end">
        <Button type="submit" disabled={isLoading}>
          {isLoading ? 'Searching...' : 'Search Properties'}
        </Button>
      </div>
    </form>
  );
};

export default SearchForm; 