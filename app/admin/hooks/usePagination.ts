'use client';

import { useState, useCallback, useMemo } from 'react';

export interface PaginationState {
  /** Current page (1-indexed) */
  currentPage: number;
  /** Items per page */
  itemsPerPage: number;
  /** Total items from API */
  totalItems: number;
  /** Total pages computed from total items and items per page */
  totalPages: number;
}

export interface UsePaginationOptions {
  /** Initial page (default: 1) */
  initialPage?: number;
  /** Initial items per page (default: 50) */
  initialItemsPerPage?: number;
  /** Callback fired when page or limit changes — use to trigger a fetch */
  onPaginationChange?: (page: number, itemsPerPage: number) => void;
}

export interface UsePaginationReturn extends PaginationState {
  /** Set page number */
  setPage: (page: number) => void;
  /** Set items per page (resets to page 1) */
  setItemsPerPage: (limit: number) => void;
  /** Update totals from API response */
  setTotalItems: (total: number) => void;
  /** Convenience: update all API response pagination data at once */
  updateFromResponse: (response: { total: number; page?: number; pages?: number }) => void;
  /** Reset pagination to initial state */
  reset: () => void;
  /** Query params object ready to pass to an API call */
  queryParams: { page: number; limit: number };
  /** Skip value for APIs that use skip/limit instead of page/limit */
  skip: number;
}

export function usePagination(options: UsePaginationOptions = {}): UsePaginationReturn {
  const {
    initialPage = 1,
    initialItemsPerPage = 50,
    onPaginationChange,
  } = options;

  const [currentPage, setCurrentPage] = useState(initialPage);
  const [itemsPerPage, setItemsPerPageState] = useState(initialItemsPerPage);
  const [totalItems, setTotalItemsState] = useState(0);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(totalItems / itemsPerPage)),
    [totalItems, itemsPerPage]
  );

  const setPage = useCallback(
    (page: number) => {
      const clamped = Math.max(1, Math.min(page, totalPages));
      setCurrentPage(clamped);
      onPaginationChange?.(clamped, itemsPerPage);
    },
    [totalPages, itemsPerPage, onPaginationChange]
  );

  const setItemsPerPage = useCallback(
    (limit: number) => {
      setItemsPerPageState(limit);
      setCurrentPage(1);
      onPaginationChange?.(1, limit);
    },
    [onPaginationChange]
  );

  const setTotalItems = useCallback((total: number) => {
    setTotalItemsState(total);
  }, []);

  const updateFromResponse = useCallback(
    (response: { total: number; page?: number; pages?: number }) => {
      setTotalItemsState(response.total);
      if (response.page !== undefined) {
        setCurrentPage(response.page);
      }
    },
    []
  );

  const reset = useCallback(() => {
    setCurrentPage(initialPage);
    setItemsPerPageState(initialItemsPerPage);
    setTotalItemsState(0);
  }, [initialPage, initialItemsPerPage]);

  const queryParams = useMemo(
    () => ({ page: currentPage, limit: itemsPerPage }),
    [currentPage, itemsPerPage]
  );

  const skip = useMemo(
    () => (currentPage - 1) * itemsPerPage,
    [currentPage, itemsPerPage]
  );

  return {
    currentPage,
    itemsPerPage,
    totalItems,
    totalPages,
    setPage,
    setItemsPerPage,
    setTotalItems,
    updateFromResponse,
    reset,
    queryParams,
    skip,
  };
}
