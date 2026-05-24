'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import BudgetSummaryCard from '../../components/budget/BudgetSummaryCard';
import BudgetCategoryCard from '../../components/budget/BudgetCategoryCard';
import PaymentHistoryPanel from '../../components/budget/PaymentHistoryPanel';
import RecordPaymentModal from '../../components/budget/RecordPaymentModal';
import { budgetApi } from '../../services/budgetApi';
import PageHeader from '../components/PageHeader';
import WeddingPicker from '../components/WeddingPicker';
import {
  getVendorDirectory,
  getWeddingVendors,
  assignVendorToWedding,
  updateVendorAssignment,
  deleteVendorAssignment,
  type VendorProfile,
  type VendorAssignment
} from '../../services/vendorManagementApi';
import { formatDate } from '@/utils/dateFormat';
import { Sparkles, X, Loader2, AlertCircle, Lightbulb } from 'lucide-react';
import UnlinkedVendorsPanel from '../../components/budget/UnlinkedVendorsPanel';
import { CampaignSponsoredRail } from '../vendors/components/CampaignSponsoredRail';
import type {
  BudgetCategory,
  BudgetSummary,
  CreateBudgetCategoryRequest,
  UpdateBudgetCategoryRequest,
  PaymentRecord,
  RecordPaymentRequest
} from '../../types/budget';

interface Wedding {
  id?: string;
  _id?: string;
  couple_names: string;
  date: string;
  slug: string;
}

interface AIInsight {
  category?: string;
  insight: string;
  recommendation?: string;
  priority?: 'high' | 'medium' | 'low';
}

interface AIInsightsResponse {
  insights: AIInsight[];
  cached: boolean;
  credits_used: number;
  warning?: string;
}

export default function BudgetDashboard() {
  const { token } = useAdmin();
  const searchParams = useSearchParams();
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [selectedWedding, setSelectedWedding] = useState<string>('');
  const [budgetSummary, setBudgetSummary] = useState<BudgetSummary | null>(null);
  const [categories, setCategories] = useState<BudgetCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  // Modal states
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [editingCategory, setEditingCategory] = useState<BudgetCategory | null>(null);
  const [categoryForm, setCategoryForm] = useState({
    name: '',
    description: '',
    budgeted_amount: 0,
    priority: 3,
    percentage_of_total: 0
  });

  const [paymentHistory, setPaymentHistory] = useState<PaymentRecord[]>([]);
  const [paymentHistoryLoading, setPaymentHistoryLoading] = useState(false);
  const [paymentHistoryError, setPaymentHistoryError] = useState<string>('');
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [activeCategory, setActiveCategory] = useState<BudgetCategory | null>(null);
  const [isRecordingPayment, setIsRecordingPayment] = useState(false);
  const [paymentModalError, setPaymentModalError] = useState<string>('');

  // Filters and search
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'name' | 'budget' | 'spent' | 'priority'>('priority');

  // Vendor integration
  const [vendorDirectory, setVendorDirectory] = useState<VendorProfile[]>([]);
  const [vendorAssignments, setVendorAssignments] = useState<VendorAssignment[]>([]);
  const [selectedVendorId, setSelectedVendorId] = useState<string>('');

  const [showAdRail, setShowAdRail] = useState(false);

  // AI Budget Insights
  const [aiInsights, setAiInsights] = useState<AIInsight[]>([]);
  const [aiInsightsLoading, setAiInsightsLoading] = useState(false);
  const [aiInsightsError, setAiInsightsError] = useState<string>('');
  const [showAiInsights, setShowAiInsights] = useState(false);
  const [aiCreditsWarning, setAiCreditsWarning] = useState<string>('');

  const fetchAiInsights = useCallback(async (forceRefresh = false) => {
    if (!token || !selectedWedding) return;

    setAiInsightsLoading(true);
    setAiInsightsError('');
    setAiCreditsWarning('');

    try {
      const baseUrl = getApiBaseUrl();
      const url = new URL(`${baseUrl}/admin/ai/weddings/${selectedWedding}/budget-insights`);
      if (forceRefresh) {
        url.searchParams.set('force_refresh', 'true');
      }
      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const detail = errorData.detail;
        const message = typeof detail === 'object' ? detail?.message : detail;

        if (response.status === 402) {
          throw new Error(message || 'Insufficient AI credits. Please upgrade your plan.');
        } else if (response.status === 429) {
          throw new Error(message || 'AI service is busy. Please try again in a moment.');
        } else if (response.status === 503) {
          throw new Error(message || 'AI service is temporarily unavailable.');
        } else if (response.status === 504) {
          throw new Error(message || 'AI request timed out. Try again.');
        }
        throw new Error(message || 'Failed to generate AI insights. Try again.');
      }

      const data: AIInsightsResponse = await response.json();
      setAiInsights(data.insights || []);
      setShowAiInsights(true);

      if (data.warning) {
        setAiCreditsWarning(data.warning);
      }

      if (data.cached) {
        // Don't show toast for cached results — it's expected behavior
      } else {
        toast.success(`AI insights generated (${data.credits_used} credits used)`);
      }
    } catch (err: any) {
      const message = err.message || 'Failed to get AI insights';
      setAiInsightsError(message);
      // Don't clear existing insights on error — keep previous insights visible
      // Only show error toast, the error banner in the UI is enough context
      toast.error(message);
      // Still show the panel so the user sees the error + any previous insights
      setShowAiInsights(true);
    } finally {
      setAiInsightsLoading(false);
    }
  }, [token, selectedWedding]);

  const fetchWeddings = useCallback(async () => {
    if (!token) {
      setWeddings([]);
      return;
    }

    try {
      const baseUrl = getApiBaseUrl();
      // Use authenticated planner endpoint to get assigned weddings
      const response = await fetch(`${baseUrl}/admin/planner/weddings`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      const data = await response.json();
      setWeddings(Array.isArray(data) ? data : []);
    } catch (err) {
      setError('Failed to load weddings');
      toast.error('Failed to load weddings');
    }
  }, [token]);

  useEffect(() => {
    fetchWeddings();
  }, [fetchWeddings]);

  // Honor `?wedding_id=…` deep-links: once the wedding list has loaded
  // and the user hasn't already picked something, pre-select the wedding
  // named in the URL if it's one we own. Only seeds — never overrides
  // a manual selection — so subsequent dropdown changes win.
  useEffect(() => {
    if (selectedWedding) return;
    const urlWeddingId = searchParams.get('wedding_id');
    if (!urlWeddingId || weddings.length === 0) return;
    const match = weddings.find(
      (w) => (w._id || w.id) === urlWeddingId
    );
    if (match) {
      setSelectedWedding(urlWeddingId);
    }
  }, [searchParams, weddings, selectedWedding]);

  const fetchPaymentHistory = useCallback(
    async (weddingId: string) => {
      if (!token) return;

      setPaymentHistoryLoading(true);
      try {
        const paymentData = await budgetApi.getPaymentHistory(token, weddingId);
        setPaymentHistory(paymentData);
        setPaymentHistoryError('');
      } catch (err: any) {
        // Payment history is non-critical; degrade gracefully instead of showing an error
        console.warn('Payment history fetch failed:', err.message || err);
        setPaymentHistoryError('');
        setPaymentHistory([]);
      } finally {
        setPaymentHistoryLoading(false);
      }
    },
    [token]
  );

  const fetchBudgetData = useCallback(async () => {
    if (!token || !selectedWedding) return;

    setLoading(true);
    try {
      const [summaryData, categoriesData, vendorData, assignmentsData] = await Promise.all([
        budgetApi.getBudgetSummary(token, selectedWedding),
        budgetApi.getBudgetCategories(token, selectedWedding),
        getVendorDirectory(token).catch(() => []),
        getWeddingVendors(token, selectedWedding).catch(() => []),
      ]);

      setBudgetSummary(summaryData);
      setCategories(categoriesData);
      setVendorDirectory(vendorData);
      setVendorAssignments(assignmentsData);
      setError('');
      await fetchPaymentHistory(selectedWedding);
    } catch (err: any) {
      setError(err.message || 'Failed to load budget data');
      toast.error(err.message || 'Failed to load budget data');
    } finally {
      setLoading(false);
    }
  }, [fetchPaymentHistory, selectedWedding, token]);

  useEffect(() => {
    if (selectedWedding && token) {
      fetchBudgetData();
    }
  }, [fetchBudgetData, selectedWedding, token]);

  const handleCreateCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !selectedWedding) return;

    try {
      const categoryData: CreateBudgetCategoryRequest = {
        wedding_id: selectedWedding,
        ...categoryForm
      };

      const newCategory = await budgetApi.createBudgetCategory(token, categoryData);
      setCategories((prev) => [...prev, newCategory]);

      // Handle vendor assignment if a vendor was selected
      if (selectedVendorId) {
        await handleVendorAssignment(newCategory.id);
      }

      setShowCategoryModal(false);
      resetCategoryForm();
      toast.success('Budget category created successfully');
      // Refresh summary
      fetchBudgetData();
    } catch (err: any) {
      toast.error(err.message || 'Failed to create budget category');
    }
  };

  const handleUpdateCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !editingCategory) return;

    try {
      const updateData: UpdateBudgetCategoryRequest = {
        name: categoryForm.name,
        description: categoryForm.description,
        budgeted_amount: categoryForm.budgeted_amount,
        priority: categoryForm.priority,
        percentage_of_total: categoryForm.percentage_of_total
      };

      const updatedCategory = await budgetApi.updateBudgetCategory(
        token,
        editingCategory.id,
        updateData
      );

      setCategories((prev) =>
        prev.map((cat) => (cat.id === editingCategory.id ? updatedCategory : cat))
      );

      const existingAssignment = vendorAssignments.find(
        a => a.budget_category_id === editingCategory.id
      );

      // Handle vendor assignment changes. Choosing "No vendor" explicitly
      // detaches the old category link while keeping the vendor on the wedding.
      if (selectedVendorId) {
        await handleVendorAssignment(editingCategory.id);
      } else if (existingAssignment) {
        await handleDetachAssignmentFromCategory(existingAssignment);
      }

      setShowCategoryModal(false);
      setEditingCategory(null);
      resetCategoryForm();
      toast.success('Budget category updated successfully');
      // Refresh summary
      fetchBudgetData();
    } catch (err: any) {
      toast.error(err.message || 'Failed to update budget category');
    }
  };

  const handleDeleteCategory = async (categoryId: string) => {
    if (!token || !confirm('Are you sure you want to delete this category?')) return;

    try {
      await budgetApi.deleteBudgetCategory(token, categoryId);
      setCategories((prev) => prev.filter((cat) => cat.id !== categoryId));
      toast.success('Budget category deleted successfully');
      // Refresh summary
      fetchBudgetData();
    } catch (err: any) {
      toast.error(err.message || 'Failed to delete budget category');
    }
  };

  const openEditModal = (category: BudgetCategory) => {
    setEditingCategory(category);
    setCategoryForm({
      name: category.name,
      description: category.description || '',
      budgeted_amount: category.budgeted_amount,
      priority: category.priority,
      percentage_of_total: category.percentage_of_total || 0
    });
    // Set the selected vendor if there's an existing assignment
    const existingAssignment = vendorAssignments.find(
      a => a.budget_category_id === (category.id)
    );
    setSelectedVendorId(existingAssignment?.vendor_profile_id || '');
    setShowCategoryModal(true);
  };

  const resetCategoryForm = () => {
    setCategoryForm({
      name: '',
      description: '',
      budgeted_amount: 0,
      priority: 3,
      percentage_of_total: 0
    });
    setEditingCategory(null);
    setSelectedVendorId('');
  };

  // Helper to find assigned vendor for a category
  const getAssignedVendorForCategory = useCallback((categoryId: string): VendorAssignment | undefined => {
    return vendorAssignments.find(a => a.budget_category_id === categoryId);
  }, [vendorAssignments]);

  const findAssignmentForVendor = useCallback(
    (vendorId: string): VendorAssignment | undefined => {
      return vendorAssignments.find(
        a => a.vendor_profile_id === vendorId
          && a.wedding_id === selectedWedding
      );
    },
    [vendorAssignments, selectedWedding]
  );

  const unlinkedAssignments = useMemo(() => {
    const categoryIds = new Set(categories.map(c => c.id));
    return vendorAssignments.filter(
      a => !a.budget_category_id
        || !categoryIds.has(a.budget_category_id)
    );
  }, [vendorAssignments, categories]);

  const handleLinkUnlinkedToCategory = useCallback(
    async (assignmentId: string, categoryId: string) => {
      if (!token) {
        throw new Error('Not authenticated');
      }
      const updated = await updateVendorAssignment(token, assignmentId, {
        budget_category_id: categoryId,
      });
      setVendorAssignments(prev => {
        const filtered = prev.filter(
          a => a._id !== updated._id
            && a.budget_category_id !== categoryId
        );
        return [...filtered, updated];
      });
      toast.success(`Linked ${updated.vendor_name} to category`);
    },
    [token]
  );

  const handleRemoveAssignment = useCallback(
    async (assignmentId: string) => {
      if (!token) {
        throw new Error('Not authenticated');
      }
      await deleteVendorAssignment(token, assignmentId);
      setVendorAssignments(prev => prev.filter(a => a._id !== assignmentId));
      toast.success('Vendor removed from this wedding');
    },
    [token]
  );

  const handleDetachAssignmentFromCategory = useCallback(
    async (assignment: VendorAssignment) => {
      if (!token) {
        throw new Error('Not authenticated');
      }
      const updated = await updateVendorAssignment(token, assignment._id, {
        budget_category_id: null,
      });
      setVendorAssignments(prev =>
        prev.map(item => item._id === updated._id ? updated : item)
      );
    },
    [token]
  );

  const describeVendorOption = useCallback(
    (vendor: VendorProfile): string => {
      const base = `${vendor.business_name} (${vendor.service_category})${
        vendor.is_preferred ? ' ★' : ''
      }`;
      const existing = findAssignmentForVendor(vendor._id);
      if (!existing) return base;

      const editingCategoryId = editingCategory?.id;
      if (editingCategoryId && existing.budget_category_id === editingCategoryId) {
        return `${base} - on this category`;
      }
      if (!existing.budget_category_id) {
        return `${base} - on this wedding (unlinked)`;
      }
      const otherCategory = categories.find(
        c => c.id === existing.budget_category_id
      );
      const label = otherCategory?.name || 'another category';
      return `${base} - on this wedding (${label})`;
    },
    [findAssignmentForVendor, editingCategory, categories]
  );

  // Handle vendor assignment when creating/updating category
  const handleVendorAssignment = async (categoryId: string) => {
    if (!token || !selectedWedding || !selectedVendorId) return;

    const vendor = vendorDirectory.find(v => v._id === selectedVendorId);
    if (!vendor) return;

    try {
      const existing = vendorAssignments.find(
        a => a.vendor_profile_id === selectedVendorId
          && a.wedding_id === selectedWedding
      );

      let assignment: VendorAssignment;
      if (existing) {
        if (existing.budget_category_id === categoryId) {
          return;
        }
        assignment = await updateVendorAssignment(token, existing._id, {
          budget_category_id: categoryId,
        });
      } else {
        assignment = await assignVendorToWedding(token, {
          vendor_profile_id: selectedVendorId,
          wedding_id: selectedWedding,
          budget_category_id: categoryId,
        });
      }

      setVendorAssignments(prev => {
        const filtered = prev.filter(
          a => a._id !== assignment._id
            && a.budget_category_id !== categoryId
        );
        return [...filtered, assignment];
      });
    } catch (err: any) {
      console.error('Failed to assign vendor:', err);
      const detail = err?.message || 'Vendor assignment failed';
      toast.error(`Category saved, but ${detail.toLowerCase()}`);
    }
  };

  // Bidirectional calculation handlers
  const handleBudgetAmountChange = (amount: number) => {
    const totalBudget = budgetSummary?.total_budget || 0;
    const percentage = totalBudget > 0 ? (amount / totalBudget) * 100 : 0;
    setCategoryForm({
      ...categoryForm,
      budgeted_amount: amount,
      percentage_of_total: parseFloat(percentage.toFixed(2))
    });
  };

  const handlePercentageChange = (percentage: number) => {
    const totalBudget = budgetSummary?.total_budget || 0;
    const amount = (percentage / 100) * totalBudget;
    setCategoryForm({
      ...categoryForm,
      percentage_of_total: percentage,
      budgeted_amount: parseFloat(amount.toFixed(2))
    });
  };

  const handleAddPayment = (category: BudgetCategory) => {
    setActiveCategory(category);
    setPaymentModalError('');
    setShowPaymentModal(true);
  };

  const handleRecordPayment = async (paymentData: RecordPaymentRequest) => {
    if (!token || !activeCategory) {
      toast.error('Select a wedding category before recording a payment.');
      return;
    }

    const categoryId = activeCategory.id;
    if (!categoryId) {
      toast.error('This category is missing an identifier. Please refresh and try again.');
      return;
    }

    setIsRecordingPayment(true);
    setPaymentModalError('');
    try {
      await budgetApi.recordPayment(token, categoryId, paymentData);
      toast.success('Payment recorded successfully');
      setShowPaymentModal(false);
      setActiveCategory(null);
      await fetchBudgetData();
    } catch (err: any) {
      const message = err.message || 'Failed to record payment';
      setPaymentModalError(message);
      toast.error(message);
    } finally {
      setIsRecordingPayment(false);
    }
  };

  const exportBudgetReport = async (format: 'pdf' | 'excel') => {
    if (!token || !selectedWedding) return;

    try {
      const blob = await budgetApi.getFinancialReport(token, selectedWedding, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `budget-report.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success(`Budget report exported as ${format.toUpperCase()}`);
    } catch (err: any) {
      toast.error(err.message || 'Failed to export budget report');
    }
  };

  // Filter and sort categories (computed during render, not in effect)
  const filteredCategories = useMemo(() =>
    categories
      .filter(category => {
        const matchesSearch = category.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                             (category.description || '').toLowerCase().includes(searchTerm.toLowerCase());
        const matchesStatus = statusFilter === 'all' || category.payment_status === statusFilter;
        return matchesSearch && matchesStatus;
      })
      .sort((a, b) => {
        switch (sortBy) {
          case 'name': return a.name.localeCompare(b.name);
          case 'budget': return b.budgeted_amount - a.budgeted_amount;
          case 'spent': return b.actual_spent - a.actual_spent;
          case 'priority': return a.priority - b.priority;
          default: return 0;
        }
      }), [categories, searchTerm, statusFilter, sortBy]);

  if (!token) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-wedding-navy mb-4">Access Denied</h2>
          <p>Please log in to access the budget dashboard.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Budget Management"
        description="Manage wedding budgets, track expenses, and compare vendor quotes"
      >

        {selectedWedding && (
          <Button
            onClick={() => fetchAiInsights(false)}
            disabled={aiInsightsLoading}
            className="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white"
          >
            {aiInsightsLoading ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4 mr-2" />
            )}
            AI Insights
          </Button>
        )}
        <Button onClick={() => exportBudgetReport('pdf')}>
          Export PDF
        </Button>
        <Button onClick={() => exportBudgetReport('excel')}>
          Export Excel
        </Button>
      </PageHeader>

      <div className={`grid grid-cols-1 ${showAdRail ? 'lg:grid-cols-4' : ''} gap-6`}>
      {/* Main Content — expands to full width when ad rail hidden */}
      <div className={`${showAdRail ? 'lg:col-span-3' : ''} space-y-6`}>

      {/* Wedding picker — shared compact pill (see WeddingPicker.tsx) */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-slate-500 dark:text-gray-400">Wedding:</span>
        <WeddingPicker
          options={weddings.map((w) => ({
            id: (w._id || w.id) as string,
            label: `${w.couple_names} — ${formatDate(w.date)}`,
          }))}
          value={selectedWedding}
          onChange={setSelectedWedding}
          placeholder="Choose a wedding…"
        />
      </div>

      {/* Budget Summary */}
      {budgetSummary && (
        <BudgetSummaryCard
          summary={budgetSummary}
          onSetTotalBudget={async (amount) => {
            if (!token || !selectedWedding) return;
            try {
              await budgetApi.setTotalBudget(token, selectedWedding, amount);
              toast.success('Total budget updated');
              await fetchBudgetData();
            } catch (err: any) {
              toast.error(err.message || 'Failed to update total budget');
              throw err;
            }
          }}
        />
      )}

      {/* AI Budget Insights Panel */}
      {showAiInsights && (
        <Card className="p-6 bg-gradient-to-br from-purple-50 to-indigo-50 dark:from-purple-900/20 dark:to-indigo-900/20 border-purple-200 dark:border-purple-800">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-purple-600 dark:text-purple-400" />
              <h2 className="text-lg font-semibold text-purple-900 dark:text-purple-100">
                AI Budget Insights
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <Button
                onClick={() => fetchAiInsights(true)}
                disabled={aiInsightsLoading}
                className="text-sm px-3 py-1"
              >
                {aiInsightsLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  'Refresh'
                )}
              </Button>
              <button
                onClick={() => setShowAiInsights(false)}
                className="p-1 hover:bg-purple-200 dark:hover:bg-purple-800 rounded"
              >
                <X className="w-4 h-4 text-purple-600 dark:text-purple-400" />
              </button>
            </div>
          </div>

          {/* Credits Warning */}
          {aiCreditsWarning && (
            <div className="mb-4 p-3 bg-amber-100 dark:bg-amber-900/30 border border-amber-300 dark:border-amber-700 rounded-lg flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-amber-800 dark:text-amber-200">{aiCreditsWarning}</p>
            </div>
          )}

          {/* Error State — shown as a warning banner, doesn't hide existing insights */}
          {aiInsightsError && (
            <div className="p-3 bg-amber-100 dark:bg-amber-900/30 border border-amber-300 dark:border-amber-700 rounded-lg flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0" />
                <p className="text-sm text-amber-800 dark:text-amber-200">{aiInsightsError}</p>
              </div>
              <Button
                onClick={() => fetchAiInsights(true)}
                disabled={aiInsightsLoading}
                className="text-xs px-2 py-1 ml-3"
              >
                Retry
              </Button>
            </div>
          )}

          {/* Insights List — show even when there's an error banner (previous insights still useful) */}
          {aiInsights.length > 0 && (
            <div className="space-y-4">
              {aiInsights.map((insight, index) => (
                <div
                  key={index}
                  className={`p-4 rounded-lg border ${
                    insight.priority === 'high'
                      ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
                      : insight.priority === 'medium'
                      ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800'
                      : 'bg-white dark:bg-slate-800 border-gray-200 dark:border-slate-700'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <Lightbulb className={`w-5 h-5 flex-shrink-0 mt-0.5 ${
                      insight.priority === 'high'
                        ? 'text-red-600 dark:text-red-400'
                        : insight.priority === 'medium'
                        ? 'text-amber-600 dark:text-amber-400'
                        : 'text-purple-600 dark:text-purple-400'
                    }`} />
                    <div className="flex-1">
                      {insight.category && (
                        <span className="inline-block px-2 py-0.5 text-xs font-medium bg-purple-100 dark:bg-purple-800 text-purple-700 dark:text-purple-200 rounded mb-2">
                          {insight.category}
                        </span>
                      )}
                      <p className="text-slate-800 dark:text-slate-200">{insight.insight}</p>
                      {insight.recommendation && (
                        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400 italic">
                          Recommendation: {insight.recommendation}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* No Insights */}
          {!aiInsightsError && aiInsights.length === 0 && !aiInsightsLoading && (
            <div className="text-center py-8 text-slate-600 dark:text-slate-400">
              <Lightbulb className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>No insights available yet. Add more budget data to get AI-powered recommendations.</p>
            </div>
          )}
        </Card>
      )}

      {selectedWedding && unlinkedAssignments.length > 0 && (
        <UnlinkedVendorsPanel
          unlinkedAssignments={unlinkedAssignments}
          categories={categories}
          onLinkToCategory={handleLinkUnlinkedToCategory}
          onRemoveAssignment={handleRemoveAssignment}
        />
      )}

      {/* Categories Section */}
      {selectedWedding && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[2fr_1fr] items-start">
          <div className="space-y-6">
            {/* Controls */}
            <div className="flex flex-col sm:flex-row gap-4 items-center justify-between bg-white/60 dark:bg-slate-800/60 backdrop-blur-xl border border-white/40 dark:border-slate-600 rounded-2xl p-4 shadow-md">
              <div className="flex flex-col sm:flex-row gap-4 items-center flex-1 w-full">
                {/* Search */}
                <input
                  type="text"
                  placeholder="Search categories..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full sm:w-auto flex-1 rounded-xl border border-white/60 dark:border-slate-600 bg-white/70 dark:bg-slate-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                />

                {/* Status Filter */}
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full sm:w-auto rounded-xl border border-white/60 dark:border-slate-600 bg-white/70 dark:bg-slate-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                >
                  <option value="all">All Status</option>
                  <option value="pending">Pending</option>
                  <option value="partial">Partial</option>
                  <option value="paid">Paid</option>
                  <option value="overdue">Overdue</option>
                </select>

                {/* Sort */}
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
                  className="w-full sm:w-auto rounded-xl border border-white/60 dark:border-slate-600 bg-white/70 dark:bg-slate-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                >
                  <option value="priority">Sort by Priority</option>
                  <option value="name">Sort by Name</option>
                  <option value="budget">Sort by Budget</option>
                  <option value="spent">Sort by Spent</option>
                </select>
              </div>

              <Button
                onClick={() => setShowCategoryModal(true)}
                className="whitespace-nowrap"
              >
                Add Category
              </Button>
            </div>

            {/* Categories Grid */}
            {loading ? (
              <div className="text-center py-12">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-wedding-rose"></div>
                <p className="mt-2 text-gray-600 dark:text-gray-400">Loading budget data...</p>
              </div>
            ) : error ? (
              <Card className="p-8 text-center">
                <p className="text-red-600 dark:text-red-300 mb-4">{error}</p>
                <Button onClick={fetchBudgetData}>Retry</Button>
              </Card>
            ) : filteredCategories.length === 0 ? (
              <Card className="p-8 text-center">
                <p className="text-gray-600 dark:text-gray-400 mb-4">
                  {categories.length === 0
                    ? "No budget categories found. Create your first category to get started."
                    : "No categories match your search criteria."
                  }
                </p>
                {categories.length === 0 && (
                  <Button onClick={() => setShowCategoryModal(true)}>
                    Create First Category
                  </Button>
                )}
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                {filteredCategories.map((category) => {
                  const assignment = getAssignedVendorForCategory(category.id);
                  return (
                    <BudgetCategoryCard
                      key={category.id}
                      category={category}
                      assignedVendor={assignment ? {
                        vendor_name: assignment.vendor_name,
                        vendor_email: assignment.vendor_email,
                        status: assignment.status
                      } : undefined}
                      onEdit={openEditModal}
                      onDelete={handleDeleteCategory}
                      onAddPayment={handleAddPayment}
                    />
                  );
                })}
              </div>
            )}
          </div>

          <PaymentHistoryPanel
            payments={paymentHistory}
            categories={categories}
            isLoading={paymentHistoryLoading}
            error={paymentHistoryError}
            onRefresh={() => selectedWedding && fetchPaymentHistory(selectedWedding)}
          />
        </div>
      )}

      {/* Category Modal */}
      {showCategoryModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-800 rounded-lg p-6 max-w-md w-full">
            <h2 className="text-xl font-bold mb-4 text-wedding-navy dark:text-white">
              {editingCategory ? 'Edit Category' : 'Add New Category'}
            </h2>
            <form onSubmit={editingCategory ? handleUpdateCategory : handleCreateCategory}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Category Name *
                  </label>
                  <input
                    type="text"
                    value={categoryForm.name}
                    onChange={(e) => setCategoryForm({...categoryForm, name: e.target.value})}
                    className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Description
                  </label>
                  <textarea
                    value={categoryForm.description}
                    onChange={(e) => setCategoryForm({...categoryForm, description: e.target.value})}
                    className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    rows={2}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Budget Amount *
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={categoryForm.budgeted_amount}
                    onChange={(e) => handleBudgetAmountChange(parseFloat(e.target.value) || 0)}
                    className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    required
                  />
                  {budgetSummary && budgetSummary.total_budget > 0 && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Total budget: ${budgetSummary.total_budget.toLocaleString()}
                    </p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Priority (1 = Highest, 5 = Lowest)
                  </label>
                  <select
                    value={categoryForm.priority}
                    onChange={(e) => setCategoryForm({...categoryForm, priority: parseInt(e.target.value) as 1|2|3|4|5})}
                    className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  >
                    <option value={1}>1 - Highest Priority</option>
                    <option value={2}>2 - High Priority</option>
                    <option value={3}>3 - Medium Priority</option>
                    <option value={4}>4 - Low Priority</option>
                    <option value={5}>5 - Lowest Priority</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Percentage of Total Budget
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    value={categoryForm.percentage_of_total}
                    onChange={(e) => handlePercentageChange(parseFloat(e.target.value) || 0)}
                    className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Auto-calculated based on budget amount
                  </p>
                </div>

                {/* Vendor Assignment */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Assign Vendor (Optional)
                  </label>
                  <select
                    value={selectedVendorId}
                    onChange={(e) => setSelectedVendorId(e.target.value)}
                    className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  >
                    <option value="">-- No vendor assigned --</option>
                    {vendorDirectory.map((vendor) => (
                      <option key={vendor._id} value={vendor._id}>
                        {describeVendorOption(vendor)}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Link a vendor from your directory to this budget category
                  </p>
                </div>
              </div>
              <div className="flex gap-3 mt-6">
                <Button type="submit" className="flex-1">
                  {editingCategory ? 'Update' : 'Create'} Category
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  onClick={() => {
                    setShowCategoryModal(false);
                    resetCategoryForm();
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      <RecordPaymentModal
        category={activeCategory}
        suggestedVendorName={
          activeCategory
            ? getAssignedVendorForCategory(activeCategory.id)?.vendor_name
            : undefined
        }
        isOpen={showPaymentModal}
        onClose={() => {
          setShowPaymentModal(false);
          setActiveCategory(null);
          setPaymentModalError('');
        }}
        onSubmit={handleRecordPayment}
        isSubmitting={isRecordingPayment}
        errorMessage={paymentModalError}
      />

      </div>
      {/* End lg:col-span-3 main content */}

      {/* Right Sidebar — Sponsored Vendors Rail (hidden when ads disabled) */}
      <div className={showAdRail ? 'lg:col-span-1' : 'hidden'}>
        <div className="sticky top-6">
          <CampaignSponsoredRail onVisibilityChange={setShowAdRail} />
        </div>
      </div>

      </div>
      {/* End grid */}
    </div>
  );
}
