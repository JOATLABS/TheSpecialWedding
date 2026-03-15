'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter } from 'next/navigation';
import PageHeader from '../components/PageHeader';
import { toast } from 'sonner';
import {
  getFeatureFlag,
  toggleFeatureFlag,
  getSponsoredVendors,
  createSponsoredVendor,
  updateSponsoredVendor,
  deleteSponsoredVendor,
  getAdStats,
  getAdPlacementLabel,
  type FeatureFlag,
  type SponsoredVendor,
  type AdStats,
  type AdPlacement,
  type CreateSponsoredVendorRequest,
} from '@/services/advertisingApi';
import { getVendorDirectory, type VendorProfile } from '@/services/vendorManagementApi';
import {
  Trash2,
  Plus,
  ToggleRight,
  ToggleLeft,
  Eye,
  EyeOff,
  TrendingUp,
  Users,
  Mouse,
  Activity,
} from 'lucide-react';

type TabId = 'settings' | 'vendors' | 'analytics';

interface DateRange {
  label: string;
  days: number;
}

export default function AdvertisingPage() {
  const { token, userProfile } = useAdmin();
  const router = useRouter();

  // Tab state
  const [activeTab, setActiveTab] = useState<TabId>('settings');

  // Loading state
  const [loading, setLoading] = useState(true);
  const [featureFlagLoading, setFeatureFlagLoading] = useState(false);
  const [vendorActionLoading, setVendorActionLoading] = useState<string | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  // Data state
  const [featureFlag, setFeatureFlag] = useState<FeatureFlag | null>(null);
  const [sponsoredVendors, setSponsoredVendors] = useState<SponsoredVendor[]>([]);
  const [allVendors, setAllVendors] = useState<VendorProfile[]>([]);
  const [vendorStats, setVendorStats] = useState<Record<string, AdStats | null>>({});

  // UI state
  const [showAddVendor, setShowAddVendor] = useState(false);
  const [editingVendorId, setEditingVendorId] = useState<string | null>(null);
  const [selectedDateRange, setSelectedDateRange] = useState<DateRange>({ label: '7d', days: 7 });

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

  // Fetch all data
  const fetchAllData = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    try {
      const [flagData, vendorsData, allVendorsData] = await Promise.all([
        getFeatureFlag(token),
        getSponsoredVendors(token),
        getVendorDirectory(token, { limit: 1000 }),
      ]);

      setFeatureFlag(flagData);
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

  // Initial data load
  useEffect(() => {
    if (token) {
      fetchAllData();
    }
  }, [token, selectedDateRange]);

  // Toggle feature flag
  const handleToggleFeatureFlag = async () => {
    if (!token || !featureFlag) return;

    setFeatureFlagLoading(true);
    try {
      const updated = await toggleFeatureFlag(token, !featureFlag.is_enabled);
      setFeatureFlag(updated);
      toast.success(
        updated.is_enabled ? 'Sponsored vendors feature enabled' : 'Sponsored vendors feature disabled'
      );
    } catch (error) {
      toast.error('Failed to update feature flag');
      console.error(error);
    } finally {
      setFeatureFlagLoading(false);
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

  // Calculate totals for analytics
  const calculateAnalyticsTotals = () => {
    let totalImpressions = 0;
    let totalClicks = 0;
    let activeCampaigns = 0;

    sponsoredVendors.forEach((vendor) => {
      const stats = vendorStats[vendor._id];
      if (stats) {
        totalImpressions += stats.total_impressions;
        totalClicks += stats.total_clicks;
      }
      if (vendor.is_active) {
        activeCampaigns += 1;
      }
    });

    const averageCTR =
      totalImpressions > 0 ? ((totalClicks / totalImpressions) * 100).toFixed(2) : '0.00';

    return {
      totalImpressions,
      totalClicks,
      averageCTR,
      activeCampaigns,
    };
  };

  const analyticsTotals = calculateAnalyticsTotals();

  // Tabs configuration
  const tabs = [
    {
      id: 'settings' as TabId,
      label: 'Feature Settings',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
          />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      ),
    },
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
      label: 'Analytics',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
          />
        </svg>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Advertising Management"
          description="Manage sponsored vendors, feature flags, and ad analytics"
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
        description="Manage sponsored vendors, feature flags, and ad analytics"
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

      {/* Tab Content */}
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
        {/* Feature Settings Tab */}
        {activeTab === 'settings' && featureFlag && (
          <div className="space-y-8">
            {/* Feature Toggle Section */}
            <div className="border-b border-slate-200 dark:border-slate-700 pb-8">
              <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6">Feature Toggle</h2>

              <div className="bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-800/50 dark:to-slate-800 rounded-xl p-8 border border-slate-200 dark:border-slate-700">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                      Sponsored Vendors Feature
                    </h3>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                      Enable or disable the sponsored vendors display across the platform
                    </p>
                  </div>
                  <button
                    onClick={handleToggleFeatureFlag}
                    disabled={featureFlagLoading}
                    className="flex items-center gap-2 px-6 py-3 rounded-lg transition-colors disabled:opacity-50"
                  >
                    {featureFlag.is_enabled ? (
                      <>
                        <ToggleRight className="w-6 h-6 text-green-600" />
                        <span className="font-medium text-green-600">Enabled</span>
                      </>
                    ) : (
                      <>
                        <ToggleLeft className="w-6 h-6 text-slate-400" />
                        <span className="font-medium text-slate-400">Disabled</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Status Indicators */}
            <div className="border-b border-slate-200 dark:border-slate-700 pb-8">
              <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6">Status</h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Current Status</span>
                    <span
                      className={`px-3 py-1 rounded-full text-xs font-semibold ${
                        featureFlag.is_enabled
                          ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
                          : 'bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-300'
                      }`}
                    >
                      {featureFlag.is_enabled ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>

                {featureFlag.enabled_by && (
                  <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
                    <div>
                      <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Last toggled by</span>
                      <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">{featureFlag.enabled_by}</p>
                    </div>
                  </div>
                )}

                {featureFlag.enabled_at && (
                  <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
                    <div>
                      <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Last toggled at</span>
                      <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                        {new Date(featureFlag.enabled_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Configuration Display */}
            <div>
              <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6">Configuration</h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Max Sponsored per Page</span>
                  <p className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
                    {featureFlag.config.max_sponsored_per_page}
                  </p>
                </div>

                <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Show Sponsored Badge</span>
                  <p className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
                    {featureFlag.config.show_sponsored_badge ? 'Yes' : 'No'}
                  </p>
                </div>

                <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Event Tracking</span>
                  <p className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
                    {featureFlag.config.enable_tracking ? 'Enabled' : 'Disabled'}
                  </p>
                </div>

                <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Min Priority Threshold</span>
                  <p className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
                    {featureFlag.config.min_priority_threshold}
                  </p>
                </div>

                <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                    Impressions Per Session
                  </span>
                  <p className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
                    {featureFlag.config.impressions_per_session_limit}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Sponsored Vendors Tab */}
        {activeTab === 'vendors' && (
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
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Vendor Name
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Placement
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Priority
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Status
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Impressions
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Clicks
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">
                        CTR
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {sponsoredVendors.map((vendor) => {
                      const stats = vendorStats[vendor._id];
                      return (
                        <tr
                          key={vendor._id}
                          className="border-b border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                        >
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
                            <span
                              className={`px-2 py-1 rounded-full text-xs font-semibold ${
                                vendor.is_active
                                  ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
                                  : 'bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-300'
                              }`}
                            >
                              {vendor.is_active ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">
                            {stats?.total_impressions ?? 0}
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">
                            {stats?.total_clicks ?? 0}
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">
                            {stats ? `${(stats.ctr * 100).toFixed(2)}%` : '-'}
                          </td>
                          <td className="px-4 py-3 text-sm space-x-2">
                            <button
                              onClick={() => handleToggleVendorStatus(vendor)}
                              disabled={vendorActionLoading === vendor._id}
                              className="inline-flex items-center gap-1 px-3 py-1 rounded bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 transition-colors disabled:opacity-50"
                            >
                              {vendor.is_active ? (
                                <EyeOff className="w-4 h-4" />
                              ) : (
                                <Eye className="w-4 h-4" />
                              )}
                            </button>
                            <button
                              onClick={() => handleDeleteVendor(vendor._id)}
                              disabled={vendorActionLoading === vendor._id}
                              className="inline-flex items-center gap-1 px-3 py-1 rounded bg-red-100 hover:bg-red-200 dark:bg-red-900/30 dark:hover:bg-red-900/50 text-red-700 dark:text-red-300 transition-colors disabled:opacity-50"
                            >
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
        )}

        {/* Analytics Tab */}
        {activeTab === 'analytics' && (
          <div className="space-y-6">
            {/* Date Range Filter */}
            <div className="flex gap-2">
              {[
                { label: '7 days', days: 7 },
                { label: '30 days', days: 30 },
                { label: '90 days', days: 90 },
              ].map((range) => (
                <button
                  key={range.days}
                  onClick={() => setSelectedDateRange({ label: `${range.days}d`, days: range.days })}
                  className={`px-4 py-2 rounded-lg transition-colors font-medium text-sm ${
                    selectedDateRange.days === range.days
                      ? 'bg-wedding-rose text-white'
                      : 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-600'
                  }`}
                >
                  {range.label}
                </button>
              ))}
            </div>

            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-900/10 rounded-xl p-6 border border-blue-200 dark:border-blue-800">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-blue-700 dark:text-blue-300">Total Impressions</span>
                  <Users className="w-5 h-5 text-blue-600" />
                </div>
                <div className="text-2xl font-bold text-blue-900 dark:text-blue-100">
                  {analyticsTotals.totalImpressions.toLocaleString()}
                </div>
              </div>

              <div className="bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-900/10 rounded-xl p-6 border border-green-200 dark:border-green-800">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-green-700 dark:text-green-300">Total Clicks</span>
                  <Mouse className="w-5 h-5 text-green-600" />
                </div>
                <div className="text-2xl font-bold text-green-900 dark:text-green-100">
                  {analyticsTotals.totalClicks.toLocaleString()}
                </div>
              </div>

              <div className="bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/20 dark:to-purple-900/10 rounded-xl p-6 border border-purple-200 dark:border-purple-800">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-purple-700 dark:text-purple-300">Average CTR</span>
                  <Activity className="w-5 h-5 text-purple-600" />
                </div>
                <div className="text-2xl font-bold text-purple-900 dark:text-purple-100">
                  {analyticsTotals.averageCTR}%
                </div>
              </div>

              <div className="bg-gradient-to-br from-orange-50 to-orange-100 dark:from-orange-900/20 dark:to-orange-900/10 rounded-xl p-6 border border-orange-200 dark:border-orange-800">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-orange-700 dark:text-orange-300">Active Campaigns</span>
                  <TrendingUp className="w-5 h-5 text-orange-600" />
                </div>
                <div className="text-2xl font-bold text-orange-900 dark:text-orange-100">
                  {analyticsTotals.activeCampaigns}
                </div>
              </div>
            </div>

            {/* Vendor Performance Table */}
            {sponsoredVendors.length === 0 ? (
              <div className="text-center py-12 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <TrendingUp className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                <p className="text-slate-600 dark:text-slate-400 font-medium">No analytics data yet</p>
                <p className="text-sm text-slate-500 dark:text-slate-500 mt-1">
                  Add sponsored vendors to see performance metrics
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Vendor
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Impressions
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Clicks
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">
                        CTR
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {sponsoredVendors
                      .map((vendor) => ({
                        vendor,
                        stats: vendorStats[vendor._id],
                      }))
                      .sort((a, b) => (b.stats?.total_impressions ?? 0) - (a.stats?.total_impressions ?? 0))
                      .map(({ vendor, stats }) => (
                        <tr
                          key={vendor._id}
                          className="border-b border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                        >
                          <td className="px-4 py-3 text-sm font-medium text-slate-900 dark:text-white">
                            {getVendorName(vendor.vendor_profile_id)}
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">
                            {stats?.total_impressions ?? 0}
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">
                            {stats?.total_clicks ?? 0}
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">
                            {stats ? `${(stats.ctr * 100).toFixed(2)}%` : '-'}
                          </td>
                          <td className="px-4 py-3 text-sm">
                            <span
                              className={`px-2 py-1 rounded-full text-xs font-semibold ${
                                vendor.is_active
                                  ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
                                  : 'bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-300'
                              }`}
                            >
                              {vendor.is_active ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
