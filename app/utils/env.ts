/**
 * Environment configuration utilities
 *
 * This module provides type-safe access to environment variables with required validation.
 * All environment variables are validated at runtime to ensure they are set.
 */

/**
 * Get the API base URL
 * @throws {Error} if NEXT_PUBLIC_API_BASE_URL is not set
 */
export function getApiBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_BASE_URL;
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
