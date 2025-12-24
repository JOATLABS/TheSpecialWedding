'use client';

import { useMemo } from 'react';

interface BudgetProgressBarProps {
  budgeted: number;
  spent: number;
  className?: string;
  showLabels?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export default function BudgetProgressBar({
  budgeted,
  spent,
  className = '',
  showLabels = true,
  size = 'md'
}: BudgetProgressBarProps) {
  const percentage = budgeted > 0 ? Math.min((spent / budgeted) * 100, 100) : 0;
  const isOverBudget = spent > budgeted;
  const remaining = budgeted - spent;
  // Color scheme based on percentage
  const getBarColor = () => {
    if (isOverBudget) return 'bg-red-500';
    if (percentage > 90) return 'bg-yellow-500';
    if (percentage > 75) return 'bg-wedding-gold';
    return 'bg-wedding-rose';
  };

  // Size variants
  const sizeClasses = {
    sm: 'h-2',
    md: 'h-3',
    lg: 'h-4'
  };

  const currencyFormatter = useMemo(() => new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }), []);

  const formatCurrency = (amount: number) => currencyFormatter.format(amount);

  return (
    <div className={`w-full ${className}`}>
      {showLabels && (
        <div className="flex justify-between items-center text-sm text-wedding-navy dark:text-gray-300 mb-2">
          <span>Spent: {formatCurrency(spent)}</span>
          <span>Budget: {formatCurrency(budgeted)}</span>
        </div>
      )}
      <div className="relative">
        {/* Background bar */}
        <div className={`w-full ${sizeClasses[size]} bg-gray-200 dark:bg-slate-600 rounded-full overflow-hidden`}>
          {/* Progress bar */}
          <div
            className={`${sizeClasses[size]} ${getBarColor()} transition-all duration-300 ease-in-out rounded-full`}
            style={{ width: `${Math.min(percentage, 100)}%` }}
          />
          {/* Over-budget indicator */}
          {isOverBudget && (
            <div
              className="absolute top-0 left-0 h-full bg-red-600 opacity-30"
              style={{ width: '100%' }}
            />
          )}
        </div>
        {/* Percentage label */}
        {showLabels && (
          <div className="flex justify-between items-center mt-2 text-xs">
            <span className={`font-medium ${isOverBudget ? 'text-red-600 dark:text-red-400' : 'text-wedding-navy dark:text-gray-300'}`}>
              {percentage.toFixed(1)}% used
            </span>
            {remaining >= 0 ? (
              <span className="text-green-600 dark:text-green-400">
                {formatCurrency(remaining)} remaining
              </span>
            ) : (
              <span className="text-red-600 dark:text-red-400 font-medium">
                {formatCurrency(Math.abs(remaining))} over budget
              </span>
            )}
          </div>
        )}
      </div>
      {/* Warning indicator for high usage */}
      {percentage > 90 && !isOverBudget && showLabels && (
        <div className="flex items-center mt-1 text-xs text-yellow-600 dark:text-yellow-400">
          <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          Approaching budget limit
        </div>
      )}
    </div>
  );
}