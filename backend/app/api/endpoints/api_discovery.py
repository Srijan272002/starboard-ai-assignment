"""
API Discovery endpoints - Provides access to Phase 2 functionality
"""

from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
import structlog

from app.core.logging import get_logger
from app.api.discovery import APIAnalyzer, APICataloger, APIHealthMonitor, RateLimiter
from app.api.standardization import FieldMapper

logger = get_logger(__name__)
router = APIRouter()

# Global instances (in production, these would be managed by dependency injection)
api_analyzer = APIAnalyzer()
api_cataloger = APICataloger()
health_monitor = APIHealthMonitor()
rate_limiter = RateLimiter()
field_mapper = FieldMapper()


class APIDiscoveryRequest(BaseModel):
    api_name: str
    base_url: str
    county: Optional[str] = None
    tags: Optional[List[str]] = None


class AnalysisResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/discover", response_model=AnalysisResponse)
async def discover_api(
    request: APIDiscoveryRequest,
    background_tasks: BackgroundTasks
):
    """
    Discover and analyze an external API
    """
    try:
        logger.info("API discovery requested", 
                   api_name=request.api_name,
                   base_url=request.base_url)
        
        # Start analysis in background
        background_tasks.add_task(
            analyze_and_catalog_api,
            request.api_name,
            request.base_url,
            request.county,
            request.tags
        )
        
        return AnalysisResponse(
            success=True,
            message=f"API analysis started for {request.api_name}",
            data={
                "api_name": request.api_name,
                "status": "analysis_started"
            }
        )
        
    except Exception as e:
        logger.error("API discovery failed", error=str(e))
        return AnalysisResponse(
            success=False,
            message="API discovery failed",
            error=str(e)
        )


async def analyze_and_catalog_api(
    api_name: str,
    base_url: str,
    county: Optional[str] = None,
    tags: Optional[List[str]] = None
):
    """Background task to analyze and catalog an API"""
    try:
        await api_cataloger.analyze_and_catalog_api(
            api_name=api_name,
            base_url=base_url,
            county=county,
            tags=tags
        )
        logger.info("API analysis completed", api_name=api_name)
    except Exception as e:
        logger.error("Background API analysis failed", 
                    api_name=api_name, 
                    error=str(e))


@router.get("/catalog", response_model=AnalysisResponse)
async def get_api_catalog(
    query: Optional[str] = Query(None, description="Search query"),
    county: Optional[str] = Query(None, description="Filter by county"),
    status: Optional[str] = Query(None, description="Filter by status"),
    min_quality_score: Optional[float] = Query(None, description="Minimum quality score")
):
    """
    Get API catalog with optional filtering
    """
    try:
        # Load catalog
        await api_cataloger.load_catalog()
        
        # Search catalog
        results = api_cataloger.search_catalog(
            query=query,
            county=county,
            status=status,
            min_quality_score=min_quality_score
        )
        
        # Get catalog summary
        summary = api_cataloger.get_catalog_summary()
        
        return AnalysisResponse(
            success=True,
            message="API catalog retrieved",
            data={
                "summary": summary,
                "results": [api.dict() for api in results],
                "total_results": len(results)
            }
        )
        
    except Exception as e:
        logger.error("Failed to get API catalog", error=str(e))
        return AnalysisResponse(
            success=False,
            message="Failed to retrieve API catalog",
            error=str(e)
        )


@router.get("/catalog/{api_name}", response_model=AnalysisResponse)
async def get_api_details(api_name: str):
    """
    Get detailed information about a specific API
    """
    try:
        await api_cataloger.load_catalog()
        api_details = api_cataloger.get_api_details(api_name)
        
        if not api_details:
            raise HTTPException(status_code=404, detail=f"API {api_name} not found")
        
        return AnalysisResponse(
            success=True,
            message=f"API details retrieved for {api_name}",
            data=api_details.dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get API details", api_name=api_name, error=str(e))
        return AnalysisResponse(
            success=False,
            message=f"Failed to retrieve API details for {api_name}",
            error=str(e)
        )


@router.get("/health", response_model=AnalysisResponse)
async def get_health_status():
    """
    Get health status for all monitored APIs
    """
    try:
        health_status = health_monitor.get_all_health_status()
        
        return AnalysisResponse(
            success=True,
            message="Health status retrieved",
            data=health_status
        )
        
    except Exception as e:
        logger.error("Failed to get health status", error=str(e))
        return AnalysisResponse(
            success=False,
            message="Failed to retrieve health status",
            error=str(e)
        )


@router.get("/health/{api_name}", response_model=AnalysisResponse)
async def get_api_health_status(api_name: str):
    """
    Get health status for a specific API
    """
    try:
        health_status = health_monitor.get_api_health_status(api_name)
        
        return AnalysisResponse(
            success=True,
            message=f"Health status retrieved for {api_name}",
            data=health_status
        )
        
    except Exception as e:
        logger.error("Failed to get API health status", 
                    api_name=api_name, 
                    error=str(e))
        return AnalysisResponse(
            success=False,
            message=f"Failed to retrieve health status for {api_name}",
            error=str(e)
        )


@router.post("/health/check", response_model=AnalysisResponse)
async def run_health_check():
    """
    Run a comprehensive health check on all monitored APIs
    """
    try:
        health_results = await health_monitor.run_comprehensive_health_check()
        
        return AnalysisResponse(
            success=True,
            message="Comprehensive health check completed",
            data=health_results
        )
        
    except Exception as e:
        logger.error("Comprehensive health check failed", error=str(e))
        return AnalysisResponse(
            success=False,
            message="Comprehensive health check failed",
            error=str(e)
        )


@router.get("/rate-limits", response_model=AnalysisResponse)
async def get_rate_limit_status():
    """
    Get rate limiting status for all APIs
    """
    try:
        # Get status for all configured APIs
        status_data = {}
        
        # This would be populated with actual API names in a real implementation
        api_names = ["cook_api", "dallas_api", "la_api"]
        
        for api_name in api_names:
            try:
                status = await rate_limiter.get_rate_limit_status(api_name)
                status_data[api_name] = status
            except:
                status_data[api_name] = {"status": "not_configured"}
        
        return AnalysisResponse(
            success=True,
            message="Rate limit status retrieved",
            data=status_data
        )
        
    except Exception as e:
        logger.error("Failed to get rate limit status", error=str(e))
        return AnalysisResponse(
            success=False,
            message="Failed to retrieve rate limit status",
            error=str(e)
        )


@router.get("/field-mappings", response_model=AnalysisResponse)
async def get_field_mappings(county: Optional[str] = Query(None)):
    """
    Get field mappings, optionally filtered by county
    """
    try:
        if county:
            mappings = field_mapper.get_field_mapping_dictionary(county)
            data = {
                "county": county,
                "mappings": mappings
            }
        else:
            stats = field_mapper.get_mapping_statistics()
            data = {
                "statistics": stats,
                "all_counties": list(field_mapper.mapping_cache.keys())
            }
        
        return AnalysisResponse(
            success=True,
            message="Field mappings retrieved",
            data=data
        )
        
    except Exception as e:
        logger.error("Failed to get field mappings", error=str(e))
        return AnalysisResponse(
            success=False,
            message="Failed to retrieve field mappings",
            error=str(e)
        )


@router.post("/field-mappings/discover", response_model=AnalysisResponse)
async def discover_field_mappings(
    county: str,
    sample_data: List[Dict[str, Any]]
):
    """
    Discover potential field mappings from sample data
    """
    try:
        suggested_mappings = field_mapper.discover_new_mappings(sample_data, county)
        
        return AnalysisResponse(
            success=True,
            message=f"Field mapping discovery completed for {county}",
            data={
                "county": county,
                "suggested_mappings": suggested_mappings,
                "sample_count": len(sample_data)
            }
        )
        
    except Exception as e:
        logger.error("Field mapping discovery failed", 
                    county=county, 
                    error=str(e))
        return AnalysisResponse(
            success=False,
            message="Field mapping discovery failed",
            error=str(e)
        )


@router.post("/catalog/refresh", response_model=AnalysisResponse)
async def refresh_catalog(
    background_tasks: BackgroundTasks,
    force_reanalyze: bool = Query(False, description="Force re-analysis of all APIs")
):
    """
    Refresh the API catalog by re-analyzing APIs
    """
    try:
        background_tasks.add_task(
            api_cataloger.refresh_catalog,
            force_reanalyze
        )
        
        return AnalysisResponse(
            success=True,
            message="Catalog refresh started",
            data={
                "status": "refresh_started",
                "force_reanalyze": force_reanalyze
            }
        )
        
    except Exception as e:
        logger.error("Catalog refresh failed", error=str(e))
        return AnalysisResponse(
            success=False,
            message="Failed to start catalog refresh",
            error=str(e)
        )


@router.get("/status", response_model=AnalysisResponse)
async def get_discovery_status():
    """
    Get overall status of the API Discovery Agent
    """
    try:
        # Get catalog summary
        await api_cataloger.load_catalog()
        catalog_summary = api_cataloger.get_catalog_summary()
        
        # Get health monitoring status
        health_status = health_monitor.get_all_health_status()
        
        # Get field mapping statistics
        field_mapping_stats = field_mapper.get_mapping_statistics()
        
        return AnalysisResponse(
            success=True,
            message="API Discovery Agent status retrieved",
            data={
                "catalog": catalog_summary,
                "health_monitoring": {
                    "overall_status": health_status.get("overall_status"),
                    "monitored_apis": health_status.get("monitored_apis"),
                    "monitoring_active": health_status.get("monitoring_active")
                },
                "field_mapping": {
                    "total_counties": field_mapping_stats.get("total_counties"),
                    "counties": list(field_mapping_stats.get("counties", {}).keys())
                },
                "components": {
                    "api_analyzer": "active",
                    "api_cataloger": "active", 
                    "health_monitor": "active",
                    "rate_limiter": "active",
                    "field_mapper": "active"
                }
            }
        )
        
    except Exception as e:
        logger.error("Failed to get discovery status", error=str(e))
        return AnalysisResponse(
            success=False,
            message="Failed to retrieve API Discovery Agent status",
            error=str(e)
        ) 