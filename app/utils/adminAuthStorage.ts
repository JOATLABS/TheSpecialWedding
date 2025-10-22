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
