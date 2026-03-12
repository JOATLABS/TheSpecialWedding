'use client';

import React from 'react';
import { cn } from './GlassCard';

interface Column<T> {
  header: string;
  accessor: keyof T | ((item: T) => React.ReactNode);
  className?: string;
}

interface GlassTableProps<T> {
  data: T[];
  columns: Column<T>[];
  keyField: keyof T;
  isLoading?: boolean;
  emptyMessage?: string;
  onRowClick?: (item: T) => void;
}

export function GlassTable<T>({
  data,
  columns,
  keyField,
  isLoading,
  emptyMessage = "No data available",
  onRowClick
}: GlassTableProps<T>) {
  return (
    <div className="w-full overflow-hidden rounded-xl border border-white/50 dark:border-slate-700/50 shadow-sm bg-white/40 dark:bg-slate-900/40 backdrop-blur-md" role="region" aria-label="Data table">
      <div className="overflow-x-auto custom-scrollbar">
        <table className="w-full text-left text-sm" role="table">
          <thead className="bg-slate-50/80 dark:bg-slate-800/80 backdrop-blur-sm border-b border-slate-200 dark:border-slate-700" role="rowgroup">
            <tr role="row">
              {columns.map((col, index) => (
                <th
                  key={index}
                  className={cn(
                    "px-6 py-4 font-semibold text-slate-700 dark:text-slate-200 uppercase tracking-wider text-xs",
                    col.className
                  )}
                  role="columnheader"
                  scope="col"
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800" role="rowgroup">
            {isLoading ? (
              <tr role="row">
                <td colSpan={columns.length} className="px-6 py-8 text-center text-slate-500" role="cell">
                  <div className="flex items-center justify-center gap-2" aria-label="Loading data">
                    <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '0s' }} aria-hidden="true" />
                    <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} aria-hidden="true" />
                    <div className="w-2 h-2 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} aria-hidden="true" />
                  </div>
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr role="row">
                <td colSpan={columns.length} className="px-6 py-8 text-center text-slate-500 italic" role="cell">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              data.map((item) => (
                <tr
                  key={String(item[keyField])}
                  onClick={() => onRowClick && onRowClick(item)}
                  role="row"
                  tabIndex={onRowClick ? 0 : -1}
                  onKeyPress={(e) => {
                    if (onRowClick && (e.key === 'Enter' || e.key === ' ')) {
                      e.preventDefault();
                      onRowClick(item);
                    }
                  }}
                  className={cn(
                    "group transition-colors duration-200",
                    onRowClick ? "cursor-pointer hover:bg-primary-50/50 dark:hover:bg-primary-900/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-500" : "hover:bg-slate-50/30 dark:hover:bg-slate-800/30"
                  )}
                >
                  {columns.map((col, idx) => (
                    <td key={idx} className="px-6 py-4 whitespace-nowrap text-slate-600 dark:text-slate-300" role="cell">
                      {typeof col.accessor === 'function'
                        ? col.accessor(item)
                        : (item[col.accessor] as React.ReactNode)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
