'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import PageHeader from './components/PageHeader';
// import MetricCard from '@/admin/components/MetricCard';
import { GlassCard } from '@/admin/components/ui/glass/GlassCard';
import { GlassTable } from '@/admin/components/ui/glass/GlassTable';
// import { Database, Server, Activity, Clock } from 'lucide-react';
// import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface MetricsSnapshot {
  id?: string;
  timestamp?: string | null;
  snapshot_time?: string | null;
  ingested_at?: string | null;
  metrics: Record<string, unknown>;
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

  const metrics = useMemo(
    () => ((latestSnapshot?.metrics ?? {}) as Record<string, unknown>),
    [latestSnapshot],
  );

  /*
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
      ['health', 'cpu', 'load_percent'],
      ['health', 'cpu', 'usage_percent'],
      ['health', 'cpu_load_percent'],
      ['cpu', 'usage_percent'],
      ['cpu_usage_percent'],
    ]);
    return typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : undefined;
  }, [metrics]);
  */

  const generalMetrics = useMemo(() => {
    return Object.entries(metrics)
      .filter(([key]) => !['health'].includes(key))
      .map(([key, value]) => ({
        key,
        value: typeof value === 'object' ? JSON.stringify(value) : String(value),
      }));
  }, [metrics]);

  // Transform history for chart
  const latencyHistoryData = useMemo(() => {
    return history.map(snap => ({
      time: new Date(snap.snapshot_time || snap.timestamp || '').toLocaleTimeString(),
      latency: getValueFromPaths(snap.metrics as Record<string, unknown>, [
        ['health', 'database', 'latency_ms'],
        ['health', 'database_latency_ms'],
        ['database', 'latency_ms'],
        ['database_latency_ms'],
        ['health_database_latency_ms'],
      ]) as number || 0
    })).reverse();
  }, [history]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Platform Health"
        description={latestSnapshot
          ? `System status updated ${formatTimestamp(latestSnapshot.snapshot_time || latestSnapshot.timestamp)}`
          : 'Waiting for metrics...'}
      >
        <div className="flex items-center gap-3">
          <label htmlFor="history-range" className="text-sm font-medium text-slate-500 dark:text-slate-400">
            Range
          </label>
          <select
            id="history-range"
            className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 outline-none"
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
        <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl text-red-600 dark:text-red-300 dark:text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Primary Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        {/* MetricCard disabled due to missing dependencies
        <MetricCard
          title="Database Status"
          value={databaseStatus === 'online' || databaseStatus === 'connected' ? 'Healthy' : databaseStatus}
          icon={<Database size={20} />}
          color={databaseStatus === 'online' || databaseStatus === 'connected' ? '#10b981' : '#f43f5e'}
          loading={loading}
        />
        <MetricCard
          title="Latency"
          value={
            databaseLatency !== undefined && !Number.isNaN(databaseLatency)
              ? `${databaseLatency.toFixed(1)} ms`
              : 'N/A'
          }
          icon={<Activity size={20} />}
          color="#8b5cf6"
          loading={loading}
        />
        <MetricCard
          title="CPU Cores"
          value={cpuCores !== undefined && !Number.isNaN(cpuCores) ? cpuCores : 'N/A'}
          icon={<Server size={20} />}
          color="#3b82f6"
          loading={loading}
        />
        <MetricCard
          title="CPU Usage"
          value={
            cpuLoad !== undefined && !Number.isNaN(cpuLoad)
              ? `${cpuLoad.toFixed(1)}%`
              : 'N/A'
          }
          icon={<Activity size={20} />}
          color={cpuLoad && cpuLoad > 80 ? '#f43f5e' : '#10b981'}
          loading={loading}
        />
        */}
        <div className="p-4 bg-yellow-50 text-yellow-800 rounded">Metrics visualization temporarily disabled</div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <GlassCard className="p-6">
           <h3 className="text-lg font-semibold mb-4 text-slate-800 dark:text-white">Database Latency Trend</h3>
           <div className="h-64 w-full flex items-center justify-center bg-slate-50">
             {/*
             <ResponsiveContainer width="100%" height="100%">
               <AreaChart data={latencyHistoryData}>
                 <defs>
                   <linearGradient id="colorLatency" x1="0" y1="0" x2="0" y2="1">
                     <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.8}/>
                     <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                   </linearGradient>
                 </defs>
                 <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" opacity={0.5} />
                 <XAxis dataKey="time" hide />
                 <YAxis stroke="#94a3b8" fontSize={12} />
                 <Tooltip
                   contentStyle={{ backgroundColor: 'rgba(255, 255, 255, 0.8)', borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}
                 />
                 <Area type="monotone" dataKey="latency" stroke="#8b5cf6" fillOpacity={1} fill="url(#colorLatency)" />
               </AreaChart>
             </ResponsiveContainer>
             */}
             <p className="text-slate-400">Chart disabled</p>
           </div>
        </GlassCard>

        <GlassCard className="p-6">
           <h3 className="text-lg font-semibold mb-4 text-slate-800 dark:text-white">Raw Metrics</h3>
           <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 h-64 overflow-y-auto custom-scrollbar pr-2">
             {generalMetrics.map((metric) => (
               <div key={metric.key} className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-700">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{metric.key.replace(/_/g, ' ')}</p>
                  <p className="text-sm font-medium text-slate-800 dark:text-slate-200 mt-1 truncate" title={String(metric.value)}>
                    {metric.value}
                  </p>
               </div>
             ))}
             {generalMetrics.length === 0 && <p className="text-slate-500">No additional metrics available.</p>}
           </div>
        </GlassCard>
      </div>

      <GlassCard className="p-0 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800">
          <h2 className="text-lg font-semibold text-slate-800 dark:text-white">Snapshot History</h2>
        </div>
        <GlassTable
          data={history}
          keyField="id"
          isLoading={historyLoading}
          emptyMessage="No snapshot history available for this range."
          columns={[
             { header: 'Captured At', accessor: (row) => formatTimestamp(row.snapshot_time) },
             { header: 'Reported Time', accessor: (row) => formatTimestamp(row.timestamp) },
             { header: 'Summary', accessor: (row) => (
               <div className="flex flex-wrap gap-1">
                 {Object.keys(row.metrics || {}).slice(0, 3).map((key) => (
                   <span key={key} className="px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-xs text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
                     {key}
                   </span>
                 ))}
                 {Object.keys(row.metrics || {}).length > 3 && (
                   <span className="px-2 py-0.5 text-xs text-slate-500">+{Object.keys(row.metrics || {}).length - 3} more</span>
                 )}
               </div>
             )}
          ]}
        />
      </GlassCard>
    </div>
  );
}
