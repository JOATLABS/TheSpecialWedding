/**
 * Decode a JWT payload without verifying the signature.
 * JWTs are base64url-encoded and the payload (second segment) contains
 * the `exp` claim we need for client-side expiry checks.
 */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    // base64url → base64 → decode
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

  try {
    localStorage.removeItem('admin_token');
  } catch (error) {
    console.warn('Unable to clear admin token from localStorage', error);
  }

  try {
    sessionStorage.removeItem('admin_token');
  } catch (error) {
    console.warn('Unable to clear admin token from sessionStorage', error);
  }

  try {
    const cookies = document.cookie.split(';');
    for (const cookie of cookies) {
      const [rawName] = cookie.split('=');
      const name = rawName?.trim();
      if (!name) {
        continue;
      }

      document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;`;
      document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=${window.location.hostname}`;
      document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;domain=.${window.location.hostname}`;
    }
  } catch (error) {
    console.warn('Unable to clear admin cookies', error);
  }
}

export function persistAdminAuthToken(token: string, rememberMe: boolean): void {
  if (typeof window === 'undefined') {
    return;
  }

  const storage = rememberMe ? window.localStorage : window.sessionStorage;

  try {
    storage.setItem('admin_token', token);
  } catch (error) {
    console.warn('Unable to persist admin token to storage', error);
  }

  const secureAttribute = window.location.protocol === 'https:' ? 'Secure;' : '';
  const maxAge = rememberMe ? 'max-age=604800;' : 'max-age=3600;';
  document.cookie = `admin_token=${token}; path=/; SameSite=Strict; ${maxAge} ${secureAttribute}`;
}
