'use client';

import { useEffect, useMemo, useState } from 'react';
import type { BudgetCategory, RecordPaymentRequest } from '../../types/budget';
import { Button } from '../ui/Button';
import { getLocalDateString } from '../../utils/dateFormat';

export interface PaymentFormValues {
  vendorName: string;
  amount: string;
  paymentMethod: RecordPaymentRequest['payment_method'];
  paymentDate: string;
  description: string;
  receiptUrl: string;
  status: RecordPaymentRequest['status'];
  notes: string;
}

const paymentMethodOptions: Array<{ value: RecordPaymentRequest['payment_method']; label: string }> = [
  { value: 'card', label: 'Card' },
  { value: 'transfer', label: 'Bank Transfer' },
  { value: 'check', label: 'Check' },
  { value: 'cash', label: 'Cash' }
];

const statusOptions: Array<{ value: NonNullable<RecordPaymentRequest['status']>; label: string }> = [
  { value: 'completed', label: 'Completed' },
  { value: 'pending', label: 'Pending' },
  { value: 'failed', label: 'Failed' }
];

interface RecordPaymentModalProps {
  category: BudgetCategory | null;
  suggestedVendorName?: string;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: RecordPaymentRequest) => Promise<void> | void;
  isSubmitting?: boolean;
  errorMessage?: string;
}

const defaultFormState = (): PaymentFormValues => ({
  vendorName: '',
  amount: '',
  paymentMethod: 'card',
  paymentDate: getLocalDateString(),
  description: '',
  receiptUrl: '',
  status: 'completed',
  notes: ''
});

export function RecordPaymentModal({
  category,
  suggestedVendorName,
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
  errorMessage,
}: RecordPaymentModalProps) {
  const [formState, setFormState] = useState<PaymentFormValues>(defaultFormState);
  const [localError, setLocalError] = useState<string>('');

  useEffect(() => {
    if (isOpen) {
      const frame = window.requestAnimationFrame(() => {
        setFormState({
          ...defaultFormState(),
          vendorName: suggestedVendorName || '',
        });
        setLocalError('');
      });

      return () => window.cancelAnimationFrame(frame);
    }
  }, [isOpen, category?.id, suggestedVendorName]);

  const remainingBudget = useMemo(() => {
    if (!category) return null;
    const remaining = category.budgeted_amount - category.actual_spent;
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(Math.max(remaining, 0));
  }, [category]);

  const handleChange = <Key extends keyof PaymentFormValues>(field: Key, value: PaymentFormValues[Key]) => {
    setFormState((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLocalError('');

    if (!category) {
      setLocalError('Select a budget category before recording a payment.');
      return;
    }

    const parsedAmount = parseFloat(formState.amount);
    if (Number.isNaN(parsedAmount) || parsedAmount <= 0) {
      setLocalError('Enter a valid payment amount greater than zero.');
      return;
    }

    if (!formState.paymentDate) {
      setLocalError('Choose the payment date.');
      return;
    }

    const paymentRequest: RecordPaymentRequest = {
      amount: parsedAmount,
      payment_method: formState.paymentMethod,
      payment_date: new Date(formState.paymentDate).toISOString(),
      vendor_name: formState.vendorName.trim() || undefined,
      description: formState.description.trim() || undefined,
      receipt_url: formState.receiptUrl.trim() || undefined,
      status: formState.status || 'completed',
      notes: formState.notes.trim() || undefined,
    };

    try {
      await onSubmit(paymentRequest);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to save payment.';
      setLocalError(message);
    }
  };

  if (!isOpen) {
    return null;
  }

  const modalTitle = category ? `Record payment for ${category.name}` : 'Record payment';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 backdrop-blur-sm px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="record-payment-title"
    >
      <div className="relative max-w-2xl w-full">
        <div className="absolute inset-0 bg-white/60 dark:bg-slate-900/40 rounded-3xl blur-3xl" aria-hidden="true" />
        <div className="relative rounded-3xl border border-white/50 dark:border-slate-600 bg-white/80 dark:bg-slate-800/90 backdrop-blur-xl shadow-2xl p-4 sm:p-6 md:p-8 space-y-6 max-h-[90vh] overflow-y-auto">
          <div className="flex items-start justify-between gap-6">
            <div>
              <h2 id="record-payment-title" className="text-2xl font-semibold text-wedding-navy dark:text-white">
                {modalTitle}
              </h2>
              <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                Capture vendor payments with transparency and keep your budget analytics accurate.
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-transparent p-2 text-gray-500 hover:text-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose focus:ring-offset-2"
              aria-label="Close payment modal"
            >
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path
                  fillRule="evenodd"
                  d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
          </div>

          {category && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 rounded-2xl border border-white/40 dark:border-slate-600 bg-white/50 dark:bg-slate-700/50 p-4 text-sm text-gray-700 dark:text-gray-300">
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Budgeted</p>
                <p className="text-base font-semibold text-wedding-navy dark:text-blue-400">
                  {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(category.budgeted_amount)}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Spent</p>
                <p className="text-base font-semibold text-wedding-rose dark:text-rose-400">
                  {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(category.actual_spent)}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Remaining</p>
                <p className="text-base font-semibold text-emerald-600 dark:text-emerald-400">{remainingBudget}</p>
              </div>
            </div>
          )}

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <label className="flex flex-col text-sm font-medium text-gray-700 dark:text-gray-300">
                Vendor name
                <input
                  type="text"
                  value={formState.vendorName}
                  onChange={(event) => handleChange('vendorName', event.target.value)}
                  className="mt-1 rounded-lg border border-white/60 dark:border-slate-600 bg-white/70 dark:bg-slate-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                  placeholder="e.g. Bloom & Co."
                />
              </label>

              <label className="flex flex-col text-sm font-medium text-gray-700 dark:text-gray-300">
                Payment amount <span className="text-red-500">*</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  inputMode="decimal"
                  value={formState.amount}
                  onChange={(event) => handleChange('amount', event.target.value)}
                  className="mt-1 rounded-lg border border-white/60 dark:border-slate-600 bg-white/70 dark:bg-slate-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                  required
                />
              </label>

              <label className="flex flex-col text-sm font-medium text-gray-700 dark:text-gray-300">
                Payment method <span className="text-red-500">*</span>
                <select
                  value={formState.paymentMethod}
                  onChange={(event) => handleChange('paymentMethod', event.target.value as PaymentFormValues['paymentMethod'])}
                  className="mt-1 rounded-lg border border-white/60 dark:border-slate-600 bg-white/70 dark:bg-slate-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                  required
                >
                  {paymentMethodOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="flex flex-col text-sm font-medium text-gray-700 dark:text-gray-300">
                Payment date <span className="text-red-500">*</span>
                <input
                  type="date"
                  value={formState.paymentDate}
                  onChange={(event) => handleChange('paymentDate', event.target.value)}
                  className="mt-1 rounded-lg border border-white/60 dark:border-slate-600 bg-white/70 dark:bg-slate-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                  required
                  max={getLocalDateString()}
                />
              </label>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <label className="flex flex-col text-sm font-medium text-gray-700 dark:text-gray-300">
                Payment status
                <select
                  value={formState.status}
                  onChange={(event) => handleChange('status', event.target.value as PaymentFormValues['status'])}
                  className="mt-1 rounded-lg border border-white/60 dark:border-slate-600 bg-white/70 dark:bg-slate-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                >
                  {statusOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="flex flex-col text-sm font-medium text-gray-700 dark:text-gray-300">
                Receipt URL
                <input
                  type="url"
                  value={formState.receiptUrl}
                  onChange={(event) => handleChange('receiptUrl', event.target.value)}
                  className="mt-1 rounded-lg border border-white/60 dark:border-slate-600 bg-white/70 dark:bg-slate-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                  placeholder="https://"
                  inputMode="url"
                />
              </label>
            </div>

            <label className="flex flex-col text-sm font-medium text-gray-700 dark:text-gray-300">
              Description
              <textarea
                value={formState.description}
                onChange={(event) => handleChange('description', event.target.value)}
                className="mt-1 h-20 rounded-lg border border-white/60 dark:border-slate-600 bg-white/70 dark:bg-slate-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                placeholder="50% deposit, mileage add-ons, etc."
              />
            </label>

            <label className="flex flex-col text-sm font-medium text-gray-700 dark:text-gray-300">
              Notes for your team
              <textarea
                value={formState.notes}
                onChange={(event) => handleChange('notes', event.target.value)}
                className="mt-1 h-20 rounded-lg border border-white/60 dark:border-slate-600 bg-white/70 dark:bg-slate-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                placeholder="Remind the couple about remaining balance next month."
              />
            </label>

            {(localError || errorMessage) && (
              <p className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 px-4 py-3 text-sm text-red-700 dark:text-red-300" role="alert">
                {localError || errorMessage}
              </p>
            )}

            <div className="flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-3 gap-3">
              <Button
                type="button"
                variant="danger"
                onClick={onClose}
                className="sm:min-w-[120px]"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={isSubmitting}
                className="sm:min-w-[160px]"
              >
                {isSubmitting ? 'Saving...' : 'Save payment'}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export default RecordPaymentModal;
