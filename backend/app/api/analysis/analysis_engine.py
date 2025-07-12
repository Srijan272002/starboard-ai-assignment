"""
Analysis Engine - Implements advanced property analysis and market insights
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from scipy import stats
from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import Session
import structlog
import json

from app.db.models import Property, PropertyComparable
from app.core.exceptions import StarboardException

logger = structlog.get_logger(__name__)

class AnalysisEngine:
    """Service for advanced property analysis and market insights"""
    
    def __init__(self, db: Session):
        self.db = db
        self.analysis_version = "1.0.0"
    
    def _calculate_data_reliability(self, property_obj: Property) -> Dict[str, float]:
        """Calculate reliability metrics for property data"""
        metrics = {
            'completeness': 0.0,
            'recency': 0.0,
            'consistency': 0.0,
            'source_reliability': 0.0
        }
        
        # Data completeness
        required_fields = [
            'square_footage', 'lot_size', 'year_built', 'latitude', 
            'longitude', 'assessed_value', 'market_value', 'features'
        ]
        present_fields = sum(1 for field in required_fields if getattr(property_obj, field))
        metrics['completeness'] = present_fields / len(required_fields)
        
        # Data recency
        if property_obj.updated_at:
            days_old = (datetime.utcnow() - property_obj.updated_at).days
            metrics['recency'] = max(0, 1 - (days_old / 365))  # Scale over 1 year
        
        # Data consistency
        if property_obj.market_value and property_obj.assessed_value:
            # Check if market value is reasonably higher than assessed value
            ratio = property_obj.market_value / property_obj.assessed_value
            metrics['consistency'] = 1.0 if 1.0 <= ratio <= 2.0 else 0.5
        
        # Source reliability (based on county data quality)
        source_reliability = {
            'cook_county': 0.9,
            'dallas_county': 0.85,
            'la_county': 0.88
        }
        county = property_obj.county.lower().replace(' ', '_')
        metrics['source_reliability'] = source_reliability.get(county, 0.7)
        
        return metrics
    
    def _calculate_uncertainty(self, property_obj: Property, market_data: List[Dict]) -> Dict[str, float]:
        """Calculate uncertainty metrics for property valuation"""
        uncertainties = {
            'value_uncertainty': 0.0,
            'market_volatility': 0.0,
            'prediction_confidence': 0.0
        }
        
        if not market_data:
            return uncertainties
            
        # Value uncertainty based on comparable spread
        if property_obj.market_value:
            comparable_values = [d['market_value'] for d in market_data if d.get('market_value')]
            if comparable_values:
                mean_value = np.mean(comparable_values)
                std_dev = np.std(comparable_values)
                cv = std_dev / mean_value if mean_value else 1.0
                uncertainties['value_uncertainty'] = min(1.0, cv)
        
        # Market volatility
        if len(market_data) >= 2:
            sorted_data = sorted(market_data, key=lambda x: x['date'])
            price_changes = []
            for i in range(1, len(sorted_data)):
                if sorted_data[i].get('market_value') and sorted_data[i-1].get('market_value'):
                    change = abs(sorted_data[i]['market_value'] - sorted_data[i-1]['market_value'])
                    change_pct = change / sorted_data[i-1]['market_value']
                    price_changes.append(change_pct)
            if price_changes:
                uncertainties['market_volatility'] = min(1.0, np.mean(price_changes) * 5)
        
        # Prediction confidence based on data quality and market conditions
        prediction_factors = [
            1 - uncertainties['value_uncertainty'],
            1 - uncertainties['market_volatility'],
            self._calculate_data_reliability(property_obj)['completeness']
        ]
        uncertainties['prediction_confidence'] = np.mean(prediction_factors)
        
        return uncertainties
    
    def _detect_market_trends(self, market_data: List[Dict], window_days: int = 90) -> Dict[str, Any]:
        """Analyze market trends and patterns"""
        if not market_data:
            return {
                'price_trend': 'stable',
                'trend_strength': 0.0,
                'seasonal_pattern': None,
                'trend_details': {}
            }
            
        # Sort data by date
        sorted_data = sorted(market_data, key=lambda x: x['date'])
        
        # Calculate price trends
        values = [d['market_value'] for d in sorted_data if d.get('market_value')]
        dates = [d['date'] for d in sorted_data if d.get('market_value')]
        
        if len(values) < 2:
            return {
                'price_trend': 'insufficient_data',
                'trend_strength': 0.0,
                'seasonal_pattern': None,
                'trend_details': {}
            }
        
        # Linear regression for trend
        x = np.arange(len(values))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, values)
        
        # Determine trend direction and strength
        trend_strength = abs(r_value)
        if slope > 0:
            trend = 'increasing' if trend_strength > 0.5 else 'slightly_increasing'
        elif slope < 0:
            trend = 'decreasing' if trend_strength > 0.5 else 'slightly_decreasing'
        else:
            trend = 'stable'
        
        # Check for seasonality (if enough data)
        seasonal_pattern = None
        if len(values) >= 365:  # At least a year of data
            # Simple seasonal decomposition
            try:
                from statsmodels.tsa.seasonal import seasonal_decompose
                result = seasonal_decompose(values, period=90)  # Quarterly seasonality
                seasonal_pattern = 'present' if np.std(result.seasonal) > np.std(values) * 0.1 else 'none'
            except:
                seasonal_pattern = 'unknown'
        
        return {
            'price_trend': trend,
            'trend_strength': trend_strength,
            'seasonal_pattern': seasonal_pattern,
            'trend_details': {
                'slope': slope,
                'r_squared': r_value ** 2,
                'p_value': p_value,
                'std_err': std_err
            }
        }
    
    def _detect_anomalies(self, property_obj: Property, market_data: List[Dict]) -> Dict[str, Any]:
        """Detect anomalies in property data and market behavior"""
        anomalies = {
            'value_anomalies': [],
            'feature_anomalies': [],
            'market_anomalies': []
        }
        
        if not market_data:
            return anomalies
        
        # Value anomalies
        if property_obj.market_value:
            comparable_values = [d['market_value'] for d in market_data if d.get('market_value')]
            if comparable_values:
                mean_value = np.mean(comparable_values)
                std_dev = np.std(comparable_values)
                z_score = (property_obj.market_value - mean_value) / std_dev if std_dev else 0
                
                if abs(z_score) > 2:
                    anomalies['value_anomalies'].append({
                        'type': 'price_outlier',
                        'severity': abs(z_score),
                        'description': 'Property value significantly different from market average'
                    })
        
        # Feature anomalies
        if property_obj.features:
            feature_stats = {}
            for d in market_data:
                if d.get('features'):
                    for k, v in d['features'].items():
                        if isinstance(v, (int, float)):
                            feature_stats.setdefault(k, []).append(v)
            
            for feature, values in feature_stats.items():
                if feature in property_obj.features and isinstance(property_obj.features[feature], (int, float)):
                    mean_val = np.mean(values)
                    std_dev = np.std(values)
                    if std_dev:
                        z_score = (property_obj.features[feature] - mean_val) / std_dev
                        if abs(z_score) > 2:
                            anomalies['feature_anomalies'].append({
                                'type': f'{feature}_outlier',
                                'severity': abs(z_score),
                                'description': f'Unusual {feature} value compared to market'
                            })
        
        # Market anomalies
        if len(market_data) >= 2:
            sorted_data = sorted(market_data, key=lambda x: x['date'])
            price_changes = []
            for i in range(1, len(sorted_data)):
                if sorted_data[i].get('market_value') and sorted_data[i-1].get('market_value'):
                    change = (sorted_data[i]['market_value'] - sorted_data[i-1]['market_value'])
                    change_pct = change / sorted_data[i-1]['market_value']
                    price_changes.append(change_pct)
            
            if price_changes:
                mean_change = np.mean(price_changes)
                std_dev = np.std(price_changes)
                
                for i, change in enumerate(price_changes):
                    if std_dev and abs((change - mean_change) / std_dev) > 2:
                        anomalies['market_anomalies'].append({
                            'type': 'price_volatility',
                            'date': sorted_data[i+1]['date'].strftime('%Y-%m-%d'),
                            'severity': abs((change - mean_change) / std_dev),
                            'description': 'Unusual price change detected'
                        })
        
        return anomalies
    
    async def analyze_property(self, property_id: int, lookback_days: int = 365) -> Dict[str, Any]:
        """
        Perform comprehensive property analysis
        
        Args:
            property_id: ID of the property to analyze
            lookback_days: Number of days of historical data to analyze
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            # Get property
            property_obj = self.db.query(Property).filter(Property.id == property_id).first()
            if not property_obj:
                raise StarboardException(f"Property with ID {property_id} not found")
            
            # Get historical market data
            start_date = datetime.utcnow() - timedelta(days=lookback_days)
            market_data = self.db.query(Property).filter(
                Property.county == property_obj.county,
                Property.property_type == property_obj.property_type,
                Property.created_at >= start_date
            ).all()
            
            market_data_list = []
            for prop in market_data:
                market_data_list.append({
                    'date': prop.created_at,
                    'market_value': prop.market_value,
                    'features': prop.features
                })
            
            # Calculate reliability metrics
            reliability_metrics = self._calculate_data_reliability(property_obj)
            
            # Calculate uncertainty metrics
            uncertainty_metrics = self._calculate_uncertainty(property_obj, market_data_list)
            
            # Analyze market trends
            market_trends = self._detect_market_trends(market_data_list)
            
            # Detect anomalies
            anomalies = self._detect_anomalies(property_obj, market_data_list)
            
            # Calculate overall confidence score
            confidence_factors = [
                reliability_metrics['completeness'],
                reliability_metrics['recency'],
                reliability_metrics['consistency'],
                reliability_metrics['source_reliability'],
                1 - uncertainty_metrics['value_uncertainty'],
                1 - uncertainty_metrics['market_volatility'],
                uncertainty_metrics['prediction_confidence']
            ]
            overall_confidence = np.mean(confidence_factors)
            
            # Prepare analysis report
            analysis_report = {
                'property_id': property_id,
                'analysis_date': datetime.utcnow().isoformat(),
                'analysis_version': self.analysis_version,
                
                'confidence_metrics': {
                    'overall_confidence': overall_confidence,
                    'reliability_metrics': reliability_metrics,
                    'uncertainty_metrics': uncertainty_metrics
                },
                
                'market_analysis': {
                    'trends': market_trends,
                    'anomalies': anomalies,
                    'market_size': len(market_data),
                    'data_timespan': {
                        'start': start_date.isoformat(),
                        'end': datetime.utcnow().isoformat()
                    }
                },
                
                'recommendations': []
            }
            
            # Generate recommendations based on analysis
            if overall_confidence < 0.6:
                analysis_report['recommendations'].append({
                    'type': 'data_quality',
                    'priority': 'high',
                    'message': 'Improve data quality by updating missing or outdated information'
                })
            
            if uncertainty_metrics['market_volatility'] > 0.7:
                analysis_report['recommendations'].append({
                    'type': 'market_monitoring',
                    'priority': 'high',
                    'message': 'Monitor market closely due to high volatility'
                })
            
            if anomalies['value_anomalies']:
                analysis_report['recommendations'].append({
                    'type': 'valuation_review',
                    'priority': 'medium',
                    'message': 'Review property valuation due to detected anomalies'
                })
            
            logger.info("Property analysis completed",
                       property_id=property_id,
                       confidence=overall_confidence)
            
            return analysis_report
            
        except Exception as e:
            logger.error("Failed to analyze property",
                        property_id=property_id,
                        error=str(e))
            raise 