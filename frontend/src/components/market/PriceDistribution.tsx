'use client'

import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { MarketAnalysis, PriceDistributionBin } from '@/lib/api/types';
import { usePolling, createPollingEndpoint } from '@/lib/services/polling';

interface FilterOptions {
  propertyType?: string;
  minSize?: number;
  maxSize?: number;
  yearBuilt?: number;
}

// MOCK DATA for demo
const mockDistribution = [
  { range: [200000, 400000], count: 10 },
  { range: [400000, 600000], count: 25 },
  { range: [600000, 800000], count: 18 },
  { range: [800000, 1000000], count: 7 },
];
const mockStats = { mean: 550000, median: 500000, std_dev: 120000 };

export default function PriceDistribution() {
  const svgRef = useRef<SVGSVGElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterOptions>({});

  // Use mock data instead of polling
  const distribution = mockDistribution;
  const stats = mockStats;

  // Render chart using D3
  useEffect(() => {
    if (!distribution || !distribution.length || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove(); // Clear previous chart

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;
    const margin = { top: 20, right: 30, bottom: 30, left: 60 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // Create scales
    const x = d3.scaleLinear()
      .domain([0, d3.max(distribution, d => d.range[1]) as number])
      .range([0, innerWidth]);

    const y = d3.scaleLinear()
      .domain([0, d3.max(distribution, d => d.count) as number])
      .range([innerHeight, 0]);

    // Create chart group
    const g = svg.append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Add bars
    g.selectAll("rect")
      .data(distribution)
      .enter()
      .append("rect")
      .attr("x", d => x(d.range[0]))
      .attr("y", d => y(d.count))
      .attr("width", d => x(d.range[1]) - x(d.range[0]))
      .attr("height", d => innerHeight - y(d.count))
      .attr("fill", "steelblue")
      .attr("opacity", 0.7);

    // Add axes
    g.append("g")
      .attr("transform", `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x).tickFormat(d => `$${d3.format(",.0f")(d as number)}`));

    g.append("g")
      .call(d3.axisLeft(y).ticks(5));

  }, [distribution]);

  return (
    <div className="p-4 bg-card rounded-lg shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Price Distribution</h2>
        {/* Add filter controls here if needed */}
      </div>
      
      {error ? (
        <div className="h-64 flex items-center justify-center">
          <p className="text-destructive">{error}</p>
        </div>
      ) : !distribution || !distribution.length ? (
        <div className="h-64 flex items-center justify-center">
          <p className="text-muted-foreground">No distribution data available</p>
        </div>
      ) : (
        <>
          <svg ref={svgRef} className="w-full h-64" />
          <div className="grid grid-cols-3 gap-4 mt-4 text-sm">
            <div className="text-center">
              <p className="text-muted-foreground">Median</p>
              <p className="font-semibold">${stats.median?.toLocaleString()}</p>
            </div>
            <div className="text-center">
              <p className="text-muted-foreground">Mean</p>
              <p className="font-semibold">${stats.mean?.toLocaleString()}</p>
            </div>
            <div className="text-center">
              <p className="text-muted-foreground">Std Dev</p>
              <p className="font-semibold">${stats.std_dev?.toLocaleString()}</p>
            </div>
          </div>
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