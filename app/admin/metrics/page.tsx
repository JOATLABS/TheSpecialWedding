'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactElement } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { Card } from '@/components/ui/Card';
import { formatDateTime } from '@/utils/dateFormat';

interface RoleBreakdown {
  [role: string]: number;
}

interface PlatformMetricsResponse {
  generated_at: string;
  timeframe: string;
  users: {
    total: number;
    active: number;
    new_in_period: number;
    growth_rate: number;
    role_breakdown: RoleBreakdown;
  };
  subscriptions: {
    total: number;
    status_breakdown: {
      trial: number;
      active: number;
      cancelled: number;
      expired: number;
      [status: string]: number;
    };
    active_plans: number;
    monthly_recurring_revenue: number;
    yearly_recurring_revenue: number;
    projected_annual_revenue: number;
    plan_breakdown: {
      [planId: string]: {
        name: string;
        monthly_revenue: number;
        annual_revenue: number;
      };
    };
  };
  operations: {
    weddings: {
      total: number;
      active: number;
      upcoming: number;
      created_in_period: number;
      guest_total: number;
      rsvp_total: number;
    };
    forms: {
      total: number;
      new_in_period: number;
      responses_total: number;
      responses_in_period: number;
    };
    communications: {
      notifications_sent: number;
      notifications_in_period: number;
      email_logs_total: number;
      emails_sent_in_period: number;
      ai_events_total: number;
      ai_events_in_period: number;
    };
  };
}

type TimeframeKey = '7d' | '30d' | '90d' | '1y';

const TIMEFRAME_OPTIONS: Array<{ value: TimeframeKey; label: string }> = [
  { value: '7d', label: 'Last 7 Days' },
  { value: '30d', label: 'Last 30 Days' },
  { value: '90d', label: 'Last 90 Days' },
  { value: '1y', label: 'Last 12 Months' },
];

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatNumber(amount: number): string {
  return new Intl.NumberFormat('en-US').format(amount);
}

function formatPercentage(value: number): string {
  return `${value.toFixed(1)}%`;
}

export default function PlatformMetricsPage(): ReactElement {
  const { token } = useAdmin();
  const [metrics, setMetrics] = useState<PlatformMetricsResponse | null>(null);
  const [timeframe, setTimeframe] = useState<TimeframeKey>('30d');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchWithAuth = useCallback(
    async (path: string) => {
      if (!token) {
        throw new Error('Missing admin authentication token. Please log in again.');
      }

      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const url = `${baseUrl}${path}`;
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache',
        },
        cache: 'no-store',
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(`Request failed (${response.status}): ${detail || response.statusText}`);
      }

      return response.json() as Promise<PlatformMetricsResponse>;
    },
    [token],
  );

  const fetchMetrics = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await fetchWithAuth(`/admin/analytics/platform?timeframe=${timeframe}`);
      setMetrics(data);
    } catch (err) {
      console.error('Failed to load platform metrics', err);
      setError(err instanceof Error ? err.message : 'Failed to load platform metrics.');
      setMetrics(null);
    } finally {
      setLoading(false);
    }
  }, [fetchWithAuth, timeframe]);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  const roleBreakdown = useMemo(() => {
    if (!metrics) {
      return [] as Array<{ role: string; count: number }>;
    }

    return Object.entries(metrics.users.role_breakdown)
      .map(([role, count]) => ({ role, count }))
      .sort((a, b) => b.count - a.count);
  }, [metrics]);

  const statusBreakdown = useMemo(() => {
    if (!metrics) {
      return [] as Array<{ status: string; count: number }>;
    }

    return Object.entries(metrics.subscriptions.status_breakdown).map(([status, count]) => ({
      status,
      count,
    }));
  }, [metrics]);

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center">
        <div className="rounded-xl bg-white/70 px-6 py-4 text-lg text-wedding-navy shadow-sm backdrop-blur">
          Loading platform analytics…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="rounded-xl border border-red-200 bg-red-50 px-6 py-4 text-red-700">
          {error}
        </div>
        <button
          onClick={fetchMetrics}
          className="rounded-lg bg-wedding-rose px-4 py-2 font-semibold text-white shadow-md transition hover:bg-wedding-rose/80"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white/70 px-6 py-4 text-gray-600 shadow-sm backdrop-blur">
        Metrics data is currently unavailable.
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-heading text-wedding-rose">Platform Analytics</h1>
          <p className="text-gray-600">
            Updated {formatDateTime(metrics.generated_at, {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
              hour: 'numeric',
              minute: '2-digit',
            })} · Timeframe: {
              TIMEFRAME_OPTIONS.find((option) => option.value === metrics.timeframe)?.label || metrics.timeframe
            }
          </p>
        </div>
        <select
          value={timeframe}
          onChange={(event) => setTimeframe(event.target.value as TimeframeKey)}
          className="rounded-lg border border-white/40 bg-white/70 px-4 py-2 text-sm font-medium text-wedding-navy shadow-inner backdrop-blur focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
        >
          {TIMEFRAME_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-wedding-navy">User Growth</h2>
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
          <Card className="border border-white/40 bg-white/70 p-6 shadow-sm backdrop-blur">
            <p className="text-sm font-medium text-gray-500">Total Accounts</p>
            <p className="mt-2 text-3xl font-bold text-wedding-navy">{formatNumber(metrics.users.total)}</p>
            <p className="mt-1 text-xs text-gray-500">Active Roles: {roleBreakdown.length}</p>
          </Card>
          <Card className="border border-white/40 bg-white/70 p-6 shadow-sm backdrop-blur">
            <p className="text-sm font-medium text-gray-500">Active This Period</p>
            <p className="mt-2 text-3xl font-bold text-wedding-navy">{formatNumber(metrics.users.active)}</p>
            <p className="mt-1 text-xs text-green-600">Growth {formatPercentage(metrics.users.growth_rate)}</p>
          </Card>
          <Card className="border border-white/40 bg-white/70 p-6 shadow-sm backdrop-blur">
            <p className="text-sm font-medium text-gray-500">New Accounts</p>
            <p className="mt-2 text-3xl font-bold text-wedding-navy">{formatNumber(metrics.users.new_in_period)}</p>
            <p className="mt-1 text-xs text-gray-500">Within selected timeframe</p>
          </Card>
          <Card className="border border-white/40 bg-white/70 p-6 shadow-sm backdrop-blur">
            <p className="text-sm font-medium text-gray-500">Role Distribution</p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              {roleBreakdown.map(({ role, count }) => (
                <span key={role} className="rounded-full bg-white/80 px-3 py-1 text-wedding-navy shadow-sm">
                  {role.replace('_', ' ')} · {formatNumber(count)}
                </span>
              ))}
              {roleBreakdown.length === 0 && <span className="text-gray-500">No accounts recorded.</span>}
            </div>
          </Card>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-wedding-navy">Subscription &amp; Revenue</h2>
        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="border border-white/40 bg-white/70 p-6 shadow-sm backdrop-blur">
            <p className="text-sm font-medium text-gray-500">Active Subscriptions</p>
            <p className="mt-2 text-3xl font-bold text-wedding-navy">
              {formatNumber(metrics.subscriptions.status_breakdown.active)}
            </p>
            <ul className="mt-3 space-y-1 text-sm text-gray-600">
              {statusBreakdown.map(({ status, count }) => (
                <li key={status} className="flex justify-between">
                  <span className="capitalize">{status.replace('_', ' ')}</span>
                  <span>{formatNumber(count)}</span>
                </li>
              ))}
            </ul>
          </Card>
          <Card className="border border-white/40 bg-white/70 p-6 shadow-sm backdrop-blur">
            <p className="text-sm font-medium text-gray-500">Recurring Revenue</p>
            <p className="mt-2 text-3xl font-bold text-wedding-navy">
              {formatCurrency(metrics.subscriptions.monthly_recurring_revenue)}
            </p>
            <p className="mt-1 text-xs text-gray-500">
              Annual Projection {formatCurrency(metrics.subscriptions.projected_annual_revenue)}
            </p>
            <p className="mt-1 text-xs text-gray-500">
              Yearly Contracts {formatCurrency(metrics.subscriptions.yearly_recurring_revenue)}
            </p>
          </Card>
          <Card className="border border-white/40 bg-white/70 p-6 shadow-sm backdrop-blur">
            <p className="text-sm font-medium text-gray-500">Subscription Plans</p>
            <p className="mt-2 text-3xl font-bold text-wedding-navy">{metrics.subscriptions.active_plans}</p>
            <p className="mt-1 text-xs text-gray-500">Active plans available to assign</p>
          </Card>
        </div>

        <Card className="border border-white/40 bg-white/70 shadow-sm backdrop-blur overflow-hidden">
          <div className="border-b border-white/40 px-6 py-4">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Plan Breakdown</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-white/40 text-sm">
              <thead className="bg-white/60 text-left text-xs uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-6 py-3">Plan</th>
                  <th className="px-6 py-3">Active Users</th>
                  <th className="px-6 py-3">Trial Users</th>
                  <th className="px-6 py-3">MRR</th>
                  <th className="px-6 py-3">ARR</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/40 bg-white/30 text-gray-700">
                {Object.keys(metrics.subscriptions.plan_breakdown).length === 0 && (
                  <tr>
                    <td className="px-6 py-4" colSpan={5}>
                      No subscription plan activity recorded yet.
                    </td>
                  </tr>
                )}
                {Object.entries(metrics.subscriptions.plan_breakdown).map(([planId, plan]) => (
                  <tr key={planId}>
                    <td className="px-6 py-4 font-medium text-wedding-navy">
                      {plan.name || planId}
                    </td>
                    <td className="px-6 py-4">N/A</td>
                    <td className="px-6 py-4">N/A</td>
                    <td className="px-6 py-4">{formatCurrency(plan.monthly_revenue)}</td>
                    <td className="px-6 py-4">{formatCurrency(plan.annual_revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-wedding-navy">Operational Load</h2>
        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="border border-white/40 bg-white/70 p-6 shadow-sm backdrop-blur">
            <h3 className="text-lg font-semibold text-wedding-navy">Wedding Projects</h3>
            <div className="mt-4 grid grid-cols-2 gap-4 text-sm text-gray-600">
              <div>
                <p className="font-medium text-wedding-navy">Total Weddings</p>
                <p className="text-2xl font-semibold">{formatNumber(metrics.operations.weddings.total)}</p>
              </div>
              <div>
                <p className="font-medium text-wedding-navy">Active</p>
                <p className="text-2xl font-semibold">{formatNumber(metrics.operations.weddings.active)}</p>
              </div>
              <div>
                <p className="font-medium text-wedding-navy">Upcoming</p>
                <p className="text-2xl font-semibold">{formatNumber(metrics.operations.weddings.upcoming)}</p>
              </div>
              <div>
                <p className="font-medium text-wedding-navy">New This Period</p>
                <p className="text-2xl font-semibold">{formatNumber(metrics.operations.weddings.created_in_period)}</p>
              </div>
            </div>
            <div className="mt-4 rounded-lg bg-white/70 px-4 py-3 text-sm text-gray-600 shadow-inner">
              <p>Guests managed: {formatNumber(metrics.operations.weddings.guest_total)}</p>
              <p>RSVP records: {formatNumber(metrics.operations.weddings.rsvp_total)}</p>
            </div>
          </Card>

          <Card className="border border-white/40 bg-white/70 p-6 shadow-sm backdrop-blur">
            <h3 className="text-lg font-semibold text-wedding-navy">Form Engagement</h3>
            <div className="mt-4 grid grid-cols-2 gap-4 text-sm text-gray-600">
              <div>
                <p className="font-medium text-wedding-navy">Active Forms</p>
                <p className="text-2xl font-semibold">{formatNumber(metrics.operations.forms.total)}</p>
              </div>
              <div>
                <p className="font-medium text-wedding-navy">New Forms</p>
                <p className="text-2xl font-semibold">{formatNumber(metrics.operations.forms.new_in_period)}</p>
              </div>
              <div>
                <p className="font-medium text-wedding-navy">Responses</p>
                <p className="text-2xl font-semibold">{formatNumber(metrics.operations.forms.responses_total)}</p>
              </div>
              <div>
                <p className="font-medium text-wedding-navy">Responses This Period</p>
                <p className="text-2xl font-semibold">{formatNumber(metrics.operations.forms.responses_in_period)}</p>
              </div>
            </div>
          </Card>
        </div>

        <Card className="border border-white/40 bg-white/70 p-6 shadow-sm backdrop-blur">
          <h3 className="text-lg font-semibold text-wedding-navy">Communication Volume</h3>
          <div className="mt-4 grid gap-6 md:grid-cols-3 text-sm text-gray-600">
            <div>
              <p className="font-medium text-wedding-navy">Notifications Sent</p>
              <p className="text-2xl font-semibold">{formatNumber(metrics.operations.communications.notifications_sent)}</p>
              <p className="text-xs text-gray-500">
                +{formatNumber(metrics.operations.communications.notifications_in_period)} this timeframe
              </p>
            </div>
            <div>
              <p className="font-medium text-wedding-navy">Email Logs</p>
              <p className="text-2xl font-semibold">{formatNumber(metrics.operations.communications.email_logs_total)}</p>
              <p className="text-xs text-gray-500">
                {formatNumber(metrics.operations.communications.emails_sent_in_period)} successful deliveries
              </p>
            </div>
            <div>
              <p className="font-medium text-wedding-navy">AI Automations</p>
              <p className="text-2xl font-semibold">{formatNumber(metrics.operations.communications.ai_events_total)}</p>
              <p className="text-xs text-gray-500">
                {formatNumber(metrics.operations.communications.ai_events_in_period)} requests this timeframe
              </p>
            </div>
          </div>
        </Card>
      </section>
    </div>
  );
}
