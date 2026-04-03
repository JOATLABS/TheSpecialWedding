'use client';

import { useEffect, useRef } from 'react';

/**
 * Calls `callback` every `intervalMs` while the tab is visible.
 * Pauses when the tab is hidden and resumes when it comes back.
 *
 * @param callback  Async-safe function to call periodically
 * @param intervalMs  Polling interval in milliseconds (default 30 000 = 30 s)
 * @param enabled  Pass `false` to pause polling without unmounting
 */
export function usePolling(
  callback: () => void | Promise<void>,
  intervalMs = 30_000,
  enabled = true
) {
  const savedCallback = useRef(callback);

  // Always keep the latest callback in the ref so we never
  // close over a stale function.
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!enabled) return;

    let id: ReturnType<typeof setInterval> | null = null;

    const start = () => {
      if (id) return;
      id = setInterval(() => {
        savedCallback.current();
      }, intervalMs);
    };

    const stop = () => {
      if (id) {
        clearInterval(id);
        id = null;
      }
    };

    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        // Fetch immediately when the user returns, then resume interval
        savedCallback.current();
        start();
      } else {
        stop();
      }
    };

    // Start the interval right away
    start();
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      stop();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [intervalMs, enabled]);
}
