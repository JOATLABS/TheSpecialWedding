'use client';

import { useCallback } from 'react';

import { useCoupleAuth } from '@/contexts/CoupleAuthContext';
import { resolveCoupleSessionFailure } from '@/couple/lib/auth';

/**
 * Returns a handler suitable for passing to API helpers that need to check
 * whether a non-OK Response represents a session-expiry / blocked-session
 * condition. If so, the auth context is told to expire the session and the
 * handler resolves to ``true``.
 */
export function useCoupleSessionExpiryHandler() {
  const { expireSession } = useCoupleAuth();

  return useCallback(
    async (
      response: Response,
      options?: { blockedFallback?: string; unauthenticatedFallback?: string },
    ) => {
      const failure = await resolveCoupleSessionFailure(response, options);
      if (!failure) {
        return false;
      }

      await expireSession(failure.message);
      return true;
    },
    [expireSession],
  );
}
