'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Guest } from '@/types/table';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';

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

  // Get token and logout from AdminContext (single source of truth for auth)
  const { token, logout } = useAdmin();

  // Track current request to prevent race conditions
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentWeddingIdRef = useRef<string>(weddingId);

  const fetchGuests = useCallback(async (signal?: AbortSignal) => {
    if (!weddingId || !token) return;

    // Determine the signal to use for this request
    let fetchSignal: AbortSignal;

    if (signal) {
      // Caller provided a signal (e.g., from useEffect) — use it directly.
      // The caller is responsible for setting abortControllerRef before calling.
      fetchSignal = signal;
    } else {
      // Manual call (refetch) — abort any in-flight request and create new controller
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;
      fetchSignal = controller.signal;
    }

    setLoading(true);
    setError(null);

    try {
      const baseUrl = getApiBaseUrl();
      const res = await fetch(
        `${baseUrl}/admin/guests?wedding_id=${weddingId}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          signal: fetchSignal
        }
      );

      // Handle auth errors consistently with AdminContext
      if (res.status === 401) {
        logout();
        return;
      }
      if (res.status === 402) {
        window.location.href = '/admin/planner/billing';
        return;
      }

      if (!res.ok) {
        throw new Error(`Failed to fetch guests: ${res.status}`);
      }

      const data = await res.json();

      // API returns { guests: [...], total, page, pages, limit }
      const guestList: any[] = Array.isArray(data) ? data : (data.guests || []);

      // Only update state if this is still the current wedding
      if (currentWeddingIdRef.current === weddingId) {
        setGuests(guestList.map((g: any) => ({
          id: g.id || g._id,
          wedding_id: g.wedding_id,
          name: g.name,
          token: g.token,
          email: g.email,
          phone: g.phone,
          group_id: g.group_id,
          table_id: g.table_id || null,
          role: g.role,
          plus_one_allowed: g.plus_one_allowed,
          number_of_plus_ones_allowed: g.number_of_plus_ones_allowed,
          plus_one_submitted: g.plus_one_submitted,
          sms_opt_in: g.sms_opt_in,
          email_opt_in: g.email_opt_in,
          phone_status: g.phone_status,
          invite_sent: g.invite_sent,
          invite_sent_date: g.invite_sent_date,
          // Seating constraint fields
          must_sit_with: g.must_sit_with || [],
          must_sit_apart: g.must_sit_apart || [],
          accessibility_needs: g.accessibility_needs,
          seating_preference: g.seating_preference,
          age_group: g.age_group,
          language_preference: g.language_preference,
          created_at: g.created_at,
          updated_at: g.updated_at,
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
  }, [weddingId, token, logout]);

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

    if (autoFetch && weddingId && token) {
      const controller = new AbortController();
      abortControllerRef.current = controller;
      fetchGuests(controller.signal);

      // Cleanup: abort on unmount or weddingId change
      return () => {
        controller.abort();
      };
    }
  }, [autoFetch, weddingId, token, fetchGuests]);

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
