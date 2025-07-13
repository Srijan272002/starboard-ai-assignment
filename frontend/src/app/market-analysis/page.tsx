import { Suspense } from 'react';
import { Card } from '@/components/ui/Card';
import MarketTrends from '@/components/market/MarketTrends';
import PriceDistribution from '@/components/market/PriceDistribution';
// import PropertyMap from '@/components/market/PropertyMap';

export default function MarketAnalysisPage() {
  return (
    <div className="container mx-auto py-8">
      <h1 className="text-3xl font-bold mb-6">Market Analysis</h1>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Suspense fallback={<Card className="h-[400px] animate-pulse" />}>
          <Card className="p-6">
            <h2 className="text-xl font-semibold mb-4">Price Trends</h2>
            <MarketTrends />
          </Card>
        </Suspense>

        <Suspense fallback={<Card className="h-[400px] animate-pulse" />}>
          <Card className="p-6">
            <h2 className="text-xl font-semibold mb-4">Price Distribution</h2>
            <PriceDistribution />
          </Card>
        </Suspense>
      </div>

      {/* Property Map removed as requested */}
    </div>
  );
} 