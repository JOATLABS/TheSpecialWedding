'use client';

import { useEffect, useRef } from 'react';
import { useSSEEvent } from '@/contexts/SSEContext';

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
  | 'checkin'
  | 'couple_message';

export interface DataChangeEvent {
  resource: SSEResource | '__reconnected__';
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
   *
   * Also called once on reconnect (after network drop / laptop sleep)
   * with `resource: '__reconnected__'` so the UI can catch up on any
   * events that were missed while disconnected.
   */
  onDataChange: (event: DataChangeEvent) => void;
  /**
   * Pass `false` to temporarily disconnect (e.g. when no wedding is selected).
   * Defaults to `true`.
   */
  enabled?: boolean;
}

/**
 * Subscribe to data-change events from the shared SSE connection.
 *
 * This hook does NOT create its own EventSource — it subscribes to the
 * single connection managed by SSEProvider, eliminating the duplicate
 * connection that previously wasted browser slots and server memory.
 *
 * On reconnect (after sleep / network loss), the callback fires once
 * with `resource: '__reconnected__'` so consumers can refetch stale data.
 */
export function useSSE({
  resources,
  weddingId,
  onDataChange,
  enabled = true,
}: UseSSEOptions) {
  const savedCallback = useRef(onDataChange);
  useEffect(() => { savedCallback.current = onDataChange; }, [onDataChange]);

  const resourceSet = useRef(new Set(resources));
  useEffect(() => { resourceSet.current = new Set(resources); }, [resources]);

  const weddingIdRef = useRef(weddingId);
  useEffect(() => { weddingIdRef.current = weddingId; }, [weddingId]);

  const enabledRef = useRef(enabled);
  useEffect(() => { enabledRef.current = enabled; }, [enabled]);

  useSSEEvent('data-change', (raw) => {
    if (!enabledRef.current) return;

    const data = raw as DataChangeEvent;

    // Always let the reconnect signal through so consumers can catch up
    if (data.resource === '__reconnected__') {
      savedCallback.current(data);
      return;
    }

    // Filter by resource type if specified
    if (resourceSet.current.size > 0 && !resourceSet.current.has(data.resource as SSEResource)) {
      return;
    }

    // Filter by wedding ID if specified
    if (weddingIdRef.current && data.wedding_id && data.wedding_id !== weddingIdRef.current) {
      return;
    }

    savedCallback.current(data);
  });
}
