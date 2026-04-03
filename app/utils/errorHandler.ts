/**
 * Error handling utilities for consistent error messages and logging
 *
 * This module provides standardized error handling across the application
 * including error message formatting, categorization, and recovery suggestions
 */

export interface ApiError {
  message: string;
  status?: number;
  code?: string;
  recoveryAction?: string;
}

/**
 * Parse an error from fetch or other operations into a standardized format
 */
export function parseError(error: any): ApiError {
  // Handle Error objects
  if (error instanceof Error) {
    return {
      message: error.message,
      code: error.name,
    };
  }

  // Handle string errors
  if (typeof error === 'string') {
    return {
      message: error,
    };
  }

  // Handle objects with error structure
  if (error && typeof error === 'object') {
    return {
      message: error.message || error.detail || 'An unexpected error occurred',
      status: error.status || error.statusCode,
      code: error.code || error.type,
    };
  }

  // Fallback
  return {
    message: 'An unexpected error occurred',
  };
}

/**
 * Get user-friendly error message based on HTTP status code
 */
export function getErrorMessage(status?: number, detail?: string): string {
  if (detail) {
    return detail;
  }

  switch (status) {
    case 400:
      return 'Invalid request. Please check your input and try again.';
    case 401:
      return 'Your session has expired. Please log in again.';
    case 403:
      return 'You do not have permission to perform this action.';
    case 404:
      return 'The requested resource was not found.';
    case 409:
      return 'This resource already exists or has been modified. Please refresh and try again.';
    case 422:
      return 'The provided data is invalid. Please check your input.';
    case 429:
      return 'Too many requests. Please wait a moment and try again.';
    case 500:
      return 'Server error. Please try again later.';
    case 502:
    case 503:
      return 'Service temporarily unavailable. Please try again later.';
    case 0:
      return 'Network error. Please check your internet connection.';
    default:
      return 'An error occurred. Please try again.';
  }
}

/**
 * Determine if an error is recoverable and suggest action
 */
export function getRecoveryAction(status?: number): string | undefined {
  switch (status) {
    case 401:
      return 'refresh'; // Trigger re-authentication
    case 409:
      return 'refresh'; // Data conflict - user should refresh
    case 429:
      return 'retry'; // Rate limit - user should retry
    case 503:
      return 'retry'; // Service unavailable - user should retry
    default:
      return undefined;
  }
}

/**
 * Check if an error is a network error
 */
export function isNetworkError(error: any): boolean {
  if (error instanceof Error) {
    return (
      error.name === 'TypeError' ||
      error.name === 'NetworkError' ||
      error.message.includes('network') ||
      error.message.includes('fetch')
    );
  }
  return false;
}

/**
 * Check if an error is an authorization error
 */
export function isAuthError(status?: number): boolean {
  return status === 401 || status === 403;
}

/**
 * Log error safely without exposing sensitive information
 */
export function logError(error: any, context?: string): void {
  const parsed = parseError(error);

  // Only log in development or if it's a critical error
  if (process.env.NODE_ENV === 'development') {
    console.error(`[${context || 'Error'}]`, parsed);
  } else if (isAuthError(parsed.status)) {
    // Always log auth errors
    console.warn(`[${context || 'Auth Error'}]`, parsed.message);
  }
}

/**
 * Create a standardized error response
 */
export function createErrorResponse<T>(
  message: string,
  code?: string,
  status?: number
): { data: null; error: string; code?: string; status?: number } {
  return {
    data: null,
    error: message,
    ...(code && { code }),
    ...(status && { status }),
  };
}
