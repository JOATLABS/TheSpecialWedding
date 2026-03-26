'use client';

import React, { useState, useEffect } from 'react';
import { useVendorAuth } from '../components/VendorAuthContext';
import { toast } from 'sonner';
import {
  getVendorBillingSummary,
  getVendorBillingCharges,
  formatCurrency,
  type VendorBillingSummary,
  type LeadCharge,
} from '@/services/campaignAdvertisingApi';
import {
  DollarSign,
  TrendingUp,
  FileText,
  FolderPlus,
  RefreshCw,
  CheckCircle2,
  Clock,
  AlertCircle,
} from 'lucide-react';

export default function VendorBillingPage() {
  const { token } = useVendorAuth();
  const [billing, setBilling] = useState<VendorBillingSummary | null>(null);
  const [charges, setCharges] = useState<LeadCharge[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    const loadData = async () => {
      try {
        const [summaryData, chargesData] = await Promise.all([
          getVendorBillingSummary(token),
          getVendorBillingCharges(token, { limit: 50 }),
        ]);
        setBilling(summaryData);
        setCharges(chargesData);
      } catch (err: any) {
        toast.error(err.message);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [token]);

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <RefreshCw size={24} className="animate-spin text-slate-400" />
      </div>
    );
  }

  if (!billing) {
    return (
      <div className="text-center py-16">
        <p className="text-slate-500">Unable to load billing data</p>
      </div>
    );
  }

  const getChargeStatusColor = (status: string) => {
    switch (status) {
      case 'free':
        return 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300';
      case 'charged':
        return 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300';
      case 'pending':
        return 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300';
      case 'failed':
        return 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300';
      default:
        return 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300';
    }
  };

  const getLeadTypeLabel = (type: string) => {
    return type === 'quote_request' ? 'Quote Request' : 'Directory Add';
  };

  const getLeadTypeIcon = (type: string) => {
    return type === 'quote_request' ? <FileText size={16} /> : <FolderPlus size={16} />;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Billing &amp; Spend</h1>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300">
            Cost Per Lead
          </span>
        </div>
        {billing.is_free_tier && (
          <p className="text-sm text-emerald-600 dark:text-emerald-400 mt-2">
            Free tier active: {billing.free_tier_reason}
          </p>
        )}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Spend */}
        <div className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 rounded-lg bg-slate-50 dark:bg-slate-700 text-emerald-500">
              <DollarSign size={20} />
            </div>
            <span className="text-xs text-slate-500 uppercase tracking-wider">Total Spend</span>
          </div>
          <p className="text-xl font-bold text-slate-900 dark:text-white">
            {billing.total_spend > 0 ? formatCurrency(billing.total_spend) : '$0'}
          </p>
          <p className="text-xs text-slate-400 mt-1">{billing.is_free_tier ? 'Free tier' : 'Lifetime total'}</p>
        </div>

        {/* Total Leads */}
        <div className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 rounded-lg bg-slate-50 dark:bg-slate-700 text-blue-500">
              <TrendingUp size={20} />
            </div>
            <span className="text-xs text-slate-500 uppercase tracking-wider">Total Leads</span>
          </div>
          <p className="text-xl font-bold text-slate-900 dark:text-white">{billing.total_leads.toLocaleString()}</p>
          <p className="text-xs text-slate-400 mt-1">All lead types</p>
        </div>

        {/* Quote Requests */}
        <div className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 rounded-lg bg-slate-50 dark:bg-slate-700 text-purple-500">
              <FileText size={20} />
            </div>
            <span className="text-xs text-slate-500 uppercase tracking-wider">Quote Requests</span>
          </div>
          <p className="text-xl font-bold text-slate-900 dark:text-white">{billing.quote_request_leads.toLocaleString()}</p>
          <p className="text-xs text-slate-400 mt-1">Paid leads</p>
        </div>

        {/* Directory Adds */}
        <div className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 rounded-lg bg-slate-50 dark:bg-slate-700 text-orange-500">
              <FolderPlus size={20} />
            </div>
            <span className="text-xs text-slate-500 uppercase tracking-wider">Directory Adds</span>
          </div>
          <p className="text-xl font-bold text-slate-900 dark:text-white">{billing.directory_add_leads.toLocaleString()}</p>
          <p className="text-xs text-slate-400 mt-1">Paid leads</p>
        </div>
      </div>

      {/* Billing History Table */}
      {billing.billing_periods && billing.billing_periods.length > 0 && (
        <div className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 p-5">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-4">Billing History</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700">
                  <th className="text-left px-3 py-2 text-xs font-medium text-slate-500 uppercase">Period</th>
                  <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 uppercase">Leads</th>
                  <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 uppercase">Quote Requests</th>
                  <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 uppercase">Directory Adds</th>
                  <th className="text-right px-3 py-2 text-xs font-medium text-slate-500 uppercase">Total Spend</th>
                  <th className="text-center px-3 py-2 text-xs font-medium text-slate-500 uppercase">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {billing.billing_periods.map((period) => (
                  <tr key={period._id}>
                    <td className="px-3 py-2 text-slate-700 dark:text-slate-300">
                      {new Date(period.billing_period_start).toLocaleDateString('en-US', {
                        month: 'short',
                        year: 'numeric',
                      })}
                    </td>
                    <td className="px-3 py-2 text-right text-slate-700 dark:text-slate-300">
                      {period.leads.toLocaleString()}
                    </td>
                    <td className="px-3 py-2 text-right text-slate-700 dark:text-slate-300">
                      {period.quote_request_leads.toLocaleString()}
                    </td>
                    <td className="px-3 py-2 text-right text-slate-700 dark:text-slate-300">
                      {period.directory_add_leads.toLocaleString()}
                    </td>
                    <td className="px-3 py-2 text-right text-slate-700 dark:text-slate-300">
                      {period.is_free_tier ? 'Free' : formatCurrency(period.total_spend)}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize ${
                          period.is_free_tier
                            ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300'
                            : 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                        }`}
                      >
                        {period.is_free_tier ? 'Free' : period.payment_status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recent Charges */}
      {charges.length > 0 && (
        <div className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 p-5">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-4">Recent Charges</h3>
          <div className="space-y-3">
            {charges.map((charge) => (
              <div
                key={charge._id}
                className="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600"
              >
                <div className="flex items-center gap-3 flex-1">
                  <div className="p-2 rounded-lg bg-slate-200 dark:bg-slate-600 text-slate-600 dark:text-slate-300">
                    {getLeadTypeIcon(charge.lead_type)}
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-900 dark:text-white">
                      {getLeadTypeLabel(charge.lead_type)}
                    </p>
                    <p className="text-xs text-slate-500">
                      {new Date(charge.created_at).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">
                      {charge.is_free_tier ? 'Free' : formatCurrency(charge.charge_amount)}
                    </p>
                  </div>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${getChargeStatusColor(charge.charge_status)}`}>
                    {charge.charge_status === 'free' ? (
                      <>
                        <CheckCircle2 size={12} className="mr-1" />
                        Free
                      </>
                    ) : charge.charge_status === 'charged' ? (
                      <>
                        <CheckCircle2 size={12} className="mr-1" />
                        Charged
                      </>
                    ) : charge.charge_status === 'pending' ? (
                      <>
                        <Clock size={12} className="mr-1" />
                        Pending
                      </>
                    ) : (
                      <>
                        <AlertCircle size={12} className="mr-1" />
                        {charge.charge_status}
                      </>
                    )}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
