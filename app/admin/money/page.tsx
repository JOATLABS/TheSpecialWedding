'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import {
  Loader2,
  DollarSign,
  TrendingUp,
  TrendingDown,
  ArrowUpRight,
  ArrowDownRight,
  Calendar,
  CreditCard,
  Receipt,
  Building2,
  Users,
  ChevronRight,
  Filter,
  Download,
  RefreshCw,
  CheckCircle,
  Clock,
  XCircle,
  AlertTriangle,
  Zap,
  ExternalLink
} from 'lucide-react';

interface PaymentSummary {
  total_incoming: number;
  total_outgoing: number;
  net_cash_flow: number;
  pending_incoming: number;
  pending_outgoing: number;
}

interface ScheduledPayment {
  id: string;
  contract_id: string;
  couple_name: string;
  wedding_title: string;
  name: string;
  amount: number;
  currency: string;
  due_date: string;
  status: 'scheduled' | 'processing' | 'succeeded' | 'failed' | 'paid_externally';
  paid_at?: string;
  card_last4?: string;
  card_brand?: string;
  payment_method_type?: string;
}

interface VendorPayment {
  id: string;
  vendor_name: string;
  vendor_email?: string;
  category: string;
  wedding_title?: string;
  wedding_id?: string;
  amount: number;
  budgeted?: number;
  due_date?: string | null;
  status: 'pending' | 'paid' | 'partial' | 'overdue';
  paid_at?: string | null;
}

interface CashFlowEvent {
  id: string;
  date: string;
  type: 'incoming' | 'outgoing' | 'subscription';
  description: string;
  amount: number;
  status: string;
}

interface SubscriptionSummary {
  plan_name: string;
  status: string;
  billing_interval: string;
  price: number;
  current_period_end: string;
  card_last_four?: string;
  card_brand?: string;
  ai_credits_used: number;
  ai_credits_total: number;
  weddings_used: number;
  weddings_total: number;
}

type TabType = 'overview' | 'incoming' | 'outgoing' | 'timeline';
type SortField = 'due_date' | 'amount' | 'couple_name';
type SortOrder = 'asc' | 'desc';
type PaymentStatus = 'all' | 'scheduled' | 'processing' | 'succeeded' | 'failed' | 'paid_externally';

export default function MoneyDashboard() {
  const router = useRouter();
  const { token: adminToken } = useAdmin();
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [summary, setSummary] = useState<PaymentSummary | null>(null);
  const [incomingPayments, setIncomingPayments] = useState<ScheduledPayment[]>([]);
  const [outgoingPayments, setOutgoingPayments] = useState<VendorPayment[]>([]);
  const [cashFlow, setCashFlow] = useState<CashFlowEvent[]>([]);
  const [dateFilter, setDateFilter] = useState<'30d' | '90d' | '1y' | 'all'>('30d');

  // Filter & Sort state for incoming payments
  const [statusFilter, setStatusFilter] = useState<PaymentStatus>('all');
  const [coupleFilter, setCoupleFilter] = useState<string>('all');
  const [sortField, setSortField] = useState<SortField>('due_date');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');
  const [showFilters, setShowFilters] = useState(false);

  // Mark External Modal state
  const [showMarkExternalModal, setShowMarkExternalModal] = useState(false);
  const [selectedPayment, setSelectedPayment] = useState<ScheduledPayment | null>(null);
  const [externalPaymentMethod, setExternalPaymentMethod] = useState('cash');
  const [externalPaymentNote, setExternalPaymentNote] = useState('');

  // Subscription state
  const [subscription, setSubscription] = useState<SubscriptionSummary | null>(null);

  const fetchMoneyData = useCallback(async () => {
    if (!adminToken) return;

    setLoading(true);
    try {
      const baseUrl = getApiBaseUrl();
      const headers = {
        'Authorization': `Bearer ${adminToken}`,
        'Content-Type': 'application/json'
      };

      // Fetch all money data in parallel
      const [summaryRes, incomingRes, contractsRes] = await Promise.all([
        fetch(`${baseUrl}/admin/autopilot/status`, { headers }),
        fetch(`${baseUrl}/admin/contracts?status=signed`, { headers }),
        fetch(`${baseUrl}/admin/contracts?status=active`, { headers })
      ]);

      // Process incoming payments from contracts
      if (incomingRes.ok || contractsRes.ok) {
        const signedData = incomingRes.ok ? await incomingRes.json() : { contracts: [] };
        const activeData = contractsRes.ok ? await contractsRes.json() : { contracts: [] };
        const allContracts = [...(signedData.contracts || []), ...(activeData.contracts || [])];

        // Fetch scheduled payments for each contract
        const paymentsPromises = allContracts.map(async (contract: { id: string; couple?: { name?: string }; package_snapshot?: { name?: string } }) => {
          try {
            const paymentsRes = await fetch(`${baseUrl}/admin/contracts/${contract.id}/payments`, { headers });
            if (paymentsRes.ok) {
              const paymentsData = await paymentsRes.json();
              return (paymentsData.payments || []).map((p: ScheduledPayment) => ({
                ...p,
                couple_name: contract.couple?.name || 'Unknown',
                wedding_title: contract.package_snapshot?.name || 'Wedding'
              }));
            }
          } catch {
            return [];
          }
          return [];
        });

        const allPayments = (await Promise.all(paymentsPromises)).flat();
        setIncomingPayments(allPayments);

        // Calculate summary
        const totalIncoming = allPayments
          .filter((p: ScheduledPayment) => p.status === 'succeeded')
          .reduce((sum: number, p: ScheduledPayment) => sum + (p.amount || 0), 0);

        const pendingIncoming = allPayments
          .filter((p: ScheduledPayment) => p.status === 'scheduled')
          .reduce((sum: number, p: ScheduledPayment) => sum + (p.amount || 0), 0);

        setSummary({
          total_incoming: totalIncoming,
          total_outgoing: 0, // Will be updated when vendor payments are fetched
          net_cash_flow: totalIncoming,
          pending_incoming: pendingIncoming,
          pending_outgoing: 0
        });
      }

      // Fetch vendor payments from budgets (outgoing)
      try {
        const weddingsRes = await fetch(`${baseUrl}/weddings`, { headers });
        if (weddingsRes.ok) {
          const weddingsData = await weddingsRes.json();
          const weddings = weddingsData.weddings || weddingsData || [];

          // Fetch budget data for each wedding to get vendor payments
          const vendorPaymentsPromises = weddings.map(async (wedding: { _id?: string; id?: string; title?: string }) => {
            const weddingId = wedding._id || wedding.id;
            if (!weddingId) return [];
            try {
              const budgetRes = await fetch(`${baseUrl}/weddings/${weddingId}/budget`, { headers });
              if (budgetRes.ok) {
                const budgetData = await budgetRes.json();
                const categories = budgetData.categories || [];
                // Extract vendor payment info from categories
                return categories
                  .filter((cat: { vendor_name?: string; actual_spent?: number }) => cat.vendor_name && cat.actual_spent)
                  .map((cat: {
                    _id?: string;
                    id?: string;
                    vendor_name?: string;
                    vendor_email?: string;
                    name?: string;
                    actual_spent?: number;
                    budgeted_amount?: number;
                    payment_status?: string;
                    payments?: Array<{ payment_date?: string }>;
                  }) => ({
                    id: cat._id || cat.id || `${weddingId}-${cat.vendor_name}`,
                    vendor_name: cat.vendor_name || 'Unknown Vendor',
                    vendor_email: cat.vendor_email,
                    category: cat.name || 'Service',
                    wedding_title: wedding.title || 'Wedding',
                    wedding_id: weddingId,
                    amount: cat.actual_spent || 0,
                    budgeted: cat.budgeted_amount || 0,
                    status: cat.payment_status || 'pending',
                    due_date: null, // Budget categories don't have due dates by default
                    paid_at: cat.payments?.length ? cat.payments[cat.payments.length - 1]?.payment_date : null
                  }));
              }
            } catch {
              return [];
            }
            return [];
          });

          const allVendorPayments = (await Promise.all(vendorPaymentsPromises)).flat();
          setOutgoingPayments(allVendorPayments);

          // Update summary with outgoing
          const totalOutgoing = allVendorPayments
            .filter((p: VendorPayment) => p.status === 'paid')
            .reduce((sum: number, p: VendorPayment) => sum + (p.amount || 0), 0);

          const pendingOutgoing = allVendorPayments
            .filter((p: VendorPayment) => p.status === 'pending' || p.status === 'partial')
            .reduce((sum: number, p: VendorPayment) => sum + (p.amount || 0), 0);

          setSummary(prev => prev ? {
            ...prev,
            total_outgoing: totalOutgoing,
            pending_outgoing: pendingOutgoing,
            net_cash_flow: prev.total_incoming - totalOutgoing
          } : null);
        }
      } catch (vendorError) {
        console.error('Error fetching vendor payments:', vendorError);
        // Non-fatal, continue without vendor data
      }

      // Fetch subscription summary
      try {
        const subRes = await fetch(`${baseUrl}/stripe/subscription`, { headers });
        if (subRes.ok) {
          const subData = await subRes.json();
          if (subData && subData.plan_id) {
            // Fetch plan details and usage
            const [plansRes, weddingsRes] = await Promise.all([
              fetch(`${baseUrl}/public/subscription-plans`),
              fetch(`${baseUrl}/admin/weddings`, { headers })
            ]);

            let planName = 'Unknown Plan';
            let aiCreditsTotal = 100;
            let weddingsTotal = 3;
            let price = 0;

            if (plansRes.ok) {
              const plans = await plansRes.json();
              const plan = plans.find((p: { _id: string; name: string; ai_credits_monthly: number; max_weddings: number; price_monthly: number; price_yearly: number }) => p._id === subData.plan_id);
              if (plan) {
                planName = plan.name;
                aiCreditsTotal = plan.ai_credits_monthly;
                weddingsTotal = plan.max_weddings;
                price = subData.billing_interval === 'yearly' ? plan.price_yearly : plan.price_monthly;
              }
            }

            let weddingsUsed = 0;
            if (weddingsRes.ok) {
              const weddingsData = await weddingsRes.json();
              weddingsUsed = (weddingsData.weddings || weddingsData || []).length;
            }

            setSubscription({
              plan_name: planName,
              status: subData.status,
              billing_interval: subData.billing_interval,
              price,
              current_period_end: subData.current_period_end,
              card_last_four: subData.card_last_four,
              card_brand: subData.card_brand,
              ai_credits_used: 0, // TODO: Get from AI usage endpoint
              ai_credits_total: aiCreditsTotal,
              weddings_used: weddingsUsed,
              weddings_total: weddingsTotal
            });
          }
        }
      } catch (subError) {
        console.error('Error fetching subscription:', subError);
        // Non-fatal
      }

    } catch (error) {
      console.error('Error fetching money data:', error);
      toast.error('Failed to load financial data');
    } finally {
      setLoading(false);
    }
  }, [adminToken]);

  useEffect(() => {
    fetchMoneyData();
  }, [fetchMoneyData]);

  // Build cash flow timeline when incoming payments change
  useEffect(() => {
    const events: CashFlowEvent[] = incomingPayments.map(p => ({
      id: p.id,
      date: p.paid_at || p.due_date,
      type: 'incoming' as const,
      description: `${p.couple_name} - ${p.name}`,
      amount: p.amount,
      status: p.status
    }));
    events.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
    setCashFlow(events);
  }, [incomingPayments]);

  // Get unique couple names for filter dropdown
  const uniqueCouples = Array.from(new Set(incomingPayments.map(p => p.couple_name))).sort();

  // Filter and sort incoming payments
  const filteredAndSortedPayments = incomingPayments
    .filter(p => {
      if (statusFilter !== 'all' && p.status !== statusFilter) return false;
      if (coupleFilter !== 'all' && p.couple_name !== coupleFilter) return false;
      return true;
    })
    .sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case 'due_date':
          comparison = new Date(a.due_date).getTime() - new Date(b.due_date).getTime();
          break;
        case 'amount':
          comparison = a.amount - b.amount;
          break;
        case 'couple_name':
          comparison = a.couple_name.localeCompare(b.couple_name);
          break;
      }
      return sortOrder === 'asc' ? comparison : -comparison;
    });

  // Action handlers
  const handleRetryPayment = async (payment: ScheduledPayment) => {
    if (!adminToken) return;
    setActionLoading(payment.id);
    try {
      const baseUrl = getApiBaseUrl();
      const res = await fetch(`${baseUrl}/admin/payments/${payment.id}/retry`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${adminToken}`,
          'Content-Type': 'application/json'
        }
      });
      if (res.ok) {
        toast.success('Payment retry initiated');
        fetchMoneyData();
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Failed to retry payment');
      }
    } catch {
      toast.error('Failed to retry payment');
    } finally {
      setActionLoading(null);
    }
  };

  const handleCancelPayment = async (payment: ScheduledPayment) => {
    if (!adminToken) return;
    if (!confirm(`Cancel scheduled payment of ${formatCurrency(payment.amount)} from ${payment.couple_name}?`)) return;

    setActionLoading(payment.id);
    try {
      const baseUrl = getApiBaseUrl();
      const res = await fetch(`${baseUrl}/admin/payments/${payment.id}/cancel`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${adminToken}`,
          'Content-Type': 'application/json'
        }
      });
      if (res.ok) {
        toast.success('Payment cancelled');
        fetchMoneyData();
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Failed to cancel payment');
      }
    } catch {
      toast.error('Failed to cancel payment');
    } finally {
      setActionLoading(null);
    }
  };

  const handleMarkExternalSubmit = async () => {
    if (!selectedPayment || !adminToken) return;
    setActionLoading(selectedPayment.id);
    try {
      const baseUrl = getApiBaseUrl();
      const res = await fetch(`${baseUrl}/admin/payments/${selectedPayment.id}/mark-paid-externally`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${adminToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          payment_method: externalPaymentMethod,
          note: externalPaymentNote
        })
      });
      if (res.ok) {
        toast.success('Payment marked as received externally');
        setShowMarkExternalModal(false);
        setSelectedPayment(null);
        setExternalPaymentMethod('cash');
        setExternalPaymentNote('');
        fetchMoneyData();
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Failed to mark payment');
      }
    } catch {
      toast.error('Failed to mark payment');
    } finally {
      setActionLoading(null);
    }
  };

  const openMarkExternalModal = (payment: ScheduledPayment) => {
    setSelectedPayment(payment);
    setShowMarkExternalModal(true);
  };

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

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      scheduled: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
      processing: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
      succeeded: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
      paid: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
      failed: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
      pending: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400',
      overdue: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
    };

    const icons: Record<string, React.ReactNode> = {
      scheduled: <Clock size={14} />,
      processing: <Loader2 size={14} className="animate-spin" />,
      succeeded: <CheckCircle size={14} />,
      paid: <CheckCircle size={14} />,
      failed: <XCircle size={14} />,
      pending: <Clock size={14} />,
      overdue: <AlertTriangle size={14} />
    };

    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${styles[status] || styles.pending}`}>
        {icons[status]}
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-sans font-bold text-slate-900 dark:text-white">Money</h1>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            Unified view of all your financial transactions
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value as typeof dateFilter)}
            className="px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-200 text-sm"
          >
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
            <option value="1y">Last year</option>
            <option value="all">All time</option>
          </select>
          <Button variant="outline" size="sm" onClick={() => fetchMoneyData()}>
            <RefreshCw size={16} className="mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Incoming */}
        <Card className="p-6">
          <div className="flex items-center justify-between">
            <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
              <ArrowDownRight className="w-5 h-5 text-green-600" />
            </div>
            <TrendingUp className="w-5 h-5 text-green-500" />
          </div>
          <div className="mt-4">
            <p className="text-sm text-slate-600 dark:text-slate-400">Total Incoming</p>
            <p className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
              {formatCurrency(summary?.total_incoming || 0)}
            </p>
            <p className="text-xs text-green-600 mt-1">
              From couples (autopilot)
            </p>
          </div>
        </Card>

        {/* Pending Incoming */}
        <Card className="p-6">
          <div className="flex items-center justify-between">
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
              <Clock className="w-5 h-5 text-blue-600" />
            </div>
            <Calendar className="w-5 h-5 text-blue-500" />
          </div>
          <div className="mt-4">
            <p className="text-sm text-slate-600 dark:text-slate-400">Pending Incoming</p>
            <p className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
              {formatCurrency(summary?.pending_incoming || 0)}
            </p>
            <p className="text-xs text-blue-600 mt-1">
              Scheduled payments
            </p>
          </div>
        </Card>

        {/* Total Outgoing */}
        <Card className="p-6">
          <div className="flex items-center justify-between">
            <div className="p-2 bg-orange-100 dark:bg-orange-900/30 rounded-lg">
              <ArrowUpRight className="w-5 h-5 text-orange-600" />
            </div>
            <Building2 className="w-5 h-5 text-orange-500" />
          </div>
          <div className="mt-4">
            <p className="text-sm text-slate-600 dark:text-slate-400">Total Outgoing</p>
            <p className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
              {formatCurrency(summary?.total_outgoing || 0)}
            </p>
            <p className="text-xs text-orange-600 mt-1">
              To vendors
            </p>
          </div>
        </Card>

        {/* Net Cash Flow */}
        <Card className="p-6">
          <div className="flex items-center justify-between">
            <div className="p-2 bg-primary-100 dark:bg-primary-900/30 rounded-lg">
              <DollarSign className="w-5 h-5 text-primary-600" />
            </div>
            {(summary?.net_cash_flow || 0) >= 0 ? (
              <TrendingUp className="w-5 h-5 text-green-500" />
            ) : (
              <TrendingDown className="w-5 h-5 text-red-500" />
            )}
          </div>
          <div className="mt-4">
            <p className="text-sm text-slate-600 dark:text-slate-400">Net Cash Flow</p>
            <p className={`text-2xl font-bold mt-1 ${
              (summary?.net_cash_flow || 0) >= 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              {formatCurrency(summary?.net_cash_flow || 0)}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Incoming - Outgoing
            </p>
          </div>
        </Card>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200 dark:border-slate-700">
        <nav className="flex gap-6">
          {[
            { id: 'overview', label: 'Overview', icon: DollarSign },
            { id: 'incoming', label: 'Incoming', icon: ArrowDownRight },
            { id: 'outgoing', label: 'Outgoing', icon: ArrowUpRight },
            { id: 'timeline', label: 'Timeline', icon: Calendar }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as TabType)}
              className={`flex items-center gap-2 pb-3 border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400'
              }`}
            >
              <tab.icon size={18} />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Incoming */}
          <Card>
            <div className="p-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
              <h2 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                <ArrowDownRight size={18} className="text-green-500" />
                Recent Incoming
              </h2>
              <Button variant="ghost" size="sm" onClick={() => setActiveTab('incoming')}>
                View All <ChevronRight size={16} />
              </Button>
            </div>
            <div className="divide-y divide-slate-200 dark:divide-slate-700">
              {incomingPayments.slice(0, 5).map((payment) => (
                <div key={payment.id} className="p-4 flex items-center justify-between">
                  <div>
                    <p className="font-medium text-slate-900 dark:text-white">{payment.couple_name}</p>
                    <p className="text-sm text-slate-600 dark:text-slate-400">{payment.name}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold text-slate-900 dark:text-white">
                      {formatCurrency(payment.amount, payment.currency)}
                    </p>
                    {getStatusBadge(payment.status)}
                  </div>
                </div>
              ))}
              {incomingPayments.length === 0 && (
                <div className="p-8 text-center text-slate-500 dark:text-slate-400">
                  <Users className="w-12 h-12 mx-auto mb-3 text-slate-300 dark:text-slate-500" />
                  <p>No incoming payments yet</p>
                  <p className="text-sm mt-1">Create contracts to receive autopilot payments</p>
                </div>
              )}
            </div>
          </Card>

          {/* Upcoming Payments */}
          <Card>
            <div className="p-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
              <h2 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                <Calendar size={18} className="text-blue-500" />
                Upcoming Payments
              </h2>
            </div>
            <div className="divide-y divide-slate-200 dark:divide-slate-700">
              {incomingPayments
                .filter(p => p.status === 'scheduled')
                .sort((a, b) => new Date(a.due_date).getTime() - new Date(b.due_date).getTime())
                .slice(0, 5)
                .map((payment) => (
                  <div key={payment.id} className="p-4 flex items-center justify-between">
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">{payment.couple_name}</p>
                      <p className="text-sm text-slate-600 dark:text-slate-400">
                        Due {formatDate(payment.due_date)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-slate-900 dark:text-white">
                        {formatCurrency(payment.amount, payment.currency)}
                      </p>
                      <p className="text-xs text-slate-500">{payment.name}</p>
                    </div>
                  </div>
                ))}
              {incomingPayments.filter(p => p.status === 'scheduled').length === 0 && (
                <div className="p-8 text-center text-slate-500 dark:text-slate-400">
                  <Clock className="w-12 h-12 mx-auto mb-3 text-slate-300 dark:text-slate-500" />
                  <p>No upcoming payments</p>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'incoming' && (
        <Card>
          <div className="p-4 border-b border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-slate-900 dark:text-white">
                Incoming Payments from Couples
              </h2>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => setShowFilters(!showFilters)}>
                  <Filter size={16} className="mr-2" />
                  {showFilters ? 'Hide Filters' : 'Filter'}
                </Button>
                <Button variant="outline" size="sm">
                  <Download size={16} className="mr-2" />
                  Export
                </Button>
              </div>
            </div>

            {/* Filter & Sort Controls */}
            {showFilters && (
              <div className="flex flex-wrap gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                {/* Status Filter */}
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-medium text-slate-500 uppercase">Status</label>
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value as PaymentStatus)}
                    className="px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-200 text-sm min-w-[140px]"
                  >
                    <option value="all">All Statuses</option>
                    <option value="scheduled">Scheduled</option>
                    <option value="processing">Processing</option>
                    <option value="succeeded">Succeeded</option>
                    <option value="failed">Failed</option>
                    <option value="paid_externally">Paid Externally</option>
                  </select>
                </div>

                {/* Couple Filter */}
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-medium text-slate-500 uppercase">Couple</label>
                  <select
                    value={coupleFilter}
                    onChange={(e) => setCoupleFilter(e.target.value)}
                    className="px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-200 text-sm min-w-[160px]"
                  >
                    <option value="all">All Couples</option>
                    {uniqueCouples.map(couple => (
                      <option key={couple} value={couple}>{couple}</option>
                    ))}
                  </select>
                </div>

                {/* Sort Field */}
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-medium text-slate-500 uppercase">Sort By</label>
                  <select
                    value={sortField}
                    onChange={(e) => setSortField(e.target.value as SortField)}
                    className="px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-200 text-sm min-w-[140px]"
                  >
                    <option value="due_date">Due Date</option>
                    <option value="amount">Amount</option>
                    <option value="couple_name">Couple Name</option>
                  </select>
                </div>

                {/* Sort Order */}
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-medium text-slate-500 uppercase">Order</label>
                  <select
                    value={sortOrder}
                    onChange={(e) => setSortOrder(e.target.value as SortOrder)}
                    className="px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-200 text-sm min-w-[120px]"
                  >
                    <option value="asc">Ascending</option>
                    <option value="desc">Descending</option>
                  </select>
                </div>

                {/* Reset Filters */}
                <div className="flex flex-col gap-1 justify-end">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setStatusFilter('all');
                      setCoupleFilter('all');
                      setSortField('due_date');
                      setSortOrder('asc');
                    }}
                  >
                    Reset
                  </Button>
                </div>
              </div>
            )}

            {/* Results count */}
            <p className="text-sm text-slate-500 mt-2">
              Showing {filteredAndSortedPayments.length} of {incomingPayments.length} payments
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50 dark:bg-slate-800/50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Couple</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Payment</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Amount</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Due Date</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Card</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                {filteredAndSortedPayments.map((payment) => (
                  <tr key={payment.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                    <td className="px-4 py-4">
                      <p className="font-medium text-slate-900 dark:text-white">{payment.couple_name}</p>
                      <p className="text-sm text-slate-500">{payment.wedding_title}</p>
                    </td>
                    <td className="px-4 py-4 text-slate-700 dark:text-slate-300">{payment.name}</td>
                    <td className="px-4 py-4 font-semibold text-slate-900 dark:text-white">
                      {formatCurrency(payment.amount, payment.currency)}
                    </td>
                    <td className="px-4 py-4 text-slate-600 dark:text-slate-400">
                      {formatDate(payment.due_date)}
                    </td>
                    <td className="px-4 py-4">
                      {payment.card_last4 ? (
                        <div className="flex items-center gap-1.5">
                          <CreditCard size={14} className="text-slate-400" />
                          <span className="text-sm text-slate-600 dark:text-slate-400">
                            {payment.card_brand || 'Card'} •••• {payment.card_last4}
                          </span>
                        </div>
                      ) : (
                        <span className="text-sm text-slate-400">No card</span>
                      )}
                    </td>
                    <td className="px-4 py-4">{getStatusBadge(payment.status)}</td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-1">
                        {/* Retry button - only for failed payments */}
                        {payment.status === 'failed' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRetryPayment(payment)}
                            disabled={actionLoading === payment.id}
                            className="text-blue-600 hover:text-blue-700 hover:bg-blue-50 dark:hover:bg-blue-900/20"
                          >
                            {actionLoading === payment.id ? (
                              <Loader2 size={14} className="animate-spin" />
                            ) : (
                              <RefreshCw size={14} />
                            )}
                          </Button>
                        )}

                        {/* Cancel button - only for scheduled payments */}
                        {payment.status === 'scheduled' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleCancelPayment(payment)}
                            disabled={actionLoading === payment.id}
                            className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20"
                          >
                            {actionLoading === payment.id ? (
                              <Loader2 size={14} className="animate-spin" />
                            ) : (
                              <XCircle size={14} />
                            )}
                          </Button>
                        )}

                        {/* Mark External button - for scheduled or failed */}
                        {(payment.status === 'scheduled' || payment.status === 'failed') && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openMarkExternalModal(payment)}
                            disabled={actionLoading === payment.id}
                            className="text-green-600 hover:text-green-700 hover:bg-green-50 dark:hover:bg-green-900/20"
                            title="Mark as paid externally"
                          >
                            <CheckCircle size={14} />
                          </Button>
                        )}

                        {/* No actions for succeeded/paid_externally */}
                        {(payment.status === 'succeeded' || payment.status === 'paid_externally') && (
                          <span className="text-xs text-slate-400">—</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredAndSortedPayments.length === 0 && (
              <div className="p-12 text-center text-slate-500 dark:text-slate-400">
                <Receipt className="w-12 h-12 mx-auto mb-3 text-slate-300 dark:text-slate-500" />
                <p>No payments match your filters</p>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Mark External Payment Modal */}
      {showMarkExternalModal && selectedPayment && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
              Mark Payment as Received Externally
            </h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
              {selectedPayment.couple_name} - {formatCurrency(selectedPayment.amount)}
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Payment Method
                </label>
                <select
                  value={externalPaymentMethod}
                  onChange={(e) => setExternalPaymentMethod(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-200"
                >
                  <option value="cash">Cash</option>
                  <option value="check">Check</option>
                  <option value="bank_transfer">Bank Transfer</option>
                  <option value="venmo">Venmo</option>
                  <option value="zelle">Zelle</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Note (optional)
                </label>
                <textarea
                  value={externalPaymentNote}
                  onChange={(e) => setExternalPaymentNote(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-200 placeholder:text-slate-400 dark:placeholder:text-slate-500 resize-none"
                  rows={3}
                  placeholder="e.g., Check #1234, received on 12/25"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <Button
                variant="outline"
                onClick={() => {
                  setShowMarkExternalModal(false);
                  setSelectedPayment(null);
                  setExternalPaymentMethod('cash');
                  setExternalPaymentNote('');
                }}
              >
                Cancel
              </Button>
              <Button
                onClick={handleMarkExternalSubmit}
                disabled={actionLoading === selectedPayment.id}
              >
                {actionLoading === selectedPayment.id ? (
                  <Loader2 size={16} className="animate-spin mr-2" />
                ) : null}
                Mark as Paid
              </Button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'outgoing' && (
        <Card>
          <div className="p-4 border-b border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-semibold text-slate-900 dark:text-white">
                Outgoing Payments to Vendors
              </h2>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm">
                  <Filter size={16} className="mr-2" />
                  Filter
                </Button>
                <Button variant="outline" size="sm">
                  <Download size={16} className="mr-2" />
                  Export
                </Button>
              </div>
            </div>
            <p className="text-sm text-slate-500">
              {outgoingPayments.length} vendor payments tracked
            </p>
          </div>

          {outgoingPayments.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 dark:bg-slate-800/50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Vendor</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Service</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Wedding</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Paid</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Budget</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                  {outgoingPayments.map((payment) => (
                    <tr key={payment.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                      <td className="px-4 py-4">
                        <p className="font-medium text-slate-900 dark:text-white">{payment.vendor_name}</p>
                        {payment.vendor_email && (
                          <p className="text-sm text-slate-500">{payment.vendor_email}</p>
                        )}
                      </td>
                      <td className="px-4 py-4 text-slate-700 dark:text-slate-300">{payment.category}</td>
                      <td className="px-4 py-4 text-slate-600 dark:text-slate-400">{payment.wedding_title || 'Wedding'}</td>
                      <td className="px-4 py-4 font-semibold text-slate-900 dark:text-white">
                        {formatCurrency(payment.amount)}
                      </td>
                      <td className="px-4 py-4 text-slate-600 dark:text-slate-400">
                        {payment.budgeted ? formatCurrency(payment.budgeted) : '—'}
                      </td>
                      <td className="px-4 py-4">{getStatusBadge(payment.status)}</td>
                      <td className="px-4 py-4">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            if (payment.wedding_id) {
                              router.push(`/admin/budget?wedding=${payment.wedding_id}`);
                            }
                          }}
                          className="text-slate-600 hover:text-slate-900"
                        >
                          <ChevronRight size={14} />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-12 text-center text-slate-500 dark:text-slate-400">
              <Building2 className="w-12 h-12 mx-auto mb-3 text-slate-300 dark:text-slate-500" />
              <p>No vendor payments tracked yet</p>
              <p className="text-sm mt-1">Add vendors to your wedding budgets to track payments here</p>
              <Button
                variant="outline"
                className="mt-4"
                onClick={() => router.push('/admin/budget')}
              >
                Go to Budget
              </Button>
            </div>
          )}
        </Card>
      )}

      {activeTab === 'timeline' && (
        <Card>
          <div className="p-4 border-b border-slate-200 dark:border-slate-700">
            <h2 className="font-semibold text-slate-900 dark:text-white">
              Cash Flow Timeline
            </h2>
          </div>
          <div className="p-6">
            <div className="relative">
              {/* Timeline line */}
              <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-slate-200 dark:bg-slate-700" />

              {/* Timeline events */}
              <div className="space-y-6">
                {cashFlow.slice(0, 20).map((event) => (
                  <div key={event.id} className="relative pl-10">
                    <div className={`absolute left-2 w-5 h-5 rounded-full flex items-center justify-center ${
                      event.type === 'incoming'
                        ? 'bg-green-100 dark:bg-green-900/30'
                        : 'bg-orange-100 dark:bg-orange-900/30'
                    }`}>
                      {event.type === 'incoming' ? (
                        <ArrowDownRight size={12} className="text-green-600" />
                      ) : (
                        <ArrowUpRight size={12} className="text-orange-600" />
                      )}
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">
                          {event.description}
                        </p>
                        <p className="text-sm text-slate-500">{formatDate(event.date)}</p>
                      </div>
                      <div className="text-right">
                        <p className={`font-semibold ${
                          event.type === 'incoming' ? 'text-green-600' : 'text-orange-600'
                        }`}>
                          {event.type === 'incoming' ? '+' : '-'}{formatCurrency(event.amount)}
                        </p>
                        {getStatusBadge(event.status)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {cashFlow.length === 0 && (
                <div className="text-center text-slate-500 dark:text-slate-400 py-12">
                  <Calendar className="w-12 h-12 mx-auto mb-3 text-slate-300 dark:text-slate-500" />
                  <p>No transactions yet</p>
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Subscription Summary */}
      {subscription && (
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2">
              <Receipt size={18} className="text-primary-500" />
              Subscription
            </h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => router.push('/admin/planner/billing')}
              className="text-primary-600"
            >
              Manage <ExternalLink size={14} className="ml-1" />
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Plan Info */}
            <div className="space-y-1">
              <p className="text-sm text-slate-500 dark:text-slate-400">Current Plan</p>
              <p className="font-semibold text-slate-900 dark:text-white">{subscription.plan_name}</p>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                {formatCurrency(subscription.price)}/{subscription.billing_interval === 'yearly' ? 'year' : 'month'}
              </p>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                subscription.status === 'active'
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                  : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
              }`}>
                {subscription.status.charAt(0).toUpperCase() + subscription.status.slice(1)}
              </span>
            </div>

            {/* Next Billing */}
            <div className="space-y-1">
              <p className="text-sm text-slate-500 dark:text-slate-400">Next Billing</p>
              <p className="font-semibold text-slate-900 dark:text-white">
                {subscription.current_period_end ? formatDate(subscription.current_period_end) : '—'}
              </p>
              {subscription.card_last_four && (
                <div className="flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-400">
                  <CreditCard size={14} />
                  {subscription.card_brand || 'Card'} •••• {subscription.card_last_four}
                </div>
              )}
            </div>

            {/* Weddings Usage */}
            <div className="space-y-1">
              <p className="text-sm text-slate-500 dark:text-slate-400">Weddings</p>
              <p className="font-semibold text-slate-900 dark:text-white">
                {subscription.weddings_used} / {subscription.weddings_total}
              </p>
              <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
                <div
                  className="bg-primary-500 h-2 rounded-full transition-all"
                  style={{ width: `${Math.min((subscription.weddings_used / subscription.weddings_total) * 100, 100)}%` }}
                />
              </div>
              <p className="text-xs text-slate-500">
                {subscription.weddings_total - subscription.weddings_used} remaining
              </p>
            </div>

            {/* AI Credits Usage */}
            <div className="space-y-1">
              <p className="text-sm text-slate-500 dark:text-slate-400 flex items-center gap-1">
                <Zap size={14} className="text-yellow-500" />
                AI Credits
              </p>
              <p className="font-semibold text-slate-900 dark:text-white">
                {subscription.ai_credits_used} / {subscription.ai_credits_total}
              </p>
              <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
                <div
                  className="bg-yellow-500 h-2 rounded-full transition-all"
                  style={{ width: `${Math.min((subscription.ai_credits_used / subscription.ai_credits_total) * 100, 100)}%` }}
                />
              </div>
              <p className="text-xs text-slate-500">
                {subscription.ai_credits_total - subscription.ai_credits_used} remaining this month
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Quick Actions */}
      <Card className="p-6">
        <h2 className="font-semibold text-slate-900 dark:text-white mb-4">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          <Button variant="outline" onClick={() => router.push('/admin/packages')}>
            <CreditCard size={18} className="mr-2" />
            Create Package
          </Button>
          <Button variant="outline" onClick={() => router.push('/admin/vendors')}>
            <Building2 size={18} className="mr-2" />
            Manage Vendors
          </Button>
          <Button variant="outline" onClick={() => router.push('/admin/planner/billing')}>
            <Receipt size={18} className="mr-2" />
            Subscription Billing
          </Button>
        </div>
      </Card>
    </div>
  );
}
