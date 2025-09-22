'use client';

import { useState, useEffect } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { Card } from '@/components/ui/Card';

interface PlatformMetrics {
  users: {
    total: number;
    active: number;
    new_this_month: number;
    growth_rate: number;
  };
  subscriptions: {
    total: number;
    active: number;
    trial: number;
    churned_this_month: number;
    mrr: number;
    arr: number;
  };
  usage: {
    weddings_created: number;
    forms_created: number;
    guests_managed: number;
    emails_sent: number;
    sms_sent: number;
  };
  performance: {
    uptime: number;
    avg_response_time: number;
    error_rate: number;
    api_calls_today: number;
  };
  revenue: {
    total_revenue: number;
    monthly_growth: number;
    average_revenue_per_user: number;
    lifetime_value: number;
  };
}

export default function PlatformMetricsPage() {
  const { apiRequest } = useAdmin();
  const [metrics, setMetrics] = useState<PlatformMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeframe, setTimeframe] = useState('30days');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMetrics();
  }, [timeframe]);

  const fetchMetrics = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch real analytics data from the platform analytics endpoint
      const response = await apiRequest(`/api/saas/analytics/overview?timeframe=${timeframe}`, 'GET');

      if (response && response.data) {
        // The backend returns the data in the exact format we need
        const realMetrics: PlatformMetrics = response.data;
        setMetrics(realMetrics);
      } else {
        throw new Error('Invalid response from analytics API');
      }
    } catch (error) {
      console.error('Error fetching metrics:', error);
      setError('Failed to load metrics');
    } finally {
      setLoading(false);
    }
  };


  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('en-US').format(num);
  };

  const formatPercentage = (num: number) => {
    return `${num.toFixed(1)}%`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64" data-testid="metrics-loading">
        <div className="text-lg text-gray-900 dark:text-gray-100">Loading metrics...</div>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="text-center py-8" data-testid="metrics-error-state">
        <div className="text-red-600 dark:text-red-400 mb-4" data-testid="error-message">Failed to load metrics</div>
        <button
          onClick={fetchMetrics}
          className="bg-wedding-rose text-white px-4 py-2 rounded-lg hover:bg-wedding-rose/80"
          data-testid="retry-button"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-heading text-wedding-rose">Platform Metrics</h1>
          <p className="text-gray-600 dark:text-gray-300">Monitor platform performance and growth</p>
        </div>
        
        <select
          id="timeframe-selector"
          data-testid="timeframe-selector"
          value={timeframe}
          onChange={(e) => setTimeframe(e.target.value)}
          className="px-4 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
        >
          <option value="7days">Last 7 Days</option>
          <option value="30days">Last 30 Days</option>
          <option value="90days">Last 90 Days</option>
          <option value="1year">Last Year</option>
        </select>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg p-4">
          <p className="text-red-700 dark:text-red-300">{error}</p>
        </div>
      )}

      {/* User Metrics */}
      <div>
        <h2 className="text-xl font-semibold text-wedding-navy dark:text-gray-100 mb-4">User Growth</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <Card className="p-6" data-testid="metric-total-users">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Users</h3>
            <p className="text-3xl font-bold text-wedding-navy" data-testid="value-total-users">{formatNumber(metrics.users.total)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-green-600">+{metrics.users.new_this_month} this month</span>
            </div>
          </Card>
          
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Active Users</h3>
            <p className="text-3xl font-bold text-green-600">{formatNumber(metrics.users.active)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {formatPercentage((metrics.users.active / metrics.users.total) * 100)} active rate
              </span>
            </div>
          </Card>
          
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">New Users</h3>
            <p className="text-3xl font-bold text-blue-600">{formatNumber(metrics.users.new_this_month)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-green-600">
                +{formatPercentage(metrics.users.growth_rate)} growth
              </span>
            </div>
          </Card>
          
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Growth Rate</h3>
            <p className="text-3xl font-bold text-purple-600">{formatPercentage(metrics.users.growth_rate)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">Month over month</span>
            </div>
          </Card>
        </div>
      </div>

      {/* Revenue Metrics */}
      <div>
        <h2 className="text-xl font-semibold text-wedding-navy dark:text-gray-100 mb-4">Revenue</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Monthly Recurring Revenue</h3>
            <p className="text-3xl font-bold text-wedding-rose">{formatCurrency(metrics.subscriptions.mrr)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-green-600">
                +{formatPercentage(metrics.revenue.monthly_growth)} growth
              </span>
            </div>
          </Card>
          
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Annual Recurring Revenue</h3>
            <p className="text-3xl font-bold text-green-600">{formatCurrency(metrics.subscriptions.arr)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">Projected yearly</span>
            </div>
          </Card>
          
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">ARPU</h3>
            <p className="text-3xl font-bold text-blue-600">{formatCurrency(metrics.revenue.average_revenue_per_user)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">Avg revenue per user</span>
            </div>
          </Card>
          
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Customer LTV</h3>
            <p className="text-3xl font-bold text-purple-600">{formatCurrency(metrics.revenue.lifetime_value)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">Lifetime value</span>
            </div>
          </Card>
        </div>
      </div>

      {/* Subscription Metrics */}
      <div>
        <h2 className="text-xl font-semibold text-wedding-navy dark:text-gray-100 mb-4">Subscriptions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Active Subscriptions</h3>
            <p className="text-3xl font-bold text-green-600">{formatNumber(metrics.subscriptions.active)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {formatPercentage((metrics.subscriptions.active / metrics.subscriptions.total) * 100)} of total
              </span>
            </div>
          </Card>
          
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Trial Users</h3>
            <p className="text-3xl font-bold text-blue-600">{formatNumber(metrics.subscriptions.trial)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">Currently on trial</span>
            </div>
          </Card>
          
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Churn This Month</h3>
            <p className="text-3xl font-bold text-red-600">{formatNumber(metrics.subscriptions.churned_this_month)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {formatPercentage((metrics.subscriptions.churned_this_month / metrics.subscriptions.total) * 100)} churn rate
              </span>
            </div>
          </Card>
          
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Subscriptions</h3>
            <p className="text-3xl font-bold text-wedding-navy">{formatNumber(metrics.subscriptions.total)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">All time</span>
            </div>
          </Card>
        </div>
      </div>

      {/* Usage Metrics */}
      <div>
        <h2 className="text-xl font-semibold text-wedding-navy dark:text-gray-100 mb-4">Platform Usage</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Weddings Created</h3>
            <p className="text-3xl font-bold text-wedding-rose">{formatNumber(metrics.usage.weddings_created)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">This period</span>
            </div>
          </Card>
          
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Guests Managed</h3>
            <p className="text-3xl font-bold text-blue-600">{formatNumber(metrics.usage.guests_managed)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">Total guests</span>
            </div>
          </Card>
          
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Forms Created</h3>
            <p className="text-3xl font-bold text-green-600">{formatNumber(metrics.usage.forms_created)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">Custom forms</span>
            </div>
          </Card>
        </div>
      </div>

      {/* Communication Metrics */}
      <div>
        <h2 className="text-xl font-semibold text-wedding-navy dark:text-gray-100 mb-4">Communications</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Emails Sent</h3>
            <p className="text-3xl font-bold text-blue-600">{formatNumber(metrics.usage.emails_sent)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">This period</span>
            </div>
          </Card>
          
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">SMS Sent</h3>
            <p className="text-3xl font-bold text-green-600">{formatNumber(metrics.usage.sms_sent)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">This period</span>
            </div>
          </Card>
        </div>
      </div>

      {/* System Performance */}
      <div>
        <h2 className="text-xl font-semibold text-wedding-navy dark:text-gray-100 mb-4">System Performance</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Uptime</h3>
            <p className="text-3xl font-bold text-green-600">{formatPercentage(metrics.performance.uptime)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-green-600">Excellent</span>
            </div>
          </Card>
          
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Response Time</h3>
            <p className="text-3xl font-bold text-blue-600">{metrics.performance.avg_response_time}ms</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">Average</span>
            </div>
          </Card>
          
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Error Rate</h3>
            <p className="text-3xl font-bold text-yellow-600">{formatPercentage(metrics.performance.error_rate)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-green-600">Within limits</span>
            </div>
          </Card>
          
          <Card className="p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">API Calls Today</h3>
            <p className="text-3xl font-bold text-purple-600">{formatNumber(metrics.performance.api_calls_today)}</p>
            <div className="flex items-center mt-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">24 hours</span>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}