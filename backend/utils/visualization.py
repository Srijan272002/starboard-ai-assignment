from typing import List, Dict, Optional
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from .validation import ValidatedProperty
from .market_analysis import market_analyzer
from .transform import DataTransformer
from .logger import setup_logger

logger = setup_logger("visualization")

class Visualization:
    """
    Handles data visualization and report generation
    """
    def __init__(self):
        self.logger = logger
        self.transformer = DataTransformer()

    def create_market_trend_chart(
        self,
        properties: List[ValidatedProperty],
        timeframe_months: int = 12
    ) -> Dict:
        """
        Creates a market trend visualization
        """
        try:
            # Get market trends
            trends = market_analyzer.analyze_market_trends(properties, timeframe_months)
            if not trends or 'price_trends' not in trends:
                return {}

            # Create price trend chart
            monthly_data = pd.DataFrame(trends['price_trends']['monthly_data'])
            
            fig = go.Figure()
            
            # Add mean price line
            fig.add_trace(go.Scatter(
                x=monthly_data.index,
                y=monthly_data['financial_price_per_square_foot']['mean'],
                mode='lines+markers',
                name='Mean Price/sqft',
                line=dict(color='blue')
            ))
            
            # Add confidence interval
            std_dev = monthly_data['financial_price_per_square_foot']['std']
            mean_price = monthly_data['financial_price_per_square_foot']['mean']
            
            fig.add_trace(go.Scatter(
                x=monthly_data.index,
                y=mean_price + std_dev,
                mode='lines',
                name='Upper Bound',
                line=dict(width=0),
                showlegend=False
            ))
            
            fig.add_trace(go.Scatter(
                x=monthly_data.index,
                y=mean_price - std_dev,
                mode='lines',
                name='Lower Bound',
                fill='tonexty',
                line=dict(width=0),
                showlegend=False
            ))
            
            fig.update_layout(
                title='Market Price Trends',
                xaxis_title='Month',
                yaxis_title='Price per Square Foot',
                hovermode='x unified'
            )
            
            return {
                'chart': fig.to_json(),
                'trend_direction': trends['price_trends']['direction'],
                'price_volatility': trends['price_trends']['price_volatility']
            }
            
        except Exception as e:
            self.logger.error(f"Market trend chart creation error: {str(e)}")
            return {}

    def create_location_heatmap(
        self,
        properties: List[ValidatedProperty]
    ) -> Dict:
        """
        Creates a location-based price heatmap
        """
        try:
            df = self.transformer.to_dataframe(properties)
            
            fig = go.Figure(go.Densitymapbox(
                lat=df['latitude'],
                lon=df['longitude'],
                z=df['financial_price_per_square_foot'],
                radius=20,
                colorscale='Viridis',
                showscale=True
            ))
            
            fig.update_layout(
                mapbox_style='stamen-terrain',
                mapbox=dict(
                    center=dict(
                        lat=df['latitude'].mean(),
                        lon=df['longitude'].mean()
                    ),
                    zoom=10
                ),
                title='Property Price Heatmap',
                margin=dict(l=0, r=0, t=30, b=0)
            )
            
            return {
                'chart': fig.to_json(),
                'center': {
                    'latitude': float(df['latitude'].mean()),
                    'longitude': float(df['longitude'].mean())
                }
            }
            
        except Exception as e:
            self.logger.error(f"Location heatmap creation error: {str(e)}")
            return {}

    def create_property_comparison_chart(
        self,
        target_property: ValidatedProperty,
        comparables: List[ValidatedProperty]
    ) -> Dict:
        """
        Creates a radar chart comparing property characteristics
        """
        try:
            # Prepare data
            properties = [target_property] + comparables
            
            metrics = ['total_square_feet', 'year_built', 'price_per_square_foot']
            data = []
            
            for prop in properties:
                data.append([
                    prop.metrics.total_square_feet,
                    prop.metrics.year_built or 0,
                    prop.financials.price_per_square_foot or 0
                ])
            
            # Normalize values
            normalized_data = []
            for metric_idx in range(len(metrics)):
                values = [row[metric_idx] for row in data]
                min_val = min(values)
                max_val = max(values)
                if max_val > min_val:
                    normalized = [(v - min_val) / (max_val - min_val) for v in values]
                else:
                    normalized = [0.5 for _ in values]
                for idx, norm_val in enumerate(normalized):
                    if len(normalized_data) <= idx:
                        normalized_data.append([])
                    normalized_data[idx].append(norm_val)
            
            # Create radar chart
            fig = go.Figure()
            
            # Add target property
            fig.add_trace(go.Scatterpolar(
                r=normalized_data[0],
                theta=metrics,
                fill='toself',
                name='Target Property'
            ))
            
            # Add comparables
            for idx, comp_data in enumerate(normalized_data[1:]):
                fig.add_trace(go.Scatterpolar(
                    r=comp_data,
                    theta=metrics,
                    fill='toself',
                    name=f'Comparable {idx + 1}'
                ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 1]
                    )
                ),
                title='Property Comparison',
                showlegend=True
            )
            
            return {
                'chart': fig.to_json(),
                'metrics': metrics
            }
            
        except Exception as e:
            self.logger.error(f"Property comparison chart creation error: {str(e)}")
            return {}

    def create_market_segment_chart(
        self,
        properties: List[ValidatedProperty]
    ) -> Dict:
        """
        Creates charts showing market segment analysis
        """
        try:
            # Get market analysis
            trends = market_analyzer.analyze_market_trends(properties)
            if not trends or 'market_segments' not in trends:
                return {}
                
            segments = trends['market_segments']
            
            # Create bar chart for segment distribution
            segment_data = {
                'segment': [],
                'count': [],
                'avg_price': []
            }
            
            for segment, data in segments.items():
                segment_data['segment'].append(segment)
                segment_data['count'].append(data['count'])
                segment_data['avg_price'].append(data['avg_price_sqft'])
            
            df = pd.DataFrame(segment_data)
            
            # Create segment distribution chart
            fig1 = go.Figure(data=[
                go.Bar(
                    x=df['segment'],
                    y=df['count'],
                    name='Property Count'
                )
            ])
            
            fig1.update_layout(
                title='Market Segment Distribution',
                xaxis_title='Segment',
                yaxis_title='Number of Properties'
            )
            
            # Create average price chart
            fig2 = go.Figure(data=[
                go.Bar(
                    x=df['segment'],
                    y=df['avg_price'],
                    name='Average Price/sqft'
                )
            ])
            
            fig2.update_layout(
                title='Average Price by Segment',
                xaxis_title='Segment',
                yaxis_title='Price per Square Foot'
            )
            
            return {
                'distribution_chart': fig1.to_json(),
                'price_chart': fig2.to_json(),
                'segment_data': segments
            }
            
        except Exception as e:
            self.logger.error(f"Market segment chart creation error: {str(e)}")
            return {}

    def generate_property_report(
        self,
        property: ValidatedProperty,
        comparables: List[ValidatedProperty],
        market_data: Dict
    ) -> Dict:
        """
        Generates a comprehensive property report with visualizations
        """
        try:
            report = {
                'timestamp': datetime.now().isoformat(),
                'property_details': {
                    'id': property.id,
                    'address': property.address.formatted,
                    'property_type': property.property_type,
                    'metrics': property.metrics.dict(),
                    'financials': property.financials.dict()
                },
                'market_analysis': {
                    'trends': self.create_market_trend_chart([property] + comparables),
                    'location': self.create_location_heatmap([property] + comparables),
                    'comparables': self.create_property_comparison_chart(property, comparables),
                    'segments': self.create_market_segment_chart([property] + comparables)
                },
                'price_adjustments': market_analyzer.calculate_price_adjustments(
                    property,
                    comparables,
                    market_data
                )
            }
            
            return report
            
        except Exception as e:
            self.logger.error(f"Property report generation error: {str(e)}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

# Global visualization instance
visualizer = Visualization() 