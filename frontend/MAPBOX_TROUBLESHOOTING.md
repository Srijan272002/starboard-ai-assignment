# Mapbox Troubleshooting Guide

## Common Issues and Solutions

### 1. ERR_BLOCKED_BY_CLIENT Error

**Problem**: Console errors like `POST https://events.mapbox.com/events/v2 net::ERR_BLOCKED_BY_CLIENT`

**Cause**: Ad blockers, privacy extensions, or browser security settings are blocking Mapbox telemetry requests.

**Solution**: This has been resolved by implementing telemetry blocking in the codebase.

### 2. Implementation Details

The solution includes several components:

#### Mapbox Configuration (`src/lib/mapbox-config.ts`)
- `configureMapbox()`: Global configuration to disable telemetry
- `createTelemetryBlockingTransform()`: Request transformer that blocks telemetry URLs
- `getDefaultMapboxOptions()`: Default options with telemetry disabled

#### Error Boundary (`src/components/market/MapboxErrorBoundary.tsx`)
- Catches and handles Mapbox-related errors
- Ignores telemetry-related errors
- Provides fallback UI for genuine errors

#### Custom Hook (`src/lib/hooks/useMapbox.ts`)
- Clean, reusable Mapbox initialization
- Built-in error handling
- Loading states

### 3. Usage

```tsx
import { useMapbox } from '@/lib/hooks/useMapbox';

function MyMapComponent() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { map, isLoading, error } = useMapbox({
    container: containerRef,
    token: process.env.NEXT_PUBLIC_MAPBOX_TOKEN
  });

  if (isLoading) return <div>Loading map...</div>;
  if (error) return <div>Error: {error}</div>;

  return <div ref={containerRef} className="h-full" />;
}
```

### 4. Environment Variables

Ensure your `.env` file contains:
```
NEXT_PUBLIC_MAPBOX_TOKEN=your_mapbox_token_here
```

### 5. Best Practices

1. **Always use the error boundary** when rendering Mapbox components
2. **Use the custom hook** for consistent initialization
3. **Don't suppress all console errors** - only telemetry-related ones
4. **Test with ad blockers enabled** to ensure compatibility

### 6. Debugging

If you still see telemetry errors:

1. Check that `configureMapbox()` is called before map initialization
2. Verify the `transformRequest` function is working
3. Ensure the error boundary is properly configured
4. Test in incognito mode with extensions disabled

### 7. Performance Considerations

- Telemetry blocking reduces unnecessary network requests
- Error boundary prevents unnecessary re-renders
- Custom hook provides better memory management

### 8. Browser Compatibility

This solution works with:
- Chrome/Chromium (with ad blockers)
- Firefox (with privacy extensions)
- Safari (with content blockers)
- Edge (with tracking prevention)

### 9. Future Updates

When updating Mapbox GL JS:
1. Test with ad blockers enabled
2. Verify telemetry blocking still works
3. Update error boundary patterns if needed
4. Check for new telemetry endpoints

## Support

If you encounter issues not covered here:
1. Check the browser console for specific error messages
2. Verify your Mapbox token is valid
3. Test in a different browser or incognito mode
4. Review the Mapbox GL JS documentation for recent changes 