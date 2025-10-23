'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAdmin } from '@/contexts/AdminContext';

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
  const { token } = useAdmin();
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
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
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
      setLatestSnapshot({
        ...payload,
        metrics: isRecord(payload.metrics) ? payload.metrics : {},
      });
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
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
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

  useEffect(() => {
    if (!token) return;
    setError('');
    fetchLatestSnapshot(token);
  }, [token, fetchLatestSnapshot]);

  useEffect(() => {
    if (!token) return;
    fetchHistorySnapshots(token, historyHours);
  }, [token, historyHours, fetchHistorySnapshots]);

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
      ['health', 'cpu', 'load_percent'],
      ['health', 'cpu', 'usage_percent'],
      ['health', 'cpu_load_percent'],
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
        value: typeof value === 'object' ? JSON.stringify(value) : String(value),
      }));
  }, [metrics]);

  return (
    <div className="space-y-8">
      <div className="bg-white shadow-xl rounded-2xl p-8 border border-rose-100">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-wedding-navy">Platform Health Overview</h1>
            <p className="text-wedding-muted mt-1">
              {latestSnapshot
                ? `Last updated ${formatTimestamp(latestSnapshot.snapshot_time || latestSnapshot.timestamp)}`
                : 'Metrics snapshots will appear once data is collected.'}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label htmlFor="history-range" className="text-sm font-medium text-wedding-muted">
              History range
            </label>
            <select
              id="history-range"
              className="border border-rose-200 rounded-lg px-3 py-2 text-sm"
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
        </div>
        {error && (
          <p className="mt-4 text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-4 py-3">
            {error}
          </p>
        )}
      </div>

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

      <div className="bg-white shadow-xl rounded-2xl border border-rose-100 overflow-hidden">
        <div className="px-6 py-4 border-b border-rose-100">
          <h2 className="text-xl font-semibold text-wedding-navy">Snapshot history</h2>
          <p className="text-sm text-wedding-muted">
            Showing {history.length} snapshots captured in the selected window.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-rose-100">
            <thead className="bg-rose-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-wedding-muted uppercase tracking-wider">
                  Captured at
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-wedding-muted uppercase tracking-wider">
                  Reported timestamp
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-wedding-muted uppercase tracking-wider">
                  Metrics summary
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-rose-50">
              {historyLoading ? (
                <tr>
                  <td colSpan={3} className="px-4 py-6 text-center text-wedding-muted">
                    Loading history…
                  </td>
                </tr>
              ) : history.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-4 py-6 text-center text-wedding-muted">
                    No snapshot history available for this range yet.
                  </td>
                </tr>
              ) : (
                history.map((snapshot) => (
                  <tr key={snapshot.id || snapshot.snapshot_time || snapshot.timestamp}>
                    <td className="px-4 py-3 text-sm text-wedding-navy whitespace-nowrap">
                      {formatTimestamp(snapshot.snapshot_time)}
                    </td>
                    <td className="px-4 py-3 text-sm text-wedding-muted whitespace-nowrap">
                      {formatTimestamp(snapshot.timestamp)}
                    </td>
                    <td className="px-4 py-3 text-sm text-wedding-muted">
                      {Object.keys(snapshot.metrics || {}).slice(0, 5).map((key) => (
                        <span key={key} className="inline-flex items-center bg-rose-50 text-rose-600 text-xs font-medium mr-2 mb-2 px-3 py-1 rounded-full">
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

      <div className="bg-white shadow-xl rounded-2xl border border-rose-100 p-6">
        <h2 className="text-xl font-semibold text-wedding-navy mb-4">Raw metrics</h2>
        {loading ? (
          <p className="text-wedding-muted">Loading latest metrics…</p>
        ) : !latestSnapshot ? (
          <p className="text-wedding-muted">No metrics snapshot captured yet.</p>
        ) : generalMetrics.length === 0 ? (
          <p className="text-wedding-muted">Metrics payload is empty.</p>
        ) : (
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
            {generalMetrics.map((metric) => (
              <div key={metric.key} className="bg-rose-50 border border-rose-100 rounded-lg px-4 py-3">
                <dt className="text-xs font-semibold text-rose-500 uppercase tracking-wide">
                  {metric.key}
                </dt>
                <dd className="text-sm text-wedding-navy mt-1 break-all">
                  {metric.value}
                </dd>
              </div>
            ))}
          </dl>
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
    <div className="bg-white border border-rose-100 rounded-2xl shadow-lg p-6 flex flex-col gap-3">
      <span className="text-sm font-semibold text-rose-500 uppercase tracking-wide">{title}</span>
      <span className="text-2xl font-bold text-wedding-navy">
        {loading ? 'Loading…' : value}
      </span>
    </div>
  );
}
