'use client';

import dynamic from 'next/dynamic';
import LoadingSpinner from '@/components/LoadingSpinner';

// Lazy load budget components for better performance
export const LazyBudgetSummaryCard = dynamic(
  () => import('./BudgetSummaryCard'),
  { 
    loading: () => <LoadingSpinner message="Loading budget summary..." />,
    ssr: false 
  }
);

export const LazyBudgetCategoryCard = dynamic(
  () => import('./BudgetCategoryCard'),
  { 
    loading: () => <LoadingSpinner size="sm" message="" />,
    ssr: false 
  }
);

export const LazyVendorQuoteCard = dynamic(
  () => import('./VendorQuoteCard'),
  { 
    loading: () => <LoadingSpinner size="sm" message="" />,
    ssr: false 
  }
);