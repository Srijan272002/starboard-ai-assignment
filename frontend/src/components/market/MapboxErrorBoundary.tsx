'use client'

import React, { Component, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class MapboxErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    // Check if the error is related to Mapbox telemetry being blocked
    const isMapboxTelemetryError = 
      error.message.includes('events.mapbox.com') ||
      error.message.includes('ERR_BLOCKED_BY_CLIENT') ||
      error.message.includes('net::ERR_BLOCKED_BY_CLIENT');

    // Only show error boundary for non-telemetry errors
    if (isMapboxTelemetryError) {
      return { hasError: false };
    }

    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log error for debugging (but not telemetry errors)
    const isMapboxTelemetryError = 
      error.message.includes('events.mapbox.com') ||
      error.message.includes('ERR_BLOCKED_BY_CLIENT') ||
      error.message.includes('net::ERR_BLOCKED_BY_CLIENT');

    if (!isMapboxTelemetryError) {
      console.error('Mapbox Error Boundary caught an error:', error, errorInfo);
    }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="flex items-center justify-center h-full bg-muted/50 rounded-lg">
          <div className="text-center p-6">
            <h3 className="text-lg font-semibold mb-2">Map Loading Error</h3>
            <p className="text-sm text-muted-foreground mb-4">
              There was an issue loading the map. Please try refreshing the page.
            </p>
            <button
              onClick={() => this.setState({ hasError: false })}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
} 