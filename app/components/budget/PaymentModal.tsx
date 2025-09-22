'use client';

import React, { useState } from 'react';
import { X, Calendar, DollarSign, Upload, Banknote, FileText, CreditCard, Building2 } from 'lucide-react';
import { RecordPaymentRequest } from '@/types/budget';

interface PaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payment: RecordPaymentRequest) => Promise<void>;
  categoryName: string;
  categoryId: string;
  remainingAmount?: number;
}

export default function PaymentModal({
  isOpen,
  onClose,
  onSubmit,
  categoryName,
  remainingAmount
}: PaymentModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState<RecordPaymentRequest>({
    vendor_name: '',
    amount: 0,
    payment_method: 'card',
    payment_date: new Date().toISOString().split('T')[0],
    description: '',
    notes: ''
  });

  const paymentMethods = [
    { value: 'cash', label: 'Cash', icon: Banknote },
    { value: 'check', label: 'Check', icon: FileText },
    { value: 'card', label: 'Credit/Debit Card', icon: CreditCard },
    { value: 'transfer', label: 'Bank Transfer', icon: Building2 }
  ] as const;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (formData.amount <= 0) {
      setError('Payment amount must be greater than 0');
      return;
    }

    setIsSubmitting(true);
    try {
      await onSubmit(formData);
      // Reset form and close modal
      setFormData({
        vendor_name: '',
        amount: 0,
        payment_method: 'card',
        payment_date: new Date().toISOString().split('T')[0],
        description: '',
        notes: ''
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to record payment');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-gradient-to-r from-wedding-rose to-wedding-gold p-6 rounded-t-2xl">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-2xl font-bold text-white">Record Payment</h2>
              <p className="text-rose-100 mt-1">Category: {categoryName}</p>
              {remainingAmount && remainingAmount > 0 && (
                <p className="text-rose-100 text-sm mt-1">
                  Remaining budget: ${remainingAmount.toLocaleString()}
                </p>
              )}
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/20 rounded-lg transition-colors"
              aria-label="Close modal"
            >
              <X className="w-6 h-6 text-white" />
            </button>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Error Display */}
          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-700 text-sm">{error}</p>
            </div>
          )}

          {/* Amount and Vendor */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label htmlFor="amount" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Payment Amount *
              </label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="number"
                  id="amount"
                  step="0.01"
                  min="0.01"
                  value={formData.amount || ''}
                  onChange={(e) => setFormData({ ...formData, amount: parseFloat(e.target.value) || 0 })}
                  className="w-full pl-10 pr-3 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent dark:bg-gray-700 dark:text-gray-100"
                  placeholder="0.00"
                  required
                />
              </div>
            </div>

            <div>
              <label htmlFor="vendor_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Vendor Name
              </label>
              <input
                type="text"
                id="vendor_name"
                value={formData.vendor_name || ''}
                onChange={(e) => setFormData({ ...formData, vendor_name: e.target.value })}
                className="w-full px-3 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent dark:bg-gray-700 dark:text-gray-100"
                placeholder="Enter vendor name"
              />
            </div>
          </div>

          {/* Payment Method and Date */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label htmlFor="payment_method" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Payment Method *
              </label>
              <div className="grid grid-cols-2 gap-2">
                {paymentMethods.map((method) => {
                  const Icon = method.icon;
                  return (
                    <button
                      key={method.value}
                      type="button"
                      onClick={() => setFormData({ ...formData, payment_method: method.value })}
                      className={`p-3 border rounded-lg transition-all flex flex-col items-center gap-1 ${
                        formData.payment_method === method.value
                          ? 'border-wedding-rose bg-wedding-rose/10 text-wedding-rose'
                          : 'border-gray-300 dark:border-gray-600 hover:border-gray-400'
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                      <p className="text-sm">{method.label}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label htmlFor="payment_date" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Payment Date *
              </label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="date"
                  id="payment_date"
                  value={formData.payment_date}
                  onChange={(e) => setFormData({ ...formData, payment_date: e.target.value })}
                  className="w-full pl-10 pr-3 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent dark:bg-gray-700 dark:text-gray-100"
                  required
                />
              </div>
            </div>
          </div>

          {/* Description */}
          <div>
            <label htmlFor="description" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Payment Description
            </label>
            <input
              type="text"
              id="description"
              value={formData.description || ''}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full px-3 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent dark:bg-gray-700 dark:text-gray-100"
              placeholder="e.g., 50% deposit for flowers"
            />
          </div>

          {/* Notes */}
          <div>
            <label htmlFor="notes" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Additional Notes
            </label>
            <textarea
              id="notes"
              value={formData.notes || ''}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              rows={3}
              className="w-full px-3 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent dark:bg-gray-700 dark:text-gray-100"
              placeholder="Any additional notes about this payment"
            />
          </div>

          {/* Receipt Upload - Future Implementation */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Receipt Upload
            </label>
            <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6 text-center">
              <Upload className="mx-auto h-12 w-12 text-gray-400" />
              <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                Receipt upload coming soon
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-500">
                You'll be able to upload PDF, JPG, or PNG files
              </p>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-6 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex-1 px-6 py-3 bg-gradient-to-r from-wedding-rose to-wedding-gold text-white rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {isSubmitting ? (
                <span className="flex items-center justify-center">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                  Recording...
                </span>
              ) : (
                'Record Payment'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}