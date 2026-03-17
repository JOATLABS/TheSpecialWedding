'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import RootAdminGuard from '@/components/RootAdminGuard';
import { toast } from 'sonner';
import {
  getReviewQueue,
  getReviewQueueCounts,
  reviewCampaign,
  getDashboardStats,
  getVendorLeaderboard,
  getFeatureFlag,
  toggleFeatureFlag,
  updateFeatureFlagConfig,
  triggerRollup,
  backfillRollups,
  getAdPlacementLabel,
  type ReviewQueueItem,
  type ReviewQueueCounts,
  type ReviewStatus,
  type DashboardStats,
  type VendorLeaderboardEntry,
  type FeatureFlagConfig,
} from '@/services/advertisingApi';
import {
  ShieldCheck,
  BarChart3,
  Settings,
  DollarSign,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Loader2,
  Eye,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  TrendingUp,
  Users,
  MousePointerClick,
  Target,
  ChevronDown,
  Database,
  Zap,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Color palette constants (no emojis, WCAG-compliant)
// ---------------------------------------------------------------------------
const NAVY = '#1D3557';
const SAGE = '#457B9D';
const ROSE = '#D4A5A5';
const GOLD = '#E9C46A';

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------
type TabKey = 'creative-review' | 'performance' | 'config' | 'revenue';

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: 'creative-review', label: 'Creative Review', icon: <ShieldCheck size={14} /> },
  { key: 'performance', label: 'Performance Dashboard', icon: <BarChart3 size={14} /> },
  { key: 'config', label: 'System Config', icon: <Settings size={14} /> },
  { key: 'revenue', label: 'Revenue & Billing', icon: <DollarSign size={14} /> },
];

// ---------------------------------------------------------------------------
// Main Page Component
// ---------------------------------------------------------------------------
export default function AdminConsole() {
  return (
    <RootAdminGuard>
      <AdminConsoleContent />
    </RootAdminGuard>
  );
}

function AdminConsoleContent() {
  const { token } = useAdmin();
  const [activeTab, setActiveTab] = useState<TabKey>('creative-review');
  const [queueCounts, setQueueCounts] = useState<ReviewQueueCounts>({
    pending_review: 0,
    approved: 0,
    rejected: 0,
    changes_requested: 0,
  });

  const fetchCounts = useCallback(async () => {
    if (!token) return;
    try {
      const counts = await getReviewQueueCounts(token);
      setQueueCounts(counts);
    } catch {
      // Silently fail for counts
    }
  }, [token]);

  useEffect(() => {
    fetchCounts();
  }, [fetchCounts]);

  return (
    <div className="min-h-screen" style={{ background: '#F8FAFC' }}>
      {/* Page header */}
      <div
        className="sticky top-0 z-50 flex items-center px-6 border-b"
        style={{
          height: 56,
          background: '#fff',
          borderColor: '#e2e8f0',
        }}
      >
        <h1 className="font-bold text-lg" style={{ color: NAVY }}>
          Ad Management Console
        </h1>
      </div>

      <div className="p-6">
        {/* Tab bar */}
        <div
          className="flex gap-0.5 mb-6 p-1 rounded-xl"
          style={{ background: '#f1f5f9' }}
        >
          {TABS.map((tab) => {
            const isActive = activeTab === tab.key;
            const pendingCount =
              tab.key === 'creative-review' ? queueCounts.pending_review : 0;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-xs font-semibold transition-all"
                style={{
                  background: isActive ? '#fff' : 'transparent',
                  color: isActive ? NAVY : '#64748b',
                  boxShadow: isActive ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                  minHeight: 44,
                }}
              >
                {tab.icon}
                {tab.label}
                {pendingCount > 0 && (
                  <span
                    className="text-white text-[9px] font-bold px-1.5 py-0.5 rounded-md"
                    style={{ background: '#ef4444' }}
                  >
                    {pendingCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Tab panels */}
        {activeTab === 'creative-review' && (
          <CreativeReviewTab
            token={token}
            queueCounts={queueCounts}
            onCountsChanged={fetchCounts}
          />
        )}
        {activeTab === 'performance' && <PerformanceDashboardTab token={token} />}
        {activeTab === 'config' && <SystemConfigTab token={token} />}
        {activeTab === 'revenue' && <RevenueBillingTab />}
      </div>
    </div>
  );
}


// ===========================================================================
// TAB 1: CREATIVE REVIEW
// ===========================================================================

function CreativeReviewTab({
  token,
  queueCounts,
  onCountsChanged,
}: {
  token: string | null;
  queueCounts: ReviewQueueCounts;
  onCountsChanged: () => void;
}) {
  const [queue, setQueue] = useState<ReviewQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [placementFilter, setPlacementFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<ReviewStatus | ''>('pending_review');
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [reviewNotes, setReviewNotes] = useState('');
  const [notesModalId, setNotesModalId] = useState<string | null>(null);

  const fetchQueue = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const items = await getReviewQueue(token, {
        status: (statusFilter || 'pending_review') as ReviewStatus,
        placement: placementFilter || undefined,
        limit: 50,
      });
      setQueue(items);
    } catch (err: any) {
      toast.error(err.message || 'Failed to load review queue');
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter, placementFilter]);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const handleReview = async (id: string, status: ReviewStatus, notes?: string) => {
    if (!token) return;
    setReviewingId(id);
    try {
      await reviewCampaign(token, id, {
        review_status: status,
        review_notes: notes || undefined,
      });
      toast.success(
        status === 'approved'
          ? 'Campaign approved and activated'
          : status === 'rejected'
          ? 'Campaign rejected'
          : 'Changes requested from vendor'
      );
      await fetchQueue();
      onCountsChanged();
    } catch (err: any) {
      toast.error(err.message || 'Review action failed');
    } finally {
      setReviewingId(null);
      setNotesModalId(null);
      setReviewNotes('');
    }
  };

  return (
    <div>
      {/* Queue stats */}
      <div className="grid grid-cols-4 gap-3 mb-5">
        <StatCard
          label="Pending Review"
          value={queueCounts.pending_review}
          color="#8b5cf6"
          icon={<Clock size={16} />}
        />
        <StatCard
          label="Approved"
          value={queueCounts.approved}
          color="#16a34a"
          icon={<CheckCircle2 size={16} />}
        />
        <StatCard
          label="Rejected"
          value={queueCounts.rejected}
          color="#dc2626"
          icon={<XCircle size={16} />}
        />
        <StatCard
          label="Changes Requested"
          value={queueCounts.changes_requested}
          color="#f59e0b"
          icon={<AlertTriangle size={16} />}
        />
      </div>

      {/* Filters */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold" style={{ color: NAVY }}>
          {statusFilter === 'pending_review'
            ? 'Pending Creative Reviews'
            : statusFilter === 'approved'
            ? 'Approved Campaigns'
            : statusFilter === 'rejected'
            ? 'Rejected Campaigns'
            : statusFilter === 'changes_requested'
            ? 'Changes Requested'
            : 'All Reviews'}
        </h3>
        <div className="flex gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as ReviewStatus | '')}
            className="px-2.5 py-1.5 border rounded-md text-xs"
            style={{ borderColor: '#e2e8f0', color: '#64748b', minHeight: 36 }}
          >
            <option value="pending_review">Pending Review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="changes_requested">Changes Requested</option>
          </select>
          <select
            value={placementFilter}
            onChange={(e) => setPlacementFilter(e.target.value)}
            className="px-2.5 py-1.5 border rounded-md text-xs"
            style={{ borderColor: '#e2e8f0', color: '#64748b', minHeight: 36 }}
          >
            <option value="">All Placements</option>
            <option value="vendor_rail">Vendor Rail</option>
            <option value="vendor_detail">Vendor Detail</option>
            <option value="milestone_module">Milestone Module</option>
            <option value="directory_boost">Directory Boost</option>
            <option value="dashboard_rail">Dashboard Rail</option>
          </select>
        </div>
      </div>

      {/* Queue list */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="animate-spin mr-2" size={20} style={{ color: SAGE }} />
          <span className="text-sm" style={{ color: '#64748b' }}>
            Loading review queue...
          </span>
        </div>
      ) : queue.length === 0 ? (
        <div className="text-center py-16">
          <ShieldCheck size={36} className="mx-auto mb-3" style={{ color: '#cbd5e1' }} />
          <p className="text-sm font-bold" style={{ color: NAVY }}>
            No campaigns to review
          </p>
          <p className="text-xs mt-1" style={{ color: '#64748b' }}>
            All caught up. New submissions will appear here.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {queue.map((item) => {
            const id = String(item._id);
            const vendorName =
              item.vendor_profile?.business_name || 'Unknown Vendor';
            const category =
              item.vendor_profile?.service_category || 'uncategorized';
            const logoUrl = item.vendor_profile?.logo_url;
            const isReviewing = reviewingId === id;

            return (
              <div
                key={id}
                className="flex gap-4 p-4 rounded-xl border"
                style={{ background: '#fff', borderColor: '#e2e8f0' }}
              >
                {/* Preview */}
                <div
                  className="flex-shrink-0 rounded-lg flex items-center justify-center overflow-hidden"
                  style={{
                    width: 160,
                    height: 110,
                    background: logoUrl
                      ? `url(${logoUrl}) center/cover`
                      : 'linear-gradient(135deg,#f0f4f8,#e2e8f0)',
                  }}
                >
                  {!logoUrl && (
                    <Eye size={28} style={{ color: '#94a3b8' }} />
                  )}
                </div>

                {/* Details */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p
                        className="text-sm font-bold truncate"
                        style={{ color: NAVY }}
                      >
                        {vendorName}
                      </p>
                      <p className="text-[11px] mt-0.5" style={{ color: '#64748b' }}>
                        Goal: {item.metadata?.goal || 'N/A'}
                        <span
                          className="inline-flex ml-2 px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase"
                          style={{
                            background: 'rgba(69,123,157,0.1)',
                            color: SAGE,
                          }}
                        >
                          {getAdPlacementLabel(item.placement as any)}
                        </span>
                      </p>
                    </div>
                    <ReviewStatusBadge status={item.review_status as ReviewStatus} />
                  </div>

                  {/* Creative preview */}
                  <div
                    className="rounded-lg p-2.5 mt-2 mb-2"
                    style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}
                  >
                    <p className="text-xs font-bold" style={{ color: NAVY }}>
                      {item.headline || 'No headline'}
                    </p>
                    <p className="text-[11px] mt-0.5" style={{ color: '#475569' }}>
                      {item.description || 'No description provided'}
                    </p>
                    {item.metadata?.offer_text && (
                      <p
                        className="text-[11px] font-semibold mt-1"
                        style={{ color: SAGE }}
                      >
                        {item.metadata.offer_text}
                      </p>
                    )}
                    {item.metadata?.cta_text && (
                      <span
                        className="inline-flex mt-1.5 px-2 py-0.5 rounded text-[9px] font-bold text-white"
                        style={{ background: SAGE }}
                      >
                        {item.metadata.cta_text}
                      </span>
                    )}
                  </div>

                  {/* Meta line */}
                  <div className="flex gap-3 text-[10px] mb-2" style={{ color: '#94a3b8' }}>
                    <span>Category: {category}</span>
                    <span>
                      Submitted:{' '}
                      {item.created_at
                        ? new Date(item.created_at).toLocaleDateString()
                        : 'N/A'}
                    </span>
                    {item.reviewed_by && (
                      <span>Reviewed by: {item.reviewed_by}</span>
                    )}
                  </div>

                  {/* Review notes modal inline */}
                  {notesModalId === id && (
                    <div className="mb-2 p-3 rounded-lg" style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                      <label className="text-xs font-semibold block mb-1" style={{ color: NAVY }}>
                        Review Notes
                      </label>
                      <textarea
                        value={reviewNotes}
                        onChange={(e) => setReviewNotes(e.target.value)}
                        placeholder="Reason for rejection or requested changes..."
                        className="w-full border rounded-md px-3 py-2 text-xs resize-none"
                        style={{ borderColor: '#e2e8f0', minHeight: 60 }}
                        rows={3}
                      />
                      <div className="flex gap-2 mt-2">
                        <button
                          onClick={() =>
                            handleReview(
                              id,
                              notesModalId === id ? 'rejected' : 'changes_requested',
                              reviewNotes
                            )
                          }
                          disabled={isReviewing}
                          className="px-3 py-1.5 rounded-md text-xs font-semibold text-white"
                          style={{ background: '#dc2626', minHeight: 36 }}
                        >
                          {isReviewing ? 'Submitting...' : 'Confirm'}
                        </button>
                        <button
                          onClick={() => {
                            setNotesModalId(null);
                            setReviewNotes('');
                          }}
                          className="px-3 py-1.5 rounded-md text-xs font-semibold border"
                          style={{ borderColor: '#e2e8f0', color: '#64748b', minHeight: 36 }}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Actions — only for pending */}
                  {item.review_status === 'pending_review' && notesModalId !== id && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleReview(id, 'approved')}
                        disabled={isReviewing}
                        className="px-4 py-1.5 rounded-md text-[11px] font-semibold text-white"
                        style={{ background: '#16a34a', minHeight: 36 }}
                      >
                        {isReviewing ? (
                          <Loader2 size={14} className="animate-spin" />
                        ) : (
                          'Approve'
                        )}
                      </button>
                      <button
                        onClick={() => setNotesModalId(id)}
                        disabled={isReviewing}
                        className="px-4 py-1.5 rounded-md text-[11px] font-semibold text-white"
                        style={{ background: '#dc2626', minHeight: 36 }}
                      >
                        Reject
                      </button>
                      <button
                        onClick={() => setNotesModalId(id)}
                        disabled={isReviewing}
                        className="px-4 py-1.5 rounded-md text-[11px] font-semibold border"
                        style={{
                          background: '#f1f5f9',
                          color: '#64748b',
                          borderColor: '#e2e8f0',
                          minHeight: 36,
                        }}
                      >
                        Request Changes
                      </button>
                    </div>
                  )}

                  {/* Show review notes if present */}
                  {item.review_notes && item.review_status !== 'pending_review' && (
                    <div
                      className="text-[11px] p-2 rounded mt-1"
                      style={{ background: '#fef3c7', color: '#92400e' }}
                    >
                      <strong>Review notes:</strong> {item.review_notes}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}


// ===========================================================================
// TAB 2: PERFORMANCE DASHBOARD
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
        <Loader2 className="animate-spin mr-2" size={20} style={{ color: SAGE }} />
        <span className="text-sm" style={{ color: '#64748b' }}>
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
        <h3 className="text-sm font-bold" style={{ color: NAVY }}>
          Performance Overview
        </h3>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="px-2.5 py-1.5 border rounded-md text-xs"
          style={{ borderColor: '#e2e8f0', color: '#64748b', minHeight: 36 }}
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
        <div
          className="rounded-xl border p-5 mb-6"
          style={{ background: '#fff', borderColor: '#e2e8f0' }}
        >
          <h4 className="text-sm font-bold mb-1" style={{ color: NAVY }}>
            Daily Impressions Trend
          </h4>
          <p className="text-[11px] mb-4" style={{ color: '#94a3b8' }}>
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
                  className="flex-1 rounded-t"
                  style={{
                    background: SAGE,
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
      <div
        className="rounded-xl border p-5 mb-6"
        style={{ background: '#fff', borderColor: '#e2e8f0' }}
      >
        <h4 className="text-sm font-bold mb-4" style={{ color: NAVY }}>
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
      <div
        className="rounded-xl border p-5"
        style={{ background: '#fff', borderColor: '#e2e8f0' }}
      >
        <h4 className="text-sm font-bold mb-4" style={{ color: NAVY }}>
          Vendor Leaderboard
        </h4>
        {leaderboard.length === 0 ? (
          <p className="text-xs text-center py-8" style={{ color: '#94a3b8' }}>
            No vendor data for the selected period. Leaderboard populates from real ad events.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr
                  className="text-left"
                  style={{ color: NAVY, borderBottom: '2px solid #e2e8f0' }}
                >
                  <th className="py-2.5 px-3 font-bold text-[10px] uppercase tracking-wide bg-[#f8fafc]">
                    Rank
                  </th>
                  <th className="py-2.5 px-3 font-bold text-[10px] uppercase tracking-wide bg-[#f8fafc]">
                    Vendor
                  </th>
                  <th className="py-2.5 px-3 font-bold text-[10px] uppercase tracking-wide bg-[#f8fafc] text-right">
                    Impressions
                  </th>
                  <th className="py-2.5 px-3 font-bold text-[10px] uppercase tracking-wide bg-[#f8fafc] text-right">
                    Clicks
                  </th>
                  <th className="py-2.5 px-3 font-bold text-[10px] uppercase tracking-wide bg-[#f8fafc] text-right">
                    CTR
                  </th>
                  <th className="py-2.5 px-3 font-bold text-[10px] uppercase tracking-wide bg-[#f8fafc] text-right">
                    Leads
                  </th>
                </tr>
              </thead>
              <tbody>
                {leaderboard.map((entry, i) => (
                  <tr
                    key={entry.vendor_profile_id || i}
                    className="hover:bg-[#f8fafc] transition-colors"
                    style={{ borderBottom: '1px solid #f1f5f9' }}
                  >
                    <td className="py-2.5 px-3 font-extrabold text-sm" style={{ color: SAGE }}>
                      {i + 1}
                    </td>
                    <td className="py-2.5 px-3 font-medium" style={{ color: NAVY }}>
                      {entry.vendor_profile_id}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      {(entry.total_impressions || 0).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      {(entry.total_clicks || 0).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      {(entry.ctr || 0).toFixed(2)}%
                    </td>
                    <td className="py-2.5 px-3 text-right">
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
// TAB 3: SYSTEM CONFIG
// ===========================================================================

function SystemConfigTab({ token }: { token: string | null }) {
  const [featureFlag, setFeatureFlag] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const fetchConfig = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const flag = await getFeatureFlag(token);
      setFeatureFlag(flag);
    } catch (err: any) {
      toast.error(err.message || 'Failed to load config');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleToggleFeature = async () => {
    if (!token || !featureFlag) return;
    setSaving(true);
    try {
      const updated = await toggleFeatureFlag(token, !featureFlag.is_enabled);
      setFeatureFlag(updated);
      toast.success(
        updated.is_enabled
          ? 'Advertising feature enabled'
          : 'Advertising feature disabled'
      );
    } catch (err: any) {
      toast.error(err.message || 'Failed to toggle feature');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateConfig = async (key: string, value: any) => {
    if (!token) return;
    setSaving(true);
    try {
      const updated = await updateFeatureFlagConfig(token, { [key]: value });
      setFeatureFlag(updated);
      toast.success('Configuration updated');
    } catch (err: any) {
      toast.error(err.message || 'Failed to update config');
    } finally {
      setSaving(false);
    }
  };

  const handleTriggerRollup = async () => {
    if (!token) return;
    setSaving(true);
    try {
      const result = await triggerRollup(token);
      toast.success(
        `Rollup completed: ${result.documents_upserted} documents processed`
      );
    } catch (err: any) {
      toast.error(err.message || 'Failed to trigger rollup');
    } finally {
      setSaving(false);
    }
  };

  const handleBackfill = async () => {
    if (!token) return;
    setSaving(true);
    try {
      const result = await backfillRollups(token, 90);
      toast.success(
        `Backfill completed: ${result.total_documents} documents over ${result.days_backfilled} days`
      );
    } catch (err: any) {
      toast.error(err.message || 'Failed to backfill');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="animate-spin mr-2" size={20} style={{ color: SAGE }} />
        <span className="text-sm" style={{ color: '#64748b' }}>
          Loading configuration...
        </span>
      </div>
    );
  }

  const config = featureFlag?.config || {};

  return (
    <div className="space-y-4">
      {/* Feature Flags */}
      <ConfigSection title="Feature Flags" desc="Core advertising feature controls">
        <ConfigToggleRow
          label="Ads Enabled"
          hint="Master switch for all advertising features"
          enabled={featureFlag?.is_enabled || false}
          onChange={handleToggleFeature}
          saving={saving}
        />
        <ConfigToggleRow
          label="Show Sponsored Badge"
          hint="Display 'Sponsored' label on ad cards"
          enabled={config.show_sponsored_badge ?? true}
          onChange={() =>
            handleUpdateConfig(
              'show_sponsored_badge',
              !(config.show_sponsored_badge ?? true)
            )
          }
          saving={saving}
        />
        <ConfigToggleRow
          label="Enable Tracking"
          hint="Track impressions, clicks, and events"
          enabled={config.enable_tracking ?? true}
          onChange={() =>
            handleUpdateConfig(
              'enable_tracking',
              !(config.enable_tracking ?? true)
            )
          }
          saving={saving}
        />
      </ConfigSection>

      {/* Serving Limits */}
      <ConfigSection title="Serving Limits" desc="Control ad delivery volume">
        <ConfigValueRow
          label="Max Ads Per Page"
          value={config.max_sponsored_per_page ?? 3}
          onSave={(v) => handleUpdateConfig('max_sponsored_per_page', Number(v))}
          saving={saving}
        />
        <ConfigValueRow
          label="Impressions Per Session"
          value={config.impressions_per_session_limit ?? 5}
          onSave={(v) =>
            handleUpdateConfig('impressions_per_session_limit', Number(v))
          }
          saving={saving}
        />
        <ConfigValueRow
          label="Min Priority Threshold"
          value={config.min_priority_threshold ?? 1}
          onSave={(v) => handleUpdateConfig('min_priority_threshold', Number(v))}
          saving={saving}
        />
      </ConfigSection>

      {/* Review Workflow */}
      <ConfigSection title="Review Workflow" desc="Campaign approval settings">
        <ConfigToggleRow
          label="Require Review"
          hint="All new campaigns require admin review before going live"
          enabled={config.require_review ?? true}
          onChange={() =>
            handleUpdateConfig('require_review', !(config.require_review ?? true))
          }
          saving={saving}
        />
        <ConfigToggleRow
          label="Auto-Approve Returning Vendors"
          hint="Skip review for vendors with previously approved campaigns"
          enabled={config.auto_approve_returning_vendors ?? false}
          onChange={() =>
            handleUpdateConfig(
              'auto_approve_returning_vendors',
              !(config.auto_approve_returning_vendors ?? false)
            )
          }
          saving={saving}
        />
        <ConfigValueRow
          label="Review SLA (hours)"
          value={config.review_sla_hours ?? 48}
          onSave={(v) => handleUpdateConfig('review_sla_hours', Number(v))}
          saving={saving}
        />
      </ConfigSection>

      {/* Data Pipeline Controls */}
      <ConfigSection title="Data Pipeline Controls" desc="Manage rollup computation and backfill">
        <div className="flex items-center justify-between py-3">
          <div>
            <p className="text-[13px] font-medium" style={{ color: NAVY }}>
              Manual Rollup
            </p>
            <p className="text-[10px]" style={{ color: '#94a3b8' }}>
              Compute daily stats rollup for yesterday
            </p>
          </div>
          <button
            onClick={handleTriggerRollup}
            disabled={saving}
            className="px-3.5 py-1.5 rounded-md text-[11px] font-semibold text-white"
            style={{ background: SAGE, minHeight: 36 }}
          >
            {saving ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <span className="flex items-center gap-1.5">
                <Database size={12} /> Run Rollup
              </span>
            )}
          </button>
        </div>
        <div
          className="flex items-center justify-between py-3"
          style={{ borderTop: '1px solid #f1f5f9' }}
        >
          <div>
            <p className="text-[13px] font-medium" style={{ color: NAVY }}>
              Backfill (90 days)
            </p>
            <p className="text-[10px]" style={{ color: '#94a3b8' }}>
              Recompute rollup data for the last 90 days
            </p>
          </div>
          <button
            onClick={handleBackfill}
            disabled={saving}
            className="px-3.5 py-1.5 rounded-md text-[11px] font-semibold border"
            style={{
              background: '#f1f5f9',
              color: '#64748b',
              borderColor: '#e2e8f0',
              minHeight: 36,
            }}
          >
            {saving ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <span className="flex items-center gap-1.5">
                <RefreshCw size={12} /> Backfill
              </span>
            )}
          </button>
        </div>
      </ConfigSection>
    </div>
  );
}


// ===========================================================================
// TAB 4: REVENUE & BILLING (Placeholder — no fake data)
// ===========================================================================

function RevenueBillingTab() {
  return (
    <div>
      {/* Notice banner */}
      <div
        className="rounded-xl p-4 mb-6 flex gap-3 items-start"
        style={{
          background: 'rgba(233,196,106,0.08)',
          border: '1px solid rgba(233,196,106,0.25)',
        }}
      >
        <AlertTriangle size={18} style={{ color: GOLD, flexShrink: 0, marginTop: 1 }} />
        <div className="text-xs leading-relaxed" style={{ color: '#78716c' }}>
          <strong style={{ color: NAVY }}>Billing is not active.</strong> Revenue
          tracking will be enabled once Stripe billing integration is built. All
          monetary values shown below are $0 — this section is a placeholder for
          the eventual billing infrastructure. No fake data is displayed.
        </div>
      </div>

      {/* Revenue metrics — all zeroed */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        <MetricCard label="Total Revenue" value="$0" muted icon={<DollarSign size={16} />} />
        <MetricCard label="Active Invoices" value="0" muted icon={<Activity size={16} />} />
        <MetricCard label="Avg CPC" value="$0.00" muted icon={<MousePointerClick size={16} />} />
        <MetricCard label="Avg CPL" value="$0.00" muted icon={<Target size={16} />} />
      </div>

      {/* What exists vs what needs to be built */}
      <div
        className="rounded-xl border p-5 mb-4"
        style={{ background: '#fff', borderColor: '#e2e8f0' }}
      >
        <h4 className="text-sm font-bold mb-3" style={{ color: NAVY }}>
          Data Already Being Captured
        </h4>
        <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-xs" style={{ color: '#475569' }}>
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} style={{ color: '#16a34a' }} />
            <span>pricing_model (cpc, cpl, flat_monthly)</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} style={{ color: '#16a34a' }} />
            <span>cpc_bid and cpl_bid per campaign</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} style={{ color: '#16a34a' }} />
            <span>daily_budget and lifetime_budget</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} style={{ color: '#16a34a' }} />
            <span>Click and lead event tracking</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} style={{ color: '#16a34a' }} />
            <span>Rollup aggregation pipeline</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} style={{ color: '#16a34a' }} />
            <span>Vendor leaderboard with impressions/clicks/leads</span>
          </div>
        </div>
      </div>

      <div
        className="rounded-xl border p-5"
        style={{ background: '#fff', borderColor: '#e2e8f0' }}
      >
        <h4 className="text-sm font-bold mb-3" style={{ color: NAVY }}>
          Needs to Be Built
        </h4>
        <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-xs" style={{ color: '#475569' }}>
          <div className="flex items-center gap-2">
            <Clock size={14} style={{ color: '#8b5cf6' }} />
            <span>Stripe billing integration</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock size={14} style={{ color: '#8b5cf6' }} />
            <span>Usage metering (click/lead consumption records)</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock size={14} style={{ color: '#8b5cf6' }} />
            <span>Budget enforcement (pause when exhausted)</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock size={14} style={{ color: '#8b5cf6' }} />
            <span>Invoice generation and history</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock size={14} style={{ color: '#8b5cf6' }} />
            <span>Webhook handlers for payment events</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock size={14} style={{ color: '#8b5cf6' }} />
            <span>Revenue dashboard with real calculations</span>
          </div>
        </div>
      </div>

      {/* Annotation */}
      <div
        className="rounded-lg p-3 mt-6 text-[11px] leading-relaxed"
        style={{ background: '#f8fafc', border: '1px solid #e2e8f0', color: '#64748b' }}
      >
        <strong style={{ color: NAVY }}>Implementation note:</strong> This tab will
        become functional once the Stripe integration is connected. The pricing data
        (CPC bids, CPL bids, daily budgets) is already stored per campaign in
        metadata. The billing system will read these values, multiply by real event
        counts from the rollup pipeline, and produce invoices. No synthetic data
        will be generated.
      </div>
    </div>
  );
}


// ===========================================================================
// SHARED SUB-COMPONENTS
// ===========================================================================

function StatCard({
  label,
  value,
  color,
  icon,
}: {
  label: string;
  value: number;
  color: string;
  icon?: React.ReactNode;
}) {
  return (
    <div
      className="rounded-xl border p-4"
      style={{ background: '#fff', borderColor: '#e2e8f0' }}
    >
      <div className="flex items-center gap-2 mb-1">
        {icon && <span style={{ color }}>{icon}</span>}
        <span
          className="text-[10px] font-semibold uppercase tracking-wide"
          style={{ color: '#94a3b8' }}
        >
          {label}
        </span>
      </div>
      <div className="text-2xl font-extrabold" style={{ color }}>
        {value}
      </div>
    </div>
  );
}

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
      className="rounded-xl border p-4"
      style={{
        background: '#fff',
        borderColor: muted ? '#cbd5e1' : '#e2e8f0',
        borderStyle: muted ? 'dashed' : 'solid',
      }}
    >
      <div className="flex items-center gap-2 mb-1">
        {icon && <span style={{ color: muted ? '#94a3b8' : SAGE }}>{icon}</span>}
        <span
          className="text-[10px] font-semibold uppercase tracking-wide"
          style={{ color: '#94a3b8' }}
        >
          {label}
        </span>
      </div>
      <div
        className="text-2xl font-extrabold"
        style={{ color: muted ? '#94a3b8' : NAVY }}
      >
        {value}
      </div>
      {subtitle && (
        <p
          className="text-[11px] mt-1 font-medium italic"
          style={{ color: muted ? SAGE : '#16a34a' }}
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
  const statusColor =
    status === 'good' ? '#16a34a' : status === 'warn' ? '#f59e0b' : '#94a3b8';
  const statusText =
    statusLabel ||
    (status === 'good' ? 'Healthy' : status === 'warn' ? 'Warning' : 'N/A');

  return (
    <div
      className="rounded-xl border p-3.5 text-center"
      style={{ background: '#fff', borderColor: '#e2e8f0' }}
    >
      <div className="text-xl font-extrabold" style={{ color: NAVY }}>
        {value}
      </div>
      <div
        className="text-[10px] font-semibold uppercase tracking-wide mt-0.5"
        style={{ color: '#94a3b8' }}
      >
        {label}
      </div>
      <div
        className="text-[10px] font-semibold mt-1"
        style={{ color: statusColor, fontStyle: status === 'na' ? 'italic' : 'normal' }}
      >
        {statusText}
      </div>
    </div>
  );
}

function ReviewStatusBadge({ status }: { status: ReviewStatus | string | undefined }) {
  if (!status) return null;

  const styles: Record<string, { bg: string; color: string; label: string }> = {
    pending_review: {
      bg: 'rgba(139,92,246,0.1)',
      color: '#8b5cf6',
      label: 'PENDING',
    },
    approved: {
      bg: 'rgba(22,163,74,0.1)',
      color: '#16a34a',
      label: 'APPROVED',
    },
    rejected: {
      bg: 'rgba(220,38,38,0.1)',
      color: '#dc2626',
      label: 'REJECTED',
    },
    changes_requested: {
      bg: 'rgba(59,130,246,0.1)',
      color: '#3b82f6',
      label: 'CHANGES REQUESTED',
    },
  };

  const s = styles[status] || styles.pending_review;

  return (
    <span
      className="inline-flex px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide"
      style={{ background: s.bg, color: s.color }}
    >
      {s.label}
    </span>
  );
}

function ConfigSection({
  title,
  desc,
  children,
}: {
  title: string;
  desc: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-xl border p-5"
      style={{ background: '#fff', borderColor: '#e2e8f0' }}
    >
      <h4 className="text-sm font-bold" style={{ color: NAVY }}>
        {title}
      </h4>
      <p className="text-xs mb-3" style={{ color: '#64748b' }}>
        {desc}
      </p>
      {children}
    </div>
  );
}

function ConfigToggleRow({
  label,
  hint,
  enabled,
  onChange,
  saving,
}: {
  label: string;
  hint?: string;
  enabled: boolean;
  onChange: () => void;
  saving: boolean;
}) {
  return (
    <div
      className="flex items-center justify-between py-2.5"
      style={{ borderBottom: '1px solid #f1f5f9' }}
    >
      <div>
        <p className="text-[13px] font-medium" style={{ color: NAVY }}>
          {label}
        </p>
        {hint && (
          <p className="text-[10px]" style={{ color: '#94a3b8' }}>
            {hint}
          </p>
        )}
      </div>
      <button
        onClick={onChange}
        disabled={saving}
        className="relative rounded-full transition-colors"
        style={{
          width: 40,
          height: 22,
          background: enabled ? SAGE : '#cbd5e1',
          minHeight: 22,
          flexShrink: 0,
        }}
      >
        <span
          className="absolute top-0.5 rounded-full bg-white shadow transition-transform"
          style={{
            width: 18,
            height: 18,
            left: 2,
            transform: enabled ? 'translateX(18px)' : 'translateX(0)',
          }}
        />
      </button>
    </div>
  );
}

function ConfigValueRow({
  label,
  value,
  onSave,
  saving,
}: {
  label: string;
  value: number;
  onSave: (val: string) => void;
  saving: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [editVal, setEditVal] = useState(String(value));

  return (
    <div
      className="flex items-center justify-between py-2.5"
      style={{ borderBottom: '1px solid #f1f5f9' }}
    >
      <p className="text-[13px] font-medium" style={{ color: NAVY }}>
        {label}
      </p>
      {editing ? (
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={editVal}
            onChange={(e) => setEditVal(e.target.value)}
            className="w-16 px-2 py-1 border rounded text-xs text-right"
            style={{ borderColor: '#e2e8f0', minHeight: 32 }}
          />
          <button
            onClick={() => {
              onSave(editVal);
              setEditing(false);
            }}
            disabled={saving}
            className="px-2 py-1 rounded text-[10px] font-semibold text-white"
            style={{ background: SAGE, minHeight: 32 }}
          >
            Save
          </button>
          <button
            onClick={() => {
              setEditVal(String(value));
              setEditing(false);
            }}
            className="px-2 py-1 rounded text-[10px] font-semibold border"
            style={{ borderColor: '#e2e8f0', color: '#64748b', minHeight: 32 }}
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          onClick={() => setEditing(true)}
          className="text-[13px] font-semibold cursor-pointer hover:underline"
          style={{ color: SAGE }}
        >
          {value}
        </button>
      )}
    </div>
  );
}
