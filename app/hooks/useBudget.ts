import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { budgetApi } from '../services/budgetApi';
import type { BudgetCategory, BudgetSummary } from '../types/budget';

interface UseBudgetOptions {
  token: string | null;
  weddingId: string;
}

interface UseBudgetReturn {
  categories: BudgetCategory[];
  summary: BudgetSummary | null;
  loading: boolean;
  error: string;
  refreshData: () => Promise<void>;
  createCategory: (data: any) => Promise<void>;
  updateCategory: (categoryId: string, data: any) => Promise<void>;
  deleteCategory: (categoryId: string) => Promise<void>;
}

export function useBudget({ token, weddingId }: UseBudgetOptions): UseBudgetReturn {
  const [categories, setCategories] = useState<BudgetCategory[]>([]);
  const [summary, setSummary] = useState<BudgetSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  const refreshData = useCallback(async () => {
    if (!token || !weddingId) return;
    
    setLoading(true);
    try {
      const [summaryData, categoriesData] = await Promise.all([
        budgetApi.getBudgetSummary(token, weddingId),
        budgetApi.getBudgetCategories(token, weddingId)
      ]);
      
      setSummary(summaryData);
      setCategories(categoriesData);
      setError('');
    } catch (err: any) {
      const errorMessage = err.message || 'Failed to load budget data';
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [token, weddingId]);

  const createCategory = useCallback(async (data: any) => {
    if (!token) return;

    try {
      const categoryData = { wedding_id: weddingId, ...data };
      const newCategory = await budgetApi.createBudgetCategory(token, categoryData);
      setCategories(prev => [...prev, newCategory]);
      toast.success('Budget category created successfully');
      await refreshData(); // Refresh to update summary
    } catch (err: any) {
      toast.error(err.message || 'Failed to create budget category');
      throw err;
    }
  }, [token, weddingId, refreshData]);

  const updateCategory = useCallback(async (categoryId: string, data: any) => {
    if (!token) return;

    try {
      const updatedCategory = await budgetApi.updateBudgetCategory(token, categoryId, data);
      setCategories(prev => prev.map(cat => 
        cat.id === categoryId ? updatedCategory : cat
      ));
      toast.success('Budget category updated successfully');
      await refreshData(); // Refresh to update summary
    } catch (err: any) {
      toast.error(err.message || 'Failed to update budget category');
      throw err;
    }
  }, [token, refreshData]);

  const deleteCategory = useCallback(async (categoryId: string) => {
    if (!token) return;

    try {
      await budgetApi.deleteBudgetCategory(token, categoryId);
      setCategories(prev => prev.filter(cat => cat.id !== categoryId));
      toast.success('Budget category deleted successfully');
      await refreshData(); // Refresh to update summary
    } catch (err: any) {
      toast.error(err.message || 'Failed to delete budget category');
      throw err;
    }
  }, [token, refreshData]);

  useEffect(() => {
    if (token && weddingId) {
      refreshData();
    }
  }, [refreshData, token, weddingId]);

  return {
    categories,
    summary,
    loading,
    error,
    refreshData,
    createCategory,
    updateCategory,
    deleteCategory,
  };
}