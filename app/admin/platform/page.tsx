'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { Card } from '@/components/ui/Card';
import { formatDateTime } from '@/utils/dateFormat';
import { toast } from 'sonner';
import PageHeader from '../components/PageHeader';
import {
  Server,
  Database,
  Cpu,
  HardDrive,
  MemoryStick,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Clock,
  Zap,
  Shield,
  Activity,
  XCircle,
  ChevronRight,
  Loader2,
  Bell,
  MessageSquare
} from 'lucide-react';

// Types
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
    status?: string;
  };
  psutil_available: boolean;
}

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

interface ErrorMetrics {
  total_24h: number;
  critical_24h: number;
  recent_errors: ErrorSummary[];
}

interface EndpointPerformance {
  endpoint: string;
  avg_response_time_ms: number;
  min_response_time_ms: number;
  max_response_time_ms: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  request_count: number;
  error_count: number;
  error_rate: number;
  status: 'healthy' | 'moderate' | 'warning' | 'critical';
}

interface PerformanceMetrics {
  summary?: {
    total_requests_24h: number;
    total_errors_24h: number;
    overall_error_rate: number;
    overall_avg_response_time_ms: number;
    slow_endpoint_count: number;
    monitored_endpoint_count: number;
  };
  endpoints?: EndpointPerformance[];
  slow_endpoints: EndpointPerformance[];
}

interface BackupStatus {
  last_backup_date?: string;
  last_backup_size_mb?: number;
  backup_count_30d?: number;
  status: string;
}

interface WebPushHealth {
  status: string;
  configured: boolean;
  enabled: boolean;
  has_public_key?: boolean;
  has_private_key?: boolean;
  vapid_email?: string;
  total_subscriptions?: number;
  error?: string;
  checked_at?: string;
}

interface TwilioHealth {
  status: string;
  configured: boolean;
  account_sid_set?: boolean;
  auth_token_set?: boolean;
  messaging_service_sid_set?: boolean;
  status_callback_configured?: boolean;
  delivery_stats_24h?: {
    total_sent: number;
    delivered: number;
    failed: number;
    undelivered: number;
    pending: number;
    delivery_rate: number;
  };
  error?: string;
}

interface ServicesMetrics {
  web_push?: WebPushHealth;
  twilio?: TwilioHealth;
}

interface PlatformMetrics {
  generated_at: string;
  health: HealthMetrics;
  errors: ErrorMetrics;
  performance: PerformanceMetrics;
  services?: ServicesMetrics;
  backups?: BackupStatus;
}

type TabType = 'health' | 'errors' | 'performance' | 'backups';
type SeverityFilter = 'all' | 'critical' | 'warning';
type AcknowledgedFilter = 'all' | 'true' | 'false';

export default function PlatformInfrastructurePage() {
  const router = useRouter();
  const { userProfile } = useAdmin();
  const [metrics, setMetrics] = useState<PlatformMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('health');

  // Error filtering state
  const [allErrors, setAllErrors] = useState<ErrorSummary[]>([]);
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all');
  const [acknowledgedFilter, setAcknowledgedFilter] = useState<AcknowledgedFilter>('all');
  const [errorLimit, setErrorLimit] = useState(50);
  const [loadingErrors, setLoadingErrors] = useState(false);
  const [acknowledgingIds, setAcknowledgingIds] = useState<Set<string>>(new Set());
  const [acknowledgingAll, setAcknowledgingAll] = useState(false);

  // Cursor-based pagination state
  const [totalErrors, setTotalErrors] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [hasNextPage, setHasNextPage] = useState(false);
  const [hasPrevPage, setHasPrevPage] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [prevCursor, setPrevCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);  // Track cursor history for "First" button

  // Access control - ROOT ADMIN only
  useEffect(() => {
    if (userProfile && !userProfile.is_root_admin) {
      router.push('/admin/planner');
    }
  }, [userProfile, router]);

  const fetchMetrics = useCallback(async () => {
    try {
      const baseUrl = getApiBaseUrl();
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');

      if (!token) {
        setError('Authentication required. Please log in.');
        setLoading(false);
        return;
      }

      const response = await fetch(`${baseUrl}/admin/platform/health`, {
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

  const fetchAllErrors = useCallback(async (cursor?: string | null, direction: 'next' | 'prev' = 'next') => {
    try {
      setLoadingErrors(true);
      const baseUrl = getApiBaseUrl();
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');

      if (!token) return;

      const params = new URLSearchParams({
        limit: errorLimit.toString(),
        direction,
        ...(cursor && { cursor }),
        ...(severityFilter !== 'all' && { severity: severityFilter }),
        ...(acknowledgedFilter !== 'all' && { acknowledged: acknowledgedFilter })
      });

      const response = await fetch(`${baseUrl}/admin/platform/errors/recent?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setAllErrors(data.errors || []);
        setTotalErrors(data.total || 0);
        setTotalPages(data.total_pages || 1);
        setHasNextPage(data.has_next || false);
        setHasPrevPage(data.has_prev || false);
        setNextCursor(data.next_cursor || null);
        setPrevCursor(data.prev_cursor || null);
      }
    } catch (err) {
      console.error('Error fetching errors:', err);
    } finally {
      setLoadingErrors(false);
    }
  }, [errorLimit, severityFilter, acknowledgedFilter]);

  useEffect(() => {
    fetchMetrics();

    if (autoRefresh) {
      const interval = setInterval(fetchMetrics, 30000);
      return () => clearInterval(interval);
    }
  }, [fetchMetrics, autoRefresh]);

  useEffect(() => {
    if (activeTab === 'errors') {
      fetchAllErrors();
    }
  }, [activeTab, fetchAllErrors]);

  // Reset cursor when filters change
  useEffect(() => {
    setNextCursor(null);
    setPrevCursor(null);
    setCursorHistory([]);
  }, [errorLimit, severityFilter, acknowledgedFilter]);

  const handleNextPage = () => {
    if (nextCursor && hasNextPage) {
      // Save current first item's cursor to history for going back
      if (allErrors.length > 0 && allErrors[0].error_id) {
        setCursorHistory(prev => [...prev, allErrors[0].error_id]);
      }
      fetchAllErrors(nextCursor, 'next');
    }
  };

  const handlePrevPage = () => {
    if (cursorHistory.length > 0) {
      // Go back using cursor history
      const newHistory = [...cursorHistory];
      const prevPageCursor = newHistory.pop();
      setCursorHistory(newHistory);
      // If we're at the beginning of history, fetch first page
      if (newHistory.length === 0) {
        fetchAllErrors(undefined, 'next');
      } else {
        fetchAllErrors(prevPageCursor, 'prev');
      }
    } else if (prevCursor) {
      fetchAllErrors(prevCursor, 'prev');
    }
  };

  const handleFirstPage = () => {
    setCursorHistory([]);
    fetchAllErrors(undefined, 'next');
  };

  const handleAcknowledgeError = async (errorId: string) => {
    setAcknowledgingIds(prev => new Set(prev).add(errorId));
    try {
      const baseUrl = getApiBaseUrl();
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');

      const response = await fetch(`${baseUrl}/admin/platform/errors/${errorId}/acknowledge`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        toast.success('Error acknowledged');
        fetchAllErrors();
        fetchMetrics();
        return;
      }

      if (response.status === 404) {
          toast.info('Error not found, it may have been handled already. Refreshing list.');
          fetchAllErrors();
          return;
      }

      const errorData = await response.json().catch(() => null);
      const errorMessage = errorData?.detail || 'Failed to acknowledge error';
      throw new Error(errorMessage);

    } catch (err) {
      console.error('Error acknowledging error:', err);
      toast.error(`Acknowledge failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setAcknowledgingIds(prev => {
        const next = new Set(prev);
        next.delete(errorId);
        return next;
      });
    }
  };

  const handleAcknowledgeAll = async () => {
    const unacknowledgedErrors = allErrors.filter(e => !e.acknowledged);
    if (unacknowledgedErrors.length === 0) return;

    setAcknowledgingAll(true);
    try {
      const baseUrl = getApiBaseUrl();
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');

      // Use bulk acknowledge endpoint for better performance
      const response = await fetch(`${baseUrl}/admin/platform/errors/acknowledge-bulk`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          error_ids: unacknowledgedErrors.map(e => e.error_id)
        })
      });

      if (response.ok) {
        const data = await response.json();
        const requested = data.requested_count || unacknowledgedErrors.length;
        const acknowledged = data.acknowledged_count || 0;

        if (acknowledged < requested) {
          toast.warning(`Acknowledged ${acknowledged} of ${requested} errors`);
        } else {
          toast.success(`Acknowledged ${acknowledged} errors`);
        }
      } else {
        const errorData = await response.json().catch(() => null);
        const errorMessage = errorData?.detail || 'Failed to acknowledge errors';
        toast.error(errorMessage);
      }

      fetchAllErrors();
      fetchMetrics();
    } catch (err) {
      console.error('Error acknowledging errors:', err);
      toast.error('Failed to acknowledge errors');
    } finally {
      setAcknowledgingAll(false);
    }
  };

  const getHealthStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'healthy':
      case 'connected':
        return 'text-green-600 bg-green-100 dark:bg-green-900/30 dark:text-green-400';
      case 'warning':
        return 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30 dark:text-yellow-400';
      case 'critical':
      case 'error':
        return 'text-red-600 bg-red-100 dark:bg-red-900/30 dark:text-red-400';
      default:
        return 'text-gray-600 bg-gray-100 dark:bg-gray-700 dark:text-gray-400';
    }
  };

  const getUsageColor = (percent: number) => {
    if (percent >= 90) return 'bg-red-500';
    if (percent >= 75) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  const getUsageStatus = (percent: number) => {
    if (percent >= 90) return { text: 'Critical', color: 'text-red-600 dark:text-red-400' };
    if (percent >= 75) return { text: 'Warning', color: 'text-yellow-600 dark:text-yellow-400' };
    return { text: 'Healthy', color: 'text-green-600 dark:text-green-400' };
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading platform infrastructure...</p>
        </div>
      </div>
    );
  }

  if (error && !metrics) {
    return (
      <div className="space-y-6">
        <div>
          <Card className="p-6 border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20">
            <div className="flex items-center gap-3 mb-4">
              <AlertTriangle className="w-6 h-6 text-red-600 dark:text-red-400" />
              <h2 className="text-lg font-semibold text-red-800 dark:text-red-300">Error Loading Metrics</h2>
            </div>
            <p className="text-red-600 dark:text-red-300 mb-4">{error}</p>
            <button
              onClick={fetchMetrics}
              className="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition-colors"
            >
              Retry
            </button>
          </Card>
        </div>
      </div>
    );
  }

  if (!metrics) return null;

  const tabs = [
    { id: 'health' as TabType, label: 'System Health', icon: Activity },
    { id: 'errors' as TabType, label: `Errors (${metrics.errors?.total_24h || 0})`, icon: AlertTriangle },
    { id: 'performance' as TabType, label: 'Performance', icon: Zap },
    { id: 'backups' as TabType, label: 'Backups', icon: Shield },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Infrastructure"
        description="System health, errors, performance, and backups"
      >
        <label className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
            className="rounded border-slate-300 dark:border-slate-600"
          />
          Auto-refresh (30s)
        </label>
        <button
          onClick={() => { fetchMetrics(); if (activeTab === 'errors') fetchAllErrors(); }}
          className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors text-sm font-medium"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </PageHeader>

      {/* Last Updated */}
      <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
        <Clock className="w-4 h-4" />
        Last updated: {formatDateTime(metrics.generated_at, {
          month: 'short',
          day: 'numeric',
          hour: 'numeric',
          minute: '2-digit',
          second: '2-digit'
        })}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="flex gap-4">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                    : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'health' && (
        <div className="space-y-6">
          {/* System Health Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
            {/* Database */}
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Database className="w-5 h-5 text-blue-500" />
                  <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Database</h3>
                </div>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${getHealthStatusColor(metrics.health?.database?.status || 'unknown')}`}>
                  {metrics.health?.database?.status || 'N/A'}
                </span>
              </div>
              <div className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-1">
                {metrics.health?.database?.latency_ms?.toFixed(1) || '0'}ms
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Response time</p>
            </Card>

            {/* CPU */}
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Cpu className="w-5 h-5 text-purple-500" />
                  <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">CPU</h3>
                </div>
                <span className="text-xs text-gray-500 dark:text-gray-400">{metrics.health?.cpu?.cores || 0} cores</span>
              </div>
              <div className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-1">
                {metrics.health?.cpu?.percent?.toFixed(1) || '0'}%
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 mt-3">
                <div
                  className={`h-2 rounded-full transition-all ${getUsageColor(metrics.health?.cpu?.percent || 0)}`}
                  style={{ width: `${Math.min(metrics.health?.cpu?.percent || 0, 100)}%` }}
                />
              </div>
              <p className={`text-sm mt-2 ${getUsageStatus(metrics.health?.cpu?.percent || 0).color}`}>
                {getUsageStatus(metrics.health?.cpu?.percent || 0).text}
              </p>
            </Card>

            {/* Memory */}
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <MemoryStick className="w-5 h-5 text-green-500" />
                  <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Memory</h3>
                </div>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {metrics.health?.memory?.used_gb?.toFixed(1) || '0'} / {metrics.health?.memory?.total_gb?.toFixed(1) || '0'} GB
                </span>
              </div>
              <div className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-1">
                {metrics.health?.memory?.percent_used?.toFixed(1) || '0'}%
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 mt-3">
                <div
                  className={`h-2 rounded-full transition-all ${getUsageColor(metrics.health?.memory?.percent_used || 0)}`}
                  style={{ width: `${Math.min(metrics.health?.memory?.percent_used || 0, 100)}%` }}
                />
              </div>
              <p className={`text-sm mt-2 ${getUsageStatus(metrics.health?.memory?.percent_used || 0).color}`}>
                {getUsageStatus(metrics.health?.memory?.percent_used || 0).text}
              </p>
            </Card>

            {/* Disk */}
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <HardDrive className="w-5 h-5 text-orange-500" />
                  <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Disk</h3>
                </div>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {metrics.health?.disk?.free_gb?.toFixed(1) || '0'} GB free
                </span>
              </div>
              <div className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-1">
                {metrics.health?.disk?.percent_used?.toFixed(1) || '0'}%
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 mt-3">
                <div
                  className={`h-2 rounded-full transition-all ${getUsageColor(metrics.health?.disk?.percent_used || 0)}`}
                  style={{ width: `${Math.min(metrics.health?.disk?.percent_used || 0, 100)}%` }}
                />
              </div>
              <p className={`text-sm mt-2 ${getUsageStatus(metrics.health?.disk?.percent_used || 0).color}`}>
                {getUsageStatus(metrics.health?.disk?.percent_used || 0).text}
              </p>
            </Card>
          </div>

          {/* Services Health */}
          <Card className="p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">External Services</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {/* Web Push Notifications */}
              <div className="p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Bell className="w-5 h-5 text-indigo-500" />
                    <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">Push Notifications (Web Push)</h4>
                  </div>
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    metrics.services?.web_push?.status === 'healthy'
                      ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                      : metrics.services?.web_push?.status === 'disabled'
                      ? 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                      : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                  }`}>
                    {metrics.services?.web_push?.status || 'unknown'}
                  </span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-gray-400">Configured</span>
                    <span className={metrics.services?.web_push?.configured ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                      {metrics.services?.web_push?.configured ? 'Yes' : 'No'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-gray-400">VAPID Keys</span>
                    <span className={metrics.services?.web_push?.has_public_key && metrics.services?.web_push?.has_private_key ? 'text-green-600 dark:text-green-400' : 'text-gray-500 dark:text-gray-400'}>
                      {metrics.services?.web_push?.has_public_key && metrics.services?.web_push?.has_private_key ? 'Set' : 'Missing'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-gray-400">Subscriptions</span>
                    <span className="text-gray-700 dark:text-gray-300 font-medium">
                      {metrics.services?.web_push?.total_subscriptions ?? 0}
                    </span>
                  </div>
                  {metrics.services?.web_push?.vapid_email && (
                    <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                      <span className="text-gray-500 dark:text-gray-400 text-xs">Contact: </span>
                      <span className="text-gray-700 dark:text-gray-300 text-xs font-mono break-all">
                        {metrics.services?.web_push?.vapid_email}
                      </span>
                    </div>
                  )}
                  {metrics.services?.web_push?.error && (
                    <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                      <div className="flex items-start gap-1">
                        <AlertTriangle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
                        <span className="text-red-600 dark:text-red-400 text-xs">
                          {metrics.services?.web_push?.error}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Twilio SMS Service */}
              <div className="p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="w-5 h-5 text-emerald-500" />
                    <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">SMS Service (Twilio)</h4>
                  </div>
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    metrics.services?.twilio?.status === 'healthy'
                      ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                      : metrics.services?.twilio?.status === 'not_configured'
                      ? 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                      : metrics.services?.twilio?.status === 'degraded' || metrics.services?.twilio?.status === 'warning'
                      ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
                      : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                  }`}>
                    {metrics.services?.twilio?.status || 'unknown'}
                  </span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-gray-400">Configured</span>
                    <span className={metrics.services?.twilio?.configured ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                      {metrics.services?.twilio?.configured ? 'Yes' : 'No'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-gray-400">Status Callback</span>
                    <span className={metrics.services?.twilio?.status_callback_configured ? 'text-green-600 dark:text-green-400' : 'text-yellow-600 dark:text-yellow-400'}>
                      {metrics.services?.twilio?.status_callback_configured ? 'Enabled' : 'Not Set'}
                    </span>
                  </div>
                  {metrics.services?.twilio?.delivery_stats_24h && metrics.services.twilio.delivery_stats_24h.total_sent > 0 && (
                    <>
                      <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                        <span className="text-gray-500 dark:text-gray-400 text-xs font-medium">24h Delivery Stats</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500 dark:text-gray-400">Total Sent</span>
                        <span className="text-gray-700 dark:text-gray-300 font-medium">
                          {metrics.services.twilio.delivery_stats_24h.total_sent}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500 dark:text-gray-400">Delivered</span>
                        <span className="text-green-600 dark:text-green-400 font-medium">
                          {metrics.services.twilio.delivery_stats_24h.delivered}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500 dark:text-gray-400">Failed</span>
                        <span className={metrics.services.twilio.delivery_stats_24h.failed > 0 ? 'text-red-600 dark:text-red-400 font-medium' : 'text-gray-500 dark:text-gray-400'}>
                          {metrics.services.twilio.delivery_stats_24h.failed}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500 dark:text-gray-400">Pending</span>
                        <span className="text-yellow-600 dark:text-yellow-400">
                          {metrics.services.twilio.delivery_stats_24h.pending}
                        </span>
                      </div>
                      <div className="flex justify-between items-center pt-1">
                        <span className="text-gray-500 dark:text-gray-400">Delivery Rate</span>
                        <span className={`font-semibold ${
                          metrics.services.twilio.delivery_stats_24h.delivery_rate >= 95
                            ? 'text-green-600 dark:text-green-400'
                            : metrics.services.twilio.delivery_stats_24h.delivery_rate >= 80
                            ? 'text-yellow-600 dark:text-yellow-400'
                            : 'text-red-600 dark:text-red-400'
                        }`}>
                          {metrics.services.twilio.delivery_stats_24h.delivery_rate}%
                        </span>
                      </div>
                    </>
                  )}
                  {metrics.services?.twilio?.error && (
                    <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                      <div className="flex items-start gap-1">
                        <AlertTriangle className="w-4 h-4 text-yellow-500 mt-0.5 flex-shrink-0" />
                        <span className="text-yellow-600 dark:text-yellow-400 text-xs">
                          {metrics.services?.twilio?.error}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </Card>

          {!metrics.health?.psutil_available && (
            <Card className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800">
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
                <p className="text-sm text-yellow-800 dark:text-yellow-300">
                  System resource metrics are unavailable. Install the optional <code className="font-mono bg-yellow-100 dark:bg-yellow-800 px-1 rounded">psutil</code> package on the API server to enable CPU, memory, and disk insights.
                </p>
              </div>
            </Card>
          )}

          {/* Quick Error Summary */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Error Summary (24h)</h3>
              <button
                onClick={() => setActiveTab('errors')}
                className="text-sm text-primary-600 dark:text-primary-400 hover:underline flex items-center gap-1"
              >
                View all errors <ChevronRight className="w-4 h-4" />
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="flex items-center gap-4 p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
                <div className="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-lg flex items-center justify-center">
                  <AlertTriangle className="w-6 h-6 text-red-600 dark:text-red-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Errors</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{metrics.errors?.total_24h || 0}</p>
                </div>
              </div>
              <div className="flex items-center gap-4 p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
                <div className="w-12 h-12 bg-orange-100 dark:bg-orange-900/30 rounded-lg flex items-center justify-center">
                  <XCircle className="w-6 h-6 text-orange-600 dark:text-orange-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Critical</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{metrics.errors?.critical_24h || 0}</p>
                </div>
              </div>
              <div className="flex items-center gap-4 p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
                <div className="w-12 h-12 bg-green-100 dark:bg-green-900/30 rounded-lg flex items-center justify-center">
                  <CheckCircle className="w-6 h-6 text-green-600 dark:text-green-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Status</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                    {(metrics.errors?.total_24h || 0) === 0 ? 'Healthy' : 'Issues'}
                  </p>
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'errors' && (
        <div className="space-y-6">
          {/* Error Filters */}
          <Card className="p-4">
            <div className="flex flex-wrap items-center gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Severity</label>
                <select
                  value={severityFilter}
                  onChange={(e) => setSeverityFilter(e.target.value as SeverityFilter)}
                  className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-800 text-gray-900 dark:text-gray-100 text-sm"
                >
                  <option value="all">All Severities</option>
                  <option value="critical">Critical Only</option>
                  <option value="warning">Warning Only</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Status</label>
                <select
                  value={acknowledgedFilter}
                  onChange={(e) => setAcknowledgedFilter(e.target.value as AcknowledgedFilter)}
                  className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-800 text-gray-900 dark:text-gray-100 text-sm"
                >
                  <option value="all">All Status</option>
                  <option value="false">Unacknowledged</option>
                  <option value="true">Acknowledged</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Limit</label>
                <select
                  value={errorLimit}
                  onChange={(e) => setErrorLimit(Number(e.target.value))}
                  className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-800 text-gray-900 dark:text-gray-100 text-sm"
                >
                  <option value={25}>25 per page</option>
                  <option value={50}>50 per page</option>
                  <option value={100}>100 per page</option>
                  <option value={200}>200 per page</option>
                </select>
              </div>
              <div className="ml-auto">
                {allErrors.some(e => !e.acknowledged) && (
                  <button
                    onClick={handleAcknowledgeAll}
                    disabled={acknowledgingAll}
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
                  >
                    {acknowledgingAll && <Loader2 className="w-4 h-4 animate-spin" />}
                    {acknowledgingAll ? 'Acknowledging...' : 'Acknowledge All'}
                  </button>
                )}
              </div>
            </div>
          </Card>

          {/* Error Statistics */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="p-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                {severityFilter !== 'all' || acknowledgedFilter !== 'all' ? 'Total Matching' : 'Total Errors (30d)'}
              </p>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{totalErrors}</p>
              {totalPages > 1 && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Showing {allErrors.length} of {totalErrors}
                </p>
              )}
            </Card>
            <Card className="p-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Critical (this page)</p>
              <p className="text-2xl font-bold text-red-600 dark:text-red-400 mt-1">
                {allErrors.filter(e => e.severity === 'critical').length}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Warnings (this page)</p>
              <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400 mt-1">
                {allErrors.filter(e => e.severity === 'warning').length}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Unacknowledged (this page)</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">
                {allErrors.filter(e => !e.acknowledged).length}
              </p>
            </Card>
          </div>

          {/* Errors Table */}
          {loadingErrors ? (
            <Card className="p-8 text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500 mx-auto mb-4"></div>
              <p className="text-gray-600 dark:text-gray-400">Loading errors...</p>
            </Card>
          ) : allErrors.length === 0 ? (
            <Card className="p-12 text-center">
              <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">No Errors Found</h3>
              <p className="text-gray-600 dark:text-gray-400">
                {severityFilter !== 'all' || acknowledgedFilter !== 'all'
                  ? 'Try adjusting your filters'
                  : 'Your application is running smoothly!'}
              </p>
            </Card>
          ) : (
            <Card className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead className="bg-gray-50 dark:bg-slate-800">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Severity</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Error Type</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Message</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Endpoint</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Timestamp</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-slate-900 divide-y divide-gray-200 dark:divide-gray-700">
                    {allErrors.map((err) => (
                      <tr key={err.error_id} className="hover:bg-gray-50 dark:hover:bg-slate-800">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                            err.severity === 'critical'
                              ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                              : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
                          }`}>
                            {err.severity}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{err.error_type}</p>
                        </td>
                        <td className="px-6 py-4">
                          <p
                            className="text-sm text-gray-700 dark:text-gray-300 max-w-md truncate cursor-help hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
                            title={err.message}
                          >
                            {err.message}
                          </p>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <p
                            className="text-sm text-gray-500 dark:text-gray-400 font-mono max-w-xs truncate cursor-help"
                            title={err.endpoint || 'N/A'}
                          >
                            {err.endpoint || 'N/A'}
                          </p>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <p className="text-sm text-gray-500 dark:text-gray-400">
                            {formatDateTime(err.timestamp, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                          </p>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {err.acknowledged ? (
                            <span className="px-2 py-1 bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400 rounded text-xs font-medium">
                              Acknowledged
                            </span>
                          ) : (
                            <span className="px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded text-xs font-medium">
                              New
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right">
                          {!err.acknowledged && (
                            <button
                              onClick={() => handleAcknowledgeError(err.error_id)}
                              disabled={acknowledgingIds.has(err.error_id)}
                              className="inline-flex items-center gap-1 text-green-600 hover:text-green-800 dark:text-green-400 dark:hover:text-green-300 disabled:opacity-50 text-sm font-medium mr-4"
                            >
                              {acknowledgingIds.has(err.error_id) && <Loader2 className="w-3 h-3 animate-spin" />}
                              {acknowledgingIds.has(err.error_id) ? 'Saving...' : 'Acknowledge'}
                            </button>
                          )}
                          <button
                            onClick={() => router.push(`/admin/platform/errors/${err.error_id}`)}
                            className="text-primary-600 hover:text-primary-800 dark:text-primary-400 text-sm font-medium"
                          >
                            Details
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* Pagination Controls */}
          {(hasNextPage || hasPrevPage || cursorHistory.length > 0) && (
            <Card className="p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  Showing {allErrors.length} of {totalErrors} total errors
                  {cursorHistory.length > 0 && (
                    <span className="ml-2 text-gray-400">
                      (Page {cursorHistory.length + 1})
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleFirstPage}
                    disabled={cursorHistory.length === 0 || loadingErrors}
                    className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    First
                  </button>
                  <button
                    onClick={handlePrevPage}
                    disabled={(cursorHistory.length === 0 && !hasPrevPage) || loadingErrors}
                    className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  <span className="px-3 py-1 text-sm font-medium bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 rounded">
                    {cursorHistory.length + 1}
                  </span>
                  <button
                    onClick={handleNextPage}
                    disabled={!hasNextPage || loadingErrors}
                    className="px-3 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
              </div>
            </Card>
          )}
        </div>
      )}

      {activeTab === 'performance' && (
        <div className="space-y-6">
          {/* Performance Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="p-4">
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Total Requests (24h)</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {(metrics.performance?.summary?.total_requests_24h ?? 0).toLocaleString()}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Avg Response Time</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {(metrics.performance?.summary?.overall_avg_response_time_ms ?? 0).toFixed(0)}ms
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Error Rate</p>
              <p className={`text-2xl font-bold ${(metrics.performance?.summary?.overall_error_rate ?? 0) > 5 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                {(metrics.performance?.summary?.overall_error_rate ?? 0).toFixed(2)}%
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Slow Endpoints</p>
              <p className={`text-2xl font-bold ${(metrics.performance?.summary?.slow_endpoint_count ?? 0) > 0 ? 'text-orange-600 dark:text-orange-400' : 'text-green-600 dark:text-green-400'}`}>
                {metrics.performance?.summary?.slow_endpoint_count ?? 0}
              </p>
            </Card>
          </div>

          {/* All Endpoints Performance Table */}
          {(metrics.performance?.endpoints?.length ?? 0) > 0 ? (
            <Card className="overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-slate-800">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                  Endpoint Performance (Top {metrics.performance?.endpoints?.length ?? 0} by response time)
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead className="bg-gray-50 dark:bg-slate-800">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Endpoint</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Avg</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">P95</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">P99</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Max</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Requests</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Error Rate</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-slate-900 divide-y divide-gray-200 dark:divide-gray-700">
                    {(metrics.performance?.endpoints ?? []).map((endpoint, idx) => {
                      const statusColors: Record<string, string> = {
                        healthy: 'bg-green-500',
                        moderate: 'bg-yellow-500',
                        warning: 'bg-orange-500',
                        critical: 'bg-red-500'
                      };
                      const statusColor = statusColors[endpoint.status] || 'bg-gray-500';
                      return (
                        <tr key={endpoint.endpoint ?? idx} className={endpoint.status === 'critical' ? 'bg-red-50 dark:bg-red-950/20' : ''}>
                          <td className="px-4 py-3">
                            <span className={`inline-block w-3 h-3 rounded-full ${statusColor}`} title={endpoint.status} />
                          </td>
                          <td className="px-4 py-3 text-sm font-mono text-gray-900 dark:text-gray-100 max-w-xs truncate" title={endpoint.endpoint}>
                            {endpoint.endpoint}
                          </td>
                          <td className="px-4 py-3 text-sm">
                            <span className={endpoint.status === 'critical' ? 'font-semibold text-red-600 dark:text-red-400' : endpoint.status === 'warning' ? 'font-semibold text-orange-600 dark:text-orange-400' : 'text-gray-700 dark:text-gray-300'}>
                              {endpoint.avg_response_time_ms.toFixed(0)}ms
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{endpoint.p95_ms.toFixed(0)}ms</td>
                          <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{endpoint.p99_ms.toFixed(0)}ms</td>
                          <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{endpoint.max_response_time_ms.toFixed(0)}ms</td>
                          <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{endpoint.request_count.toLocaleString()}</td>
                          <td className="px-4 py-3 text-sm">
                            <span className={endpoint.error_rate > 5 ? 'text-red-600 dark:text-red-400 font-semibold' : endpoint.error_rate > 1 ? 'text-orange-600 dark:text-orange-400' : 'text-gray-600 dark:text-gray-400'}>
                              {endpoint.error_rate.toFixed(1)}%
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          ) : (
            <Card className="p-12 text-center">
              <Zap className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">No Performance Data Available</h3>
              <p className="text-gray-600 dark:text-gray-400">Performance metrics will appear once requests are logged to the audit system.</p>
            </Card>
          )}
        </div>
      )}

      {activeTab === 'backups' && (
        <div className="space-y-6">
          {metrics.backups ? (
            <Card className="p-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-6">Backup Status</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">Last Backup</p>
                  {metrics.backups.last_backup_date ? (
                    <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                      {formatDateTime(metrics.backups.last_backup_date, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                    </p>
                  ) : (
                    <p className="text-lg text-gray-500 dark:text-gray-400">No backups yet</p>
                  )}
                </div>
                <div className="p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">Backup Size</p>
                  <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                    {metrics.backups.last_backup_size_mb ? `${metrics.backups.last_backup_size_mb.toFixed(1)} MB` : 'N/A'}
                  </p>
                </div>
                <div className="p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">Backups (30 days)</p>
                  <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                    {metrics.backups.backup_count_30d || 0}
                  </p>
                </div>
              </div>
            </Card>
          ) : (
            <Card className="p-12 text-center">
              <Shield className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">Backup Status Unavailable</h3>
              <p className="text-gray-600 dark:text-gray-400">Backup monitoring is not configured for this environment.</p>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}