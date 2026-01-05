/**
 * Environment configuration utilities
 *
 * This module provides type-safe access to environment variables with required validation.
 * All environment variables are validated at runtime to ensure they are set.
 */

/**
 * Get the API base URL
 *
 * For Coolify single-container deployments:
 * - Returns '/api/proxy' to use Next.js rewrites that proxy to localhost:8000
 *
 * For development or separate API deployments:
 * - Returns NEXT_PUBLIC_API_BASE_URL (e.g., http://localhost:8000 or https://api.thespecialwedding.com)
 */
export function getApiBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_BASE_URL;

  // In production without a configured API URL, use proxy path
  // This handles Coolify single-container deployments where frontend proxies to backend
  if (!url || url === 'http://localhost:8000') {
    // Check if we're in browser and on a production domain
    if (typeof window !== 'undefined') {
      const hostname = window.location.hostname;
      // If on production domain without separate API subdomain, use proxy
      if (hostname.includes('thespecialwedding') && !url?.includes('api.thespecialwedding')) {
        return '/api/proxy';
      }
    }
  }

  if (!url) {
    throw new Error(
      'NEXT_PUBLIC_API_BASE_URL environment variable is required. ' +
      'Please set it in your .env file.'
    );
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
