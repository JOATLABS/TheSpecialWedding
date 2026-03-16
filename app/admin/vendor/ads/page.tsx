'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAdmin } from '@/contexts/AdminContext';
import {
  getSponsoredVendors,
  getAdStats,
  type SponsoredVendor,
  type AdStats,
  getAdPlacementLabel,
} from '@/services/advertisingApi';
import {
  BarChart3,
  TrendingUp,
  Users,
  MousePointerClick,
  Activity,
  Plus,
  Calendar,
  DollarSign,
  MessageSquare,
} from 'lucide-react';
import { toast } from 'sonner';

type TabId = 'overview' | 'campaigns' | 'leads' | 'billing';

interface PerformanceMetrics {
  totalImpressions: number;
  totalClicks: number;
  ctr: number;
  activeCampaigns: number;
  totalLeads: number;
  totalSpend: number;
}

interface Campaign {
  id: string;
  name: string;
  status: 'active' | 'paused' | 'ended';
  budget: number;
  spent: number;
  impressions: number;
  clicks: number;
  leads: number;
  createdAt: string;
  endDate?: string;
}

interface Lead {
  id: string;
  plannerName: string;
  weddingDate: string;
  status: 'new' | 'contacted' | 'converted' | 'lost';
  source: string;
  timestamp: string;
}

export default function VendorAdsDashboard() {
  const router = useRouter();
  const { token, userProfile } = useAdmin();
  const [activeTab, setActiveTab] = useState<TabId>('overview');

  // Loading states
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Data states
  const [sponsoredVendors, setSponsoredVendors] = useState<SponsoredVendor[]>([]);
  const [vendorStats, setVendorStats] = useState<Record<string, AdStats | null>>({});

  // Mock data for leads and billing (would come from real API in production)
  const mockLeads: Lead[] = useMemo(
    () => [
      {
        id: '1',
        plannerName: 'Sarah Johnson',
        weddingDate: '2024-06-15',
        status: 'new',
        source: 'Ad Click',
        timestamp: '2024-03-10T14:30:00Z',
      },
      {
        id: '2',
        plannerName: 'Emily Chen',
        weddingDate: '2024-07-20',
        status: 'contacted',
        source: 'Ad Click',
        timestamp: '2024-03-09T09:15:00Z',
      },
      {
        id: '3',
        plannerName: 'Jessica Martinez',
        weddingDate: '2024-05-10',
        status: 'converted',
        source: 'Quote Request',
        timestamp: '2024-03-08T16:45:00Z',
      },
      {
        id: '4',
        plannerName: 'Amanda Williams',
        weddingDate: '2024-08-30',
        status: 'new',
        source: 'Ad Click',
        timestamp: '2024-03-07T11:20:00Z',
      },
      {
        id: '5',
        plannerName: 'Rachel Brown',
        weddingDate: '2024-09-12',
        status: 'contacted',
        source: 'Message',
        timestamp: '2024-03-06T13:50:00Z',
      },
    ],
    []
  );

  const mockCurrentSpend = 245.50;
  const mockMonthlyBudget = 1000;
  const mockUpcomingInvoice = 315.75;
  const mockSpendHistory = [
    { date: '2024-03-01', amount: 289.50 },
    { date: '2024-02-01', amount: 412.30 },
    { date: '2024-01-01', amount: 356.75 },
  ];

  // Authentication check
  useEffect(() => {
    if (!token) {
      router.push('/admin/login');
      return;
    }

    if (!userProfile?.is_vendor) {
      router.push('/admin');
      return;
    }

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        const vendors = await getSponsoredVendors(token, { limit: 50 });
        setSponsoredVendors(vendors);

        // Fetch stats for each vendor
        const statsMap: Record<string, AdStats | null> = {};
        for (const vendor of vendors) {
          try {
            const stats = await getAdStats(token, vendor._id, 30);
            statsMap[vendor._id] = stats;
          } catch (err) {
            statsMap[vendor._id] = null;
          }
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

  // Calculate performance metrics
  const metrics: PerformanceMetrics = useMemo(() => {
    const totalImpressions = Object.values(vendorStats).reduce(
      (sum, stats) => sum + (stats?.total_impressions ?? 0),
      0
    );
    const totalClicks = Object.values(vendorStats).reduce(
      (sum, stats) => sum + (stats?.total_clicks ?? 0),
      0
    );
    const ctr = totalImpressions > 0 ? ((totalClicks / totalImpressions) * 100).toFixed(2) : '0.00';

    return {
      totalImpressions,
      totalClicks,
      ctr: parseFloat(ctr),
      activeCampaigns: sponsoredVendors.filter((v) => v.is_active).length,
      totalLeads: mockLeads.length,
      totalSpend: mockCurrentSpend,
    };
  }, [vendorStats, sponsoredVendors, mockLeads]);

  const getStatusBadgeColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-emerald-100/50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300';
      case 'paused':
        return 'bg-yellow-100/50 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300';
      case 'ended':
        return 'bg-slate-100/50 text-slate-700 dark:bg-slate-900/30 dark:text-slate-300';
      case 'new':
        return 'bg-blue-100/50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300';
      case 'contacted':
        return 'bg-purple-100/50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300';
      case 'converted':
        return 'bg-emerald-100/50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300';
      case 'lost':
        return 'bg-red-100/50 text-red-700 dark:bg-red-900/30 dark:text-red-300';
      default:
        return 'bg-slate-100/50 text-slate-700 dark:bg-slate-900/30 dark:text-slate-300';
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(value);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Activity className="w-8 h-8 animate-spin mx-auto mb-3 text-wedding-rose" />
          <p className="text-slate-600 dark:text-slate-400">Loading your advertising dashboard...</p>
        </div>
      </div>
    );
  }

  if (error && sponsoredVendors.length === 0) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 dark:border-red-900/30 dark:bg-red-900/10 p-6">
        <h3 className="font-semibold text-red-900 dark:text-red-200">Error loading data</h3>
        <p className="text-sm text-red-700 dark:text-red-300 mt-1">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Tab Navigation */}
      <div className="flex gap-2 border-b border-slate-200 dark:border-slate-700">
        {(['overview', 'campaigns', 'leads', 'billing'] as const).map((tabId) => (
          <button
            key={tabId}
            onClick={() => setActiveTab(tabId)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tabId
                ? 'border-wedding-rose text-wedding-rose'
                : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
          >
            {tabId.charAt(0).toUpperCase() + tabId.slice(1)}
          </button>
        ))}
      </div>

      {/* OVERVIEW TAB */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Performance Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                    Total Impressions
                  </p>
                  <p className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
                    {metrics.totalImpressions.toLocaleString()}
                  </p>
                </div>
                <BarChart3 className="w-8 h-8 text-wedding-rose/30" />
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                    Total Clicks
                  </p>
                  <p className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
                    {metrics.totalClicks.toLocaleString()}
                  </p>
                </div>
                <MousePointerClick className="w-8 h-8 text-wedding-gold/30" />
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                    Click-Through Rate
                  </p>
                  <p className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
                    {metrics.ctr.toFixed(2)}%
                  </p>
                </div>
                <TrendingUp className="w-8 h-8 text-wedding-sage/30" />
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                    Active Campaigns
                  </p>
                  <p className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
                    {metrics.activeCampaigns}
                  </p>
                </div>
                <Activity className="w-8 h-8 text-wedding-navy/30" />
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                    Total Leads
                  </p>
                  <p className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
                    {metrics.totalLeads}
                  </p>
                </div>
                <Users className="w-8 h-8 text-wedding-rose/30" />
              </div>
            </div>
          </div>

          {/* Chart Placeholder */}
          <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 p-6">
            <h3 className="font-semibold text-slate-900 dark:text-white mb-4">Performance Trend</h3>
            <div className="h-64 flex items-center justify-center bg-slate-50 dark:bg-slate-700/30 rounded text-slate-500 dark:text-slate-400">
              <p className="text-sm">30-day performance chart placeholder</p>
            </div>
          </div>
        </div>
      )}

      {/* CAMPAIGNS TAB */}
      {activeTab === 'campaigns' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <Link
              href="/admin/vendor/ads/campaigns/new"
              className="inline-flex items-center gap-2 rounded-lg bg-wedding-rose text-white px-4 py-2 text-sm font-medium hover:bg-wedding-rose/90 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Create Campaign
            </Link>
          </div>

          {sponsoredVendors.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-slate-800/30 p-8 text-center">
              <Calendar className="w-10 h-10 text-slate-400 mx-auto mb-3" />
              <h3 className="font-semibold text-slate-900 dark:text-white">No campaigns yet</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                Create your first campaign to start reaching planners
              </p>
              <Link
                href="/admin/vendor/ads/campaigns/new"
                className="inline-flex items-center gap-2 rounded-lg bg-wedding-rose text-white px-4 py-2 text-sm font-medium hover:bg-wedding-rose/90 transition-colors mt-4"
              >
                <Plus className="w-4 h-4" />
                Create Campaign
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-slate-200 dark:border-slate-700">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold text-slate-900 dark:text-white">Campaign</th>
                    <th className="px-4 py-3 text-left font-semibold text-slate-900 dark:text-white">Status</th>
                    <th className="px-4 py-3 text-left font-semibold text-slate-900 dark:text-white">Placement</th>
                    <th className="px-4 py-3 text-right font-semibold text-slate-900 dark:text-white">Impressions</th>
                    <th className="px-4 py-3 text-right font-semibold text-slate-900 dark:text-white">Clicks</th>
                    <th className="px-4 py-3 text-right font-semibold text-slate-900 dark:text-white">CTR</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                  {sponsoredVendors.map((vendor) => {
                    const stats = vendorStats[vendor._id];
                    const ctr = stats && stats.total_impressions > 0
                      ? ((stats.total_clicks / stats.total_impressions) * 100).toFixed(2)
                      : '0.00';
                    return (
                      <tr key={vendor._id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                        <td className="px-4 py-3">
                          <p className="font-medium text-slate-900 dark:text-white">
                            {vendor.headline || 'Untitled Campaign'}
                          </p>
                          <p className="text-xs text-slate-500 dark:text-slate-400">ID: {vendor._id.slice(0, 8)}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex px-2 py-1 rounded text-xs font-medium ${getStatusBadgeColor(vendor.is_active ? 'active' : 'paused')}`}>
                            {vendor.is_active ? 'Active' : 'Paused'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                          {getAdPlacementLabel(vendor.placement)}
                        </td>
                        <td className="px-4 py-3 text-right text-slate-900 dark:text-white">
                          {stats?.total_impressions.toLocaleString() || '0'}
                        </td>
                        <td className="px-4 py-3 text-right text-slate-900 dark:text-white">
                          {stats?.total_clicks.toLocaleString() || '0'}
                        </td>
                        <td className="px-4 py-3 text-right text-slate-900 dark:text-white font-medium">
                          {ctr}%
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* LEADS TAB */}
      {activeTab === 'leads' && (
        <div className="space-y-4">
          {mockLeads.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-slate-800/30 p-8 text-center">
              <MessageSquare className="w-10 h-10 text-slate-400 mx-auto mb-3" />
              <h3 className="font-semibold text-slate-900 dark:text-white">No leads yet</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                Your leads from planner interactions will appear here
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-slate-200 dark:border-slate-700">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold text-slate-900 dark:text-white">Planner</th>
                    <th className="px-4 py-3 text-left font-semibold text-slate-900 dark:text-white">Wedding Date</th>
                    <th className="px-4 py-3 text-left font-semibold text-slate-900 dark:text-white">Source</th>
                    <th className="px-4 py-3 text-left font-semibold text-slate-900 dark:text-white">Status</th>
                    <th className="px-4 py-3 text-left font-semibold text-slate-900 dark:text-white">Date Received</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                  {mockLeads.map((lead) => (
                    <tr key={lead.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                      <td className="px-4 py-3 font-medium text-slate-900 dark:text-white">
                        {lead.plannerName}
                      </td>
                      <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                        {formatDate(lead.weddingDate)}
                      </td>
                      <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                        {lead.source}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-1 rounded text-xs font-medium ${getStatusBadgeColor(lead.status)}`}>
                          {lead.status.charAt(0).toUpperCase() + lead.status.slice(1)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                        {formatDate(lead.timestamp)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* BILLING TAB */}
      {activeTab === 'billing' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Current Spend */}
          <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-slate-900 dark:text-white">Current Spend</h3>
              <DollarSign className="w-5 h-5 text-wedding-gold" />
            </div>
            <p className="text-3xl font-bold text-slate-900 dark:text-white">
              {formatCurrency(mockCurrentSpend)}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
              of {formatCurrency(mockMonthlyBudget)} monthly budget
            </p>
            <div className="mt-4 w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
              <div
                className="bg-wedding-gold h-2 rounded-full"
                style={{ width: `${(mockCurrentSpend / mockMonthlyBudget) * 100}%` }}
              />
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
              {((mockCurrentSpend / mockMonthlyBudget) * 100).toFixed(1)}% of monthly budget used
            </p>
          </div>

          {/* Upcoming Invoice */}
          <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-slate-900 dark:text-white">Upcoming Invoice</h3>
              <Calendar className="w-5 h-5 text-wedding-rose" />
            </div>
            <p className="text-3xl font-bold text-slate-900 dark:text-white">
              {formatCurrency(mockUpcomingInvoice)}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
              Due April 1, 2024
            </p>
            <button className="mt-4 w-full rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700/50 px-3 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 transition-colors">
              View Invoice
            </button>
          </div>

          {/* Payment Method */}
          <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-slate-900 dark:text-white">Payment Method</h3>
            </div>
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-6 bg-slate-300 dark:bg-slate-600 rounded flex items-center justify-center">
                  <span className="text-xs font-bold text-slate-600 dark:text-slate-300">CARD</span>
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-900 dark:text-white">Visa ending in 4242</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">Expires 12/2026</p>
                </div>
              </div>
              <button className="w-full rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700/50 px-3 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 transition-colors">
                Update Payment Method
              </button>
            </div>
          </div>

          {/* Spend History */}
          <div className="lg:col-span-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 p-6">
            <h3 className="font-semibold text-slate-900 dark:text-white mb-4">Spend History</h3>
            <div className="space-y-2">
              {mockSpendHistory.map((item) => (
                <div key={item.date} className="flex items-center justify-between py-3 border-b border-slate-100 dark:border-slate-700/50 last:border-b-0">
                  <p className="text-sm text-slate-600 dark:text-slate-400">
                    {formatDate(item.date)}
                  </p>
                  <p className="text-sm font-medium text-slate-900 dark:text-white">
                    {formatCurrency(item.amount)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
