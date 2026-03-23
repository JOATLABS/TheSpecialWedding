'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import {
  Heart, Calendar, Users, DollarSign, FileText, Bell,
  Clock, MapPin, ChevronRight, LogOut, Loader2,
  CheckCircle, AlertCircle, XCircle, TrendingUp,
  Sparkles, Phone, Mail, Building2, Archive,
  ClipboardList, Send
} from 'lucide-react';

// ============================================================================
// TYPES
// ============================================================================

interface EventDetail {
  venue_name?: string;
  location?: string;
  time?: string;
  attire?: string;
  timezone?: string;
}

interface WeddingEvent {
  type: string;
  date: string;
  details?: EventDetail;
}

interface PlannerInfo {
  name?: string;
  company?: string;
  email?: string;
  phone?: string;
  profile_image_url?: string;
}

interface GuestStats {
  total_invited: number;
  confirmed: number;
  declined: number;
  pending: number;
}

interface BudgetSummary {
  total_budget: number;
  total_spent: number;
  remaining: number;
}

interface Payment {
  id: string;
  name: string;
  amount: number;
  currency: string;
  due_date: string;
  status: string;
  paid_at?: string;
}

interface ContractInfo {
  id: string;
  status: string;
  package_name: string;
  signed_at?: string;
  payments: Payment[];
  summary: {
    total_amount: number;
    paid_amount: number;
    remaining: number;
  };
}

interface FormItem {
  id: string;
  title: string;
  description?: string;
  status: string;
  submitted_at?: string;
  created_at?: string;
}

interface UpdateItem {
  id: string;
  type: string;
  title: string;
  content: string;
  category?: string;
  attachments: any[];
  is_milestone: boolean;
  created_at?: string;
  created_by?: string;
}

interface DashboardData {
  archived: boolean;
  archived_at?: string;
  wedding: {
    id: string;
    couple_names: string;
    date: string;
    timezone: string;
    venue?: string;
    cultural_style?: string;
    theme_config?: any;
    events: WeddingEvent[];
    registries: any[];
    faqs: any[];
  };
  planner?: PlannerInfo;
  guest_stats: GuestStats;
  budget_summary: BudgetSummary;
  contract?: ContractInfo;
  forms: FormItem[];
  updates: UpdateItem[];
}

type TabType = 'overview' | 'timeline' | 'payments' | 'forms' | 'updates';

// ============================================================================
// HELPERS
// ============================================================================

function formatCurrency(amount: number, currency: string = 'usd'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency.toUpperCase(),
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00');
  return date.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
}

function daysUntil(dateStr: string): number {
  const target = new Date(dateStr + 'T00:00:00');
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

function eventTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    traditional: 'Traditional Ceremony',
    white_wedding: 'White Wedding',
    reception: 'Reception',
    engagement: 'Engagement Party',
    rehearsal: 'Rehearsal Dinner',
  };
  return labels[type] || type.charAt(0).toUpperCase() + type.slice(1).replace(/_/g, ' ');
}

function paymentStatusColor(status: string): string {
  const colors: Record<string, string> = {
    succeeded: 'bg-green-100 text-green-700',
    scheduled: 'bg-blue-100 text-blue-700',
    processing: 'bg-yellow-100 text-yellow-700',
    failed: 'bg-red-100 text-red-700',
    cancelled: 'bg-gray-100 text-gray-500',
  };
  return colors[status] || 'bg-gray-100 text-gray-600';
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function CoupleDashboardPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<DashboardData | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  const fetchDashboard = useCallback(async () => {
    const token = localStorage.getItem('couple_token');
    if (!token) {
      router.push('/couple/login');
      return;
    }

    try {
      const res = await fetch(`${getApiBaseUrl()}/couple/portal/dashboard`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.status === 401) {
        localStorage.removeItem('couple_token');
        localStorage.removeItem('couple_data');
        router.push('/couple/login');
        return;
      }

      if (!res.ok) {
        const err = await res.json();
        toast.error(err.detail || 'Failed to load dashboard');
        return;
      }

      const dashboardData = await res.json();
      setData(dashboardData);
    } catch (err) {
      toast.error('Failed to connect to server');
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  const handleLogout = () => {
    localStorage.removeItem('couple_token');
    localStorage.removeItem('couple_data');
    router.push('/couple/login');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-10 h-10 animate-spin text-[#1e3a5f] mx-auto mb-4" />
          <p className="text-gray-500">Loading your wedding portal...</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-4" />
          <p className="text-gray-600 mb-4">Could not load your dashboard</p>
          <button onClick={fetchDashboard} className="text-[#1e3a5f] font-medium hover:underline">Try Again</button>
        </div>
      </div>
    );
  }

  const days = data.wedding?.date ? daysUntil(data.wedding.date) : null;

  const tabs: { key: TabType; label: string; icon: React.ReactNode; count?: number }[] = [
    { key: 'overview', label: 'Overview', icon: <Heart className="w-4 h-4" /> },
    { key: 'timeline', label: 'Timeline', icon: <Calendar className="w-4 h-4" />, count: data.wedding?.events?.length },
    { key: 'payments', label: 'Payments', icon: <DollarSign className="w-4 h-4" />, count: data.contract?.payments?.length },
    { key: 'forms', label: 'Forms', icon: <ClipboardList className="w-4 h-4" />, count: data.forms?.filter(f => f.status === 'pending').length },
    { key: 'updates', label: 'Updates', icon: <Bell className="w-4 h-4" />, count: data.updates?.length },
  ];

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-md border-b border-gray-100 sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-[#1e3a5f] rounded-full flex items-center justify-center">
              <Heart className="w-5 h-5 text-[#d4af37]" />
            </div>
            <div>
              <h1 className="text-lg font-serif text-[#1e3a5f] leading-tight">{data.wedding?.couple_names || 'Your Wedding'}</h1>
              <p className="text-xs text-gray-400 tracking-wide">WEDDING PORTAL</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-gray-400 hover:text-gray-600 transition-colors text-sm"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Sign Out</span>
          </button>
        </div>
      </header>

      {/* Archived Banner */}
      {data.archived && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-3">
          <div className="max-w-6xl mx-auto flex items-center gap-3 text-amber-700">
            <Archive className="w-5 h-5 flex-shrink-0" />
            <p className="text-sm">This wedding has been completed and archived. You can still view your wedding details and memories.</p>
          </div>
        </div>
      )}

      {/* Countdown Hero */}
      {days !== null && days > 0 && !data.archived && (
        <div className="bg-gradient-to-r from-[#1e3a5f] to-[#2a4a6f] text-white">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-12 text-center">
            <p className="text-[#d4af37] text-sm tracking-widest uppercase mb-2">Counting Down</p>
            <div className="text-5xl sm:text-7xl font-serif mb-2">{days}</div>
            <p className="text-white/70 text-lg">days until your wedding</p>
            <p className="text-white/50 text-sm mt-2">{data.wedding?.date ? formatDate(data.wedding.date) : ''}</p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-100 bg-white/60 backdrop-blur-sm sticky top-[73px] z-20">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <nav className="flex gap-1 overflow-x-auto -mb-px scrollbar-hide">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                  activeTab === tab.key
                    ? 'border-[#1e3a5f] text-[#1e3a5f]'
                    : 'border-transparent text-gray-400 hover:text-gray-600'
                }`}
              >
                {tab.icon}
                {tab.label}
                {tab.count !== undefined && tab.count > 0 && (
                  <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                    activeTab === tab.key ? 'bg-[#1e3a5f] text-white' : 'bg-gray-100 text-gray-500'
                  }`}>
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Tab Content */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {activeTab === 'overview' && <OverviewTab data={data} />}
        {activeTab === 'timeline' && <TimelineTab events={data.wedding?.events || []} timezone={data.wedding?.timezone} />}
        {activeTab === 'payments' && <PaymentsTab contract={data.contract} />}
        {activeTab === 'forms' && <FormsTab forms={data.forms || []} />}
        {activeTab === 'updates' && <UpdatesTab updates={data.updates || []} />}
      </main>
    </div>
  );
}

// ============================================================================
// TAB COMPONENTS
// ============================================================================

function OverviewTab({ data }: { data: DashboardData }) {
  const stats = data.guest_stats;
  const budget = data.budget_summary;
  const budgetPercent = budget.total_budget > 0 ? Math.min(100, (budget.total_spent / budget.total_budget) * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Quick Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
          <Users className="w-5 h-5 text-[#1e3a5f] mb-2" />
          <div className="text-2xl font-semibold text-gray-800">{stats.total_invited}</div>
          <div className="text-xs text-gray-500">Guests Invited</div>
        </div>
        <div className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
          <CheckCircle className="w-5 h-5 text-green-500 mb-2" />
          <div className="text-2xl font-semibold text-gray-800">{stats.confirmed}</div>
          <div className="text-xs text-gray-500">Confirmed</div>
        </div>
        <div className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
          <Clock className="w-5 h-5 text-amber-500 mb-2" />
          <div className="text-2xl font-semibold text-gray-800">{stats.pending}</div>
          <div className="text-xs text-gray-500">Pending</div>
        </div>
        <div className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
          <DollarSign className="w-5 h-5 text-[#d4af37] mb-2" />
          <div className="text-2xl font-semibold text-gray-800">{formatCurrency(budget.total_budget)}</div>
          <div className="text-xs text-gray-500">Total Budget</div>
        </div>
      </div>

      {/* Budget Progress */}
      {budget.total_budget > 0 && (
        <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium text-gray-800">Budget Progress</h3>
            <span className="text-sm text-gray-500">{budgetPercent.toFixed(0)}% spent</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-3 mb-3">
            <div
              className="h-3 rounded-full transition-all bg-gradient-to-r from-[#1e3a5f] to-[#d4af37]"
              style={{ width: `${budgetPercent}%` }}
            />
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-500">Spent: {formatCurrency(budget.total_spent)}</span>
            <span className="text-gray-500">Remaining: {formatCurrency(budget.remaining)}</span>
          </div>
        </div>
      )}

      {/* Venue & Planner */}
      <div className="grid sm:grid-cols-2 gap-4">
        {data.wedding?.venue && (
          <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
            <div className="flex items-center gap-3 mb-3">
              <MapPin className="w-5 h-5 text-[#c8847e]" />
              <h3 className="font-medium text-gray-800">Venue</h3>
            </div>
            <p className="text-gray-600">{data.wedding.venue}</p>
          </div>
        )}

        {data.planner && (
          <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
            <div className="flex items-center gap-3 mb-3">
              <Building2 className="w-5 h-5 text-[#1e3a5f]" />
              <h3 className="font-medium text-gray-800">Your Planner</h3>
            </div>
            <p className="text-gray-800 font-medium">{data.planner.name || data.planner.company}</p>
            {data.planner.company && data.planner.name && (
              <p className="text-gray-500 text-sm">{data.planner.company}</p>
            )}
            <div className="mt-3 space-y-1">
              {data.planner.email && (
                <a href={`mailto:${data.planner.email}`} className="flex items-center gap-2 text-sm text-[#1e3a5f] hover:underline">
                  <Mail className="w-3.5 h-3.5" /> {data.planner.email}
                </a>
              )}
              {data.planner.phone && (
                <a href={`tel:${data.planner.phone}`} className="flex items-center gap-2 text-sm text-[#1e3a5f] hover:underline">
                  <Phone className="w-3.5 h-3.5" /> {data.planner.phone}
                </a>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Upcoming Events Preview */}
      {data.wedding?.events?.length > 0 && (
        <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
          <h3 className="font-medium text-gray-800 mb-4">Upcoming Events</h3>
          <div className="space-y-3">
            {data.wedding.events.slice(0, 3).map((event, i) => (
              <div key={i} className="flex items-center gap-4 p-3 rounded-lg bg-gray-50">
                <div className="w-12 h-12 bg-[#1e3a5f] rounded-lg flex items-center justify-center text-white text-xs font-medium">
                  {new Date(event.date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-800 text-sm">{eventTypeLabel(event.type)}</p>
                  <p className="text-xs text-gray-500 truncate">
                    {event.details?.venue_name && `${event.details.venue_name}`}
                    {event.details?.time && ` · ${event.details.time}`}
                  </p>
                </div>
                <ChevronRight className="w-4 h-4 text-gray-300 flex-shrink-0" />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TimelineTab({ events, timezone }: { events: WeddingEvent[]; timezone?: string }) {
  if (!events || events.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400">
        <Calendar className="w-10 h-10 mx-auto mb-3 opacity-50" />
        <p>No events scheduled yet</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {events.map((event, i) => (
        <div key={i} className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="bg-gradient-to-r from-[#1e3a5f] to-[#2a4a6f] px-6 py-3">
            <p className="text-[#d4af37] text-sm font-medium">{eventTypeLabel(event.type)}</p>
          </div>
          <div className="p-6">
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="flex items-start gap-3">
                <Calendar className="w-5 h-5 text-gray-400 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-gray-800">{formatDate(event.date)}</p>
                  {event.details?.time && <p className="text-sm text-gray-500">{event.details.time}</p>}
                </div>
              </div>
              {event.details?.venue_name && (
                <div className="flex items-start gap-3">
                  <MapPin className="w-5 h-5 text-gray-400 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-gray-800">{event.details.venue_name}</p>
                    {event.details.location && <p className="text-sm text-gray-500">{event.details.location}</p>}
                  </div>
                </div>
              )}
            </div>
            {event.details?.attire && (
              <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                <p className="text-sm text-gray-600">
                  <span className="font-medium">Attire:</span> {event.details.attire}
                </p>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function PaymentsTab({ contract }: { contract?: ContractInfo | null }) {
  if (!contract) {
    return (
      <div className="text-center py-12 text-gray-400">
        <DollarSign className="w-10 h-10 mx-auto mb-3 opacity-50" />
        <p>No payment schedule yet</p>
        <p className="text-sm mt-1">Your planner will set this up soon</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Payment Summary */}
      <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
        <h3 className="font-medium text-gray-800 mb-4">Payment Summary — {contract.package_name}</h3>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-2xl font-semibold text-gray-800">{formatCurrency(contract.summary.total_amount)}</div>
            <div className="text-xs text-gray-500">Total</div>
          </div>
          <div>
            <div className="text-2xl font-semibold text-green-600">{formatCurrency(contract.summary.paid_amount)}</div>
            <div className="text-xs text-gray-500">Paid</div>
          </div>
          <div>
            <div className="text-2xl font-semibold text-amber-600">{formatCurrency(contract.summary.remaining)}</div>
            <div className="text-xs text-gray-500">Remaining</div>
          </div>
        </div>
      </div>

      {/* Payment List */}
      <div className="space-y-3">
        {contract.payments.map((payment) => (
          <div key={payment.id} className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-800">{payment.name}</p>
              <p className="text-sm text-gray-500">
                Due: {payment.due_date ? new Date(payment.due_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'TBD'}
              </p>
            </div>
            <div className="text-right">
              <p className="font-semibold text-gray-800">{formatCurrency(payment.amount, payment.currency)}</p>
              <span className={`text-xs px-2 py-0.5 rounded-full ${paymentStatusColor(payment.status)}`}>
                {payment.status === 'succeeded' ? 'Paid' : payment.status.charAt(0).toUpperCase() + payment.status.slice(1)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FormsTab({ forms }: { forms: FormItem[] }) {
  const router = useRouter();

  if (!forms || forms.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400">
        <ClipboardList className="w-10 h-10 mx-auto mb-3 opacity-50" />
        <p>No forms to fill out yet</p>
        <p className="text-sm mt-1">Your planner will share forms when needed</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {forms.map((form) => (
        <div key={form.id} className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-medium text-gray-800">{form.title}</h3>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  form.status === 'submitted' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                }`}>
                  {form.status === 'submitted' ? 'Submitted' : 'Pending'}
                </span>
              </div>
              {form.description && <p className="text-sm text-gray-500 truncate">{form.description}</p>}
            </div>
            <button
              onClick={() => router.push(`/couple/forms/${form.id}`)}
              className="ml-4 flex items-center gap-1.5 text-sm text-[#1e3a5f] font-medium hover:underline"
            >
              {form.status === 'submitted' ? 'Edit' : 'Fill Out'}
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function UpdatesTab({ updates }: { updates: UpdateItem[] }) {
  if (!updates || updates.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400">
        <Bell className="w-10 h-10 mx-auto mb-3 opacity-50" />
        <p>No updates yet</p>
        <p className="text-sm mt-1">Your planner will share updates here</p>
      </div>
    );
  }

  const categoryColors: Record<string, string> = {
    venue: 'bg-purple-100 text-purple-700',
    catering: 'bg-orange-100 text-orange-700',
    decor: 'bg-pink-100 text-pink-700',
    timeline: 'bg-blue-100 text-blue-700',
    budget: 'bg-green-100 text-green-700',
    vendor: 'bg-indigo-100 text-indigo-700',
  };

  return (
    <div className="space-y-4">
      {updates.map((update) => (
        <div key={update.id} className={`bg-white rounded-xl border shadow-sm overflow-hidden ${
          update.is_milestone ? 'border-[#d4af37]' : 'border-gray-100'
        }`}>
          {update.is_milestone && (
            <div className="bg-gradient-to-r from-[#d4af37] to-[#c8847e] px-4 py-1.5">
              <div className="flex items-center gap-1.5 text-white text-xs font-medium">
                <Sparkles className="w-3.5 h-3.5" />
                MILESTONE
              </div>
            </div>
          )}
          <div className="p-5">
            <div className="flex items-start justify-between mb-2">
              <h3 className="font-medium text-gray-800">{update.title}</h3>
              {update.category && (
                <span className={`text-xs px-2 py-0.5 rounded-full ${categoryColors[update.category] || 'bg-gray-100 text-gray-600'}`}>
                  {update.category}
                </span>
              )}
            </div>
            <p className="text-sm text-gray-600 whitespace-pre-wrap">{update.content}</p>
            <div className="mt-3 flex items-center gap-2 text-xs text-gray-400">
              {update.created_by && <span>From: {update.created_by}</span>}
              {update.created_at && (
                <span>· {new Date(update.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
