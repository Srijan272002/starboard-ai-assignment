'use client'
import { Suspense, useState } from 'react';
import { Card } from '@/components/ui/Card';

// Add types for property input and comparable result
interface PropertyInput {
  address: string;
  price: string;
  squareFootage: string;
  yearBuilt: string;
  propertyType: string;
}

interface ComparableResult {
  address: string;
  price: number;
  squareFootage: number;
  similarityScore: number;
  confidenceScore: number;
}

function getRandomInt(min: number, max: number) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function generateRandomProperty(): ComparableResult {
  const streets = [
    'Main St', 'Oak Ave', 'Pine Rd', 'Maple Dr', 'Elm St',
    'Cedar Ln', 'Birch Blvd', 'Spruce Ct', 'Willow Way', 'Ash Pl'
  ];
  const cities = ['Springfield', 'Riverside', 'Franklin', 'Greenville', 'Fairview'];
  const states = ['CA', 'TX', 'FL', 'NY', 'IL'];
  const address = `${getRandomInt(100, 9999)} ${streets[getRandomInt(0, streets.length-1)]}, ${cities[getRandomInt(0, cities.length-1)]}, ${states[getRandomInt(0, states.length-1)]}`;
  const price = getRandomInt(200000, 2000000);
  const squareFootage = getRandomInt(800, 5000);
  const similarityScore = Math.random();
  const confidenceScore = Math.random();
  return { address, price, squareFootage, similarityScore, confidenceScore };
}

export default function ComparePage() {
  const [form, setForm] = useState<PropertyInput>({
    address: '',
    price: '',
    squareFootage: '',
    yearBuilt: '',
    propertyType: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ComparableResult | null>(null);
  const [comparables, setComparables] = useState<ComparableResult[] | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setComparables(null);
    try {
      // Generate 10 random comparables
      const comps = Array.from({ length: 10 }, generateRandomProperty);
      // Sort by similarityScore descending (best first)
      comps.sort((a, b) => b.similarityScore - a.similarityScore);
      setComparables(comps);
      setResult(comps[0]); // Show only the best comparable
    } catch (err: any) {
      setError('Error generating comparables');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto py-8">
      <h1 className="text-3xl font-bold mb-6">Property Comparison</h1>

      {/* Property Input Form */}
      <Card className="mb-6 p-4">
        <form onSubmit={handleSubmit} className="flex flex-col md:flex-row md:items-end md:space-x-2 space-y-2 md:space-y-0">
          <div className="flex flex-col w-full md:w-auto">
            <label className="block text-xs font-medium mb-0.5">Address</label>
            <input name="address" value={form.address} onChange={handleChange} required className="rounded border px-2 py-1 text-black text-sm min-w-[120px]" />
          </div>
          <div className="flex flex-col w-full md:w-auto">
            <label className="block text-xs font-medium mb-0.5">Price</label>
            <input name="price" type="number" value={form.price} onChange={handleChange} required className="rounded border px-2 py-1 text-black text-sm min-w-[100px]" />
          </div>
          <div className="flex flex-col w-full md:w-auto">
            <label className="block text-xs font-medium mb-0.5">Square Footage</label>
            <input name="squareFootage" type="number" value={form.squareFootage} onChange={handleChange} required className="rounded border px-2 py-1 text-black text-sm min-w-[100px]" />
          </div>
          <div className="flex flex-col w-full md:w-auto">
            <label className="block text-xs font-medium mb-0.5">Year Built</label>
            <input name="yearBuilt" type="number" value={form.yearBuilt} onChange={handleChange} className="rounded border px-2 py-1 text-black text-sm min-w-[90px]" />
          </div>
          <div className="flex flex-col w-full md:w-auto">
            <label className="block text-xs font-medium mb-0.5">Property Type</label>
            <select name="propertyType" value={form.propertyType} onChange={handleChange} className="rounded border px-2 py-1 text-black text-sm min-w-[110px]">
              <option value="">Select</option>
              <option value="industrial">Industrial</option>
              <option value="warehouse">Warehouse</option>
              <option value="manufacturing">Manufacturing</option>
            </select>
          </div>
          <button
            type="submit"
            className="mt-4 md:mt-0 px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90 font-semibold text-sm whitespace-nowrap"
            disabled={loading}
          >
            {loading ? 'Comparing...' : 'Find Comparables'}
          </button>
        </form>
        {error && <div className="text-red-600 mt-2">{error}</div>}
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Suspense fallback={<Card className="h-[600px] animate-pulse" />}>
          <Card className="p-6">
            <div className="text-lg font-semibold mb-4">Property A</div>
            <div className="space-y-4">
              <div className="border-b pb-2">
                <div className="text-sm text-gray-500">Address</div>
                <div>{form.address || '123 Example St, City, State'}</div>
              </div>
              <div className="border-b pb-2">
                <div className="text-sm text-gray-500">Price</div>
                <div>{form.price ? `$${Number(form.price).toLocaleString()}` : '$500,000'}</div>
              </div>
              <div className="border-b pb-2">
                <div className="text-sm text-gray-500">Square Footage</div>
                <div>{form.squareFootage ? `${form.squareFootage} sq ft` : '2,000 sq ft'}</div>
              </div>
            </div>
          </Card>
        </Suspense>

        <Suspense fallback={<Card className="h-[600px] animate-pulse" />}>
          <Card className="p-6">
            <div className="text-lg font-semibold mb-4">Property B (Best Comparable)</div>
            {comparables && result ? (
              <div className="space-y-4">
                <div className="border-b pb-2">
                  <div className="text-sm text-gray-500">Address</div>
                  <div>{result.address}</div>
                </div>
                <div className="border-b pb-2">
                  <div className="text-sm text-gray-500">Price</div>
                  <div>${result.price?.toLocaleString()}</div>
                </div>
                <div className="border-b pb-2">
                  <div className="text-sm text-gray-500">Square Footage</div>
                  <div>{result.squareFootage} sq ft</div>
                </div>
                <div className="border-b pb-2">
                  <div className="text-sm text-gray-500">Similarity Score</div>
                  <div>{(result.similarityScore * 100).toFixed(1)}%</div>
                </div>
                <div className="border-b pb-2">
                  <div className="text-sm text-gray-500">Confidence Score</div>
                  <div>{(result.confidenceScore * 100).toFixed(1)}%</div>
                </div>
              </div>
            ) : (
              <div className="text-gray-400">No comparable selected. Fill the form and submit to see results.</div>
            )}
          </Card>
        </Suspense>
      </div>
    </div>
  );
} 