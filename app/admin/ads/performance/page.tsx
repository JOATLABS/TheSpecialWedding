'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import RootAdminGuard from '@/components/RootAdminGuard';
import { toast } from 'sonner';
import {
  getDashboardStats,
  getVendorLeaderboard,
  type DashboardStats,
  type VendorLeaderboardEntry,
} from '@/services/advertisingApi';
import {
  Eye,
  MousePointerClick,
  TrendingUp,
  Target,
  DollarSign,
  Activity,
  Loader2,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Main Page Component
// ---------------------------------------------------------------------------
export default function PerformancePage() {
  return (
    <RootAdminGuard>
      <PerformanceContent />
    </RootAdminGuard>
  );
}

function PerformanceContent() {
  const { token } = useAdmin();

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      {/* Page header */}
      <div className="sticky top-0 z-50 flex items-center px-6 border-b bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700" style={{ height: 56 }}>
        <h1 className="text-slate-900 dark:text-white font-bold text-lg">
          Performance Dashboard
        </h1>
      </div>

      <div className="p-6">
        <PerformanceDashboardTab token={token} />
      </div>
    </div>
  );
}

// ===========================================================================
// PERFORMANCE DASHBOARD TAB CONTENT
// ===========================================================================

function PerformanceDashboardTab({ token }: { token: string | null }) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [leaderboard, setLeaderboard] = useState<VendorLeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  const fetchData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const [dashStats, leaders] = await Promise.all([
        getDashboardStats(token, { days }),
        getVendorLeaderboard(token, { days, limit: 20 }),
      ]);
      setStats(dashStats);
      setLeaderboard(leaders);
    } catch (err: any) {
      toast.error(err.message || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  }, [token, days]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="animate-spin mr-2 text-wedding-sage" size={20} />
        <span className="text-sm text-slate-500 dark:text-slate-400">
          Loading performance data...
        </span>
      </div>
    );
  }

  const totals = stats?.totals || {
    impressions: 0,
    clicks: 0,
    ctr: 0,
    leads: 0,
    conversions: 0,
  };

  return (
    <div>
      {/* Period selector */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold text-slate-900 dark:text-white">
          Performance Overview
        </h3>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="px-2.5 py-1.5 border border-slate-200 dark:border-slate-600 rounded-md text-xs bg-white dark:bg-slate-700 text-slate-500 dark:text-slate-400"
          style={{ minHeight: 44 }}
        >
          <option value={7}>Last 7 Days</option>
          <option value={14}>Last 14 Days</option>
          <option value={30}>Last 30 Days</option>
          <option value={90}>Last 90 Days</option>
        </select>
      </div>

      {/* Top-level metrics */}
      <div className="grid grid-cols-5 gap-3 mb-6">
        <MetricCard
          label="Impressions"
          value={totals.impressions.toLocaleString()}
          icon={<Eye size={16} />}
        />
        <MetricCard
          label="Clicks"
          value={totals.clicks.toLocaleString()}
          icon={<MousePointerClick size={16} />}
        />
        <MetricCard
          label="CTR"
          value={`${totals.ctr}%`}
          icon={<TrendingUp size={16} />}
        />
        <MetricCard
          label="Leads"
          value={totals.leads.toLocaleString()}
          icon={<Target size={16} />}
        />
        <MetricCard
          label="Revenue"
          value="$0"
          subtitle="Billing not active"
          muted
          icon={<DollarSign size={16} />}
        />
      </div>

      {/* Daily series chart (simplified bar representation) */}
      {stats?.daily_series && stats.daily_series.length > 0 && (
        <div className="rounded-xl border bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 p-5 mb-6">
          <h4 className="text-sm font-bold mb-1 text-slate-900 dark:text-white">
            Daily Impressions Trend
          </h4>
          <p className="text-[11px] mb-4 text-slate-400 dark:text-slate-500">
            {days}-day period
          </p>
          <div className="flex items-end gap-1" style={{ height: 120 }}>
            {stats.daily_series.map((day: any, i: number) => {
              const maxImpressions = Math.max(
                ...stats.daily_series.map((d: any) => d.impressions || 0),
                1
              );
              const heightPct = ((day.impressions || 0) / maxImpressions) * 100;
              return (
                <div
                  key={i}
                  className="flex-1 rounded-t bg-wedding-sage hover:bg-wedding-navy"
                  style={{
                    height: `${Math.max(heightPct, 2)}%`,
                    minWidth: 2,
                    opacity: 0.8,
                  }}
                  title={`${day.date}: ${day.impressions} impressions, ${day.clicks} clicks`}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* Platform Health */}
      <div className="rounded-xl border bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 p-5 mb-6">
        <h4 className="text-sm font-bold mb-4 text-slate-900 dark:text-white">
          Platform Health
        </h4>
        <div className="grid grid-cols-3 gap-3">
          <HealthCard label="Active Campaigns" value={String(leaderboard.length)} status="good" />
          <HealthCard
            label="Total Impressions"
            value={totals.impressions.toLocaleString()}
            status={totals.impressions > 0 ? 'good' : 'na'}
          />
          <HealthCard
            label="Total Clicks"
            value={totals.clicks.toLocaleString()}
            status={totals.clicks > 0 ? 'good' : 'na'}
          />
          <HealthCard
            label="Total Leads"
            value={totals.leads.toLocaleString()}
            status={totals.leads > 0 ? 'good' : 'na'}
          />
          <HealthCard
            label="Avg CTR"
            value={`${totals.ctr}%`}
            status={totals.ctr > 1 ? 'good' : totals.ctr > 0 ? 'warn' : 'na'}
          />
          <HealthCard label="Revenue" value="$0" status="na" statusLabel="Billing not active" />
        </div>
      </div>

      {/* Vendor Leaderboard */}
      <div className="rounded-xl border bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 p-5">
        <h4 className="text-sm font-bold mb-4 text-slate-900 dark:text-white">
          Vendor Leaderboard
        </h4>
        {leaderboard.length === 0 ? (
          <p className="text-xs text-center py-8 text-slate-400 dark:text-slate-500">
            No vendor data for the selected period. Leaderboard populates from real ad events.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-wedding-navy dark:text-slate-300 border-b-2 border-slate-200 dark:border-slate-700">
                  <th className="py-2.5 px-3 font-bold text-[10px] uppercase tracking-wide bg-slate-50 dark:bg-slate-800">
                    Rank
                  </th>
                  <th className="py-2.5 px-3 font-bold text-[10px] uppercase tracking-wide bg-slate-50 dark:bg-slate-800">
                    Vendor
                  </th>
                  <th className="py-2.5 px-3 font-bold text-[10px] uppercase tracking-wide bg-slate-50 dark:bg-slate-800 text-right">
                    Impressions
                  </th>
                  <th className="py-2.5 px-3 font-bold text-[10px] uppercase tracking-wide bg-slate-50 dark:bg-slate-800 text-right">
                    Clicks
                  </th>
                  <th className="py-2.5 px-3 font-bold text-[10px] uppercase tracking-wide bg-slate-50 dark:bg-slate-800 text-right">
                    CTR
                  </th>
                  <th className="py-2.5 px-3 font-bold text-[10px] uppercase tracking-wide bg-slate-50 dark:bg-slate-800 text-right">
                    Leads
                  </th>
                </tr>
              </thead>
              <tbody>
                {leaderboard.map((entry, i) => (
                  <tr
                    key={entry.vendor_profile_id || i}
                    className="hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors border-b border-slate-100 dark:border-slate-700"
                  >
                    <td className="py-2.5 px-3 font-extrabold text-sm text-wedding-sage">
                      {i + 1}
                    </td>
                    <td className="py-2.5 px-3 font-medium text-wedding-navy dark:text-white">
                      {entry.vendor_profile_id}
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-600 dark:text-slate-400">
                      {(entry.total_impressions || 0).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-600 dark:text-slate-400">
                      {(entry.total_clicks || 0).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-600 dark:text-slate-400">
                      {(entry.ctr || 0).toFixed(2)}%
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-600 dark:text-slate-400">
                      {(entry.total_leads || 0).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ===========================================================================
// SUB-COMPONENTS
// ===========================================================================

function MetricCard({
  label,
  value,
  subtitle,
  muted,
  icon,
}: {
  label: string;
  value: string;
  subtitle?: string;
  muted?: boolean;
  icon?: React.ReactNode;
}) {
  return (
    <div
      className={`rounded-xl border p-4 ${
        muted
          ? 'bg-white dark:bg-slate-800 border-dashed border-slate-300 dark:border-slate-600'
          : 'bg-white dark:bg-slate-800 border-solid border-slate-200 dark:border-slate-700'
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        {icon && (
          <span className={muted ? 'text-slate-400 dark:text-slate-500' : 'text-wedding-sage'}>
            {icon}
          </span>
        )}
        <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
          {label}
        </span>
      </div>
      <div className={`text-2xl font-extrabold ${muted ? 'text-slate-400 dark:text-slate-500' : 'text-wedding-navy dark:text-white'}`}>
        {value}
      </div>
      {subtitle && (
        <p
          className={`text-[11px] mt-1 font-medium italic ${
            muted ? 'text-wedding-sage' : 'text-green-600 dark:text-green-400'
          }`}
        >
          {subtitle}
        </p>
      )}
    </div>
  );
}

function HealthCard({
  label,
  value,
  status,
  statusLabel,
}: {
  label: string;
  value: string;
  status: 'good' | 'warn' | 'na';
  statusLabel?: string;
}) {
  const statusColorClass =
    status === 'good'
      ? 'text-green-600 dark:text-green-400'
      : status === 'warn'
        ? 'text-amber-600 dark:text-amber-400'
        : 'text-slate-400 dark:text-slate-500';
  const statusText =
    statusLabel ||
    (status === 'good' ? 'Healthy' : status === 'warn' ? 'Warning' : 'N/A');

  return (
    <div className="rounded-xl border bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 p-3.5 text-center">
      <div className="text-xl font-extrabold text-wedding-navy dark:text-white">
        {value}
      </div>
      <div className="text-[10px] font-semibold uppercase tracking-wide mt-0.5 text-slate-400 dark:text-slate-500">
        {label}
      </div>
      <div
        className={`text-[10px] font-semibold mt-1 ${statusColorClass}`}
        style={{ fontStyle: status === 'na' ? 'italic' : 'normal' }}
      >
        {statusText}
      </div>
    </div>
  );
}
