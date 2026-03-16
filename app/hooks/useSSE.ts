'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';

/**
 * Resource types that the backend can signal as changed.
 * Keep in sync with `sse_manager.broadcast_data_change()`.
 */
export type SSEResource =
  | 'guest'
  | 'rsvp'
  | 'wedding'
  | 'plus_one'
  | 'budget'
  | 'table'
  | 'invite'
  | 'checkin';

export interface DataChangeEvent {
  resource: SSEResource;
  action: 'created' | 'updated' | 'deleted' | 'bulk_updated';
  wedding_id?: string | null;
  record_id?: string | null;
}

interface UseSSEOptions {
  /**
   * Only listen for changes to these resources. If empty / undefined,
   * listen for all data-change events.
   */
  resources?: SSEResource[];
  /**
   * Optional wedding ID filter — ignore events for other weddings.
   */
  weddingId?: string | null;
  /**
   * Called whenever a matching data-change event arrives.
   * Typically this triggers a refetch of the affected data.
   */
  onDataChange: (event: DataChangeEvent) => void;
  /**
   * Pass `false` to temporarily disconnect (e.g. when no wedding is selected).
   * Defaults to `true`.
   */
  enabled?: boolean;
}

/**
 * Subscribe to the existing SSE notification stream and listen for
 * `data-change` events so the UI updates in real-time without polling.
 *
 * The TopHeader component already maintains its own EventSource for
 * notification badges. This hook does NOT create a duplicate connection —
 * it re-uses the same SSE endpoint but listens for a different event type.
 *
 * NOTE: The browser SSE EventSource API does not support custom headers,
 * so the JWT is passed as a query parameter (same as TopHeader).
 */
export function useSSE({
  resources,
  weddingId,
  onDataChange,
  enabled = true,
}: UseSSEOptions) {
  const { token } = useAdmin();
  const savedCallback = useRef(onDataChange);
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attempts = useRef(0);

  // Always keep the latest callback in the ref to avoid stale closures.
  useEffect(() => {
    savedCallback.current = onDataChange;
  }, [onDataChange]);

  // Memoised resource set for stable comparison.
  const resourceSet = useRef(new Set(resources));
  useEffect(() => {
    resourceSet.current = new Set(resources);
  }, [resources]);

  const weddingIdRef = useRef(weddingId);
  useEffect(() => {
    weddingIdRef.current = weddingId;
  }, [weddingId]);

  const cleanup = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
  }, []);

  useEffect(() => {
    if (!enabled || !token) {
      cleanup();
      return;
    }

    const connect = () => {
      cleanup();

      const url = `${getApiBaseUrl()}/admin/notifications/stream?token=${encodeURIComponent(token)}`;
      const es = new EventSource(url);
      esRef.current = es;

      es.addEventListener('data-change', (evt) => {
        try {
          const data: DataChangeEvent = JSON.parse(evt.data);

          // Filter by resource type if specified
          if (resourceSet.current.size > 0 && !resourceSet.current.has(data.resource)) {
            return;
          }

          // Filter by wedding ID if specified
          if (weddingIdRef.current && data.wedding_id && data.wedding_id !== weddingIdRef.current) {
            return;
          }

          savedCallback.current(data);
        } catch {
          // Ignore malformed events
        }
      });

      es.onopen = () => {
        attempts.current = 0;
      };

      es.onerror = () => {
        es.close();
        esRef.current = null;

        // Exponential backoff — max 60 seconds, max 12 attempts
        if (attempts.current < 12) {
          const delay = Math.min(1000 * Math.pow(2, attempts.current), 60_000);
          attempts.current += 1;
          reconnectTimer.current = setTimeout(connect, delay);
        }
      };
    };

    connect();

    return cleanup;
  }, [enabled, token, cleanup]);
}
