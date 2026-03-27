'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter } from 'next/navigation';
import PageHeader from '../components/PageHeader';
import { Card } from '@/components/ui/Card';
import { toast } from 'sonner';
import {
  getAdminReviewQueue,
  getAdminReviewCounts,
  approveCampaign,
  rejectCampaign,
  requestCampaignChanges,
  getCreativeReviewQueue,
  approveCreative,
  rejectCreative,
  getAdminCampaigns,
  adminPauseCampaign,
  adminDeactivateCampaign,
  getAdminRevenue,
  getAdminFeedback,
  getAdminFraudSignals,
  updateFraudSignal,
  getAdminVendorAccounts,
  setCampaignFreeTier,
  setVendorFreeTier,
  listFreeTierVendors,
  getCampaignBilling,
  getCampaignStatusLabel,
  getCampaignStatusColor,
  getCreativeStatusLabel,
  getCreativeStatusColor,
  getFraudSignalLabel,
  formatCurrency,
  formatNumber,
  formatPercent,
  type AdCampaign,
  type AdCreative,
  type ReviewCounts,
  type RevenueResponse,
  type AdFraudSignal,
  type VendorAccountSummary,
  type PlannerFeedbackEntry,
  type CampaignStatus,
  type FreeTierStatus,
  type CampaignBillingSummary,
  approveVendorAccount,
  suspendVendorAccount,
  reactivateVendorAccount,
} from '@/services/campaignAdvertisingApi';
import {
  Megaphone,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Eye,
  Pause,
  Ban,
  TrendingUp,
  DollarSign,
  Users,
  MousePointerClick,
  BarChart3,
  MessageSquare,
  Shield,
  Building2,
  RefreshCw,
  Image,
  FileText,
  Activity,
  Search,
  Filter,
  ArrowUpRight,
  type LucideIcon,
} from 'lucide-react';

// =============================================================================
// Tab configuration
// =============================================================================

type TabId = 'creative-review' | 'campaigns' | 'revenue' | 'vendors' | 'feedback';

const TABS: { id: TabId; label: string }[] = [
  { id: 'creative-review', label: 'Creative Review' },
  { id: 'campaigns', label: 'Campaign Monitor' },
  { id: 'revenue', label: 'Revenue Dashboard' },
  { id: 'vendors', label: 'Vendor Accounts' },
  { id: 'feedback', label: 'Planner Feedback' },
];

const ADS_PANEL_CLASS =
  'bg-white dark:bg-slate-800/95 rounded-xl shadow-md border border-slate-200 dark:border-slate-700';

// =============================================================================
// Main Page Component
// =============================================================================

export default function AdminAdsPage() {
  const { token, userProfile } = useAdmin();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabId>('creative-review');

  // Redirect non-admins
  useEffect(() => {
    if (userProfile && !userProfile.is_root_admin) {
      router.push('/admin/planner');
    }
  }, [userProfile, router]);

  if (!userProfile?.is_root_admin) return null;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Advertising Platform"
        description="Manage ad campaigns, review creatives, and monitor platform monetization"
      >
        <button
          onClick={() => router.push('/admin/saas?tab=ad-config')}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-700"
        >
          Manage Ad Config
          <ArrowUpRight className="h-4 w-4" />
        </button>
      </PageHeader>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="scrollbar-thin -mb-px flex min-w-max gap-4 overflow-x-auto pb-1 pr-2 sm:gap-6 lg:gap-8">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`shrink-0 whitespace-nowrap border-b-2 px-1 py-3 text-sm font-medium ${
                activeTab === tab.id
                  ? 'border-wedding-rose text-wedding-rose'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'creative-review' && <CreativeReviewTab token={token!} />}
      {activeTab === 'campaigns' && <CampaignMonitorTab token={token!} />}
      {activeTab === 'revenue' && <RevenueDashboardTab token={token!} />}
      {activeTab === 'vendors' && <VendorAccountsTab token={token!} />}
      {activeTab === 'feedback' && <PlannerFeedbackTab token={token!} />}
    </div>
  );
}

// =============================================================================
// Shared Components
// =============================================================================

function StatCard({ label, value, icon: Icon, color = 'text-slate-600' }: {
  label: string;
  value: string | number;
  icon: LucideIcon;
  color?: string;
}) {
  return (
    <Card className="h-full p-4 sm:p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{label}</p>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-gray-100">{value}</p>
        </div>
        <div className={`rounded-lg bg-slate-100 p-2.5 dark:bg-slate-700 ${color}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </Card>
  );
}

function StatusBadge({ status, getLabel, getColor }: {
  status: string;
  getLabel: (s: any) => string;
  getColor: (s: any) => string;
}) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getColor(status)}`}>
      {getLabel(status)}
    </span>
  );
}

function EmptyState({ icon: Icon, title, description }: {
  icon: LucideIcon;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-xl border-2 border-dashed border-gray-300 bg-gray-50 px-4 py-8 text-center dark:border-gray-600 dark:bg-slate-700">
      <Icon className="mx-auto mb-2 h-10 w-10 text-gray-400" />
      <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">{title}</h3>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{description}</p>
    </div>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-gray-600 dark:text-gray-400">Loading...</p>
      </div>
    </div>
  );
}

// =============================================================================
// Tab 1: Creative Review
// =============================================================================

function CreativeReviewTab({ token }: { token: string }) {
  const [campaigns, setCampaigns] = useState<AdCampaign[]>([]);
  const [creatives, setCreatives] = useState<AdCreative[]>([]);
  const [counts, setCounts] = useState<ReviewCounts | null>(null);
  const [loading, setLoading] = useState(true);
  const [reviewFilter, setReviewFilter] = useState<string>('pending_review');
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [queue, queueCounts, creativeQueue] = await Promise.all([
        getAdminReviewQueue(token, { status: reviewFilter, limit: 50 }),
        getAdminReviewCounts(token),
        getCreativeReviewQueue(token, { limit: 50 }),
      ]);
      setCampaigns(Array.isArray(queue) ? queue : (queue as any).items ?? []);
      setCounts(queueCounts);
      setCreatives(Array.isArray(creativeQueue) ? creativeQueue : (creativeQueue as any).items ?? []);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, reviewFilter]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleCampaignAction = async (campaignId: string, action: 'approve' | 'reject' | 'request-changes') => {
    try {
      setActionLoading(campaignId);
      const notes = reviewNotes[campaignId] || '';
      if (action === 'approve') {
        await approveCampaign(token, campaignId, { review_notes: notes || undefined });
        toast.success('Campaign approved');
      } else if (action === 'reject') {
        await rejectCampaign(token, campaignId, { review_notes: notes || undefined });
        toast.success('Campaign rejected');
      } else {
        if (!notes.trim()) { toast.error('Please add review notes for change requests'); return; }
        await requestCampaignChanges(token, campaignId, { review_notes: notes });
        toast.success('Changes requested');
      }
      loadData();
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleCreativeAction = async (creativeId: string, action: 'approve' | 'reject') => {
    try {
      setActionLoading(creativeId);
      if (action === 'approve') {
        await approveCreative(token, creativeId);
        toast.success('Creative approved');
      } else {
        await rejectCreative(token, creativeId);
        toast.success('Creative rejected');
      }
      loadData();
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-5">
      {/* Status Counts */}
      {counts && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
          <StatCard label="Pending" value={counts.pending_review} icon={Clock} color="text-amber-500" />
          <StatCard label="Active" value={counts.active} icon={CheckCircle2} color="text-emerald-500" />
          <StatCard label="Paused" value={counts.paused} icon={Pause} color="text-orange-500" />
          <StatCard label="Rejected" value={counts.rejected} icon={XCircle} color="text-red-500" />
          <StatCard label="Draft" value={counts.draft} icon={FileText} color="text-slate-500" />
          <StatCard label="Completed" value={counts.completed} icon={CheckCircle2} color="text-blue-500" />
          <StatCard label="Total" value={counts.total} icon={Megaphone} color="text-primary-500" />
        </div>
      )}

      {/* Filter */}
      <div className="flex flex-wrap items-center gap-2">
        <Filter size={16} className="text-slate-400" />
        <select
          value={reviewFilter}
          onChange={(e) => setReviewFilter(e.target.value)}
          className="min-w-[190px] text-sm border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-1.5 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200"
        >
          <option value="pending_review">Pending Review</option>
          <option value="active">Active</option>
          <option value="paused">Paused</option>
          <option value="rejected">Rejected</option>
          <option value="draft">Draft</option>
        </select>
        <button onClick={loadData} className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors">
          <RefreshCw size={16} className="text-slate-400" />
        </button>
      </div>

      {/* Campaign Review Queue */}
      <div>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">Campaign Review Queue</h2>
        {campaigns.length === 0 ? (
          <EmptyState icon={Megaphone} title="No campaigns to review" description={`No ${reviewFilter.replace('_', ' ')} campaigns found.`} />
        ) : (
          <div className="space-y-3">
            {campaigns.map((campaign) => (
              <div key={campaign._id} className={`${ADS_PANEL_CLASS} p-4 sm:p-5`}>
                <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-base font-semibold text-slate-900 dark:text-white truncate">{campaign.campaign_name}</h3>
                      <StatusBadge status={campaign.status} getLabel={getCampaignStatusLabel} getColor={getCampaignStatusColor} />
                    </div>
                    <div className="grid grid-cols-1 gap-2 text-sm text-slate-600 dark:text-slate-400 sm:grid-cols-2 xl:grid-cols-4">
                      <div><span className="text-slate-400">Vendor:</span> {campaign.vendor_name}</div>
                      <div><span className="text-slate-400">Goal:</span> {campaign.goal.replace('_', ' ')}</div>
                      <div><span className="text-slate-400">Category:</span> {campaign.vendor_category || 'Not set'}</div>
                      <div><span className="text-slate-400">Budget:</span> {formatCurrency(campaign.daily_budget)}/day</div>
                    </div>
                    {campaign.campaign_description && (
                      <p className="text-sm text-slate-500 dark:text-slate-400 mt-2 line-clamp-2">{campaign.campaign_description}</p>
                    )}
                    {campaign.target_categories.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {campaign.target_categories.map((cat) => (
                        <span key={cat} className="px-2 py-0.5 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-md text-xs">{cat}</span>
                      ))}
                      </div>
                    )}
                  </div>

                  {/* Review Actions */}
                  {reviewFilter === 'pending_review' && (
                    <div className="flex flex-col gap-2 lg:min-w-[220px]">
                      <textarea
                        placeholder="Review notes (optional)..."
                        value={reviewNotes[campaign._id] || ''}
                        onChange={(e) => setReviewNotes((prev) => ({ ...prev, [campaign._id]: e.target.value }))}
                        className="w-full text-sm border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 resize-none"
                        rows={2}
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleCampaignAction(campaign._id, 'approve')}
                          disabled={actionLoading === campaign._id}
                          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
                        >
                          <CheckCircle2 size={14} /> Approve
                        </button>
                        <button
                          onClick={() => handleCampaignAction(campaign._id, 'reject')}
                          disabled={actionLoading === campaign._id}
                          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
                        >
                          <XCircle size={14} /> Reject
                        </button>
                      </div>
                      <button
                        onClick={() => handleCampaignAction(campaign._id, 'request-changes')}
                        disabled={actionLoading === campaign._id}
                        className="flex items-center justify-center gap-1.5 px-3 py-1.5 border border-amber-400 text-amber-600 dark:text-amber-400 text-sm font-medium rounded-lg hover:bg-amber-50 dark:hover:bg-amber-900/20 transition-colors disabled:opacity-50"
                      >
                        <AlertTriangle size={14} /> Request Changes
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Creative Review Queue */}
      <div>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">Creative Review Queue</h2>
        {creatives.length === 0 ? (
          <EmptyState icon={Image} title="No creatives to review" description="All creatives have been reviewed." />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {creatives.map((creative) => (
              <div key={creative._id} className={`${ADS_PANEL_CLASS} overflow-hidden`}>
                {creative.image_url && (
                  <div className="aspect-video bg-slate-100 dark:bg-slate-700 relative">
                    <img src={creative.image_url} alt={creative.image_alt_text || creative.headline} className="w-full h-full object-cover" />
                  </div>
                )}
                <div className="p-3.5 sm:p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-semibold text-sm text-slate-900 dark:text-white truncate">{creative.headline}</h4>
                    <StatusBadge status={creative.review_status} getLabel={getCreativeStatusLabel} getColor={getCreativeStatusColor} />
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mb-3 line-clamp-2">{creative.description}</p>
                  {creative.offer && (
                    <p className="text-xs text-amber-600 dark:text-amber-400 font-medium mb-3">{creative.offer}</p>
                  )}
                  {creative.review_status === 'pending' && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleCreativeAction(creative._id, 'approve')}
                        disabled={actionLoading === creative._id}
                        className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                      >
                        <CheckCircle2 size={12} /> Approve
                      </button>
                      <button
                        onClick={() => handleCreativeAction(creative._id, 'reject')}
                        disabled={actionLoading === creative._id}
                        className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
                      >
                        <XCircle size={12} /> Reject
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Tab 2: Campaign Monitor
// =============================================================================

function CampaignMonitorTab({ token }: { token: string }) {
  const [campaigns, setCampaigns] = useState<AdCampaign[]>([]);
  const [fraudSignals, setFraudSignals] = useState<AdFraudSignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [campaignData, fraudData] = await Promise.all([
        getAdminCampaigns(token, { status: statusFilter || undefined, limit: 100 }),
        getAdminFraudSignals(token, { status: 'pending', limit: 20 }),
      ]);
      setCampaigns(Array.isArray(campaignData) ? campaignData : (campaignData as any).items ?? []);
      setFraudSignals(Array.isArray(fraudData) ? fraudData : (fraudData as any).items ?? []);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter]);

  useEffect(() => { loadData(); }, [loadData]);

  const handlePause = async (id: string) => {
    try {
      setActionLoading(id);
      await adminPauseCampaign(token, id, 'Admin paused');
      toast.success('Campaign paused');
      loadData();
    } catch (err: any) { toast.error(err.message); }
    finally { setActionLoading(null); }
  };

  const handleDeactivate = async (id: string) => {
    try {
      setActionLoading(id);
      await adminDeactivateCampaign(token, id, 'Admin deactivated');
      toast.success('Campaign deactivated');
      loadData();
    } catch (err: any) { toast.error(err.message); }
    finally { setActionLoading(null); }
  };

  const handleFraudUpdate = async (signalId: string, status: string) => {
    try {
      await updateFraudSignal(token, signalId, { status });
      toast.success('Signal updated');
      loadData();
    } catch (err: any) { toast.error(err.message); }
  };

  const handleToggleFreeTier = async (id: string, isCurrentlyFree: boolean) => {
    try {
      setActionLoading(id);
      await setCampaignFreeTier(token, id, { is_free: !isCurrentlyFree });
      toast.success(!isCurrentlyFree ? 'Campaign set to free tier' : 'Campaign removed from free tier');
      loadData();
    } catch (err: any) { toast.error(err.message); }
    finally { setActionLoading(null); }
  };

  const filteredCampaigns = campaigns.filter((c) =>
    !searchQuery || c.campaign_name.toLowerCase().includes(searchQuery.toLowerCase()) || c.vendor_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-5">
      {/* Fraud Signals Alert */}
      {fraudSignals.length > 0 && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Shield size={18} className="text-red-500" />
            <h3 className="text-sm font-semibold text-red-700 dark:text-red-400">Fraud Signals ({fraudSignals.length})</h3>
          </div>
          <div className="space-y-2">
            {fraudSignals.slice(0, 5).map((signal) => (
              <div key={signal._id} className="flex items-center justify-between bg-white dark:bg-slate-800 rounded-lg p-3 text-sm">
                <div>
                  <span className="font-medium text-slate-900 dark:text-white">{getFraudSignalLabel(signal.signal_type)}</span>
                  {signal.click_velocity && <span className="text-red-500 ml-2">({signal.click_velocity} clicks/5min)</span>}
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleFraudUpdate(signal._id, 'false_alarm')} className="text-xs px-2 py-1 bg-slate-100 dark:bg-slate-700 rounded hover:bg-slate-200">Dismiss</button>
                  <button onClick={() => handleFraudUpdate(signal._id, 'confirmed_fraud')} className="text-xs px-2 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200">Confirm</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search campaigns or vendors..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-sm border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200"
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="pending_review">Pending Review</option>
          <option value="paused">Paused</option>
          <option value="draft">Draft</option>
          <option value="rejected">Rejected</option>
          <option value="completed">Completed</option>
        </select>
        <button onClick={loadData} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors">
          <RefreshCw size={16} className="text-slate-400" />
        </button>
      </div>

      {/* Campaign Table */}
      <div className={`${ADS_PANEL_CLASS} overflow-hidden`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-700">
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">Campaign</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">Vendor</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">Status</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">Impressions</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">Clicks</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">Leads</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">CTR</th>
                <th className="text-center px-4 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {filteredCampaigns.map((campaign) => {
                const ctr = campaign.impression_count > 0
                  ? (campaign.click_count / campaign.impression_count)
                  : 0;
                return (
                  <tr key={campaign._id} className="hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900 dark:text-white truncate max-w-[200px]">{campaign.campaign_name}</div>
                      <div className="text-xs text-slate-400">{campaign.goal.replace('_', ' ')}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300 truncate max-w-[150px]">{campaign.vendor_name}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={campaign.status} getLabel={getCampaignStatusLabel} getColor={getCampaignStatusColor} />
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700 dark:text-slate-300">{formatNumber(campaign.impression_count)}</td>
                    <td className="px-4 py-3 text-right text-slate-700 dark:text-slate-300">{formatNumber(campaign.click_count)}</td>
                    <td className="px-4 py-3 text-right text-slate-700 dark:text-slate-300">{formatNumber(campaign.lead_count)}</td>
                    <td className="px-4 py-3 text-right text-slate-700 dark:text-slate-300">{formatPercent(ctr)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1">
                          {campaign.status === 'active' && (
                            <button
                              onClick={() => handlePause(campaign._id)}
                              disabled={actionLoading === campaign._id}
                              className="p-1.5 hover:bg-orange-50 dark:hover:bg-orange-900/20 text-orange-500 rounded-lg transition-colors disabled:opacity-50"
                              title="Pause"
                            >
                              <Pause size={14} />
                            </button>
                          )}
                          {(campaign.status === 'active' || campaign.status === 'paused') && (
                            <button
                              onClick={() => handleDeactivate(campaign._id)}
                              disabled={actionLoading === campaign._id}
                              className="p-1.5 hover:bg-red-50 dark:hover:bg-red-900/20 text-red-500 rounded-lg transition-colors disabled:opacity-50"
                              title="Deactivate"
                            >
                              <Ban size={14} />
                            </button>
                          )}
                        </div>
                        <button
                          onClick={() => handleToggleFreeTier(campaign._id, campaign.is_free_tier || false)}
                          disabled={actionLoading === campaign._id}
                          className={`text-xs px-2 py-1 rounded transition-colors disabled:opacity-50 ${
                            campaign.is_free_tier
                              ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                              : 'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-300'
                          }`}
                          title={campaign.is_free_tier ? 'Remove free tier' : 'Make free tier'}
                        >
                          {campaign.is_free_tier ? 'Free ✓' : 'Make Free'}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {filteredCampaigns.length === 0 && (
          <EmptyState icon={Megaphone} title="No campaigns found" description="No campaigns match your filters." />
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Tab 3: Revenue Dashboard
// =============================================================================

function RevenueDashboardTab({ token }: { token: string }) {
  const [revenue, setRevenue] = useState<RevenueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [freeTierVendors, setFreeTierVendors] = useState<any[]>([]);
  const [freeTierLoading, setFreeTierLoading] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getAdminRevenue(token, days);
      setRevenue(data);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, days]);

  const loadFreeTierVendors = useCallback(async () => {
    try {
      setFreeTierLoading(true);
      const data = await listFreeTierVendors(token);
      setFreeTierVendors(Array.isArray(data) ? data : (data as any).items ?? []);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setFreeTierLoading(false);
    }
  }, [token]);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => { loadFreeTierVendors(); }, [loadFreeTierVendors]);

  if (loading) return <LoadingSpinner />;
  if (!revenue) return <EmptyState icon={DollarSign} title="No data" description="Revenue data is not available yet." />;

  return (
    <div className="space-y-5">
      {/* Period Selector */}
      <div className="flex items-center gap-2">
        {[7, 14, 30, 90].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
              days === d
                ? 'bg-primary-500 text-white'
                : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600'
            }`}
          >
            {d}d
          </button>
        ))}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Revenue" value={formatCurrency(revenue.total_revenue)} icon={DollarSign} color="text-emerald-500" />
        <StatCard label="Impressions" value={formatNumber(revenue.total_impressions)} icon={Eye} color="text-blue-500" />
        <StatCard label="Clicks" value={formatNumber(revenue.total_clicks)} icon={MousePointerClick} color="text-purple-500" />
        <StatCard label="Leads" value={formatNumber(revenue.total_leads)} icon={Users} color="text-amber-500" />
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Conversions" value={formatNumber(revenue.total_conversions)} icon={TrendingUp} color="text-emerald-500" />
        <StatCard label="Active Campaigns" value={revenue.active_campaigns} icon={Megaphone} color="text-primary-500" />
        <StatCard label="Active Vendors" value={revenue.active_vendors} icon={Building2} color="text-indigo-500" />
        <StatCard label="Avg CTR" value={formatPercent(revenue.avg_ctr)} icon={BarChart3} color="text-orange-500" />
      </div>

      {/* Daily Trend (simple table for now — Recharts can be added later) */}
      {revenue.daily_series && revenue.daily_series.length > 0 && (
        <div className={`${ADS_PANEL_CLASS} p-4 sm:p-5`}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-4">Daily Trend</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700">
                  <th className="text-left px-3 py-2 text-xs font-medium text-slate-500 uppercase">Date</th>
                  <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 uppercase">Revenue</th>
                  <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 uppercase">Impressions</th>
                  <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 uppercase">Clicks</th>
                  <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 uppercase">Leads</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {revenue.daily_series.slice(-14).map((day) => (
                  <tr key={day.date}>
                    <td className="px-3 py-2 text-slate-700 dark:text-slate-300">{new Date(day.date).toLocaleDateString()}</td>
                    <td className="px-3 py-2 text-right text-slate-700 dark:text-slate-300">{formatCurrency(day.revenue)}</td>
                    <td className="px-3 py-2 text-right text-slate-700 dark:text-slate-300">{formatNumber(day.impressions)}</td>
                    <td className="px-3 py-2 text-right text-slate-700 dark:text-slate-300">{formatNumber(day.clicks)}</td>
                    <td className="px-3 py-2 text-right text-slate-700 dark:text-slate-300">{formatNumber(day.leads)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Free Tier Vendors */}
      {!freeTierLoading && (
        <div className={`${ADS_PANEL_CLASS} p-4 sm:p-5`}>
          <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-4">Free Tier Vendors ({freeTierVendors.length})</h3>
          {freeTierVendors.length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-slate-400">No vendors currently on free tier.</p>
          ) : (
            <div className="space-y-2">
              {freeTierVendors.map((vendor: any) => (
                <div key={vendor.vendor_id || vendor._id} className="flex items-center justify-between bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3 text-sm">
                  <div>
                    <span className="font-medium text-slate-900 dark:text-white">{vendor.vendor_name || vendor.name}</span>
                    <div className="text-xs text-slate-500 mt-0.5">{vendor.campaigns_count || 0} campaigns</div>
                  </div>
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">Free</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Free Tier Notice */}
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-4">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-blue-500" />
          <p className="text-sm text-blue-700 dark:text-blue-300">
            <strong>Free Tier Active</strong> — All campaigns are currently running at $0 cost. Revenue tracking is in place for when paid tiers are launched.
          </p>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Tab 4: Vendor Accounts
// =============================================================================

function VendorAccountsTab({ token }: { token: string }) {
  const [vendors, setVendors] = useState<VendorAccountSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getAdminVendorAccounts(token, { status: statusFilter || undefined, limit: 100 });
      setVendors(Array.isArray(data) ? data : (data as any).items ?? []);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleToggleFreeTier = async (vendorId: string, isCurrentlyFree: boolean) => {
    try {
      setActionLoading(vendorId);
      await setVendorFreeTier(token, vendorId, { is_free: !isCurrentlyFree, reason: 'Admin override' });
      toast.success(!isCurrentlyFree ? 'Vendor set to free tier' : 'Vendor removed from free tier');
      loadData();
    } catch (err: any) { toast.error(err.message); }
    finally { setActionLoading(null); }
  };

  const handleApprove = async (vendorId: string) => {
    try {
      setActionLoading(vendorId);
      await approveVendorAccount(token, vendorId);
      toast.success('Vendor approved! Temporary password emailed.');
      loadData();
    } catch (err: any) { toast.error(err.message); }
    finally { setActionLoading(null); }
  };

  const handleSuspend = async (vendorId: string) => {
    const reason = window.prompt('Reason for suspension (optional):');
    if (reason === null) return; // cancelled
    try {
      setActionLoading(vendorId);
      const result = await suspendVendorAccount(token, vendorId, reason);
      toast.success(`Vendor suspended. ${result.campaigns_paused} campaign(s) paused.`);
      loadData();
    } catch (err: any) { toast.error(err.message); }
    finally { setActionLoading(null); }
  };

  const handleReactivate = async (vendorId: string) => {
    try {
      setActionLoading(vendorId);
      await reactivateVendorAccount(token, vendorId);
      toast.success('Vendor reactivated. Campaigns remain paused.');
      loadData();
    } catch (err: any) { toast.error(err.message); }
    finally { setActionLoading(null); }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-5">
      {/* Filter */}
      <div className="flex items-center gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-sm border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200"
        >
          <option value="">All Vendors</option>
          <option value="active">Active</option>
          <option value="pending_approval">Pending Approval</option>
          <option value="suspended">Suspended</option>
          <option value="inactive">Inactive</option>
        </select>
        <span className="text-sm text-slate-500">{vendors.length} vendor{vendors.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Vendor Cards */}
      {vendors.length === 0 ? (
        <EmptyState icon={Building2} title="No vendor accounts" description="No advertising vendors have registered yet." />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {vendors.map((vendor) => (
            <div key={vendor.vendor_id} className={`${ADS_PANEL_CLASS} p-4 sm:p-5`}>
              <div className="flex items-start justify-between mb-3">
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white truncate">{vendor.vendor_name}</h3>
                  <p className="text-xs text-slate-500 truncate">{vendor.vendor_email}</p>
                </div>
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                  vendor.status === 'active' ? 'bg-emerald-100 text-emerald-700' :
                  vendor.status === 'pending_approval' ? 'bg-amber-100 text-amber-700' :
                  vendor.status === 'suspended' ? 'bg-red-100 text-red-700' :
                  'bg-slate-100 text-slate-700'
                }`}>
                  {vendor.status.replace('_', ' ')}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-2">
                  <p className="text-xs text-slate-500">Campaigns</p>
                  <p className="text-sm font-semibold text-slate-900 dark:text-white">{vendor.campaigns_count}</p>
                </div>
                <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-2">
                  <p className="text-xs text-slate-500">Active</p>
                  <p className="text-sm font-semibold text-emerald-600">{vendor.active_campaigns}</p>
                </div>
                <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-2">
                  <p className="text-xs text-slate-500">Leads</p>
                  <p className="text-sm font-semibold text-slate-900 dark:text-white">{vendor.total_leads}</p>
                </div>
              </div>
              <div className="flex justify-between mt-3 text-xs text-slate-500">
                <span>{formatNumber(vendor.total_impressions)} impressions</span>
                <span>{formatNumber(vendor.total_clicks)} clicks</span>
              </div>
              {/* Action Buttons */}
              <div className="flex gap-2 mt-4">
                {vendor.status === 'pending_approval' && (
                  <button
                    onClick={() => handleApprove(vendor.vendor_id)}
                    disabled={actionLoading === vendor.vendor_id}
                    className="flex-1 text-xs px-2 py-1.5 rounded font-medium bg-emerald-100 text-emerald-700 hover:bg-emerald-200 disabled:opacity-50 transition-colors"
                  >
                    Approve
                  </button>
                )}
                {vendor.status === 'active' && (
                  <button
                    onClick={() => handleSuspend(vendor.vendor_id)}
                    disabled={actionLoading === vendor.vendor_id}
                    className="flex-1 text-xs px-2 py-1.5 rounded font-medium bg-red-100 text-red-700 hover:bg-red-200 disabled:opacity-50 transition-colors"
                  >
                    Suspend
                  </button>
                )}
                {vendor.status === 'suspended' && (
                  <button
                    onClick={() => handleReactivate(vendor.vendor_id)}
                    disabled={actionLoading === vendor.vendor_id}
                    className="flex-1 text-xs px-2 py-1.5 rounded font-medium bg-blue-100 text-blue-700 hover:bg-blue-200 disabled:opacity-50 transition-colors"
                  >
                    Reactivate
                  </button>
                )}
                <button
                  onClick={() => handleToggleFreeTier(vendor.vendor_id, vendor.is_free_tier || false)}
                  disabled={actionLoading === vendor.vendor_id}
                  className={`flex-1 text-xs px-2 py-1.5 rounded transition-colors disabled:opacity-50 font-medium ${
                    vendor.is_free_tier
                      ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-300'
                  }`}
                  title={vendor.is_free_tier ? 'Remove free tier' : 'Make free tier'}
                >
                  {vendor.is_free_tier ? 'Free ✓' : 'Make Free'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Tab 6: Planner Feedback
// =============================================================================

function PlannerFeedbackTab({ token }: { token: string }) {
  const [feedback, setFeedback] = useState<PlannerFeedbackEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getAdminFeedback(token, { limit: 50 });
      setFeedback(Array.isArray(data) ? data : (data as any).items ?? []);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { loadData(); }, [loadData]);

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-3">
      {feedback.length === 0 ? (
        <EmptyState icon={MessageSquare} title="No feedback yet" description="Planners haven't submitted any feedback about ads." />
      ) : (
        feedback.map((entry) => (
          <div key={entry._id} className={`${ADS_PANEL_CLASS} p-4 sm:p-5`}>
            <div className="flex items-start justify-between mb-2">
              <div>
                <span className="text-sm font-medium text-slate-900 dark:text-white">{entry.planner_email}</span>
                <span className={`ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                  entry.feedback_type === 'positive' ? 'bg-emerald-100 text-emerald-700' :
                  entry.feedback_type === 'negative' ? 'bg-red-100 text-red-700' :
                  'bg-slate-100 text-slate-700'
                }`}>
                  {entry.feedback_type}
                </span>
              </div>
              <span className="text-xs text-slate-400">{new Date(entry.created_at).toLocaleDateString()}</span>
            </div>
            <p className="text-sm text-slate-600 dark:text-slate-300">{entry.message}</p>
          </div>
        ))
      )}
    </div>
  );
}
