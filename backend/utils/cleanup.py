"""
Data cleanup utilities
"""

import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy import and_, or_
from .db import get_db_session
from ..models.property import Property
from ..models.financials import PropertyFinancials

logger = logging.getLogger(__name__)

def cleanup_stale_data(days_threshold: int = 30) -> None:
    """
    Clean up stale data that hasn't been updated in the specified number of days
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days_threshold)
    
    with get_db_session() as session:
        stale_properties = session.query(Property).filter(
            Property.updated_at < cutoff_date
        ).all()
        
        for property in stale_properties:
            logger.info(f"Cleaning up stale property: {property.id}")
            session.delete(property)

def cleanup_invalid_financials() -> List[str]:
    """
    Clean up invalid financial data (e.g., negative prices, future dates)
    Returns list of cleaned property IDs
    """
    cleaned_ids = []
    current_date = datetime.utcnow().date()
    
    with get_db_session() as session:
        invalid_financials = session.query(PropertyFinancials).filter(
            or_(
                PropertyFinancials.list_price < 0,
                PropertyFinancials.sale_price < 0,
                PropertyFinancials.estimated_value < 0,
                PropertyFinancials.last_sale_date > current_date
            )
        ).all()
        
        for financial in invalid_financials:
            logger.warning(f"Found invalid financial data for property: {financial.property.id}")
            if financial.list_price and financial.list_price < 0:
                financial.list_price = None
            if financial.sale_price and financial.sale_price < 0:
                financial.sale_price = None
            if financial.estimated_value and financial.estimated_value < 0:
                financial.estimated_value = None
            if financial.last_sale_date and financial.last_sale_date > current_date:
                financial.last_sale_date = None
            
            cleaned_ids.append(financial.property.id)
    
    return cleaned_ids

def vacuum_database() -> None:
    """
    Perform database vacuum to reclaim storage and update statistics
    """
    with get_db_session() as session:
        session.execute("VACUUM ANALYZE")
        logger.info("Database vacuum completed successfully") 