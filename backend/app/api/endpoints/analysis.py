"""
Analysis Endpoints - API endpoints for property analysis and market insights
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.api.analysis.analysis_engine import AnalysisEngine

logger = get_logger(__name__)
router = APIRouter()


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ConfidenceMetrics(BaseModel):
    """Model for confidence metrics"""
    overall_confidence: float
    reliability_metrics: Dict[str, float]
    uncertainty_metrics: Dict[str, float]


class MarketTrend(BaseModel):
    """Model for market trend data"""
    price_trend: str
    trend_strength: float
    seasonal_pattern: Optional[str]
    trend_details: Dict[str, Any]


class Anomaly(BaseModel):
    """Model for anomaly data"""
    type: str
    severity: float
    description: str
    date: Optional[str] = None


class MarketAnalysis(BaseModel):
    """Model for market analysis data"""
    trends: MarketTrend
    anomalies: Dict[str, List[Anomaly]]
    market_size: int
    data_timespan: Dict[str, str]


class Recommendation(BaseModel):
    """Model for analysis recommendations"""
    type: str
    priority: str
    message: str


class AnalysisReport(BaseModel):
    """Model for complete analysis report"""
    property_id: int
    analysis_date: str
    analysis_version: str
    confidence_metrics: ConfidenceMetrics
    market_analysis: MarketAnalysis
    recommendations: List[Recommendation]

    class Config:
        from_attributes = True


@router.get("/{property_id}", response_model=AnalysisReport)
async def analyze_property(
    property_id: int,
    lookback_days: int = Query(365, ge=30, le=3650),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive analysis for a property
    
    Args:
        property_id: ID of the property to analyze
        lookback_days: Number of days of historical data to analyze (30-3650 days)
    """
    try:
        # Initialize analysis engine
        analysis_engine = AnalysisEngine(db)
        
        # Perform analysis
        analysis_report = await analysis_engine.analyze_property(
            property_id=property_id,
            lookback_days=lookback_days
        )
        
        return AnalysisReport(**analysis_report)
        
    except Exception as e:
        logger.error("Failed to analyze property", 
                    property_id=property_id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze property: {str(e)}"
        ) 