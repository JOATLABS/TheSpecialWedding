'use client';

import { useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import BudgetProgressBar from './BudgetProgressBar';
import type { BudgetCategory } from '../../types/budget';
import { formatDate } from '@/utils/dateFormat';

interface AssignedVendor {
  vendor_name: string;
  vendor_email: string;
  status: string;
}

interface BudgetCategoryCardProps {
  category: BudgetCategory;
  assignedVendor?: AssignedVendor;
  onEdit: (category: BudgetCategory) => void;
  onDelete: (categoryId: string) => void;
  onAddPayment: (category: BudgetCategory) => void;
  className?: string;
}

export default function BudgetCategoryCard({
  category,
  assignedVendor,
  onEdit,
  onDelete,
  onAddPayment,
  className = ''
}: BudgetCategoryCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'paid': return 'text-green-600 bg-green-100 dark:text-green-400 dark:bg-green-900/40';
      case 'partial': return 'text-yellow-600 bg-yellow-100 dark:text-yellow-400 dark:bg-yellow-900/40';
      case 'overdue': return 'text-red-600 bg-red-100 dark:text-red-400 dark:bg-red-900/40';
      default: return 'text-gray-600 bg-gray-100 dark:text-gray-400 dark:bg-gray-700';
    }
  };

  const getPriorityIcon = (priority: number) => {
    const colors = {
      1: 'text-red-500',
      2: 'text-orange-500',
      3: 'text-yellow-500',
      4: 'text-blue-500',
      5: 'text-gray-500'
    };
    return colors[priority as keyof typeof colors] || 'text-gray-500';
  };

  const subcategoriesTotal = category.subcategories.reduce(
    (sum, sub) => sum + sub.actual_spent, 0
  );

  return (
    <Card className={`p-4 ${className}`}>
      {/* Header */}
      <div className="flex justify-between items-start mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-wedding-navy dark:text-white text-lg">
              {category.name}
            </h3>
            {/* Priority indicator */}
            <div className={`flex items-center ${getPriorityIcon(category.priority)}`}>
              {Array.from({ length: category.priority }, (_, i) => (
                <svg key={i} className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
              ))}
            </div>
          </div>
          {category.description && (
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">{category.description}</p>
          )}
          {/* Assigned Vendor */}
          {assignedVendor && (
            <div className="flex items-center gap-1.5 text-sm">
              <svg className="w-4 h-4 text-indigo-500 dark:text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
              <span className="text-indigo-600 dark:text-indigo-400 font-medium">
                {assignedVendor.vendor_name}
              </span>
              <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                assignedVendor.status === 'confirmed' || assignedVendor.status === 'contracted'
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400'
                  : assignedVendor.status === 'inquiry'
                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400'
                    : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-400'
              }`}>
                {assignedVendor.status}
              </span>
            </div>
          )}
        </div>
        {/* Status badge */}
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(category.payment_status)}`}>
          {category.payment_status.charAt(0).toUpperCase() + category.payment_status.slice(1)}
        </span>
      </div>

      {/* Budget progress */}
      <div className="mb-4">
        <BudgetProgressBar
          budgeted={category.budgeted_amount}
          spent={category.actual_spent}
          size="md"
        />
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-3 gap-2 mb-4 text-center text-sm">
        <div>
          <div className="font-semibold text-wedding-navy dark:text-blue-400">
            {formatCurrency(category.budgeted_amount)}
          </div>
          <div className="text-gray-600 dark:text-gray-400">Budget</div>
        </div>
        <div>
          <div className="font-semibold text-wedding-rose dark:text-rose-400">
            {formatCurrency(category.actual_spent)}
          </div>
          <div className="text-gray-600 dark:text-gray-400">Spent</div>
        </div>
        <div>
          <div className={`font-semibold ${
            category.budgeted_amount - category.actual_spent >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
          }`}>
            {formatCurrency(category.budgeted_amount - category.actual_spent)}
          </div>
          <div className="text-gray-600 dark:text-gray-400">Remaining</div>
        </div>
      </div>

      {/* Subcategories toggle */}
      {category.subcategories.length > 0 && (
        <div className="mb-4">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center text-sm text-wedding-rose hover:text-wedding-gold transition-colors"
          >
            <svg
              className={`w-4 h-4 mr-1 transform transition-transform ${
                isExpanded ? 'rotate-90' : ''
              }`}
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
            </svg>
            {category.subcategories.length} subcategories
          </button>
        </div>
      )}

      {/* Expanded subcategories */}
      {isExpanded && category.subcategories.length > 0 && (
        <div className="mb-4 pl-4 border-l-2 border-gray-200 dark:border-gray-600">
          <div className="space-y-2">
            {category.subcategories.map((subcategory) => (
              <div key={subcategory.id} className="flex justify-between items-center text-sm">
                <div className="flex-1">
                  <span className="font-medium dark:text-gray-200">{subcategory.name}</span>
                  {subcategory.notes && (
                    <span className="text-gray-500 dark:text-gray-400 ml-2">({subcategory.notes})</span>
                  )}
                </div>
                <div className="text-right">
                  <div className="font-medium dark:text-gray-200">
                    {formatCurrency(subcategory.actual_spent)} / {formatCurrency(subcategory.budgeted_amount)}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {((subcategory.actual_spent / subcategory.budgeted_amount) * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Vendor quotes indicator */}
      {category.vendor_quotes.length > 0 && (
        <div className="mb-4 p-2 bg-purple-50 dark:bg-purple-900/30 rounded-lg border border-transparent dark:border-purple-800">
          <div className="flex items-center text-sm text-purple-700 dark:text-purple-300">
            <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {category.vendor_quotes.length} vendor quotes available
          </div>
        </div>
      )}

      {/* Recent payments indicator */}
      {category.payments.length > 0 && (
        <div className="mb-4 p-2 bg-green-50 dark:bg-green-900/30 rounded-lg border border-transparent dark:border-green-800">
          <div className="text-sm text-green-700 dark:text-green-300">
            {category.payments.length} payment{category.payments.length !== 1 ? 's' : ''} recorded
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2 pt-2 border-t border-gray-200 dark:border-gray-600">
        <Button
          onClick={() => onEdit(category)}
          className="flex-1 text-sm"
        >
          Edit
        </Button>
        <Button
          onClick={() => onAddPayment(category)}
          className="flex-1 text-sm"
        >
          Add Payment
        </Button>

        <Button
          variant="danger"
          onClick={() => onDelete(category.id)}
          className="text-sm px-3"
        >
          Delete
        </Button>
      </div>

      {/* Additional info */}
      <div className="mt-2 text-xs text-gray-500 dark:text-gray-400 text-center">
        Last updated: {formatDate(category.updated_at)}
        {!!category.percentage_of_total && (
          <span className="ml-2">• {category.percentage_of_total.toFixed(1)}% of total budget</span>
        )}
      </div>
    </Card>
  );
}
