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
  ClipboardList, Send, ChevronDown, ChevronUp,
  MessageSquare, StickyNote, FileSignature, Eye,
  MessageCircle, CalendarClock, Repeat,
  Gift, HelpCircle, QrCode, BellRing, Plus,
  Pencil, Trash2, ExternalLink, Download, BellOff
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

interface EventNote {
  id: string;
  author_role: 'planner' | 'couple';
  author_name?: string;
  text: string;
  status: 'pending' | 'seen' | 'addressed';
  reply_to?: string;
  created_at?: string;
}

interface OrderItem {
  id: string;
  title: string;
  description?: string;
  time?: string;
  duration_minutes?: number;
  order: number;
  notes: EventNote[];
}

interface WeddingEvent {
  type: string;
  date: string;
  details?: EventDetail;
  order_of_events?: OrderItem[];
  event_notes?: EventNote[];
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

interface ContractSection {
  title: string;
  content: string;
}

interface ContractDetail {
  id: string;
  status: string;
  package_name: string;
  couple_name?: string;
  couple_email?: string;
  signed_at?: string;
  created_at?: string;
  sent_at?: string;
  viewed_at?: string;
  sections: ContractSection[];
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

type TabType = 'overview' | 'timeline' | 'payments' | 'contracts' | 'forms' | 'updates' | 'messages' | 'meetings' | 'registry' | 'faq';

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
  const [unreadMessages, setUnreadMessages] = useState(0);

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

      // Fetch unread message count
      try {
        const unreadRes = await fetch(`${getApiBaseUrl()}/couple/portal/messages/unread-count`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (unreadRes.ok) {
          const unreadData = await unreadRes.json();
          setUnreadMessages(unreadData.unread_count || 0);
        }
      } catch { /* non-critical */ }
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
    { key: 'contracts', label: 'Contract', icon: <FileSignature className="w-4 h-4" /> },
    { key: 'forms', label: 'Forms', icon: <ClipboardList className="w-4 h-4" />, count: data.forms?.filter(f => f.status === 'pending').length },
    { key: 'updates', label: 'Updates', icon: <Bell className="w-4 h-4" />, count: data.updates?.length },
    { key: 'messages', label: 'Messages', icon: <MessageCircle className="w-4 h-4" />, count: unreadMessages || undefined },
    { key: 'meetings', label: 'Meetings', icon: <CalendarClock className="w-4 h-4" /> },
    { key: 'registry', label: 'Registry', icon: <Gift className="w-4 h-4" />, count: data.wedding?.registries?.length || undefined },
    { key: 'faq', label: 'FAQ', icon: <HelpCircle className="w-4 h-4" />, count: data.wedding?.faqs?.length || undefined },
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
                className={`flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-4 py-3 text-xs sm:text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
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
        {activeTab === 'timeline' && <TimelineTab events={data.wedding?.events || []} timezone={data.wedding?.timezone} onNoteAdded={fetchDashboard} />}
        {activeTab === 'payments' && <PaymentsTab contract={data.contract} />}
        {activeTab === 'contracts' && <ContractTab />}
        {activeTab === 'forms' && <FormsTab forms={data.forms || []} />}
        {activeTab === 'updates' && <UpdatesTab updates={data.updates || []} />}
        {activeTab === 'messages' && <MessagesTab onMessageSent={() => { setUnreadMessages(0); }} onMessagesRead={() => { setUnreadMessages(0); }} archived={!!data.archived} />}
        {activeTab === 'meetings' && <MeetingsTab />}
        {activeTab === 'registry' && <RegistryTab registries={data.wedding?.registries || []} archived={!!data.archived} onUpdated={fetchDashboard} />}
        {activeTab === 'faq' && <FAQTab faqs={data.wedding?.faqs || []} archived={!!data.archived} onUpdated={fetchDashboard} />}
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

function TimelineTab({ events, timezone, onNoteAdded }: { events: WeddingEvent[]; timezone?: string; onNoteAdded?: () => void }) {
  const [expandedEvent, setExpandedEvent] = useState<number | null>(null);
  const [noteText, setNoteText] = useState('');
  const [noteTarget, setNoteTarget] = useState<{ eventIndex: number; itemId?: string } | null>(null);
  const [submittingNote, setSubmittingNote] = useState(false);

  if (!events || events.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400">
        <Calendar className="w-10 h-10 mx-auto mb-3 opacity-50" />
        <p>No events scheduled yet</p>
      </div>
    );
  }

  const handleSubmitNote = async (eventIndex: number, itemId?: string) => {
    if (!noteText.trim()) return;
    const token = localStorage.getItem('couple_token');
    if (!token) return;

    setSubmittingNote(true);
    try {
      const url = itemId
        ? `${getApiBaseUrl()}/couple/portal/events/${eventIndex}/order-of-events/${itemId}/notes`
        : `${getApiBaseUrl()}/couple/portal/events/${eventIndex}/notes`;

      const res = await fetch(url, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: noteText.trim() }),
      });

      if (res.ok) {
        toast.success('Note sent to your planner');
        setNoteText('');
        setNoteTarget(null);
        onNoteAdded?.();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to add note');
      }
    } catch {
      toast.error('Failed to connect');
    } finally {
      setSubmittingNote(false);
    }
  };

  const noteStatusBadge = (status: string) => {
    switch (status) {
      case 'pending': return <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700">Pending</span>;
      case 'seen': return <span className="text-xs px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700">Seen</span>;
      case 'addressed': return <span className="text-xs px-1.5 py-0.5 rounded-full bg-green-100 text-green-700">Addressed</span>;
      default: return null;
    }
  };

  return (
    <div className="space-y-4">
      {events.map((event, eventIdx) => {
        const orderItems = (event.order_of_events || []).sort((a, b) => a.order - b.order);
        const eventNotes = event.event_notes || [];
        const isExpanded = expandedEvent === eventIdx;

        return (
          <div key={eventIdx} className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
            {/* Event Header */}
            <div className="bg-gradient-to-r from-[#1e3a5f] to-[#2a4a6f] px-6 py-3 flex items-center justify-between">
              <p className="text-[#d4af37] text-sm font-medium">{eventTypeLabel(event.type)}</p>
              {(orderItems.length > 0 || eventNotes.length > 0) && (
                <button
                  onClick={() => setExpandedEvent(isExpanded ? null : eventIdx)}
                  className="text-white/70 hover:text-white text-xs flex items-center gap-1"
                >
                  {orderItems.length > 0 && `${orderItems.length} items`}
                  {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
              )}
            </div>

            {/* Event Info */}
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
                  <p className="text-sm text-gray-600"><span className="font-medium">Attire:</span> {event.details.attire}</p>
                </div>
              )}
            </div>

            {/* Expanded: Order of Events + Notes */}
            {isExpanded && (
              <div className="border-t border-gray-100 px-6 py-4 space-y-4">
                {/* Order of Events Items */}
                {orderItems.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                      <Clock className="w-4 h-4" /> Run of Show
                    </h4>
                    <div className="space-y-2">
                      {orderItems.map((item) => (
                        <div key={item.id} className="p-3 bg-gray-50 rounded-lg">
                          <div className="flex items-center gap-3">
                            {item.time && (
                              <span className="text-xs font-medium text-[#1e3a5f] bg-[#1e3a5f]/10 px-2 py-1 rounded min-w-[60px] text-center">
                                {item.time}
                              </span>
                            )}
                            <div className="flex-1">
                              <p className="text-sm font-medium text-gray-800">{item.title}</p>
                              {item.description && <p className="text-xs text-gray-500 mt-0.5">{item.description}</p>}
                              {item.duration_minutes && <p className="text-xs text-gray-400">{item.duration_minutes} minutes</p>}
                            </div>
                            <button
                              onClick={() => setNoteTarget({ eventIndex: eventIdx, itemId: item.id })}
                              className="text-gray-400 hover:text-[#1e3a5f] transition-colors p-1"
                              title="Add a note"
                            >
                              <MessageSquare className="w-4 h-4" />
                            </button>
                          </div>

                          {/* Item-level notes (threaded with planner replies) */}
                          {item.notes.length > 0 && (() => {
                            const parentItemNotes = item.notes.filter(n => !n.reply_to);
                            const itemReplies = item.notes.filter(n => !!n.reply_to);
                            const itemRepliesMap: Record<string, EventNote[]> = {};
                            itemReplies.forEach(r => {
                              const replyTo = r.reply_to;
                              if (!replyTo) return;
                              if (!itemRepliesMap[replyTo]) itemRepliesMap[replyTo] = [];
                              itemRepliesMap[replyTo].push(r);
                            });
                            return (parentItemNotes.length > 0 || itemReplies.length > 0) ? (
                              <div className="mt-2 ml-[72px] space-y-1.5">
                                {parentItemNotes.map((note) => (
                                  <div key={note.id}>
                                    <div className="flex items-start gap-2 text-xs">
                                      <StickyNote className="w-3 h-3 text-amber-400 mt-0.5 flex-shrink-0" />
                                      <div className="flex-1">
                                        <span className="text-gray-600">{note.text}</span>
                                        <div className="flex items-center gap-1.5 mt-0.5">
                                          <span className="text-gray-400">{note.author_name || note.author_role}</span>
                                          {noteStatusBadge(note.status)}
                                        </div>
                                      </div>
                                    </div>
                                    {/* Planner replies */}
                                    {(itemRepliesMap[note.id] || []).map(reply => (
                                      <div key={reply.id} className="ml-5 mt-1 flex items-start gap-2 text-xs">
                                        <MessageCircle className="w-3 h-3 text-blue-400 mt-0.5 flex-shrink-0" />
                                        <div className="flex-1">
                                          <span className="text-gray-600">{reply.text}</span>
                                          <div className="flex items-center gap-1.5 mt-0.5">
                                            <span className="text-[#1e3a5f] font-medium">Planner</span>
                                            {reply.created_at && (
                                              <span className="text-gray-400">· {new Date(reply.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
                                            )}
                                          </div>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                ))}
                              </div>
                            ) : null;
                          })()}

                          {/* Inline note form for this item */}
                          {noteTarget?.eventIndex === eventIdx && noteTarget?.itemId === item.id && (
                            <div className="mt-2 ml-[72px] flex gap-2">
                              <input
                                type="text"
                                value={noteText}
                                onChange={(e) => setNoteText(e.target.value)}
                                placeholder="Add a note for your planner..."
                                className="flex-1 px-3 py-1.5 border border-gray-200 rounded-lg text-xs"
                                autoFocus
                                onKeyDown={(e) => e.key === 'Enter' && handleSubmitNote(eventIdx, item.id)}
                              />
                              <button
                                onClick={() => handleSubmitNote(eventIdx, item.id)}
                                disabled={submittingNote || !noteText.trim()}
                                className="px-3 py-1.5 bg-[#1e3a5f] text-white rounded-lg text-xs disabled:opacity-50 flex items-center gap-1"
                              >
                                {submittingNote ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                              </button>
                              <button
                                onClick={() => { setNoteTarget(null); setNoteText(''); }}
                                className="text-gray-400 hover:text-gray-600 text-xs"
                              >
                                Cancel
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Event-level notes (threaded with planner replies) */}
                {eventNotes.length > 0 && (() => {
                  const parentEventNotes = eventNotes.filter(n => !n.reply_to);
                  const eventReplies = eventNotes.filter(n => !!n.reply_to);
                  const eventRepliesMap: Record<string, EventNote[]> = {};
                  eventReplies.forEach(r => {
                    const replyTo = r.reply_to;
                    if (!replyTo) return;
                    if (!eventRepliesMap[replyTo]) eventRepliesMap[replyTo] = [];
                    eventRepliesMap[replyTo].push(r);
                  });
                  return (parentEventNotes.length > 0 || eventReplies.length > 0) ? (
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                        <StickyNote className="w-4 h-4" /> General Notes
                      </h4>
                      <div className="space-y-2">
                        {parentEventNotes.map((note) => (
                          <div key={note.id}>
                            <div className="p-3 bg-amber-50/50 border border-amber-100 rounded-lg">
                              <p className="text-sm text-gray-700">{note.text}</p>
                              <div className="flex items-center gap-2 mt-1.5 text-xs text-gray-400">
                                <span>{note.author_name || note.author_role}</span>
                                {noteStatusBadge(note.status)}
                                {note.created_at && (
                                  <span>· {new Date(note.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
                                )}
                              </div>
                            </div>
                            {/* Planner replies threaded below */}
                            {(eventRepliesMap[note.id] || []).map(reply => (
                              <div key={reply.id} className="ml-4 mt-1.5 p-2.5 bg-blue-50/60 border border-blue-100 rounded-lg">
                                <p className="text-sm text-gray-700">{reply.text}</p>
                                <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
                                  <span className="text-[#1e3a5f] font-medium">Planner</span>
                                  {reply.created_at && (
                                    <span>· {new Date(reply.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null;
                })()}

                {/* Add general event note */}
                {noteTarget?.eventIndex === eventIdx && !noteTarget?.itemId ? (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={noteText}
                      onChange={(e) => setNoteText(e.target.value)}
                      placeholder="Add a general note for this event..."
                      className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm"
                      autoFocus
                      onKeyDown={(e) => e.key === 'Enter' && handleSubmitNote(eventIdx)}
                    />
                    <button
                      onClick={() => handleSubmitNote(eventIdx)}
                      disabled={submittingNote || !noteText.trim()}
                      className="px-4 py-2 bg-[#1e3a5f] text-white rounded-lg text-sm disabled:opacity-50 flex items-center gap-1"
                    >
                      {submittingNote ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    </button>
                    <button onClick={() => { setNoteTarget(null); setNoteText(''); }} className="text-gray-400 hover:text-gray-600 text-sm">Cancel</button>
                  </div>
                ) : (
                  <button
                    onClick={() => setNoteTarget({ eventIndex: eventIdx })}
                    className="w-full py-2 border border-dashed border-gray-200 rounded-lg text-sm text-gray-400 hover:border-[#1e3a5f] hover:text-[#1e3a5f] transition-colors flex items-center justify-center gap-1"
                  >
                    <MessageSquare className="w-4 h-4" />
                    Add a Note
                  </button>
                )}
              </div>
            )}

            {/* If there are items but not expanded, show a hint */}
            {!isExpanded && orderItems.length > 0 && (
              <button
                onClick={() => setExpandedEvent(eventIdx)}
                className="w-full border-t border-gray-100 px-6 py-2.5 text-sm text-[#1e3a5f] hover:bg-gray-50 transition-colors flex items-center justify-center gap-1"
              >
                <Clock className="w-4 h-4" />
                View Run of Show ({orderItems.length} items)
                <ChevronDown className="w-4 h-4" />
              </button>
            )}
          </div>
        );
      })}
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

function ContractTab() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [contract, setContract] = useState<ContractDetail | null>(null);

  useEffect(() => {
    const fetchContract = async () => {
      const token = localStorage.getItem('couple_token');
      if (!token) return;
      try {
        const res = await fetch(`${getApiBaseUrl()}/couple/portal/contracts`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setContract(data.contract || null);
        }
      } catch (err) {
        console.error('Failed to fetch contract', err);
      } finally {
        setLoading(false);
      }
    };
    fetchContract();
  }, []);

  if (loading) {
    return (
      <div className="text-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-[#1e3a5f] mx-auto" />
      </div>
    );
  }

  if (!contract) {
    return (
      <div className="text-center py-12 text-gray-400">
        <FileSignature className="w-10 h-10 mx-auto mb-3 opacity-50" />
        <p>No contract available yet</p>
        <p className="text-sm mt-1">Your planner will share the contract when it is ready</p>
      </div>
    );
  }

  const contractStatusLabel = (status: string) => {
    const labels: Record<string, { text: string; style: string }> = {
      draft: { text: 'Draft', style: 'bg-gray-100 text-gray-600' },
      sent: { text: 'Awaiting Signature', style: 'bg-amber-100 text-amber-700' },
      viewed: { text: 'Viewed', style: 'bg-blue-100 text-blue-700' },
      signed: { text: 'Signed', style: 'bg-green-100 text-green-700' },
      active: { text: 'Active', style: 'bg-green-100 text-green-700' },
      completed: { text: 'Completed', style: 'bg-emerald-100 text-emerald-700' },
      cancelled: { text: 'Cancelled', style: 'bg-red-100 text-red-700' },
    };
    return labels[status] || { text: status, style: 'bg-gray-100 text-gray-600' };
  };

  const statusInfo = contractStatusLabel(contract.status);

  return (
    <div className="space-y-6">
      {/* Contract Header */}
      <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-800">{contract.package_name || 'Wedding Package'}</h3>
            {contract.couple_name && <p className="text-sm text-gray-500 mt-0.5">{contract.couple_name}</p>}
          </div>
          <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${statusInfo.style}`}>
            {statusInfo.text}
          </span>
        </div>

        {/* Key Dates */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          {contract.sent_at && (
            <div>
              <p className="text-gray-400 text-xs">Sent</p>
              <p className="text-gray-700">{new Date(contract.sent_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</p>
            </div>
          )}
          {contract.viewed_at && (
            <div>
              <p className="text-gray-400 text-xs">Viewed</p>
              <p className="text-gray-700">{new Date(contract.viewed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</p>
            </div>
          )}
          {contract.signed_at && (
            <div>
              <p className="text-gray-400 text-xs">Signed</p>
              <p className="text-gray-700">{new Date(contract.signed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</p>
            </div>
          )}
        </div>
      </div>

      {/* Payment Summary */}
      {contract.summary && (
        <div className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
          <h3 className="font-medium text-gray-800 mb-4">Payment Summary</h3>
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
      )}

      {/* Contract Sections */}
      {contract.sections && contract.sections.length > 0 && (
        <div className="space-y-4">
          {contract.sections.map((section, idx) => (
            <div key={idx} className="bg-white rounded-xl p-6 border border-gray-100 shadow-sm">
              <h3 className="font-medium text-gray-800 mb-3">{section.title}</h3>
              <div className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">{section.content}</div>
            </div>
          ))}
        </div>
      )}

      {/* Payment Schedule */}
      {contract.payments && contract.payments.length > 0 && (
        <div>
          <h3 className="font-medium text-gray-800 mb-3">Payment Schedule</h3>
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
      )}
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


// ============================================================================
// MESSAGES TAB (Sprint 3)
// ============================================================================

interface MessageItem {
  id: string;
  sender_role: 'couple' | 'planner';
  sender_name: string;
  content: string;
  read_by_planner: boolean;
  created_at?: string;
}

function MessagesTab({ onMessageSent, onMessagesRead, archived = false }: { onMessageSent: () => void; onMessagesRead: () => void; archived?: boolean }) {
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [msgLoading, setMsgLoading] = useState(true);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useCallback((node: HTMLDivElement | null) => {
    if (node) node.scrollIntoView({ behavior: 'smooth' });
  }, []);

  const fetchMessages = useCallback(async () => {
    const token = localStorage.getItem('couple_token');
    if (!token) return;

    try {
      const res = await fetch(`${getApiBaseUrl()}/couple/portal/messages?limit=100`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
        onMessagesRead(); // Clear unread badge — backend marks read on fetch
      }
    } catch {
      toast.error('Failed to load messages');
    } finally {
      setMsgLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMessages();
  }, [fetchMessages]);

  const handleSend = async () => {
    if (!newMessage.trim() || sending) return;
    const token = localStorage.getItem('couple_token');
    if (!token) return;

    setSending(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/couple/portal/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ content: newMessage.trim() }),
      });

      if (res.ok) {
        setNewMessage('');
        onMessageSent();
        await fetchMessages();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to send message');
      }
    } catch {
      toast.error('Failed to send message');
    } finally {
      setSending(false);
    }
  };

  if (msgLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-[#1e3a5f]" />
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm flex flex-col" style={{ height: 'calc(100vh - 280px)', minHeight: '400px', maxHeight: '700px' }}>
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <MessageCircle className="w-12 h-12 mb-3 opacity-50" />
            <p className="text-sm">No messages yet</p>
            <p className="text-xs mt-1">Send a message to your planner to start the conversation</p>
          </div>
        ) : (
          messages.map((msg, idx) => {
            const isCouple = msg.sender_role === 'couple';
            return (
              <div key={msg.id} className={`flex ${isCouple ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${
                  isCouple
                    ? 'bg-[#1e3a5f] text-white rounded-br-md'
                    : 'bg-gray-100 text-gray-800 rounded-bl-md'
                }`}>
                  {!isCouple && (
                    <p className="text-xs font-medium text-gray-500 mb-1">{msg.sender_name}</p>
                  )}
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  <div className={`flex items-center gap-1.5 mt-1 ${isCouple ? 'justify-end' : ''}`}>
                    <span className={`text-xs ${isCouple ? 'text-white/50' : 'text-gray-400'}`}>
                      {msg.created_at ? new Date(msg.created_at).toLocaleTimeString('en-US', {
                        hour: 'numeric', minute: '2-digit', hour12: true,
                      }) : ''}
                    </span>
                    {isCouple && msg.read_by_planner && (
                      <Eye className="w-3 h-3 text-white/50" />
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      {/* Input area — disabled for archived weddings */}
      {archived ? (
        <div className="border-t border-gray-100 p-3 bg-gray-50">
          <p className="text-sm text-gray-400 text-center flex items-center justify-center gap-2">
            <Archive className="w-4 h-4" />
            Messaging is disabled for archived weddings
          </p>
        </div>
      ) : (
        <div className="border-t border-gray-100 p-3 flex gap-2">
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
            placeholder="Type a message to your planner..."
            className="flex-1 px-4 py-2.5 border border-gray-200 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f]"
            disabled={sending}
          />
          <button
            onClick={handleSend}
            disabled={!newMessage.trim() || sending}
            className="w-10 h-10 flex items-center justify-center bg-[#1e3a5f] text-white rounded-full hover:bg-[#2a4a6f] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
      )}
    </div>
  );
}


// ============================================================================
// MEETINGS TAB — Couple views upcoming meetings with planner
// ============================================================================

interface CoupleMeeting {
  id: string;
  title: string;
  description?: string;
  start_date: string;
  end_date?: string;
  is_recurring: boolean;
  status: string;
}

function MeetingsTab() {
  const [meetings, setMeetings] = useState<CoupleMeeting[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMeetings = async () => {
      const token = localStorage.getItem('couple_token');
      if (!token) return;
      try {
        const res = await fetch(`${getApiBaseUrl()}/couple/portal/meetings`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setMeetings(data.meetings || []);
        } else if (res.status !== 401) {
          toast.error('Failed to load meetings');
        }
      } catch {
        toast.error('Failed to load meetings');
      } finally {
        setLoading(false);
      }
    };
    fetchMeetings();
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>;
  }

  if (meetings.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400">
        <CalendarClock className="w-10 h-10 mx-auto mb-3 opacity-50" />
        <p>No upcoming meetings</p>
        <p className="text-sm mt-1">Your planner will schedule check-ins here</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-3">
      <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
        <CalendarClock className="w-5 h-5 text-[#1e3a5f]" /> Upcoming Meetings
      </h2>
      {meetings.map((m) => (
        <div key={m.id} className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-sm font-medium text-gray-800">{m.title}</h3>
            {m.is_recurring && (
              <span className="text-xs px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-700 flex items-center gap-0.5">
                <Repeat className="w-3 h-3" /> Recurring
              </span>
            )}
          </div>
          {m.description && <p className="text-xs text-gray-500 mb-2">{m.description}</p>}
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Calendar className="w-3.5 h-3.5" />
            <span>{new Date(m.start_date).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500 mt-1">
            <Clock className="w-3.5 h-3.5" />
            <span>{new Date(m.start_date).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}</span>
            {m.end_date && <span>– {new Date(m.end_date).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}


// ============================================================================
// SPRINT 6: REGISTRY TAB (CRUD — syncs to wedding model)
// ============================================================================

interface RegistryItem {
  name: string;
  url: string;
  color?: string;
}

function RegistryTab({ registries, archived, onUpdated }: { registries: RegistryItem[]; archived: boolean; onUpdated: () => void }) {
  const [showForm, setShowForm] = useState(false);
  const [editIndex, setEditIndex] = useState<number | null>(null);
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [color, setColor] = useState('bg-gray-600');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);

  const colorOptions = [
    { value: 'bg-red-600', label: 'Red' },
    { value: 'bg-orange-500', label: 'Orange' },
    { value: 'bg-amber-500', label: 'Amber' },
    { value: 'bg-green-600', label: 'Green' },
    { value: 'bg-blue-600', label: 'Blue' },
    { value: 'bg-indigo-600', label: 'Indigo' },
    { value: 'bg-purple-600', label: 'Purple' },
    { value: 'bg-pink-600', label: 'Pink' },
    { value: 'bg-gray-600', label: 'Gray' },
    { value: 'bg-[#1e3a5f]', label: 'Navy' },
  ];

  const resetForm = () => {
    setName('');
    setUrl('');
    setColor('bg-gray-600');
    setShowForm(false);
    setEditIndex(null);
  };

  const startEdit = (index: number) => {
    const item = registries[index];
    setName(item.name);
    setUrl(item.url);
    setColor(item.color || 'bg-gray-600');
    setEditIndex(index);
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!name.trim() || !url.trim()) return;
    setSaving(true);
    try {
      const token = localStorage.getItem('couple_token');
      const isEdit = editIndex !== null;
      const endpoint = isEdit
        ? `${getApiBaseUrl()}/couple/portal/registries/${editIndex}`
        : `${getApiBaseUrl()}/couple/portal/registries`;

      const res = await fetch(endpoint, {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name: name.trim(), url: url.trim(), color }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to save registry');
      }

      toast.success(isEdit ? 'Registry updated' : 'Registry added');
      resetForm();
      onUpdated();
    } catch (e: any) {
      toast.error(e.message || 'Something went wrong');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (index: number) => {
    setDeleting(index);
    try {
      const token = localStorage.getItem('couple_token');
      const res = await fetch(`${getApiBaseUrl()}/couple/portal/registries/${index}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to delete');
      }

      toast.success('Registry removed');
      onUpdated();
    } catch (e: any) {
      toast.error(e.message || 'Something went wrong');
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
          <Gift className="w-5 h-5 text-[#1e3a5f]" /> Wedding Registry
        </h2>
        {!archived && !showForm && (
          <button
            onClick={() => { resetForm(); setShowForm(true); }}
            className="flex items-center gap-1.5 text-sm font-medium text-[#1e3a5f] hover:text-[#2a4a6f] transition-colors"
            aria-label="Add new registry item"
          >
            <Plus className="w-4 h-4" /> Add Registry
          </button>
        )}
      </div>

      <p className="text-sm text-gray-500 mb-4">Your presence is the greatest gift, but if you&apos;d like to celebrate with us, we&apos;re registered at:</p>

      {/* Add/Edit Form */}
      {showForm && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 mb-6" role="form" aria-label={editIndex !== null ? 'Edit registry item' : 'Add registry item'}>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">{editIndex !== null ? 'Edit Registry' : 'Add Registry'}</h3>
          <div className="space-y-3">
            <div>
              <label htmlFor="reg-name" className="block text-xs font-medium text-gray-600 mb-1">Registry Name</label>
              <input
                id="reg-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Target, Amazon, Zola"
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none"
                aria-required="true"
              />
            </div>
            <div>
              <label htmlFor="reg-url" className="block text-xs font-medium text-gray-600 mb-1">Registry URL</label>
              <input
                id="reg-url"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://www.target.com/gift-registry/..."
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none"
                aria-required="true"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Button Color</label>
              <div className="flex flex-wrap gap-2">
                {colorOptions.map((c) => (
                  <button
                    key={c.value}
                    type="button"
                    onClick={() => setColor(c.value)}
                    className={`w-8 h-8 rounded-full ${c.value} transition-all ${color === c.value ? 'ring-2 ring-offset-2 ring-[#1e3a5f] scale-110' : 'opacity-60 hover:opacity-100'}`}
                    title={c.label}
                    aria-label={`Select ${c.label} color`}
                    aria-pressed={color === c.value}
                  />
                ))}
              </div>
            </div>
            <div className="flex gap-2 pt-2">
              <button
                onClick={handleSave}
                disabled={saving || !name.trim() || !url.trim()}
                className="flex items-center gap-1.5 px-4 py-2 bg-[#1e3a5f] text-white text-sm font-medium rounded-lg hover:bg-[#2a4a6f] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                {editIndex !== null ? 'Update' : 'Save'}
              </button>
              <button
                onClick={resetForm}
                className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Registry Grid */}
      {registries.length === 0 && !showForm ? (
        <div className="text-center py-12">
          <Gift className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-400 font-medium">No registries added yet</p>
          {!archived && <p className="text-sm text-gray-400 mt-1">Click &quot;Add Registry&quot; to get started</p>}
        </div>
      ) : (
        <div className={`grid gap-4 ${registries.length === 1 ? 'grid-cols-1 max-w-xs mx-auto' : registries.length === 2 ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3'}`}>
          {registries.map((reg, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 text-center group">
              <h3 className="text-base font-semibold text-gray-800 mb-3">{reg.name}</h3>
              <a
                href={reg.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`${reg.color || 'bg-gray-600'} text-white px-6 py-2.5 rounded-lg hover:opacity-90 transition-opacity inline-flex items-center gap-2 text-sm font-medium`}
                aria-label={`View ${reg.name} registry (opens in new tab)`}
              >
                View Registry <ExternalLink className="w-3.5 h-3.5" />
              </a>
              {!archived && (
                <div className="flex items-center justify-center gap-2 mt-3 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => startEdit(i)}
                    className="text-xs text-gray-400 hover:text-[#1e3a5f] flex items-center gap-1 transition-colors"
                    aria-label={`Edit ${reg.name}`}
                  >
                    <Pencil className="w-3 h-3" /> Edit
                  </button>
                  <button
                    onClick={() => handleDelete(i)}
                    disabled={deleting === i}
                    className="text-xs text-gray-400 hover:text-red-500 flex items-center gap-1 transition-colors disabled:opacity-50"
                    aria-label={`Delete ${reg.name}`}
                  >
                    {deleting === i ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />} Delete
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ============================================================================
// SPRINT 6: FAQ TAB (CRUD — syncs to wedding model)
// ============================================================================

interface FAQItem {
  question: string;
  answer: string;
  link_url?: string | null;
  link_label?: string | null;
}

function FAQTab({ faqs, archived, onUpdated }: { faqs: FAQItem[]; archived: boolean; onUpdated: () => void }) {
  const [showForm, setShowForm] = useState(false);
  const [editIndex, setEditIndex] = useState<number | null>(null);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [linkUrl, setLinkUrl] = useState('');
  const [linkLabel, setLinkLabel] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const resetForm = () => {
    setQuestion('');
    setAnswer('');
    setLinkUrl('');
    setLinkLabel('');
    setShowForm(false);
    setEditIndex(null);
  };

  const startEdit = (index: number) => {
    const item = faqs[index];
    setQuestion(item.question);
    setAnswer(item.answer);
    setLinkUrl(item.link_url || '');
    setLinkLabel(item.link_label || '');
    setEditIndex(index);
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!question.trim() || !answer.trim()) return;
    setSaving(true);
    try {
      const token = localStorage.getItem('couple_token');
      const isEdit = editIndex !== null;
      const endpoint = isEdit
        ? `${getApiBaseUrl()}/couple/portal/faqs/${editIndex}`
        : `${getApiBaseUrl()}/couple/portal/faqs`;

      const body: any = { question: question.trim(), answer: answer.trim() };
      if (linkUrl.trim()) body.link_url = linkUrl.trim();
      if (linkLabel.trim()) body.link_label = linkLabel.trim();

      const res = await fetch(endpoint, {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to save FAQ');
      }

      toast.success(isEdit ? 'FAQ updated' : 'FAQ added');
      resetForm();
      onUpdated();
    } catch (e: any) {
      toast.error(e.message || 'Something went wrong');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (index: number) => {
    setDeleting(index);
    try {
      const token = localStorage.getItem('couple_token');
      const res = await fetch(`${getApiBaseUrl()}/couple/portal/faqs/${index}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to delete');
      }

      toast.success('FAQ removed');
      onUpdated();
    } catch (e: any) {
      toast.error(e.message || 'Something went wrong');
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
          <HelpCircle className="w-5 h-5 text-[#1e3a5f]" /> Frequently Asked Questions
        </h2>
        {!archived && !showForm && (
          <button
            onClick={() => { resetForm(); setShowForm(true); }}
            className="flex items-center gap-1.5 text-sm font-medium text-[#1e3a5f] hover:text-[#2a4a6f] transition-colors"
            aria-label="Add new FAQ item"
          >
            <Plus className="w-4 h-4" /> Add FAQ
          </button>
        )}
      </div>

      <p className="text-sm text-gray-500 mb-4">These FAQs will appear on your wedding page for your guests. Add questions and answers to help them prepare.</p>

      {/* Add/Edit Form */}
      {showForm && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 mb-6" role="form" aria-label={editIndex !== null ? 'Edit FAQ item' : 'Add FAQ item'}>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">{editIndex !== null ? 'Edit FAQ' : 'Add FAQ'}</h3>
          <div className="space-y-3">
            <div>
              <label htmlFor="faq-q" className="block text-xs font-medium text-gray-600 mb-1">Question</label>
              <input
                id="faq-q"
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="e.g., What should I wear?"
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none"
                aria-required="true"
              />
            </div>
            <div>
              <label htmlFor="faq-a" className="block text-xs font-medium text-gray-600 mb-1">Answer</label>
              <textarea
                id="faq-a"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Your answer here..."
                rows={3}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none resize-none"
                aria-required="true"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="faq-link" className="block text-xs font-medium text-gray-600 mb-1">Link URL (optional)</label>
                <input
                  id="faq-link"
                  type="url"
                  value={linkUrl}
                  onChange={(e) => setLinkUrl(e.target.value)}
                  placeholder="https://..."
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none"
                />
              </div>
              <div>
                <label htmlFor="faq-label" className="block text-xs font-medium text-gray-600 mb-1">Link Label (optional)</label>
                <input
                  id="faq-label"
                  type="text"
                  value={linkLabel}
                  onChange={(e) => setLinkLabel(e.target.value)}
                  placeholder="e.g., Book Hotel Room"
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none"
                />
              </div>
            </div>
            <div className="flex gap-2 pt-2">
              <button
                onClick={handleSave}
                disabled={saving || !question.trim() || !answer.trim()}
                className="flex items-center gap-1.5 px-4 py-2 bg-[#1e3a5f] text-white text-sm font-medium rounded-lg hover:bg-[#2a4a6f] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                {editIndex !== null ? 'Update' : 'Save'}
              </button>
              <button
                onClick={resetForm}
                className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* FAQ List */}
      {faqs.length === 0 && !showForm ? (
        <div className="text-center py-12">
          <HelpCircle className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-400 font-medium">No FAQs added yet</p>
          {!archived && <p className="text-sm text-gray-400 mt-1">Click &quot;Add FAQ&quot; to help your guests prepare</p>}
        </div>
      ) : (
        <div className="space-y-3">
          {faqs.map((faq, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden group">
              <button
                onClick={() => setExpandedIndex(expandedIndex === i ? null : i)}
                className="w-full px-5 py-4 flex items-center justify-between text-left"
                aria-expanded={expandedIndex === i}
                aria-controls={`faq-answer-${i}`}
              >
                <h3 className="text-sm font-semibold text-gray-800 pr-4">{faq.question}</h3>
                {expandedIndex === i ? <ChevronUp className="w-4 h-4 text-gray-400 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0" />}
              </button>
              {expandedIndex === i && (
                <div id={`faq-answer-${i}`} className="px-5 pb-4 border-t border-gray-50">
                  <p className="text-sm text-gray-600 leading-relaxed mt-3">{faq.answer}</p>
                  {faq.link_url && faq.link_label && (
                    <a
                      href={faq.link_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 mt-3 px-4 py-2 bg-[#1e3a5f] text-white text-xs font-medium rounded-lg hover:bg-[#2a4a6f] transition-colors"
                    >
                      {faq.link_label} <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                  {!archived && (
                    <div className="flex items-center gap-3 mt-3 pt-3 border-t border-gray-50">
                      <button
                        onClick={(e) => { e.stopPropagation(); startEdit(i); }}
                        className="text-xs text-gray-400 hover:text-[#1e3a5f] flex items-center gap-1 transition-colors"
                        aria-label={`Edit FAQ: ${faq.question}`}
                      >
                        <Pencil className="w-3 h-3" /> Edit
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(i); }}
                        disabled={deleting === i}
                        className="text-xs text-gray-400 hover:text-red-500 flex items-center gap-1 transition-colors disabled:opacity-50"
                        aria-label={`Delete FAQ: ${faq.question}`}
                      >
                        {deleting === i ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />} Delete
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
