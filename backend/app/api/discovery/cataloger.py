"""
API Cataloger - Automated API cataloging system
"""

import os
import json
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import structlog
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import StarboardException
from .api_analyzer import APIAnalyzer, APIDocumentation, APIAnalysisResult

logger = structlog.get_logger(__name__)


class APICatalogEntry(BaseModel):
    """Entry in the API catalog"""
    api_name: str
    county: Optional[str] = None
    base_url: str
    status: str = "unknown"
    last_analyzed: Optional[datetime] = None
    documentation_path: Optional[str] = None
    health_endpoint: Optional[str] = None
    data_quality_score: float = 0.0
    endpoints_count: int = 0
    field_mappings: Dict[str, str] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class APICatalog(BaseModel):
    """Complete API catalog"""
    version: str = "1.0"
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    total_apis: int = 0
    active_apis: int = 0
    apis: Dict[str, APICatalogEntry] = Field(default_factory=dict)
    statistics: Dict[str, Any] = Field(default_factory=dict)


class APICataloger:
    """Automated API cataloging system"""
    
    def __init__(self):
        self.analyzer = APIAnalyzer()
        
        # Get absolute path for API documentation
        docs_path = Path(settings.API_DOCUMENTATION_PATH)
        if not docs_path.is_absolute():
            # If relative path, make it relative to the current working directory
            docs_path = Path.cwd() / docs_path
            
        self.catalog_path = docs_path / "catalog.yaml"
        self.catalog: APICatalog = APICatalog()
        self._ensure_catalog_directory()
    
    def _ensure_catalog_directory(self):
        """Ensure the catalog directory exists"""
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def load_catalog(self) -> APICatalog:
        """Load existing catalog from file"""
        try:
            if self.catalog_path.exists():
                with open(self.catalog_path, 'r') as f:
                    catalog_data = yaml.safe_load(f)
                    
                # Convert datetime strings back to datetime objects
                if 'last_updated' in catalog_data:
                    catalog_data['last_updated'] = datetime.fromisoformat(catalog_data['last_updated'])
                
                for api_name, api_data in catalog_data.get('apis', {}).items():
                    if 'last_analyzed' in api_data and api_data['last_analyzed']:
                        api_data['last_analyzed'] = datetime.fromisoformat(api_data['last_analyzed'])
                
                self.catalog = APICatalog(**catalog_data)
                logger.info("Catalog loaded", total_apis=self.catalog.total_apis)
            else:
                logger.info("No existing catalog found, creating new one")
                
        except Exception as e:
            logger.error("Failed to load catalog", error=str(e))
            self.catalog = APICatalog()
            
        return self.catalog
    
    async def save_catalog(self):
        """Save catalog to file"""
        try:
            # Convert to dict and handle datetime serialization
            catalog_dict = self.catalog.dict()
            catalog_dict['last_updated'] = self.catalog.last_updated.isoformat()
            
            for api_name, api_data in catalog_dict['apis'].items():
                if api_data.get('last_analyzed'):
                    api_data['last_analyzed'] = api_data['last_analyzed'].isoformat()
                else:
                    api_data['last_analyzed'] = None
            
            with open(self.catalog_path, 'w') as f:
                yaml.dump(catalog_dict, f, default_flow_style=False, sort_keys=False)
                
            logger.info("Catalog saved", path=str(self.catalog_path))
            
        except Exception as e:
            logger.error("Failed to save catalog", error=str(e))
            raise StarboardException(f"Failed to save catalog: {str(e)}")
    
    async def add_api_to_catalog(
        self,
        api_name: str,
        base_url: str,
        county: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> APICatalogEntry:
        """
        Add an API to the catalog
        
        Args:
            api_name: Name of the API
            base_url: Base URL of the API
            county: County name
            tags: Tags for categorization
            metadata: Additional metadata
            
        Returns:
            APICatalogEntry
        """
        entry = APICatalogEntry(
            api_name=api_name,
            county=county,
            base_url=base_url,
            tags=tags or [],
            metadata=metadata or {}
        )
        
        self.catalog.apis[api_name] = entry
        self.catalog.total_apis = len(self.catalog.apis)
        self.catalog.last_updated = datetime.utcnow()
        
        logger.info("API added to catalog", api_name=api_name, county=county)
        
        # Auto-save if enabled
        if settings.AUTO_API_CATALOGING:
            await self.save_catalog()
        
        return entry
    
    async def analyze_and_catalog_api(
        self,
        api_name: str,
        base_url: str,
        county: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> APICatalogEntry:
        """
        Analyze an API and add it to the catalog
        
        Args:
            api_name: Name of the API
            base_url: Base URL of the API
            county: County name
            tags: Tags for categorization
            metadata: Additional metadata
            
        Returns:
            Updated APICatalogEntry
        """
        logger.info("Analyzing and cataloging API", api_name=api_name, base_url=base_url)
        
        try:
            # Analyze the API
            analysis_result = await self.analyzer.discover_api(base_url, api_name)
            
            # Create or update catalog entry
            entry = APICatalogEntry(
                api_name=api_name,
                county=county,
                base_url=base_url,
                status=analysis_result.health_status,
                last_analyzed=datetime.utcnow(),
                documentation_path=f"{api_name}.yaml",
                data_quality_score=analysis_result.data_quality_score,
                endpoints_count=len(analysis_result.discovered_endpoints),
                field_mappings=analysis_result.field_mappings,
                tags=tags or [],
                metadata=metadata or {}
            )
            
            # Add health endpoint if discovered
            health_endpoints = [
                ep.url for ep in analysis_result.discovered_endpoints
                if any(term in ep.url.lower() for term in ['health', 'status', 'ping'])
            ]
            if health_endpoints:
                entry.health_endpoint = health_endpoints[0]
            
            # Add county-specific tags
            if county:
                entry.tags.append(f"county:{county.lower()}")
            
            # Add quality tags
            if entry.data_quality_score >= 0.8:
                entry.tags.append("high-quality")
            elif entry.data_quality_score >= 0.6:
                entry.tags.append("medium-quality")
            else:
                entry.tags.append("low-quality")
            
            # Add status tags
            entry.tags.append(f"status:{entry.status}")
            
            # Update catalog
            self.catalog.apis[api_name] = entry
            self.catalog.total_apis = len(self.catalog.apis)
            self.catalog.active_apis = len([
                api for api in self.catalog.apis.values()
                if api.status in ["active", "healthy"]
            ])
            self.catalog.last_updated = datetime.utcnow()
            
            # Update statistics
            await self._update_catalog_statistics()
            
            logger.info("API analyzed and cataloged", 
                       api_name=api_name,
                       status=entry.status,
                       quality_score=entry.data_quality_score,
                       endpoints_found=entry.endpoints_count)
            
            # Auto-save if enabled
            if settings.AUTO_API_CATALOGING:
                await self.save_catalog()
            
            return entry
            
        except Exception as e:
            logger.error("Failed to analyze and catalog API", 
                        api_name=api_name, 
                        error=str(e))
            
            # Create entry with error status
            entry = APICatalogEntry(
                api_name=api_name,
                county=county,
                base_url=base_url,
                status="error",
                last_analyzed=datetime.utcnow(),
                tags=(tags or []) + ["status:error"],
                metadata=(metadata or {})
            )
            entry.metadata["error"] = str(e)
            
            self.catalog.apis[api_name] = entry
            self.catalog.total_apis = len(self.catalog.apis)
            self.catalog.last_updated = datetime.utcnow()
            
            if settings.AUTO_API_CATALOGING:
                await self.save_catalog()
            
            return entry
    
    async def _update_catalog_statistics(self):
        """Update catalog statistics"""
        apis = list(self.catalog.apis.values())
        
        if not apis:
            return
        
        # Status distribution
        status_counts = {}
        for api in apis:
            status = api.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # County distribution
        county_counts = {}
        for api in apis:
            county = api.county or "unknown"
            county_counts[county] = county_counts.get(county, 0) + 1
        
        # Quality distribution
        quality_ranges = {"high": 0, "medium": 0, "low": 0}
        total_quality = 0
        for api in apis:
            if api.data_quality_score >= 0.8:
                quality_ranges["high"] += 1
            elif api.data_quality_score >= 0.6:
                quality_ranges["medium"] += 1
            else:
                quality_ranges["low"] += 1
            total_quality += api.data_quality_score
        
        # Average quality score
        avg_quality = total_quality / len(apis) if apis else 0
        
        # Total endpoints
        total_endpoints = sum(api.endpoints_count for api in apis)
        
        self.catalog.statistics = {
            "status_distribution": status_counts,
            "county_distribution": county_counts,
            "quality_distribution": quality_ranges,
            "average_quality_score": round(avg_quality, 3),
            "total_endpoints": total_endpoints,
            "last_updated": datetime.utcnow().isoformat()
        }
    
    async def refresh_catalog(self, force_reanalyze: bool = False):
        """
        Refresh the entire catalog by re-analyzing all APIs
        
        Args:
            force_reanalyze: Force re-analysis even for recently analyzed APIs
        """
        logger.info("Refreshing catalog", force_reanalyze=force_reanalyze)
        
        apis_to_analyze = []
        cutoff_time = datetime.utcnow() - timedelta(hours=24)  # Re-analyze if older than 24 hours
        
        for api_name, api_entry in self.catalog.apis.items():
            should_analyze = force_reanalyze
            
            if not should_analyze:
                # Check if needs re-analysis
                if not api_entry.last_analyzed or api_entry.last_analyzed < cutoff_time:
                    should_analyze = True
                elif api_entry.status in ["error", "unknown"]:
                    should_analyze = True
            
            if should_analyze:
                apis_to_analyze.append((api_name, api_entry))
        
        logger.info("APIs to analyze", count=len(apis_to_analyze))
        
        # Analyze APIs
        for api_name, api_entry in apis_to_analyze:
            try:
                await self.analyze_and_catalog_api(
                    api_name=api_name,
                    base_url=api_entry.base_url,
                    county=api_entry.county,
                    tags=api_entry.tags,
                    metadata=api_entry.metadata
                )
            except Exception as e:
                logger.error("Failed to refresh API", api_name=api_name, error=str(e))
        
        await self.save_catalog()
        logger.info("Catalog refresh completed")
    
    def search_catalog(
        self,
        query: Optional[str] = None,
        county: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_quality_score: Optional[float] = None
    ) -> List[APICatalogEntry]:
        """
        Search the API catalog
        
        Args:
            query: Text query for API name or base URL
            county: Filter by county
            status: Filter by status
            tags: Filter by tags (all must match)
            min_quality_score: Minimum quality score
            
        Returns:
            List of matching APICatalogEntry objects
        """
        results = []
        
        for api_entry in self.catalog.apis.values():
            # Text query filter
            if query:
                query_lower = query.lower()
                if (query_lower not in api_entry.api_name.lower() and
                    query_lower not in api_entry.base_url.lower()):
                    continue
            
            # County filter
            if county and api_entry.county != county:
                continue
            
            # Status filter
            if status and api_entry.status != status:
                continue
            
            # Tags filter
            if tags:
                api_tags = set(api_entry.tags)
                required_tags = set(tags)
                if not required_tags.issubset(api_tags):
                    continue
            
            # Quality score filter
            if min_quality_score and api_entry.data_quality_score < min_quality_score:
                continue
            
            results.append(api_entry)
        
        # Sort by quality score descending
        results.sort(key=lambda x: x.data_quality_score, reverse=True)
        
        return results
    
    def get_catalog_summary(self) -> Dict[str, Any]:
        """Get a summary of the catalog"""
        return {
            "version": self.catalog.version,
            "last_updated": self.catalog.last_updated.isoformat(),
            "total_apis": self.catalog.total_apis,
            "active_apis": self.catalog.active_apis,
            "statistics": self.catalog.statistics,
            "catalog_path": str(self.catalog_path)
        }
    
    def get_api_details(self, api_name: str) -> Optional[APICatalogEntry]:
        """Get details for a specific API"""
        return self.catalog.apis.get(api_name)
    
    async def remove_api_from_catalog(self, api_name: str) -> bool:
        """
        Remove an API from the catalog
        
        Args:
            api_name: Name of the API to remove
            
        Returns:
            True if removed, False if not found
        """
        if api_name in self.catalog.apis:
            del self.catalog.apis[api_name]
            self.catalog.total_apis = len(self.catalog.apis)
            self.catalog.active_apis = len([
                api for api in self.catalog.apis.values()
                if api.status in ["active", "healthy"]
            ])
            self.catalog.last_updated = datetime.utcnow()
            
            await self._update_catalog_statistics()
            
            if settings.AUTO_API_CATALOGING:
                await self.save_catalog()
            
            logger.info("API removed from catalog", api_name=api_name)
            return True
        
        return False
    
    async def export_catalog(self, format: str = "yaml") -> str:
        """
        Export catalog in specified format
        
        Args:
            format: Export format (yaml, json)
            
        Returns:
            Serialized catalog data
        """
        catalog_dict = self.catalog.dict()
        catalog_dict['last_updated'] = self.catalog.last_updated.isoformat()
        
        for api_name, api_data in catalog_dict['apis'].items():
            if api_data.get('last_analyzed'):
                api_data['last_analyzed'] = api_data['last_analyzed'].isoformat()
        
        if format.lower() == "json":
            return json.dumps(catalog_dict, indent=2)
        else:  # Default to YAML
            return yaml.dump(catalog_dict, default_flow_style=False, sort_keys=False)
    
    async def close(self):
        """Close the cataloger"""
        await self.analyzer.close()
        logger.info("API cataloger closed") 