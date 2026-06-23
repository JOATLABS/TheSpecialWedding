'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { Card } from '@/components/ui/Card';
import { formatAdminTimestamp, DEFAULT_TIMEZONE } from '@/utils/dateFormat';
import { toast } from 'sonner';
import PageHeader from '../components/PageHeader';
import { usePagination } from '@/admin/hooks/usePagination';
import { GlassPagination } from '@/admin/components/ui/glass/GlassPagination';
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
  MessageSquare,
  Calendar,
  PlayCircle
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
  window_days: number;
  total: number;
  critical: number;
  warning: number;
  other: number;
  unacknowledged: number;
  acknowledged: number;
  total_24h?: number | null;
  critical_24h?: number | null;
  recent_errors: ErrorSummary[];
}

interface ErrorScopeSummary {
  total: number;
  critical: number;
  warning: number;
  other: number;
  unacknowledged: number;
  acknowledged: number;
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
  auth_rejection_count?: number;
  error_rate: number;
  status: 'healthy' | 'moderate' | 'warning' | 'critical';
}

interface PerformanceMetrics {
  summary?: {
    total_requests_24h: number;
    total_errors_24h: number;
    auth_rejections_24h?: number;
    overall_error_rate: number;
    overall_avg_response_time_ms: number;
    overall_avg_response_time_seconds?: number;
    overall_p95_response_time_seconds?: number;
    slow_endpoint_count: number;
    monitored_endpoint_count: number;
    monthly_infra_cost_usd?: number | null;
    daily_infra_cost_usd?: number | null;
    requests_per_dollar_24h?: number | null;
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

interface SchedulerRunSummary {
  run_id: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  error: string | null;
  params?: Record<string, unknown> | null;
  result?: unknown;
}

interface SchedulerJobStaleInfo {
  is_stale: boolean;
  threshold_minutes: number | null;
  minutes_since_success: number | null;
  reason?: string;
}

interface SchedulerJobStats24h {
  total: number;
  success: number;
  failed: number;
  running: number;
}

interface SchedulerJobSummary {
  job_name: string;
  label: string;
  description: string;
  expected_interval_minutes: number;
  last_run: SchedulerRunSummary | null;
  last_success_at: string | null;
  stale: SchedulerJobStaleInfo;
  stats_24h: SchedulerJobStats24h;
}

interface SchedulerSummaryTotals {
  total_jobs: number;
  stale_jobs: number;
  failed_runs_24h: number;
}

interface SchedulerOverview {
  generated_at: string;
  jobs: SchedulerJobSummary[];
  summary: SchedulerSummaryTotals;
}

type TabType = 'health' | 'errors' | 'performance' | 'backups' | 'scheduler';
type SeverityFilter = 'all' | 'critical' | 'warning' | 'other';
type AcknowledgedFilter = 'all' | 'true' | 'false';

const ERROR_WINDOW_OPTIONS = [
  { value: 1, label: '24 hours' },
  { value: 7, label: '7 days' },
  { value: 30, label: '30 days' },
  { value: 90, label: '90 days' },
];

const formatErrorWindowLabel = (days: number) => {
  if (days <= 1) return '24h';
  return `${days}d`;
};

export default function PlatformInfrastructurePage() {
  const router = useRouter();
  const { userProfile, token, isLoading: authLoading } = useAdmin();
  const adminTimezone = userProfile?.user_data?.timezone || DEFAULT_TIMEZONE;
  const [metrics, setMetrics] = useState<PlatformMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('health');

  // Error filtering state
  const [allErrors, setAllErrors] = useState<ErrorSummary[]>([]);
  const [errorSummary, setErrorSummary] = useState<ErrorScopeSummary | null>(null);
  const [errorWindowDays, setErrorWindowDays] = useState(1);
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all');
  const [acknowledgedFilter, setAcknowledgedFilter] = useState<AcknowledgedFilter>('all');
  const [loadingErrors, setLoadingErrors] = useState(false);
  const [acknowledgingIds, setAcknowledgingIds] = useState<Set<string>>(new Set());
  const [acknowledgingAll, setAcknowledgingAll] = useState(false);

  // Scheduler state
  const [schedulerOverview, setSchedulerOverview] = useState<SchedulerOverview | null>(null);
  const [loadingScheduler, setLoadingScheduler] = useState(false);
  const [schedulerError, setSchedulerError] = useState<string | null>(null);
  const [expandedJob, setExpandedJob] = useState<string | null>(null);
  const [jobRuns, setJobRuns] = useState<Record<string, SchedulerRunSummary[]>>({});
  const [loadingJobRuns, setLoadingJobRuns] = useState<Record<string, boolean>>({});

  // Page-based pagination
  const errorPagination = usePagination({ initialItemsPerPage: 50 });
  const {
    currentPage: errorCurrentPage,
    itemsPerPage: errorItemsPerPage,
    setPage: setErrorPage,
    setTotalItems: setErrorTotalItems,
  } = errorPagination;

  // Access control - ROOT ADMIN only
  useEffect(() => {
    if (authLoading) {
      return;
    }

    if (userProfile && !userProfile.is_root_admin) {
      setLoading(false);
      router.replace('/admin/planner');
    }
  }, [authLoading, userProfile, router]);

  const fetchMetrics = useCallback(async () => {
    try {
      if (authLoading || !userProfile) {
        return;
      }

      if (!userProfile.is_root_admin) {
        setLoading(false);
        return;
      }

      const baseUrl = getApiBaseUrl();

      if (!token) {
        setError('Authentication required. Please log in.');
        setLoading(false);
        return;
      }

      const params = new URLSearchParams({
        days: errorWindowDays.toString(),
      });

      const response = await fetch(`${baseUrl}/admin/platform/health?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        credentials: 'include',
      });

      if (response.status === 403) {
        setLoading(false);
        router.replace('/admin/planner');
        return;
      }

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
  }, [authLoading, errorWindowDays, router, token, userProfile]);

  const fetchAllErrors = useCallback(async () => {
    try {
      setLoadingErrors(true);

      if (authLoading || !userProfile) {
        return;
      }

      const baseUrl = getApiBaseUrl();

      if (!userProfile.is_root_admin) {
        return;
      }

      if (!token) return;

      const params = new URLSearchParams({
        days: errorWindowDays.toString(),
        page: errorCurrentPage.toString(),
        limit: errorItemsPerPage.toString(),
        ...(severityFilter !== 'all' && { severity: severityFilter }),
        ...(acknowledgedFilter !== 'all' && { acknowledged: acknowledgedFilter })
      });

      const response = await fetch(`${baseUrl}/admin/platform/errors/recent?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        credentials: 'include',
      });

      if (response.status === 403) {
        router.replace('/admin/planner');
        return;
      }

      if (response.ok) {
        const data = await response.json();
        setAllErrors(data.errors || []);
        setErrorTotalItems(data.summary?.total ?? data.total ?? 0);
        setErrorSummary(data.summary || null);
      }
    } catch (err) {
      console.error('Error fetching errors:', err);
    } finally {
      setLoadingErrors(false);
    }
  }, [authLoading, errorCurrentPage, errorItemsPerPage, errorWindowDays, severityFilter, acknowledgedFilter, router, setErrorTotalItems, token, userProfile]);

  const fetchSchedulerJobs = useCallback(async () => {
    try {
      if (authLoading || !userProfile) {
        return;
      }

      if (!userProfile.is_root_admin) {
        return;
      }

      if (!token) {
        return;
      }

      setLoadingScheduler(true);

      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/platform/scheduler/jobs`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        credentials: 'include',
      });

      if (response.status === 403) {
        router.replace('/admin/planner');
        return;
      }

      if (!response.ok) {
        throw new Error(`Failed to fetch scheduler overview: ${response.statusText}`);
      }

      const data = (await response.json()) as SchedulerOverview;
      setSchedulerOverview(data);
      setSchedulerError(null);
    } catch (err) {
      console.error('Error fetching scheduler overview:', err);
      setSchedulerError(err instanceof Error ? err.message : 'Failed to load scheduler overview');
    } finally {
      setLoadingScheduler(false);
    }
  }, [authLoading, router, token, userProfile]);

  const fetchJobRuns = useCallback(async (jobName: string) => {
    try {
      if (!token) return;

      setLoadingJobRuns((prev) => ({ ...prev, [jobName]: true }));

      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/platform/scheduler/jobs/${jobName}/runs?limit=25`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch runs: ${response.statusText}`);
      }

      const data = await response.json();
      setJobRuns((prev) => ({ ...prev, [jobName]: (data.runs || []) as SchedulerRunSummary[] }));
    } catch (err) {
      console.error(`Error fetching runs for ${jobName}:`, err);
      toast.error(`Could not load runs for ${jobName}`);
    } finally {
      setLoadingJobRuns((prev) => ({ ...prev, [jobName]: false }));
    }
  }, [token]);

  useEffect(() => {
    if (authLoading) {
      return;
    }

    if (!userProfile || !userProfile.is_root_admin) {
      return;
    }

    fetchMetrics();

    if (autoRefresh) {
      const interval = setInterval(fetchMetrics, 30000);
      return () => clearInterval(interval);
    }
  }, [authLoading, fetchMetrics, autoRefresh, userProfile]);

  useEffect(() => {
    if (authLoading) {
      return;
    }

    if (!userProfile || !userProfile.is_root_admin) {
      return;
    }

    if (activeTab === 'errors') {
      fetchAllErrors();
    }
  }, [activeTab, authLoading, fetchAllErrors, userProfile]);

  useEffect(() => {
    if (authLoading) {
      return;
    }

    if (!userProfile || !userProfile.is_root_admin) {
      return;
    }

    if (activeTab !== 'scheduler') {
      return;
    }

    fetchSchedulerJobs();

    if (autoRefresh) {
      const interval = setInterval(fetchSchedulerJobs, 30000);
      return () => clearInterval(interval);
    }
  }, [activeTab, authLoading, autoRefresh, fetchSchedulerJobs, userProfile]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setErrorPage(1);
  }, [severityFilter, acknowledgedFilter, errorWindowDays, setErrorPage]);

  const handleAcknowledgeError = async (errorId: string) => {
    setAcknowledgingIds(prev => new Set(prev).add(errorId));
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

      // Use bulk acknowledge endpoint for better performance
      const response = await fetch(`${baseUrl}/admin/platform/errors/acknowledge-bulk`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        credentials: 'include',
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

  const handleToggleJobExpand = (jobName: string) => {
    setExpandedJob((prev) => {
      const next = prev === jobName ? null : jobName;
      if (next && !jobRuns[jobName]) {
        void fetchJobRuns(jobName);
      }
      return next;
    });
  };

  const formatIntervalMinutes = (minutes: number): string => {
    if (minutes >= 1440) {
      const days = minutes / 1440;
      return `${days % 1 === 0 ? days : days.toFixed(1)}d`;
    }
    if (minutes >= 60) {
      const hours = minutes / 60;
      return `${hours % 1 === 0 ? hours : hours.toFixed(1)}h`;
    }
    return `${minutes}m`;
  };

  const formatMinutesSince = (minutes: number | null): string => {
    if (minutes === null || minutes === undefined) return '—';
    if (minutes < 1) return '<1m ago';
    if (minutes < 60) return `${Math.round(minutes)}m ago`;
    if (minutes < 1440) return `${(minutes / 60).toFixed(1)}h ago`;
    return `${(minutes / 1440).toFixed(1)}d ago`;
  };

  const formatDuration = (ms: number | null): string => {
    if (ms === null || ms === undefined) return '—';
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  const getRunStatusChip = (status: string) => {
    switch (status) {
      case 'success':
        return 'text-green-700 bg-green-100 dark:bg-green-900/30 dark:text-green-300';
      case 'failed':
        return 'text-red-700 bg-red-100 dark:bg-red-900/30 dark:text-red-300';
      case 'running':
        return 'text-blue-700 bg-blue-100 dark:bg-blue-900/30 dark:text-blue-300';
      default:
        return 'text-gray-700 bg-gray-100 dark:bg-gray-700 dark:text-gray-300';
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

  if (authLoading || loading) {
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

  const selectedErrorWindowLabel = formatErrorWindowLabel(errorWindowDays);
  const healthErrorWindowLabel = formatErrorWindowLabel(metrics.errors?.window_days || errorWindowDays);
  const fullScopeErrorSummary: ErrorScopeSummary = errorSummary ?? {
    total: errorPagination.totalItems,
    critical: 0,
    warning: 0,
    other: 0,
    unacknowledged: 0,
    acknowledged: 0,
  };

  const tabs = [
    { id: 'health' as TabType, label: 'System Health', icon: Activity },
    { id: 'errors' as TabType, label: 'Errors', icon: AlertTriangle },
    { id: 'performance' as TabType, label: 'Performance', icon: Zap },
    { id: 'scheduler' as TabType, label: 'Scheduler', icon: Calendar },
    { id: 'backups' as TabType, label: 'Backups', icon: Shield },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Infrastructure"
        description="System health, errors, performance, and backups"
      >
        <label className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
          <span>Error window</span>
          <select
            value={errorWindowDays}
            onChange={(e) => setErrorWindowDays(Number(e.target.value))}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
          >
            {ERROR_WINDOW_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
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
          onClick={() => {
            fetchMetrics();
            if (activeTab === 'errors') fetchAllErrors();
            if (activeTab === 'scheduler') fetchSchedulerJobs();
          }}
          className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors text-sm font-medium"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </PageHeader>

      {/* Last Updated */}
      <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
        <Clock className="w-4 h-4" />
        Last updated: {formatAdminTimestamp(metrics.generated_at, adminTimezone)}
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
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  Error Summary ({healthErrorWindowLabel})
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  These totals use the same selected error window as the Errors tab.
                </p>
              </div>
              <button
                onClick={() => setActiveTab('errors')}
                className="text-sm text-primary-600 dark:text-primary-400 hover:underline flex items-center gap-1"
              >
                View all errors <ChevronRight className="w-4 h-4" />
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
              <div className="flex items-center gap-4 p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
                <div className="w-12 h-12 bg-red-100 dark:bg-red-900/30 rounded-lg flex items-center justify-center">
                  <AlertTriangle className="w-6 h-6 text-red-600 dark:text-red-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Errors</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{metrics.errors?.total || 0}</p>
                </div>
              </div>
              <div className="flex items-center gap-4 p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
                <div className="w-12 h-12 bg-orange-100 dark:bg-orange-900/30 rounded-lg flex items-center justify-center">
                  <XCircle className="w-6 h-6 text-orange-600 dark:text-orange-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Critical</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{metrics.errors?.critical || 0}</p>
                </div>
              </div>
              <div className="flex items-center gap-4 p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
                <div className="w-12 h-12 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg flex items-center justify-center">
                  <AlertTriangle className="w-6 h-6 text-yellow-600 dark:text-yellow-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Warnings</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{metrics.errors?.warning || 0}</p>
                </div>
              </div>
              <div className="flex items-center gap-4 p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
                <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
                  <Bell className="w-6 h-6 text-blue-600 dark:text-blue-300" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Other Severities</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{metrics.errors?.other || 0}</p>
                </div>
              </div>
              <div className="flex items-center gap-4 p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
                <div className="w-12 h-12 bg-slate-200 dark:bg-slate-700 rounded-lg flex items-center justify-center">
                  <CheckCircle className="w-6 h-6 text-slate-700 dark:text-slate-200" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Unacknowledged</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{metrics.errors?.unacknowledged || 0}</p>
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
                  <option value="other">Other Only</option>
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
                  value={errorPagination.itemsPerPage}
                  onChange={(e) => errorPagination.setItemsPerPage(Number(e.target.value))}
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
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <Card className="p-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
                {severityFilter !== 'all' || acknowledgedFilter !== 'all'
                  ? `Total Matching (${selectedErrorWindowLabel})`
                  : `Total Errors (${selectedErrorWindowLabel})`}
              </p>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{errorPagination.totalItems}</p>
              {errorPagination.totalPages > 1 && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Showing {allErrors.length} of {errorPagination.totalItems}
                </p>
              )}
            </Card>
            <Card className="p-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Critical</p>
              <p className="text-2xl font-bold text-red-600 dark:text-red-400 mt-1">
                {fullScopeErrorSummary.critical}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Warnings</p>
              <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400 mt-1">
                {fullScopeErrorSummary.warning}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Other Severities</p>
              <p className="text-2xl font-bold text-blue-600 dark:text-blue-400 mt-1">
                {fullScopeErrorSummary.other}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Unacknowledged</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">
                {fullScopeErrorSummary.unacknowledged}
              </p>
            </Card>
          </div>

          <p className="text-sm text-gray-500 dark:text-gray-400">
            The cards above summarize the full filtered result set for the selected error window. They should reconcile with the total count shown for this tab.
          </p>

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
            <div className="space-y-4">
              <GlassPagination
                currentPage={errorPagination.currentPage}
                totalPages={errorPagination.totalPages}
                totalItems={errorPagination.totalItems}
                itemsPerPage={errorPagination.itemsPerPage}
                onPageChange={errorPagination.setPage}
                variant="compact"
                itemLabel="errors"
              />
              <Card className="overflow-hidden">
                <div className="md:hidden divide-y divide-gray-200 dark:divide-gray-700">
                  {allErrors.map((err) => (
                    <div key={err.error_id} className="p-4 space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          err.severity === 'critical'
                            ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                            : err.severity === 'warning'
                              ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
                              : 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'
                        }`}>
                          {err.severity}
                        </span>
                        {err.acknowledged ? (
                          <span className="px-1.5 py-0.5 bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400 rounded text-xs font-medium">
                            Ack'd
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded text-xs font-medium">
                            New
                          </span>
                        )}
                      </div>

                      <div>
                        <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Error type</p>
                        <p className="text-sm font-medium text-gray-900 dark:text-gray-100 break-words">{err.error_type}</p>
                      </div>

                      <div>
                        <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Message</p>
                        <p className="text-sm text-gray-700 dark:text-gray-300 break-words">{err.message}</p>
                      </div>

                      <div className="grid grid-cols-1 gap-2">
                        <div>
                          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Endpoint</p>
                          <p className="text-sm text-gray-500 dark:text-gray-400 font-mono break-all">{err.endpoint || 'N/A'}</p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Timestamp</p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            {formatAdminTimestamp(err.timestamp, adminTimezone)}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center justify-end gap-3 pt-1">
                        {!err.acknowledged && (
                          <button
                            onClick={() => handleAcknowledgeError(err.error_id)}
                            disabled={acknowledgingIds.has(err.error_id)}
                            className="inline-flex items-center gap-1 text-green-600 hover:text-green-800 dark:text-green-400 dark:hover:text-green-300 disabled:opacity-50 text-xs font-medium"
                          >
                            {acknowledgingIds.has(err.error_id) && <Loader2 className="w-3 h-3 animate-spin" />}
                            {acknowledgingIds.has(err.error_id) ? '...' : 'Ack'}
                          </button>
                        )}
                        <button
                          onClick={() => router.push(`/admin/platform/errors/${err.error_id}`)}
                          className="text-primary-600 hover:text-primary-800 dark:text-primary-400 text-xs font-medium"
                        >
                          Details
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full min-w-[980px] table-fixed divide-y divide-gray-200 dark:divide-gray-700">
                    <thead className="bg-gray-50 dark:bg-slate-800">
                      <tr>
                        <th className="w-[72px] px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Severity</th>
                        <th className="w-[14%] px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Error Type</th>
                        <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Message</th>
                        <th className="w-[18%] px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Endpoint</th>
                        <th className="w-[140px] px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Timestamp</th>
                        <th className="w-[80px] px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                        <th className="w-[120px] px-3 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white dark:bg-slate-900 divide-y divide-gray-200 dark:divide-gray-700">
                      {allErrors.map((err) => (
                        <tr key={err.error_id} className="hover:bg-gray-50 dark:hover:bg-slate-800">
                          <td className="px-3 py-3">
                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                              err.severity === 'critical'
                                ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                                : err.severity === 'warning'
                                  ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
                                  : 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'
                            }`}>
                              {err.severity}
                            </span>
                          </td>
                          <td className="px-3 py-3">
                            <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate" title={err.error_type}>{err.error_type}</p>
                          </td>
                          <td className="px-3 py-3">
                            <p
                              className="text-sm text-gray-700 dark:text-gray-300 truncate cursor-help hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
                              title={err.message}
                            >
                              {err.message}
                            </p>
                          </td>
                          <td className="px-3 py-3">
                            <p
                              className="text-sm text-gray-500 dark:text-gray-400 font-mono truncate cursor-help"
                              title={err.endpoint || 'N/A'}
                            >
                              {err.endpoint || 'N/A'}
                            </p>
                          </td>
                          <td className="px-3 py-3">
                            <p className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                              {formatAdminTimestamp(err.timestamp, adminTimezone)}
                            </p>
                          </td>
                          <td className="px-3 py-3">
                            {err.acknowledged ? (
                              <span className="px-1.5 py-0.5 bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400 rounded text-xs font-medium">
                                Ack'd
                              </span>
                            ) : (
                              <span className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded text-xs font-medium">
                                New
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-3 text-right whitespace-nowrap">
                            {!err.acknowledged && (
                              <button
                                onClick={() => handleAcknowledgeError(err.error_id)}
                                disabled={acknowledgingIds.has(err.error_id)}
                                className="inline-flex items-center gap-1 text-green-600 hover:text-green-800 dark:text-green-400 dark:hover:text-green-300 disabled:opacity-50 text-xs font-medium mr-2"
                              >
                                {acknowledgingIds.has(err.error_id) && <Loader2 className="w-3 h-3 animate-spin" />}
                                {acknowledgingIds.has(err.error_id) ? '...' : 'Ack'}
                              </button>
                            )}
                            <button
                              onClick={() => router.push(`/admin/platform/errors/${err.error_id}`)}
                              className="text-primary-600 hover:text-primary-800 dark:text-primary-400 text-xs font-medium"
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
            </div>
          )}

          {/* Pagination Controls */}
          <GlassPagination
            currentPage={errorPagination.currentPage}
            totalPages={errorPagination.totalPages}
            totalItems={errorPagination.totalItems}
            itemsPerPage={errorPagination.itemsPerPage}
            isLoading={loadingErrors}
            onPageChange={errorPagination.setPage}
            onItemsPerPageChange={errorPagination.setItemsPerPage}
            pageSizeOptions={[25, 50, 100, 200]}
            itemLabel="errors"
          />
        </div>
      )}

      {activeTab === 'performance' && (
        <div className="space-y-6">
          {/* Performance Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-7 gap-4">
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
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">P95 Response</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {((metrics.performance?.summary?.overall_p95_response_time_seconds ?? 0) * 1000).toFixed(0)}ms
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Operational Error Rate</p>
              <p className={`text-2xl font-bold ${(metrics.performance?.summary?.overall_error_rate ?? 0) > 5 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                {(metrics.performance?.summary?.overall_error_rate ?? 0).toFixed(2)}%
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Auth/Billing Rejections</p>
              <p className={`text-2xl font-bold ${(metrics.performance?.summary?.auth_rejections_24h ?? 0) > 0 ? 'text-amber-600 dark:text-amber-400' : 'text-green-600 dark:text-green-400'}`}>
                {(metrics.performance?.summary?.auth_rejections_24h ?? 0).toLocaleString()}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Slow Endpoints</p>
              <p className={`text-2xl font-bold ${(metrics.performance?.summary?.slow_endpoint_count ?? 0) > 0 ? 'text-orange-600 dark:text-orange-400' : 'text-green-600 dark:text-green-400'}`}>
                {metrics.performance?.summary?.slow_endpoint_count ?? 0}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Requests / $</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                {metrics.performance?.summary?.requests_per_dollar_24h != null
                  ? metrics.performance.summary.requests_per_dollar_24h.toLocaleString(undefined, { maximumFractionDigits: 0 })
                  : 'Set cost'}
              </p>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">24h normalized by daily infra cost</p>
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
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Operational Errors</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Auth/Billing</th>
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
                          <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                            {(endpoint.auth_rejection_count ?? 0).toLocaleString()}
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

      {activeTab === 'scheduler' && (
        <div className="space-y-6">
          {loadingScheduler && !schedulerOverview ? (
            <Card className="p-12 text-center">
              <Loader2 className="w-12 h-12 text-primary-500 mx-auto mb-4 animate-spin" />
              <p className="text-gray-600 dark:text-gray-400">Loading scheduled job status…</p>
            </Card>
          ) : schedulerError ? (
            <Card className="p-6 border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20">
              <div className="flex items-center gap-3 mb-3">
                <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400" />
                <h3 className="text-base font-semibold text-red-800 dark:text-red-300">Could not load scheduler data</h3>
              </div>
              <p className="text-sm text-red-600 dark:text-red-300 mb-4">{schedulerError}</p>
              <button
                onClick={fetchSchedulerJobs}
                className="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition-colors text-sm"
              >
                Retry
              </button>
            </Card>
          ) : schedulerOverview ? (
            <>
              {/* Summary tiles */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <Calendar className="w-5 h-5 text-primary-500" />
                    <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Jobs</p>
                  </div>
                  <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">
                    {schedulerOverview.summary.total_jobs}
                  </p>
                </Card>
                <Card className="p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <AlertTriangle className={`w-5 h-5 ${schedulerOverview.summary.stale_jobs > 0 ? 'text-red-500' : 'text-gray-400'}`} />
                    <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Stale Jobs</p>
                  </div>
                  <p className={`text-3xl font-bold ${schedulerOverview.summary.stale_jobs > 0 ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-gray-100'}`}>
                    {schedulerOverview.summary.stale_jobs}
                  </p>
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">No successful run within expected window</p>
                </Card>
                <Card className="p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <XCircle className={`w-5 h-5 ${schedulerOverview.summary.failed_runs_24h > 0 ? 'text-red-500' : 'text-gray-400'}`} />
                    <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Failed Runs (24h)</p>
                  </div>
                  <p className={`text-3xl font-bold ${schedulerOverview.summary.failed_runs_24h > 0 ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-gray-100'}`}>
                    {schedulerOverview.summary.failed_runs_24h}
                  </p>
                </Card>
              </div>

              {/* Jobs table */}
              <Card className="p-0 overflow-hidden">
                <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Scheduled Jobs</h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                      Click a row to view recent runs. Stale jobs haven&apos;t completed a successful run inside the expected window.
                    </p>
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Last updated: {formatAdminTimestamp(schedulerOverview.generated_at, adminTimezone)}
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 dark:bg-slate-800/60">
                      <tr className="text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                        <th className="px-6 py-3">Job</th>
                        <th className="px-4 py-3">Interval</th>
                        <th className="px-4 py-3">Last Run</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3">Last Success</th>
                        <th className="px-4 py-3 text-right">24h (ok / fail)</th>
                        <th className="px-4 py-3"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                      {schedulerOverview.jobs.map((job) => {
                        const isExpanded = expandedJob === job.job_name;
                        const runs = jobRuns[job.job_name] || [];
                        const runsLoading = !!loadingJobRuns[job.job_name];
                        const lastRunStatus = job.last_run?.status ?? 'never';
                        const successCount24h = job.stats_24h?.success ?? 0;
                        const failedCount24h = job.stats_24h?.failed ?? 0;
                        return (
                          <React.Fragment key={job.job_name}>
                            <tr
                              onClick={() => handleToggleJobExpand(job.job_name)}
                              className={`cursor-pointer hover:bg-gray-50 dark:hover:bg-slate-800/60 transition-colors ${job.stale.is_stale ? 'bg-red-50/40 dark:bg-red-900/10' : ''}`}
                            >
                              <td className="px-6 py-4">
                                <div className="flex items-start gap-2">
                                  {job.stale.is_stale ? (
                                    <AlertTriangle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
                                  ) : (
                                    <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                                  )}
                                  <div>
                                    <p className="font-medium text-gray-900 dark:text-gray-100">{job.label}</p>
                                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{job.description}</p>
                                    <p className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-gray-500 mt-0.5 font-mono">{job.job_name}</p>
                                  </div>
                                </div>
                              </td>
                              <td className="px-4 py-4 text-gray-700 dark:text-gray-300">
                                every {formatIntervalMinutes(job.expected_interval_minutes)}
                              </td>
                              <td className="px-4 py-4 text-gray-700 dark:text-gray-300">
                                {job.last_run?.started_at
                                  ? formatAdminTimestamp(job.last_run.started_at, adminTimezone)
                                  : <span className="text-gray-400">never</span>}
                                {job.last_run?.duration_ms !== null && job.last_run?.duration_ms !== undefined && (
                                  <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
                                    ({formatDuration(job.last_run.duration_ms)})
                                  </span>
                                )}
                              </td>
                              <td className="px-4 py-4">
                                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${getRunStatusChip(lastRunStatus)}`}>
                                  {lastRunStatus}
                                </span>
                                {job.stale.is_stale && (
                                  <div className="mt-1 text-[11px] text-red-600 dark:text-red-400">
                                    stale · threshold {job.stale.threshold_minutes}m
                                  </div>
                                )}
                              </td>
                              <td className="px-4 py-4 text-gray-700 dark:text-gray-300">
                                {job.last_success_at
                                  ? formatMinutesSince(job.stale.minutes_since_success)
                                  : <span className="text-red-500">never</span>}
                              </td>
                              <td className="px-4 py-4 text-right font-mono text-xs text-gray-700 dark:text-gray-300">
                                <span className={successCount24h > 0 ? 'text-green-600 dark:text-green-400' : ''}>{successCount24h}</span>
                                <span className="mx-1 text-gray-400">/</span>
                                <span className={failedCount24h > 0 ? 'text-red-600 dark:text-red-400 font-semibold' : ''}>{failedCount24h}</span>
                              </td>
                              <td className="px-4 py-4 text-right">
                                <ChevronRight className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                              </td>
                            </tr>
                            {isExpanded && (
                              <tr>
                                <td colSpan={7} className="bg-gray-50 dark:bg-slate-800/40 px-6 py-4">
                                  <div className="flex items-center justify-between mb-3">
                                    <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-200 flex items-center gap-2">
                                      <PlayCircle className="w-4 h-4" />
                                      Recent runs
                                    </h4>
                                    <button
                                      onClick={(e) => { e.stopPropagation(); void fetchJobRuns(job.job_name); }}
                                      className="text-xs text-primary-600 dark:text-primary-400 hover:underline flex items-center gap-1"
                                    >
                                      <RefreshCw className={`w-3 h-3 ${runsLoading ? 'animate-spin' : ''}`} />
                                      Refresh
                                    </button>
                                  </div>
                                  {runsLoading && runs.length === 0 ? (
                                    <div className="text-sm text-gray-500 dark:text-gray-400 py-4">Loading runs…</div>
                                  ) : runs.length === 0 ? (
                                    <div className="text-sm text-gray-500 dark:text-gray-400 py-4">No runs recorded yet. Once the cron fires it&apos;ll show up here.</div>
                                  ) : (
                                    <div className="overflow-x-auto border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-slate-900">
                                      <table className="w-full text-xs">
                                        <thead>
                                          <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                                            <th className="px-3 py-2">Started</th>
                                            <th className="px-3 py-2">Duration</th>
                                            <th className="px-3 py-2">Status</th>
                                            <th className="px-3 py-2">Error / Result</th>
                                          </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                                          {runs.map((run) => (
                                            <tr key={run.run_id}>
                                              <td className="px-3 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap">
                                                {run.started_at ? formatAdminTimestamp(run.started_at, adminTimezone) : '—'}
                                              </td>
                                              <td className="px-3 py-2 text-gray-700 dark:text-gray-300 whitespace-nowrap">
                                                {formatDuration(run.duration_ms)}
                                              </td>
                                              <td className="px-3 py-2">
                                                <span className={`inline-flex items-center px-2 py-0.5 rounded-full font-semibold ${getRunStatusChip(run.status)}`}>
                                                  {run.status}
                                                </span>
                                              </td>
                                              <td className="px-3 py-2 text-gray-600 dark:text-gray-400 max-w-xl">
                                                {run.error ? (
                                                  <span className="text-red-600 dark:text-red-400 font-mono text-[11px] break-words">{run.error}</span>
                                                ) : run.result ? (
                                                  <code className="text-[11px] text-gray-500 dark:text-gray-400 break-words">
                                                    {typeof run.result === 'string' ? run.result : JSON.stringify(run.result)}
                                                  </code>
                                                ) : (
                                                  <span className="text-gray-400">—</span>
                                                )}
                                              </td>
                                            </tr>
                                          ))}
                                        </tbody>
                                      </table>
                                    </div>
                                  )}
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          ) : (
            <Card className="p-12 text-center">
              <Calendar className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">No Scheduler Data</h3>
              <p className="text-gray-600 dark:text-gray-400">Scheduled jobs haven&apos;t reported any runs yet.</p>
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
                      {formatAdminTimestamp(metrics.backups.last_backup_date, adminTimezone)}
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
