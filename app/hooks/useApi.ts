'use client';

import { useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';

export interface ApiOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: any;
  headers?: Record<string, string>;
  showErrorToast?: boolean;
  abortSignal?: AbortSignal;
}

export interface ApiResponse<T> {
  data: T | null;
  error: string | null;
  status?: number;
}

/**
 * useApi - Centralized hook for making API requests with standardized error handling
 *
 * Features:
 * - Automatic authentication token injection
 * - Standardized error handling and user feedback
 * - Type-safe responses
 * - Support for abort signals for cancellation
 *
 * Usage:
 * const { request } = useApi();
 * const { data, error } = await request('/api/guests', { method: 'GET' });
 */
export function useApi() {
  const { token } = useAuth();

  const request = useCallback(
    async <T = any>(path: string, options: ApiOptions = {}): Promise<ApiResponse<T>> => {
      const {
        method = 'GET',
        body,
        showErrorToast = true,
        abortSignal,
      } = options;

      try {
        const baseUrl = getApiBaseUrl();
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...options.headers,
        };

        const fetchOptions: RequestInit = {
          method,
          headers,
          cache: 'no-store',
          credentials: 'include',
          ...(body ? { body: JSON.stringify(body) } : {}),
          ...(abortSignal ? { signal: abortSignal } : {}),
        };

        const response = await fetch(`${baseUrl}${path}`, fetchOptions);

        // Handle non-OK responses
        if (!response.ok) {
          let errorMessage = `Request failed (${response.status})`;

          try {
            const errorData = await response.json();
            errorMessage = errorData.detail || errorData.message || errorMessage;
          } catch {
            // If response body is not JSON, try to use status text
            errorMessage = response.statusText || errorMessage;
          }

          // Handle specific HTTP status codes
          if (response.status === 401) {
            // Unauthorized - token may have expired
            console.warn('Authentication failed: token may be expired');
          } else if (response.status === 403) {
            // Forbidden - user doesn't have permission
            console.warn('Access forbidden for this resource');
          }

          if (showErrorToast) {
            toast.error(errorMessage);
          }

          return { data: null, error: errorMessage, status: response.status };
        }

        // Handle empty responses
        if (response.status === 204 || response.status === 205) {
          return { data: null, error: null, status: response.status };
        }

        // Check content length for empty responses
        const contentLength = response.headers.get('Content-Length');
        if (contentLength && parseInt(contentLength, 10) === 0) {
          return { data: null, error: null, status: response.status };
        }

        // Parse response
        const contentType = response.headers.get('Content-Type') || '';
        const rawBody = await response.text();

        if (!rawBody.trim()) {
          return { data: null, error: null, status: response.status };
        }

        // Try to parse JSON if content-type indicates JSON
        if (contentType.toLowerCase().includes('json')) {
          try {
            const data = JSON.parse(rawBody) as T;
            return { data, error: null, status: response.status };
          } catch (parseError) {
            const message = 'Invalid JSON response from server';
            console.error(`Failed to parse JSON response for ${path}:`, parseError);
            if (showErrorToast) {
              toast.error(message);
            }
            return { data: null, error: message, status: response.status };
          }
        }

        // Return raw text response as generic type
        return { data: (rawBody as unknown as T), error: null, status: response.status };
      } catch (err) {
        // Handle network errors and other exceptions
        if (err instanceof Error) {
          // Ignore abort errors as they're usually intentional
          if (err.name === 'AbortError') {
            return { data: null, error: 'Request cancelled', status: 0 };
          }

          if (showErrorToast) {
            toast.error(err.message);
          }
          return { data: null, error: err.message };
        }

        const message = 'Network error occurred';
        if (showErrorToast) {
          toast.error(message);
        }
        return { data: null, error: message };
      }
    },
    [token]
  );

  return { request };
}
