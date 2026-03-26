import { getApiBaseUrl } from '@/utils/env';

declare global {
  interface Window {
    __TSW_ADMIN_AUTH_TOKEN__?: string;
    __TSW_ADMIN_REMEMBER_ME__?: boolean;
  }
}

function clearLegacyAdminStorage(): void {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    localStorage.removeItem('admin_token');
  } catch (error) {
    console.warn('Unable to clear legacy admin token from localStorage', error);
  }

  try {
    sessionStorage.removeItem('admin_token');
  } catch (error) {
    console.warn('Unable to clear legacy admin token from sessionStorage', error);
  }
}

function setInMemoryAdminToken(token: string | null): void {
  if (typeof window === 'undefined') {
    return;
  }

  if (token) {
    window.__TSW_ADMIN_AUTH_TOKEN__ = token;
  } else {
    delete window.__TSW_ADMIN_AUTH_TOKEN__;
  }
}

/**
 * Decode a JWT payload without verifying the signature.
 * JWTs are base64url-encoded and the payload (second segment) contains
 * the `exp` claim we need for client-side expiry checks.
 */
export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const json = atob(base64);
    return JSON.parse(json);
  } catch {
    return null;
  }
}

/**
 * Check if a JWT has expired (or will expire within `bufferSeconds`).
 *
 * Uses a 30-second buffer so the token isn't used in the last moments
 * before expiry, which would race with the backend's own check.
 *
 * Returns `true` if the token is expired, malformed, or missing `exp`.
 */
export function isTokenExpired(token: string | null, bufferSeconds = 30): boolean {
  if (!token) return true;
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== 'number') return true;
  return Date.now() / 1000 > payload.exp - bufferSeconds;
}

export function clearAdminAuthStorage(): void {
  if (typeof window === 'undefined') {
    return;
  }

  clearLegacyAdminStorage();
  setInMemoryAdminToken(null);
  delete window.__TSW_ADMIN_REMEMBER_ME__;
}

export function persistAdminAuthToken(token: string, rememberMe: boolean): void {
  if (typeof window === 'undefined') {
    return;
  }

  clearLegacyAdminStorage();
  setInMemoryAdminToken(token);
  window.__TSW_ADMIN_REMEMBER_ME__ = rememberMe;
}

export function getAdminAuthToken(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }

  return window.__TSW_ADMIN_AUTH_TOKEN__ ?? null;
}

export function wasAdminSessionRemembered(): boolean {
  if (typeof window === 'undefined') {
    return true;
  }

  return window.__TSW_ADMIN_REMEMBER_ME__ ?? true;
}

export async function bootstrapAdminAuthToken(): Promise<string | null> {
  const existingToken = getAdminAuthToken();
  if (existingToken && !isTokenExpired(existingToken)) {
    return existingToken;
  }

  clearAdminAuthStorage();

  try {
    const response = await fetch(`${getApiBaseUrl()}/admin/token/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      return null;
    }

    const payload = await response.json();
    const freshToken = payload?.access_token;

    if (typeof freshToken !== 'string' || isTokenExpired(freshToken)) {
      return null;
    }

    persistAdminAuthToken(freshToken, wasAdminSessionRemembered());
    return freshToken;
  } catch {
    return null;
  }
}

/**
 * Returns the number of milliseconds until the JWT expires.
 * Returns 0 if the token is already expired, malformed, or missing `exp`.
 */
export function getTokenExpiresInMs(token: string | null): number {
  if (!token) return 0;
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== 'number') return 0;
  const msUntilExpiry = payload.exp * 1000 - Date.now();
  return Math.max(0, msUntilExpiry);
}
