'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter } from 'next/navigation';
import PageHeader from '../components/PageHeader';
import { toast } from 'sonner';
import {
  getSponsoredVendors,
  createSponsoredVendor,
  updateSponsoredVendor,
  deleteSponsoredVendor,
  getAdStats,
  getAdPlacementLabel,
  getDashboardStats,
  getVendorLeaderboard,
  triggerRollup,
  type SponsoredVendor,
  type AdStats,
  type AdPlacement,
  type CreateSponsoredVendorRequest,
  type DashboardStats,
  type VendorLeaderboardEntry,
} from '@/services/advertisingApi';
import { getVendorDirectory, type VendorProfile } from '@/services/vendorManagementApi';
import {
  Trash2,
  Plus,
  Eye,
  EyeOff,
  TrendingUp,
  TrendingDown,
  Users,
  MousePointerClick,
  Activity,
  BarChart3,
  Target,
  Clock,
  RefreshCw,
  ArrowUpRight,
  Zap,
} from 'lucide-react';

type TabId = 'vendors' | 'analytics';

interface DateRange {
  label: string;
  days: number;
}

export default function AdvertisingPage() {
  const { token, userProfile } = useAdmin();
  const router = useRouter();

  // Tab state
  const [activeTab, setActiveTab] = useState<TabId>('vendors');

  // Loading state
  const [loading, setLoading] = useState(true);
  const [vendorActionLoading, setVendorActionLoading] = useState<string | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [rollupLoading, setRollupLoading] = useState(false);

  // Data state
  const [sponsoredVendors, setSponsoredVendors] = useState<SponsoredVendor[]>([]);
  const [allVendors, setAllVendors] = useState<VendorProfile[]>([]);
  const [vendorStats, setVendorStats] = useState<Record<string, AdStats | null>>({});
  const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(null);
  const [leaderboard, setLeaderboard] = useState<VendorLeaderboardEntry[]>([]);

  // UI state
  const [showAddVendor, setShowAddVendor] = useState(false);
  const [editingVendorId, setEditingVendorId] = useState<string | null>(null);
  const [selectedDateRange, setSelectedDateRange] = useState<DateRange>({ label: '30d', days: 30 });

  // Form state for adding/editing vendor
  const [formData, setFormData] = useState<CreateSponsoredVendorRequest>({
    vendor_profile_id: '',
    placement: 'vendor_rail',
    priority: 1,
    headline: '',
    description: '',
    is_active: true,
    target_categories: [],
    target_wedding_stages: [],
  });

  // Check authentication
  useEffect(() => {
    if (!token) {
      router.push('/admin/login');
    }
  }, [token, router]);

  // Fetch vendor data (for vendors tab)
  const fetchVendorData = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    try {
      const [vendorsData, allVendorsData] = await Promise.all([
        getSponsoredVendors(token),
        getVendorDirectory(token, { limit: 100 }),
      ]);

      setSponsoredVendors(vendorsData);
      setAllVendors(allVendorsData);

      // Fetch stats for all vendors
      const statsMap: Record<string, AdStats | null> = {};
      for (const vendor of vendorsData) {
        try {
          const stats = await getAdStats(token, vendor._id, selectedDateRange.days);
          statsMap[vendor._id] = stats;
        } catch (error) {
          console.error(`Failed to fetch stats for vendor ${vendor._id}:`, error);
          statsMap[vendor._id] = null;
        }
      }
      setVendorStats(statsMap);
    } catch (error) {
      toast.error('Failed to load advertising data');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [token, selectedDateRange.days]);

  // Fetch dashboard data (for analytics tab)
  const fetchDashboardData = useCallback(async () => {
    if (!token) return;

    setDashboardLoading(true);
    try {
      const [stats, leaders] = await Promise.all([
        getDashboardStats(token, { days: selectedDateRange.days }),
        getVendorLeaderboard(token, { days: selectedDateRange.days, limit: 20 }),
      ]);

      setDashboardStats(stats);
      setLeaderboard(leaders);
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
      // Don't toast error for dashboard — gracefully show empty state
    } finally {
      setDashboardLoading(false);
    }
  }, [token, selectedDateRange.days]);

  // Initial data load
  useEffect(() => {
    if (token) {
      fetchVendorData();
    }
  }, [token]);

  // Load dashboard data when analytics tab is activated or date range changes
  useEffect(() => {
    if (token && activeTab === 'analytics') {
      fetchDashboardData();
    }
  }, [token, activeTab, selectedDateRange]);

  // Trigger manual rollup
  const handleTriggerRollup = async () => {
    if (!token) return;

    setRollupLoading(true);
    try {
      const result = await triggerRollup(token);
      toast.success(`Rollup complete: ${result.documents_upserted} stats updated`);
      // Refresh dashboard after rollup
      await fetchDashboardData();
    } catch (error) {
      toast.error('Failed to trigger rollup');
      console.error(error);
    } finally {
      setRollupLoading(false);
    }
  };

  // Add new sponsored vendor
  const handleAddVendor = async () => {
    if (!token || !formData.vendor_profile_id) {
      toast.error('Please select a vendor');
      return;
    }

    setVendorActionLoading('add');
    try {
      const newVendor = await createSponsoredVendor(token, formData);
      setSponsoredVendors([...sponsoredVendors, newVendor]);
      setShowAddVendor(false);
      resetForm();
      toast.success('Sponsored vendor added');
    } catch (error) {
      toast.error('Failed to add sponsored vendor');
      console.error(error);
    } finally {
      setVendorActionLoading(null);
    }
  };

  // Update vendor priority
  const handleUpdatePriority = async (vendorId: string, newPriority: number) => {
    if (!token) return;

    setVendorActionLoading(vendorId);
    try {
      const updated = await updateSponsoredVendor(token, vendorId, { priority: newPriority });
      setSponsoredVendors(sponsoredVendors.map((v) => (v._id === vendorId ? updated : v)));
      toast.success('Priority updated');
    } catch (error) {
      toast.error('Failed to update priority');
      console.error(error);
    } finally {
      setVendorActionLoading(null);
    }
  };

  // Toggle vendor active status
  const handleToggleVendorStatus = async (vendor: SponsoredVendor) => {
    if (!token) return;

    setVendorActionLoading(vendor._id);
    try {
      const updated = await updateSponsoredVendor(token, vendor._id, { is_active: !vendor.is_active });
      setSponsoredVendors(sponsoredVendors.map((v) => (v._id === vendor._id ? updated : v)));
      toast.success(updated.is_active ? 'Vendor activated' : 'Vendor deactivated');
    } catch (error) {
      toast.error('Failed to update vendor status');
      console.error(error);
    } finally {
      setVendorActionLoading(null);
    }
  };

  // Delete vendor
  const handleDeleteVendor = async (vendorId: string) => {
    if (!confirm('Are you sure you want to delete this sponsored vendor?')) return;

    if (!token) return;

    setVendorActionLoading(vendorId);
    try {
      await deleteSponsoredVendor(token, vendorId);
      setSponsoredVendors(sponsoredVendors.filter((v) => v._id !== vendorId));
      const newStats = { ...vendorStats };
      delete newStats[vendorId];
      setVendorStats(newStats);
      toast.success('Sponsored vendor deleted');
    } catch (error) {
      toast.error('Failed to delete sponsored vendor');
      console.error(error);
    } finally {
      setVendorActionLoading(null);
    }
  };

  // Reset form
  const resetForm = () => {
    setFormData({
      vendor_profile_id: '',
      placement: 'vendor_rail',
      priority: 1,
      headline: '',
      description: '',
      is_active: true,
      target_categories: [],
      target_wedding_stages: [],
    });
    setEditingVendorId(null);
  };

  // Get vendor name by ID
  const getVendorName = (vendorId: string) => {
    return allVendors.find((v) => v._id === vendorId)?.business_name || vendorId;
  };

  // Format large numbers
  const formatNumber = (num: number): string => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toLocaleString();
  };

  // Compute hourly heatmap data
  const hourlyHeatmapData = useMemo(() => {
    if (!dashboardStats?.hourly_clicks) return [];
    const clicks = dashboardStats.hourly_clicks;
    const maxClicks = Math.max(...clicks, 1);
    return clicks.map((count, hour) => ({
      hour,
      count,
      intensity: count / maxClicks,
      label: `${hour.toString().padStart(2, '0')}:00`,
    }));
  }, [dashboardStats?.hourly_clicks]);

  // Compute lead funnel data
  const leadFunnelData = useMemo(() => {
    if (!dashboardStats?.leads_by_status) return [];
    const statusOrder = ['pending', 'contacted', 'responded', 'converted', 'closed'];
    const statusLabels: Record<string, string> = {
      pending: 'Pending',
      contacted: 'Contacted',
      responded: 'Responded',
      converted: 'Converted',
      closed: 'Closed',
    };
    const statusColors: Record<string, string> = {
      pending: 'bg-yellow-500',
      contacted: 'bg-blue-500',
      responded: 'bg-indigo-500',
      converted: 'bg-green-500',
      closed: 'bg-slate-400',
    };
    return statusOrder.map((status) => ({
      status,
      label: statusLabels[status] || status,
      count: dashboardStats.leads_by_status[status] || 0,
      color: statusColors[status] || 'bg-slate-400',
    }));
  }, [dashboardStats?.leads_by_status]);

  // Tabs configuration
  const tabs = [
    {
      id: 'vendors' as TabId,
      label: 'Sponsored Vendors',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
          />
        </svg>
      ),
    },
    {
      id: 'analytics' as TabId,
      label: 'Analytics Dashboard',
      icon: <BarChart3 className="w-5 h-5" />,
    },
  ];

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Advertising Management"
          description="Manage sponsored vendors and ad analytics"
        />
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-8 text-center">
          <div className="inline-block">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-wedding-rose"></div>
          </div>
          <p className="mt-4 text-slate-600 dark:text-slate-400">Loading advertising data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Advertising Management"
        description="Manage sponsored vendors and ad analytics"
      />

      {/* Tabs */}
      <div className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
        <div className="border-b border-gray-200 dark:border-gray-700">
          <nav className="flex -mb-px overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-6 py-4 border-b-2 font-medium text-sm whitespace-nowrap transition-colors ${
                  activeTab === tab.id
                    ? 'border-wedding-rose text-wedding-rose'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Sponsored Vendors Tab */}
      {activeTab === 'vendors' && (
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-bold text-slate-900 dark:text-white">Sponsored Vendors</h2>
              <button
                onClick={() => {
                  resetForm();
                  setShowAddVendor(true);
                }}
                className="flex items-center gap-2 px-4 py-2 bg-wedding-rose text-white rounded-lg hover:bg-wedding-rose/90 transition-colors font-medium"
              >
                <Plus className="w-4 h-4" />
                Add Sponsored Vendor
              </button>
            </div>

            {/* Add/Edit Vendor Form */}
            {showAddVendor && (
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-6 border border-slate-200 dark:border-slate-700 space-y-4">
                <h3 className="font-semibold text-slate-900 dark:text-white">Add Sponsored Vendor</h3>

                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Vendor
                  </label>
                  <select
                    value={formData.vendor_profile_id}
                    onChange={(e) => setFormData({ ...formData, vendor_profile_id: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  >
                    <option value="">Select a vendor...</option>
                    {allVendors.map((vendor) => (
                      <option key={vendor._id} value={vendor._id}>
                        {vendor.business_name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Placement
                    </label>
                    <select
                      value={formData.placement}
                      onChange={(e) =>
                        setFormData({ ...formData, placement: e.target.value as AdPlacement })
                      }
                      className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    >
                      <option value="vendor_rail">Vendor Rail</option>
                      <option value="vendor_detail">Vendor Detail</option>
                      <option value="milestone_module">Milestone Module</option>
                      <option value="directory_boost">Directory Boost</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Priority
                    </label>
                    <input
                      type="number"
                      min="1"
                      value={formData.priority}
                      onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) })}
                      className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Headline (optional)
                  </label>
                  <input
                    type="text"
                    value={formData.headline}
                    onChange={(e) => setFormData({ ...formData, headline: e.target.value })}
                    placeholder="e.g., Featured Photographer"
                    className="w-full px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  />
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={handleAddVendor}
                    disabled={vendorActionLoading === 'add'}
                    className="flex-1 px-4 py-2 bg-wedding-rose text-white rounded-lg hover:bg-wedding-rose/90 transition-colors disabled:opacity-50 font-medium"
                  >
                    {vendorActionLoading === 'add' ? 'Adding...' : 'Add Vendor'}
                  </button>
                  <button
                    onClick={() => {
                      setShowAddVendor(false);
                      resetForm();
                    }}
                    className="flex-1 px-4 py-2 bg-slate-300 dark:bg-slate-600 text-slate-900 dark:text-white rounded-lg hover:bg-slate-400 dark:hover:bg-slate-500 transition-colors font-medium"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {/* Vendors Table */}
            {sponsoredVendors.length === 0 ? (
              <div className="text-center py-12">
                <TrendingUp className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                <p className="text-slate-600 dark:text-slate-400 font-medium">No sponsored vendors yet</p>
                <p className="text-sm text-slate-500 dark:text-slate-500 mt-1">
                  Add your first sponsored vendor to get started
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">Vendor Name</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">Placement</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">Priority</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">Impressions</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">Clicks</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">CTR</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sponsoredVendors.map((vendor) => {
                      const stats = vendorStats[vendor._id];
                      return (
                        <tr key={vendor._id} className="border-b border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                          <td className="px-4 py-3 text-sm font-medium text-slate-900 dark:text-white">
                            {getVendorName(vendor.vendor_profile_id)}
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">
                            {getAdPlacementLabel(vendor.placement)}
                          </td>
                          <td className="px-4 py-3 text-sm">
                            <input
                              type="number"
                              min="1"
                              value={vendor.priority}
                              onChange={(e) => handleUpdatePriority(vendor._id, parseInt(e.target.value))}
                              disabled={vendorActionLoading === vendor._id}
                              className="w-16 px-2 py-1 border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-700 text-slate-900 dark:text-white text-sm focus:ring-2 focus:ring-wedding-rose focus:border-transparent disabled:opacity-50"
                            />
                          </td>
                          <td className="px-4 py-3 text-sm">
                            <span className={`px-2 py-1 rounded-full text-xs font-semibold ${vendor.is_active ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300' : 'bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-300'}`}>
                              {vendor.is_active ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">{stats?.total_impressions ?? 0}</td>
                          <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">{stats?.total_clicks ?? 0}</td>
                          <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">{stats ? `${(stats.ctr * 100).toFixed(2)}%` : '-'}</td>
                          <td className="px-4 py-3 text-sm space-x-2">
                            <button onClick={() => handleToggleVendorStatus(vendor)} disabled={vendorActionLoading === vendor._id} className="inline-flex items-center gap-1 px-3 py-1 rounded bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 transition-colors disabled:opacity-50">
                              {vendor.is_active ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                            <button onClick={() => handleDeleteVendor(vendor._id)} disabled={vendorActionLoading === vendor._id} className="inline-flex items-center gap-1 px-3 py-1 rounded bg-red-100 hover:bg-red-200 dark:bg-red-900/30 dark:hover:bg-red-900/50 text-red-700 dark:text-red-300 transition-colors disabled:opacity-50">
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Analytics Dashboard Tab */}
      {activeTab === 'analytics' && (
        <div className="space-y-6">
          {/* Date Range & Actions Bar */}
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-4 flex flex-wrap items-center justify-between gap-4">
            <div className="flex gap-2">
              {[
                { label: '7 days', days: 7 },
                { label: '14 days', days: 14 },
                { label: '30 days', days: 30 },
                { label: '90 days', days: 90 },
              ].map((range) => (
                <button
                  key={range.days}
                  onClick={() => setSelectedDateRange({ label: `${range.days}d`, days: range.days })}
                  className={`px-4 py-2 rounded-lg transition-colors font-medium text-sm ${
                    selectedDateRange.days === range.days
                      ? 'bg-wedding-rose text-white'
                      : 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600'
                  }`}
                >
                  {range.label}
                </button>
              ))}
            </div>

            <button
              onClick={handleTriggerRollup}
              disabled={rollupLoading}
              className="flex items-center gap-2 px-4 py-2 bg-slate-900 dark:bg-slate-700 text-white rounded-lg hover:bg-slate-800 dark:hover:bg-slate-600 transition-colors font-medium text-sm disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${rollupLoading ? 'animate-spin' : ''}`} />
              {rollupLoading ? 'Computing...' : 'Refresh Rollup'}
            </button>
          </div>

          {dashboardLoading ? (
            <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-12 text-center">
              <div className="inline-block">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-wedding-rose"></div>
              </div>
              <p className="mt-4 text-slate-600 dark:text-slate-400">Loading analytics...</p>
            </div>
          ) : !dashboardStats ? (
            <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-12 text-center">
              <BarChart3 className="w-16 h-16 text-slate-300 mx-auto mb-4" />
              <p className="text-lg font-semibold text-slate-700 dark:text-slate-300">No analytics data yet</p>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-2 max-w-md mx-auto">
                Once ad events start collecting, click &quot;Refresh Rollup&quot; to compute the daily aggregations for the dashboard.
              </p>
            </div>
          ) : (
            <>
              {/* KPI Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                <div className="bg-white dark:bg-slate-800 rounded-xl p-5 shadow-lg border border-slate-200 dark:border-slate-700">
                  <div className="flex items-center gap-2 mb-1">
                    <Eye className="w-4 h-4 text-blue-600" />
                    <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Impressions</span>
                  </div>
                  <div className="text-2xl font-bold text-slate-900 dark:text-white">
                    {formatNumber(dashboardStats.totals.impressions)}
                  </div>
                </div>

                <div className="bg-white dark:bg-slate-800 rounded-xl p-5 shadow-lg border border-slate-200 dark:border-slate-700">
                  <div className="flex items-center gap-2 mb-1">
                    <MousePointerClick className="w-4 h-4 text-green-600" />
                    <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Clicks</span>
                  </div>
                  <div className="text-2xl font-bold text-slate-900 dark:text-white">
                    {formatNumber(dashboardStats.totals.clicks)}
                  </div>
                </div>

                <div className="bg-white dark:bg-slate-800 rounded-xl p-5 shadow-lg border border-slate-200 dark:border-slate-700">
                  <div className="flex items-center gap-2 mb-1">
                    <Activity className="w-4 h-4 text-purple-600" />
                    <span className="text-xs font-medium text-slate-500 dark:text-slate-400">CTR</span>
                  </div>
                  <div className="text-2xl font-bold text-slate-900 dark:text-white">
                    {dashboardStats.totals.ctr}%
                  </div>
                </div>

                <div className="bg-white dark:bg-slate-800 rounded-xl p-5 shadow-lg border border-slate-200 dark:border-slate-700">
                  <div className="flex items-center gap-2 mb-1">
                    <Target className="w-4 h-4 text-orange-600" />
                    <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Leads</span>
                  </div>
                  <div className="text-2xl font-bold text-slate-900 dark:text-white">
                    {formatNumber(dashboardStats.totals.leads)}
                  </div>
                </div>

                <div className="bg-white dark:bg-slate-800 rounded-xl p-5 shadow-lg border border-slate-200 dark:border-slate-700">
                  <div className="flex items-center gap-2 mb-1">
                    <Zap className="w-4 h-4 text-emerald-600" />
                    <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Conversions</span>
                  </div>
                  <div className="text-2xl font-bold text-slate-900 dark:text-white">
                    {formatNumber(dashboardStats.totals.conversions)}
                  </div>
                </div>

                <div className="bg-white dark:bg-slate-800 rounded-xl p-5 shadow-lg border border-slate-200 dark:border-slate-700">
                  <div className="flex items-center gap-2 mb-1">
                    <Users className="w-4 h-4 text-indigo-600" />
                    <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Unique Planners</span>
                  </div>
                  <div className="text-2xl font-bold text-slate-900 dark:text-white">
                    {formatNumber(dashboardStats.totals.unique_planners)}
                  </div>
                </div>
              </div>

              {/* Daily Trend Chart (CSS bar chart) */}
              {dashboardStats.daily_series.length > 0 && (
                <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Daily Performance Trend</h3>
                  <div className="overflow-x-auto">
                    <div className="flex items-end gap-1 min-w-[600px]" style={{ height: '200px' }}>
                      {dashboardStats.daily_series.map((day, idx) => {
                        const maxImpressions = Math.max(...dashboardStats.daily_series.map((d) => d.impressions), 1);
                        const barHeight = Math.max((day.impressions / maxImpressions) * 180, 2);
                        const clickBarHeight = Math.max((day.clicks / maxImpressions) * 180, 0);
                        return (
                          <div key={day.date} className="flex-1 flex flex-col items-center gap-0.5 group relative" title={`${day.date}\nImpressions: ${day.impressions}\nClicks: ${day.clicks}\nCTR: ${day.ctr}%`}>
                            <div className="w-full flex flex-col items-center justify-end" style={{ height: '180px' }}>
                              <div
                                className="w-full bg-blue-200 dark:bg-blue-900/40 rounded-t relative overflow-hidden transition-all group-hover:bg-blue-300 dark:group-hover:bg-blue-900/60"
                                style={{ height: `${barHeight}px` }}
                              >
                                <div
                                  className="absolute bottom-0 w-full bg-blue-500 dark:bg-blue-400 rounded-t"
                                  style={{ height: `${clickBarHeight}px` }}
                                />
                              </div>
                            </div>
                            {idx % Math.ceil(dashboardStats.daily_series.length / 10) === 0 && (
                              <span className="text-[9px] text-slate-400 whitespace-nowrap mt-1">
                                {day.date.slice(5)}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <div className="flex items-center gap-6 mt-3 text-xs text-slate-500 dark:text-slate-400">
                    <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-blue-200 dark:bg-blue-900/40 inline-block"></span> Impressions</span>
                    <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-blue-500 dark:bg-blue-400 inline-block"></span> Clicks</span>
                  </div>
                </div>
              )}

              {/* Two-column layout: Lead Funnel + Hourly Heatmap */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Lead Funnel */}
                <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Lead Funnel</h3>
                  {leadFunnelData.length === 0 || leadFunnelData.every((d) => d.count === 0) ? (
                    <p className="text-sm text-slate-500 dark:text-slate-400 text-center py-8">No lead data yet</p>
                  ) : (
                    <div className="space-y-3">
                      {leadFunnelData.map((item) => {
                        const maxCount = Math.max(...leadFunnelData.map((d) => d.count), 1);
                        const widthPercent = (item.count / maxCount) * 100;
                        return (
                          <div key={item.status}>
                            <div className="flex justify-between text-sm mb-1">
                              <span className="font-medium text-slate-700 dark:text-slate-300">{item.label}</span>
                              <span className="text-slate-600 dark:text-slate-400">{item.count}</span>
                            </div>
                            <div className="h-6 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                              <div
                                className={`h-full ${item.color} rounded-full transition-all duration-500`}
                                style={{ width: `${widthPercent}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Lead Types Breakdown */}
                  {dashboardStats.leads_by_type && Object.keys(dashboardStats.leads_by_type).length > 0 && (
                    <div className="mt-6 pt-4 border-t border-slate-200 dark:border-slate-700">
                      <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3">Lead Types</h4>
                      <div className="grid grid-cols-2 gap-3">
                        {Object.entries(dashboardStats.leads_by_type).map(([type, count]) => (
                          <div key={type} className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3">
                            <span className="text-xs text-slate-500 dark:text-slate-400 capitalize">{type.replace(/_/g, ' ')}</span>
                            <p className="text-lg font-bold text-slate-900 dark:text-white">{count}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Hourly Click Heatmap */}
                <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Hourly Click Activity</h3>
                  {hourlyHeatmapData.every((d) => d.count === 0) ? (
                    <p className="text-sm text-slate-500 dark:text-slate-400 text-center py-8">No click data yet</p>
                  ) : (
                    <>
                      <div className="grid grid-cols-6 gap-2">
                        {hourlyHeatmapData.map((cell) => (
                          <div
                            key={cell.hour}
                            className="aspect-square rounded-lg flex flex-col items-center justify-center text-xs transition-all hover:scale-105"
                            style={{
                              backgroundColor: cell.intensity > 0
                                ? `rgba(59, 130, 246, ${0.1 + cell.intensity * 0.8})`
                                : 'rgb(241, 245, 249)',
                            }}
                            title={`${cell.label}: ${cell.count} clicks`}
                          >
                            <span className={`font-medium ${cell.intensity > 0.5 ? 'text-white' : 'text-slate-600 dark:text-slate-400'}`}>
                              {cell.label.slice(0, 2)}
                            </span>
                            <span className={`text-[10px] ${cell.intensity > 0.5 ? 'text-blue-100' : 'text-slate-400'}`}>
                              {cell.count}
                            </span>
                          </div>
                        ))}
                      </div>
                      <div className="flex items-center gap-2 mt-4 text-xs text-slate-500">
                        <span>Low</span>
                        <div className="flex gap-0.5">
                          {[0.1, 0.3, 0.5, 0.7, 0.9].map((opacity) => (
                            <div
                              key={opacity}
                              className="w-4 h-3 rounded"
                              style={{ backgroundColor: `rgba(59, 130, 246, ${opacity})` }}
                            />
                          ))}
                        </div>
                        <span>High</span>
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* Vendor Leaderboard */}
              {leaderboard.length > 0 && (
                <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Vendor Performance Leaderboard</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">#</th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">Vendor</th>
                          <th className="px-4 py-3 text-right text-xs font-semibold text-slate-700 dark:text-slate-300">Impressions</th>
                          <th className="px-4 py-3 text-right text-xs font-semibold text-slate-700 dark:text-slate-300">Clicks</th>
                          <th className="px-4 py-3 text-right text-xs font-semibold text-slate-700 dark:text-slate-300">CTR</th>
                          <th className="px-4 py-3 text-right text-xs font-semibold text-slate-700 dark:text-slate-300">Leads</th>
                          <th className="px-4 py-3 text-right text-xs font-semibold text-slate-700 dark:text-slate-300">Conversions</th>
                          <th className="px-4 py-3 text-right text-xs font-semibold text-slate-700 dark:text-slate-300">Unique Planners</th>
                          <th className="px-4 py-3 text-right text-xs font-semibold text-slate-700 dark:text-slate-300">Days Active</th>
                        </tr>
                      </thead>
                      <tbody>
                        {leaderboard.map((entry, idx) => (
                          <tr key={entry.sponsored_vendor_id} className="border-b border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                            <td className="px-4 py-3 text-sm font-bold text-slate-500 dark:text-slate-400">
                              {idx + 1}
                            </td>
                            <td className="px-4 py-3 text-sm font-medium text-slate-900 dark:text-white">
                              {getVendorName(entry.vendor_profile_id)}
                            </td>
                            <td className="px-4 py-3 text-sm text-right text-slate-600 dark:text-slate-400">
                              {entry.total_impressions.toLocaleString()}
                            </td>
                            <td className="px-4 py-3 text-sm text-right text-slate-600 dark:text-slate-400">
                              {entry.total_clicks.toLocaleString()}
                            </td>
                            <td className="px-4 py-3 text-sm text-right">
                              <span className={`font-medium ${entry.ctr > 2 ? 'text-green-600' : entry.ctr > 1 ? 'text-yellow-600' : 'text-slate-600 dark:text-slate-400'}`}>
                                {entry.ctr.toFixed(2)}%
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm text-right text-slate-600 dark:text-slate-400">
                              {entry.total_leads}
                            </td>
                            <td className="px-4 py-3 text-sm text-right">
                              <span className={`font-medium ${entry.total_conversions > 0 ? 'text-green-600' : 'text-slate-400'}`}>
                                {entry.total_conversions}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm text-right text-slate-600 dark:text-slate-400">
                              {entry.unique_planners}
                            </td>
                            <td className="px-4 py-3 text-sm text-right text-slate-600 dark:text-slate-400">
                              {entry.days_active}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
