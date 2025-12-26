'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import {
  Loader2,
  CheckCircle,
  Clock,
  AlertCircle,
  XCircle,
  CreditCard,
  Calendar,
  DollarSign,
  Download,
  RefreshCw,
  Mail,
  Phone,
  User,
  ExternalLink,
  ChevronRight
} from 'lucide-react';

interface Payment {
  id: string;
  name: string;
  amount: number;
  currency: string;
  due_date: string;
  status: 'scheduled' | 'processing' | 'succeeded' | 'failed' | 'cancelled';
  paid_at?: string;
  receipt_url?: string;
  failure_reason?: string;
}

interface PortalData {
  contract: {
    id: string;
    status: string;
    couple: {
      name: string;
      email: string;
      partner_name?: string;
    };
    wedding_date?: string;
    venue?: string;
    package_name: string;
    signed_at?: string;
    payment_method_last4?: string;
    payment_method_brand?: string;
    planner_name?: string;
    planner_email?: string;
    planner_phone?: string;
  };
  payments: Payment[];
  summary: {
    total_amount: number;
    paid_amount: number;
    pending_amount: number;
    failed_amount: number;
    remaining_amount: number;
    payment_count: number;
    completed_count: number;
    next_payment?: {
      name: string;
      amount: number;
      due_date: string;
    };
  };
}

export default function CouplePortalPage() {
  const params = useParams();
  const token = params.token as string;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [data, setData] = useState<PortalData | null>(null);
  const [updatingPayment, setUpdatingPayment] = useState(false);

  const fetchPortalData = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    setError('');

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/public/portal/${token}`);

      if (response.status === 404) {
        setError('This portal link is invalid or has expired.');
        return;
      }

      if (response.status === 403) {
        setError('Portal access is only available after signing the contract.');
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to load portal');
      }

      const portalData = await response.json();
      setData(portalData);
    } catch (err) {
      setError('Unable to load your payment portal. Please try again later.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchPortalData();
  }, [fetchPortalData]);

  const formatCurrency = (amount: number, currency: string = 'usd') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency.toUpperCase()
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  const getDaysUntil = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = date.getTime() - now.getTime();
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  const getStatusBadge = (status: string) => {
    const styles = {
      scheduled: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
      processing: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
      succeeded: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
      failed: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
      cancelled: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400'
    };

    const icons = {
      scheduled: <Clock size={14} />,
      processing: <Loader2 size={14} className="animate-spin" />,
      succeeded: <CheckCircle size={14} />,
      failed: <XCircle size={14} />,
      cancelled: <XCircle size={14} />
    };

    const labels = {
      scheduled: 'Scheduled',
      processing: 'Processing',
      succeeded: 'Paid',
      failed: 'Failed',
      cancelled: 'Cancelled'
    };

    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${styles[status as keyof typeof styles] || styles.scheduled}`}>
        {icons[status as keyof typeof icons]}
        {labels[status as keyof typeof labels] || status}
      </span>
    );
  };

  const handleUpdatePaymentMethod = async () => {
    setUpdatingPayment(true);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/public/portal/${token}/update-payment-method`, {
        method: 'POST'
      });

      if (!response.ok) {
        throw new Error('Failed to initialize payment update');
      }

      const { client_secret } = await response.json();

      // Redirect to payment update page or open modal
      // For now, show a message
      toast.info('Payment method update flow would open here with Stripe Elements');

    } catch (err) {
      toast.error('Failed to start payment method update');
    } finally {
      setUpdatingPayment(false);
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary-500 mx-auto mb-4" />
          <p className="text-slate-600 dark:text-slate-400">Loading your payment portal...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !data) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex items-center justify-center p-4">
        <Card className="max-w-md w-full p-8 text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
            Portal Not Available
          </h1>
          <p className="text-slate-600 dark:text-slate-400">
            {error || 'This portal link is invalid or has expired.'}
          </p>
        </Card>
      </div>
    );
  }

  const { contract, payments, summary } = data;
  const progressPercent = summary.total_amount > 0
    ? Math.round((summary.paid_amount / summary.total_amount) * 100)
    : 0;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">
            Payment Portal
          </h1>
          <p className="text-slate-600 dark:text-slate-400">
            {contract.package_name}
          </p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {/* Total Progress */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm text-slate-600 dark:text-slate-400">Total Progress</span>
              <span className="text-lg font-bold text-primary-600">{progressPercent}%</span>
            </div>
            <div className="w-full h-3 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-primary-500 to-primary-600 rounded-full transition-all duration-500"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <div className="mt-3 flex justify-between text-sm">
              <span className="text-green-600 dark:text-green-400">
                {formatCurrency(summary.paid_amount)} paid
              </span>
              <span className="text-slate-500">
                of {formatCurrency(summary.total_amount)}
              </span>
            </div>
          </Card>

          {/* Next Payment */}
          <Card className="p-6">
            <div className="flex items-center gap-2 mb-3">
              <Calendar size={18} className="text-primary-500" />
              <span className="text-sm text-slate-600 dark:text-slate-400">Next Payment</span>
            </div>
            {summary.next_payment ? (
              <>
                <p className="text-2xl font-bold text-slate-900 dark:text-white">
                  {formatCurrency(summary.next_payment.amount)}
                </p>
                <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                  {summary.next_payment.name}
                </p>
                <p className="text-sm mt-2">
                  {getDaysUntil(summary.next_payment.due_date) > 0 ? (
                    <span className="text-blue-600 dark:text-blue-400">
                      Due in {getDaysUntil(summary.next_payment.due_date)} days
                    </span>
                  ) : getDaysUntil(summary.next_payment.due_date) === 0 ? (
                    <span className="text-yellow-600 dark:text-yellow-400">Due today</span>
                  ) : (
                    <span className="text-red-600 dark:text-red-400">Overdue</span>
                  )}
                </p>
              </>
            ) : (
              <p className="text-slate-500">All payments complete!</p>
            )}
          </Card>

          {/* Payment Method */}
          <Card className="p-6">
            <div className="flex items-center gap-2 mb-3">
              <CreditCard size={18} className="text-primary-500" />
              <span className="text-sm text-slate-600 dark:text-slate-400">Payment Method</span>
            </div>
            {contract.payment_method_last4 ? (
              <>
                <p className="text-lg font-semibold text-slate-900 dark:text-white capitalize">
                  {contract.payment_method_brand || 'Card'} ****{contract.payment_method_last4}
                </p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleUpdatePaymentMethod}
                  disabled={updatingPayment}
                  className="mt-3 text-primary-600"
                >
                  {updatingPayment ? (
                    <Loader2 size={14} className="animate-spin mr-2" />
                  ) : (
                    <RefreshCw size={14} className="mr-2" />
                  )}
                  Update Card
                </Button>
              </>
            ) : (
              <p className="text-slate-500">No payment method on file</p>
            )}
          </Card>
        </div>

        {/* Payment Schedule */}
        <Card className="mb-8">
          <div className="p-6 border-b border-slate-200 dark:border-slate-700">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
              Payment Schedule
            </h2>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              {summary.completed_count} of {summary.payment_count} payments completed
            </p>
          </div>

          <div className="divide-y divide-slate-200 dark:divide-slate-700">
            {payments.map((payment, index) => (
              <div
                key={payment.id}
                className={`p-4 flex items-center justify-between ${
                  payment.status === 'succeeded' ? 'bg-green-50/50 dark:bg-green-900/10' : ''
                }`}
              >
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    payment.status === 'succeeded'
                      ? 'bg-green-100 dark:bg-green-900/30'
                      : payment.status === 'failed'
                      ? 'bg-red-100 dark:bg-red-900/30'
                      : 'bg-slate-100 dark:bg-slate-800'
                  }`}>
                    {payment.status === 'succeeded' ? (
                      <CheckCircle className="text-green-600" size={20} />
                    ) : payment.status === 'failed' ? (
                      <XCircle className="text-red-600" size={20} />
                    ) : (
                      <span className="text-sm font-medium text-slate-600 dark:text-slate-400">
                        {index + 1}
                      </span>
                    )}
                  </div>

                  <div>
                    <p className="font-medium text-slate-900 dark:text-white">
                      {payment.name}
                    </p>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      {payment.status === 'succeeded' && payment.paid_at
                        ? `Paid on ${formatDate(payment.paid_at)}`
                        : `Due ${formatDate(payment.due_date)}`}
                    </p>
                    {payment.failure_reason && (
                      <p className="text-sm text-red-600 mt-1">
                        {payment.failure_reason}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <p className="font-semibold text-slate-900 dark:text-white">
                      {formatCurrency(payment.amount, payment.currency)}
                    </p>
                    {getStatusBadge(payment.status)}
                  </div>

                  {payment.receipt_url && (
                    <a
                      href={payment.receipt_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
                      title="Download Receipt"
                    >
                      <Download size={18} className="text-slate-600 dark:text-slate-400" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Planner Contact */}
        {(contract.planner_name || contract.planner_email || contract.planner_phone) && (
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
              Your Wedding Planner
            </h2>
            <div className="flex flex-wrap gap-6">
              {contract.planner_name && (
                <div className="flex items-center gap-2">
                  <User size={18} className="text-slate-500" />
                  <span className="text-slate-700 dark:text-slate-300">{contract.planner_name}</span>
                </div>
              )}
              {contract.planner_email && (
                <a
                  href={`mailto:${contract.planner_email}`}
                  className="flex items-center gap-2 text-primary-600 hover:text-primary-700"
                >
                  <Mail size={18} />
                  <span>{contract.planner_email}</span>
                </a>
              )}
              {contract.planner_phone && (
                <a
                  href={`tel:${contract.planner_phone}`}
                  className="flex items-center gap-2 text-primary-600 hover:text-primary-700"
                >
                  <Phone size={18} />
                  <span>{contract.planner_phone}</span>
                </a>
              )}
            </div>
          </Card>
        )}

        {/* Footer */}
        <div className="mt-8 text-center text-sm text-slate-500 dark:text-slate-400">
          <p>Questions about your payments? Contact your wedding planner directly.</p>
          <p className="mt-2">
            Contract signed on {contract.signed_at && formatDate(contract.signed_at)}
          </p>
        </div>
      </div>
    </div>
  );
}
