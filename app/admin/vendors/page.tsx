'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter } from 'next/navigation';
import PageHeader from '../components/PageHeader';
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
import VendorImportModal from '@/components/vendor/VendorImportModal';
import { VendorPaymentModal } from './components/VendorPaymentModal';
import { PaymentMilestones } from './components/PaymentMilestones';
import { getApiBaseUrl } from '@/utils/env';
import { CampaignSponsoredRail } from './components/CampaignSponsoredRail';
import { usePagination } from '@/admin/hooks/usePagination';
import { GlassPagination } from '@/admin/components/ui/glass/GlassPagination';

// AI Recommendation types
interface VendorRecommendation {
  vendor_type: string;
  selection_criteria: Array<{ criterion: string; importance: string; why: string }>;
  questions_to_ask: Array<{ question: string; why_important: string }>;
  red_flags: Array<{ flag: string; severity: string }>;
  budget_assessment: {
    verdict: string;
    typical_range_min: number;
    typical_range_max: number;
    explanation: string;
  };
  pro_tips: string[];
}

interface PriceAnalysis {
  verdict: string;
  confidence: string;
  typical_range: { min: number; max: number; average: number };
  analysis: string;
  factors_considered: Array<{ factor: string; impact: string; explanation: string }>;
  recommendations: string[];
  value_assessment: string;
}

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
  const [showImportModal, setShowImportModal] = useState(false);
  const [newVendor, setNewVendor] = useState({
    business_name: '',
    contact_name: '',
    email: '',
    phone: '',
    website: '',
    service_category: 'photographer' as VendorCategory,
    custom_service_category: '',
    service_description: '',
    internal_notes: '',
    is_preferred: false,
  });

  // Payment Modal State
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [selectedVendorForPayment, setSelectedVendorForPayment] = useState<{
    id: string;
    name: string;
    email: string;
  } | null>(null);

  // AI Recommendations State
  const [showAiRecommendations, setShowAiRecommendations] = useState(false);
  const [aiRecommendations, setAiRecommendations] = useState<VendorRecommendation | null>(null);
  const [aiRecommendationsLoading, setAiRecommendationsLoading] = useState(false);
  const [aiVendorType, setAiVendorType] = useState<VendorCategory>('photographer');
  const [aiBudgetMin, setAiBudgetMin] = useState<string>('');
  const [aiBudgetMax, setAiBudgetMax] = useState<string>('');

  // AI Price Analysis State
  const [showPriceAnalysis, setShowPriceAnalysis] = useState(false);
  const [priceAnalysis, setPriceAnalysis] = useState<PriceAnalysis | null>(null);
  const [priceAnalysisLoading, setPriceAnalysisLoading] = useState(false);
  const [priceVendorType, setPriceVendorType] = useState<VendorCategory>('photographer');
  const [priceQuotedAmount, setPriceQuotedAmount] = useState<string>('');
  const [priceDescription, setPriceDescription] = useState<string>('');
  const [showAdRail, setShowAdRail] = useState(false);

  // Pagination
  const pagination = usePagination({ initialItemsPerPage: 50 });
  const {
    skip: vendorSkip,
    itemsPerPage: vendorItemsPerPage,
    setPage: setVendorPage,
    setTotalItems: setVendorTotalItems,
  } = pagination;

  // AI Functions
  const fetchAiRecommendations = async () => {
    if (!token) return;

    setAiRecommendationsLoading(true);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/ai/vendor-recommendations`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          vendor_type: aiVendorType,
          budget_range: aiBudgetMin || aiBudgetMax ? {
            min: aiBudgetMin ? parseFloat(aiBudgetMin) : undefined,
            max: aiBudgetMax ? parseFloat(aiBudgetMax) : undefined,
          } : undefined,
        }),
      });

      if (response.status === 402) {
        toast.error('Insufficient AI credits');
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to get recommendations');
      }

      const data = await response.json();
      setAiRecommendations(data.recommendations);
      toast.success(`Got recommendations! Used ${data.credits_used} credits`);
    } catch {
      toast.error('Failed to get AI recommendations');
    } finally {
      setAiRecommendationsLoading(false);
    }
  };

  const fetchPriceAnalysis = async () => {
    if (!token || !priceQuotedAmount) return;

    setPriceAnalysisLoading(true);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/ai/analyze-vendor-price`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          vendor_type: priceVendorType,
          quoted_price: parseFloat(priceQuotedAmount),
          service_description: priceDescription || undefined,
        }),
      });

      if (response.status === 402) {
        toast.error('Insufficient AI credits');
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to analyze price');
      }

      const data = await response.json();
      setPriceAnalysis(data.analysis);
      toast.success(`Analysis complete! Used ${data.credits_used} credit`);
    } catch {
      toast.error('Failed to analyze price');
    } finally {
      setPriceAnalysisLoading(false);
    }
  };

  // Fetch data
  const fetchData = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    try {
      const results = await Promise.allSettled([
        getVendorDashboard(token),
        getVendorDirectory(token, {
          search: searchQuery || undefined,
          category: categoryFilter || undefined,
          is_preferred: preferredOnly ? true : undefined,
          skip: vendorSkip,
          limit: vendorItemsPerPage,
        }),
        getContracts(token),
        getPaymentMilestones(token),
      ]);

      const [dashboardResult, vendorsResult, contractsResult, milestonesResult] = results;

      // Check if any failure indicates a plan restriction
      const planError = results.find(
        (r) => r.status === 'rejected' && r.reason?.message?.includes('not included in your plan')
      );
      if (planError) {
        setFeatureEnabled(false);
        return;
      }

      if (dashboardResult.status === 'fulfilled') setDashboard(dashboardResult.value);
      if (vendorsResult.status === 'fulfilled') {
        const vendorList = vendorsResult.value || [];
        setVendors(vendorList);
        setVendorTotalItems(vendorList.length);
      }
      if (contractsResult.status === 'fulfilled') setContracts(contractsResult.value);
      if (milestonesResult.status === 'fulfilled') setMilestones(milestonesResult.value);
      setFeatureEnabled(true);
    } catch (error: unknown) {
      console.error('Error fetching vendor data:', error);
    } finally {
      setLoading(false);
    }
  }, [token, searchQuery, categoryFilter, preferredOnly, vendorSkip, vendorItemsPerPage, setVendorTotalItems]);

  useEffect(() => {
    if (!userProfile) {
      fetchUserProfile();
    } else if (!userProfile.is_wedding_planner && !userProfile.is_root_admin) {
      router.push('/admin');
    } else {
      fetchData();
    }
  }, [fetchData, fetchUserProfile, router, userProfile]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setVendorPage(1);
  }, [searchQuery, categoryFilter, preferredOnly, setVendorPage]);


  // Handle add vendor
  const handleAddVendor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    // Auto-prepend https:// if user entered a bare domain
    const vendorData = { ...newVendor };
    if (vendorData.service_category === 'other') {
      vendorData.custom_service_category = vendorData.custom_service_category.trim();
      if (!vendorData.custom_service_category) {
        toast.error('Please enter a custom vendor category');
        return;
      }
    } else {
      vendorData.custom_service_category = '';
    }
    if (vendorData.website && vendorData.website.trim()) {
      const w = vendorData.website.trim();
      if (!/^https?:\/\//i.test(w)) {
        vendorData.website = `https://${w}`;
      }
    }

    try {
      await createVendorProfile(token, vendorData);
      toast.success('Vendor added to directory');
      setShowAddVendor(false);
      setNewVendor({
        business_name: '',
        contact_name: '',
        email: '',
        phone: '',
        website: '',
        service_category: 'photographer',
        custom_service_category: '',
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
      <div className="flex items-center justify-center py-24 p-4">
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
      <div className="flex items-center justify-center py-24">
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
      <PageHeader
        title="Vendor Management"
        description="Your complete vendor CRM - directory, contracts, and payments in one place"
      />

      <div className={`grid grid-cols-1 ${showAdRail ? 'lg:grid-cols-4' : ''} gap-6`}>
      {/* Main Content — expands to full width when ad rail hidden */}
      <div className={showAdRail ? 'lg:col-span-3' : ''}>

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
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
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

            {/* AI Tools */}
            <div className="bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 rounded-xl p-6 border border-indigo-200 dark:border-indigo-800">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">AI Vendor Tools</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Get intelligent recommendations and price analysis</p>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <button
                  onClick={() => setShowAiRecommendations(true)}
                  className="flex items-center gap-3 p-4 bg-white dark:bg-slate-800 rounded-xl border border-indigo-200 dark:border-indigo-700 hover:border-indigo-400 dark:hover:border-indigo-500 hover:shadow-md transition-all"
                >
                  <div className="w-10 h-10 bg-indigo-100 dark:bg-indigo-900/30 rounded-lg flex items-center justify-center">
                    <svg className="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <div className="text-left">
                    <div className="font-semibold text-gray-900 dark:text-gray-100">Vendor Recommendations</div>
                    <div className="text-sm text-gray-500">What to look for, questions to ask • 2 credits</div>
                  </div>
                </button>
                <button
                  onClick={() => setShowPriceAnalysis(true)}
                  className="flex items-center gap-3 p-4 bg-white dark:bg-slate-800 rounded-xl border border-purple-200 dark:border-purple-700 hover:border-purple-400 dark:hover:border-purple-500 hover:shadow-md transition-all"
                >
                  <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900/30 rounded-lg flex items-center justify-center">
                    <svg className="w-5 h-5 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                  </div>
                  <div className="text-left">
                    <div className="font-semibold text-gray-900 dark:text-gray-100">Analyze Quote Price</div>
                    <div className="text-sm text-gray-500">Check if a quote is fair • 1 credit</div>
                  </div>
                </button>
              </div>
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
              {userProfile?.is_root_admin && (
                <button
                  onClick={() => setShowImportModal(true)}
                  className="flex items-center gap-2 px-4 py-2 border-2 border-dashed border-rose-300 text-rose-500 rounded-lg text-sm font-semibold hover:bg-rose-50 transition-colors dark:border-rose-700 dark:text-rose-400 dark:hover:bg-rose-900/20"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
                  Import Vendors
                </button>
              )}
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
              <div className="space-y-4">
                <GlassPagination
                  currentPage={pagination.currentPage}
                  totalPages={pagination.totalPages}
                  totalItems={pagination.totalItems}
                  itemsPerPage={pagination.itemsPerPage}
                  onPageChange={pagination.setPage}
                  variant="compact"
                  itemLabel="vendors"
                />
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* Vendors */}
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
                            {getCategoryLabel(vendor.service_category, vendor.custom_service_category)}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                         <button
                           onClick={() => {
                             setSelectedVendorForPayment({
                               id: vendor._id,
                               name: vendor.business_name,
                               email: vendor.email,
                             });
                             setShowPaymentModal(true);
                           }}
                           className="text-gray-400 hover:text-green-500 transition-colors"
                           title="Create Payment Link"
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
              <GlassPagination
                currentPage={pagination.currentPage}
                totalPages={pagination.totalPages}
                totalItems={pagination.totalItems}
                itemsPerPage={pagination.itemsPerPage}
                onPageChange={pagination.setPage}
                onItemsPerPageChange={pagination.setItemsPerPage}
                itemLabel="vendors"
              />
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
                          {contract.vendor_name} - {getCategoryLabel(contract.service_category, contract.custom_service_category)}
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
        {activeTab === 'payments' && token && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Payment Milestones</h3>
              <p className="text-sm text-gray-500">
                Track and manage all vendor payment milestones across your contracts
              </p>
            </div>

            <PaymentMilestones
              token={token}
              plannerEmail={userProfile?.email}
              plannerName={userProfile?.first_name ? `${userProfile.first_name} ${userProfile.last_name || ''}`.trim() : userProfile?.email}
              onMilestoneUpdated={fetchData}
            />
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
                    onChange={(e) => setNewVendor({
                      ...newVendor,
                      service_category: e.target.value as VendorCategory,
                      custom_service_category: e.target.value === 'other' ? newVendor.custom_service_category : '',
                    })}
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
              {newVendor.service_category === 'other' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Custom Category *
                  </label>
                  <input
                    type="text"
                    required
                    value={newVendor.custom_service_category}
                    onChange={(e) => setNewVendor({ ...newVendor, custom_service_category: e.target.value })}
                    placeholder="e.g., MC / Host"
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  />
                </div>
              )}
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
                    type="text"
                    value={newVendor.website}
                    onChange={(e) => setNewVendor({ ...newVendor, website: e.target.value })}
                    placeholder="e.g. joatlabs.dev"
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
          vendorEmail={selectedVendorForPayment.email}
          plannerEmail={userProfile?.email}
          plannerName={userProfile?.first_name ? `${userProfile.first_name} ${userProfile.last_name || ''}`.trim() : userProfile?.email}
          onPaymentLinkCreated={() => {
            fetchData();
            setShowPaymentModal(false);
          }}
        />
      )}

      {/* AI Recommendations Modal */}
      {showAiRecommendations && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-800 rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
            {/* Header */}
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-indigo-500 to-purple-600">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">AI Vendor Recommendations</h3>
                    <p className="text-sm text-indigo-100">Get selection criteria and questions to ask</p>
                  </div>
                </div>
                <button
                  onClick={() => {
                    setShowAiRecommendations(false);
                    setAiRecommendations(null);
                  }}
                  className="p-2 text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto p-6">
              {!aiRecommendations ? (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Vendor Type
                    </label>
                    <select
                      value={aiVendorType}
                      onChange={(e) => setAiVendorType(e.target.value as VendorCategory)}
                      className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                    >
                      {VENDOR_CATEGORIES.map((cat) => (
                        <option key={cat.value} value={cat.value}>{cat.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Budget Min (optional)
                      </label>
                      <input
                        type="number"
                        value={aiBudgetMin}
                        onChange={(e) => setAiBudgetMin(e.target.value)}
                        placeholder="$0"
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Budget Max (optional)
                      </label>
                      <input
                        type="number"
                        value={aiBudgetMax}
                        onChange={(e) => setAiBudgetMax(e.target.value)}
                        placeholder="$10,000"
                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                      />
                    </div>
                  </div>
                  <button
                    onClick={fetchAiRecommendations}
                    disabled={aiRecommendationsLoading}
                    className="w-full px-4 py-3 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg font-medium hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {aiRecommendationsLoading ? (
                      <>
                        <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        Getting recommendations...
                      </>
                    ) : (
                      <>
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        Get Recommendations (2 credits)
                      </>
                    )}
                  </button>
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Selection Criteria */}
                  {aiRecommendations.selection_criteria?.length > 0 && (
                    <div>
                      <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
                        <svg className="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Selection Criteria
                      </h4>
                      <div className="space-y-2">
                        {aiRecommendations.selection_criteria.map((item, i) => (
                          <div key={i} className="p-3 bg-gray-50 dark:bg-slate-700 rounded-lg">
                            <div className="flex items-center justify-between">
                              <span className="font-medium text-gray-900 dark:text-gray-100">{item.criterion}</span>
                              <span className={`text-xs px-2 py-1 rounded-full ${
                                item.importance === 'high' ? 'bg-red-100 text-red-700' :
                                item.importance === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                                'bg-green-100 text-green-700'
                              }`}>
                                {item.importance}
                              </span>
                            </div>
                            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{item.why}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Questions to Ask */}
                  {aiRecommendations.questions_to_ask?.length > 0 && (
                    <div>
                      <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
                        <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Questions to Ask
                      </h4>
                      <div className="space-y-2">
                        {aiRecommendations.questions_to_ask.map((item, i) => (
                          <div key={i} className="p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                            <p className="font-medium text-gray-900 dark:text-gray-100">&quot;{item.question}&quot;</p>
                            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{item.why_important}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Red Flags */}
                  {aiRecommendations.red_flags?.length > 0 && (
                    <div>
                      <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
                        <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                        Red Flags to Watch For
                      </h4>
                      <div className="space-y-2">
                        {aiRecommendations.red_flags.map((item, i) => (
                          <div key={i} className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg flex items-start gap-2">
                            <span className={`text-xs px-2 py-0.5 rounded ${
                              item.severity === 'critical' ? 'bg-red-600 text-white' :
                              item.severity === 'moderate' ? 'bg-orange-500 text-white' :
                              'bg-yellow-400 text-black'
                            }`}>
                              {item.severity}
                            </span>
                            <span className="text-gray-900 dark:text-gray-100">{item.flag}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Budget Assessment */}
                  {aiRecommendations.budget_assessment && (
                    <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                      <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 flex items-center gap-2">
                        <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Typical Price Range
                      </h4>
                      <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                        ${aiRecommendations.budget_assessment.typical_range_min?.toLocaleString()} - ${aiRecommendations.budget_assessment.typical_range_max?.toLocaleString()}
                      </p>
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{aiRecommendations.budget_assessment.explanation}</p>
                    </div>
                  )}

                  {/* Pro Tips */}
                  {aiRecommendations.pro_tips?.length > 0 && (
                    <div>
                      <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
                        <svg className="w-5 h-5 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        Pro Tips
                      </h4>
                      <ul className="space-y-1">
                        {aiRecommendations.pro_tips.map((tip, i) => (
                          <li key={i} className="flex items-start gap-2 text-gray-700 dark:text-gray-300">
                            <span className="text-yellow-500 mt-1">•</span>
                            {tip}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* New Search */}
                  <button
                    onClick={() => setAiRecommendations(null)}
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700"
                  >
                    Search Another Vendor Type
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* AI Price Analysis Modal */}
      {showPriceAnalysis && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-800 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
            {/* Header */}
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-purple-500 to-pink-600">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-white">Quote Price Analysis</h3>
                    <p className="text-sm text-purple-100">Check if a vendor quote is fair</p>
                  </div>
                </div>
                <button
                  onClick={() => {
                    setShowPriceAnalysis(false);
                    setPriceAnalysis(null);
                  }}
                  className="p-2 text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto p-6">
              {!priceAnalysis ? (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Vendor Type
                    </label>
                    <select
                      value={priceVendorType}
                      onChange={(e) => setPriceVendorType(e.target.value as VendorCategory)}
                      className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                    >
                      {VENDOR_CATEGORIES.map((cat) => (
                        <option key={cat.value} value={cat.value}>{cat.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Quoted Price *
                    </label>
                    <input
                      type="number"
                      value={priceQuotedAmount}
                      onChange={(e) => setPriceQuotedAmount(e.target.value)}
                      placeholder="$5,000"
                      className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      What&apos;s Included (optional)
                    </label>
                    <textarea
                      value={priceDescription}
                      onChange={(e) => setPriceDescription(e.target.value)}
                      rows={3}
                      placeholder="8 hours coverage, second shooter, engagement session, photo album..."
                      className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                    />
                  </div>
                  <button
                    onClick={fetchPriceAnalysis}
                    disabled={priceAnalysisLoading || !priceQuotedAmount}
                    className="w-full px-4 py-3 bg-gradient-to-r from-purple-500 to-pink-600 text-white rounded-lg font-medium hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {priceAnalysisLoading ? (
                      <>
                        <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        Analyzing price...
                      </>
                    ) : (
                      <>
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                        </svg>
                        Analyze Price (1 credit)
                      </>
                    )}
                  </button>
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Verdict */}
                  <div className={`p-4 rounded-lg border ${
                    priceAnalysis.verdict === 'below_market' ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800' :
                    priceAnalysis.verdict === 'at_market' ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800' :
                    'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800'
                  }`}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                        {priceAnalysis.verdict === 'below_market' ? 'Below Market' :
                         priceAnalysis.verdict === 'at_market' ? 'At Market Rate' :
                         priceAnalysis.verdict === 'above_market' ? 'Above Market' : 'Significantly Above'}
                      </span>
                      <span className="text-sm text-gray-500">Confidence: {priceAnalysis.confidence}</span>
                    </div>
                    <p className="text-gray-700 dark:text-gray-300">{priceAnalysis.analysis}</p>
                  </div>

                  {/* Typical Range */}
                  {priceAnalysis.typical_range && (
                    <div className="p-4 bg-gray-50 dark:bg-slate-700 rounded-lg">
                      <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Typical Price Range</h4>
                      <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                        ${priceAnalysis.typical_range.min?.toLocaleString()} - ${priceAnalysis.typical_range.max?.toLocaleString()}
                      </p>
                      <p className="text-sm text-gray-500">Average: ${priceAnalysis.typical_range.average?.toLocaleString()}</p>
                    </div>
                  )}

                  {/* Value Assessment */}
                  {priceAnalysis.value_assessment && (
                    <div className="p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                      <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Value Assessment</h4>
                      <p className="text-gray-700 dark:text-gray-300">{priceAnalysis.value_assessment}</p>
                    </div>
                  )}

                  {/* Recommendations */}
                  {priceAnalysis.recommendations?.length > 0 && (
                    <div>
                      <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">Recommendations</h4>
                      <ul className="space-y-2">
                        {priceAnalysis.recommendations.map((rec, i) => (
                          <li key={i} className="flex items-start gap-2 text-gray-700 dark:text-gray-300">
                            <span className="text-purple-500 mt-1">•</span>
                            {rec}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* New Analysis */}
                  <button
                    onClick={() => setPriceAnalysis(null)}
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700"
                  >
                    Analyze Another Quote
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      </div>

      {/* Right Sidebar — Sponsored Vendors Rail (hidden when ads disabled) */}
      <div className={showAdRail ? 'lg:col-span-1' : 'hidden'}>
        <div className="sticky top-6">
          <CampaignSponsoredRail onVisibilityChange={setShowAdRail} />
        </div>
      </div>

      </div>

      {/* Vendor Import Modal (Root Admin only) */}
      {token && (
        <VendorImportModal
          isOpen={showImportModal}
          onClose={() => setShowImportModal(false)}
          token={token}
          onImportComplete={(result) => {
            toast.success(
              `Import complete: ${result.inserted} inserted, ${result.updated} updated` +
              (result.errors > 0 ? `, ${result.errors} errors` : '')
            );
            // Refresh vendor list
            fetchData();
          }}
        />
      )}
    </div>
  );
}
