'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useApi, type ApiResponse } from './useApi';

export interface UseFetchOptions {
  skip?: boolean; // Skip fetching if true
  refetchInterval?: number; // Refetch interval in milliseconds
  retryCount?: number; // Number of retries on failure
  retryDelay?: number; // Delay between retries in milliseconds
}

export interface UseFetchResult<T> extends ApiResponse<T> {
  loading: boolean;
  refetch: () => Promise<void>;
  isStale: boolean;
}

/**
 * useFetch - Automatic data fetching hook with loading, error, and refetch states
 *
 * Features:
 * - Automatic fetch on mount and dependency changes
 * - Loading state management
 * - Error handling with toast notifications
 * - Refetch capability
 * - Optional auto-refetch at intervals
 * - Retry logic for failed requests
 * - Stale data tracking
 *
 * Usage:
 * const { data, error, loading, refetch } = useFetch('/api/guests', [weddingId]);
 *
 * Or with options:
 * const { data, loading, refetch } = useFetch('/api/guests', [weddingId], {
 *   refetchInterval: 30000,
 *   retryCount: 3,
 *   skip: !isReady
 * });
 */
export function useFetch<T = any>(
  path: string,
  deps: any[] = [],
  options: UseFetchOptions = {}
): UseFetchResult<T> {
  const { skip = false, refetchInterval, retryCount = 0, retryDelay = 1000 } = options;

  const { request } = useApi();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isStale, setIsStale] = useState(false);

  const retryCountRef = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const refetchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastFetchTimeRef = useRef<number>(0);

  // Perform the actual fetch
  const performFetch = useCallback(async () => {
    if (skip) return;

    // Cancel previous request if still pending
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();
    setLoading(true);
    setError(null);
    setIsStale(false);

    try {
      const response = await request<T>(path, {
        abortSignal: abortControllerRef.current.signal,
        showErrorToast: true,
      });

      if (response.error) {
        if (retryCountRef.current < retryCount) {
          retryCountRef.current += 1;
          // Wait before retrying
          await new Promise((resolve) => setTimeout(resolve, retryDelay));
          await performFetch();
          return;
        }
        setError(response.error);
        setData(null);
      } else {
        setData(response.data);
        setError(null);
        retryCountRef.current = 0;
      }

      lastFetchTimeRef.current = Date.now();
    } catch (err) {
      // Ignore abort errors
      if (err instanceof Error && err.name !== 'AbortError') {
        setError(err.message);
        setData(null);
      }
    } finally {
      setLoading(false);
    }
  }, [path, skip, request, retryCount, retryDelay]);

  // Refetch function exposed to consumers
  const refetch = useCallback(async () => {
    retryCountRef.current = 0;
    await performFetch();
  }, [performFetch]);

  // Initial fetch on mount and dependency changes
  useEffect(() => {
    performFetch();

    // Setup auto-refetch interval if specified
    if (refetchInterval && refetchInterval > 0) {
      refetchTimeoutRef.current = setInterval(() => {
        setIsStale(true);
        performFetch();
      }, refetchInterval);
    }

    return () => {
      // Cleanup: abort pending request and clear interval
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (refetchTimeoutRef.current) {
        clearInterval(refetchTimeoutRef.current);
      }
    };
  }, [performFetch, refetchInterval]);

  return {
    data,
    error,
    loading,
    refetch,
    isStale,
    status: undefined, // Not applicable for fetch hook
  };
}
