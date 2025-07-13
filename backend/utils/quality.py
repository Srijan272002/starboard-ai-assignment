from typing import List, Dict, Optional, Union, Any
import pandas as pd
import numpy as np
from datetime import datetime
from .validation import ValidatedProperty
from .outliers import outlier_detector
from .logger import setup_logger

logger = setup_logger("quality")

class DataQualityMetrics:
    """
    Calculates and tracks data quality metrics
    """
    def __init__(self):
        self.logger = logger

    def calculate_completeness(
        self,
        properties: List[ValidatedProperty]
    ) -> Dict[str, float]:
        """
        Calculates completeness metrics for each field
        """
        try:
            df = pd.DataFrame([p.dict() for p in properties])
            
            # Flatten nested structures
            df = pd.json_normalize(df.to_dict('records'))
            
            # Calculate completeness for each column
            completeness = {}
            for col in df.columns:
                if col != 'raw_data':  # Skip raw data field
                    non_null = df[col].notna().sum()
                    total = len(df)
                    completeness[col] = (non_null / total) * 100
                    
            return completeness
            
        except Exception as e:
            self.logger.error(f"Completeness calculation error: {str(e)}")
            return {}

    def calculate_accuracy(
        self,
        properties: List[ValidatedProperty]
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculates accuracy metrics
        """
        try:
            accuracy_metrics = {
                'value_ranges': self._check_value_ranges(properties),
                'outlier_impact': self._calculate_outlier_impact(properties),
                'data_consistency': self._check_data_consistency(properties)
            }
            
            return accuracy_metrics
            
        except Exception as e:
            self.logger.error(f"Accuracy calculation error: {str(e)}")
            return {}

    def _check_value_ranges(
        self,
        properties: List[ValidatedProperty]
    ) -> Dict[str, Dict[str, float]]:
        """
        Checks if values fall within expected ranges
        """
        try:
            metrics = {}
            
            # Convert to DataFrame for easier analysis
            df = pd.DataFrame([{
                'total_square_feet': p.metrics.total_square_feet,
                'price_per_sqft': p.financials.price_per_square_foot or 0,
                'year_built': p.metrics.year_built or 0,
                'ceiling_height': p.metrics.ceiling_height or 0,
                'cap_rate': p.financials.cap_rate or 0,
                'occupancy_rate': p.financials.occupancy_rate or 0
            } for p in properties])
            
            # Define expected ranges
            ranges = {
                'total_square_feet': (1000, 1000000),
                'price_per_sqft': (10, 1000),
                'year_built': (1800, datetime.now().year),
                'ceiling_height': (8, 100),
                'cap_rate': (0, 20),
                'occupancy_rate': (0, 100)
            }
            
            for col, (min_val, max_val) in ranges.items():
                if col in df.columns:
                    valid_count = df[
                        (df[col] >= min_val) & 
                        (df[col] <= max_val)
                    ].shape[0]
                    
                    metrics[col] = {
                        'valid_percentage': (valid_count / len(df)) * 100,
                        'min_value': df[col].min(),
                        'max_value': df[col].max(),
                        'expected_min': min_val,
                        'expected_max': max_val
                    }
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Value range check error: {str(e)}")
            return {}

    def _calculate_outlier_impact(
        self,
        properties: List[ValidatedProperty]
    ) -> Dict[str, float]:
        """
        Calculates the impact of outliers on data quality
        """
        try:
            # Get outlier summary
            summary = outlier_detector.get_outlier_summary(properties)
            
            impact_metrics = {
                'total_outliers_percentage': sum(
                    summary['outlier_counts'].values()
                ) / (len(properties) * 4) * 100,  # 4 numeric metrics per property
                'high_confidence_outliers_percentage': len(
                    summary['high_confidence_outliers']
                ) / len(properties) * 100,
                'metrics_affected_count': len(summary['metrics_affected'])
            }
            
            return impact_metrics
            
        except Exception as e:
            self.logger.error(f"Outlier impact calculation error: {str(e)}")
            return {}

    def _check_data_consistency(
        self,
        properties: List[ValidatedProperty]
    ) -> Dict[str, float]:
        """
        Checks for data consistency and relationships
        """
        try:
            consistency_checks = {
                'valid_coordinates': 0,
                'valid_address': 0,
                'valid_financials': 0,
                'valid_metrics': 0
            }
            
            total = len(properties)
            if total == 0:
                return {k: 100.0 for k in consistency_checks}
            
            for prop in properties:
                # Check coordinates
                if (-90 <= prop.latitude <= 90 and 
                    -180 <= prop.longitude <= 180):
                    consistency_checks['valid_coordinates'] += 1
                
                # Check address
                if all([
                    prop.address.street,
                    prop.address.city,
                    prop.address.state,
                    prop.address.zip_code
                ]):
                    consistency_checks['valid_address'] += 1
                
                # Check financials
                if any([
                    prop.financials.last_sale_price,
                    prop.financials.current_value,
                    prop.financials.price_per_square_foot
                ]):
                    consistency_checks['valid_financials'] += 1
                
                # Check metrics
                if all([
                    prop.metrics.total_square_feet > 0,
                    prop.metrics.year_built is not None
                ]):
                    consistency_checks['valid_metrics'] += 1
            
            # Convert to percentages
            return {
                k: (v / total) * 100 
                for k, v in consistency_checks.items()
            }
            
        except Exception as e:
            self.logger.error(f"Data consistency check error: {str(e)}")
            return {}

    def generate_quality_report(
        self,
        properties: List[ValidatedProperty]
    ) -> Dict[str, Any]:
        """
        Generates a comprehensive data quality report
        """
        try:
            report = {
                'timestamp': datetime.now().isoformat(),
                'total_properties': len(properties),
                'completeness': self.calculate_completeness(properties),
                'accuracy': self.calculate_accuracy(properties),
                'quality_score': self._calculate_quality_score(properties)
            }
            
            return report
            
        except Exception as e:
            self.logger.error(f"Quality report generation error: {str(e)}")
            return {
                'timestamp': datetime.now().isoformat(),
                'total_properties': len(properties),
                'error': str(e)
            }

    def _calculate_quality_score(
        self,
        properties: List[ValidatedProperty]
    ) -> float:
        """
        Calculates an overall data quality score
        """
        try:
            weights = {
                'completeness': 0.3,
                'accuracy': 0.3,
                'consistency': 0.2,
                'outlier_impact': 0.2
            }
            
            # Get metrics
            completeness = self.calculate_completeness(properties)
            accuracy = self.calculate_accuracy(properties)
            consistency = self._check_data_consistency(properties)
            
            # Calculate component scores
            completeness_score = np.mean(list(completeness.values()))
            accuracy_score = np.mean([
                np.mean([m['valid_percentage'] for m in accuracy['value_ranges'].values()]),
                100 - accuracy['outlier_impact']['total_outliers_percentage']
            ])
            consistency_score = np.mean(list(consistency.values()))
            outlier_score = 100 - accuracy['outlier_impact']['total_outliers_percentage']
            
            # Calculate weighted average
            quality_score = (
                completeness_score * weights['completeness'] +
                accuracy_score * weights['accuracy'] +
                consistency_score * weights['consistency'] +
                outlier_score * weights['outlier_impact']
            )
            
            return round(quality_score, 2)
            
        except Exception as e:
            self.logger.error(f"Quality score calculation error: {str(e)}")
            return 0.0

# Global quality metrics instance
quality_metrics = DataQualityMetrics() 