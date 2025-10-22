'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Card } from '@/components/ui/Card';
import { formatDateTime } from '@/utils/dateFormat';

interface ErrorSummary {
  error_id: string;
  error_type: string;
  message: string;
  timestamp: string;
  severity: string;
  endpoint?: string;
  user_id?: string;
  acknowledged: boolean;
}

type SeverityFilter = 'all' | 'critical' | 'warning';
type AcknowledgedFilter = 'all' | 'true' | 'false';

export default function AllErrorsPage() {
  const router = useRouter();
  const [errors, setErrors] = useState<ErrorSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all');
  const [acknowledgedFilter, setAcknowledgedFilter] = useState<AcknowledgedFilter>('false');
  const [limit, setLimit] = useState(50);

  const fetchErrors = useCallback(async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');

      if (!token) {
        setError('Authentication required. Please log in.');
        setLoading(false);
        return;
      }

      const params = new URLSearchParams({
        limit: limit.toString(),
        ...(severityFilter !== 'all' && { severity: severityFilter }),
        ...(acknowledgedFilter !== 'all' && { acknowledged: acknowledgedFilter })
      });

      const response = await fetch(`${baseUrl}/admin/platform/errors/recent?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch errors: ${response.statusText}`);
      }

      const data = await response.json();
      setErrors(data.errors || []);
      setError(null);
    } catch (err) {
      console.error('Error fetching errors:', err);
      setError(err instanceof Error ? err.message : 'Failed to load errors');
    } finally {
      setLoading(false);
    }
  }, [limit, severityFilter, acknowledgedFilter]);

  useEffect(() => {
    fetchErrors();
  }, [fetchErrors]);

  const handleAcknowledgeAll = async () => {
    if (!confirm('Mark all filtered errors as acknowledged?')) {
      return;
    }

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');

      const unacknowledgedErrors = errors.filter(e => !e.acknowledged);

      for (const error of unacknowledgedErrors) {
        await fetch(`${baseUrl}/admin/platform/errors/${error.error_id}/acknowledge`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });
      }

      alert(`Acknowledged ${unacknowledgedErrors.length} errors`);
      fetchErrors();
    } catch (err) {
      console.error('Error acknowledging errors:', err);
      alert('Failed to acknowledge errors');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading errors...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between py-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Error Logs</h1>
              <p className="text-gray-600 text-sm mt-1">
                Browse and manage application errors
              </p>
            </div>
            <div className="flex items-center space-x-3">
              <button
                onClick={fetchErrors}
                className="bg-white border border-gray-300 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-50 transition-colors text-sm font-medium"
              >
                Refresh
              </button>
              <button
                onClick={() => router.push('/admin/platform/metrics')}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
              >
                ← Back to Dashboard
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Filters */}
        <Card className="p-6 mb-6">
          <div className="flex flex-wrap items-center gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Severity</label>
              <select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value as SeverityFilter)}
                className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Severities</option>
                <option value="critical">Critical Only</option>
                <option value="warning">Warning Only</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
              <select
                value={acknowledgedFilter}
                onChange={(e) => setAcknowledgedFilter(e.target.value as AcknowledgedFilter)}
                className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Status</option>
                <option value="false">Unacknowledged</option>
                <option value="true">Acknowledged</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Limit</label>
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value={25}>25 errors</option>
                <option value={50}>50 errors</option>
                <option value={100}>100 errors</option>
                <option value={200}>200 errors</option>
              </select>
            </div>

            <div className="ml-auto">
              {errors.some(e => !e.acknowledged) && (
                <button
                  onClick={handleAcknowledgeAll}
                  className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors text-sm font-medium"
                >
                  Acknowledge All Filtered
                </button>
              )}
            </div>
          </div>
        </Card>

        {/* Error Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card className="p-4">
            <p className="text-sm font-medium text-gray-500">Total Errors</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{errors.length}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm font-medium text-gray-500">Critical</p>
            <p className="text-2xl font-bold text-red-600 mt-1">
              {errors.filter(e => e.severity === 'critical').length}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm font-medium text-gray-500">Warnings</p>
            <p className="text-2xl font-bold text-yellow-600 mt-1">
              {errors.filter(e => e.severity === 'warning').length}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm font-medium text-gray-500">Unacknowledged</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">
              {errors.filter(e => !e.acknowledged).length}
            </p>
          </Card>
        </div>

        {/* Errors List */}
        {errors.length === 0 ? (
          <Card className="p-12 text-center">
            <div className="text-green-600 mb-4">
              <svg className="w-16 h-16 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">No Errors Found</h3>
            <p className="text-gray-600">
              {severityFilter !== 'all' || acknowledgedFilter !== 'all'
                ? 'Try adjusting your filters'
                : 'Your application is running smoothly!'
              }
            </p>
          </Card>
        ) : (
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Severity
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Error Type
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Message
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Endpoint
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Timestamp
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {errors.map((error) => (
                    <tr key={error.error_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                          error.severity === 'critical' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'
                        }`}>
                          {error.severity}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <p className="text-sm font-medium text-gray-900">{error.error_type}</p>
                      </td>
                      <td className="px-6 py-4">
                        <p className="text-sm text-gray-700 max-w-md truncate">{error.message}</p>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <p className="text-sm text-gray-500 font-mono">{error.endpoint || 'N/A'}</p>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <p className="text-sm text-gray-500">
                          {formatDateTime(error.timestamp, {
                            month: 'short',
                            day: 'numeric',
                            hour: 'numeric',
                            minute: '2-digit'
                          })}
                        </p>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {error.acknowledged ? (
                          <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs font-medium">
                            Acknowledged
                          </span>
                        ) : (
                          <span className="px-2 py-1 bg-gray-100 text-gray-800 rounded text-xs font-medium">
                            New
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right">
                        <button
                          onClick={() => router.push(`/admin/platform/errors/${error.error_id}`)}
                          className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                        >
                          View Details →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {errors.length > 0 && (
          <p className="text-center text-sm text-gray-500 mt-4">
            Showing {errors.length} error{errors.length !== 1 ? 's' : ''}
          </p>
        )}
      </div>
    </div>
  );
}
