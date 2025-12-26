'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter } from 'next/navigation';
import {
  getVendorDirectory,
  getContracts,
  getPaymentMilestones,
  getVendorDashboard,
  createVendorProfile,
  deleteVendorProfile,
  VENDOR_CATEGORIES,
  getCategoryLabel,
  getContractStatusColor,
  getPaymentStatusColor,
  type VendorProfile,
  type VendorContract,
  type PaymentMilestone,
  type VendorDashboard,
  type VendorCategory,
} from '@/services/vendorManagementApi';
import { toast } from 'sonner';
import { VendorPaymentModal } from './components/VendorPaymentModal';

// Tab type
type TabId = 'overview' | 'directory' | 'contracts' | 'payments';

export default function VendorManagementPage() {
  const { token, userProfile, fetchUserProfile } = useAdmin();
  const router = useRouter();

  // State
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [loading, setLoading] = useState(true);
  const [featureEnabled, setFeatureEnabled] = useState(true);

  // Data state
  const [dashboard, setDashboard] = useState<VendorDashboard | null>(null);
  const [vendors, setVendors] = useState<VendorProfile[]>([]);
  const [contracts, setContracts] = useState<VendorContract[]>([]);
  const [milestones, setMilestones] = useState<PaymentMilestone[]>([]);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [preferredOnly, setPreferredOnly] = useState(false);

  // Modal state
  const [showAddVendor, setShowAddVendor] = useState(false);
  const [newVendor, setNewVendor] = useState({
    business_name: '',
    contact_name: '',
    email: '',
    phone: '',
    website: '',
    service_category: 'photographer' as VendorCategory,
    service_description: '',
    internal_notes: '',
    is_preferred: false,
  });

  // Payment Modal State
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [selectedVendorForPayment, setSelectedVendorForPayment] = useState<{id: string, name: string} | null>(null);

  // Fetch data
  const fetchData = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    try {
      const [dashboardData, vendorsData, contractsData, milestonesData] = await Promise.all([
        getVendorDashboard(token),
        getVendorDirectory(token, {
          search: searchQuery || undefined,
          category: categoryFilter || undefined,
          is_preferred: preferredOnly ? true : undefined,
        }),
        getContracts(token),
        getPaymentMilestones(token),
      ]);

      setDashboard(dashboardData);
      setVendors(vendorsData);
      setContracts(contractsData);
      setMilestones(milestonesData);
      setFeatureEnabled(true);
    } catch (error: unknown) {
      const err = error as { message?: string };
      if (err.message?.includes('not included in your plan')) {
        setFeatureEnabled(false);
      } else {
        console.error('Error fetching vendor data:', error);
      }
    } finally {
      setLoading(false);
    }
  }, [token, searchQuery, categoryFilter, preferredOnly]);

  useEffect(() => {
    if (!userProfile) {
      fetchUserProfile();
    } else if (!userProfile.is_wedding_planner && !userProfile.is_root_admin) {
      router.push('/admin');
    } else {
      fetchData();
    }
  }, [fetchData, fetchUserProfile, router, userProfile]);

  // Handle add vendor
  const handleAddVendor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    try {
      await createVendorProfile(token, newVendor);
      toast.success('Vendor added to directory');
      setShowAddVendor(false);
      setNewVendor({
        business_name: '',
        contact_name: '',
        email: '',
        phone: '',
        website: '',
        service_category: 'photographer',
        service_description: '',
        internal_notes: '',
        is_preferred: false,
      });
      fetchData();
    } catch (error) {
      toast.error('Failed to add vendor');
    }
  };

  // Handle delete vendor
  const handleDeleteVendor = async (vendorId: string) => {
    if (!token || !confirm('Remove this vendor from your directory?')) return;

    try {
      await deleteVendorProfile(token, vendorId);
      toast.success('Vendor removed');
      fetchData();
    } catch (error) {
      toast.error('Failed to remove vendor');
    }
  };

  // Feature not enabled view
  if (!featureEnabled) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="max-w-md text-center">
          <div className="w-16 h-16 bg-gradient-to-br from-wedding-rose to-wedding-gold rounded-2xl flex items-center justify-center mx-auto mb-6">
            <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
            Vendor Management
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Manage your vendor directory, create contracts, and track payments all in one place.
          </p>
          <button
            onClick={() => router.push('/admin/planner/billing')}
            className="bg-gradient-to-r from-wedding-rose to-wedding-gold text-white px-6 py-3 rounded-lg font-semibold hover:opacity-90 transition-opacity"
          >
            Upgrade Your Plan
          </button>
        </div>
      </div>
    );
  }

  // Loading state
  if (loading && !dashboard) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-wedding-rose mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading vendor management...</p>
        </div>
      </div>
    );
  }

  const tabs: { id: TabId; label: string; icon: React.ReactNode; count?: number }[] = [
    {
      id: 'overview',
      label: 'Overview',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
        </svg>
      ),
    },
    {
      id: 'directory',
      label: 'Vendor Directory',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
        </svg>
      ),
      count: vendors.length,
    },
    {
      id: 'contracts',
      label: 'Contracts',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
      count: contracts.length,
    },
    {
      id: 'payments',
      label: 'Payments',
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      count: milestones.filter((m) => m.status !== 'paid').length,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Vendor Management</h1>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            Your complete vendor CRM - directory, contracts, and payments in one place
          </p>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">

        {/* Tabs */}
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
                {tab.count !== undefined && tab.count > 0 && (
                  <span className={`ml-1 px-2 py-0.5 rounded-full text-xs ${
                    activeTab === tab.id
                      ? 'bg-wedding-rose/10 text-wedding-rose'
                      : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                  }`}>
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Tab Content */}
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6">
        {/* Overview Tab */}
        {activeTab === 'overview' && dashboard && (
          <div className="space-y-6">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-white dark:bg-slate-800/95 rounded-xl p-6 border border-slate-200 dark:border-slate-700">
                <div className="flex items-center justify-between mb-2">
                  <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                    <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                    </svg>
                  </div>
                </div>
                <div className="text-2xl font-bold text-slate-900 dark:text-white">{dashboard.vendors.total}</div>
                <div className="text-sm text-slate-500 dark:text-slate-400">Total Vendors</div>
                <div className="text-xs text-blue-600 mt-1">{dashboard.vendors.preferred} preferred</div>
              </div>
              <div className="bg-white dark:bg-slate-800/95 rounded-xl p-6 border border-slate-200 dark:border-slate-700">
                <div className="flex items-center justify-between mb-2">
                  <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                    <svg className="w-5 h-5 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                </div>
                <div className="text-2xl font-bold text-slate-900 dark:text-white">{dashboard.contracts.total}</div>
                <div className="text-sm text-slate-500 dark:text-slate-400">Contracts</div>
                <div className="text-xs text-purple-600 mt-1">{dashboard.contracts.signed} signed</div>
              </div>
              <div className="bg-white dark:bg-slate-800/95 rounded-xl p-6 border border-slate-200 dark:border-slate-700">
                <div className="flex items-center justify-between mb-2">
                  <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                    <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                </div>
                <div className="text-2xl font-bold text-slate-900 dark:text-white">${dashboard.payments.total_paid.toLocaleString()}</div>
                <div className="text-sm text-slate-500 dark:text-slate-400">Total Paid</div>
              </div>
              <div className="bg-white dark:bg-slate-800/95 rounded-xl p-6 border border-slate-200 dark:border-slate-700">
                <div className="flex items-center justify-between mb-2">
                  <div className="p-2 bg-orange-100 dark:bg-orange-900/30 rounded-lg">
                    <svg className="w-5 h-5 text-orange-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                </div>
                <div className="text-2xl font-bold text-slate-900 dark:text-white">${dashboard.payments.total_due.toLocaleString()}</div>
                <div className="text-sm text-slate-500 dark:text-slate-400">Outstanding</div>
                <div className="text-xs text-orange-600 mt-1">{dashboard.payments.overdue_count} overdue</div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <button
                onClick={() => setShowAddVendor(true)}
                className="flex items-center gap-3 p-4 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl hover:border-wedding-rose hover:bg-wedding-rose/5 transition-colors"
              >
                <div className="w-10 h-10 bg-wedding-rose/10 rounded-lg flex items-center justify-center">
                  <svg className="w-5 h-5 text-wedding-rose" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                </div>
                <div className="text-left">
                  <div className="font-semibold text-gray-900 dark:text-gray-100">Add Vendor</div>
                  <div className="text-sm text-gray-500">Add to your directory</div>
                </div>
              </button>
              <button
                onClick={() => setActiveTab('contracts')}
                className="flex items-center gap-3 p-4 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl hover:border-purple-500 hover:bg-purple-50 dark:hover:bg-purple-900/10 transition-colors"
              >
                <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900/30 rounded-lg flex items-center justify-center">
                  <svg className="w-5 h-5 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <div className="text-left">
                  <div className="font-semibold text-gray-900 dark:text-gray-100">Create Contract</div>
                  <div className="text-sm text-gray-500">Use Contract Canvas</div>
                </div>
              </button>
              <button
                onClick={() => setActiveTab('payments')}
                className="flex items-center gap-3 p-4 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl hover:border-green-500 hover:bg-green-50 dark:hover:bg-green-900/10 transition-colors"
              >
                <div className="w-10 h-10 bg-green-100 dark:bg-green-900/30 rounded-lg flex items-center justify-center">
                  <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
                <div className="text-left">
                  <div className="font-semibold text-gray-900 dark:text-gray-100">Record Payment</div>
                  <div className="text-sm text-gray-500">Track vendor payments</div>
                </div>
              </button>
            </div>

            {/* Recent Activity */}
            {dashboard.contracts.recent.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Recent Contracts</h3>
                <div className="space-y-3">
                  {dashboard.contracts.recent.map((contract) => (
                    <div
                      key={contract._id}
                      className="flex items-center justify-between p-4 bg-gray-50 dark:bg-slate-700 rounded-lg"
                    >
                      <div>
                        <div className="font-medium text-gray-900 dark:text-gray-100">{contract.vendor_name}</div>
                        <div className="text-sm text-gray-500">{contract.contract_title}</div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-gray-900 dark:text-gray-100 font-medium">
                          ${contract.total_amount.toLocaleString()}
                        </span>
                        <span className={`px-2 py-1 text-xs rounded-full ${getContractStatusColor(contract.status)}`}>
                          {contract.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Directory Tab */}
        {activeTab === 'directory' && (
          <div className="space-y-6">
            {/* Search & Filters */}
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="flex-1">
                <input
                  type="text"
                  placeholder="Search vendors..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                />
              </div>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
              >
                <option value="">All Categories</option>
                {VENDOR_CATEGORIES.map((cat) => (
                  <option key={cat.value} value={cat.value}>
                    {cat.label}
                  </option>
                ))}
              </select>
              <label className="flex items-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferredOnly}
                  onChange={(e) => setPreferredOnly(e.target.checked)}
                  className="rounded text-wedding-rose"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">Preferred only</span>
              </label>
              <button
                onClick={() => setShowAddVendor(true)}
                className="px-4 py-2 bg-wedding-rose text-white rounded-lg font-medium hover:bg-wedding-rose/90 transition-colors"
              >
                + Add Vendor
              </button>
            </div>

            {/* Vendor Grid */}
            {vendors.length === 0 ? (
              <div className="text-center py-12">
                <div className="w-16 h-16 bg-gray-100 dark:bg-gray-700 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-1">No vendors yet</h3>
                <p className="text-gray-500 dark:text-gray-400 mb-4">
                  Start building your vendor directory by adding your first vendor.
                </p>
                <button
                  onClick={() => setShowAddVendor(true)}
                  className="px-6 py-2 bg-wedding-rose text-white rounded-lg font-medium hover:bg-wedding-rose/90"
                >
                  Add Your First Vendor
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {vendors.map((vendor) => (
                  <div
                    key={vendor._id}
                    className="border border-gray-200 dark:border-gray-700 rounded-xl p-4 hover:shadow-lg transition-shadow"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 bg-gradient-to-br from-wedding-rose to-wedding-gold rounded-lg flex items-center justify-center text-white font-bold">
                          {vendor.business_name.charAt(0)}
                        </div>
                        <div>
                          <div className="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                            {vendor.business_name}
                            {vendor.is_preferred && (
                              <svg className="w-4 h-4 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                              </svg>
                            )}
                          </div>
                          <div className="text-sm text-gray-500 dark:text-gray-400">
                            {getCategoryLabel(vendor.service_category)}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                         <button
                           onClick={() => {
                             // Assuming vendor._id is what we need, but typically we need the User ID for payment.
                             // For now, passing vendor._id and we'll handle resolution in modal or backend if needed.
                             // Ideally vendor profile should link to a User ID.
                             setSelectedVendorForPayment({ id: vendor._id, name: vendor.business_name });
                             setShowPaymentModal(true);
                           }}
                           className="text-gray-400 hover:text-green-500 transition-colors"
                           title="Pay Vendor"
                         >
                           <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                             <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                           </svg>
                         </button>
                         <button
                           onClick={() => handleDeleteVendor(vendor._id)}
                           className="text-gray-400 hover:text-red-500 transition-colors"
                           title="Delete Vendor"
                         >
                           <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                             <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                           </svg>
                         </button>
                      </div>
                    </div>
                    <div className="space-y-2 text-sm">
                      <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                        {vendor.email}
                      </div>
                      {vendor.phone && (
                        <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                          </svg>
                          {vendor.phone}
                        </div>
                      )}
                    </div>
                    <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700 flex items-center justify-between">
                      <div className="text-xs text-gray-500">
                        {vendor.weddings_count} wedding{vendor.weddings_count !== 1 ? 's' : ''}
                      </div>
                      {typeof vendor.internal_rating === 'number' && vendor.internal_rating > 0 && (
                        <div className="flex items-center gap-1">
                          {[...Array(5)].map((_, i) => (
                            <svg
                              key={i}
                              className={`w-4 h-4 ${i < (vendor.internal_rating || 0) ? 'text-yellow-400' : 'text-gray-300'}`}
                              fill="currentColor"
                              viewBox="0 0 20 20"
                            >
                              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                            </svg>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Contracts Tab */}
        {activeTab === 'contracts' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Your Contracts</h3>
              <button
                onClick={() => router.push('/admin/vendors/contracts/new')}
                className="px-4 py-2 bg-gradient-to-r from-purple-600 to-wedding-rose text-white rounded-lg font-medium hover:opacity-90 transition-opacity flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Open Contract Canvas
              </button>
            </div>

            {contracts.length === 0 ? (
              <div className="text-center py-12 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl">
                <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No contracts yet</h3>
                <p className="text-gray-500 dark:text-gray-400 mb-4">
                  Use the Contract Canvas to create beautiful, professional contracts.
                </p>
                <button
                  onClick={() => router.push('/admin/vendors/contracts/new')}
                  className="px-6 py-3 bg-gradient-to-r from-purple-600 to-wedding-rose text-white rounded-lg font-medium hover:opacity-90"
                >
                  Create Your First Contract
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {contracts.map((contract) => (
                  <div
                    key={contract._id}
                    className="border border-gray-200 dark:border-gray-700 rounded-xl p-4 hover:shadow-md transition-shadow cursor-pointer"
                    onClick={() => router.push(`/admin/vendors/contracts/${contract._id}`)}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-semibold text-gray-900 dark:text-gray-100">{contract.contract_title}</div>
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          {contract.vendor_name} - {getCategoryLabel(contract.service_category)}
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <div className="font-semibold text-gray-900 dark:text-gray-100">
                            ${contract.total_amount.toLocaleString()}
                          </div>
                          {contract.contract_number && (
                            <div className="text-xs text-gray-500">#{contract.contract_number}</div>
                          )}
                        </div>
                        <span className={`px-3 py-1 text-sm rounded-full ${getContractStatusColor(contract.status)}`}>
                          {contract.status.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Payments Tab */}
        {activeTab === 'payments' && (
          <div className="space-y-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Payment Milestones</h3>

            {milestones.length === 0 ? (
              <div className="text-center py-12">
                <div className="w-16 h-16 bg-gray-100 dark:bg-gray-700 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-1">No payment milestones</h3>
                <p className="text-gray-500 dark:text-gray-400">
                  Payment milestones will appear here once you create contracts.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {milestones.map((milestone) => (
                  <div
                    key={milestone._id}
                    className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-xl"
                  >
                    <div>
                      <div className="font-medium text-gray-900 dark:text-gray-100">{milestone.description}</div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">
                        {milestone.vendor_name} - Due {new Date(milestone.due_date).toLocaleDateString()}
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <div className="font-semibold text-gray-900 dark:text-gray-100">
                          ${milestone.amount.toLocaleString()}
                        </div>
                        {milestone.paid_amount > 0 && (
                          <div className="text-xs text-green-600">${milestone.paid_amount.toLocaleString()} paid</div>
                        )}
                      </div>
                      <span className={`px-3 py-1 text-sm rounded-full ${getPaymentStatusColor(milestone.status)}`}>
                        {milestone.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Add Vendor Modal */}
      {showAddVendor && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-800 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Add Vendor to Directory</h2>
            </div>
            <form onSubmit={handleAddVendor} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Business Name *
                </label>
                <input
                  type="text"
                  required
                  value={newVendor.business_name}
                  onChange={(e) => setNewVendor({ ...newVendor, business_name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Contact Name
                  </label>
                  <input
                    type="text"
                    value={newVendor.contact_name}
                    onChange={(e) => setNewVendor({ ...newVendor, contact_name: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Category *
                  </label>
                  <select
                    required
                    value={newVendor.service_category}
                    onChange={(e) => setNewVendor({ ...newVendor, service_category: e.target.value as VendorCategory })}
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  >
                    {VENDOR_CATEGORIES.map((cat) => (
                      <option key={cat.value} value={cat.value}>
                        {cat.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email *</label>
                <input
                  type="email"
                  required
                  value={newVendor.email}
                  onChange={(e) => setNewVendor({ ...newVendor, email: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Phone</label>
                  <input
                    type="tel"
                    value={newVendor.phone}
                    onChange={(e) => setNewVendor({ ...newVendor, phone: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Website</label>
                  <input
                    type="url"
                    value={newVendor.website}
                    onChange={(e) => setNewVendor({ ...newVendor, website: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Notes</label>
                <textarea
                  rows={3}
                  value={newVendor.internal_notes}
                  onChange={(e) => setNewVendor({ ...newVendor, internal_notes: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  placeholder="Private notes about this vendor..."
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="preferred"
                  checked={newVendor.is_preferred}
                  onChange={(e) => setNewVendor({ ...newVendor, is_preferred: e.target.checked })}
                  className="rounded text-wedding-rose"
                />
                <label htmlFor="preferred" className="text-sm text-gray-700 dark:text-gray-300">
                  Mark as preferred vendor
                </label>
              </div>
              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowAddVendor(false)}
                  className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-wedding-rose text-white rounded-lg font-medium hover:bg-wedding-rose/90"
                >
                  Add Vendor
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Payment Modal */}
      {showPaymentModal && selectedVendorForPayment && (
        <VendorPaymentModal
          open={showPaymentModal}
          onClose={() => setShowPaymentModal(false)}
          vendorId={selectedVendorForPayment.id}
          vendorName={selectedVendorForPayment.name}
        />
      )}
    </div>
  );
}
