'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAdmin } from '@/contexts/AdminContext';
import {
  getSponsoredVendors,
  getAdStats,
  getDashboardStats,
  getAdLeads,
  getAdPlacementLabel,
  type SponsoredVendor,
  type AdStats,
  type DashboardStats,
  type DashboardDailySeries,
  type AdLead,
} from '@/services/advertisingApi';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  Activity,
  Plus,
  TrendingUp,
  TrendingDown,
  Minus,
} from 'lucide-react';
import { toast } from 'sonner';

// ── Interfaces ──────────────────────────────────────────────────
interface WeeklyData {
  label: string;
  impressions: number;
  clicks: number;
}

interface FunnelStep {
  label: string;
  value: number;
  rate: string;
  color: string;
  width: string;
}

// ── Helpers ─────────────────────────────────────────────────────

/** Group daily series into weeks */
function aggregateWeekly(daily: DashboardDailySeries[]): WeeklyData[] {
  if (daily.length === 0) return [];
  const sorted = [...daily].sort((a, b) => a.date.localeCompare(b.date));
  const weeks: WeeklyData[] = [];
  let weekIdx = 1;
  for (let i = 0; i < sorted.length; i += 7) {
    const chunk = sorted.slice(i, i + 7);
    weeks.push({
      label: `Week ${weekIdx}`,
      impressions: chunk.reduce((s, d) => s + d.impressions, 0),
      clicks: chunk.reduce((s, d) => s + d.clicks, 0),
    });
    weekIdx++;
  }
  return weeks;
}

/** Build funnel data from stats */
function buildFunnel(totals: DashboardStats['totals'], vendorAddedCount: number): FunnelStep[] {
  const impressions = totals.impressions;
  const clicks = totals.clicks;
  const leads = totals.leads;
  const added = vendorAddedCount;
  const conversions = totals.conversions;

  const ctr = impressions > 0 ? ((clicks / impressions) * 100).toFixed(1) : '0';
  const clickToLead = clicks > 0 ? ((leads / clicks) * 100).toFixed(1) : '0';
  const leadToAdded = leads > 0 ? ((added / leads) * 100).toFixed(1) : '0';
  const addedToConversion = added > 0 ? ((conversions / added) * 100).toFixed(1) : '0';

  return [
    { label: `${impressions.toLocaleString()} Impressions`, value: impressions, rate: '', color: '#457B9D', width: '100%' },
    { label: `${clicks.toLocaleString()} Clicks`, value: clicks, rate: `↓ ${ctr}% click rate`, color: 'rgba(69,123,157,0.7)', width: '75%' },
    { label: `${leads.toLocaleString()} Leads`, value: leads, rate: `↓ ${clickToLead}% to lead`, color: 'rgba(69,123,157,0.5)', width: '50%' },
    { label: `${added.toLocaleString()} Added to Wedding`, value: added, rate: `↓ ${leadToAdded}% conversion`, color: '#E9C46A', width: '30%' },
    { label: `${conversions.toLocaleString()} Bookings`, value: conversions, rate: `↓ ${addedToConversion}% booked`, color: '#1D3557', width: '20%' },
  ];
}

/** Compute % change text and color */
function computeChange(current: number, previous: number): { text: string; color: string; icon: 'up' | 'down' | 'stable' } {
  if (previous === 0) return { text: 'New', color: '#457B9D', icon: 'stable' };
  const pct = ((current - previous) / previous) * 100;
  if (Math.abs(pct) < 1) return { text: '→ Stable', color: '#f59e0b', icon: 'stable' };
  if (pct > 0) return { text: `↑ ${Math.round(pct)}%`, color: '#16a34a', icon: 'up' };
  return { text: `↓ ${Math.abs(Math.round(pct))}%`, color: '#ef4444', icon: 'down' };
}

// ── Main Component ──────────────────────────────────────────────

export default function VendorAdsDashboard() {
  const router = useRouter();
  const { token, userProfile } = useAdmin();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Data
  const [sponsoredVendors, setSponsoredVendors] = useState<SponsoredVendor[]>([]);
  const [vendorStats, setVendorStats] = useState<Record<string, AdStats | null>>({});
  const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(null);
  const [prevDashboardStats, setPrevDashboardStats] = useState<DashboardStats | null>(null);
  const [leads, setLeads] = useState<AdLead[]>([]);

  // Auth + data fetch
  useEffect(() => {
    if (!token) { router.push('/admin/login'); return; }
    if (!userProfile?.is_vendor) { router.push('/admin'); return; }

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Parallel fetches
        const [vendors, stats30, stats60, adLeads] = await Promise.all([
          getSponsoredVendors(token, { limit: 50 }),
          getDashboardStats(token, 30).catch(() => null),
          getDashboardStats(token, 60).catch(() => null),
          getAdLeads(token, { limit: 100 }).catch(() => []),
        ]);

        setSponsoredVendors(vendors);
        setDashboardStats(stats30);
        setPrevDashboardStats(stats60);
        setLeads(adLeads);

        // Fetch per-vendor stats
        const statsMap: Record<string, AdStats | null> = {};
        for (const vendor of vendors) {
          try {
            statsMap[vendor._id] = await getAdStats(token, vendor._id, 30);
          } catch { statsMap[vendor._id] = null; }
        }
        setVendorStats(statsMap);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load advertising data');
        toast.error('Failed to load your advertising data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [token, router, userProfile?.is_vendor]);

  // ── Derived data ────────────────────────────────────────────

  const totals = dashboardStats?.totals ?? { impressions: 0, clicks: 0, leads: 0, conversions: 0, unique_planners: 0, unique_weddings: 0, ctr: 0 };
  const prevTotals = prevDashboardStats?.totals ?? { impressions: 0, clicks: 0, leads: 0, conversions: 0, unique_planners: 0, unique_weddings: 0, ctr: 0 };

  // Cost per lead (mock for now since billing not yet live)
  const costPerLead = totals.leads > 0 ? 0 : 0; // Free tier — will compute from billing when enabled

  // Weekly chart data
  const weeklyData = useMemo(
    () => aggregateWeekly(dashboardStats?.daily_series ?? []),
    [dashboardStats?.daily_series]
  );

  // Vendor added count from daily series
  const vendorAddedCount = useMemo(
    () => (dashboardStats?.daily_series ?? []).reduce((s, d) => s + d.vendor_added_to_wedding, 0),
    [dashboardStats?.daily_series]
  );

  // Funnel
  const funnelSteps = useMemo(
    () => buildFunnel(totals, vendorAddedCount),
    [totals, vendorAddedCount]
  );

  // Change indicators
  const impressionChange = computeChange(totals.impressions, prevTotals.impressions);
  const clickChange = computeChange(totals.clicks, prevTotals.clicks);
  const ctrChange = computeChange(totals.ctr, prevTotals.ctr);
  const leadChange = computeChange(totals.leads, prevTotals.leads);

  const getStatusBadgeColor = (isActive: boolean) =>
    isActive
      ? 'bg-emerald-100 text-emerald-700'
      : 'bg-yellow-100 text-yellow-700';

  // ── Render ──────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Activity className="w-8 h-8 animate-spin mx-auto mb-3 text-wedding-sage" />
          <p className="text-sm text-gray-600">Loading your advertising dashboard...</p>
        </div>
      </div>
    );
  }

  if (error && sponsoredVendors.length === 0) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6">
        <h3 className="font-bold text-red-900">Error loading data</h3>
        <p className="text-sm text-red-700 mt-1">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h2 className="text-[22px] font-extrabold text-wedding-navy">Advertising Overview</h2>
        <p className="text-[13px] text-gray-500 mt-1">
          {userProfile?.business_name || 'Your Business'} · Last 30 days
        </p>
      </div>

      {/* ── Performance Metric Cards ── (5 cards matching mockup) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {/* Impressions */}
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <p className="text-2xl font-extrabold text-wedding-navy">{totals.impressions.toLocaleString()}</p>
          <p className="text-[11px] font-medium text-gray-500 mt-1">Impressions</p>
          <p className="text-[11px] font-bold mt-1" style={{ color: impressionChange.color }}>{impressionChange.text}</p>
        </div>
        {/* Clicks */}
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <p className="text-2xl font-extrabold text-wedding-navy">{totals.clicks.toLocaleString()}</p>
          <p className="text-[11px] font-medium text-gray-500 mt-1">Clicks</p>
          <p className="text-[11px] font-bold mt-1" style={{ color: clickChange.color }}>{clickChange.text}</p>
        </div>
        {/* Click Rate */}
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <p className="text-2xl font-extrabold text-wedding-navy">{totals.ctr.toFixed(2)}%</p>
          <p className="text-[11px] font-medium text-gray-500 mt-1">Click Rate</p>
          <p className="text-[11px] font-bold mt-1" style={{ color: ctrChange.color }}>{ctrChange.text}</p>
        </div>
        {/* Leads */}
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <p className="text-2xl font-extrabold text-wedding-navy">{totals.leads.toLocaleString()}</p>
          <p className="text-[11px] font-medium text-gray-500 mt-1">Leads</p>
          <p className="text-[11px] font-bold mt-1" style={{ color: leadChange.color }}>{leadChange.text}</p>
        </div>
        {/* Cost / Lead */}
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <p className="text-2xl font-extrabold text-wedding-navy">${costPerLead.toFixed(2)}</p>
          <p className="text-[11px] font-medium text-gray-500 mt-1">Cost / Lead</p>
          <p className="text-[11px] font-bold mt-1 text-wedding-sage">Free Tier</p>
        </div>
      </div>

      {/* ── Charts Row: Performance by Week + Conversion Funnel ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Performance by Week — 2/3 width */}
        <div className="lg:col-span-2 bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-[15px] font-bold text-wedding-navy mb-4">Performance by Week</h3>
          {weeklyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={weeklyData} barCategoryGap="20%">
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#64748b' }} />
                <YAxis tick={{ fontSize: 11, fill: '#64748b' }} />
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
                  labelStyle={{ fontWeight: 700, color: '#1D3557' }}
                />
                <Bar dataKey="impressions" fill="#457B9D" radius={[4, 4, 0, 0]} name="Impressions" />
                <Bar dataKey="clicks" fill="#E9C46A" radius={[4, 4, 0, 0]} name="Clicks" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[240px] flex items-center justify-center bg-gray-50 rounded-lg text-gray-500 text-sm">
              No performance data yet. Data will appear here once your campaigns start running.
            </div>
          )}
          <p className="text-[10px] text-gray-500 mt-2">Impressions and clicks aggregated by week · Updated nightly</p>
        </div>

        {/* Conversion Funnel — 1/3 width */}
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-[15px] font-bold text-wedding-navy mb-4">Conversion Funnel</h3>
          <div className="flex flex-col items-center space-y-1">
            {funnelSteps.map((step, i) => (
              <React.Fragment key={step.label}>
                {i > 0 && (
                  <p className="text-[10px] text-gray-400">{step.rate}</p>
                )}
                <div
                  className="text-white text-[12px] font-bold py-2 px-3 rounded-md text-center"
                  style={{ backgroundColor: step.color, width: step.width, minWidth: '80px' }}
                >
                  {step.label}
                </div>
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>

      {/* ── Active Campaigns Table ── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[15px] font-bold text-wedding-navy">Active Campaigns</h3>
          <Link
            href="/admin/vendor/ads/campaigns/new"
            className="inline-flex items-center gap-1.5 rounded-lg bg-wedding-sage text-white px-3 py-2 text-[12px] font-semibold hover:bg-wedding-navy transition-colors min-h-[44px]"
          >
            <Plus className="w-4 h-4" />
            New Campaign
          </Link>
        </div>

        {sponsoredVendors.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
            <p className="font-semibold text-wedding-navy">No campaigns yet</p>
            <p className="text-sm text-gray-500 mt-1">Create your first campaign to start reaching planners</p>
            <Link
              href="/admin/vendor/ads/campaigns/new"
              className="inline-flex items-center gap-2 rounded-lg bg-wedding-sage text-white px-4 py-2 text-sm font-semibold hover:bg-wedding-navy transition-colors mt-4 min-h-[44px]"
            >
              <Plus className="w-4 h-4" />
              Create Campaign
            </Link>
          </div>
        ) : (
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50">
                    <th className="px-4 py-3 text-left text-[11px] font-bold text-wedding-navy uppercase tracking-wide">Campaign</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold text-wedding-navy uppercase tracking-wide">Status</th>
                    <th className="px-4 py-3 text-left text-[11px] font-bold text-wedding-navy uppercase tracking-wide">Placement</th>
                    <th className="px-4 py-3 text-right text-[11px] font-bold text-wedding-navy uppercase tracking-wide">Impressions</th>
                    <th className="px-4 py-3 text-right text-[11px] font-bold text-wedding-navy uppercase tracking-wide">Clicks</th>
                    <th className="px-4 py-3 text-right text-[11px] font-bold text-wedding-navy uppercase tracking-wide">Leads</th>
                    <th className="px-4 py-3 text-right text-[11px] font-bold text-wedding-navy uppercase tracking-wide">CTR</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {sponsoredVendors.map((vendor) => {
                    const stats = vendorStats[vendor._id];
                    const impressions = stats?.total_impressions ?? 0;
                    const clicks = stats?.total_clicks ?? 0;
                    const ctr = impressions > 0 ? ((clicks / impressions) * 100).toFixed(2) : '0.00';
                    // Count leads for this vendor
                    const vendorLeads = leads.filter(l => l.sponsored_vendor_id === vendor._id).length;

                    return (
                      <tr key={vendor._id} className="hover:bg-gray-50/50 transition-colors">
                        <td className="px-4 py-3">
                          <p className="font-semibold text-wedding-navy text-[13px]">
                            {vendor.headline || 'Untitled Campaign'}
                          </p>
                          <p className="text-[10px] text-gray-400">ID: {vendor._id.slice(0, 8)}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wide ${getStatusBadgeColor(vendor.is_active)}`}>
                            {vendor.is_active ? 'Active' : 'Paused'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-[12px] text-gray-600">
                          {getAdPlacementLabel(vendor.placement)}
                        </td>
                        <td className="px-4 py-3 text-right text-[13px] font-medium text-wedding-navy">
                          {impressions.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-right text-[13px] font-medium text-wedding-navy">
                          {clicks.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-right text-[13px] font-medium text-wedding-navy">
                          {vendorLeads}
                        </td>
                        <td className="px-4 py-3 text-right text-[13px] font-bold text-wedding-navy">
                          {ctr}%
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Annotation — how your data works */}
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-[11px] text-gray-600 space-y-1">
        <p><strong className="text-gray-700">How we track performance:</strong> Every planner interaction is recorded — from viewing your ad to requesting a quote.</p>
        <p><strong className="text-gray-700">Full-funnel attribution:</strong> Each planner journey is traced from impression through to booking, so you can see exactly where leads come from.</p>
        <p><strong className="text-gray-700">Data freshness:</strong> Stats are updated nightly. Today&apos;s activity will appear in tomorrow&apos;s report.</p>
      </div>
    </div>
  );
}
