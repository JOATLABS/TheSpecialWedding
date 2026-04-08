'use client';

import { getApiBaseUrl } from '@/utils/env';

export function clearLegacyCoupleStorage(): void {
  if (typeof window === 'undefined') {
    return;
  }

  localStorage.removeItem('couple_token');
  localStorage.removeItem('couple_data');
}

export async function coupleFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers ?? {});

  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  return fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers,
    credentials: 'include',
  });
}

export async function extractApiErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const data = await response.json();
    const detail = data?.detail;

    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }

    if (detail && typeof detail === 'object' && typeof detail.message === 'string' && detail.message.trim()) {
      return detail.message;
    }

    if (typeof data?.message === 'string' && data.message.trim()) {
      return data.message;
    }
  } catch {
    // Ignore malformed or empty error bodies and return the fallback.
  }

  return fallback;
}

export function buildCoupleLoginRedirect(message?: string | null): string {
  if (!message) {
    return '/couple/login';
  }

  return `/couple/login?message=${encodeURIComponent(message)}`;
}

export async function logoutCoupleSession(): Promise<void> {
  try {
    await coupleFetch('/couple/logout', {
      method: 'POST',
    });
  } catch {
    // Ignore logout network failures and still clear legacy storage.
  } finally {
    clearLegacyCoupleStorage();
  }
}
