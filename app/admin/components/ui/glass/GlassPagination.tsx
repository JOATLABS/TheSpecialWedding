'use client';

import React from 'react';
import { cn } from './GlassCard';
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';

export interface GlassPaginationProps {
  /** Current page number (1-indexed) */
  currentPage: number;
  /** Total number of pages */
  totalPages: number;
  /** Total number of items across all pages */
  totalItems: number;
  /** Items shown per page */
  itemsPerPage: number;
  /** Whether data is currently loading */
  isLoading?: boolean;
  /** Callback when page changes */
  onPageChange: (page: number) => void;
  /** Callback when items per page changes */
  onItemsPerPageChange?: (limit: number) => void;
  /** Available page size options */
  pageSizeOptions?: number[];
  /** Label for the items (e.g. "guests", "tickets") */
  itemLabel?: string;
  /** Display variant: 'full' shows everything, 'compact' hides page numbers and per-page dropdown */
  variant?: 'full' | 'compact';
}

export function GlassPagination({
  currentPage = 1,
  totalPages = 1,
  totalItems = 0,
  itemsPerPage = 50,
  isLoading = false,
  onPageChange,
  onItemsPerPageChange,
  pageSizeOptions = [10, 25, 50, 100],
  itemLabel = 'items',
  variant = 'full',
}: Partial<GlassPaginationProps> & { onPageChange?: (page: number) => void }) {
  // Defensive: ensure numeric values are valid
  const safeTotalItems = totalItems ?? 0;
  const safeCurrentPage = currentPage ?? 1;
  const safeTotalPages = totalPages ?? 1;
  const safeItemsPerPage = itemsPerPage ?? 50;

  const startItem = safeTotalItems === 0 ? 0 : (safeCurrentPage - 1) * safeItemsPerPage + 1;
  const endItem = Math.min(safeCurrentPage * safeItemsPerPage, safeTotalItems);

  // Generate page numbers to display with ellipsis
  const getPageNumbers = (): (number | 'ellipsis')[] => {
    if (safeTotalPages <= 7) {
      return Array.from({ length: safeTotalPages }, (_, i) => i + 1);
    }

    const pages: (number | 'ellipsis')[] = [1];

    if (safeCurrentPage > 3) {
      pages.push('ellipsis');
    }

    const start = Math.max(2, safeCurrentPage - 1);
    const end = Math.min(safeTotalPages - 1, safeCurrentPage + 1);

    for (let i = start; i <= end; i++) {
      pages.push(i);
    }

    if (safeCurrentPage < safeTotalPages - 2) {
      pages.push('ellipsis');
    }

    if (safeTotalPages > 1) {
      pages.push(safeTotalPages);
    }

    return pages;
  };

  if (safeTotalItems === 0 && !isLoading) return null;

  const isCompact = variant === 'compact';

  return (
    <div
      className={cn(
        'flex items-center justify-between gap-3 rounded-xl border border-slate-200/80 dark:border-slate-700/50 bg-white/85 dark:bg-slate-900/40 backdrop-blur-md',
        isCompact ? 'px-3 py-2' : 'flex-col sm:flex-row px-4 py-3'
      )}
      role="navigation"
      aria-label="Pagination"
    >
      {/* Left: Showing X-Y of Z */}
      <div className={cn('flex items-center gap-3 text-slate-600 dark:text-slate-400', isCompact ? 'text-xs' : 'text-sm')}>
        <span>
          Showing <span className="font-medium text-slate-800 dark:text-slate-200">{startItem}</span>
          {' '}&ndash;{' '}
          <span className="font-medium text-slate-800 dark:text-slate-200">{endItem}</span>
          {' '}of{' '}
          <span className="font-medium text-slate-800 dark:text-slate-200">{safeTotalItems.toLocaleString()}</span>
          {' '}{itemLabel}
        </span>

        {/* Per-page dropdown — hidden in compact variant */}
        {!isCompact && onItemsPerPageChange && (
          <select
            value={safeItemsPerPage}
            onChange={(e) => onItemsPerPageChange(Number(e.target.value))}
            disabled={isLoading}
            className="cursor-pointer rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700 backdrop-blur-sm disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-800/60 dark:text-slate-300"
            aria-label="Items per page"
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>
                {size} / page
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Right: Page navigation */}
      <div className="flex items-center gap-1">
        {/* First page — hidden in compact */}
        {!isCompact && (
          <PaginationButton
            onClick={() => onPageChange?.(1)}
            disabled={safeCurrentPage === 1 || isLoading}
            aria-label="First page"
            title="First page"
            compact={isCompact}
          >
            <ChevronsLeft className={isCompact ? 'w-3.5 h-3.5' : 'w-4 h-4'} />
          </PaginationButton>
        )}

        {/* Previous page */}
        <PaginationButton
          onClick={() => onPageChange?.(safeCurrentPage - 1)}
          disabled={safeCurrentPage === 1 || isLoading}
          aria-label="Previous page"
          title="Previous page"
          compact={isCompact}
        >
          <ChevronLeft className={isCompact ? 'w-3.5 h-3.5' : 'w-4 h-4'} />
        </PaginationButton>

        {/* Page numbers — full variant shows individual buttons, compact shows "Page X of Y" */}
        {isCompact ? (
          <span className="px-2 text-xs text-slate-600 dark:text-slate-400 whitespace-nowrap">
            Page <span className="font-medium text-slate-800 dark:text-slate-200">{safeCurrentPage}</span> of{' '}
            <span className="font-medium text-slate-800 dark:text-slate-200">{safeTotalPages}</span>
          </span>
        ) : (
          getPageNumbers().map((page, index) =>
            page === 'ellipsis' ? (
              <span
                key={`ellipsis-${index}`}
                className="px-1 text-slate-400 dark:text-slate-500 select-none"
                aria-hidden="true"
              >
                &hellip;
              </span>
            ) : (
              <PaginationButton
                key={page}
                onClick={() => onPageChange?.(page)}
                disabled={isLoading}
                active={page === safeCurrentPage}
                aria-label={`Page ${page}`}
                aria-current={page === safeCurrentPage ? 'page' : undefined}
              >
                {page}
              </PaginationButton>
            )
          )
        )}

        {/* Next page */}
        <PaginationButton
          onClick={() => onPageChange?.(safeCurrentPage + 1)}
          disabled={safeCurrentPage === safeTotalPages || isLoading}
          aria-label="Next page"
          title="Next page"
          compact={isCompact}
        >
          <ChevronRight className={isCompact ? 'w-3.5 h-3.5' : 'w-4 h-4'} />
        </PaginationButton>

        {/* Last page — hidden in compact */}
        {!isCompact && (
          <PaginationButton
            onClick={() => onPageChange?.(safeTotalPages)}
            disabled={safeCurrentPage === safeTotalPages || isLoading}
            aria-label="Last page"
            title="Last page"
            compact={isCompact}
          >
            <ChevronsRight className={isCompact ? 'w-3.5 h-3.5' : 'w-4 h-4'} />
          </PaginationButton>
        )}
      </div>
    </div>
  );
}

/* ─── Internal button sub-component ──────────────────────── */

interface PaginationButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
  compact?: boolean;
  children: React.ReactNode;
}

function PaginationButton({ active, compact, children, className, disabled, ...props }: PaginationButtonProps) {
  return (
    <button
      disabled={disabled}
      className={cn(
        'font-medium rounded-lg transition-all duration-200',
        'border border-transparent',
        'disabled:opacity-40 disabled:cursor-not-allowed',
        'focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary-500',
        compact
          ? 'min-w-[26px] h-6 px-1.5 text-xs'
          : 'min-w-[32px] h-8 px-2 text-sm',
        active
          ? 'bg-primary-500/90 text-white shadow-sm shadow-primary-500/20 border-primary-400/50'
          : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700/60 hover:text-slate-800 dark:hover:text-slate-200 hover:border-slate-200 dark:hover:border-slate-600',
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
