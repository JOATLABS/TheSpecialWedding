/**
 * MIGRATION EXAMPLE: Converting Guests Page to use new Error Handling
 *
 * This file shows how to migrate the existing guests page to use the new
 * useApi and useFetch hooks for better error handling and less boilerplate.
 *
 * Key changes:
 * 1. Replace manual fetch + state management with useFetch for data loading
 * 2. Replace custom fetch logic in event handlers with useApi
 * 3. Consolidate error handling to use standardized toast messages
 * 4. Remove repetitive fetch/error/loading state combinations
 */

// ============================================================================
// BEFORE: Current Implementation (Verbose)
// ============================================================================

/*
'use client';

import { useCallback, useState, useEffect } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';

interface Guest {
  id?: string;
  _id?: string;
  name: string;
  email?: string;
  wedding_id: string;
}

export default function AdminGuestsPage() {
  const { token } = useAdmin();
  const [guests, setGuests] = useState<Guest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [weddings, setWeddings] = useState<any[]>([]);
  const [selectedWedding, setSelectedWedding] = useState<string>('');

  // Fetch weddings on mount
  const fetchWeddings = useCallback(async () => {
    if (!token) return;
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const response = await fetch(`${baseUrl}/admin/planner/weddings`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      const data = await response.json();
      setWeddings(Array.isArray(data) ? data : []);
    } catch {
      setError('Failed to load weddings');
    }
  }, [token]);

  // Fetch guests when wedding is selected
  const fetchGuestData = useCallback(async () => {
    if (!selectedWedding) return;

    setLoading(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';

      // Fetch guests
      const guestsResponse = await fetch(
        `${baseUrl}/admin/guests?wedding_id=${selectedWedding}`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );

      let normalizedGuests: Guest[] = [];
      if (guestsResponse.ok) {
        const guestsData = await guestsResponse.json();
        normalizedGuests = Array.isArray(guestsData) ? guestsData : [];
      }
      setGuests(normalizedGuests);
    } catch {
      setError('Failed to load guest data');
    } finally {
      setLoading(false);
    }
  }, [selectedWedding, token]);

  // Create guest (POST request)
  const createGuest = async (guestData: Guest) => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const response = await fetch(`${baseUrl}/admin/guests`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ...guestData, wedding_id: selectedWedding }),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Failed to create guest');
      }

      const newGuest = await response.json();
      setGuests([...guests, newGuest]);
      toast.success('Guest created successfully');
    } catch (err: any) {
      toast.error(err.message || 'Failed to create guest');
    }
  };

  useEffect(() => {
    fetchWeddings();
  }, [fetchWeddings]);

  useEffect(() => {
    if (selectedWedding) {
      fetchGuestData();
    }
  }, [fetchGuestData, selectedWedding]);

  // Component JSX...
}
*/

// ============================================================================
// AFTER: Refactored with useApi and useFetch
// ============================================================================

import { useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useApi } from '@/hooks/useApi';
import { useFetch } from '@/hooks/useFetch';
import { toast } from 'sonner';

interface Guest {
  id?: string;
  _id?: string;
  name: string;
  email?: string;
  wedding_id: string;
}

interface Wedding {
  id?: string;
  couple_names: string;
  date: string;
  slug: string;
}

export default function AdminGuestsPageRefactored() {
  const { token } = useAdmin();
  const { request } = useApi();

  // State for selected wedding
  // (Could also use URL params instead)
  const [selectedWedding, setSelectedWedding] = useCallback('', []);

  // IMPROVEMENT 1: Automatic weddings fetching with loading state
  // - No need for manual setLoading/setError state
  // - Automatically refetches when token changes
  const {
    data: weddings,
    loading: weddingsLoading,
    error: weddingsError,
  } = useFetch<Wedding[]>(
    '/admin/planner/weddings',
    [token], // Re-fetch if token changes
    { skip: !token } // Don't fetch if no token
  );

  // IMPROVEMENT 2: Automatic guests fetching when wedding is selected
  // - Cleaner dependency tracking
  // - Automatic refetch when selectedWedding changes
  const {
    data: guests,
    loading: guestsLoading,
    error: guestsError,
    refetch: refetchGuests,
  } = useFetch<Guest[]>(
    `/admin/guests?wedding_id=${selectedWedding}`,
    [selectedWedding], // Re-fetch when wedding changes
    { skip: !selectedWedding } // Don't fetch until wedding is selected
  );

  // IMPROVEMENT 3: Simplified POST request with error handling
  // - Less boilerplate than manual fetch
  // - Consistent error messages
  // - Automatic error toasts
  const createGuest = useCallback(
    async (guestData: Guest) => {
      const { data: newGuest, error } = await request('/admin/guests', {
        method: 'POST',
        body: { ...guestData, wedding_id: selectedWedding },
      });

      if (error) {
        console.error('Failed to create guest:', error);
        return;
      }

      // Refetch list to include new guest
      // (or manually update state if you want to avoid extra request)
      await refetchGuests();
      toast.success('Guest created successfully');
    },
    [request, selectedWedding, refetchGuests]
  );

  // IMPROVEMENT 4: Simplified PUT request
  const updateGuest = useCallback(
    async (guestId: string, guestData: Partial<Guest>) => {
      const { error } = await request(`/admin/guests/${guestId}`, {
        method: 'PUT',
        body: guestData,
      });

      if (error) {
        return;
      }

      await refetchGuests();
      toast.success('Guest updated successfully');
    },
    [request, refetchGuests]
  );

  // IMPROVEMENT 5: Simplified DELETE request
  const deleteGuest = useCallback(
    async (guestId: string) => {
      const { error } = await request(`/admin/guests/${guestId}`, {
        method: 'DELETE',
      });

      if (error) {
        return;
      }

      await refetchGuests();
      toast.success('Guest deleted successfully');
    },
    [request, refetchGuests]
  );

  // Simple rendering logic - error/loading states are provided by hooks
  if (weddingsLoading) return <div>Loading weddings...</div>;
  if (weddingsError) return <div>Error: {weddingsError}</div>;

  if (!selectedWedding) {
    return (
      <div>
        <select onChange={(e) => setSelectedWedding(e.target.value)}>
          <option>Select a wedding...</option>
          {(weddings || []).map((wedding) => (
            <option key={wedding.id} value={wedding.id}>
              {wedding.couple_names}
            </option>
          ))}
        </select>
      </div>
    );
  }

  if (guestsLoading) return <div>Loading guests...</div>;
  if (guestsError) return <div>Error: {guestsError}</div>;

  return (
    <div>
      <h1>Guests ({(guests || []).length})</h1>
      {/* Guest list UI */}
      {(guests || []).map((guest) => (
        <div key={guest.id || guest._id}>
          <p>{guest.name}</p>
          <button onClick={() => updateGuest(guest.id || guest._id, { name: 'New Name' })}>
            Update
          </button>
          <button onClick={() => deleteGuest(guest.id || guest._id)}>
            Delete
          </button>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// KEY BENEFITS OF THE REFACTORED VERSION
// ============================================================================

/**
 * 1. LESS CODE
 *    - No need for separate loading/error/data state for each data fetch
 *    - useFetch and useApi handle all state management
 *    - Reduces component complexity
 *
 * 2. CONSISTENCY
 *    - All errors show as toasts automatically
 *    - Status codes handled consistently
 *    - Auth errors trigger same behavior everywhere
 *
 * 3. BETTER ERROR HANDLING
 *    - Standard error messages for common HTTP status codes
 *    - Network errors distinguished from validation errors
 *    - Error details logged for debugging
 *
 * 4. AUTOMATIC REFETCHING
 *    - Data refetches when dependencies change
 *    - Manual refetch() available when needed
 *    - Can be configured to auto-refetch at intervals
 *
 * 5. TESTABILITY
 *    - Easier to mock useApi and useFetch
 *    - Error cases covered by hook tests
 *    - Component logic simplified
 *
 * 6. TYPE SAFETY
 *    - Generic types: useFetch<Guest[]>
 *    - Response objects are typed
 *    - Better IDE autocompletion
 */

// ============================================================================
// MIGRATION CHECKLIST
// ============================================================================

/**
 * To migrate the guests page:
 *
 * ✓ 1. Add imports for useApi and useFetch
 * ✓ 2. Replace manual fetch calls with useFetch for GET requests
 * ✓ 3. Replace form submit handlers with useApi for POST/PUT/DELETE
 * ✓ 4. Remove manual loading/error state for data fetching
 * ✓ 5. Update JSX to use data from hooks instead of component state
 * ✓ 6. Test all error scenarios (network, validation, auth)
 * ✓ 7. Verify toasts still appear for errors
 * ✓ 8. Test refetch behavior
 *
 * Gradual migration is recommended:
 * 1. Start with simple GET endpoints
 * 2. Then convert POST/PUT/DELETE handlers
 * 3. Finally consolidate error handling
 *
 * Both old and new patterns can coexist during migration.
 */
