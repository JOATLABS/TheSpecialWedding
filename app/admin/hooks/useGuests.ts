'use client';

import { useState, useEffect, useCallback } from 'react';
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
}

export function useGuests(weddingId: string, options: UseGuestsOptions = {}): UseGuestsReturn {
  const { autoFetch = true } = options;
  const [guests, setGuests] = useState<Guest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchGuests = useCallback(async () => {
    if (!weddingId) return;

    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('admin_token');
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/admin/guests/${weddingId}`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );

      if (!res.ok) {
        throw new Error(`Failed to fetch guests: ${res.status}`);
      }

      const data = await res.json();
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
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to fetch guests';
      setError(message);
      console.error('Failed to fetch guests:', e);
    } finally {
      setLoading(false);
    }
  }, [weddingId]);

  // Optimistic update for table assignment
  const updateGuestTable = useCallback((guestId: string, tableId: string | null) => {
    setGuests(prev => prev.map(guest =>
      guest.id === guestId ? { ...guest, table_id: tableId } : guest
    ));
  }, []);

  useEffect(() => {
    if (autoFetch && weddingId) {
      fetchGuests();
    }
  }, [autoFetch, weddingId, fetchGuests]);

  return {
    guests,
    setGuests,
    loading,
    error,
    fetchGuests,
    updateGuestTable
  };
}

export default useGuests;
