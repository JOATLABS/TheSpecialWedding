'use client';

/**
 * SSEProvider — single shared EventSource connection for the entire admin app.
 *
 * Problem solved: TopHeader.tsx and useSSE.ts each opened their own EventSource
 * to the same endpoint, wasting 2 of the browser's 6-per-domain HTTP/1.1 slots
 * and doubling server-side queue memory per tab.
 *
 * Now there is ONE EventSource per tab, managed by this context.  Components
 * subscribe to specific event types via useSSEEvent().  The hook also supports
 * a `catchUpOnReconnect` option so that when the connection recovers after a
 * network drop or laptop sleep, the subscriber is called once immediately to
 * refetch data it may have missed while disconnected.
 */

import React, { createContext, useContext, useEffect, useRef, useCallback, useState } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';

// ------------------------------------------------------------------
// Types
// ------------------------------------------------------------------

type SSEEventType = 'notification-count' | 'notification-new' | 'data-change';

interface SSESubscription {
  eventType: SSEEventType;
  callback: (data: unknown) => void;
}

interface SSEContextValue {
  /** Subscribe to a specific SSE event type. Returns an unsubscribe function. */
  subscribe: (sub: SSESubscription) => () => void;
  /** Whether the EventSource is currently connected. */
  connected: boolean;
}

const SSECtx = createContext<SSEContextValue | null>(null);

// ------------------------------------------------------------------
// Provider
// ------------------------------------------------------------------

const INITIAL_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 30_000;
const MAX_RECONNECT_ATTEMPTS = 20;

export function SSEProvider({ children }: { children: React.ReactNode }) {
  const { token } = useAdmin();
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attempts = useRef(0);
  const isMountedRef = useRef(true);
  const probeControllers = useRef<Set<AbortController>>(new Set());
  const subscribersRef = useRef<Set<SSESubscription>>(new Set());
  const [connected, setConnected] = useState(false);

  // Notify all subscribers of a given event type
  const dispatch = useCallback((eventType: SSEEventType, data: unknown) => {
    subscribersRef.current.forEach((sub) => {
      if (sub.eventType === eventType) {
        try {
          sub.callback(data);
        } catch {
          // Subscriber threw — ignore to avoid poisoning other subscribers
        }
      }
    });
  }, []);

  // Notify data-change subscribers with a synthetic "reconnected" event so they
  // can refetch anything they missed while disconnected.
  const dispatchReconnect = useCallback(() => {
    dispatch('data-change', { resource: '__reconnected__', action: 'bulk_updated', wedding_id: null, record_id: null });
  }, [dispatch]);

  const subscribe = useCallback((sub: SSESubscription) => {
    subscribersRef.current.add(sub);
    return () => {
      subscribersRef.current.delete(sub);
    };
  }, []);

  // Connection management
  useEffect(() => {
    if (!token) return;
    isMountedRef.current = true;

    const cleanup = () => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
      probeControllers.current.forEach((c) => c.abort());
      probeControllers.current.clear();
      setConnected(false);
    };

    const connect = () => {
      cleanup();
      const url = `${getApiBaseUrl()}/admin/notifications/stream`;
      // EventSource cannot send Authorization headers, so the backend stream
      // authenticates via the existing HttpOnly admin session cookie instead.
      const es = new EventSource(url, { withCredentials: true });
      esRef.current = es;

      // Listen for all event types the backend emits
      es.addEventListener('notification-count', (evt) => {
        try { dispatch('notification-count', JSON.parse(evt.data)); } catch { /* ignore */ }
      });
      es.addEventListener('notification-new', (evt) => {
        try { dispatch('notification-new', JSON.parse(evt.data)); } catch { /* ignore */ }
      });
      es.addEventListener('data-change', (evt) => {
        try { dispatch('data-change', JSON.parse(evt.data)); } catch { /* ignore */ }
      });

      es.onopen = () => {
        const wasReconnect = attempts.current > 0;
        attempts.current = 0;
        setConnected(true);
        // On reconnect, tell all data-change subscribers to refetch
        if (wasReconnect) {
          dispatchReconnect();
        }
      };

      es.onerror = () => {
        es.close();
        esRef.current = null;
        setConnected(false);

        if (attempts.current < MAX_RECONNECT_ATTEMPTS && isMountedRef.current) {
          const delay = Math.min(
            INITIAL_RECONNECT_DELAY * Math.pow(2, attempts.current),
            MAX_RECONNECT_DELAY,
          );
          attempts.current += 1;

          reconnectTimer.current = setTimeout(() => {
            if (!isMountedRef.current) return;

            const controller = new AbortController();
            probeControllers.current.add(controller);
            const probeTimeout = setTimeout(() => controller.abort(), 5000);

            fetch(`${getApiBaseUrl()}/admin/user/notifications/count`, {
              headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
              signal: controller.signal,
            })
              .then((probe) => {
                if (probe.status === 401 || probe.status === 402) {
                  attempts.current = MAX_RECONNECT_ATTEMPTS;
                  return;
                }
                if (isMountedRef.current && !controller.signal.aborted) connect();
              })
              .catch(() => {
                if (isMountedRef.current && !controller.signal.aborted) connect();
              })
              .finally(() => {
                clearTimeout(probeTimeout);
                probeControllers.current.delete(controller);
              });
          }, delay);
        }
      };
    };

    connect();

    // Pause SSE when tab is hidden, resume when visible
    const handleVisibility = () => {
      if (!isMountedRef.current) return;
      if (document.hidden) {
        cleanup();
      } else {
        attempts.current = 0;
        connect();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      isMountedRef.current = false;
      cleanup();
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [token, dispatch, dispatchReconnect]);

  return (
    <SSECtx.Provider value={{ subscribe, connected }}>
      {children}
    </SSECtx.Provider>
  );
}

// ------------------------------------------------------------------
// Hooks
// ------------------------------------------------------------------

/**
 * Low-level hook: subscribe to any SSE event type dispatched by the shared
 * EventSource.  Returns current connection status.
 */
export function useSSEEvent(eventType: SSEEventType, callback: (data: unknown) => void) {
  const ctx = useContext(SSECtx);
  const savedCb = useRef(callback);
  useEffect(() => { savedCb.current = callback; }, [callback]);

  useEffect(() => {
    if (!ctx) return;
    const sub: SSESubscription = { eventType, callback: (data) => savedCb.current(data) };
    return ctx.subscribe(sub);
  }, [ctx, eventType]);

  return { connected: ctx?.connected ?? false };
}
