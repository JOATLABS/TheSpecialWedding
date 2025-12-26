'use client';

import { useState, useEffect, useCallback } from 'react';
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
  AlertTriangle
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
  status: 'scheduled' | 'processing' | 'succeeded' | 'failed';
  paid_at?: string;
}

interface VendorPayment {
  id: string;
  vendor_name: string;
  category: string;
  amount: number;
  due_date?: string;
  status: 'pending' | 'paid' | 'overdue';
  paid_at?: string;
}

interface CashFlowEvent {
  id: string;
  date: string;
  type: 'incoming' | 'outgoing' | 'subscription';
  description: string;
  amount: number;
  status: string;
}

type TabType = 'overview' | 'incoming' | 'outgoing' | 'timeline';

export default function MoneyDashboard() {
  const { token: adminToken, userProfile } = useAdmin();
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [summary, setSummary] = useState<PaymentSummary | null>(null);
  const [incomingPayments, setIncomingPayments] = useState<ScheduledPayment[]>([]);
  const [outgoingPayments, setOutgoingPayments] = useState<VendorPayment[]>([]);
  const [cashFlow, setCashFlow] = useState<CashFlowEvent[]>([]);
  const [dateFilter, setDateFilter] = useState<'30d' | '90d' | '1y' | 'all'>('30d');

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

      // Build cash flow timeline
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

    } catch (error) {
      console.error('Error fetching money data:', error);
      toast.error('Failed to load financial data');
    } finally {
      setLoading(false);
    }
  }, [adminToken, incomingPayments]);

  useEffect(() => {
    fetchMoneyData();
  }, [fetchMoneyData]);

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
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Money</h1>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            Unified view of all your financial transactions
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value as typeof dateFilter)}
            className="px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800 text-sm"
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
                <div className="p-8 text-center text-slate-500">
                  <Users className="w-12 h-12 mx-auto mb-3 text-slate-300" />
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
                <div className="p-8 text-center text-slate-500">
                  <Clock className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                  <p>No upcoming payments</p>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'incoming' && (
        <Card>
          <div className="p-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900 dark:text-white">
              Incoming Payments from Couples
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
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50 dark:bg-slate-800/50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Couple</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Payment</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Amount</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Due Date</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                {incomingPayments.map((payment) => (
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
                    <td className="px-4 py-4">{getStatusBadge(payment.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {incomingPayments.length === 0 && (
              <div className="p-12 text-center text-slate-500">
                <Receipt className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                <p>No incoming payments</p>
              </div>
            )}
          </div>
        </Card>
      )}

      {activeTab === 'outgoing' && (
        <Card>
          <div className="p-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
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
          <div className="p-12 text-center text-slate-500">
            <Building2 className="w-12 h-12 mx-auto mb-3 text-slate-300" />
            <p>Vendor payment tracking coming soon</p>
            <p className="text-sm mt-1">Track payments to your wedding vendors</p>
          </div>
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
                <div className="text-center text-slate-500 py-12">
                  <Calendar className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                  <p>No transactions yet</p>
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Quick Actions */}
      <Card className="p-6">
        <h2 className="font-semibold text-slate-900 dark:text-white mb-4">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          <Button variant="outline" onClick={() => window.location.href = '/admin/packages'}>
            <CreditCard size={18} className="mr-2" />
            Create Package
          </Button>
          <Button variant="outline" onClick={() => window.location.href = '/admin/vendors'}>
            <Building2 size={18} className="mr-2" />
            Manage Vendors
          </Button>
          <Button variant="outline" onClick={() => window.location.href = '/admin/planner/billing'}>
            <Receipt size={18} className="mr-2" />
            Subscription Billing
          </Button>
        </div>
      </Card>
    </div>
  );
}
