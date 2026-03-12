# API Error Handling System

This document describes the standardized error handling system for the WeddingWebApp frontend.

## Overview

The error handling system consists of three main components:

1. **useApi** - Low-level hook for individual API requests
2. **useFetch** - High-level hook for automatic data fetching with loading states
3. **errorHandler** - Utility functions for error parsing and messages

## useApi Hook

Use `useApi` when you need to make individual API requests and handle them explicitly.

### Basic Usage

```typescript
'use client';

import { useApi } from '@/hooks/useApi';

export function MyComponent() {
  const { request } = useApi();

  const handleSubmit = async (data: any) => {
    const { data: result, error } = await request('/api/guests', {
      method: 'POST',
      body: data,
    });

    if (error) {
      console.error('Failed to create guest:', error);
      return;
    }

    console.log('Guest created:', result);
  };

  return (
    <form onSubmit={(e) => {
      e.preventDefault();
      handleSubmit({ name: 'John Doe' });
    }}>
      <button type="submit">Create Guest</button>
    </form>
  );
}
```

### Advanced Usage with Options

```typescript
const { data, error } = await request('/api/guests', {
  method: 'GET',
  showErrorToast: false, // Disable automatic error toast
  headers: { 'Custom-Header': 'value' }, // Add custom headers
  abortSignal: abortController.signal, // Cancel request if needed
});

if (error) {
  // Handle error manually
  toast.error(`Failed to fetch guests: ${error}`);
}
```

### Key Features

- **Automatic Auth Token Injection**: Adds `Authorization: Bearer {token}` header automatically
- **Standardized Response**: Always returns `{ data, error, status }`
- **Error Toast Notifications**: Shows error toasts by default (can be disabled)
- **JSON Parsing**: Automatically parses JSON responses
- **Abort Signal Support**: Cancel requests with AbortController
- **Empty Response Handling**: Properly handles 204/205 status codes

## useFetch Hook

Use `useFetch` when you need automatic data fetching with loading states on component mount.

### Basic Usage

```typescript
'use client';

import { useFetch } from '@/hooks/useFetch';

interface Guest {
  id: string;
  name: string;
  email: string;
}

export function GuestList({ weddingId }: { weddingId: string }) {
  const { data: guests, loading, error, refetch } = useFetch<Guest[]>(
    `/api/weddings/${weddingId}/guests`
  );

  if (loading) return <div>Loading guests...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!guests) return <div>No guests found</div>;

  return (
    <div>
      <ul>
        {guests.map((guest) => (
          <li key={guest.id}>{guest.name}</li>
        ))}
      </ul>
      <button onClick={refetch}>Refresh</button>
    </div>
  );
}
```

### With Dependencies (Updates when dependencies change)

```typescript
const { data, loading, error, refetch } = useFetch<Guest[]>(
  `/api/weddings/${weddingId}/guests`,
  [weddingId] // Re-fetch when weddingId changes
);
```

### With Options

```typescript
const { data, loading, error, refetch, isStale } = useFetch<Guest[]>(
  `/api/weddings/${weddingId}/guests`,
  [weddingId],
  {
    skip: !weddingId, // Don't fetch until weddingId is available
    refetchInterval: 30000, // Auto-refetch every 30 seconds
    retryCount: 3, // Retry 3 times on failure
    retryDelay: 1000, // Wait 1 second between retries
  }
);
```

### Key Features

- **Automatic Loading State**: `loading` prop shows while fetching
- **Auto-Refetch**: Optional interval-based refetching
- **Retry Logic**: Configurable automatic retries on failure
- **Manual Refetch**: `refetch()` method for manual refresh
- **Stale Detection**: `isStale` indicates if data is outdated
- **Conditional Fetching**: `skip` option to defer fetching
- **Abort Handling**: Cancels previous requests when dependencies change

## Error Handler Utility

Use error handler functions for consistent error message formatting.

### Basic Usage

```typescript
import { getErrorMessage, parseError, logError } from '@/utils/errorHandler';

try {
  // API call
} catch (error) {
  const parsed = parseError(error);
  logError(error, 'GuestCreation');
  const userMessage = getErrorMessage(parsed.status, parsed.message);
  toast.error(userMessage);
}
```

### Helper Functions

```typescript
// Get user-friendly message from status code
const message = getErrorMessage(401); // "Your session has expired..."

// Parse any error into standard format
const parsed = parseError(error);
// Returns: { message: string, status?: number, code?: string }

// Check if error is network-related
if (isNetworkError(error)) {
  // Show offline message
}

// Check if error is auth-related
if (isAuthError(401)) {
  // Redirect to login
}

// Get recovery action suggestion
const action = getRecoveryAction(429); // "retry" for rate limit
```

## Migration Examples

### Example 1: Converting Inline Fetch to useApi

**Before:**
```typescript
const [loading, setLoading] = useState(false);
const [error, setError] = useState<string>('');

const createGuest = async (data: any) => {
  setLoading(true);
  try {
    const response = await fetch(`${baseUrl}/api/guests`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to create');
    setGuests([...guests, await response.json()]);
  } catch (err) {
    setError(err.message);
  } finally {
    setLoading(false);
  }
};
```

**After:**
```typescript
const { request } = useApi();

const createGuest = async (data: any) => {
  const { data: guest, error } = await request('/api/guests', {
    method: 'POST',
    body: data,
  });
  if (!error) {
    setGuests([...guests, guest]);
  }
};
```

### Example 2: Converting Manual Data Fetching to useFetch

**Before:**
```typescript
const [guests, setGuests] = useState<Guest[]>([]);
const [loading, setLoading] = useState(false);

useEffect(() => {
  const fetchGuests = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${baseUrl}/api/guests/${weddingId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      setGuests(data);
    } finally {
      setLoading(false);
    }
  };
  if (weddingId) fetchGuests();
}, [weddingId, token]);
```

**After:**
```typescript
const { data: guests, loading } = useFetch<Guest[]>(
  `/api/guests/${weddingId}`,
  [weddingId]
);
```

## Best Practices

1. **Use useApi for Forms/Actions**: Use `useApi` for POST, PUT, PATCH, DELETE operations
2. **Use useFetch for Data Loading**: Use `useFetch` for GET operations on component mount
3. **Show Error Context**: Always show what operation failed to users
4. **Disable Toast for Modal Dialogs**: Set `showErrorToast: false` when handling errors in modals
5. **Handle Auth Errors**: Watch for 401 errors and redirect to login
6. **Test Error Paths**: Always test network errors, timeouts, and validation errors
7. **Avoid Silent Failures**: Always show users when something goes wrong

## Common Patterns

### Loading Skeleton with Fallback

```typescript
const { data, loading, error } = useFetch<Guest[]>(`/api/guests/${weddingId}`);

if (error) return <ErrorBoundary message={error} />;
if (loading) return <GuestListSkeleton />;
return <GuestListTable guests={data || []} />;
```

### Refetch on Action

```typescript
const { data, refetch } = useFetch<Guest[]>(`/api/guests`);
const { request } = useApi();

const handleDelete = async (guestId: string) => {
  const { error } = await request(`/api/guests/${guestId}`, {
    method: 'DELETE',
  });
  if (!error) {
    await refetch(); // Refresh list after deletion
  }
};
```

### Polling with Auto-Refetch

```typescript
const { data, isStale } = useFetch<Event[]>(`/api/events`, [], {
  refetchInterval: 60000, // Poll every 60 seconds
});

// Show indicator when data is stale
{isStale && <div className="text-yellow-500">Data has been refreshed</div>}
```

### Retry on Network Error

```typescript
const { data, error, refetch } = useFetch<Guest[]>(`/api/guests`, [], {
  retryCount: 3,
  retryDelay: 2000,
});

if (error && isNetworkError(error)) {
  return <button onClick={refetch}>Retry</button>;
}
```

## Troubleshooting

### Q: Why is the toast not showing?

A: Check if `showErrorToast: false` was set. Also ensure the Sonner provider is in your layout.

### Q: How do I cancel a request?

A: Pass an AbortSignal:
```typescript
const controller = new AbortController();
await request('/api/guests', { abortSignal: controller.signal });
controller.abort(); // Cancel the request
```

### Q: How do I handle conditional API calls?

A: Use the `skip` option in useFetch:
```typescript
const { data } = useFetch('/api/guests', [weddingId], { skip: !weddingId });
```

### Q: How do I add custom headers?

A: Pass them in options:
```typescript
const { data } = await request('/api/guests', {
  headers: { 'X-Custom': 'value' }
});
```

## See Also

- `app/hooks/useApi.ts` - Low-level API hook implementation
- `app/hooks/useFetch.ts` - High-level fetch hook implementation
- `app/utils/errorHandler.ts` - Error handling utilities
- `app/contexts/AuthContext.tsx` - Authentication context
- `app/contexts/APIContext.tsx` - Legacy API context (being replaced)
