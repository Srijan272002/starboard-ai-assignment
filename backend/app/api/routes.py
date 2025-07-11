from fastapi import APIRouter
from app.api.endpoints import properties, comparables, health

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(properties.router, prefix="/properties", tags=["properties"])
api_router.include_router(comparables.router, prefix="/comparables", tags=["comparables"]) 