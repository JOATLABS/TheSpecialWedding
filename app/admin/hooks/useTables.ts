import { useState, useCallback } from 'react';
import { Table, CreateTableRequest, UpdateTableRequest, AssignGuestsRequest } from '@/types/table';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || '';

export function useTables(weddingId: string) {
  const [tables, setTables] = useState<Table[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getAuthHeader = (): Record<string, string> => {
    const token = typeof window !== 'undefined'
      ? localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token')
      : null;
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const fetchTables = useCallback(async () => {
    if (!weddingId) return;
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/admin/tables/${weddingId}`, {
        headers: getAuthHeader(),
      });
      if (!response.ok) throw new Error('Failed to fetch tables');
      const data = await response.json();
      setTables(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [weddingId]);

  const createTable = async (data: CreateTableRequest) => {
    try {
      const response = await fetch(`${API_BASE_URL}/admin/tables`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify(data),
      });
      if (!response.ok) throw new Error('Failed to create table');
      const newTable = await response.json();
      setTables((prev) => [...prev, newTable]);
      return newTable;
    } catch (err: any) {
      setError(err.message);
      throw err;
    }
  };

  const updateTable = async (tableId: string, data: UpdateTableRequest) => {
    try {
      const response = await fetch(`${API_BASE_URL}/admin/tables/${tableId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify(data),
      });
      if (!response.ok) throw new Error('Failed to update table');

      setTables((prev) =>
        prev.map((t) => (t.id === tableId ? { ...t, ...data } : t))
      );
    } catch (err: any) {
      setError(err.message);
      throw err;
    }
  };

  const deleteTable = async (tableId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/admin/tables/${tableId}`, {
        method: 'DELETE',
        headers: getAuthHeader(),
      });
      if (!response.ok) throw new Error('Failed to delete table');

      setTables((prev) => prev.filter((t) => t.id !== tableId));
    } catch (err: any) {
      setError(err.message);
      throw err;
    }
  };

  const assignGuests = async (tableId: string, guestIds: string[]) => {
    try {
      const response = await fetch(`${API_BASE_URL}/admin/tables/assign`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify({ table_id: tableId, guest_ids: guestIds }),
      });
      if (!response.ok) {
        // Parse error response to get actual message (e.g., capacity exceeded)
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to assign guests');
      }
      return true;
    } catch (err: any) {
      setError(err.message);
      throw err;
    }
  };

  const unassignGuests = async (guestIds: string[]) => {
    try {
      const response = await fetch(`${API_BASE_URL}/admin/tables/unassign`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify({ guest_ids: guestIds, wedding_id: weddingId }),
      });
      if (!response.ok) throw new Error('Failed to unassign guests');
      return true;
    } catch (err: any) {
      setError(err.message);
      throw err;
    }
  };

  return {
    tables,
    loading,
    error,
    fetchTables,
    createTable,
    updateTable,
    deleteTable,
    assignGuests,
    unassignGuests,
    setTables, // Exposed for optimistic updates
  };
}
