'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import CoupleSidebar, { type CoupleSection } from '../components/CoupleSidebar';
import CoupleTopHeader from '../components/CoupleTopHeader';
import PageHeader from '@/components/ui/PageHeader';
import MessageBubble from '@/components/ui/MessageBubble';
import ChatInput from '@/components/ui/ChatInput';
import InboxListItem from '@/components/ui/InboxListItem';
import SplitPanelInbox from '@/components/ui/SplitPanelInbox';
import {
  Heart, Calendar, Users, DollarSign, FileText,
  Clock, MapPin, ChevronRight, Loader2,
  CheckCircle, AlertCircle, Phone, Mail, Building2, Archive,
  ClipboardList, Send, ChevronDown, ChevronUp,
  MessageSquare, StickyNote, FileSignature, Eye,
  MessageCircle,
  Gift, HelpCircle, QrCode, BellRing, Plus,
  Pencil, Trash2, ExternalLink, Download, BellOff,
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
    succeeded: 'bg-green-100 dark:bg-green-950/30 text-green-700 dark:text-green-400',
    scheduled: 'bg-blue-100 dark:bg-blue-950/30 text-blue-700 dark:text-blue-400',
    processing: 'bg-yellow-100 dark:bg-yellow-950/30 text-yellow-700 dark:text-yellow-400',
    failed: 'bg-red-100 dark:bg-red-950/30 text-red-700 dark:text-red-400',
    cancelled: 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400',
  };
  return colors[status] || 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400';
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function CoupleDashboardPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<DashboardData | null>(null);
  const [activeSection, setActiveSection] = useState<CoupleSection>('dashboard');
  const [unreadMessages, setUnreadMessages] = useState(0);

  // Sidebar state
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 1024;
      setIsMobile(mobile);
      if (mobile) setSidebarOpen(false);
      else setSidebarOpen(true);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

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
    } catch {
      toast.error('Failed to connect to server');
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  // Register service worker for PWA + push
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch((err) => {
        console.warn('SW registration failed:', err);
      });
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('couple_token');
    localStorage.removeItem('couple_data');
    router.push('/couple/login');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-10 h-10 animate-spin text-primary-500 mx-auto mb-4" />
          <p className="text-slate-600 dark:text-slate-400">Loading your wedding portal...</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-4" />
          <p className="text-slate-700 dark:text-slate-300 mb-4">We couldn&apos;t load your dashboard right now.</p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={fetchDashboard}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Try Again
            </button>
            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Sign Out
            </button>
          </div>
        </div>
      </div>
    );
  }

  const pendingForms = data.forms?.filter(f => f.status === 'pending').length || 0;

  return (
    <div className="min-h-screen overflow-x-hidden bg-light-bg dark:bg-dark-bg text-light-text dark:text-dark-text font-sans transition-colors duration-300">
      <CoupleSidebar
        isOpen={sidebarOpen}
        setIsOpen={setSidebarOpen}
        isMobile={isMobile}
        activeSection={activeSection}
        onSectionChange={setActiveSection}
        onLogout={handleLogout}
        unreadInbox={unreadMessages}
        pendingForms={pendingForms}
      />

      <div
        className="relative z-10 flex flex-col min-h-screen transition-[margin] duration-300 ease-out"
        style={{
          marginLeft: !isMobile ? (sidebarOpen ? '18rem' : '5rem') : '0',
        }}
      >
        <CoupleTopHeader
          onMenuClick={() => setSidebarOpen(!sidebarOpen)}
          coupleName={data.wedding?.couple_names}
          onLogout={handleLogout}
        />

        {/* Archived Banner */}
        {data.archived && (
          <div className="bg-amber-50 dark:bg-amber-950/30 border-b border-amber-200 dark:border-amber-800/50 px-4 py-3">
            <div className="flex items-center gap-3 text-amber-700 dark:text-amber-400">
              <Archive className="w-5 h-5 flex-shrink-0" />
              <p className="text-sm">This wedding has been completed and archived. You can still view all your details and memories.</p>
            </div>
          </div>
        )}

        <main className="flex-1 p-4 sm:p-6 lg:p-8 space-y-6 overflow-x-hidden">
          {activeSection === 'dashboard' && <DashboardSection data={data} />}
          {activeSection === 'timeline' && <TimelineSection events={data.wedding?.events || []} timezone={data.wedding?.timezone} onNoteAdded={fetchDashboard} />}
          {activeSection === 'payments' && <PaymentsSection contract={data.contract} />}
          {activeSection === 'forms' && <FormsSection forms={data.forms || []} />}
          {activeSection === 'inbox' && (
            <InboxSection
              updates={data.updates || []}
              onMessageSent={() => setUnreadMessages(0)}
              onMessagesRead={() => setUnreadMessages(0)}
              archived={!!data.archived}
            />
          )}
          {activeSection === 'registry' && <RegistrySection registries={data.wedding?.registries || []} archived={!!data.archived} onUpdated={fetchDashboard} />}
          {activeSection === 'faq' && <FAQSection faqs={data.wedding?.faqs || []} archived={!!data.archived} onUpdated={fetchDashboard} />}
        </main>
      </div>
    </div>
  );
}


// ============================================================================
// SECTION: DASHBOARD (Overview)
// ============================================================================

function DashboardSection({ data }: { data: DashboardData }) {
  const days = data.wedding?.date ? daysUntil(data.wedding.date) : null;
  const stats = data.guest_stats;
  const budget = data.budget_summary;
  const budgetPercent = budget.total_budget > 0 ? Math.min(100, (budget.total_spent / budget.total_budget) * 100) : 0;

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" description="Your wedding overview at a glance" />
      {/* Countdown */}
      {days !== null && days > 0 && !data.archived && (
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <p className="text-slate-500 dark:text-slate-400 text-sm font-medium mb-2">Your big day is</p>
          <div className="text-5xl sm:text-6xl font-semibold text-slate-900 dark:text-white mb-1">{days}</div>
          <p className="text-slate-600 dark:text-slate-300">days away</p>
          <p className="text-slate-400 dark:text-slate-500 text-sm mt-2">{data.wedding?.date ? formatDate(data.wedding.date) : ''}</p>
        </div>
      )}

      {/* Quick Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700 shadow-sm">
          <Users className="w-5 h-5 text-indigo-500 mb-2" />
          <div className="text-2xl font-semibold text-slate-900 dark:text-white">{stats.total_invited}</div>
          <div className="text-xs text-slate-500 dark:text-slate-400">Guests invited</div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700 shadow-sm">
          <CheckCircle className="w-5 h-5 text-green-500 mb-2" />
          <div className="text-2xl font-semibold text-slate-900 dark:text-white">{stats.confirmed}</div>
          <div className="text-xs text-slate-500 dark:text-slate-400">Confirmed</div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700 shadow-sm">
          <Clock className="w-5 h-5 text-amber-500 mb-2" />
          <div className="text-2xl font-semibold text-slate-900 dark:text-white">{stats.pending}</div>
          <div className="text-xs text-slate-500 dark:text-slate-400">Awaiting response</div>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700 shadow-sm">
          <DollarSign className="w-5 h-5 text-emerald-500 mb-2" />
          <div className="text-2xl font-semibold text-slate-900 dark:text-white">{formatCurrency(budget.total_budget)}</div>
          <div className="text-xs text-slate-500 dark:text-slate-400">Total budget</div>
        </div>
      </div>

      {/* Budget Progress */}
      {budget.total_budget > 0 && (
        <div className="bg-white dark:bg-slate-800 rounded-xl p-6 border border-slate-200 dark:border-slate-700 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-slate-900 dark:text-white">Budget progress</h3>
            <span className="text-sm text-slate-500 dark:text-slate-400">{budgetPercent.toFixed(0)}% spent</span>
          </div>
          <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-3 mb-3">
            <div
              className={`h-3 rounded-full transition-all ${budgetPercent > 90 ? 'bg-red-500' : budgetPercent > 70 ? 'bg-amber-500' : 'bg-indigo-500'}`}
              style={{ width: `${budgetPercent}%` }}
            />
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-500 dark:text-slate-400">Spent: {formatCurrency(budget.total_spent)}</span>
            <span className="text-slate-500 dark:text-slate-400">Remaining: {formatCurrency(budget.remaining)}</span>
          </div>
        </div>
      )}

      {/* Venue & Planner */}
      <div className="grid sm:grid-cols-2 gap-4">
        {data.wedding?.venue && (
          <div className="bg-white dark:bg-slate-800 rounded-xl p-6 border border-slate-200 dark:border-slate-700 shadow-sm">
            <div className="flex items-center gap-3 mb-3">
              <MapPin className="w-5 h-5 text-indigo-500" />
              <h3 className="font-semibold text-slate-900 dark:text-white">Venue</h3>
            </div>
            <p className="text-slate-700 dark:text-slate-300">{data.wedding.venue}</p>
          </div>
        )}

        {data.planner && (
          <div className="bg-white dark:bg-slate-800 rounded-xl p-6 border border-slate-200 dark:border-slate-700 shadow-sm">
            <div className="flex items-center gap-3 mb-3">
              <Building2 className="w-5 h-5 text-indigo-500" />
              <h3 className="font-semibold text-slate-900 dark:text-white">Your planner</h3>
            </div>
            <p className="text-slate-900 dark:text-white font-medium">{data.planner.name || data.planner.company}</p>
            {data.planner.company && data.planner.name && (
              <p className="text-slate-500 dark:text-slate-400 text-sm">{data.planner.company}</p>
            )}
            <div className="mt-3 space-y-1">
              {data.planner.email && (
                <a href={`mailto:${data.planner.email}`} className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">
                  <Mail className="w-3.5 h-3.5" /> {data.planner.email}
                </a>
              )}
              {data.planner.phone && (
                <a href={`tel:${data.planner.phone}`} className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">
                  <Phone className="w-3.5 h-3.5" /> {data.planner.phone}
                </a>
              )}
            </div>
          </div>
        )}
      </div>

      {/* QR Code + Push Notifications */}
      <div className="grid sm:grid-cols-2 gap-4">
        <QRCodeWidget />
        <PushNotificationWidget />
      </div>

      {/* Upcoming Events Preview */}
      {data.wedding?.events?.length > 0 && (
        <div className="bg-white dark:bg-slate-800 rounded-xl p-6 border border-slate-200 dark:border-slate-700 shadow-sm">
          <h3 className="font-semibold text-slate-900 dark:text-white mb-4">Coming up</h3>
          <div className="space-y-3">
            {data.wedding.events.slice(0, 3).map((event, i) => (
              <div key={i} className="flex items-center gap-4 p-3 rounded-lg bg-slate-50 dark:bg-slate-700/50">
                <div className="w-12 h-12 bg-indigo-600 dark:bg-indigo-500 rounded-lg flex items-center justify-center text-white text-xs font-medium">
                  {new Date(event.date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-slate-900 dark:text-white text-sm">{eventTypeLabel(event.type)}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                    {event.details?.venue_name && `${event.details.venue_name}`}
                    {event.details?.time && ` · ${event.details.time}`}
                  </p>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-300 dark:text-slate-600 flex-shrink-0" />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


// ============================================================================
// SECTION: TIMELINE
// ============================================================================

function TimelineSection({ events, timezone, onNoteAdded }: { events: WeddingEvent[]; timezone?: string; onNoteAdded?: () => void }) {
  const [expandedEvent, setExpandedEvent] = useState<number | null>(null);
  const [noteText, setNoteText] = useState('');
  const [noteTarget, setNoteTarget] = useState<{ eventIndex: number; itemId?: string } | null>(null);
  const [submittingNote, setSubmittingNote] = useState(false);

  if (!events || events.length === 0) {
    return (
      <div>
        <PageHeader title="Timeline" description="Your wedding day schedule and events" />
        <div className="text-center py-16">
          <Calendar className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
          <p className="text-slate-600 dark:text-slate-400 font-medium">No events scheduled yet</p>
          <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">Your planner will add events as they&apos;re confirmed.</p>
        </div>
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
        toast.error(err.detail || 'Could not add note. Please try again.');
      }
    } catch {
      toast.error('Connection error — please check your internet and try again.');
    } finally {
      setSubmittingNote(false);
    }
  };

  const noteStatusBadge = (status: string) => {
    switch (status) {
      case 'pending': return <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-100 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400">Pending</span>;
      case 'seen': return <span className="text-xs px-1.5 py-0.5 rounded-full bg-blue-100 dark:bg-blue-950/30 text-blue-700 dark:text-blue-400">Seen</span>;
      case 'addressed': return <span className="text-xs px-1.5 py-0.5 rounded-full bg-green-100 dark:bg-green-950/30 text-green-700 dark:text-green-400">Done</span>;
      default: return null;
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Timeline" description="Your wedding day schedule and events" />
      {events.map((event, eventIdx) => {
        const orderItems = (event.order_of_events || []).sort((a, b) => a.order - b.order);
        const eventNotes = event.event_notes || [];
        const isExpanded = expandedEvent === eventIdx;

        return (
          <div key={eventIdx} className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden">
            {/* Event Header */}
            <div className="bg-indigo-600 dark:bg-indigo-500/90 px-6 py-3 flex items-center justify-between">
              <p className="text-white text-sm font-medium">{eventTypeLabel(event.type)}</p>
              {(orderItems.length > 0 || eventNotes.length > 0) && (
                <button
                  onClick={() => setExpandedEvent(isExpanded ? null : eventIdx)}
                  className="text-indigo-200 hover:text-white text-xs flex items-center gap-1 transition-colors"
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
                  <Calendar className="w-5 h-5 text-slate-400 dark:text-slate-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-slate-900 dark:text-white">{formatDate(event.date)}</p>
                    {event.details?.time && <p className="text-sm text-slate-500 dark:text-slate-400">{event.details.time}</p>}
                  </div>
                </div>
                {event.details?.venue_name && (
                  <div className="flex items-start gap-3">
                    <MapPin className="w-5 h-5 text-slate-400 dark:text-slate-500 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-slate-900 dark:text-white">{event.details.venue_name}</p>
                      {event.details.location && <p className="text-sm text-slate-500 dark:text-slate-400">{event.details.location}</p>}
                    </div>
                  </div>
                )}
              </div>
              {event.details?.attire && (
                <div className="mt-4 p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg">
                  <p className="text-sm text-slate-700 dark:text-slate-300"><span className="font-medium">Dress code:</span> {event.details.attire}</p>
                </div>
              )}
            </div>

            {/* Expanded: Order of Events + Notes */}
            {isExpanded && (
              <div className="border-t border-slate-200 dark:border-slate-700 px-6 py-4 space-y-4">
                {orderItems.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                      <Clock className="w-4 h-4" /> Run of show
                    </h4>
                    <div className="space-y-2">
                      {orderItems.map((item) => (
                        <div key={item.id} className="p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg">
                          <div className="flex items-center gap-3">
                            {item.time && (
                              <span className="text-xs font-medium text-slate-900 dark:text-slate-100 bg-slate-200 dark:bg-slate-600 px-2 py-1 rounded min-w-[60px] text-center">
                                {item.time}
                              </span>
                            )}
                            <div className="flex-1">
                              <p className="text-sm font-medium text-slate-900 dark:text-white">{item.title}</p>
                              {item.description && <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{item.description}</p>}
                              {item.duration_minutes && <p className="text-xs text-slate-400 dark:text-slate-500">{item.duration_minutes} min</p>}
                            </div>
                            <button
                              onClick={() => setNoteTarget({ eventIndex: eventIdx, itemId: item.id })}
                              className="text-slate-400 dark:text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors p-1"
                              title="Leave a note for your planner"
                            >
                              <MessageSquare className="w-4 h-4" />
                            </button>
                          </div>

                          {/* Item-level notes */}
                          {item.notes.length > 0 && (() => {
                            const parentNotes = item.notes.filter(n => !n.reply_to);
                            const replies = item.notes.filter(n => !!n.reply_to);
                            const repliesMap: Record<string, EventNote[]> = {};
                            replies.forEach(r => {
                              if (r.reply_to) {
                                if (!repliesMap[r.reply_to]) repliesMap[r.reply_to] = [];
                                repliesMap[r.reply_to].push(r);
                              }
                            });
                            return parentNotes.length > 0 ? (
                              <div className="mt-2 ml-[72px] space-y-1.5">
                                {parentNotes.map((note) => (
                                  <div key={note.id}>
                                    <div className="flex items-start gap-2 text-xs">
                                      <StickyNote className="w-3 h-3 text-amber-400 mt-0.5 flex-shrink-0" />
                                      <div className="flex-1">
                                        <span className="text-slate-600 dark:text-slate-300">{note.text}</span>
                                        <div className="flex items-center gap-1.5 mt-0.5">
                                          <span className="text-slate-400 dark:text-slate-500">{note.author_name || note.author_role}</span>
                                          {noteStatusBadge(note.status)}
                                        </div>
                                      </div>
                                    </div>
                                    {(repliesMap[note.id] || []).map(reply => (
                                      <div key={reply.id} className="ml-5 mt-1 flex items-start gap-2 text-xs">
                                        <MessageCircle className="w-3 h-3 text-blue-400 mt-0.5 flex-shrink-0" />
                                        <div className="flex-1">
                                          <span className="text-slate-600 dark:text-slate-300">{reply.text}</span>
                                          <div className="flex items-center gap-1.5 mt-0.5">
                                            <span className="font-medium text-slate-900 dark:text-white">Planner</span>
                                            {reply.created_at && (
                                              <span className="text-slate-400 dark:text-slate-500">· {new Date(reply.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
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

                          {/* Inline note form */}
                          {noteTarget?.eventIndex === eventIdx && noteTarget?.itemId === item.id && (
                            <div className="mt-2 ml-[72px] flex gap-2">
                              <input
                                type="text"
                                value={noteText}
                                onChange={(e) => setNoteText(e.target.value)}
                                placeholder="Leave a note for your planner..."
                                className="flex-1 px-3 py-1.5 border border-slate-300 dark:border-slate-600 rounded-lg text-xs bg-white dark:bg-slate-700 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                                autoFocus
                                onKeyDown={(e) => e.key === 'Enter' && handleSubmitNote(eventIdx, item.id)}
                              />
                              <button
                                onClick={() => handleSubmitNote(eventIdx, item.id)}
                                disabled={submittingNote || !noteText.trim()}
                                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs disabled:opacity-50 flex items-center gap-1 transition-colors"
                              >
                                {submittingNote ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                              </button>
                              <button
                                onClick={() => { setNoteTarget(null); setNoteText(''); }}
                                className="text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 text-xs"
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
                {eventNotes.length > 0 && (() => {
                  const parentNotes = eventNotes.filter(n => !n.reply_to);
                  const replies = eventNotes.filter(n => !!n.reply_to);
                  const repliesMap: Record<string, EventNote[]> = {};
                  replies.forEach(r => {
                    if (r.reply_to) {
                      if (!repliesMap[r.reply_to]) repliesMap[r.reply_to] = [];
                      repliesMap[r.reply_to].push(r);
                    }
                  });
                  return parentNotes.length > 0 ? (
                    <div>
                      <h4 className="text-sm font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                        <StickyNote className="w-4 h-4" /> Notes
                      </h4>
                      <div className="space-y-2">
                        {parentNotes.map((note) => (
                          <div key={note.id}>
                            <div className="p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/50 rounded-lg">
                              <p className="text-sm text-slate-900 dark:text-amber-100">{note.text}</p>
                              <div className="flex items-center gap-2 mt-1.5 text-xs text-slate-500 dark:text-amber-600">
                                <span>{note.author_name || note.author_role}</span>
                                {noteStatusBadge(note.status)}
                                {note.created_at && <span>· {new Date(note.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>}
                              </div>
                            </div>
                            {(repliesMap[note.id] || []).map(reply => (
                              <div key={reply.id} className="ml-4 mt-1.5 p-2.5 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800/50 rounded-lg">
                                <p className="text-sm text-slate-900 dark:text-blue-100">{reply.text}</p>
                                <div className="flex items-center gap-2 mt-1 text-xs text-slate-500 dark:text-blue-600">
                                  <span className="font-medium">Planner</span>
                                  {reply.created_at && <span>· {new Date(reply.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>}
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
                      placeholder="Leave a note about this event..."
                      className="flex-1 px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none"
                      autoFocus
                      onKeyDown={(e) => e.key === 'Enter' && handleSubmitNote(eventIdx)}
                    />
                    <button
                      onClick={() => handleSubmitNote(eventIdx)}
                      disabled={submittingNote || !noteText.trim()}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm disabled:opacity-50 flex items-center gap-1 transition-colors"
                    >
                      {submittingNote ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    </button>
                    <button onClick={() => { setNoteTarget(null); setNoteText(''); }} className="text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 text-sm">Cancel</button>
                  </div>
                ) : (
                  <button
                    onClick={() => setNoteTarget({ eventIndex: eventIdx })}
                    className="w-full py-2 border border-dashed border-slate-300 dark:border-slate-600 rounded-lg text-sm text-slate-500 dark:text-slate-400 hover:border-indigo-400 dark:hover:border-indigo-500 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors flex items-center justify-center gap-1"
                  >
                    <MessageSquare className="w-4 h-4" />
                    Add a note
                  </button>
                )}
              </div>
            )}

            {/* Collapse hint */}
            {!isExpanded && orderItems.length > 0 && (
              <button
                onClick={() => setExpandedEvent(eventIdx)}
                className="w-full border-t border-slate-200 dark:border-slate-700 px-6 py-2.5 text-sm text-indigo-600 dark:text-indigo-400 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors flex items-center justify-center gap-1"
              >
                <Clock className="w-4 h-4" />
                View run of show ({orderItems.length} items)
                <ChevronDown className="w-4 h-4" />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}


// ============================================================================
// SECTION: PAYMENTS (merged Payments + Contract)
// ============================================================================

function PaymentsSection({ contract }: { contract?: ContractInfo | null }) {
  const [contractDetail, setContractDetail] = useState<ContractDetail | null>(null);
  const [loadingContract, setLoadingContract] = useState(true);

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
          setContractDetail(data.contract || null);
        }
      } catch (err) {
        console.error('Failed to fetch contract', err);
      } finally {
        setLoadingContract(false);
      }
    };
    fetchContract();
  }, []);

  if (!contract && loadingContract) {
    return (
      <div>
        <PageHeader title="Payments" description="Track your wedding package and payment schedule" />
        <div className="text-center py-16">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto" />
        </div>
      </div>
    );
  }

  if (!contract) {
    return (
      <div>
        <PageHeader title="Payments" description="Track your wedding package and payment schedule" />
        <div className="text-center py-16">
          <DollarSign className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
          <p className="text-slate-600 dark:text-slate-400 font-medium">No payment schedule yet</p>
          <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">Your planner will set this up once your package is confirmed.</p>
        </div>
      </div>
    );
  }

  const contractStatusLabel = (status: string) => {
    const labels: Record<string, { text: string; style: string }> = {
      draft: { text: 'Draft', style: 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400' },
      sent: { text: 'Awaiting Signature', style: 'bg-amber-100 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400' },
      viewed: { text: 'Viewed', style: 'bg-blue-100 dark:bg-blue-950/30 text-blue-700 dark:text-blue-400' },
      signed: { text: 'Signed', style: 'bg-green-100 dark:bg-green-950/30 text-green-700 dark:text-green-400' },
      active: { text: 'Active', style: 'bg-green-100 dark:bg-green-950/30 text-green-700 dark:text-green-400' },
      completed: { text: 'Completed', style: 'bg-emerald-100 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400' },
      cancelled: { text: 'Cancelled', style: 'bg-red-100 dark:bg-red-950/30 text-red-700 dark:text-red-400' },
    };
    return labels[status] || { text: status, style: 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400' };
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Payments" description="Track your wedding package and payment schedule" />

      {/* Contract Summary Card */}
      {contractDetail && (
        <div className="bg-white dark:bg-slate-800 rounded-xl p-6 border border-slate-200 dark:border-slate-700 shadow-sm">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{contractDetail.package_name || 'Wedding Package'}</h3>
              {contractDetail.couple_name && <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">{contractDetail.couple_name}</p>}
            </div>
            <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${contractStatusLabel(contractDetail.status).style}`}>
              {contractStatusLabel(contractDetail.status).text}
            </span>
          </div>

          {/* Key Dates */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            {contractDetail.sent_at && (
              <div>
                <p className="text-slate-400 dark:text-slate-500 text-xs">Sent</p>
                <p className="text-slate-900 dark:text-white">{new Date(contractDetail.sent_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</p>
              </div>
            )}
            {contractDetail.viewed_at && (
              <div>
                <p className="text-slate-400 dark:text-slate-500 text-xs">Viewed</p>
                <p className="text-slate-900 dark:text-white">{new Date(contractDetail.viewed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</p>
              </div>
            )}
            {contractDetail.signed_at && (
              <div>
                <p className="text-slate-400 dark:text-slate-500 text-xs">Signed</p>
                <p className="text-slate-900 dark:text-white">{new Date(contractDetail.signed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Payment Summary */}
      <div className="bg-white dark:bg-slate-800 rounded-xl p-6 border border-slate-200 dark:border-slate-700 shadow-sm">
        <h3 className="font-semibold text-slate-900 dark:text-white mb-4">Payment overview</h3>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-2xl font-semibold text-slate-900 dark:text-white">{formatCurrency(contract.summary.total_amount)}</div>
            <div className="text-xs text-slate-500 dark:text-slate-400">Total</div>
          </div>
          <div>
            <div className="text-2xl font-semibold text-green-600 dark:text-green-400">{formatCurrency(contract.summary.paid_amount)}</div>
            <div className="text-xs text-slate-500 dark:text-slate-400">Paid</div>
          </div>
          <div>
            <div className="text-2xl font-semibold text-amber-600 dark:text-amber-400">{formatCurrency(contract.summary.remaining)}</div>
            <div className="text-xs text-slate-500 dark:text-slate-400">Remaining</div>
          </div>
        </div>
      </div>

      {/* Contract Sections */}
      {contractDetail?.sections && contractDetail.sections.length > 0 && (
        <div className="space-y-4">
          <h3 className="font-semibold text-slate-900 dark:text-white">Contract details</h3>
          {contractDetail.sections.map((section, idx) => (
            <div key={idx} className="bg-white dark:bg-slate-800 rounded-xl p-6 border border-slate-200 dark:border-slate-700 shadow-sm">
              <h4 className="font-semibold text-slate-900 dark:text-white mb-3">{section.title}</h4>
              <div className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed whitespace-pre-wrap">{section.content}</div>
            </div>
          ))}
        </div>
      )}

      {/* Payment Schedule */}
      <div>
        <h3 className="font-semibold text-slate-900 dark:text-white mb-3">Payment schedule</h3>
        <div className="space-y-3">
          {contract.payments.map((payment) => (
            <div key={payment.id} className="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700 shadow-sm flex items-center justify-between">
              <div>
                <p className="font-medium text-slate-900 dark:text-white">{payment.name}</p>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Due {payment.due_date ? new Date(payment.due_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'TBD'}
                </p>
              </div>
              <div className="text-right">
                <p className="font-semibold text-slate-900 dark:text-white">{formatCurrency(payment.amount, payment.currency)}</p>
                <span className={`text-xs px-2 py-0.5 rounded-full ${paymentStatusColor(payment.status)}`}>
                  {payment.status === 'succeeded' ? 'Paid' : payment.status.charAt(0).toUpperCase() + payment.status.slice(1)}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}


// ============================================================================
// SECTION: FORMS
// ============================================================================

function FormsSection({ forms }: { forms: FormItem[] }) {
  const router = useRouter();

  if (!forms || forms.length === 0) {
    return (
      <div>
        <PageHeader title="Forms" description="Questionnaires and forms from your planner" />
        <div className="text-center py-16">
          <ClipboardList className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
          <p className="text-slate-600 dark:text-slate-400 font-medium">No forms to fill out</p>
          <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">Your planner will share forms here when they need information from you.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Forms" description="Questionnaires and forms from your planner" />
      {forms.map((form) => (
        <div key={form.id} className="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-medium text-slate-900 dark:text-white">{form.title}</h3>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  form.status === 'submitted'
                    ? 'bg-green-100 dark:bg-green-950/30 text-green-700 dark:text-green-400'
                    : 'bg-amber-100 dark:bg-amber-950/30 text-amber-700 dark:text-amber-400'
                }`}>
                  {form.status === 'submitted' ? 'Submitted' : 'Needs your input'}
                </span>
              </div>
              {form.description && <p className="text-sm text-slate-500 dark:text-slate-400 truncate">{form.description}</p>}
            </div>
            <button
              onClick={() => router.push(`/couple/forms/${form.id}`)}
              className="ml-4 flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {form.status === 'submitted' ? 'Review' : 'Fill out'}
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}


// ============================================================================
// SECTION: INBOX (shared components, split-panel layout)
// ============================================================================

interface MessageItem {
  id: string;
  sender_role: 'couple' | 'planner';
  sender_name: string;
  content: string;
  read_by_planner: boolean;
  created_at?: string;
}

function InboxSection({ updates, onMessageSent, onMessagesRead, archived = false }: {
  updates: UpdateItem[];
  onMessageSent: () => void;
  onMessagesRead: () => void;
  archived?: boolean;
}) {
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [msgLoading, setMsgLoading] = useState(true);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [mobileShowDetail, setMobileShowDetail] = useState(false);
  const messagesEndRef = useCallback((node: HTMLDivElement | null) => {
    if (node) node.scrollIntoView({ behavior: 'smooth' });
  }, []);

  const fetchMessages = useCallback(async () => {
    const token = localStorage.getItem('couple_token');
    if (!token) return;
    try {
      const res = await fetch(`${getApiBaseUrl()}/couple/portal/messages?limit=100`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: 'no-store',
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
        onMessagesRead();
      }
    } catch {
      toast.error('Could not load messages. Please try again.');
    } finally {
      setMsgLoading(false);
    }
  }, []);

  useEffect(() => { fetchMessages(); }, [fetchMessages]);

  const handleSend = async () => {
    if (!newMessage.trim() || sending) return;
    const token = localStorage.getItem('couple_token');
    if (!token) return;
    setSending(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/couple/portal/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ content: newMessage.trim() }),
      });
      if (res.ok) {
        setNewMessage('');
        onMessageSent();
        await fetchMessages();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Message not sent. Please try again.');
      }
    } catch {
      toast.error('Connection error — please check your internet.');
    } finally {
      setSending(false);
    }
  };

  const handleRefresh = () => { setMsgLoading(true); fetchMessages(); };

  const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
  const unreadCount = messages.filter(m => m.sender_role === 'planner' && !m.read_by_planner).length;
  const conversationPreview = lastMessage
    ? `${lastMessage.sender_role === 'couple' ? 'You' : lastMessage.sender_name}: ${lastMessage.content}`
    : 'Start a conversation with your planner';

  return (
    <div className="space-y-4">
      <PageHeader title="Inbox" description="Messages between you and your planner" />

      {/* Toolbar */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <span className="text-sm text-slate-500 dark:text-slate-400">
          1 conversation
          {unreadCount > 0 && (
            <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400">
              {unreadCount} unread
            </span>
          )}
        </span>
        <button
          onClick={handleRefresh}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm bg-white text-slate-600 hover:bg-slate-100 dark:bg-slate-800 dark:text-slate-400 transition border border-slate-200 dark:border-slate-700"
        >
          <Loader2 size={14} className={msgLoading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Split-panel layout using shared component */}
      <SplitPanelInbox
        loading={msgLoading}
        hasSelection={showChat}
        mobileShowDetail={mobileShowDetail}
        listContent={
          <InboxListItem
            id="planner-conversation"
            type="planner"
            name="Your Planner"
            preview={conversationPreview}
            isRead={unreadCount === 0}
            isSelected={showChat}
            timestamp={lastMessage?.created_at ? new Date(lastMessage.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : ''}
            unreadCount={unreadCount > 0 ? unreadCount : undefined}
            accentColor="indigo"
            onClick={() => { setShowChat(true); setMobileShowDetail(true); }}
          />
        }
        detailContent={
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 flex flex-col h-[calc(100vh-300px)]">
            {/* Chat header */}
            <div className="p-4 border-b border-slate-100 dark:border-slate-800">
              <button
                onClick={() => { setMobileShowDetail(false); setShowChat(false); }}
                className="lg:hidden flex items-center gap-1 text-sm text-slate-500 mb-3"
              >
                <ChevronDown size={16} className="rotate-90" />
                Back to inbox
              </button>
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
                  <Heart size={16} className="text-indigo-500" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Your Planner</h2>
                  <p className="text-xs text-slate-400">Direct conversation</p>
                </div>
              </div>
            </div>

            {/* Messages area using shared MessageBubble */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {msgLoading ? (
                <div className="text-center text-slate-400 py-8">
                  <Loader2 className="w-5 h-5 mx-auto mb-2 animate-spin" />
                  Loading messages...
                </div>
              ) : messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-slate-400 dark:text-slate-500">
                  <MessageCircle className="w-12 h-12 mb-3 opacity-50" />
                  <p className="text-sm font-medium">No messages yet</p>
                  <p className="text-xs mt-1">Send a message to start a conversation with your planner.</p>
                </div>
              ) : (
                messages.map((msg) => (
                  <MessageBubble
                    key={msg.id}
                    content={msg.content}
                    senderName={msg.sender_role !== 'couple' ? msg.sender_name : undefined}
                    isSelf={msg.sender_role === 'couple'}
                    timestamp={msg.created_at ? new Date(msg.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true }) : undefined}
                    isRead={msg.read_by_planner}
                    showReadIndicator={true}
                    accentColor="indigo"
                  />
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input area using shared ChatInput */}
            <ChatInput
              value={newMessage}
              onChange={setNewMessage}
              onSend={handleSend}
              sending={sending}
              archived={archived}
              placeholder="Message your planner..."
              accentColor="indigo"
            />
          </div>
        }
      />
    </div>
  );
}


// ============================================================================
// SECTION: REGISTRY
// ============================================================================

interface RegistryItem {
  name: string;
  url: string;
  color?: string;
}

function RegistrySection({ registries, archived, onUpdated }: { registries: RegistryItem[]; archived: boolean; onUpdated: () => void }) {
  const [showForm, setShowForm] = useState(false);
  const [editIndex, setEditIndex] = useState<number | null>(null);
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [color, setColor] = useState('bg-indigo-600');
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
    { value: 'bg-slate-600', label: 'Slate' },
    { value: 'bg-slate-900', label: 'Navy' },
  ];

  const resetForm = () => {
    setName('');
    setUrl('');
    setColor('bg-indigo-600');
    setShowForm(false);
    setEditIndex(null);
  };

  const startEdit = (index: number) => {
    const item = registries[index];
    setName(item.name);
    setUrl(item.url);
    setColor(item.color || 'bg-indigo-600');
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
        throw new Error(err.detail || 'Could not save registry');
      }

      toast.success(isEdit ? 'Registry updated' : 'Registry added');
      resetForm();
      onUpdated();
    } catch (e: any) {
      toast.error(e.message || 'Something went wrong. Please try again.');
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
        throw new Error(err.detail || 'Could not remove registry');
      }

      toast.success('Registry removed');
      onUpdated();
    } catch (e: any) {
      toast.error(e.message || 'Something went wrong. Please try again.');
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div>
      <PageHeader title="Registry" description="Your guests can find your registries here. Add links to any store where you're registered.">
        {!archived && !showForm && (
          <button
            onClick={() => { resetForm(); setShowForm(true); }}
            className="flex items-center gap-1.5 px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg transition-colors"
            aria-label="Add a new registry"
          >
            <Plus className="w-4 h-4" /> Add registry
          </button>
        )}
      </PageHeader>

      {/* Add/Edit Form */}
      {showForm && (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm p-5 mb-6" role="form" aria-label={editIndex !== null ? 'Edit registry' : 'Add registry'}>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">{editIndex !== null ? 'Edit registry' : 'New registry'}</h3>
          <div className="space-y-3">
            <div>
              <label htmlFor="reg-name" className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Store name</label>
              <input
                id="reg-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Target, Amazon, Zola"
                className="w-full px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none bg-white dark:bg-slate-700 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500"
                aria-required="true"
              />
            </div>
            <div>
              <label htmlFor="reg-url" className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Registry link</label>
              <input
                id="reg-url"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://www.target.com/gift-registry/..."
                className="w-full px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none bg-white dark:bg-slate-700 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500"
                aria-required="true"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Button color</label>
              <div className="flex flex-wrap gap-2">
                {colorOptions.map((c) => (
                  <button
                    key={c.value}
                    type="button"
                    onClick={() => setColor(c.value)}
                    className={`w-8 h-8 rounded-full ${c.value} transition-all ${color === c.value ? 'ring-2 ring-offset-2 ring-indigo-500 dark:ring-indigo-400 scale-110' : 'opacity-60 hover:opacity-100'}`}
                    title={c.label}
                    aria-label={`Select ${c.label}`}
                    aria-pressed={color === c.value}
                  />
                ))}
              </div>
            </div>
            <div className="flex gap-2 pt-2">
              <button
                onClick={handleSave}
                disabled={saving || !name.trim() || !url.trim()}
                className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                {editIndex !== null ? 'Update' : 'Save'}
              </button>
              <button onClick={resetForm} className="px-4 py-2 text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-white transition-colors">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Registry Grid */}
      {registries.length === 0 && !showForm ? (
        <div className="text-center py-16">
          <Gift className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
          <p className="text-slate-600 dark:text-slate-400 font-medium">No registries added yet</p>
          {!archived && <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">Click &quot;Add registry&quot; to share where guests can find your wish list.</p>}
        </div>
      ) : (
        <div className={`grid gap-4 ${registries.length === 1 ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3' : registries.length === 2 ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3'}`}>
          {registries.map((reg, i) => (
            <div key={i} className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm p-5 text-center group">
              <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-3">{reg.name}</h3>
              <a
                href={reg.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`${reg.color || 'bg-indigo-600'} text-white px-6 py-2.5 rounded-lg hover:opacity-90 transition-opacity inline-flex items-center gap-2 text-sm font-medium`}
                aria-label={`View ${reg.name} registry (opens in new tab)`}
              >
                View registry <ExternalLink className="w-3.5 h-3.5" />
              </a>
              {!archived && (
                <div className="flex items-center justify-center gap-2 mt-3 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={() => startEdit(i)} className="text-xs text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 flex items-center gap-1 transition-colors" aria-label={`Edit ${reg.name}`}>
                    <Pencil className="w-3 h-3" /> Edit
                  </button>
                  <button onClick={() => handleDelete(i)} disabled={deleting === i} className="text-xs text-slate-500 dark:text-slate-400 hover:text-red-500 dark:hover:text-red-400 flex items-center gap-1 transition-colors disabled:opacity-50" aria-label={`Delete ${reg.name}`}>
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
// SECTION: FAQ
// ============================================================================

interface FAQItem {
  question: string;
  answer: string;
  link_url?: string | null;
  link_label?: string | null;
}

function FAQSection({ faqs, archived, onUpdated }: { faqs: FAQItem[]; archived: boolean; onUpdated: () => void }) {
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
    setQuestion(''); setAnswer(''); setLinkUrl(''); setLinkLabel('');
    setShowForm(false); setEditIndex(null);
  };

  const startEdit = (index: number) => {
    const item = faqs[index];
    setQuestion(item.question); setAnswer(item.answer);
    setLinkUrl(item.link_url || ''); setLinkLabel(item.link_label || '');
    setEditIndex(index); setShowForm(true);
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
        throw new Error(err.detail || 'Could not save FAQ');
      }

      toast.success(isEdit ? 'FAQ updated' : 'FAQ added');
      resetForm(); onUpdated();
    } catch (e: any) {
      toast.error(e.message || 'Something went wrong. Please try again.');
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
        throw new Error(err.detail || 'Could not remove FAQ');
      }
      toast.success('FAQ removed'); onUpdated();
    } catch (e: any) {
      toast.error(e.message || 'Something went wrong. Please try again.');
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div>
      <PageHeader title="FAQ" description="Help your guests prepare by answering common questions about your wedding day.">
        {!archived && !showForm && (
          <button
            onClick={() => { resetForm(); setShowForm(true); }}
            className="flex items-center gap-1.5 px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg transition-colors"
            aria-label="Add a new FAQ"
          >
            <Plus className="w-4 h-4" /> Add FAQ
          </button>
        )}
      </PageHeader>

      {/* Add/Edit Form */}
      {showForm && (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm p-5 mb-6" role="form" aria-label={editIndex !== null ? 'Edit FAQ' : 'Add FAQ'}>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">{editIndex !== null ? 'Edit FAQ' : 'New FAQ'}</h3>
          <div className="space-y-3">
            <div>
              <label htmlFor="faq-q" className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Question</label>
              <input
                id="faq-q" type="text" value={question} onChange={(e) => setQuestion(e.target.value)}
                placeholder="e.g., What should I wear?"
                className="w-full px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none bg-white dark:bg-slate-700 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500"
                aria-required="true"
              />
            </div>
            <div>
              <label htmlFor="faq-a" className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Answer</label>
              <textarea
                id="faq-a" value={answer} onChange={(e) => setAnswer(e.target.value)}
                placeholder="Your answer..."
                rows={3}
                className="w-full px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none resize-none bg-white dark:bg-slate-700 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500"
                aria-required="true"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="faq-link" className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Link URL (optional)</label>
                <input
                  id="faq-link" type="url" value={linkUrl} onChange={(e) => setLinkUrl(e.target.value)}
                  placeholder="https://..."
                  className="w-full px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none bg-white dark:bg-slate-700 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500"
                />
              </div>
              <div>
                <label htmlFor="faq-label" className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Link label (optional)</label>
                <input
                  id="faq-label" type="text" value={linkLabel} onChange={(e) => setLinkLabel(e.target.value)}
                  placeholder="e.g., Book hotel room"
                  className="w-full px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none bg-white dark:bg-slate-700 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500"
                />
              </div>
            </div>
            <div className="flex gap-2 pt-2">
              <button
                onClick={handleSave} disabled={saving || !question.trim() || !answer.trim()}
                className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                {editIndex !== null ? 'Update' : 'Save'}
              </button>
              <button onClick={resetForm} className="px-4 py-2 text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-white transition-colors">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* FAQ List */}
      {faqs.length === 0 && !showForm ? (
        <div className="text-center py-16">
          <HelpCircle className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
          <p className="text-slate-600 dark:text-slate-400 font-medium">No FAQs yet</p>
          {!archived && <p className="text-sm text-slate-400 dark:text-slate-500 mt-1">Add questions and answers to help your guests know what to expect.</p>}
        </div>
      ) : (
        <div className="space-y-3">
          {faqs.map((faq, i) => (
            <div key={i} className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden">
              <button
                onClick={() => setExpandedIndex(expandedIndex === i ? null : i)}
                className="w-full px-5 py-4 flex items-center justify-between text-left"
                aria-expanded={expandedIndex === i}
                aria-controls={`faq-answer-${i}`}
              >
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white pr-4">{faq.question}</h3>
                {expandedIndex === i ? <ChevronUp className="w-4 h-4 text-slate-400 dark:text-slate-500 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 text-slate-400 dark:text-slate-500 flex-shrink-0" />}
              </button>
              {expandedIndex === i && (
                <div id={`faq-answer-${i}`} className="px-5 pb-4 border-t border-slate-100 dark:border-slate-700">
                  <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed mt-3">{faq.answer}</p>
                  {faq.link_url && faq.link_label && (
                    <a
                      href={faq.link_url} target="_blank" rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 mt-3 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium rounded-lg transition-colors"
                    >
                      {faq.link_label} <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                  {!archived && (
                    <div className="flex items-center gap-3 mt-3 pt-3 border-t border-slate-100 dark:border-slate-700">
                      <button onClick={(e) => { e.stopPropagation(); startEdit(i); }} className="text-xs text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 flex items-center gap-1 transition-colors" aria-label={`Edit: ${faq.question}`}>
                        <Pencil className="w-3 h-3" /> Edit
                      </button>
                      <button onClick={(e) => { e.stopPropagation(); handleDelete(i); }} disabled={deleting === i} className="text-xs text-slate-500 dark:text-slate-400 hover:text-red-500 dark:hover:text-red-400 flex items-center gap-1 transition-colors disabled:opacity-50" aria-label={`Delete: ${faq.question}`}>
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


// ============================================================================
// WIDGETS
// ============================================================================

function QRCodeWidget() {
  const [qrUrl, setQrUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const generateQR = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('couple_token');
      const res = await fetch(`${getApiBaseUrl()}/couple/portal/qr-code`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Failed to generate QR code');
      const blob = await res.blob();
      setQrUrl(URL.createObjectURL(blob));
    } catch {
      toast.error('Could not generate QR code. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const downloadQR = () => {
    if (!qrUrl) return;
    const a = document.createElement('a');
    a.href = qrUrl;
    a.download = 'wedding-portal-qr.png';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl p-6 border border-slate-200 dark:border-slate-700 shadow-sm">
      <div className="flex items-center gap-3 mb-3">
        <QrCode className="w-5 h-5 text-indigo-500" />
        <h3 className="font-medium text-slate-900 dark:text-white">Portal QR code</h3>
      </div>
      <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">Share quick access to your wedding portal with guests.</p>

      {qrUrl ? (
        <div className="text-center">
          <img src={qrUrl} alt="Wedding portal QR code" width={160} height={160} className="mx-auto rounded-lg border border-slate-200 dark:border-slate-700" />
          <button onClick={downloadQR} className="flex items-center gap-1.5 mx-auto mt-3 text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:opacity-70 transition-opacity" aria-label="Download QR code as PNG">
            <Download className="w-3.5 h-3.5" /> Download PNG
          </button>
        </div>
      ) : (
        <button
          onClick={generateQR}
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 border border-slate-200 dark:border-slate-600 rounded-lg text-sm text-slate-700 dark:text-white font-medium transition-colors disabled:opacity-50"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <QrCode className="w-4 h-4" />}
          Generate QR code
        </button>
      )}
    </div>
  );
}

function PushNotificationWidget() {
  const [pushStatus, setPushStatus] = useState<'loading' | 'unsupported' | 'denied' | 'subscribed' | 'unsubscribed'>('loading');
  const [subscribing, setSubscribing] = useState(false);

  useEffect(() => { checkStatus(); }, []);

  const checkStatus = async () => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) { setPushStatus('unsupported'); return; }
    if (Notification.permission === 'denied') { setPushStatus('denied'); return; }

    try {
      const token = localStorage.getItem('couple_token');
      const res = await fetch(`${getApiBaseUrl()}/couple/portal/push/status`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const data = await res.json();
        setPushStatus(!data.enabled ? 'unsupported' : data.subscribed ? 'subscribed' : 'unsubscribed');
      } else {
        setPushStatus('unsubscribed');
      }
    } catch { setPushStatus('unsubscribed'); }
  };

  const handleSubscribe = async () => {
    setSubscribing(true);
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') { setPushStatus('denied'); toast.error('Notification permission denied'); return; }

      const token = localStorage.getItem('couple_token');
      const keyRes = await fetch(`${getApiBaseUrl()}/web-push/vapid-public-key`);
      if (!keyRes.ok) throw new Error('Push not configured');
      const { vapid_public_key } = await keyRes.json();

      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: vapid_public_key });

      const subRes = await fetch(`${getApiBaseUrl()}/couple/portal/push/subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ subscription: subscription.toJSON() }),
      });
      if (!subRes.ok) throw new Error('Failed to save subscription');

      setPushStatus('subscribed');
      toast.success('Push notifications enabled');
    } catch (e: any) {
      toast.error(e.message || 'Could not enable notifications');
    } finally { setSubscribing(false); }
  };

  const handleUnsubscribe = async () => {
    setSubscribing(true);
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        const token = localStorage.getItem('couple_token');
        await fetch(`${getApiBaseUrl()}/couple/portal/push/unsubscribe`, {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ endpoint: subscription.endpoint }),
        });
        await subscription.unsubscribe();
      }
      setPushStatus('unsubscribed');
      toast.success('Push notifications disabled');
    } catch { toast.error('Could not disable notifications'); }
    finally { setSubscribing(false); }
  };

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl p-6 border border-slate-200 dark:border-slate-700 shadow-sm">
      <div className="flex items-center gap-3 mb-3">
        {pushStatus === 'subscribed' ? <BellRing className="w-5 h-5 text-green-500" /> : <BellOff className="w-5 h-5 text-slate-400 dark:text-slate-500" />}
        <h3 className="font-medium text-slate-900 dark:text-white">Push notifications</h3>
      </div>
      <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">Get notified about updates, messages, and important dates.</p>

      {pushStatus === 'loading' && <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400"><Loader2 className="w-4 h-4 animate-spin" /> Checking...</div>}
      {pushStatus === 'unsupported' && <p className="text-xs text-slate-500 dark:text-slate-400">Push notifications aren&apos;t available in this browser.</p>}
      {pushStatus === 'denied' && <p className="text-xs text-amber-600 dark:text-amber-400">Notifications are blocked. Enable them in your browser settings to receive updates.</p>}

      {pushStatus === 'subscribed' && (
        <div>
          <div className="flex items-center gap-2 text-xs text-green-600 dark:text-green-400 mb-3"><CheckCircle className="w-3.5 h-3.5" /> Notifications active</div>
          <button onClick={handleUnsubscribe} disabled={subscribing} className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-red-100 dark:bg-red-950/30 hover:bg-red-200 dark:hover:bg-red-900/50 text-red-700 dark:text-red-400 text-xs font-medium rounded-lg transition-colors disabled:opacity-50">
            {subscribing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <BellOff className="w-3.5 h-3.5" />}
            Turn off notifications
          </button>
        </div>
      )}

      {pushStatus === 'unsubscribed' && (
        <button onClick={handleSubscribe} disabled={subscribing} className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50">
          {subscribing ? <Loader2 className="w-4 h-4 animate-spin" /> : <BellRing className="w-4 h-4" />}
          Turn on notifications
        </button>
      )}
    </div>
  );
}
