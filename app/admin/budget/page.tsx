'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import BudgetSummaryCard from '../../components/budget/BudgetSummaryCard';
import BudgetCategoryCard from '../../components/budget/BudgetCategoryCard';
import PaymentHistoryPanel from '../../components/budget/PaymentHistoryPanel';
import RecordPaymentModal from '../../components/budget/RecordPaymentModal';
import { budgetApi } from '../../services/budgetApi';
import { formatDate } from '@/utils/dateFormat';
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

export default function BudgetDashboard() {
  const { token } = useAdmin();
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

  const fetchWeddings = useCallback(async () => {
    if (!token) {
      setWeddings([]);
      return;
    }

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
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

  const fetchPaymentHistory = useCallback(
    async (weddingId: string) => {
      if (!token) return;

      setPaymentHistoryLoading(true);
      try {
        const paymentData = await budgetApi.getPaymentHistory(token, weddingId);
        setPaymentHistory(paymentData);
        setPaymentHistoryError('');
      } catch (err: any) {
        const message = err.message || 'Failed to load payment history';
        setPaymentHistoryError(message);
        setPaymentHistory([]);
        toast.error(message);
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
      const [summaryData, categoriesData] = await Promise.all([
        budgetApi.getBudgetSummary(token, selectedWedding),
        budgetApi.getBudgetCategories(token, selectedWedding),
      ]);

      setBudgetSummary(summaryData);
      setCategories(categoriesData);
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

    const categoryId = activeCategory.id || activeCategory._id;
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
      throw new Error(message);
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
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-heading font-bold text-wedding-navy">
            Budget Management
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Manage wedding budgets, track expenses, and compare vendor quotes
          </p>
        </div>
        <div className="flex gap-3">
          <Button onClick={() => exportBudgetReport('pdf')}>
            Export PDF
          </Button>
          <Button onClick={() => exportBudgetReport('excel')}>
            Export Excel
          </Button>
        </div>
      </div>

      {/* Wedding Selection */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row gap-4 items-center">
          <label className="font-medium text-wedding-navy whitespace-nowrap">
            Select Wedding:
          </label>
          <select
            value={selectedWedding}
            onChange={(e) => setSelectedWedding(e.target.value)}
            className="flex-1 p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
          >
            <option value="">Choose a wedding...</option>
            {weddings.map((wedding) => (
              <option key={wedding._id || wedding.id} value={wedding._id || wedding.id}>
                {wedding.couple_names} - {formatDate(wedding.date)}
              </option>
            ))}
          </select>
        </div>
      </Card>

      {/* Budget Summary */}
      {budgetSummary && (
        <BudgetSummaryCard summary={budgetSummary} />
      )}

      {/* Categories Section */}
      {selectedWedding && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[2fr_1fr] items-start">
          <div className="space-y-6">
            {/* Controls */}
            <div className="flex flex-col sm:flex-row gap-4 items-center justify-between bg-white/60 backdrop-blur-xl border border-white/40 rounded-2xl p-4 shadow-md">
              <div className="flex flex-col sm:flex-row gap-4 items-center flex-1 w-full">
                {/* Search */}
                <input
                  type="text"
                  placeholder="Search categories..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full sm:w-auto flex-1 rounded-xl border border-white/60 bg-white/70 px-3 py-2 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                />

                {/* Status Filter */}
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full sm:w-auto rounded-xl border border-white/60 bg-white/70 px-3 py-2 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
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
                  className="w-full sm:w-auto rounded-xl border border-white/60 bg-white/70 px-3 py-2 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
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
                {filteredCategories.map((category) => (
                  <BudgetCategoryCard
                    key={category.id || category._id}
                    category={category}
                    onEdit={openEditModal}
                    onDelete={handleDeleteCategory}
                    onAddPayment={handleAddPayment}
                  />
                ))}
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
            <h2 className="text-xl font-bold mb-4 text-wedding-navy">
              {editingCategory ? 'Edit Category' : 'Add New Category'}
            </h2>
            <form onSubmit={editingCategory ? handleUpdateCategory : handleCreateCategory}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                    Category Name *
                  </label>
                  <input
                    type="text"
                    value={categoryForm.name}
                    onChange={(e) => setCategoryForm({...categoryForm, name: e.target.value})}
                    className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                    Description
                  </label>
                  <textarea
                    value={categoryForm.description}
                    onChange={(e) => setCategoryForm({...categoryForm, description: e.target.value})}
                    className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    rows={2}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                    Budget Amount *
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={categoryForm.budgeted_amount}
                    onChange={(e) => handleBudgetAmountChange(parseFloat(e.target.value) || 0)}
                    className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    required
                  />
                  {budgetSummary && budgetSummary.total_budget > 0 && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Total budget: ${budgetSummary.total_budget.toLocaleString()}
                    </p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                    Priority (1 = Highest, 5 = Lowest)
                  </label>
                  <select
                    value={categoryForm.priority}
                    onChange={(e) => setCategoryForm({...categoryForm, priority: parseInt(e.target.value) as 1|2|3|4|5})}
                    className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  >
                    <option value={1}>1 - Highest Priority</option>
                    <option value={2}>2 - High Priority</option>
                    <option value={3}>3 - Medium Priority</option>
                    <option value={4}>4 - Low Priority</option>
                    <option value={5}>5 - Lowest Priority</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                    Percentage of Total Budget
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    value={categoryForm.percentage_of_total}
                    onChange={(e) => handlePercentageChange(parseFloat(e.target.value) || 0)}
                    className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-md focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    Auto-calculated based on budget amount
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
  );
}