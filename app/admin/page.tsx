'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import PageHeader from './components/PageHeader';

interface MetricsSnapshot {
  id?: string;
  timestamp?: string | null;
  snapshot_time?: string | null;
  ingested_at?: string | null;
  metrics: Record<string, unknown>;
}

interface AdminActivity {
  _id: string;
  id: string;
  action_type: string;
  title: string;
  message: string;
  admin_id: string;
  entity_type?: string;
  entity_id?: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

const HISTORY_OPTIONS = [
  { label: '24 hours', hours: 24 },
  { label: '3 days', hours: 72 },
  { label: '7 days', hours: 168 },
];

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const getValueFromPaths = (
  source: Record<string, unknown>,
  paths: Array<Array<string>>,
): unknown => {
  for (const path of paths) {
    let current: unknown = source;
    let found = true;
    for (const key of path) {
      if (isRecord(current) && key in current) {
        current = current[key];
      } else {
        found = false;
        break;
      }
    }
    if (found && current !== undefined) {
      return current;
    }
  }
  return undefined;
};

const formatTimestamp = (value?: string | null) => {
  if (!value) return 'Unknown';
  const parsed = new Date(value);
  return isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
};

export default function AdminMetricsDashboard() {
  const router = useRouter();
  const { token, userProfile, fetchUserProfile } = useAdmin();
  const [latestSnapshot, setLatestSnapshot] = useState<MetricsSnapshot | null>(null);
  const [history, setHistory] = useState<MetricsSnapshot[]>([]);
  const [historyHours, setHistoryHours] = useState<number>(HISTORY_OPTIONS[0].hours);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [recentActivities, setRecentActivities] = useState<AdminActivity[]>([]);
  const [activitiesLoading, setActivitiesLoading] = useState(false);

  const fetchLatestSnapshot = useCallback(async (authToken: string) => {
    setError('');
    setLoading(true);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/platform/metrics`, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      if (!response.ok) {
        const problem = await response.json().catch(() => ({}));
        throw new Error(problem.detail || 'Failed to load platform metrics');
      }

      const payload = await response.json();
      setLatestSnapshot(payload);
    } catch (err) {
      console.error('Error loading latest metrics snapshot', err);
      setError(err instanceof Error ? err.message : 'Failed to load platform metrics');
      setLatestSnapshot(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchHistorySnapshots = useCallback(async (authToken: string, hours: number) => {
    setError('');
    setHistoryLoading(true);
    try {
      const baseUrl = getApiBaseUrl();
      const startDate = new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
      const response = await fetch(
        `${baseUrl}/admin/platform/metrics/history?start_date=${encodeURIComponent(startDate)}`,
        {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        },
      );

      if (!response.ok) {
        const problem = await response.json().catch(() => ({}));
        throw new Error(problem.detail || 'Failed to load metrics history');
      }

      const payload = await response.json();
      const snapshots: MetricsSnapshot[] = Array.isArray(payload)
        ? payload.map((item) => ({
            ...item,
            metrics: isRecord(item?.metrics) ? (item.metrics as Record<string, unknown>) : {},
          }))
        : [];

      setHistory(snapshots);
    } catch (err) {
      console.error('Error loading metrics history', err);
      setError(err instanceof Error ? err.message : 'Failed to load metrics history');
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const fetchRecentActivities = useCallback(async (authToken: string) => {
    setActivitiesLoading(true);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/activity-log/recent?limit=10`, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      if (!response.ok) return;

      const payload = await response.json();
      setRecentActivities(payload.activities || []);
    } catch (err) {
      console.error('Error loading recent activities', err);
      setRecentActivities([]);
    } finally {
      setActivitiesLoading(false);
    }
  }, []);

  // Redirect wedding planners to their dashboard
  useEffect(() => {
    if (!token) {
      router.push('/admin/login');
      return;
    }

    if (!userProfile) {
      fetchUserProfile();
      return;
    }

    // Only ROOT_ADMIN can access Platform Health Overview
    if (userProfile && userProfile.is_wedding_planner) {
      router.push('/admin/planner');
      return;
    }
  }, [token, userProfile, fetchUserProfile, router]);

  useEffect(() => {
    // Only fetch metrics if user is ROOT_ADMIN (after profile is loaded)
    if (!token || !userProfile) return;
    if (!userProfile.is_root_admin) return;

    setError('');
    fetchLatestSnapshot(token);
  }, [token, userProfile, fetchLatestSnapshot]);

  useEffect(() => {
    // Only fetch history if user is ROOT_ADMIN (after profile is loaded)
    if (!token || !userProfile) return;
    if (!userProfile.is_root_admin) return;

    fetchHistorySnapshots(token, historyHours);
  }, [token, userProfile, historyHours, fetchHistorySnapshots]);

  useEffect(() => {
    // Only fetch activities if user is ROOT_ADMIN (after profile is loaded)
    if (!token || !userProfile) return;
    if (!userProfile.is_root_admin) return;

    fetchRecentActivities(token);
  }, [token, userProfile, fetchRecentActivities]);

  const metrics = useMemo(
    () => ((latestSnapshot?.metrics ?? {}) as Record<string, unknown>),
    [latestSnapshot],
  );

  const databaseStatus = useMemo(() => {
    const value = getValueFromPaths(metrics, [
      ['health', 'database', 'status'],
      ['health', 'database', 'state'],
      ['health', 'database'],
      ['database', 'status'],
      ['database_status'],
      ['health_database_status'],
    ]);
    return typeof value === 'string' ? value : value !== undefined ? String(value) : 'Unknown';
  }, [metrics]);

  const databaseLatency = useMemo(() => {
    const value = getValueFromPaths(metrics, [
      ['health', 'database', 'latency_ms'],
      ['health', 'database_latency_ms'],
      ['database', 'latency_ms'],
      ['database_latency_ms'],
      ['health_database_latency_ms'],
    ]);
    return typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : undefined;
  }, [metrics]);

  const cpuCores = useMemo(() => {
    const value = getValueFromPaths(metrics, [
      ['health', 'cpu', 'cores'],
      ['health', 'cpu_cores'],
      ['cpu', 'cores'],
      ['cpu_cores'],
    ]);
    return typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : undefined;
  }, [metrics]);

  const cpuLoad = useMemo(() => {
    const value = getValueFromPaths(metrics, [
      ['health', 'cpu', 'percent'],
      ['health', 'cpu', 'load_percent'],
      ['health', 'cpu', 'usage_percent'],
      ['health', 'cpu_load_percent'],
      ['cpu', 'percent'],
      ['cpu', 'usage_percent'],
      ['cpu_usage_percent'],
    ]);
    return typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : undefined;
  }, [metrics]);

  const generalMetrics = useMemo(() => {
    return Object.entries(metrics)
      .filter(([key]) => !['health'].includes(key))
      .map(([key, value]) => ({
        key,
        value,
        isObject: typeof value === 'object' && value !== null,
      }));
  }, [metrics]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Health Overview"
        description={latestSnapshot
          ? `Last updated ${formatTimestamp(latestSnapshot.snapshot_time || latestSnapshot.timestamp)}`
          : 'Metrics snapshots will appear once data is collected.'}
      >
        <div className="flex items-center gap-3">
          <label htmlFor="history-range" className="text-sm font-medium text-slate-500 dark:text-slate-400">
            History range
          </label>
          <select
            id="history-range"
            className="border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-700 dark:text-white"
            value={historyHours}
            onChange={(event) => setHistoryHours(Number(event.target.value))}
          >
            {HISTORY_OPTIONS.map((option) => (
              <option key={option.hours} value={option.hours}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </PageHeader>

      {error && (
        <p className="text-sm text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 rounded-lg px-4 py-3">
          {error}
        </p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        <MetricCard
          title="Database status"
          value={databaseStatus}
          loading={loading}
        />
        <MetricCard
          title="Database latency"
          value={
            databaseLatency !== undefined && !Number.isNaN(databaseLatency)
              ? `${databaseLatency.toFixed(1)} ms`
              : 'Unavailable'
          }
          loading={loading}
        />
        <MetricCard
          title="CPU cores"
          value={cpuCores !== undefined && !Number.isNaN(cpuCores) ? cpuCores : 'Unavailable'}
          loading={loading}
        />
        <MetricCard
          title="CPU usage"
          value={
            cpuLoad !== undefined && !Number.isNaN(cpuLoad)
              ? `${cpuLoad.toFixed(1)}%`
              : 'Unavailable'
          }
          loading={loading}
        />
      </div>

      {/* Recent Admin Activity Section */}
      <div className="bg-white dark:bg-slate-800 shadow-xl rounded-2xl border border-rose-100 dark:border-slate-700 overflow-hidden">
        <div className="px-6 py-4 border-b border-rose-100 dark:border-slate-700 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-wedding-navy dark:text-white">Recent Admin Activity</h2>
            <p className="text-sm text-wedding-muted dark:text-gray-400">
              Latest actions performed by administrators
            </p>
          </div>
          <a
            href="/admin/users"
            className="text-sm text-rose-500 hover:text-rose-600 dark:text-rose-400 dark:hover:text-rose-300"
          >
            View all →
          </a>
        </div>
        <div className="divide-y divide-rose-50 dark:divide-slate-700">
          {activitiesLoading ? (
            <div className="px-6 py-8 text-center text-wedding-muted dark:text-gray-400">
              Loading recent activities…
            </div>
          ) : recentActivities.length === 0 ? (
            <div className="px-6 py-8 text-center text-wedding-muted dark:text-gray-400">
              No recent admin activity to display.
            </div>
          ) : (
            recentActivities.map((activity) => (
              <ActivityItem key={activity._id || activity.id} activity={activity} />
            ))
          )}
        </div>
      </div>

      <div className="bg-white dark:bg-slate-800 shadow-xl rounded-2xl border border-rose-100 dark:border-slate-700 overflow-hidden">
        <div className="px-6 py-4 border-b border-rose-100 dark:border-slate-700">
          <h2 className="text-xl font-semibold text-wedding-navy dark:text-white">Snapshot history</h2>
          <p className="text-sm text-wedding-muted dark:text-gray-400">
            Showing {history.length} snapshots captured in the selected window.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-rose-100 dark:divide-slate-700">
            <thead className="bg-rose-50 dark:bg-slate-700">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-wedding-muted dark:text-gray-300 uppercase tracking-wider">
                  Captured at
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-wedding-muted dark:text-gray-300 uppercase tracking-wider">
                  Reported timestamp
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-wedding-muted dark:text-gray-300 uppercase tracking-wider">
                  Metrics summary
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-slate-800 divide-y divide-rose-50 dark:divide-slate-700">
              {historyLoading ? (
                <tr>
                  <td colSpan={3} className="px-4 py-6 text-center text-wedding-muted dark:text-gray-400">
                    Loading history…
                  </td>
                </tr>
              ) : history.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-4 py-6 text-center text-wedding-muted dark:text-gray-400">
                    No snapshot history available for this range yet.
                  </td>
                </tr>
              ) : (
                history.map((snapshot) => (
                  <tr key={snapshot.id || snapshot.snapshot_time || snapshot.timestamp}>
                    <td className="px-4 py-3 text-sm text-wedding-navy dark:text-white whitespace-nowrap">
                      {formatTimestamp(snapshot.snapshot_time)}
                    </td>
                    <td className="px-4 py-3 text-sm text-wedding-muted dark:text-gray-400 whitespace-nowrap">
                      {formatTimestamp(snapshot.timestamp)}
                    </td>
                    <td className="px-4 py-3 text-sm text-wedding-muted dark:text-gray-400">
                      {Object.keys(snapshot.metrics || {}).slice(0, 5).map((key) => (
                        <span key={key} className="inline-flex items-center bg-rose-50 dark:bg-slate-700 text-rose-600 dark:text-rose-400 text-xs font-medium mr-2 mb-2 px-3 py-1 rounded-full">
                          {key}
                        </span>
                      ))}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-800 shadow-xl rounded-2xl border border-rose-100 dark:border-slate-700 p-6">
        <h2 className="text-xl font-semibold text-wedding-navy dark:text-white mb-4">Raw metrics</h2>
        {loading ? (
          <p className="text-wedding-muted dark:text-gray-400">Loading latest metrics…</p>
        ) : !latestSnapshot ? (
          <p className="text-wedding-muted dark:text-gray-400">No metrics snapshot captured yet.</p>
        ) : generalMetrics.length === 0 ? (
          <p className="text-wedding-muted dark:text-gray-400">Metrics payload is empty.</p>
        ) : (
          <div className="space-y-4">
            {generalMetrics.map((metric) => (
              <CollapsibleMetric key={metric.key} metricKey={metric.key} value={metric.value} isObject={metric.isObject} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface MetricCardProps {
  title: string;
  value: string | number;
  loading: boolean;
}

function MetricCard({ title, value, loading }: MetricCardProps) {
  return (
    <div className="bg-white dark:bg-slate-800 border border-rose-100 dark:border-slate-700 rounded-2xl shadow-lg p-6 flex flex-col gap-3">
      <span className="text-sm font-semibold text-rose-500 dark:text-rose-400 uppercase tracking-wide">{title}</span>
      <span className="text-2xl font-bold text-wedding-navy dark:text-white">
        {loading ? 'Loading…' : value}
      </span>
    </div>
  );
}

interface ActivityItemProps {
  activity: AdminActivity;
}

interface CollapsibleMetricProps {
  metricKey: string;
  value: unknown;
  isObject: boolean;
}

function CollapsibleMetric({ metricKey, value, isObject }: CollapsibleMetricProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const renderValue = (val: unknown, depth = 0): React.ReactNode => {
    if (val === null) return <span className="text-slate-400">null</span>;
    if (val === undefined) return <span className="text-slate-400">undefined</span>;

    if (typeof val === 'string') {
      // Check if it's a timestamp
      if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(val)) {
        const date = new Date(val);
        if (!isNaN(date.getTime())) {
          return <span className="text-emerald-600 dark:text-emerald-400">{date.toLocaleString()}</span>;
        }
      }
      return <span className="text-emerald-600 dark:text-emerald-400">&quot;{val}&quot;</span>;
    }

    if (typeof val === 'number') {
      return <span className="text-blue-600 dark:text-blue-400">{val}</span>;
    }

    if (typeof val === 'boolean') {
      return <span className="text-amber-600 dark:text-amber-400">{val ? 'true' : 'false'}</span>;
    }

    if (Array.isArray(val)) {
      if (val.length === 0) return <span className="text-slate-500">[]</span>;
      return (
        <div className="ml-4">
          <span className="text-slate-500">[</span>
          {val.map((item, index) => (
            <div key={index} className="ml-4 border-l-2 border-slate-200 dark:border-slate-600 pl-3 my-1">
              <span className="text-slate-400 text-xs mr-2">{index}:</span>
              {renderValue(item, depth + 1)}
            </div>
          ))}
          <span className="text-slate-500">]</span>
        </div>
      );
    }

    if (typeof val === 'object') {
      const entries = Object.entries(val as Record<string, unknown>);
      if (entries.length === 0) return <span className="text-slate-500">{'{}'}</span>;

      return (
        <div className={depth > 0 ? 'ml-4' : ''}>
          {entries.map(([key, nestedValue]) => (
            <div key={key} className="border-l-2 border-slate-200 dark:border-slate-600 pl-3 my-2">
              <span className="text-purple-600 dark:text-purple-400 font-medium">{key}:</span>{' '}
              {renderValue(nestedValue, depth + 1)}
            </div>
          ))}
        </div>
      );
    }

    return <span>{String(val)}</span>;
  };

  // For simple non-object values, render inline
  if (!isObject) {
    return (
      <div className="bg-rose-50 dark:bg-slate-700 border border-rose-100 dark:border-slate-600 rounded-lg px-4 py-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-rose-500 dark:text-rose-400 uppercase tracking-wide">
            {metricKey}
          </span>
        </div>
        <div className="text-sm text-wedding-navy dark:text-white mt-2 font-mono">
          {renderValue(value)}
        </div>
      </div>
    );
  }

  // For objects, render with collapsible section
  const objectEntries = Object.entries(value as Record<string, unknown>);
  const previewKeys = objectEntries.slice(0, 3).map(([k]) => k).join(', ');
  const hasMore = objectEntries.length > 3;

  return (
    <div className="bg-rose-50 dark:bg-slate-700 border border-rose-100 dark:border-slate-600 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-rose-100 dark:hover:bg-slate-600 transition-colors"
      >
        <div className="flex items-center gap-3">
          <svg
            className={`w-4 h-4 text-slate-500 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <span className="text-xs font-semibold text-rose-500 dark:text-rose-400 uppercase tracking-wide">
            {metricKey}
          </span>
        </div>
        <span className="text-xs text-slate-500 dark:text-slate-400">
          {objectEntries.length} {objectEntries.length === 1 ? 'property' : 'properties'}
          {!isExpanded && (
            <span className="ml-2 text-slate-400">
              ({previewKeys}{hasMore ? '...' : ''})
            </span>
          )}
        </span>
      </button>
      {isExpanded && (
        <div className="px-4 py-3 border-t border-rose-100 dark:border-slate-600 bg-white dark:bg-slate-800">
          <div className="text-sm text-wedding-navy dark:text-white font-mono overflow-x-auto">
            {renderValue(value)}
          </div>
        </div>
      )}
    </div>
  );
}

function ActivityItem({ activity }: ActivityItemProps) {
  const getActivityIcon = (actionType: string) => {
    switch (actionType) {
      case 'invitation_sent':
        return (
          <div className="w-10 h-10 rounded-xl bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
            <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
            </svg>
          </div>
        );
      case 'invitation_resent':
        return (
          <div className="w-10 h-10 rounded-xl bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
            <svg className="w-5 h-5 text-amber-600 dark:text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </div>
        );
      case 'invitation_cancelled':
        return (
          <div className="w-10 h-10 rounded-xl bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
            <svg className="w-5 h-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
        );
      case 'invitation_completed':
        return (
          <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
            <svg className="w-5 h-5 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
        );
      case 'planner_suspended':
        return (
          <div className="w-10 h-10 rounded-xl bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center">
            <svg className="w-5 h-5 text-orange-600 dark:text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7a4 4 0 11-8 0 4 4 0 018 0zM9 14a6 6 0 00-6 6v1h12v-1a6 6 0 00-6-6zM21 12h-6" />
            </svg>
          </div>
        );
      case 'planner_activated':
        return (
          <div className="w-10 h-10 rounded-xl bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
            <svg className="w-5 h-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
        );
      case 'planner_deleted':
        return (
          <div className="w-10 h-10 rounded-xl bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
            <svg className="w-5 h-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </div>
        );
      default:
        return (
          <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-700 flex items-center justify-center">
            <svg className="w-5 h-5 text-slate-600 dark:text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
        );
    }
  };

  const formatActivityTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="px-6 py-4 flex items-start gap-4 hover:bg-rose-50/50 dark:hover:bg-slate-700/50 transition-colors">
      {getActivityIcon(activity.action_type)}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <p className="font-medium text-wedding-navy dark:text-white truncate">
            {activity.title}
          </p>
          <span className="text-xs text-wedding-muted dark:text-gray-400 whitespace-nowrap">
            {formatActivityTime(activity.created_at)}
          </span>
        </div>
        <p className="text-sm text-wedding-muted dark:text-gray-400 mt-0.5">
          {activity.message}
        </p>
        {activity.admin_id && (
          <p className="text-xs text-wedding-muted dark:text-gray-500 mt-1">
            by {activity.admin_id}
          </p>
        )}
      </div>
    </div>
  );
}
