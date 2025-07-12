# Starboard Implementation Fix Plan

## Current Issues

1. **Frontend Using Mock Data Instead of API Data**
   - Frontend components are using hardcoded mock data
   - API connections not properly implemented
   - Possible CORS issues preventing successful API calls

2. **Properties Page Not Accessible (404 Error)**
   - Route configuration issues
   - Page component may have errors

3. **Search Properties Component on Homepage**
   - Need to remove from homepage

## Implementation Plan

### 1. Connect Frontend to Backend API

#### Step 1: Create API Service Layer
- Create a dedicated API service to handle all backend requests
- Implement proper error handling and response parsing

```typescript
// src/lib/api.ts
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchProperties(filters = {}) {
  const queryParams = new URLSearchParams();
  
  // Add any filters to query params
  Object.entries(filters).forEach(([key, value]) => {
    if (value) queryParams.append(key, String(value));
  });
  
  const response = await fetch(`${API_BASE_URL}/api/properties?${queryParams}`);
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  
  return response.json();
}

export async function fetchPropertyById(id) {
  const response = await fetch(`${API_BASE_URL}/api/properties/${id}`);
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  
  return response.json();
}

// Add more API methods as needed
```

#### Step 2: Update Environment Configuration
- Create or update `.env.local` file in frontend directory

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### Step 3: Replace Mock Data in Components
- Update all components to use the API service instead of hardcoded data
- Implement loading states and error handling

### 2. Fix Properties Page Route

#### Step 1: Verify Route Structure
- Ensure the properties page component is properly exported
- Check for any syntax errors in the page component

#### Step 2: Update Next.js Configuration
- Verify routes are properly configured in `next.config.ts`
- Check for any middleware that might be affecting routes

#### Step 3: Fix Properties Page Component
- Review and fix any errors in the properties page component
- Ensure it's properly fetching data from the API

### 3. Remove Search Properties from Homepage

#### Step 1: Update Homepage Component
- Remove or comment out the search properties component from the homepage
- Adjust layout as needed to maintain visual consistency

### 4. CORS Configuration

#### Step 1: Verify Backend CORS Settings
- Ensure backend CORS settings match frontend origin

```python
# backend/app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### Step 2: Update .env File if Needed
- Ensure BACKEND_CORS_ORIGINS includes the frontend URL

### 5. Testing Plan

1. **API Connection Testing**
   - Test each API endpoint with Postman or similar tool
   - Verify proper data is returned from backend

2. **Frontend Integration Testing**
   - Test properties listing page with real API data
   - Test property details page with real API data
   - Verify search and filtering functionality

3. **Error Handling Testing**
   - Test behavior when API is unavailable
   - Test behavior with invalid data responses

### 6. Implementation Timeline

| Task | Estimated Time | Dependencies |
|------|---------------|--------------|
| Create API Service Layer | 2 hours | None |
| Update Environment Configuration | 30 minutes | None |
| Replace Mock Data in Components | 4 hours | API Service Layer |
| Verify Route Structure | 1 hour | None |
| Update Next.js Configuration | 1 hour | None |
| Fix Properties Page Component | 2 hours | API Service Layer |
| Remove Search from Homepage | 30 minutes | None |
| Verify CORS Settings | 1 hour | None |
| Testing | 3 hours | All above tasks |

## Additional Considerations

### Performance Optimization
- Implement data caching for API responses
- Use React Query or SWR for efficient data fetching and caching

### Error Handling
- Create consistent error UI components
- Implement comprehensive error logging

### User Experience
- Add loading indicators during API calls
- Implement skeleton screens for better perceived performance

### Security
- Ensure sensitive data isn't exposed in frontend code
- Implement proper authentication if required 