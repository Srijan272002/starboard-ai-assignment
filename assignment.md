Starboard AI/Agent Engineer Take-Home Challenge

Overview

Goal: Build an intelligent agent system that can integrate multiple county property APIs and perform comparable analysis.

Starboard helps real estate investors close more deals, faster through AI-powered analysis. We need to integrate property data from multiple county APIs to create a unified database of industrial properties with comprehensive comparable analysis capabilities.

Challenge: Multi-County Industrial Property Comparable Analysis

Background:
We're expanding Starboard to cover the three largest industrial real estate markets:
- Cook County, Illinois (Chicago) - Largest market nationally
- Dallas County, Texas - Fastest growing market
- Los Angeles County, California - Largest inventory

Each county has different API structures, data formats, and rate limits. Your task is to build an intelligent agent system that can handle this complexity automatically.

Task Requirements

- Build an intelligent agent system with these capabilities:
- API Discovery Agent

- Discover, ingest and catalogue API
- Maps available data fields and identifies industrial property filters
- Detects authentication requirements and rate limits
- Handles field name variations (e.g., "square_feet" vs "sqft" vs "building_area")
- Identifies missing or inconsistent data types
- Automatically detects and respects API rate limits
- Implements intelligent batching and retry logic

Phase 2: Data Extraction System
- Create agents that can extract and process property data:
- Filters for industrial zoning codes (M1, M2, I-1, I-2, etc.)
- Handles different response formats (JSON, CSV, GeoJSON)
- Validates required fields are present and reasonable
- Flags outliers and suspicious records
- Logs errors with context for debugging

Phase 3: Comparable Discovery Agent
- Build an agent that performs comparable property analysis:
- Finds similar properties by size, location, age, and type
- Weights similarity factors appropriately
- Generates confidence scores for each comparable

Languages: Python + Next.js
Output: ability to input an industrial property from the dataset and output the best comparables
use Attomdata’s free API 