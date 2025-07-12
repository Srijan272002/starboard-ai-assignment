'use client';

import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Scale,
  Tick,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import Card from '../ui/Card';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface PriceHistoryChartProps {
  propertyId: string;
  data?: {
    labels: string[];
    datasets: {
      label: string;
      data: number[];
      borderColor: string;
      backgroundColor: string;
    }[];
  };
  loading?: boolean;
  error?: string;
  title?: string;
  className?: string;
}

export const PriceHistoryChart = ({
  propertyId,
  data,
  loading = false,
  error,
  title = 'Price History',
  className = '',
}: PriceHistoryChartProps) => {
  // Example data if none is provided
  const defaultData = {
    labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    datasets: [
      {
        label: 'Property Value',
        data: [350000, 355000, 360000, 365000, 370000, 375000, 380000, 385000, 390000, 395000, 400000, 405000],
        borderColor: 'rgb(53, 162, 235)',
        backgroundColor: 'rgba(53, 162, 235, 0.5)',
      },
      {
        label: 'Market Average',
        data: [340000, 345000, 350000, 355000, 360000, 365000, 370000, 375000, 380000, 385000, 390000, 395000],
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.5)',
      },
    ],
  };

  const chartData = data || defaultData;

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
    },
    scales: {
      y: {
        beginAtZero: false,
        ticks: {
          // Update callback to match Chart.js expected signature
          callback: function(tickValue: number | string, index: number, ticks: Tick[]) {
            // Ensure tickValue is a number before formatting
            if (typeof tickValue === 'number') {
              return new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD',
                maximumFractionDigits: 0,
              }).format(tickValue);
            }
            return tickValue;
          },
        },
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

  return (
    <Card className={`${className} p-4`}>
      <Line options={options} data={chartData} />
    </Card>
  );
};

export default PriceHistoryChart; 