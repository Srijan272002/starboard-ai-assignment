from typing import List, Dict, Optional, Tuple, Union
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from .validation import ValidatedProperty
from .logger import setup_logger

logger = setup_logger("outliers")

class OutlierDetector:
    """
    Detects outliers using various statistical methods
    """
    def __init__(self):
        self.logger = logger
        self.scaler = StandardScaler()

    def detect_zscore_outliers(
        self,
        data: Union[List[float], np.ndarray],
        threshold: float = 3.0
    ) -> List[int]:
        """
        Detects outliers using Z-score method
        """
        try:
            if len(data) < 2:
                return []

            z_scores = np.abs(stats.zscore(data))
            return [i for i, z in enumerate(z_scores) if z > threshold]
        except Exception as e:
            self.logger.error(f"Z-score outlier detection error: {str(e)}")
            return []

    def detect_iqr_outliers(
        self,
        data: Union[List[float], np.ndarray],
        multiplier: float = 1.5
    ) -> List[int]:
        """
        Detects outliers using IQR method
        """
        try:
            if len(data) < 4:  # Need at least 4 points for meaningful quartiles
                return []

            q1 = np.percentile(data, 25)
            q3 = np.percentile(data, 75)
            iqr = q3 - q1
            
            lower_bound = q1 - (multiplier * iqr)
            upper_bound = q3 + (multiplier * iqr)
            
            return [i for i, x in enumerate(data) if x < lower_bound or x > upper_bound]
        except Exception as e:
            self.logger.error(f"IQR outlier detection error: {str(e)}")
            return []

    def detect_isolation_forest_outliers(
        self,
        data: Union[List[float], np.ndarray],
        contamination: float = 0.1
    ) -> List[int]:
        """
        Detects outliers using Isolation Forest algorithm
        """
        try:
            if len(data) < 10:  # Need reasonable sample size for IF
                return []

            # Reshape for sklearn if needed
            X = np.array(data).reshape(-1, 1)
            
            # Fit and predict
            iso_forest = IsolationForest(
                contamination=contamination,
                random_state=42
            )
            predictions = iso_forest.fit_predict(X)
            
            # Return indices where predictions are -1 (outliers)
            return [i for i, pred in enumerate(predictions) if pred == -1]
        except Exception as e:
            self.logger.error(f"Isolation Forest outlier detection error: {str(e)}")
            return []

    def detect_property_outliers(
        self,
        properties: List[ValidatedProperty],
        methods: List[str] = ['zscore', 'iqr', 'isolation_forest']
    ) -> Dict[str, List[Dict]]:
        """
        Detects outliers in property data using multiple methods
        """
        try:
            # Convert properties to DataFrame for analysis
            df = pd.DataFrame([{
                'id': p.id,
                'total_square_feet': p.metrics.total_square_feet,
                'price_per_sqft': p.financials.price_per_square_foot or 0,
                'year_built': p.metrics.year_built or 0,
                'ceiling_height': p.metrics.ceiling_height or 0,
            } for p in properties])

            results = {}
            numeric_columns = [
                'total_square_feet',
                'price_per_sqft',
                'year_built',
                'ceiling_height'
            ]

            for method in methods:
                method_results = []
                
                for col in numeric_columns:
                    if df[col].nunique() > 1:  # Skip if no variation
                        data = df[col].values
                        outlier_indices = []
                        
                        if method == 'zscore':
                            outlier_indices = self.detect_zscore_outliers(data)
                        elif method == 'iqr':
                            outlier_indices = self.detect_iqr_outliers(data)
                        elif method == 'isolation_forest':
                            outlier_indices = self.detect_isolation_forest_outliers(data)
                        
                        # Add outliers to results
                        for idx in outlier_indices:
                            method_results.append({
                                'property_id': df.iloc[idx]['id'],
                                'metric': col,
                                'value': df.iloc[idx][col],
                                'confidence': self._calculate_outlier_confidence(
                                    df.iloc[idx][col],
                                    data
                                )
                            })
                
                results[method] = method_results

            return results
            
        except Exception as e:
            self.logger.error(f"Property outlier detection error: {str(e)}")
            return {method: [] for method in methods}

    def _calculate_outlier_confidence(
        self,
        value: float,
        data: np.ndarray,
        max_zscore: float = 5.0
    ) -> float:
        """
        Calculates confidence score for outlier detection
        """
        try:
            z_score = abs(stats.zscore([value] + list(data))[0])
            return min(z_score / max_zscore, 1.0)
        except Exception:
            return 0.0

    def get_outlier_summary(
        self,
        properties: List[ValidatedProperty]
    ) -> Dict[str, Dict]:
        """
        Generates summary statistics and outlier information
        """
        try:
            # Get outliers using all methods
            outliers = self.detect_property_outliers(properties)
            
            # Calculate summary statistics
            summary = {
                'total_properties': len(properties),
                'outlier_counts': {
                    method: len(outliers[method])
                    for method in outliers
                },
                'metrics_affected': {},
                'high_confidence_outliers': []
            }
            
            # Analyze outliers
            for method, method_outliers in outliers.items():
                for outlier in method_outliers:
                    metric = outlier['metric']
                    
                    # Count metrics affected
                    if metric not in summary['metrics_affected']:
                        summary['metrics_affected'][metric] = 0
                    summary['metrics_affected'][metric] += 1
                    
                    # Track high confidence outliers
                    if outlier['confidence'] > 0.8:
                        summary['high_confidence_outliers'].append({
                            'property_id': outlier['property_id'],
                            'metric': metric,
                            'value': outlier['value'],
                            'confidence': outlier['confidence'],
                            'method': method
                        })
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Outlier summary error: {str(e)}")
            return {
                'total_properties': len(properties),
                'outlier_counts': {},
                'metrics_affected': {},
                'high_confidence_outliers': []
            }

# Global outlier detector instance
outlier_detector = OutlierDetector() 