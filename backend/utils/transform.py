from typing import List, Dict, Any, Callable, Optional, TypeVar, Union
from datetime import datetime
from decimal import Decimal
import pandas as pd
import numpy as np
from .validation import ValidatedProperty
from .logger import setup_logger

logger = setup_logger("transform")

T = TypeVar('T')
TransformFunc = Callable[[Any], Any]

class DataTransformer:
    """
    Handles data transformations and normalizations
    """
    def __init__(self):
        self.logger = logger

    def normalize_numeric(
        self,
        value: Union[int, float, str, None],
        default: float = 0.0
    ) -> float:
        """
        Normalizes numeric values
        """
        if value is None:
            return default
            
        try:
            if isinstance(value, str):
                # Remove currency symbols and commas
                value = value.replace('$', '').replace(',', '')
            return float(value)
        except (ValueError, TypeError):
            self.logger.warning(f"Could not normalize numeric value: {value}")
            return default

    def normalize_date(
        self,
        value: Union[str, datetime, None],
        default: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        Normalizes date values
        """
        if value is None:
            return default
            
        if isinstance(value, datetime):
            return value
            
        try:
            if isinstance(value, str):
                # Try common date formats
                formats = [
                    "%Y-%m-%d",
                    "%m/%d/%Y",
                    "%d/%m/%Y",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S"
                ]
                
                for fmt in formats:
                    try:
                        return datetime.strptime(value, fmt)
                    except ValueError:
                        continue
                        
            self.logger.warning(f"Could not parse date value: {value}")
            return default
            
        except Exception as e:
            self.logger.error(f"Error normalizing date: {str(e)}")
            return default

    def normalize_boolean(
        self,
        value: Any,
        default: bool = False
    ) -> bool:
        """
        Normalizes boolean values
        """
        if value is None:
            return default
            
        if isinstance(value, bool):
            return value
            
        if isinstance(value, (int, float)):
            return bool(value)
            
        if isinstance(value, str):
            return value.lower() in ['true', 'yes', '1', 'y', 't']
            
        return default

    def apply_pipeline(
        self,
        data: List[Dict],
        pipeline: List[TransformFunc]
    ) -> List[Dict]:
        """
        Applies a series of transformations to the data
        """
        transformed = data
        for transform in pipeline:
            try:
                transformed = [transform(item) for item in transformed]
            except Exception as e:
                self.logger.error(f"Pipeline transform error: {str(e)}")
                raise
                
        return transformed

    def to_dataframe(
        self,
        properties: List[ValidatedProperty]
    ) -> pd.DataFrame:
        """
        Converts property list to pandas DataFrame
        """
        try:
            # Extract main property attributes
            data = []
            for prop in properties:
                row = {
                    'id': prop.id,
                    'property_type': prop.property_type.value,
                    'zoning_type': prop.zoning_type.value,
                    'latitude': prop.latitude,
                    'longitude': prop.longitude,
                    'address': prop.address.formatted,
                }
                
                # Add metrics
                metrics = prop.metrics.dict()
                row.update({f"metric_{k}": v for k, v in metrics.items()})
                
                # Add financials
                financials = prop.financials.dict()
                row.update({f"financial_{k}": v for k, v in financials.items()})
                
                data.append(row)
                
            return pd.DataFrame(data)
            
        except Exception as e:
            self.logger.error(f"DataFrame conversion error: {str(e)}")
            raise

    def calculate_derived_metrics(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculates derived metrics for properties
        """
        try:
            # Calculate age if year_built is available
            current_year = datetime.now().year
            if 'metric_year_built' in df.columns:
                df['age'] = current_year - df['metric_year_built']

            # Calculate total value if we have price per sqft
            if all(col in df.columns for col in ['metric_total_square_feet', 'financial_price_per_square_foot']):
                df['calculated_total_value'] = df['metric_total_square_feet'] * df['financial_price_per_square_foot']

            # Calculate space utilization
            space_cols = [
                'metric_office_square_feet',
                'metric_warehouse_square_feet',
                'metric_manufacturing_square_feet'
            ]
            
            for col in space_cols:
                if col in df.columns:
                    util_col = f"{col}_utilization"
                    df[util_col] = (df[col] / df['metric_total_square_feet'] * 100).round(2)

            return df
            
        except Exception as e:
            self.logger.error(f"Derived metrics calculation error: {str(e)}")
            raise

    def clean_outliers(
        self,
        df: pd.DataFrame,
        columns: List[str],
        std_dev: float = 3.0
    ) -> pd.DataFrame:
        """
        Removes or caps outliers in specified columns
        """
        try:
            df_clean = df.copy()
            
            for col in columns:
                if col in df.columns and df[col].dtype in ['int64', 'float64']:
                    mean = df[col].mean()
                    std = df[col].std()
                    
                    # Cap values at 3 standard deviations
                    lower_bound = mean - (std_dev * std)
                    upper_bound = mean + (std_dev * std)
                    
                    df_clean[col] = df_clean[col].clip(lower_bound, upper_bound)
                    
            return df_clean
            
        except Exception as e:
            self.logger.error(f"Outlier cleaning error: {str(e)}")
            raise

    def export_csv(
        self,
        df: pd.DataFrame,
        filename: str
    ) -> None:
        """
        Exports DataFrame to CSV file
        """
        try:
            df.to_csv(filename, index=False)
            self.logger.info(f"Data exported to {filename}")
        except Exception as e:
            self.logger.error(f"CSV export error: {str(e)}")
            raise

# Global transformer instance
transformer = DataTransformer() 