'use client'

import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
// Remove MarketTrend import since we use mock data
// import { MarketTrend } from '@/lib/api/types';
import { usePolling, createPollingEndpoint } from '@/lib/services/polling';

type TimeFrame = '1M' | '3M' | '6M' | '1Y' | 'ALL';

// MOCK DATA for demo
const mockTrendsData: Record<string, { date: string; median_price: number }[]> = {
  '1M': [
    { date: '2024-07-01', median_price: 470000 },
    { date: '2024-08-01', median_price: 480000 },
  ],
  '3M': [
    { date: '2024-06-01', median_price: 460000 },
    { date: '2024-07-01', median_price: 470000 },
    { date: '2024-08-01', median_price: 480000 },
  ],
  '6M': [
    { date: '2024-03-01', median_price: 420000 },
    { date: '2024-04-01', median_price: 430000 },
    { date: '2024-05-01', median_price: 440000 },
    { date: '2024-06-01', median_price: 460000 },
    { date: '2024-07-01', median_price: 470000 },
    { date: '2024-08-01', median_price: 480000 },
  ],
  '1Y': [
    { date: '2023-09-01', median_price: 390000 },
    { date: '2023-11-01', median_price: 400000 },
    { date: '2024-01-01', median_price: 410000 },
    { date: '2024-03-01', median_price: 420000 },
    { date: '2024-05-01', median_price: 440000 },
    { date: '2024-07-01', median_price: 470000 },
    { date: '2024-08-01', median_price: 480000 },
  ],
  'ALL': [
    { date: '2022-01-01', median_price: 320000 },
    { date: '2022-07-01', median_price: 340000 },
    { date: '2023-01-01', median_price: 360000 },
    { date: '2023-07-01', median_price: 380000 },
    { date: '2024-01-01', median_price: 410000 },
    { date: '2024-08-01', median_price: 480000 },
  ],
};

export default function MarketTrends() {
  const svgRef = useRef<SVGSVGElement>(null);
  const [timeframe, setTimeframe] = useState<TimeFrame>('6M');
  const [error, setError] = useState<string | null>(null);

  // Use mock data based on timeframe
  const trends = mockTrendsData[timeframe];

  // Render chart using D3
  useEffect(() => {
    if (!trends || !trends.length || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove(); // Clear previous chart

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;
    const margin = { top: 20, right: 30, bottom: 30, left: 60 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // Create scales
    const x = d3.scaleTime()
      .domain(d3.extent(trends, d => new Date(d.date)) as [Date, Date])
      .range([0, innerWidth]);

    const y = d3.scaleLinear()
      .domain([0, d3.max(trends, d => d.median_price) as number * 1.1])
      .range([innerHeight, 0]);

    // Create line generator
    const line = d3.line<typeof mockTrendsData[string][0]>()
      .x(d => x(new Date(d.date)))
      .y(d => y(d.median_price))
      .curve(d3.curveMonotoneX);

    // Create chart group
    const g = svg.append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Add axes
    g.append("g")
      .attr("transform", `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x));

    g.append("g")
      .call(d3.axisLeft(y).ticks(5).tickFormat(d => `$${d3.format(",.0f")(d as number)}`));

    // Add line path
    g.append("path")
      .datum(trends)
      .attr("fill", "none")
      .attr("stroke", "steelblue")
      .attr("stroke-width", 2)
      .attr("d", line);

    // Add dots
    g.selectAll("circle")
      .data(trends)
      .enter()
      .append("circle")
      .attr("cx", d => x(new Date(d.date)))
      .attr("cy", d => y(d.median_price))
      .attr("r", 4)
      .attr("fill", "steelblue");

  }, [trends]);

  return (
    <div className="p-4 bg-card rounded-lg shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Market Trends</h2>
        <div className="flex gap-2">
          {(['1M', '3M', '6M', '1Y', 'ALL'] as TimeFrame[]).map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-2 py-1 text-sm rounded ${
                timeframe === tf
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>
      
      {error ? (
        <div className="h-64 flex items-center justify-center">
          <p className="text-destructive">{error}</p>
        </div>
      ) : !trends || trends.length === 0 ? (
        <div className="h-64 flex items-center justify-center">
          <p className="text-muted-foreground">No trend data available</p>
        </div>
      ) : (
        <>
          <svg ref={svgRef} className="w-full h-64" />
          <div className="mt-2 text-xs text-right text-muted-foreground">
            <span className="flex items-center justify-end">
              <span className="h-2 w-2 rounded-full bg-green-500 mr-1"></span>
              Static data (live updates unavailable)
            </span>
          </div>
        </>
      )}
    </div>
  );
} 