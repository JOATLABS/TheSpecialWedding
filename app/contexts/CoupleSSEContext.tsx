'use client';

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useCoupleAuth } from '@/contexts/CoupleAuthContext';

type CoupleSSEEventType = 'data-change';

interface CoupleSSESubscription {
  eventType: CoupleSSEEventType;
  callback: (data: unknown) => void;
}

interface CoupleSSEContextValue {
  subscribe: (sub: CoupleSSESubscription) => () => void;
  connected: boolean;
}

const CoupleSSECtx = createContext<CoupleSSEContextValue | null>(null);

const INITIAL_RECONNECT_DELAY = 1000;
const MAX_RECONNECT_DELAY = 30_000;
const MAX_RECONNECT_ATTEMPTS = 20;

export function CoupleSSEProvider({ children }: { children: React.ReactNode }) {
  const { authStatus, isAuthenticated, expireSession, revalidateSession } = useCoupleAuth();
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attempts = useRef(0);
  const isMountedRef = useRef(true);
  const probeControllers = useRef<Set<AbortController>>(new Set());
  const subscribersRef = useRef<Set<CoupleSSESubscription>>(new Set());
  const [connected, setConnected] = useState(false);

  const dispatch = useCallback((eventType: CoupleSSEEventType, data: unknown) => {
    subscribersRef.current.forEach((sub) => {
      if (sub.eventType === eventType) {
        try {
          sub.callback(data);
        } catch {
          // Ignore subscriber errors so one consumer does not poison the stream.
        }
      }
    });
  }, []);

  const dispatchReconnect = useCallback(() => {
    dispatch('data-change', { resource: '__reconnected__', action: 'bulk_updated', wedding_id: null, record_id: null });
  }, [dispatch]);

  const subscribe = useCallback((sub: CoupleSSESubscription) => {
    subscribersRef.current.add(sub);
    return () => subscribersRef.current.delete(sub);
  }, []);

  useEffect(() => {
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
      probeControllers.current.forEach((controller) => controller.abort());
      probeControllers.current.clear();
      setConnected(false);
    };

    if (authStatus === 'loading') {
      cleanup();
      return undefined;
    }

    if (!isAuthenticated) {
      cleanup();
      return undefined;
    }

    const connect = () => {
      cleanup();
      const es = new EventSource(`${getApiBaseUrl()}/couple/notifications/stream`, { withCredentials: true });
      esRef.current = es;

      es.addEventListener('data-change', (evt) => {
        try {
          dispatch('data-change', JSON.parse(evt.data));
        } catch {
          // Ignore malformed payloads.
        }
      });

      es.onopen = () => {
        const wasReconnect = attempts.current > 0;
        attempts.current = 0;
        setConnected(true);
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

            void revalidateSession()
              .then(async (result) => {
                if (result === 'unauthenticated') {
                  attempts.current = MAX_RECONNECT_ATTEMPTS;
                  await expireSession();
                  return;
                }

                if (isMountedRef.current && !controller.signal.aborted) {
                  connect();
                }
              })
              .catch(() => {
                if (isMountedRef.current && !controller.signal.aborted) {
                  connect();
                }
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
  }, [authStatus, dispatch, dispatchReconnect, expireSession, isAuthenticated, revalidateSession]);

  return (
    <CoupleSSECtx.Provider value={{ subscribe, connected }}>
      {children}
    </CoupleSSECtx.Provider>
  );
}

export function useCoupleSSEEvent(eventType: CoupleSSEEventType, callback: (data: unknown) => void) {
  const ctx = useContext(CoupleSSECtx);
  const savedCallback = useRef(callback);

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!ctx) return;
    const sub: CoupleSSESubscription = {
      eventType,
      callback: (data) => savedCallback.current(data),
    };
    return ctx.subscribe(sub);
  }, [ctx, eventType]);

  return { connected: ctx?.connected ?? false };
}
