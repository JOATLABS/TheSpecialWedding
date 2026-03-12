'use client';

import { useState, useCallback } from 'react';
import { useApi, type ApiOptions, type ApiResponse } from './useApi';

export interface UseMutationOptions extends Omit<ApiOptions, 'method'> {
  onSuccess?: (data: any) => void | Promise<void>;
  onError?: (error: string) => void | Promise<void>;
  showSuccessToast?: boolean;
}

export interface UseMutationResult<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  status?: number;
  mutate: (body?: any) => Promise<{ data: T | null; error: string | null }>;
}

/**
 * useMutation - Wrapper around useApi for POST/PUT/PATCH/DELETE operations
 *
 * Provides additional features for mutations:
 * - Loading state during request
 * - Success callback support
 * - Error callback support
 * - Optional success toast
 *
 * Usage:
 * const { mutate, loading, error } = useMutation('/api/guests', {
 *   method: 'POST',
 *   onSuccess: () => { refetch(); },
 * });
 *
 * const handleCreate = async (data) => {
 *   const { data: result, error } = await mutate(data);
 * };
 */
export function useMutation<T = any>(
  path: string,
  options: UseMutationOptions & { method: 'POST' | 'PUT' | 'PATCH' | 'DELETE' }
): UseMutationResult<T> {
  const { onSuccess, onError, showSuccessToast = false, ...apiOptions } = options;

  const { request } = useApi();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<number | undefined>();

  const mutate = useCallback(
    async (body?: any) => {
      setLoading(true);
      setError(null);
      setData(null);

      try {
        const response = await request<T>(path, {
          ...apiOptions,
          body: body !== undefined ? body : apiOptions.body,
          showErrorToast: apiOptions.showErrorToast !== false,
        });

        setStatus(response.status);

        if (response.error) {
          setError(response.error);
          if (onError) {
            await onError(response.error);
          }
          return { data: null, error: response.error };
        }

        setData(response.data);

        if (onSuccess) {
          await onSuccess(response.data);
        }

        if (showSuccessToast) {
          const { toast } = await import('sonner');
          toast.success('Operation successful');
        }

        return { data: response.data, error: null };
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown error';
        setError(message);
        if (onError) {
          await onError(message);
        }
        return { data: null, error: message };
      } finally {
        setLoading(false);
      }
    },
    [request, path, apiOptions, onSuccess, onError, showSuccessToast]
  );

  return {
    data,
    error,
    loading,
    status,
    mutate,
  };
}

/**
 * useCreateMutation - Convenience hook for POST requests
 */
export function useCreateMutation<T = any>(
  path: string,
  options?: Omit<UseMutationOptions, 'method'>
) {
  return useMutation<T>(path, { ...options, method: 'POST' });
}

/**
 * useUpdateMutation - Convenience hook for PUT requests
 */
export function useUpdateMutation<T = any>(
  path: string,
  options?: Omit<UseMutationOptions, 'method'>
) {
  return useMutation<T>(path, { ...options, method: 'PUT' });
}

/**
 * useDeleteMutation - Convenience hook for DELETE requests
 */
export function useDeleteMutation<T = any>(
  path: string,
  options?: Omit<UseMutationOptions, 'method'>
) {
  return useMutation<T>(path, { ...options, method: 'DELETE' });
}
