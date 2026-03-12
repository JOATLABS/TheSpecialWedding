'use client';

import { useState, useEffect, useCallback } from 'react';
import { useApi, type ApiResponse } from './useApi';

export interface PaginationMeta {
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
  totalPages: number;
}

export interface UsePaginatedFetchOptions {
  initialPage?: number;
  pageSize?: number;
  skip?: boolean;
}

export interface UsePaginatedFetchResult<T> {
  data: T[];
  loading: boolean;
  error: string | null;
  pagination: PaginationMeta;
  nextPage: () => Promise<void>;
  prevPage: () => Promise<void>;
  goToPage: (page: number) => Promise<void>;
  refetch: () => Promise<void>;
}

/**
 * usePaginatedFetch - Hook for handling paginated API responses
 *
 * Features:
 * - Automatic pagination management
 * - Loading and error states
 * - Page navigation (next, prev, goto)
 * - Metadata tracking (total items, pages, etc.)
 *
 * Usage:
 * const { data, pagination, nextPage, loading } = usePaginatedFetch<Guest>(
 *   '/api/guests',
 *   { initialPage: 1, pageSize: 20 }
 * );
 *
 * The API endpoint should accept:
 * - page=1
 * - page_size=20
 *
 * And return an object with structure:
 * {
 *   data: T[],
 *   pagination: {
 *     total: number,
 *     page: number,
 *     page_size: number,
 *     total_pages: number
 *   }
 * }
 */
export function usePaginatedFetch<T = any>(
  basePath: string,
  options: UsePaginatedFetchOptions = {}
): UsePaginatedFetchResult<T> {
  const { initialPage = 1, pageSize = 20, skip = false } = options;

  const { request } = useApi();
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(initialPage);
  const [pagination, setPagination] = useState<PaginationMeta>({
    total: 0,
    page: initialPage,
    pageSize,
    hasMore: false,
    totalPages: 0,
  });

  const fetchPage = useCallback(
    async (pageNum: number) => {
      if (skip) return;

      setLoading(true);
      setError(null);

      try {
        const separator = basePath.includes('?') ? '&' : '?';
        const url = `${basePath}${separator}page=${pageNum}&page_size=${pageSize}`;

        const response = await request<any>(url, {
          method: 'GET',
          showErrorToast: true,
        });

        if (response.error) {
          setError(response.error);
          setData([]);
          return;
        }

        // Handle different response formats
        let items: T[] = [];
        let paginationData: Partial<PaginationMeta> = {};

        if (Array.isArray(response.data)) {
          // Simple array response
          items = response.data;
        } else if (response.data && typeof response.data === 'object') {
          // Response object with data and pagination
          if ('data' in response.data) {
            items = Array.isArray(response.data.data) ? response.data.data : [];
          } else if ('items' in response.data) {
            items = Array.isArray(response.data.items) ? response.data.items : [];
          }

          // Extract pagination metadata
          if ('pagination' in response.data) {
            const pageMeta = response.data.pagination;
            paginationData = {
              total: pageMeta.total || 0,
              page: pageMeta.page || pageNum,
              pageSize: pageMeta.page_size || pageSize,
              totalPages: pageMeta.total_pages || Math.ceil((pageMeta.total || 0) / pageSize),
            };
          }
        }

        setData(items);
        setPage(pageNum);

        // Update pagination metadata
        setPagination((prev) => ({
          total: paginationData.total ?? prev.total,
          page: pageNum,
          pageSize,
          totalPages: paginationData.totalPages ?? prev.totalPages,
          hasMore: pageNum < (paginationData.totalPages ?? 1),
        }));
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to fetch data';
        setError(message);
        setData([]);
      } finally {
        setLoading(false);
      }
    },
    [basePath, pageSize, skip, request]
  );

  // Fetch initial page on mount
  useEffect(() => {
    fetchPage(initialPage);
  }, [fetchPage, initialPage]);

  const nextPage = useCallback(async () => {
    if (pagination.hasMore) {
      await fetchPage(page + 1);
    }
  }, [page, pagination.hasMore, fetchPage]);

  const prevPage = useCallback(async () => {
    if (page > 1) {
      await fetchPage(page - 1);
    }
  }, [page, fetchPage]);

  const goToPage = useCallback(
    async (pageNum: number) => {
      if (pageNum >= 1 && pageNum <= pagination.totalPages) {
        await fetchPage(pageNum);
      }
    },
    [pagination.totalPages, fetchPage]
  );

  const refetch = useCallback(async () => {
    await fetchPage(page);
  }, [page, fetchPage]);

  return {
    data,
    loading,
    error,
    pagination,
    nextPage,
    prevPage,
    goToPage,
    refetch,
  };
}
