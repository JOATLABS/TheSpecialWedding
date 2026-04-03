'use client';

import { useEffect } from 'react';

export default function TeamError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Team page error:', error);
  }, [error]);

  return (
    <div className="p-8 max-w-2xl mx-auto mt-8">
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-6">
        <h2 className="text-lg font-bold text-red-700 dark:text-red-400 mb-2">
          Team Page Error
        </h2>
        <p className="text-sm text-red-600 dark:text-red-300 mb-1">
          <strong>Message:</strong> {error.message}
        </p>
        <p className="text-xs text-red-500 dark:text-red-400 mb-4 font-mono">
          <strong>Name:</strong> {error.name}
        </p>
        {error.stack && (
          <details className="mb-4">
            <summary className="cursor-pointer text-sm text-red-600 dark:text-red-400 font-medium">
              Stack trace
            </summary>
            <pre className="mt-2 text-xs text-red-500 dark:text-red-400 whitespace-pre-wrap overflow-auto max-h-64 bg-red-100 dark:bg-red-900/30 p-3 rounded">
              {error.stack}
            </pre>
          </details>
        )}
        <button
          onClick={reset}
          className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm font-medium"
        >
          Try Again
        </button>
      </div>
    </div>
  );
}
