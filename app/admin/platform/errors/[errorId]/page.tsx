'use client';

import React, { useState, useEffect } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useParams, useRouter } from 'next/navigation';
import { Card } from '@/components/ui/Card';
import { useAdmin } from '@/contexts/AdminContext';
import { formatDateTime } from '@/utils/dateFormat';
import { toast } from 'sonner';

interface ErrorDetails {
  error_id: string;
  error_type: string;
  message: string;
  stack_trace: string;
  severity: string;
  timestamp: string;
  acknowledged: boolean;
  acknowledged_by?: string;
  acknowledged_at?: string;
  request?: {
    method: string;
    endpoint: string;
    ip: string;
    user_agent: string;
    user_id?: string;
    body?: any;
    query_params?: any;
    headers?: Record<string, string>;
  };
  response?: {
    status_code?: number;
    error_code?: string;
    response_message?: string;
  };
  context?: {
    [key: string]: any;
  };
  // Enhanced debugging fields
  environment?: string;
  user_authenticated?: boolean;
  error_source?: string;
  metadata?: Record<string, any>;
  full_error_message?: string;
  exception_type?: string;
  troubleshooting_hints?: string[];
}

export default function ErrorDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const { token, isLoading: authLoading } = useAdmin();
  const errorId = params.errorId as string;

  const [error, setError] = useState<ErrorDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    const fetchErrorDetails = async () => {
      try {
        const baseUrl = getApiBaseUrl();

        if (!token) {
          setFetchError('Authentication required. Please log in.');
          setLoading(false);
          return;
        }

        const response = await fetch(`${baseUrl}/admin/platform/errors/${errorId}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          credentials: 'include',
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => null);
          const errorMessage = errorData?.detail || `Failed to fetch error details: ${response.statusText}`;
          throw new Error(errorMessage);
        }

        const data = await response.json();
        setError(data);
        setFetchError(null);
      } catch (err) {
        console.error('Error fetching error details:', err);
        setFetchError(err instanceof Error ? err.message : 'Failed to load error details');
      } finally {
        setLoading(false);
      }
    };

    if (!authLoading && errorId) {
      fetchErrorDetails();
    }
  }, [authLoading, errorId, token]);

  const handleAcknowledge = async () => {
    try {
      const baseUrl = getApiBaseUrl();

      const response = await fetch(`${baseUrl}/admin/platform/errors/${errorId}/acknowledge`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        credentials: 'include',
      });

      if (response.ok) {
        setError(prev => prev ? { ...prev, acknowledged: true } : null);
        toast.success('Error acknowledged successfully');
      } else {
        if (response.status === 404) {
          setFetchError('Error not found. It may have been acknowledged or deleted already.');
          setError(null);
          return;
        }

        const errorData = await response.json().catch(() => null);
        const errorMessage = errorData?.detail || 'Failed to acknowledge error';
        throw new Error(errorMessage);
      }
    } catch (err) {
      console.error('Error acknowledging error:', err);
      toast.error(`Failed to acknowledge error: ${err instanceof Error ? err.message : 'An unknown error occurred'}`);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading error details...</p>
        </div>
      </div>
    );
  }

  if (fetchError || !error) {
    return (
      <div className="min-h-screen p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6">
            <h2 className="text-red-800 dark:text-red-400 font-semibold mb-2">Error Loading Details</h2>
            <p className="text-red-600 dark:text-red-300">{fetchError || 'Error not found'}</p>
            <button
              onClick={() => router.back()}
              className="mt-4 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
            >
              ← Go Back
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <div className="bg-white dark:bg-slate-800 shadow-sm border-b dark:border-slate-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between py-6">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => router.back()}
                className="text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
              >
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Error Details</h1>
                <p className="text-sm text-gray-500 dark:text-gray-400">Error ID: {error.error_id}</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              {!error.acknowledged && (
                <button
                  onClick={handleAcknowledge}
                  className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Mark as Acknowledged
                </button>
              )}
              {error.acknowledged && (
                <span className="px-3 py-2 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400 rounded-lg text-sm font-medium">
                  ✓ Acknowledged
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Error Overview */}
        <Card className="p-6">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <div className="flex items-center space-x-3 mb-2">
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                  error.severity === 'critical' ? 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400' : 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-400'
                }`}>
                  {error.severity.toUpperCase()}
                </span>
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                  {error.exception_type || error.error_type}
                </h2>
              </div>
              <p className="text-gray-700 dark:text-gray-300 text-lg mb-3">{error.message}</p>
              {error.full_error_message && error.full_error_message !== error.message && (
                <div className="bg-gray-50 dark:bg-slate-700 rounded p-3 mb-3 border-l-4 border-orange-500">
                  <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">Full Error Message:</p>
                  <p className="text-gray-800 dark:text-gray-200 text-sm font-mono">{error.full_error_message}</p>
                </div>
              )}
              <div className="flex flex-wrap gap-4 text-sm text-gray-500 dark:text-gray-400">
                <span>
                  Occurred at {formatDateTime(error.timestamp, {
                    month: 'long',
                    day: 'numeric',
                    year: 'numeric',
                    hour: 'numeric',
                    minute: '2-digit',
                    second: '2-digit'
                  })}
                </span>
                {error.environment && (
                  <span className="flex items-center gap-1">
                    <span className={`w-2 h-2 rounded-full ${error.environment === 'production' ? 'bg-red-500' : 'bg-yellow-500'}`} />
                    {error.environment}
                  </span>
                )}
                {error.error_source && (
                  <span className="px-2 py-0.5 bg-gray-200 dark:bg-slate-600 rounded text-xs">
                    {error.error_source}
                  </span>
                )}
              </div>
              {error.acknowledged && error.acknowledged_by && (
                <p className="text-sm text-green-600 dark:text-green-400 mt-2">
                  Acknowledged by {error.acknowledged_by}
                  {error.acknowledged_at && ` on ${formatDateTime(error.acknowledged_at, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}`}
                </p>
              )}
            </div>
          </div>
        </Card>

        {/* Request Information */}
        {error.request && (
          <Card className="p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Request Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="text-sm font-medium text-gray-500 dark:text-gray-400 block mb-1">Method</label>
                <p className="text-gray-900 dark:text-white font-mono">
                  <span className="px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-400 rounded text-sm font-semibold">
                    {error.request.method}
                  </span>
                </p>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-500 dark:text-gray-400 block mb-1">Endpoint</label>
                <p className="text-gray-900 dark:text-white font-mono text-sm">{error.request.endpoint}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-500 dark:text-gray-400 block mb-1">IP Address</label>
                <p className="text-gray-900 dark:text-white font-mono text-sm">{error.request.ip}</p>
              </div>
              {error.request.user_id && (
                <div>
                  <label className="text-sm font-medium text-gray-500 dark:text-gray-400 block mb-1">User ID</label>
                  <p className="text-gray-900 dark:text-white font-mono text-sm">{error.request.user_id}</p>
                </div>
              )}
            </div>

            {error.request.user_agent && (
              <div className="mb-4">
                <label className="text-sm font-medium text-gray-500 dark:text-gray-400 block mb-1">User Agent</label>
                <p className="text-gray-700 dark:text-gray-300 text-sm break-all">{error.request.user_agent}</p>
              </div>
            )}

            {error.request.query_params && Object.keys(error.request.query_params).length > 0 && (
              <div className="mb-4">
                <label className="text-sm font-medium text-gray-500 dark:text-gray-400 block mb-2">Query Parameters</label>
                <div className="bg-gray-50 dark:bg-slate-700 rounded p-3 border border-gray-200 dark:border-slate-600">
                  <pre className="text-sm text-gray-800 dark:text-gray-200 overflow-x-auto">
                    {JSON.stringify(error.request.query_params, null, 2)}
                  </pre>
                </div>
              </div>
            )}

            {error.request.body && (
              <div>
                <label className="text-sm font-medium text-gray-500 dark:text-gray-400 block mb-2">Request Body</label>
                <div className="bg-gray-50 dark:bg-slate-700 rounded p-3 border border-gray-200 dark:border-slate-600">
                  <pre className="text-sm text-gray-800 dark:text-gray-200 overflow-x-auto">
                    {typeof error.request.body === 'string'
                      ? error.request.body
                      : JSON.stringify(error.request.body, null, 2)
                    }
                  </pre>
                </div>
              </div>
            )}
          </Card>
        )}

        {/* Stack Trace */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Stack Trace</h3>
            {error.stack_trace && (
              <button
                onClick={() => {
                  navigator.clipboard.writeText(error.stack_trace);
                  toast.success('Stack trace copied to clipboard');
                }}
                className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
              >
                Copy to clipboard
              </button>
            )}
          </div>
          {error.stack_trace ? (
            <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto max-h-96 overflow-y-auto">
              <pre className="text-sm text-gray-100 font-mono whitespace-pre-wrap">
                {error.stack_trace}
              </pre>
            </div>
          ) : (
            <div className="bg-gray-100 dark:bg-slate-700 rounded-lg p-6 text-center">
              <p className="text-gray-500 dark:text-gray-400">
                No stack trace available for this error.
              </p>
              <p className="text-sm text-gray-400 dark:text-gray-500 mt-2">
                This may be a handled exception or the error was logged from audit logs.
              </p>
            </div>
          )}
        </Card>

        {/* Response Information */}
        {error.response && (error.response.status_code || error.response.error_code) && (
          <Card className="p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Response Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {error.response.status_code && (
                <div>
                  <label className="text-sm font-medium text-gray-500 dark:text-gray-400 block mb-1">Status Code</label>
                  <p className={`text-lg font-mono font-bold ${
                    error.response.status_code >= 500 ? 'text-red-600 dark:text-red-400' :
                    error.response.status_code >= 400 ? 'text-orange-600 dark:text-orange-400' :
                    'text-green-600 dark:text-green-400'
                  }`}>
                    {error.response.status_code}
                  </p>
                </div>
              )}
              {error.response.error_code && (
                <div>
                  <label className="text-sm font-medium text-gray-500 dark:text-gray-400 block mb-1">Error Code</label>
                  <p className="text-gray-900 dark:text-white font-mono">{error.response.error_code}</p>
                </div>
              )}
              {error.response.response_message && (
                <div className="md:col-span-3">
                  <label className="text-sm font-medium text-gray-500 dark:text-gray-400 block mb-1">Response Message</label>
                  <p className="text-gray-700 dark:text-gray-300">{error.response.response_message}</p>
                </div>
              )}
            </div>
          </Card>
        )}

        {/* Additional Context */}
        {error.context && Object.keys(error.context).length > 0 && (
          <Card className="p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Additional Context</h3>
            <div className="bg-gray-50 dark:bg-slate-700 rounded p-4 border border-gray-200 dark:border-slate-600">
              <pre className="text-sm text-gray-800 dark:text-gray-200 overflow-x-auto">
                {JSON.stringify(error.context, null, 2)}
              </pre>
            </div>
          </Card>
        )}

        {/* Metadata */}
        {error.metadata && Object.keys(error.metadata).length > 0 && (
          <Card className="p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Error Metadata</h3>
            <div className="bg-gray-50 dark:bg-slate-700 rounded p-4 border border-gray-200 dark:border-slate-600">
              <pre className="text-sm text-gray-800 dark:text-gray-200 overflow-x-auto">
                {JSON.stringify(error.metadata, null, 2)}
              </pre>
            </div>
          </Card>
        )}

        {/* Troubleshooting Steps - Dynamic or Fallback */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Troubleshooting Steps</h3>
          <ol className="list-decimal list-inside space-y-2 text-gray-700 dark:text-gray-300">
            {error.troubleshooting_hints && error.troubleshooting_hints.length > 0 ? (
              error.troubleshooting_hints.map((hint, idx) => (
                <li key={idx}>{hint}</li>
              ))
            ) : (
              <>
                <li>Review the stack trace above to identify the source of the error</li>
                <li>Check if this is a recurring issue by searching for similar errors</li>
                <li>Verify the request parameters and endpoint configuration</li>
                {error.request?.user_id && <li>Contact the user (ID: {error.request.user_id}) for more context if needed</li>}
                <li>Check application logs for additional context around this timestamp</li>
                <li>If this is a critical bug, create a ticket in your issue tracker</li>
              </>
            )}
          </ol>
        </Card>

        {/* Quick Actions */}
        <div className="flex space-x-4">
          <button
            onClick={() => router.push('/admin/platform')}
            className="flex-1 bg-white dark:bg-slate-800 border border-gray-300 dark:border-slate-600 text-gray-700 dark:text-gray-300 px-4 py-3 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors font-medium"
          >
            ← Back to Dashboard
          </button>
          <button
            onClick={() => router.push('/admin/platform')}
            className="flex-1 bg-blue-600 text-white px-4 py-3 rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            View All Errors →
          </button>
        </div>
      </div>
    </div>
  );
}
