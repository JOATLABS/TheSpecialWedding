'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * Redirect — Business Analytics has been merged into the SaaS Management
 * Overview tab.  This page exists solely so that bookmarks, browser history,
 * and any stale links land in the right place.
 */
export default function MetricsRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/admin/saas');
  }, [router]);

  return (
    <div className="flex min-h-64 items-center justify-center">
      <div className="rounded-xl bg-white dark:bg-slate-800 px-6 py-4 text-lg text-gray-900 dark:text-white shadow-sm">
        Redirecting to SaaS Management…
      </div>
    </div>
  );
}
