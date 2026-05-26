import { useState, useCallback } from 'react';
import { Table, CreateTableRequest, UpdateTableRequest } from '@/types/table';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';
import {
  applyBillingBlockTarget,
  resolvePaymentRequiredResponse,
} from '@/utils/adminApiAuthGuard';

export function useTables(weddingId: string) {
  const [tables, setTables] = useState<Table[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Get token and logout from AdminContext (single source of truth for auth)
  const { token, logout, userProfile } = useAdmin();

  /**
   * Handle auth-related response statuses consistently with AdminContext.
   * Returns true if the response was handled (caller should return early).
   */
  const handleAuthResponse = useCallback(async (response: Response): Promise<boolean> => {
    if (response.status === 401) {
      logout();
      return true;
    }
    if (response.status === 402) {
      const resolution = await resolvePaymentRequiredResponse(response, {
        profile: userProfile,
        navigation: 'hard',
      });
      if (resolution.kind === 'billing_block') {
        applyBillingBlockTarget(resolution.target, { logout });
        return true;
      }
      return false;
    }
    return false;
  }, [logout, userProfile]);

  const getHeaders = useCallback((includeContentType = false): Record<string, string> => {
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    if (includeContentType) {
      headers['Content-Type'] = 'application/json';
    }
    return headers;
  }, [token]);

  const fetchTables = useCallback(async () => {
    if (!weddingId || !token) return;
    setLoading(true);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/tables/${weddingId}`, {
        headers: getHeaders(),
      });
      if (await handleAuthResponse(response)) return;
      if (!response.ok) throw new Error('Failed to fetch tables');
      const data = await response.json();
      setTables(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [weddingId, token, getHeaders, handleAuthResponse]);

  const createTable = async (data: CreateTableRequest) => {
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/tables`, {
        method: 'POST',
        headers: getHeaders(true),
        body: JSON.stringify(data),
      });
      if (await handleAuthResponse(response)) return;
      if (!response.ok) throw new Error('Failed to create table');
      const newTable = await response.json();
      setTables((prev) => [...prev, newTable]);
      return newTable;
    } catch (err: any) {
      setError(err.message);
      throw err;
    }
  };

  const updateTable = async (tableId: string, data: Partial<Table>) => {
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/tables/${tableId}`, {
        method: 'PUT',
        headers: getHeaders(true),
        body: JSON.stringify(data),
      });
      if (await handleAuthResponse(response)) return;
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
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/tables/${tableId}`, {
        method: 'DELETE',
        headers: getHeaders(),
      });
      if (await handleAuthResponse(response)) return;
      if (!response.ok) throw new Error('Failed to delete table');

      setTables((prev) => prev.filter((t) => t.id !== tableId));
    } catch (err: any) {
      setError(err.message);
      throw err;
    }
  };

  const assignGuests = async (tableId: string, guestIds: string[]) => {
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/tables/assign`, {
        method: 'POST',
        headers: getHeaders(true),
        body: JSON.stringify({ table_id: tableId, guest_ids: guestIds }),
      });
      if (await handleAuthResponse(response)) return false;
      if (!response.ok) {
        // Parse error response to get actual message (e.g., capacity exceeded)
        const errorData = await response.json().catch(() => ({}));
        const detail = errorData.detail;
        const message = typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
          ? detail.map((d: any) => d.msg || d.message || JSON.stringify(d)).join('; ')
          : 'Failed to assign guests';
        throw new Error(message);
      }
      return true;
    } catch (err: any) {
      setError(err.message);
      throw err;
    }
  };

  const unassignGuests = async (guestIds: string[]) => {
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/tables/unassign`, {
        method: 'POST',
        headers: getHeaders(true),
        body: JSON.stringify({ guest_ids: guestIds, wedding_id: weddingId }),
      });
      if (await handleAuthResponse(response)) return false;
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
