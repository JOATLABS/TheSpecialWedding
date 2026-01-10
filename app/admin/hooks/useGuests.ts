'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Guest } from '@/types/table';

interface UseGuestsOptions {
  autoFetch?: boolean;
}

interface UseGuestsReturn {
  guests: Guest[];
  setGuests: React.Dispatch<React.SetStateAction<Guest[]>>;
  loading: boolean;
  error: string | null;
  fetchGuests: () => Promise<void>;
  updateGuestTable: (guestId: string, tableId: string | null) => void;
  refetch: () => Promise<void>;
}

export function useGuests(weddingId: string, options: UseGuestsOptions = {}): UseGuestsReturn {
  const { autoFetch = true } = options;
  const [guests, setGuests] = useState<Guest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Track current request to prevent race conditions
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentWeddingIdRef = useRef<string>(weddingId);

  const fetchGuests = useCallback(async (signal?: AbortSignal) => {
    if (!weddingId) return;

    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Create new abort controller if not provided
    const controller = signal ? null : new AbortController();
    const fetchSignal = signal || controller?.signal;
    if (controller) {
      abortControllerRef.current = controller;
    }

    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('admin_token');
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/admin/guests/${weddingId}`,
        {
          headers: { Authorization: `Bearer ${token}` },
          signal: fetchSignal
        }
      );

      if (!res.ok) {
        throw new Error(`Failed to fetch guests: ${res.status}`);
      }

      const data = await res.json();

      // Only update state if this is still the current wedding
      if (currentWeddingIdRef.current === weddingId) {
        setGuests(data.map((g: any) => ({
          id: g._id,
          wedding_id: g.wedding_id,
          name: g.name,
          email: g.email,
          phone: g.phone,
          group_id: g.group_id,
          table_id: g.table_id || null,
          role: g.role,
          rsvp_status: g.rsvp_status,
          dietary_restrictions: g.dietary_restrictions,
          notes: g.notes
        })));
      }
    } catch (e) {
      // Ignore abort errors - they're expected when switching weddings
      if (e instanceof Error && e.name === 'AbortError') {
        return;
      }
      const message = e instanceof Error ? e.message : 'Failed to fetch guests';
      if (currentWeddingIdRef.current === weddingId) {
        setError(message);
      }
      console.error('Failed to fetch guests:', e);
    } finally {
      if (currentWeddingIdRef.current === weddingId) {
        setLoading(false);
      }
    }
  }, [weddingId]);

  // Optimistic update for table assignment
  const updateGuestTable = useCallback((guestId: string, tableId: string | null) => {
    setGuests(prev => prev.map(guest =>
      guest.id === guestId ? { ...guest, table_id: tableId } : guest
    ));
  }, []);

  // Manual refetch function
  const refetch = useCallback(() => fetchGuests(), [fetchGuests]);

  useEffect(() => {
    // Update ref when weddingId changes
    currentWeddingIdRef.current = weddingId;

    // Clear guests when switching weddings to prevent stale data flash
    setGuests([]);
    setError(null);

    if (autoFetch && weddingId) {
      const controller = new AbortController();
      abortControllerRef.current = controller;
      fetchGuests(controller.signal);

      // Cleanup: abort on unmount or weddingId change
      return () => {
        controller.abort();
      };
    }
  }, [autoFetch, weddingId, fetchGuests]);

  return {
    guests,
    setGuests,
    loading,
    error,
    fetchGuests,
    updateGuestTable,
    refetch
  };
}

export default useGuests;
