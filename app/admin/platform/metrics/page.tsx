'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import { formatDateTime } from '@/utils/dateFormat';

interface HealthMetrics {
  database: {
    status: string;
    latency_ms: number;
  };
  disk: {
    total_gb: number;
    used_gb: number;
    free_gb: number;
    percent_used: number;
  };
  memory: {
    total_gb: number;
    used_gb: number;
    available_gb: number;
    percent_used: number;
  };
  cpu: {
    percent: number;
    cores: number;
  };
}

interface ErrorMetrics {
  total_24h: number;
  critical_24h: number;
  recent_errors: Array<{
    error_id: string;
    error_type: string;
    message: string;
    timestamp: string;
    severity: string;
    endpoint?: string;
    user_id?: string;
  }>;
}

interface BusinessMetrics {
  total_users: number;
  active_subscriptions: number;
  total_weddings: number;
  mrr: number;
  arr: number;
}

interface PerformanceMetrics {
  slow_endpoints: Array<{
    path: string;
    method: string;
    avg_duration_ms: number;
    call_count: number;
  }>;
}

interface BackupStatus {
  last_backup_date?: string;
  last_backup_size_mb?: number;
  backup_count_30d?: number;
  status: string;
}

interface PlatformMetrics {
  generated_at: string;
  health: HealthMetrics;
  errors: ErrorMetrics;
  business: BusinessMetrics;
  performance: PerformanceMetrics;
  backups?: BackupStatus;
}

export default function PlatformMonitoringDashboard() {
  const [metrics, setMetrics] = useState<PlatformMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchMetrics = useCallback(async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');

      if (!token) {
        setError('Authentication required. Please log in.');
        setLoading(false);
        return;
      }

      const response = await fetch(`${baseUrl}/admin/platform/metrics`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch metrics: ${response.statusText}`);
      }

      const data = await response.json();
      setMetrics(data);
      setError(null);
    } catch (err) {
      console.error('Error fetching platform metrics:', err);
      setError(err instanceof Error ? err.message : 'Failed to load platform metrics');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();

    // Auto-refresh every 30 seconds if enabled
    if (autoRefresh) {
      const interval = setInterval(fetchMetrics, 30000);
      return () => clearInterval(interval);
    }
  }, [fetchMetrics, autoRefresh]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading platform monitoring data...</p>
        </div>
      </div>
    );
  }

  if (error && !metrics) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <h2 className="text-red-800 font-semibold mb-2">Error Loading Metrics</h2>
            <p className="text-red-600">{error}</p>
            <button
              onClick={fetchMetrics}
              className="mt-4 bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!metrics) {
    return null;
  }

  const getHealthStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'healthy':
      case 'connected':
        return 'text-green-600 bg-green-100';
      case 'warning':
        return 'text-yellow-600 bg-yellow-100';
      case 'critical':
      case 'error':
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const getUsageColor = (percent: number) => {
    if (percent >= 90) return 'bg-red-500';
    if (percent >= 75) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Platform Monitoring</h1>
              <p className="text-gray-600 text-sm mt-1">
                System health, errors, and operational metrics
              </p>
            </div>
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <label className="flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoRefresh}
                    onChange={(e) => setAutoRefresh(e.target.checked)}
                    className="mr-2"
                  />
                  <span className="text-sm text-gray-600">Auto-refresh (30s)</span>
                </label>
              </div>
              <button
                onClick={fetchMetrics}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
              >
                Refresh Now
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Last Updated */}
        <div className="mb-6 text-sm text-gray-500">
          Last updated: {formatDateTime(metrics.generated_at, {
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            second: '2-digit'
          })}
        </div>

        {/* System Health */}
        <section className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">System Health</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
            {/* Database Health */}
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-500">Database</h3>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${getHealthStatusColor(metrics.health.database.status)}`}>
                  {metrics.health.database.status}
                </span>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-2">
                {metrics.health.database.latency_ms.toFixed(1)}ms
              </div>
              <p className="text-sm text-gray-500">Response time</p>
            </Card>

            {/* CPU Usage */}
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-500">CPU</h3>
                <span className="text-xs text-gray-500">{metrics.health.cpu.cores} cores</span>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-2">
                {metrics.health.cpu.percent.toFixed(1)}%
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2 mt-3">
                <div
                  className={`h-2 rounded-full ${getUsageColor(metrics.health.cpu.percent)}`}
                  style={{ width: `${Math.min(metrics.health.cpu.percent, 100)}%` }}
                ></div>
              </div>
            </Card>

            {/* Memory Usage */}
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-500">Memory</h3>
                <span className="text-xs text-gray-500">
                  {metrics.health.memory.used_gb.toFixed(1)} / {metrics.health.memory.total_gb.toFixed(1)} GB
                </span>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-2">
                {metrics.health.memory.percent_used.toFixed(1)}%
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2 mt-3">
                <div
                  className={`h-2 rounded-full ${getUsageColor(metrics.health.memory.percent_used)}`}
                  style={{ width: `${Math.min(metrics.health.memory.percent_used, 100)}%` }}
                ></div>
              </div>
            </Card>

            {/* Disk Usage */}
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-gray-500">Disk</h3>
                <span className="text-xs text-gray-500">
                  {metrics.health.disk.free_gb.toFixed(1)} GB free
                </span>
              </div>
              <div className="text-3xl font-bold text-gray-900 mb-2">
                {metrics.health.disk.percent_used.toFixed(1)}%
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2 mt-3">
                <div
                  className={`h-2 rounded-full ${getUsageColor(metrics.health.disk.percent_used)}`}
                  style={{ width: `${Math.min(metrics.health.disk.percent_used, 100)}%` }}
                ></div>
              </div>
            </Card>
          </div>
        </section>

        {/* Error Monitoring */}
        <section className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Error Monitoring</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <Card className="p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="w-12 h-12 bg-red-100 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  </div>
                </div>
                <div className="ml-5">
                  <p className="text-sm font-medium text-gray-500">Total Errors (24h)</p>
                  <p className="text-2xl font-bold text-gray-900">{metrics.errors.total_24h}</p>
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-orange-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                </div>
                <div className="ml-5">
                  <p className="text-sm font-medium text-gray-500">Critical Errors (24h)</p>
                  <p className="text-2xl font-bold text-gray-900">{metrics.errors.critical_24h}</p>
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                </div>
                <div className="ml-5">
                  <p className="text-sm font-medium text-gray-500">Recent Errors</p>
                  <p className="text-2xl font-bold text-gray-900">{metrics.errors.recent_errors.length}</p>
                </div>
              </div>
            </Card>
          </div>

          {/* Recent Errors List */}
          {metrics.errors.recent_errors.length > 0 && (
            <Card className="overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
                <h3 className="text-sm font-semibold text-gray-900">Recent Errors</h3>
              </div>
              <div className="divide-y divide-gray-200">
                {metrics.errors.recent_errors.slice(0, 10).map((error) => (
                  <div key={error.error_id} className="p-4 hover:bg-gray-50 transition-colors">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-1">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                            error.severity === 'critical' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'
                          }`}>
                            {error.severity}
                          </span>
                          <span className="text-sm font-medium text-gray-900">{error.error_type}</span>
                          {error.endpoint && (
                            <span className="text-xs text-gray-500">{error.endpoint}</span>
                          )}
                        </div>
                        <p className="text-sm text-gray-700 mb-1">{error.message}</p>
                        <p className="text-xs text-gray-500">
                          {formatDateTime(error.timestamp, {
                            month: 'short',
                            day: 'numeric',
                            hour: 'numeric',
                            minute: '2-digit'
                          })}
                          {error.user_id && ` · User: ${error.user_id}`}
                        </p>
                      </div>
                      <a
                        href={`/admin/platform/errors/${error.error_id}`}
                        className="ml-4 text-blue-600 hover:text-blue-800 text-sm font-medium"
                      >
                        View Details →
                      </a>
                    </div>
                  </div>
                ))}
              </div>
              {metrics.errors.recent_errors.length > 10 && (
                <div className="px-6 py-3 bg-gray-50 border-t border-gray-200 text-center">
                  <a href="/admin/platform/errors" className="text-sm text-blue-600 hover:text-blue-800 font-medium">
                    View All Errors ({metrics.errors.recent_errors.length})
                  </a>
                </div>
              )}
            </Card>
          )}

          {metrics.errors.recent_errors.length === 0 && (
            <Card className="p-8 text-center">
              <div className="text-green-600 mb-2">
                <svg className="w-12 h-12 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <p className="text-gray-600">No errors in the last 24 hours!</p>
            </Card>
          )}
        </section>

        {/* Performance Metrics */}
        {metrics.performance.slow_endpoints.length > 0 && (
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Performance Issues</h2>
            <Card className="overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
                <h3 className="text-sm font-semibold text-gray-900">Slow Endpoints (&gt;1s avg)</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Endpoint</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Method</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Avg Duration</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Calls</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {metrics.performance.slow_endpoints.map((endpoint, idx) => (
                      <tr key={idx}>
                        <td className="px-6 py-4 text-sm font-mono text-gray-900">{endpoint.path}</td>
                        <td className="px-6 py-4 text-sm">
                          <span className="px-2 py-1 rounded bg-blue-100 text-blue-800 font-medium">
                            {endpoint.method}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm">
                          <span className="font-semibold text-orange-600">{endpoint.avg_duration_ms.toFixed(0)}ms</span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-600">{endpoint.call_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </section>
        )}

        {/* Business Overview */}
        <section className="mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Business Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-6">
            <Card className="p-6">
              <p className="text-sm font-medium text-gray-500 mb-2">Total Users</p>
              <p className="text-3xl font-bold text-gray-900">{metrics.business.total_users}</p>
            </Card>

            <Card className="p-6">
              <p className="text-sm font-medium text-gray-500 mb-2">Active Subscriptions</p>
              <p className="text-3xl font-bold text-gray-900">{metrics.business.active_subscriptions}</p>
            </Card>

            <Card className="p-6">
              <p className="text-sm font-medium text-gray-500 mb-2">Total Weddings</p>
              <p className="text-3xl font-bold text-gray-900">{metrics.business.total_weddings}</p>
            </Card>

            <Card className="p-6">
              <p className="text-sm font-medium text-gray-500 mb-2">MRR</p>
              <p className="text-3xl font-bold text-gray-900">${metrics.business.mrr.toFixed(0)}</p>
            </Card>

            <Card className="p-6">
              <p className="text-sm font-medium text-gray-500 mb-2">ARR</p>
              <p className="text-3xl font-bold text-gray-900">${metrics.business.arr.toFixed(0)}</p>
            </Card>
          </div>
        </section>

        {/* Backup Status */}
        {metrics.backups && (
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Backup Status</h2>
            <Card className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div>
                  <p className="text-sm font-medium text-gray-500 mb-2">Last Backup</p>
                  {metrics.backups.last_backup_date ? (
                    <p className="text-lg font-semibold text-gray-900">
                      {formatDateTime(metrics.backups.last_backup_date, {
                        month: 'short',
                        day: 'numeric',
                        hour: 'numeric',
                        minute: '2-digit'
                      })}
                    </p>
                  ) : (
                    <p className="text-lg text-gray-500">No backups yet</p>
                  )}
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500 mb-2">Backup Size</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {metrics.backups.last_backup_size_mb ? `${metrics.backups.last_backup_size_mb.toFixed(1)} MB` : 'N/A'}
                  </p>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500 mb-2">Backups (30 days)</p>
                  <p className="text-lg font-semibold text-gray-900">
                    {metrics.backups.backup_count_30d || 0}
                  </p>
                </div>
              </div>
            </Card>
          </section>
        )}

        {/* Quick Actions */}
        <section>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Quick Actions</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <a
              href="/admin/platform/errors"
              className="block p-4 bg-white border border-gray-200 rounded-lg hover:border-blue-500 hover:shadow-md transition-all"
            >
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <div>
                  <p className="font-medium text-gray-900">View All Errors</p>
                  <p className="text-sm text-gray-500">Browse error logs</p>
                </div>
              </div>
            </a>

            <a
              href="/admin/metrics"
              className="block p-4 bg-white border border-gray-200 rounded-lg hover:border-blue-500 hover:shadow-md transition-all"
            >
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                  <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <div>
                  <p className="font-medium text-gray-900">Business Analytics</p>
                  <p className="text-sm text-gray-500">View detailed metrics</p>
                </div>
              </div>
            </a>

            <a
              href="/admin/saas"
              className="block p-4 bg-white border border-gray-200 rounded-lg hover:border-blue-500 hover:shadow-md transition-all"
            >
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                  <svg className="w-5 h-5 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                <div>
                  <p className="font-medium text-gray-900">SaaS Management</p>
                  <p className="text-sm text-gray-500">Manage plans & content</p>
                </div>
              </div>
            </a>
          </div>
        </section>
      </div>
    </div>
  );
}
