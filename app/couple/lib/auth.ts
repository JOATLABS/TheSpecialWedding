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
