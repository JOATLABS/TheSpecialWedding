'use client';

import React, { useState, useEffect } from 'react';
import { useVendorAuth } from '../layout';
import { toast } from 'sonner';
import {
  getVendorBilling,
  formatCurrency,
  type BillingSummaryResponse,
} from '@/services/campaignAdvertisingApi';
import {
  CreditCard,
  RefreshCw,
  DollarSign,
  Megaphone,
  Gift,
  CheckCircle2,
} from 'lucide-react';

export default function VendorBillingPage() {
  const { token } = useVendorAuth();
  const [billing, setBilling] = useState<BillingSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    getVendorBilling(token)
      .then(setBilling)
      .catch((err) => toast.error(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <RefreshCw size={24} className="animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Billing</h1>
        <p className="text-sm text-slate-500 mt-1">Manage your advertising billing and payments</p>
      </div>

      {/* Free Tier Banner */}
      <div className="bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20 border border-emerald-200 dark:border-emerald-800 rounded-2xl p-6">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-emerald-100 dark:bg-emerald-800 rounded-xl">
            <Gift size={28} className="text-emerald-600 dark:text-emerald-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-emerald-900 dark:text-emerald-100">Free Tier Active</h2>
            <p className="text-sm text-emerald-700 dark:text-emerald-300 mt-1">
              You&apos;re currently on the free tier. All ad campaigns run at $0 cost while we build out the platform.
              Enjoy full access to impressions, clicks, and leads at no charge!
            </p>
            <div className="flex items-center gap-4 mt-3">
              <div className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 size={16} />
                Unlimited campaigns
              </div>
              <div className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 size={16} />
                Full analytics
              </div>
              <div className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 size={16} />
                All targeting options
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Billing Summary Cards */}
      {billing && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 p-5">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 rounded-lg bg-slate-50 dark:bg-slate-700 text-emerald-500">
                <DollarSign size={20} />
              </div>
              <span className="text-xs text-slate-500 uppercase tracking-wider">Total Spend</span>
            </div>
            <p className="text-2xl font-bold text-slate-900 dark:text-white">{billing.total_spend > 0 ? formatCurrency(billing.total_spend) : 'Free'}</p>
            <p className="text-xs text-slate-400 mt-1">{billing.total_spend > 0 ? 'Lifetime total' : 'No charges on the free tier'}</p>
          </div>

          <div className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 p-5">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 rounded-lg bg-slate-50 dark:bg-slate-700 text-blue-500">
                <CreditCard size={20} />
              </div>
              <span className="text-xs text-slate-500 uppercase tracking-wider">Current Period</span>
            </div>
            <p className="text-2xl font-bold text-slate-900 dark:text-white">{billing.current_period_spend > 0 ? formatCurrency(billing.current_period_spend) : 'Free'}</p>
            <p className="text-xs text-slate-400 mt-1">{billing.current_period_spend > 0 ? 'This billing cycle' : 'No charges on the free tier'}</p>
          </div>

          <div className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 p-5">
            <div className="flex items-center gap-3 mb-3">
              <div className="p-2 rounded-lg bg-slate-50 dark:bg-slate-700 text-primary-500">
                <Megaphone size={20} />
              </div>
              <span className="text-xs text-slate-500 uppercase tracking-wider">Campaigns</span>
            </div>
            <p className="text-2xl font-bold text-slate-900 dark:text-white">{billing.campaigns_count}</p>
            <p className="text-xs text-slate-400 mt-1">Total campaigns</p>
          </div>
        </div>
      )}

      {/* Billing History */}
      {billing && billing.billing_records && billing.billing_records.length > 0 && (
        <div className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 p-5">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-4">Billing History</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700">
                  <th className="text-left px-3 py-2 text-xs font-medium text-slate-500 uppercase">Period</th>
                  <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 uppercase">Impressions</th>
                  <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 uppercase">Clicks</th>
                  <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 uppercase">Leads</th>
                  <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 uppercase">Spend</th>
                  <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 uppercase">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {billing.billing_records.map((record) => (
                  <tr key={record._id}>
                    <td className="px-3 py-2 text-slate-700 dark:text-slate-300">
                      {new Date(record.billing_period_start).toLocaleDateString()} &mdash; {new Date(record.billing_period_end).toLocaleDateString()}
                    </td>
                    <td className="px-3 py-2 text-right text-slate-700 dark:text-slate-300">{record.impressions.toLocaleString()}</td>
                    <td className="px-3 py-2 text-right text-slate-700 dark:text-slate-300">{record.clicks.toLocaleString()}</td>
                    <td className="px-3 py-2 text-right text-slate-700 dark:text-slate-300">{record.leads.toLocaleString()}</td>
                    <td className="px-3 py-2 text-right text-slate-700 dark:text-slate-300">{formatCurrency(record.total_spend)}</td>
                    <td className="px-3 py-2 text-right">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
                        {record.payment_status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
