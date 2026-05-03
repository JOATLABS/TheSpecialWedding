'use client';

import React from 'react';

interface PageHeaderProps {
  title: string;
  description?: string;
  children?: React.ReactNode;
  /**
   * Override the default outer wrapper className. Useful when a page
   * controls its own vertical rhythm via a flex-column layout and the
   * default `mb-6` would stack on top of the parent's gap. Falls back
   * to the original `mb-6` when omitted, so all existing call sites
   * stay byte-identical.
   */
  className?: string;
}

/**
 * Unified page header component for consistent styling across all portal pages.
 * Based on the SAAS landing page hero section typography.
 *
 * Style: font-semibold, leading-tight, text-slate-900 dark:text-white
 * Size: text-2xl sm:text-3xl (responsive)
 */
export default function PageHeader({
  title,
  description,
  children,
  className = 'mb-6',
}: PageHeaderProps) {
  return (
    <div className={className}>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-semibold leading-tight text-slate-900 dark:text-white">
            {title}
          </h1>
          {description && (
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {description}
            </p>
          )}
        </div>
        {children && (
          <div className="flex items-center gap-2">
            {children}
          </div>
        )}
      </div>
    </div>
  );
}
