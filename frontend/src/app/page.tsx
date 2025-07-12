import React from 'react';
import Link from 'next/link';
import MainLayout from '../components/layout/MainLayout';
import Card from '../components/ui/Card';
import { ArrowRightIcon } from '@heroicons/react/24/outline';

export default function Home() {
  return (
    <MainLayout>
      <div className="space-y-12">
        {/* Hero Section */}
        <section className="bg-blue-600 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8 py-16 text-white rounded-lg">
          <div className="max-w-3xl mx-auto text-center">
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl mb-6">
              Find and Analyze Property Data
            </h1>
            <p className="text-xl text-blue-100 mb-8">
              Comprehensive property data from multiple counties, all in one place.
              Search, compare, and analyze with powerful tools.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link 
                href="/search" 
                className="bg-white text-blue-600 hover:bg-blue-50 px-6 py-3 rounded-md font-medium text-lg"
              >
                Search Properties
              </Link>
              <Link 
                href="/dashboard" 
                className="bg-blue-700 text-white hover:bg-blue-800 px-6 py-3 rounded-md font-medium text-lg"
              >
                View Dashboard
              </Link>
            </div>
          </div>
        </section>


        {/* Features Section */}
        <section>
          <h2 className="text-2xl font-bold mb-8 text-center">Key Features</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <Card className="p-6">
              <div className="flex flex-col h-full">
                <h3 className="text-xl font-semibold mb-4">Property Search</h3>
                <p className="text-gray-600 mb-6 flex-grow">
                  Search across multiple counties with advanced filtering options to find exactly what you're looking for.
                </p>
                <Link 
                  href="/search" 
                  className="flex items-center text-blue-600 hover:text-blue-800 font-medium"
                >
                  Try it now
                  <ArrowRightIcon className="h-4 w-4 ml-1" />
                </Link>
              </div>
            </Card>
            
            <Card className="p-6">
              <div className="flex flex-col h-full">
                <h3 className="text-xl font-semibold mb-4">Data Visualization</h3>
                <p className="text-gray-600 mb-6 flex-grow">
                  Interactive maps, charts, and graphs to help you visualize property data and market trends.
                </p>
                <Link 
                  href="/dashboard" 
                  className="flex items-center text-blue-600 hover:text-blue-800 font-medium"
                >
                  View dashboard
                  <ArrowRightIcon className="h-4 w-4 ml-1" />
                </Link>
              </div>
            </Card>
            
            <Card className="p-6">
              <div className="flex flex-col h-full">
                <h3 className="text-xl font-semibold mb-4">Property Comparison</h3>
                <p className="text-gray-600 mb-6 flex-grow">
                  Compare multiple properties side by side to make informed decisions about your investments.
                </p>
                <Link 
                  href="/compare" 
                  className="flex items-center text-blue-600 hover:text-blue-800 font-medium"
                >
                  Compare properties
                  <ArrowRightIcon className="h-4 w-4 ml-1" />
                </Link>
              </div>
            </Card>
          </div>
        </section>

        {/* Counties Section */}
        <section>
          <h2 className="text-2xl font-bold mb-8 text-center">Available Counties</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Link href="/search?county=cook" className="block">
              <Card className="p-6 hover:shadow-md transition-shadow">
                <h3 className="text-xl font-semibold mb-2">Cook County</h3>
                <p className="text-gray-600">Illinois</p>
              </Card>
            </Link>
            <Link href="/search?county=dallas" className="block">
              <Card className="p-6 hover:shadow-md transition-shadow">
                <h3 className="text-xl font-semibold mb-2">Dallas County</h3>
                <p className="text-gray-600">Texas</p>
              </Card>
            </Link>
            <Link href="/search?county=la" className="block">
              <Card className="p-6 hover:shadow-md transition-shadow">
                <h3 className="text-xl font-semibold mb-2">LA County</h3>
                <p className="text-gray-600">California</p>
              </Card>
            </Link>
          </div>
        </section>
      </div>
    </MainLayout>
  );
}
