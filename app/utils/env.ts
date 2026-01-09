/**
 * Environment configuration utilities
 *
 * This module provides type-safe access to environment variables with required validation.
 * All environment variables are validated at runtime to ensure they are set.
 * NO FALLBACKS - missing variables will throw errors and notify root admin.
 */

function reportConfigError(errorType: string, message: string, variableName: string, currentValue?: string): void {
  if (typeof window === 'undefined') return;

  const payload = JSON.stringify({
    error_type: errorType,
    message,
    variable_name: variableName,
    current_value: currentValue,
    hostname: window.location.hostname,
    user_agent: navigator.userAgent,
  });

  // Use sendBeacon for reliable delivery even if page crashes/navigates
  if (navigator.sendBeacon) {
    const blob = new Blob([payload], { type: 'application/json' });
    navigator.sendBeacon('/report-config-error', blob);
  } else {
    // Fallback to fetch (fire-and-forget)
    fetch('/report-config-error', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload,
      keepalive: true, // Ensures request completes even if page unloads
    }).catch(() => {});
  }
}

/**
 * Get the API base URL
 *
 * @throws {Error} if NEXT_PUBLIC_API_BASE_URL is not set or misconfigured
 * NO FALLBACKS - the build must have this variable properly baked in
 */
export function getApiBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_BASE_URL;

  if (!url) {
    const errorMsg = 'CRITICAL: NEXT_PUBLIC_API_BASE_URL environment variable is not set. ' +
      'This must be configured in your deployment environment. ' +
      'Check Coolify secrets or .env file.';
    console.error(errorMsg);
    reportConfigError('MissingEnvVar', errorMsg, 'NEXT_PUBLIC_API_BASE_URL');
    throw new Error(errorMsg);
  }

  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    const isLocalDev = hostname === 'localhost' || hostname === '127.0.0.1';

    if (!isLocalDev && url.includes('localhost')) {
      const errorMsg = `CRITICAL: NEXT_PUBLIC_API_BASE_URL is set to "${url}" but app is running on "${hostname}". ` +
        'The API URL was not properly configured during build. ' +
        'Ensure Coolify secrets are set correctly and rebuild.';
      console.error(errorMsg);
      reportConfigError('MisconfiguredEnvVar', errorMsg, 'NEXT_PUBLIC_API_BASE_URL', url);
      throw new Error(errorMsg);
    }
  }

  return url;
}

/**
 * Get the frontend base URL (for server-side use only)
 * @throws {Error} if FRONTEND_URL is not set
 */
export function getFrontendUrl(): string {
  const url = process.env.FRONTEND_URL;
  if (!url) {
    throw new Error(
      'FRONTEND_URL environment variable is required. ' +
      'Please set it in your .env file.'
    );
  }
  return url;
}

/**
 * Check if API base URL is configured
 */
export function isApiConfigured(): boolean {
  return !!process.env.NEXT_PUBLIC_API_BASE_URL;
}
