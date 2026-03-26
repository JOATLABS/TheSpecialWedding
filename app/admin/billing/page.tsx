"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { formatAdminDate, DEFAULT_TIMEZONE } from '@/utils/dateFormat';
import { Card } from '@/components/ui/Card';
import PageHeader from '../components/PageHeader';
import {
  DollarSign,
  TrendingUp,
  Users,
  CreditCard,
  AlertCircle,
  CheckCircle,
  Clock,
  XCircle,
  ExternalLink,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react';

interface SubscriptionSummary {
  _id: string;
  user_id: string;
  user_email?: string;
  company_name?: string;
  plan_id: string;
  plan_name?: string;
  status: string;
  billing_interval: string;
  amount: number;
  current_period_start: string;
  current_period_end: string;
  created_at: string;
}

interface BillingMetrics {
  mrr: number;
  arr: number;
  mrr_growth: number;
  total_subscriptions: number;
  active_subscriptions: number;
  trial_subscriptions: number;
  cancelled_subscriptions: number;
  past_due_subscriptions: number;
  churn_rate: number;
  conversion_rate: number;
  average_revenue_per_user: number;
}

interface RecentEvent {
  id: string;
  type: string;
  description: string;
  amount?: number;
  timestamp: string;
  user_email?: string;
}

export default function AdminBillingDashboard() {
  const router = useRouter();
  const { userProfile, token, isLoading: authLoading } = useAdmin();
  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState<BillingMetrics | null>(null);
  const [subscriptions, setSubscriptions] = useState<SubscriptionSummary[]>([]);
  const [recentEvents, setRecentEvents] = useState<RecentEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // ROOT_ADMIN access control
  useEffect(() => {
    if (authLoading) {
      return;
    }

    if (userProfile && !userProfile.is_root_admin) {
      setLoading(false);
      router.replace('/admin');
    }
  }, [authLoading, userProfile, router]);

  const fetchBillingData = useCallback(async () => {
    try {
      setLoading(true);

      if (authLoading || !userProfile) {
        return;
      }

      if (!userProfile.is_root_admin) {
        setLoading(false);
        return;
      }

      const baseUrl = getApiBaseUrl();
      if (!token) {
        setError('Authentication required');
        setLoading(false);
        return;
      }

      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };

      // Fetch platform metrics which includes business/billing data
      const metricsResponse = await fetch(`${baseUrl}/admin/platform/health`, { headers, credentials: 'include' });

      if (metricsResponse.status === 403) {
        setLoading(false);
        router.replace('/admin');
        return;
      }

      if (metricsResponse.ok) {
        const metricsData = await metricsResponse.json();

        // Extract billing metrics from platform metrics
        const businessMetrics = metricsData.business || {};
        setMetrics({
          mrr: businessMetrics.mrr || 0,
          arr: businessMetrics.arr || 0,
          mrr_growth: 0, // Would need historical data
          total_subscriptions: (businessMetrics.active_subscriptions || 0) +
                              (businessMetrics.trial_subscriptions || 0) +
                              (businessMetrics.canceled_subscriptions || 0),
          active_subscriptions: businessMetrics.active_subscriptions || 0,
          trial_subscriptions: businessMetrics.trial_subscriptions || 0,
          cancelled_subscriptions: businessMetrics.canceled_subscriptions || 0,
          past_due_subscriptions: 0,
          churn_rate: 0,
          conversion_rate: businessMetrics.conversion_rate || 0,
          average_revenue_per_user: businessMetrics.active_subscriptions > 0
            ? (businessMetrics.mrr || 0) / businessMetrics.active_subscriptions
            : 0
        });
      }

      // Fetch all subscriptions
      const subsResponse = await fetch(`${baseUrl}/subscriptions`, { headers, credentials: 'include' });
      if (subsResponse.ok) {
        const subsData = await subsResponse.json();
        setSubscriptions(Array.isArray(subsData) ? subsData : subsData.subscriptions || []);
      }

      // Generate mock recent events (would come from webhooks/events API)
      setRecentEvents([
        {
          id: '1',
          type: 'subscription_created',
          description: 'New subscription started',
          amount: 59,
          timestamp: new Date().toISOString(),
          user_email: 'planner@example.com'
        }
      ]);

      setError(null);
    } catch (err) {
      console.error('Error fetching billing data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load billing data');

      // Set default metrics on error
      setMetrics({
        mrr: 0,
        arr: 0,
        mrr_growth: 0,
        total_subscriptions: 0,
        active_subscriptions: 0,
        trial_subscriptions: 0,
        cancelled_subscriptions: 0,
        past_due_subscriptions: 0,
        churn_rate: 0,
        conversion_rate: 0,
        average_revenue_per_user: 0
      });
    } finally {
      setLoading(false);
    }
  }, [authLoading, router, token, userProfile]);

  useEffect(() => {
    if (authLoading) {
      return;
    }

    if (!userProfile || !userProfile.is_root_admin) {
      return;
    }

    fetchBillingData();
  }, [authLoading, fetchBillingData, userProfile]);

  const getStatusBadge = (status: string) => {
    const config: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
      active: {
        bg: 'bg-green-100 dark:bg-green-900/30',
        text: 'text-green-800 dark:text-green-300',
        icon: <CheckCircle className="w-3 h-3" />
      },
      trialing: {
        bg: 'bg-blue-100 dark:bg-blue-900/30',
        text: 'text-blue-800 dark:text-blue-300',
        icon: <Clock className="w-3 h-3" />
      },
      past_due: {
        bg: 'bg-yellow-100 dark:bg-yellow-900/30',
        text: 'text-yellow-800 dark:text-yellow-300',
        icon: <AlertCircle className="w-3 h-3" />
      },
      canceled: {
        bg: 'bg-red-100 dark:bg-red-900/30',
        text: 'text-red-800 dark:text-red-300',
        icon: <XCircle className="w-3 h-3" />
      },
      cancelled: {
        bg: 'bg-red-100 dark:bg-red-900/30',
        text: 'text-red-800 dark:text-red-300',
        icon: <XCircle className="w-3 h-3" />
      }
    };

    const statusConfig = config[status] || config.active;

    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${statusConfig.bg} ${statusConfig.text}`}>
        {statusConfig.icon}
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return formatAdminDate(dateString, DEFAULT_TIMEZONE);
  };

  const filteredSubscriptions = subscriptions.filter(sub =>
    statusFilter === 'all' || sub.status === statusFilter
  );

  if (authLoading || loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading billing dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Billing & Revenue"
        description="Platform-wide subscription and revenue analytics"
      >
        <button
          onClick={fetchBillingData}
          className="inline-flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-600 transition-colors text-sm font-medium text-slate-700 dark:text-slate-300"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
        <a
          href="https://dashboard.stripe.com"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-4 py-2 bg-[#635BFF] text-white rounded-lg hover:bg-[#5851ea] transition-colors text-sm font-medium"
        >
          <ExternalLink className="w-4 h-4" />
          Stripe Dashboard
        </a>
      </PageHeader>

      <div>
        {error && (
          <div className="mb-6 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
            <p className="text-yellow-700 dark:text-yellow-300 text-sm">{error}</p>
          </div>
        )}

        {/* Revenue Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Monthly Recurring Revenue</p>
                <p className="text-3xl font-bold text-gray-900 dark:text-gray-100 mt-1">
                  {formatCurrency(metrics?.mrr || 0)}
                </p>
                {metrics?.mrr_growth !== 0 && (
                  <p className={`text-sm mt-1 flex items-center gap-1 ${metrics?.mrr_growth && metrics.mrr_growth > 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {metrics?.mrr_growth && metrics.mrr_growth > 0 ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
                    {Math.abs(metrics?.mrr_growth || 0)}% from last month
                  </p>
                )}
              </div>
              <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-lg">
                <DollarSign className="w-6 h-6 text-green-600 dark:text-green-400" />
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Annual Recurring Revenue</p>
                <p className="text-3xl font-bold text-gray-900 dark:text-gray-100 mt-1">
                  {formatCurrency(metrics?.arr || 0)}
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  Projected yearly
                </p>
              </div>
              <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                <TrendingUp className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Active Subscriptions</p>
                <p className="text-3xl font-bold text-gray-900 dark:text-gray-100 mt-1">
                  {metrics?.active_subscriptions || 0}
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  +{metrics?.trial_subscriptions || 0} in trial
                </p>
              </div>
              <div className="p-3 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                <Users className="w-6 h-6 text-purple-600 dark:text-purple-400" />
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Avg. Revenue per User</p>
                <p className="text-3xl font-bold text-gray-900 dark:text-gray-100 mt-1">
                  {formatCurrency(metrics?.average_revenue_per_user || 0)}
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  Per month
                </p>
              </div>
              <div className="p-3 bg-orange-100 dark:bg-orange-900/30 rounded-lg">
                <CreditCard className="w-6 h-6 text-orange-600 dark:text-orange-400" />
              </div>
            </div>
          </Card>
        </div>

        {/* Subscription Breakdown */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <Card className="p-6 lg:col-span-2">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Subscription Status</h2>
            </div>
            <div className="grid grid-cols-4 gap-4">
              <div className="text-center p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                  {metrics?.active_subscriptions || 0}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">Active</p>
              </div>
              <div className="text-center p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                  {metrics?.trial_subscriptions || 0}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">Trialing</p>
              </div>
              <div className="text-center p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
                <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
                  {metrics?.past_due_subscriptions || 0}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">Past Due</p>
              </div>
              <div className="text-center p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                  {metrics?.cancelled_subscriptions || 0}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">Cancelled</p>
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-6">Key Metrics</h2>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-gray-600 dark:text-gray-400">Conversion Rate</span>
                <span className="font-semibold text-gray-900 dark:text-gray-100">
                  {(metrics?.conversion_rate || 0).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600 dark:text-gray-400">Churn Rate</span>
                <span className="font-semibold text-gray-900 dark:text-gray-100">
                  {(metrics?.churn_rate || 0).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600 dark:text-gray-400">Total Subscriptions</span>
                <span className="font-semibold text-gray-900 dark:text-gray-100">
                  {metrics?.total_subscriptions || 0}
                </span>
              </div>
            </div>
          </Card>
        </div>

        {/* All Subscriptions Table */}
        <Card className="overflow-hidden">
          <div className="p-6 border-b dark:border-slate-700">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">All Subscriptions</h2>
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-600 dark:text-gray-400">Filter:</label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="px-3 py-1.5 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="all">All Status</option>
                  <option value="active">Active</option>
                  <option value="trialing">Trialing</option>
                  <option value="past_due">Past Due</option>
                  <option value="canceled">Cancelled</option>
                </select>
              </div>
            </div>
          </div>

          {filteredSubscriptions.length === 0 ? (
            <div className="p-12 text-center">
              <CreditCard className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No Subscriptions Found</h3>
              <p className="text-gray-600 dark:text-gray-400">
                {statusFilter !== 'all'
                  ? 'Try adjusting your filter'
                  : 'Subscriptions will appear here when planners subscribe to your plans'
                }
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-slate-700">
                <thead className="bg-gray-50 dark:bg-slate-800">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Customer
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Plan
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Amount
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Billing
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Next Renewal
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white dark:bg-slate-800 divide-y divide-gray-200 dark:divide-slate-700">
                  {filteredSubscriptions.map((sub) => (
                    <tr key={sub._id} className="hover:bg-gray-50 dark:hover:bg-slate-700">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div>
                          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                            {sub.company_name || 'N/A'}
                          </p>
                          <p className="text-sm text-gray-500 dark:text-gray-400">
                            {sub.user_email || sub.user_id}
                          </p>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <p className="text-sm text-gray-900 dark:text-gray-100">
                          {sub.plan_name || sub.plan_id}
                        </p>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {getStatusBadge(sub.status)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                          {formatCurrency(sub.amount || 0)}
                        </p>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <p className="text-sm text-gray-600 dark:text-gray-400 capitalize">
                          {sub.billing_interval || 'monthly'}
                        </p>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          {sub.current_period_end ? formatDate(sub.current_period_end) : 'N/A'}
                        </p>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Quick Links */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            onClick={() => router.push('/admin/saas')}
            className="p-4 bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-lg hover:border-blue-500 dark:hover:border-blue-500 transition-colors text-left group"
          >
            <h3 className="font-medium text-gray-900 dark:text-gray-100 group-hover:text-blue-600 dark:group-hover:text-blue-400">
              Manage Subscription Plans
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Create, edit, or delete subscription plans
            </p>
          </button>

          <a
            href="https://dashboard.stripe.com/subscriptions"
            target="_blank"
            rel="noopener noreferrer"
            className="p-4 bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-lg hover:border-blue-500 dark:hover:border-blue-500 transition-colors text-left group"
          >
            <h3 className="font-medium text-gray-900 dark:text-gray-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 flex items-center gap-2">
              Stripe Subscriptions
              <ExternalLink className="w-4 h-4" />
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              View detailed subscription data in Stripe
            </p>
          </a>

          <a
            href="https://dashboard.stripe.com/invoices"
            target="_blank"
            rel="noopener noreferrer"
            className="p-4 bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-lg hover:border-blue-500 dark:hover:border-blue-500 transition-colors text-left group"
          >
            <h3 className="font-medium text-gray-900 dark:text-gray-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 flex items-center gap-2">
              Invoices & Payments
              <ExternalLink className="w-4 h-4" />
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              View all invoices and payment history
            </p>
          </a>
        </div>
      </div>
    </div>
  );
}
