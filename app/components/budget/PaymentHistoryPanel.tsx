'use client';

import { useMemo, useState } from 'react';
import type { BudgetCategory, PaymentRecord } from '../../types/budget';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { formatDate } from '@/utils/dateFormat';

interface PaymentHistoryPanelProps {
  payments: PaymentRecord[];
  categories: BudgetCategory[];
  isLoading: boolean;
  error?: string;
  onRefresh?: () => void;
  onEditPayment?: (payment: PaymentRecord) => void;
  onDeletePayment?: (payment: PaymentRecord) => void;
}

type PaymentMethodFilter = 'all' | PaymentRecord['payment_method'];
type PaymentStatusFilter = 'all' | NonNullable<PaymentRecord['status']>;

const methodLabels: Record<PaymentRecord['payment_method'], string> = {
  card: 'Card',
  cash: 'Cash',
  check: 'Check',
  transfer: 'Bank Transfer',
};

const statusLabels: Record<NonNullable<PaymentRecord['status']>, string> = {
  completed: 'Completed',
  pending: 'Pending',
  failed: 'Failed',
};

function formatCurrency(amount: number) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}

export function PaymentHistoryPanel({
  payments,
  categories,
  isLoading,
  error,
  onRefresh,
  onEditPayment,
  onDeletePayment,
}: PaymentHistoryPanelProps) {
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [methodFilter, setMethodFilter] = useState<PaymentMethodFilter>('all');
  const [statusFilter, setStatusFilter] = useState<PaymentStatusFilter>('all');
  const [searchTerm, setSearchTerm] = useState('');

  const categoryLookup = useMemo(() => {
    const map = new Map<string, string>();
    categories.forEach((category) => {
      map.set(category.id, category.name);
      if (category._id && !map.has(category._id)) {
        map.set(category._id, category.name);
      }
    });
    return map;
  }, [categories]);

  const resolvedPayments = useMemo(() => {
    return payments
      .map((payment) => ({
        ...payment,
        category_name:
          payment.category_name || categoryLookup.get(payment.category_id) || 'Unknown category',
      }))
      .sort((a, b) => new Date(b.payment_date).getTime() - new Date(a.payment_date).getTime());
  }, [payments, categoryLookup]);

  const filteredPayments = useMemo(() => {
    return resolvedPayments.filter((payment) => {
      if (categoryFilter !== 'all') {
        const selectedCategoryName = categoryLookup.get(categoryFilter);
        if (payment.category_id !== categoryFilter && payment.category_name !== selectedCategoryName) {
          return false;
        }
      }

      if (methodFilter !== 'all' && payment.payment_method !== methodFilter) {
        return false;
      }

      if (statusFilter !== 'all' && payment.status !== statusFilter) {
        return false;
      }

      if (searchTerm.trim().length > 0) {
        const haystack = [
          payment.vendor_name,
          payment.description,
          payment.notes,
          payment.category_name,
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();

        if (!haystack.includes(searchTerm.trim().toLowerCase())) {
          return false;
        }
      }

      return true;
    });
  }, [categoryFilter, categoryLookup, methodFilter, resolvedPayments, searchTerm, statusFilter]);

  const summary = useMemo(() => {
    const totalRecorded = payments.reduce((acc, payment) => acc + (payment.amount || 0), 0);
    const totalCompleted = payments
      .filter((payment) => payment.status === 'completed' || payment.status === undefined)
      .reduce((acc, payment) => acc + payment.amount, 0);
    const totalPending = payments
      .filter((payment) => payment.status === 'pending')
      .reduce((acc, payment) => acc + payment.amount, 0);
    const lastPayment = resolvedPayments[0];

    return {
      totalRecorded,
      totalCompleted,
      totalPending,
      lastPaymentLabel: lastPayment
        ? `${formatCurrency(lastPayment.amount)} • ${formatDate(lastPayment.payment_date)}`
        : 'No payments logged yet',
    };
  }, [payments, resolvedPayments]);

  return (
    <Card className="p-0 overflow-hidden">
      <div className="bg-gradient-to-br from-white/80 via-white/70 to-white/50 dark:from-slate-800/80 dark:via-slate-800/70 dark:to-slate-800/50 backdrop-blur-xl p-6 space-y-6">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-wedding-navy dark:text-white">Payment history</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">Audit every vendor transaction and monitor outstanding balances.</p>
          </div>
          {onRefresh && (
            <Button type="button" onClick={onRefresh} className="self-start sm:self-auto">
              Refresh
            </Button>
          )}
        </header>

        <section className="grid grid-cols-1 gap-4 rounded-2xl border border-white/40 dark:border-slate-600 bg-white/60 dark:bg-slate-700/60 p-4 text-sm text-gray-700 dark:text-gray-300 shadow-inner">
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Recorded</span>
            <span className="text-base font-semibold text-wedding-navy dark:text-blue-400">{formatCurrency(summary.totalRecorded)}</span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Cleared</span>
            <span className="text-base font-semibold text-emerald-600 dark:text-emerald-400">{formatCurrency(summary.totalCompleted)}</span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Pending</span>
            <span className="text-base font-semibold text-amber-600 dark:text-amber-400">{formatCurrency(summary.totalPending)}</span>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Last payment</span>
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{summary.lastPaymentLabel}</span>
          </div>
        </section>

        <section className="space-y-4">
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-1">
            <input
              type="search"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search vendor, notes, or category"
              className="w-full rounded-xl border border-white/60 dark:border-slate-600 bg-white/70 dark:bg-slate-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
            />
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 xl:grid-cols-1">
              <select
                value={categoryFilter}
                onChange={(event) => setCategoryFilter(event.target.value)}
                className="w-full rounded-xl border border-white/60 dark:border-slate-600 bg-white/70 dark:bg-slate-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
              >
                <option value="all">All categories</option>
                {categories.map((category) => {
                  const optionValue = category.id || category._id;
                  if (!optionValue) {
                    return null;
                  }
                  return (
                    <option key={optionValue} value={optionValue}>
                      {category.name}
                    </option>
                  );
                })}
              </select>

              <select
                value={methodFilter}
                onChange={(event) => setMethodFilter(event.target.value as PaymentMethodFilter)}
                className="w-full rounded-xl border border-white/60 dark:border-slate-600 bg-white/70 dark:bg-slate-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
              >
                <option value="all">All methods</option>
                {Object.entries(methodLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>

              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as PaymentStatusFilter)}
                className="w-full rounded-xl border border-white/60 dark:border-slate-600 bg-white/70 dark:bg-slate-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
              >
                <option value="all">All statuses</option>
                {Object.entries(statusLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="max-h-[420px] space-y-3 overflow-y-auto pr-2">
            {isLoading && (
              <div className="space-y-3" role="status" aria-live="polite">
                {Array.from({ length: 3 }).map((_, index) => (
                  <div
                    key={index}
                    className="h-20 animate-pulse rounded-2xl bg-white/60 dark:bg-slate-700/60"
                  />
                ))}
                <span className="sr-only">Loading payment history…</span>
              </div>
            )}

            {!isLoading && error && (
              <div className="rounded-2xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-300" role="alert">
                {error}
              </div>
            )}

            {!isLoading && !error && filteredPayments.length === 0 && (
              <div className="rounded-2xl border border-white/40 dark:border-slate-600 bg-white/60 dark:bg-slate-700/60 p-6 text-center text-sm text-gray-600 dark:text-gray-400">
                <p>No payments match the current filters.</p>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-500">Try resetting your filters or log a new payment to get started.</p>
              </div>
            )}

            {!isLoading && !error && filteredPayments.length > 0 && (
              <ul className="space-y-3" aria-live="polite">
                {filteredPayments.map((payment) => (
                  <li
                    key={payment.id}
                    className="rounded-2xl border border-white/40 dark:border-slate-600 bg-white/70 dark:bg-slate-700/70 p-4 shadow-sm"
                  >
                    <div className="flex flex-col gap-2">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-sm font-semibold text-wedding-navy dark:text-white">{payment.category_name}</p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            {formatDate(payment.payment_date, {
                              month: 'short',
                              day: 'numeric',
                              year: 'numeric',
                            })}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-base font-semibold text-wedding-rose dark:text-rose-400">{formatCurrency(payment.amount)}</p>
                          <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                            {methodLabels[payment.payment_method]} · {statusLabels[payment.status || 'completed']}
                          </p>
                        </div>
                      </div>

                      {(payment.vendor_name || payment.description) && (
                        <div className="rounded-xl border border-white/40 dark:border-slate-600 bg-white/60 dark:bg-slate-600/60 p-3 text-sm text-gray-700 dark:text-gray-300">
                          {payment.vendor_name && (
                            <p className="font-medium text-wedding-navy dark:text-white">{payment.vendor_name}</p>
                          )}
                          {payment.description && (
                            <p className="mt-1 leading-relaxed">{payment.description}</p>
                          )}
                        </div>
                      )}

                      {payment.notes && (
                        <p className="text-xs text-gray-500 dark:text-gray-400">{payment.notes}</p>
                      )}

                      {payment.receipt_url && (
                        <a
                          href={payment.receipt_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sm font-medium text-wedding-rose dark:text-rose-400 underline underline-offset-2"
                        >
                          View receipt
                        </a>
                      )}

                      {(onEditPayment || onDeletePayment) && (
                        <div className="flex items-center gap-2 pt-2 border-t border-white/30 dark:border-slate-600">
                          {onEditPayment && (
                            <button
                              type="button"
                              onClick={() => onEditPayment(payment)}
                              className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 transition-colors"
                            >
                              Edit
                            </button>
                          )}
                          {onDeletePayment && (
                            <button
                              type="button"
                              onClick={() => onDeletePayment(payment)}
                              className="text-xs font-medium text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 transition-colors"
                            >
                              Delete
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </Card>
  );
}

export default PaymentHistoryPanel;
