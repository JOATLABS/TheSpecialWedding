'use client';

import React, { Component, ReactNode } from 'react';
import { Analytics } from '@vercel/analytics/next';

interface ErrorBoundaryState {
  hasError: boolean;
}

/**
 * Error boundary wrapper for Vercel Analytics.
 * Prevents the entire app from crashing if the analytics script fails to load
 * (e.g., when running locally or if the Vercel endpoint returns a 404).
 */
class AnalyticsErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // Log the error but don't crash the app
    console.warn('Analytics failed to load:', error.message);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      // Return nothing if analytics fails - the app should continue working
      return null;
    }
    return this.props.children;
  }
}

/**
 * Safe Analytics component that won't crash the app if Vercel Analytics
 * fails to load (404 errors, network issues, etc.).
 */
export function SafeAnalytics(): JSX.Element | null {
  // Only render analytics in production or when explicitly enabled
  const isProduction = process.env.NODE_ENV === 'production';
  const analyticsEnabled = process.env.NEXT_PUBLIC_VERCEL_ANALYTICS_ENABLED !== 'false';

  if (!isProduction && !analyticsEnabled) {
    return null;
  }

  return (
    <AnalyticsErrorBoundary>
      <Analytics />
    </AnalyticsErrorBoundary>
  );
}

export default SafeAnalytics;
