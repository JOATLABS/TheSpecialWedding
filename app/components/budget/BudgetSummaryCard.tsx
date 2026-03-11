'use client';

import { useState, useRef, useEffect } from 'react';
import { Card } from '../ui/Card';
import BudgetProgressBar from './BudgetProgressBar';
import type { BudgetSummary } from '../../types/budget';
import { formatDate } from '@/utils/dateFormat';
import { Pencil, Check, X } from 'lucide-react';

interface BudgetSummaryCardProps {
  summary: BudgetSummary;
  className?: string;
  onSetTotalBudget?: (amount: number) => Promise<void>;
}

export default function BudgetSummaryCard({ summary, className = '', onSetTotalBudget }: BudgetSummaryCardProps) {
  const [isEditingBudget, setIsEditingBudget] = useState(false);
  const [budgetInput, setBudgetInput] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditingBudget && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditingBudget]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatPercentage = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
  };

  const getVarianceColor = (percentage: number) => {
    if (percentage > 10) return 'text-red-600';
    if (percentage > 5) return 'text-yellow-600';
    if (percentage < -5) return 'text-green-600';
    return 'text-wedding-navy';
  };

  const handleEditBudget = () => {
    setBudgetInput(summary.total_budget.toString());
    setIsEditingBudget(true);
  };

  const handleCancelEdit = () => {
    setIsEditingBudget(false);
    setBudgetInput('');
  };

  const handleSaveBudget = async () => {
    const amount = parseFloat(budgetInput);
    if (isNaN(amount) || amount < 0 || !onSetTotalBudget) return;

    setIsSaving(true);
    try {
      await onSetTotalBudget(amount);
      setIsEditingBudget(false);
    } catch {
      // Error handled by parent
    } finally {
      setIsSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSaveBudget();
    if (e.key === 'Escape') handleCancelEdit();
  };

  return (
    <Card className={`p-6 ${className}`}>
      <div className="flex justify-between items-start mb-6">
        <h2 className="text-2xl font-heading font-bold text-wedding-navy dark:text-white">
          Budget Overview
        </h2>
        <div className="text-right">
          <div className="text-sm text-gray-600 dark:text-gray-400">Last Updated</div>
          <div className="text-sm font-medium dark:text-gray-200">
            {formatDate(summary.last_updated)}
          </div>
        </div>
      </div>

      {/* Main budget progress */}
      <div className="mb-6">
        <BudgetProgressBar
          budgeted={summary.total_budget}
          spent={summary.total_spent}
          size="lg"
        />
      </div>

      {/* Key metrics grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {/* Total Budget — editable */}
        <div className="text-center p-4 bg-gray-50 dark:bg-slate-700/50 rounded-lg border border-transparent dark:border-slate-600 relative group">
          {isEditingBudget ? (
            <div className="flex flex-col items-center gap-2">
              <div className="flex items-center gap-1">
                <span className="text-lg font-bold text-wedding-navy dark:text-blue-400">$</span>
                <input
                  ref={inputRef}
                  type="number"
                  min="0"
                  step="100"
                  value={budgetInput}
                  onChange={(e) => setBudgetInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={isSaving}
                  className="w-28 text-center text-lg font-bold text-wedding-navy dark:text-blue-400 bg-white dark:bg-slate-600 border border-wedding-rose rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                />
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={handleSaveBudget}
                  disabled={isSaving}
                  className="p-1 rounded bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400 hover:bg-green-200 dark:hover:bg-green-900/60 transition-colors"
                  title="Save"
                >
                  <Check className="w-4 h-4" />
                </button>
                <button
                  onClick={handleCancelEdit}
                  disabled={isSaving}
                  className="p-1 rounded bg-gray-100 dark:bg-slate-600 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-slate-500 transition-colors"
                  title="Cancel"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="text-2xl font-bold text-wedding-navy dark:text-blue-400">
                {formatCurrency(summary.total_budget)}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400 flex items-center justify-center gap-1">
                Total Budget
                {onSetTotalBudget && (
                  <button
                    onClick={handleEditBudget}
                    className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-gray-200 dark:hover:bg-slate-600"
                    title="Edit total budget"
                  >
                    <Pencil className="w-3.5 h-3.5 text-wedding-rose" />
                  </button>
                )}
              </div>
            </>
          )}
        </div>
        <div className="text-center p-4 bg-gray-50 dark:bg-slate-700/50 rounded-lg border border-transparent dark:border-slate-600">
          <div className="text-2xl font-bold text-wedding-rose dark:text-rose-400">
            {formatCurrency(summary.total_spent)}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Total Spent</div>
        </div>
        <div className="text-center p-4 bg-gray-50 dark:bg-slate-700/50 rounded-lg border border-transparent dark:border-slate-600">
          <div className="text-2xl font-bold text-wedding-gold dark:text-yellow-400">
            {formatCurrency(summary.total_committed)}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Committed</div>
        </div>
        <div className="text-center p-4 bg-gray-50 dark:bg-slate-700/50 rounded-lg border border-transparent dark:border-slate-600">
          <div className={`text-2xl font-bold ${
            summary.remaining_budget >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
          }`}>
            {formatCurrency(summary.remaining_budget)}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Remaining</div>
        </div>
      </div>

      {/* Budget variance indicator */}
      {summary.budget_variance !== 0 && (
        <div className="mb-6 p-4 bg-gray-50 dark:bg-slate-700/50 rounded-lg border border-transparent dark:border-slate-600">
          <div className="flex items-center justify-between">
            <span className="font-medium text-wedding-navy dark:text-gray-200">Budget Variance:</span>
            <div className="text-right">
              <div className={`text-lg font-bold ${getVarianceColor(summary.variance_percentage)}`}>
                {formatCurrency(Math.abs(summary.budget_variance))}
                <span className="text-sm ml-1">
                  ({formatPercentage(summary.variance_percentage)})
                </span>
              </div>
              <div className="text-xs text-gray-600 dark:text-gray-400">
                {summary.budget_variance > 0 ? 'Over Budget' : 'Under Budget'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Category and payment status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
        <div className="p-3 bg-blue-50 dark:bg-blue-900/30 rounded-lg border border-transparent dark:border-blue-800">
          <div className="text-xl font-bold text-blue-600 dark:text-blue-400">
            {summary.categories_count}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Categories</div>
        </div>
        <div className="p-3 bg-green-50 dark:bg-green-900/30 rounded-lg border border-transparent dark:border-green-800">
          <div className="text-xl font-bold text-green-600 dark:text-green-400">
            {summary.paid_categories}
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">Paid Categories</div>
        </div>
        {summary.overdue_categories > 0 && (
          <div className="p-3 bg-red-50 dark:bg-red-900/30 rounded-lg border border-transparent dark:border-red-800">
            <div className="text-xl font-bold text-red-600 dark:text-red-400">
              {summary.overdue_categories}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Overdue</div>
          </div>
        )}
        {summary.vendor_quotes_count > 0 && (
          <div className="p-3 bg-purple-50 dark:bg-purple-900/30 rounded-lg border border-transparent dark:border-purple-800">
            <div className="text-xl font-bold text-purple-600 dark:text-purple-400">
              {summary.vendor_quotes_count}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">Vendor Quotes</div>
          </div>
        )}
      </div>

      {/* Action indicators */}
      {(summary.overdue_categories > 0 || summary.variance_percentage > 10) && (
        <div className="mt-4 p-3 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-800 rounded-lg">
          <div className="flex items-center">
            <svg className="w-5 h-5 text-yellow-600 dark:text-yellow-400 mr-2" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <span className="text-yellow-800 dark:text-yellow-200 font-medium">
              Action Required:
              {summary.overdue_categories > 0 && ' Overdue payments detected.'}
              {summary.variance_percentage > 10 && ' Budget significantly exceeded.'}
            </span>
          </div>
        </div>
      )}
    </Card>
  );
}
