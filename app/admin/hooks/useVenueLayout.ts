import { useCallback, useEffect, useState } from 'react';
import { VenueLayout, UpdateVenueLayoutRequest } from '@/types/table';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';
import {
  applyBillingBlockTarget,
  resolvePaymentRequiredResponse,
} from '@/utils/adminApiAuthGuard';

export const DEFAULT_VENUE_LAYOUT_SIZE = {
  width: 1600,
  height: 1000,
} as const;

export function createEmptyVenueLayout(weddingId: string): VenueLayout {
  return {
    id: null,
    wedding_id: weddingId,
    canvas_width: DEFAULT_VENUE_LAYOUT_SIZE.width,
    canvas_height: DEFAULT_VENUE_LAYOUT_SIZE.height,
    outline: [],
    background_image_data_url: null,
    background_image_name: null,
    background_locked: true,
    scale_pixels: null,
    scale_distance: null,
    scale_unit: 'ft',
    fixtures: [],
    updated_at: null,
  };
}

export function useVenueLayout(weddingId: string) {
  const [layout, setLayout] = useState<VenueLayout>(() => createEmptyVenueLayout(weddingId));
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { token, logout, userProfile } = useAdmin();

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
      headers.Authorization = `Bearer ${token}`;
    }
    if (includeContentType) {
      headers['Content-Type'] = 'application/json';
    }
    return headers;
  }, [token]);

  const fetchLayout = useCallback(async () => {
    if (!weddingId || !token) {
      setLayout(createEmptyVenueLayout(weddingId));
      return;
    }

    setLoading(true);
    setError(null);
    setLayout(createEmptyVenueLayout(weddingId));
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/tables/${weddingId}/venue-layout`, {
        headers: getHeaders(),
      });
      if (await handleAuthResponse(response)) return;
      if (!response.ok) throw new Error('Failed to fetch venue layout');
      const data = await response.json();
      setLayout(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [weddingId, token, getHeaders, handleAuthResponse]);

  const saveLayout = useCallback(async (data: UpdateVenueLayoutRequest) => {
    if (!weddingId || !token) return null;

    setSaving(true);
    setError(null);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/tables/${weddingId}/venue-layout`, {
        method: 'PUT',
        headers: getHeaders(true),
        body: JSON.stringify(data),
      });
      if (await handleAuthResponse(response)) return null;
      if (!response.ok) throw new Error('Failed to save venue layout');
      const saved = await response.json();
      setLayout(saved);
      return saved as VenueLayout;
    } catch (err: any) {
      setError(err.message);
      throw err;
    } finally {
      setSaving(false);
    }
  }, [weddingId, token, getHeaders, handleAuthResponse]);

  useEffect(() => {
    fetchLayout();
  }, [fetchLayout]);

  return {
    layout,
    loading,
    saving,
    error,
    fetchLayout,
    saveLayout,
    setLayout,
  };
}
