# Frontend Error Handling System - Setup & Integration Guide

## Overview

This document describes the new standardized frontend error handling system for the WeddingWebApp. The system provides type-safe, consistent API request handling with automatic error management and user feedback.

## What Was Added

### New Hooks

1. **useApi** (`app/hooks/useApi.ts`)
   - Low-level hook for individual API requests
   - Handles authentication, error parsing, response parsing
   - Best for POST, PUT, PATCH, DELETE operations

2. **useFetch** (`app/hooks/useFetch.ts`)
   - High-level hook for automatic data fetching
   - Manages loading, error, and stale states
   - Best for GET operations on component mount

3. **useMutation** (`app/hooks/useMutation.ts`)
   - Wrapper around useApi with additional mutation features
   - Supports success/error callbacks
   - Convenience methods: useCreateMutation, useUpdateMutation, useDeleteMutation

4. **usePaginatedFetch** (`app/hooks/usePaginatedFetch.ts`)
   - Specialized hook for paginated API responses
   - Handles page navigation (next, prev, goto)
   - Extracts pagination metadata

### Utilities

5. **errorHandler** (`app/utils/errorHandler.ts`)
   - Error parsing and formatting utilities
   - User-friendly message generation
   - Recovery action suggestions

### Documentation

6. **API_ERROR_HANDLING.md** (`app/hooks/API_ERROR_HANDLING.md`)
   - Complete usage guide with examples
   - Best practices and patterns
   - Troubleshooting section

## Installation Status

✓ All files have been created and are ready to use.
✓ No breaking changes - existing code continues to work.
✓ Can be adopted gradually alongside existing patterns.

## Quick Start

### For Simple Data Loading

Replace manual fetch with `useFetch`:

```typescript
import { useFetch } from '@/hooks/useFetch';

function GuestList({ weddingId }) {
  const { data: guests, loading, error } = useFetch(`/api/guests/${weddingId}`);

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;
  return <ul>{guests?.map(g => <li>{g.name}</li>)}</ul>;
}
```

### For Form Submissions

Replace manual fetch with `useApi` or `useMutation`:

```typescript
import { useApi } from '@/hooks/useApi';

function AddGuest() {
  const { request } = useApi();

  const handleSubmit = async (data) => {
    const { data: guest, error } = await request('/api/guests', {
      method: 'POST',
      body: data,
    });

    if (error) return;
    // Success - guest was created
  };

  return <form onSubmit={handleSubmit}>{/* ... */}</form>;
}
```

## Migration Path

### Phase 1: Simple Pages (Week 1)
- [ ] Convert dashboard GET requests to useFetch
- [ ] Convert simple form submissions to useApi
- [ ] Test error scenarios (network, validation, auth)

**Pages to migrate:**
- `app/admin/dashboard/page.tsx`
- `app/admin/profile/page.tsx`

### Phase 2: Complex Pages (Week 2)
- [ ] Convert guests page with multiple endpoints
- [ ] Add pagination using usePaginatedFetch
- [ ] Add refetch capabilities

**Pages to migrate:**
- `app/admin/guests/page.tsx`
- `app/admin/team/page.tsx`

### Phase 3: Components (Week 3)
- [ ] Convert modal components
- [ ] Convert search/filter components
- [ ] Convert bulk action handlers

### Phase 4: Legacy APIs (Week 4)
- [ ] Replace apiRequest usage with useApi
- [ ] Deprecate manual fetch patterns
- [ ] Update error boundary components

## Integration Checklist

For each page/component you update:

- [ ] Import new hook (useApi, useFetch, useMutation, usePaginatedFetch)
- [ ] Remove manual useState calls for loading/error/data
- [ ] Replace fetch calls with hook equivalents
- [ ] Update error handling to use hook error states
- [ ] Update JSX to show loading states from hooks
- [ ] Test all error paths:
  - [ ] Network error (offline)
  - [ ] 401 Unauthorized
  - [ ] 400 Bad Request
  - [ ] 500 Server Error
  - [ ] Timeout
- [ ] Verify toast notifications appear
- [ ] Test refetch functionality
- [ ] Run component tests if available

## Error Handling Best Practices

### 1. Show Loading States

```typescript
const { data, loading } = useFetch('/api/guests');

if (loading) {
  return <Skeleton />; // Show loading UI
}
```

### 2. Handle Errors Gracefully

```typescript
const { data, error } = useFetch('/api/guests');

if (error) {
  return <ErrorMessage message={error} />;
}
```

### 3. Provide Refetch Options

```typescript
const { data, refetch } = useFetch('/api/guests');

return (
  <>
    {/* List */}
    <button onClick={refetch}>Refresh</button>
  </>
);
```

### 4. Validate Before Mutation

```typescript
const { mutate } = useMutation('/api/guests', { method: 'POST' });

const handleSubmit = async (formData) => {
  // Validate before sending
  if (!formData.email) {
    toast.error('Email is required');
    return;
  }
  const { error } = await mutate(formData);
};
```

### 5. Handle Auth Errors

```typescript
const { data, error } = useFetch('/api/guests');

useEffect(() => {
  if (error?.includes('401') || error?.includes('expired')) {
    // Redirect to login
    window.location.href = '/admin/login';
  }
}, [error]);
```

## API Response Format Standards

The system expects API responses in one of these formats:

### Simple Array Response
```json
[
  { "id": 1, "name": "John" },
  { "id": 2, "name": "Jane" }
]
```

### Object with Data Field
```json
{
  "data": [
    { "id": 1, "name": "John" },
    { "id": 2, "name": "Jane" }
  ]
}
```

### Paginated Response
```json
{
  "data": [
    { "id": 1, "name": "John" },
    { "id": 2, "name": "Jane" }
  ],
  "pagination": {
    "total": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5
  }
}
```

### Error Response
```json
{
  "detail": "Guest not found",
  "code": "GUEST_NOT_FOUND",
  "status": 404
}
```

## Common Patterns

### Refetch After Mutation

```typescript
const { data: guests, refetch } = useFetch('/api/guests');
const { mutate } = useMutation('/api/guests', { method: 'POST' });

const handleCreate = async (data) => {
  const { error } = await mutate(data);
  if (!error) {
    await refetch(); // Refresh list
  }
};
```

### Optimistic Updates

```typescript
const [guests, setGuests] = useState([]);
const { request } = useApi();

const handleDelete = async (guestId) => {
  // Optimistic update
  setGuests(guests.filter(g => g.id !== guestId));

  const { error } = await request(`/api/guests/${guestId}`, {
    method: 'DELETE',
  });

  if (error) {
    // Rollback on error
    refetch();
  }
};
```

### Dependent Queries

```typescript
const { data: weddings } = useFetch('/api/weddings');
const [selectedId, setSelectedId] = useState('');

const { data: guests } = useFetch(
  `/api/guests/${selectedId}`,
  [selectedId],
  { skip: !selectedId } // Don't fetch until wedding is selected
);
```

### Search/Filter

```typescript
const [searchTerm, setSearchTerm] = useState('');
const { data: results, refetch } = useFetch(
  `/api/guests?search=${encodeURIComponent(searchTerm)}`,
  [searchTerm],
  { skip: searchTerm.length < 2 } // Debounce short searches
);
```

## Troubleshooting

### Issue: Toast not showing on error

**Solution:**
- Ensure Sonner provider is in app layout
- Check if `showErrorToast: false` was set
- Verify the error message is non-empty

### Issue: Fetch runs twice on mount

**Solution:**
- This is React 18 StrictMode behavior in development
- It only happens in dev, not in production
- It verifies components handle effects correctly

### Issue: Stale data after mutation

**Solution:**
- Call `refetch()` after mutation succeeds
- Or use `refetchInterval` to auto-refresh

### Issue: Authentication token missing

**Solution:**
- Ensure token is set in AuthContext
- useApi automatically injects token from context
- Check AuthContext is in provider tree

## Files Reference

```
app/
├── hooks/
│   ├── useApi.ts                    # Low-level API requests
│   ├── useFetch.ts                  # Data fetching with loading state
│   ├── useMutation.ts               # Form submission mutations
│   ├── usePaginatedFetch.ts         # Paginated API responses
│   └── API_ERROR_HANDLING.md        # Complete usage guide
├── utils/
│   └── errorHandler.ts              # Error parsing utilities
├── contexts/
│   ├── AuthContext.tsx              # Authentication state
│   ├── AdminContext.tsx             # Admin context wrapper
│   └── APIContext.tsx               # Legacy API context
└── admin/
    ├── guests/
    │   ├── page.tsx                 # (To be migrated)
    │   └── MIGRATION_EXAMPLE.ts     # Example migration
    ├── team/
    │   └── page.tsx                 # (To be migrated)
    └── dashboard/
        └── page.tsx                 # (To be migrated)
```

## Support & Questions

For detailed usage examples, see:
- `app/hooks/API_ERROR_HANDLING.md` - Complete usage guide
- `app/admin/guests/MIGRATION_EXAMPLE.ts` - Real-world example

## Next Steps

1. Read `app/hooks/API_ERROR_HANDLING.md` for detailed usage
2. Try useApi/useFetch in a simple page first
3. Test error scenarios in your dev environment
4. Gradually migrate pages from most critical to least
5. Update team with new patterns and best practices

## Backward Compatibility

- Existing code using manual fetch still works
- Existing code using useAdmin().apiRequest still works
- Old and new patterns can coexist during migration
- No breaking changes to existing APIs

## Performance Notes

- useFetch creates AbortController for each request
- Previous requests are cancelled when dependencies change
- No memory leaks from pending requests
- Retries are configurable and not enabled by default
- Auto-refetch interval is opt-in

## Security Considerations

- Authorization header injected automatically from AuthContext
- No sensitive data logged in production
- Network errors don't expose server details to users
- 401 errors trigger re-authentication flow
- CORS errors handled appropriately
