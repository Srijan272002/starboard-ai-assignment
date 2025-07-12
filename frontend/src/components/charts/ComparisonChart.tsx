'use client';

import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import Card from '../ui/Card';
import { Property } from '../properties/PropertyCard';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

interface ComparisonChartProps {
  properties: Property[];
  loading?: boolean;
  error?: string;
  title?: string;
  className?: string;
}

export const ComparisonChart = ({
  properties,
  loading = false,
  error,
  title = 'Property Comparison',
  className = '',
}: ComparisonChartProps) => {
  // Generate chart data from properties
  const chartData = {
    labels: properties.map(p => p.address.split(',')[0]), // Just the street address
    datasets: [
      {
        label: 'Price',
        data: properties.map(p => p.price),
        backgroundColor: 'rgba(53, 162, 235, 0.5)',
      },
      {
        label: 'Square Feet',
        data: properties.map(p => p.squareFeet || 0),
        backgroundColor: 'rgba(75, 192, 192, 0.5)',
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: title,
      },
      tooltip: {
        callbacks: {
          label: function(context: any) {
            let label = context.dataset.label || '';
            if (label) {
              label += ': ';
            }
            if (context.parsed.y !== null) {
              if (label.includes('Price')) {
                label += new Intl.NumberFormat('en-US', {
                  style: 'currency',
                  currency: 'USD',
                  maximumFractionDigits: 0,
                }).format(context.parsed.y);
              } else {
                label += new Intl.NumberFormat('en-US').format(context.parsed.y);
                if (label.includes('Square')) {
                  label += ' sq ft';
                }
              }
            }
            return label;
          }
        }
      }
    },
    scales: {
      y: {
        beginAtZero: true,
      },
    },
  };

  if (loading) {
    return (
      <Card className={`${className} p-4 h-80`}>
        <div className="flex items-center justify-center h-full">
          <div className="animate-pulse flex flex-col items-center">
            <div className="h-6 w-48 bg-gray-200 rounded mb-4"></div>
            <div className="h-40 w-full bg-gray-200 rounded"></div>
          </div>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={`${className} p-4`}>
        <div className="flex items-center justify-center h-64">
          <p className="text-red-500">{error}</p>
        </div>
      </Card>
    );
  }

  if (properties.length === 0) {
    return (
      <Card className={`${className} p-4`}>
        <div className="flex items-center justify-center h-64">
          <p className="text-gray-500">No properties to compare</p>
        </div>
      </Card>
    );
  }

  return (
    <Card className={`${className} p-4`}>
      <Bar options={options} data={chartData} />
    </Card>
  );
};

export default ComparisonChart; 