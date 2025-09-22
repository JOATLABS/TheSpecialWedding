'use client';

import { Card } from '@/components/ui/Card';
import BudgetProgressBar from './BudgetProgressBar';
import type { BudgetSummary } from '@/types/budget';

interface BudgetSummaryCardProps {
  summary: BudgetSummary;
  className?: string;
}

export default function BudgetSummaryCard({ summary, className = '' }: BudgetSummaryCardProps) {
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

  return (
    <Card className={`p-6 ${className}`}>
      <div className="flex justify-between items-start mb-6">
        <h2 className="text-2xl font-heading font-bold text-wedding-navy">
          Budget Overview
        </h2>
        <div className="text-right">
          <div className="text-sm text-gray-600">Last Updated</div>
          <div className="text-sm font-medium">
            {new Date(summary.last_updated).toLocaleDateString()}
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
        <div className="text-center p-4 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-wedding-navy">
            {formatCurrency(summary.total_budget)}
          </div>
          <div className="text-sm text-gray-600">Total Budget</div>
        </div>
        
        <div className="text-center p-4 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-wedding-rose">
            {formatCurrency(summary.total_spent)}
          </div>
          <div className="text-sm text-gray-600">Total Spent</div>
        </div>
        
        <div className="text-center p-4 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-wedding-gold">
            {formatCurrency(summary.total_committed)}
          </div>
          <div className="text-sm text-gray-600">Committed</div>
        </div>
        
        <div className="text-center p-4 bg-gray-50 rounded-lg">
          <div className={`text-2xl font-bold ${
            summary.remaining_budget >= 0 ? 'text-green-600' : 'text-red-600'
          }`}>
            {formatCurrency(summary.remaining_budget)}
          </div>
          <div className="text-sm text-gray-600">Remaining</div>
        </div>
      </div>

      {/* Budget variance indicator */}
      {summary.budget_variance !== 0 && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="font-medium text-wedding-navy">Budget Variance:</span>
            <div className="text-right">
              <div className={`text-lg font-bold ${getVarianceColor(summary.variance_percentage)}`}>
                {formatCurrency(Math.abs(summary.budget_variance))} 
                <span className="text-sm ml-1">
                  ({formatPercentage(summary.variance_percentage)})
                </span>
              </div>
              <div className="text-xs text-gray-600">
                {summary.budget_variance > 0 ? 'Over Budget' : 'Under Budget'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Category and payment status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
        <div className="p-3 bg-blue-50 rounded-lg">
          <div className="text-xl font-bold text-blue-600">
            {summary.categories_count}
          </div>
          <div className="text-sm text-gray-600">Categories</div>
        </div>
        
        <div className="p-3 bg-green-50 rounded-lg">
          <div className="text-xl font-bold text-green-600">
            {summary.paid_categories}
          </div>
          <div className="text-sm text-gray-600">Paid Categories</div>
        </div>
        
        {summary.overdue_categories > 0 && (
          <div className="p-3 bg-red-50 rounded-lg">
            <div className="text-xl font-bold text-red-600">
              {summary.overdue_categories}
            </div>
            <div className="text-sm text-gray-600">Overdue</div>
          </div>
        )}
        
        {summary.vendor_quotes_count > 0 && (
          <div className="p-3 bg-purple-50 rounded-lg">
            <div className="text-xl font-bold text-purple-600">
              {summary.vendor_quotes_count}
            </div>
            <div className="text-sm text-gray-600">Vendor Quotes</div>
          </div>
        )}
      </div>

      {/* Action indicators */}
      {(summary.overdue_categories > 0 || summary.variance_percentage > 10) && (
        <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="flex items-center">
            <svg className="w-5 h-5 text-yellow-600 mr-2" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <span className="text-yellow-800 font-medium">
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