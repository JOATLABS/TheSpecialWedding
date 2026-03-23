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
  MessageSquare, StickyNote, FileSignature, Eye
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

type TabType = 'overview' | 'timeline' | 'payments' | 'contracts' | 'forms' | 'updates';

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
    { key: 'contracts', label: 'Contract', icon: <FileSignature className="w-4 h-4" /> },
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
        {activeTab === 'timeline' && <TimelineTab events={data.wedding?.events || []} timezone={data.wedding?.timezone} onNoteAdded={fetchDashboard} />}
        {activeTab === 'payments' && <PaymentsTab contract={data.contract} />}
        {activeTab === 'contracts' && <ContractTab />}
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

                          {/* Item-level notes */}
                          {item.notes.length > 0 && (
                            <div className="mt-2 ml-[72px] space-y-1.5">
                              {item.notes.map((note) => (
                                <div key={note.id} className="flex items-start gap-2 text-xs">
                                  <StickyNote className="w-3 h-3 text-amber-400 mt-0.5 flex-shrink-0" />
                                  <div className="flex-1">
                                    <span className="text-gray-600">{note.text}</span>
                                    <div className="flex items-center gap-1.5 mt-0.5">
                                      <span className="text-gray-400">{note.author_name || note.author_role}</span>
                                      {noteStatusBadge(note.status)}
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}

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

                {/* Event-level notes */}
                {eventNotes.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
                      <StickyNote className="w-4 h-4" /> General Notes
                    </h4>
                    <div className="space-y-2">
                      {eventNotes.map((note) => (
                        <div key={note.id} className="p-3 bg-amber-50/50 border border-amber-100 rounded-lg">
                          <p className="text-sm text-gray-700">{note.text}</p>
                          <div className="flex items-center gap-2 mt-1.5 text-xs text-gray-400">
                            <span>{note.author_name || note.author_role}</span>
                            {noteStatusBadge(note.status)}
                            {note.created_at && (
                              <span>· {new Date(note.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

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
