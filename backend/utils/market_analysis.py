"""
Market analysis utilities for processing and analyzing real estate data
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from statistics import mean, median, stdev
from collections import defaultdict
from backend.utils.cache import cache_result
from backend.utils.db import get_session_maker
from backend.models.property import Property
from backend.models.financials import PropertyFinancials
from backend.models.metrics import PropertyMetrics
from sqlalchemy import select, and_, func
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

@cache_result(ttl=300)  # Cache for 5 minutes
async def get_market_trends(start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """
    Get market trends data including:
    - Median price trends
    - Average price per sqft
    - Total sales volume
    - Price change percentage
    """
    try:
        session_maker = get_session_maker()
        async with session_maker() as session:
            # Query property sales data with proper joins
            stmt = select(
                PropertyFinancials.last_sale_date,
                PropertyFinancials.sale_price,
                PropertyMetrics.square_footage
            ).select_from(
                PropertyFinancials.join(Property, PropertyFinancials.id == Property.financials_id)
                .join(PropertyMetrics, Property.metrics_id == PropertyMetrics.id)
            ).where(
                and_(
                    PropertyFinancials.last_sale_date >= start_date,
                    PropertyFinancials.last_sale_date <= end_date,
                    PropertyFinancials.sale_price.isnot(None)  # Ensure we have a sale price
                )
            ).order_by(PropertyFinancials.last_sale_date)

            result = await session.execute(stmt)
            sales_data = result.fetchall()

            if not sales_data:
                logger.warning(f"No sales data found between {start_date} and {end_date}")
                return {
                    "median_prices": [],
                    "price_per_sqft": [],
                    "sales_volume": [],
                    "price_change": 0
                }

            # Process data by month
            monthly_data = defaultdict(list)
            for sale_date, price, sqft in sales_data:
                if price is None:
                    continue  # Skip entries with no price
                    
                month_key = sale_date.strftime("%Y-%m")
                if sqft and sqft > 0:  # Avoid division by zero
                    monthly_data[month_key].append({
                        "price": price,
                        "price_per_sqft": price / sqft
                    })
                else:
                    monthly_data[month_key].append({
                        "price": price,
                        "price_per_sqft": None  # Mark as None to filter out later
                    })

            # Calculate monthly metrics
            monthly_metrics = []
            for month in sorted(monthly_data.keys()):
                prices = [item["price"] for item in monthly_data[month]]
                price_per_sqft = [item["price_per_sqft"] for item in monthly_data[month] if item["price_per_sqft"] is not None]
                
                monthly_metrics.append({
                    "date": month,
                    "median_price": median(prices) if prices else 0,
                    "avg_price": mean(prices) if prices else 0,
                    "total_volume": sum(prices),
                    "num_sales": len(prices),
                    "median_price_per_sqft": median(price_per_sqft) if price_per_sqft else 0,
                    "avg_price_per_sqft": mean(price_per_sqft) if price_per_sqft else 0
                })

            # Calculate price change percentage
            if len(monthly_metrics) >= 2:
                first_month = monthly_metrics[0]["median_price"]
                last_month = monthly_metrics[-1]["median_price"]
                if first_month > 0:
                    price_change = ((last_month - first_month) / first_month) * 100
                else:
                    price_change = 0
            else:
                price_change = 0

            return {
                "median_prices": monthly_metrics,
                "price_per_sqft": [m["median_price_per_sqft"] for m in monthly_metrics],
                "sales_volume": [m["total_volume"] for m in monthly_metrics],
                "price_change": round(price_change, 2)
            }

    except SQLAlchemyError as e:
        logger.error(f"Database error in get_market_trends: {str(e)}")
        return {
            "median_prices": [],
            "price_per_sqft": [],
            "sales_volume": [],
            "price_change": 0
        }
    except Exception as e:
        logger.error(f"Error in get_market_trends: {str(e)}")
        return {
            "median_prices": [],
            "price_per_sqft": [],
            "sales_volume": [],
            "price_change": 0
        }

@cache_result(ttl=300)  # Cache for 5 minutes
async def get_price_distribution() -> Dict[str, Any]:
    """
    Get current price distribution data including:
    - Price range buckets
    - Property counts per bucket
    - Statistical measures (mean, median, std dev)
    """
    try:
        session_maker = get_session_maker()
        async with session_maker() as session:
            # Get recent sales (last 6 months)
            six_months_ago = datetime.now() - timedelta(days=180)
            stmt = select(PropertyFinancials.sale_price).where(
                and_(
                    PropertyFinancials.last_sale_date >= six_months_ago,
                    PropertyFinancials.sale_price.isnot(None)
                )
            )

            result = await session.execute(stmt)
            prices = [row[0] for row in result.fetchall()]

            if not prices:
                logger.warning("No price data found for distribution analysis")
                return {
                    "distribution": [],
                    "stats": {
                        "mean": 0,
                        "median": 0,
                        "std_dev": 0
                    }
                }

            # Calculate basic statistics
            price_mean = mean(prices)
            price_median = median(prices)
            price_std_dev = stdev(prices) if len(prices) > 1 else 0

            # Create price range buckets
            min_price = min(prices)
            max_price = max(prices)
            
            # Create 10 buckets for price distribution
            if min_price == max_price:
                buckets = [(min_price, max_price)]
            else:
                step = (max_price - min_price) / 10
                buckets = [(min_price + i * step, min_price + (i + 1) * step) for i in range(10)]

            # Count properties in each bucket
            distribution = []
            for start, end in buckets:
                count = sum(1 for price in prices if start <= price <= end)
                distribution.append({
                    "range": [start, end],
                    "count": count
                })

            return {
                "distribution": distribution,
                "stats": {
                    "mean": round(price_mean, 2),
                    "median": round(price_median, 2),
                    "std_dev": round(price_std_dev, 2)
                }
            }

    except SQLAlchemyError as e:
        logger.error(f"Database error in get_price_distribution: {str(e)}")
        return {
            "distribution": [],
            "stats": {
                "mean": 0,
                "median": 0,
                "std_dev": 0
            }
        }
    except Exception as e:
        logger.error(f"Error in get_price_distribution: {str(e)}")
        return {
            "distribution": [],
            "stats": {
                "mean": 0,
                "median": 0,
                "std_dev": 0
            }
        } 