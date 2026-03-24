'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import PageHeader from '../components/PageHeader';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import {
  Users, Mail, Clock, CheckCircle, XCircle, Send, RefreshCw,
  ChevronDown, ChevronUp, MessageSquare, Eye, CheckCheck,
  Plus, GripVertical, Trash2, Pencil, Save, X, Loader2,
  ListOrdered, StickyNote, ShieldOff, ShieldCheck, AlertCircle,
  MessageCircle, Bell, Archive, FileText, Copy, Calendar, Repeat
} from 'lucide-react';

// ============================================================================
// TYPES
// ============================================================================

interface CoupleUser {
  id: string;
  email: string;
  partner1_name?: string;
  partner2_name?: string;
  wedding_id: string;
  is_active: boolean;
  setup_completed: boolean;
  last_login?: string;
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

interface EventNote {
  id: string;
  author_role: 'planner' | 'couple';
  author_name?: string;
  text: string;
  status: 'pending' | 'seen' | 'addressed';
  reply_to?: string;
  created_at?: string;
}

interface WeddingEvent {
  type: string;
  date: string;
  details?: {
    venue_name?: string;
    location?: string;
    time?: string;
    attire?: string;
  };
  order_of_events: OrderItem[];
  event_notes: EventNote[];
}

interface WeddingOption {
  id: string;
  couple_names: string;
  date: string;
}

// ============================================================================
// COMPONENT
// ============================================================================

export default function CouplePortalManagementPage() {
  const { token, apiRequest } = useAdmin();
  const [couples, setCouples] = useState<CoupleUser[]>([]);
  const [weddings, setWeddings] = useState<WeddingOption[]>([]);
  const [selectedWeddingId, setSelectedWeddingId] = useState<string>('');
  const [events, setEvents] = useState<WeddingEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState<'couples' | 'program' | 'notes' | 'messages' | 'templates' | 'meetings'>('couples');

  // Invite form
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [invitePartner1, setInvitePartner1] = useState('');
  const [invitePartner2, setInvitePartner2] = useState('');
  const [inviting, setInviting] = useState(false);

  // Fetch weddings for selector
  const fetchWeddings = useCallback(async () => {
    try {
      const res = await fetch(`${getApiBaseUrl()}/weddings`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        const list = (data.weddings || data || []).map((w: any) => ({
          id: w.id || w._id,
          couple_names: w.couple_names,
          date: w.date,
        }));
        setWeddings(list);
        if (list.length > 0 && !selectedWeddingId) {
          setSelectedWeddingId(list[0].id);
        }
      }
    } catch (err) {
      console.error('Failed to fetch weddings', err);
    }
  }, [token]);

  // Fetch couples
  const fetchCouples = useCallback(async () => {
    if (!token) return;
    try {
      const url = selectedWeddingId
        ? `${getApiBaseUrl()}/admin/couple-portal/couples?wedding_id=${selectedWeddingId}`
        : `${getApiBaseUrl()}/admin/couple-portal/couples`;
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setCouples(data.couples || []);
      }
    } catch (err) {
      console.error('Failed to fetch couples', err);
    }
  }, [token, selectedWeddingId]);

  // Fetch events for the selected wedding (for program management)
  const fetchEvents = useCallback(async () => {
    if (!selectedWeddingId || !token) return;
    try {
      const res = await fetch(`${getApiBaseUrl()}/weddings/${selectedWeddingId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const wedding = await res.json();
        setEvents(wedding.events || []);
      }
    } catch (err) {
      console.error('Failed to fetch events', err);
    }
  }, [token, selectedWeddingId]);

  useEffect(() => {
    fetchWeddings().then(() => setLoading(false));
  }, [fetchWeddings]);

  useEffect(() => {
    if (selectedWeddingId) {
      fetchCouples();
      fetchEvents();
    }
  }, [selectedWeddingId, fetchCouples, fetchEvents]);

  // Invite couple
  const handleInvite = async () => {
    if (!inviteEmail || !invitePartner1 || !selectedWeddingId) {
      toast.error('Please fill in the required fields');
      return;
    }
    setInviting(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/admin/couple-portal/invite`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: inviteEmail,
          partner1_name: invitePartner1,
          partner2_name: invitePartner2 || undefined,
          wedding_id: selectedWeddingId,
        }),
      });
      if (res.ok) {
        toast.success('Invitation sent!');
        setShowInviteForm(false);
        setInviteEmail('');
        setInvitePartner1('');
        setInvitePartner2('');
        fetchCouples();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to send invitation');
      }
    } catch {
      toast.error('Failed to connect to server');
    } finally {
      setInviting(false);
    }
  };

  // Revoke/Restore access
  const handleToggleAccess = async (coupleId: string, isActive: boolean) => {
    const action = isActive ? 'revoke' : 'restore';
    try {
      const res = await fetch(`${getApiBaseUrl()}/couple-portal/couples/${coupleId}/${action}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      });
      if (res.ok) {
        toast.success(`Access ${action}d`);
        fetchCouples();
      } else {
        const err = await res.json();
        toast.error(err.detail || `Failed to ${action} access`);
      }
    } catch {
      toast.error('Failed to connect');
    }
  };

  // Resend invite
  const handleResend = async (coupleId: string) => {
    try {
      const res = await fetch(`${getApiBaseUrl()}/admin/couple-portal/resend-invite`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ couple_id: coupleId }),
      });
      if (res.ok) {
        toast.success('Invitation resent');
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to resend');
      }
    } catch {
      toast.error('Failed to connect');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  const sectionTabs = [
    { key: 'couples' as const, label: 'Couples', icon: <Users className="w-4 h-4" /> },
    { key: 'program' as const, label: 'Program / Run of Show', icon: <ListOrdered className="w-4 h-4" /> },
    { key: 'notes' as const, label: 'Couple Notes', icon: <StickyNote className="w-4 h-4" /> },
    { key: 'messages' as const, label: 'Messages', icon: <MessageCircle className="w-4 h-4" /> },
    { key: 'templates' as const, label: 'Form Templates', icon: <Copy className="w-4 h-4" /> },
    { key: 'meetings' as const, label: 'Meetings', icon: <Calendar className="w-4 h-4" /> },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Couple Portal"
        description="Manage couple access, program details, and collaborative notes"
      />

      {/* Wedding Selector + Archive */}
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex flex-col sm:flex-row gap-4 items-center">
          <label className="font-medium text-slate-700 dark:text-gray-200 whitespace-nowrap">
            Select Wedding:
          </label>
          <select
            value={selectedWeddingId}
            onChange={(e) => setSelectedWeddingId(e.target.value)}
            className="flex-1 px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
          >
            <option value="">Choose a wedding...</option>
            {weddings.map((w) => (
              <option key={w.id} value={w.id}>{w.couple_names} — {w.date}</option>
            ))}
          </select>
          {selectedWeddingId && (
            <ArchiveButton weddingId={selectedWeddingId} token={token || ''} onArchived={() => { fetchCouples(); fetchEvents(); }} />
          )}
        </div>
      </div>

      {/* Section Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200 dark:border-gray-700">
        {sectionTabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveSection(tab.key)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeSection === tab.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Section Content */}
      {activeSection === 'couples' && (
        <CouplesSection
          couples={couples}
          onInvite={() => setShowInviteForm(true)}
          onResend={handleResend}
          onToggleAccess={handleToggleAccess}
        />
      )}

      {activeSection === 'program' && (
        <ProgramSection
          events={events}
          weddingId={selectedWeddingId}
          token={token || ''}
          onRefresh={fetchEvents}
        />
      )}

      {activeSection === 'notes' && (
        <NotesSection
          events={events}
          weddingId={selectedWeddingId}
          token={token || ''}
          onRefresh={fetchEvents}
        />
      )}

      {activeSection === 'messages' && (
        <PlannerMessagesSection
          weddingId={selectedWeddingId}
          token={token || ''}
        />
      )}

      {activeSection === 'templates' && (
        <FormTemplatesSection
          weddingId={selectedWeddingId}
          token={token || ''}
        />
      )}

      {activeSection === 'meetings' && (
        <MeetingsSection
          weddingId={selectedWeddingId}
          token={token || ''}
        />
      )}

      {/* Invite Modal */}
      {showInviteForm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-md p-6">
            <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4">Invite Couple</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Email *</label>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200"
                  placeholder="couple@email.com"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Partner 1 Name *</label>
                <input
                  type="text"
                  value={invitePartner1}
                  onChange={(e) => setInvitePartner1(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Partner 2 Name</label>
                <input
                  type="text"
                  value={invitePartner2}
                  onChange={(e) => setInvitePartner2(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowInviteForm(false)}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={handleInvite}
                disabled={inviting}
                className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                {inviting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                Send Invitation
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


// ============================================================================
// COUPLES SECTION
// ============================================================================

function CouplesSection({
  couples,
  onInvite,
  onResend,
  onToggleAccess,
}: {
  couples: CoupleUser[];
  onInvite: () => void;
  onResend: (id: string) => void;
  onToggleAccess: (id: string, isActive: boolean) => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-200">Couple Accounts</h2>
        <button
          onClick={onInvite}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" />
          Invite Couple
        </button>
      </div>

      {couples.length === 0 ? (
        <div className="text-center py-12 text-gray-400 dark:text-gray-500">
          <Users className="w-10 h-10 mx-auto mb-3 opacity-50" />
          <p>No couples invited yet</p>
          <p className="text-sm mt-1">Click "Invite Couple" to get started</p>
        </div>
      ) : (
        <div className="space-y-3">
          {couples.map((couple) => (
            <div key={couple.id} className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-medium ${
                  couple.is_active ? 'bg-green-500' : couple.setup_completed ? 'bg-red-400' : 'bg-amber-400'
                }`}>
                  {(couple.partner1_name || 'C').charAt(0)}
                </div>
                <div>
                  <p className="font-medium text-gray-800 dark:text-gray-200 text-sm">
                    {couple.partner1_name}{couple.partner2_name ? ` & ${couple.partner2_name}` : ''}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{couple.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2 py-1 rounded-full ${
                  couple.is_active
                    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                    : couple.setup_completed
                    ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                    : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                }`}>
                  {couple.is_active ? 'Active' : couple.setup_completed ? 'Revoked' : 'Pending Setup'}
                </span>

                {!couple.setup_completed && (
                  <button
                    onClick={() => onResend(couple.id)}
                    className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                    title="Resend invitation"
                  >
                    <RefreshCw className="w-3 h-3" />
                    Resend
                  </button>
                )}

                {couple.setup_completed && (
                  <button
                    onClick={() => onToggleAccess(couple.id, couple.is_active)}
                    className={`text-xs flex items-center gap-1 ${
                      couple.is_active ? 'text-red-600 hover:text-red-700' : 'text-green-600 hover:text-green-700'
                    }`}
                  >
                    {couple.is_active ? (
                      <><ShieldOff className="w-3 h-3" /> Revoke</>
                    ) : (
                      <><ShieldCheck className="w-3 h-3" /> Restore</>
                    )}
                  </button>
                )}

                {couple.last_login && (
                  <span className="text-xs text-gray-400 dark:text-gray-500" title="Last login">
                    {new Date(couple.last_login).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ============================================================================
// PROGRAM / ORDER OF EVENTS SECTION (Planner CRUD)
// ============================================================================

function ProgramSection({
  events,
  weddingId,
  token,
  onRefresh,
}: {
  events: WeddingEvent[];
  weddingId: string;
  token: string;
  onRefresh: () => void;
}) {
  const [expandedEvent, setExpandedEvent] = useState<number | null>(events.length > 0 ? 0 : null);
  const [addingToEvent, setAddingToEvent] = useState<number | null>(null);
  const [editingItem, setEditingItem] = useState<string | null>(null);

  // Add item form state
  const [newTitle, setNewTitle] = useState('');
  const [newTime, setNewTime] = useState('');
  const [newDuration, setNewDuration] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [saving, setSaving] = useState(false);

  const eventTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      traditional: 'Traditional Ceremony',
      white_wedding: 'White Wedding',
      reception: 'Reception',
      engagement: 'Engagement Party',
      rehearsal: 'Rehearsal Dinner',
    };
    return labels[type] || type.charAt(0).toUpperCase() + type.slice(1).replace(/_/g, ' ');
  };

  const handleAddItem = async (eventIndex: number) => {
    if (!newTitle.trim()) {
      toast.error('Title is required');
      return;
    }
    setSaving(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/couple-portal/events/${eventIndex}/order-of-events`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          wedding_id: weddingId,
          title: newTitle.trim(),
          time: newTime || undefined,
          duration_minutes: newDuration ? parseInt(newDuration) : undefined,
          description: newDescription || undefined,
        }),
      });
      if (res.ok) {
        toast.success('Item added');
        setAddingToEvent(null);
        setNewTitle('');
        setNewTime('');
        setNewDuration('');
        setNewDescription('');
        onRefresh();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to add item');
      }
    } catch {
      toast.error('Failed to connect');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteItem = async (eventIndex: number, itemId: string) => {
    try {
      const res = await fetch(
        `${getApiBaseUrl()}/couple-portal/events/${eventIndex}/order-of-events/${itemId}?wedding_id=${weddingId}`,
        {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (res.ok) {
        toast.success('Item removed');
        onRefresh();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to delete');
      }
    } catch {
      toast.error('Failed to connect');
    }
  };

  if (events.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400 dark:text-gray-500">
        <ListOrdered className="w-10 h-10 mx-auto mb-3 opacity-50" />
        <p>No events in this wedding yet</p>
        <p className="text-sm mt-1">Add events to the wedding first, then manage the run of show here</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
        Build the detailed run of show for each ceremony. Couples will see this in their portal and can leave notes.
      </p>

      {events.map((event, eventIdx) => (
        <div key={eventIdx} className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          {/* Event Header */}
          <button
            onClick={() => setExpandedEvent(expandedEvent === eventIdx ? null : eventIdx)}
            className="w-full flex items-center justify-between px-5 py-3 hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors"
          >
            <div className="flex items-center gap-3">
              <ListOrdered className="w-5 h-5 text-blue-500" />
              <div className="text-left">
                <p className="font-medium text-gray-800 dark:text-gray-200">{eventTypeLabel(event.type)}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {event.date} · {event.order_of_events?.length || 0} items
                </p>
              </div>
            </div>
            {expandedEvent === eventIdx ? <ChevronUp className="w-5 h-5 text-gray-400 dark:text-gray-500" /> : <ChevronDown className="w-5 h-5 text-gray-400 dark:text-gray-500" />}
          </button>

          {/* Expanded: Order of Events List */}
          {expandedEvent === eventIdx && (
            <div className="border-t border-gray-100 dark:border-gray-700 px-5 py-4">
              {(event.order_of_events || []).length === 0 ? (
                <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-4">No program items yet</p>
              ) : (
                <div className="space-y-2 mb-4">
                  {(event.order_of_events || [])
                    .sort((a, b) => a.order - b.order)
                    .map((item) => (
                      <div
                        key={item.id}
                        className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-slate-700/50 rounded-lg group"
                      >
                        <GripVertical className="w-4 h-4 text-gray-300 dark:text-gray-600 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="font-medium text-gray-800 dark:text-gray-200 text-sm">{item.title}</p>
                            {item.time && (
                              <span className="text-xs text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-1.5 py-0.5 rounded">
                                {item.time}
                              </span>
                            )}
                            {item.duration_minutes && (
                              <span className="text-xs text-gray-400 dark:text-gray-500">{item.duration_minutes}min</span>
                            )}
                          </div>
                          {item.description && (
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{item.description}</p>
                          )}
                          {item.notes.length > 0 && (
                            <div className="flex items-center gap-1 mt-1">
                              <MessageSquare className="w-3 h-3 text-amber-500" />
                              <span className="text-xs text-amber-600">
                                {item.notes.length} note{item.notes.length > 1 ? 's' : ''}
                              </span>
                            </div>
                          )}
                        </div>
                        <button
                          onClick={() => handleDeleteItem(eventIdx, item.id)}
                          className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600 transition-opacity"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                </div>
              )}

              {/* Add Item Form */}
              {addingToEvent === eventIdx ? (
                <div className="border border-blue-200 dark:border-blue-700 rounded-lg p-4 bg-blue-50/50 dark:bg-blue-900/20">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="col-span-2">
                      <input
                        type="text"
                        placeholder="Title (e.g. First Dance)"
                        value={newTitle}
                        onChange={(e) => setNewTitle(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200"
                        autoFocus
                      />
                    </div>
                    <input
                      type="text"
                      placeholder="Time (e.g. 6:30 PM)"
                      value={newTime}
                      onChange={(e) => setNewTime(e.target.value)}
                      className="px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200"
                    />
                    <input
                      type="number"
                      placeholder="Duration (min)"
                      value={newDuration}
                      onChange={(e) => setNewDuration(e.target.value)}
                      className="px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200"
                      min="1"
                    />
                    <div className="col-span-2">
                      <textarea
                        placeholder="Description (optional)"
                        value={newDescription}
                        onChange={(e) => setNewDescription(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm resize-none bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200"
                        rows={2}
                      />
                    </div>
                  </div>
                  <div className="flex justify-end gap-2 mt-3">
                    <button
                      onClick={() => setAddingToEvent(null)}
                      className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleAddItem(eventIdx)}
                      disabled={saving}
                      className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1"
                    >
                      {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                      Add
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setAddingToEvent(eventIdx)}
                  className="w-full py-2 border border-dashed border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-500 dark:text-gray-400 hover:border-blue-400 hover:text-blue-600 dark:hover:border-blue-500 dark:hover:text-blue-400 transition-colors flex items-center justify-center gap-1"
                >
                  <Plus className="w-4 h-4" />
                  Add Program Item
                </button>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}


// ============================================================================
// NOTES SECTION (Planner views and manages couple notes)
// ============================================================================

function NotesSection({
  events,
  weddingId,
  token,
  onRefresh,
}: {
  events: WeddingEvent[];
  weddingId: string;
  token: string;
  onRefresh: () => void;
}) {
  const [replyTarget, setReplyTarget] = useState<string | null>(null);
  const [replyText, setReplyText] = useState('');
  const [submittingReply, setSubmittingReply] = useState(false);

  // Collect all notes across all events and items
  type NoteEntry = {
    note: EventNote;
    context: string;
    eventIndex: number;
    itemId?: string;
    noteId: string;
  };
  const allNotes: NoteEntry[] = [];

  events.forEach((event, eventIdx) => {
    const eventLabel = {
      traditional: 'Traditional Ceremony',
      white_wedding: 'White Wedding',
      reception: 'Reception',
      engagement: 'Engagement Party',
      rehearsal: 'Rehearsal Dinner',
    }[event.type] || event.type;

    // Event-level notes
    (event.event_notes || []).forEach((note) => {
      allNotes.push({
        note,
        context: eventLabel,
        eventIndex: eventIdx,
        noteId: note.id,
      });
    });

    // Item-level notes
    (event.order_of_events || []).forEach((item) => {
      (item.notes || []).forEach((note) => {
        allNotes.push({
          note,
          context: `${eventLabel} → ${item.title}`,
          eventIndex: eventIdx,
          itemId: item.id,
          noteId: note.id,
        });
      });
    });
  });

  // Separate parent notes (no reply_to) from replies
  const parentNotes = allNotes.filter(n => !n.note.reply_to);
  const replyNotes = allNotes.filter(n => !!n.note.reply_to);

  // Build a map of parent note ID -> replies
  const repliesMap: Record<string, NoteEntry[]> = {};
  replyNotes.forEach(entry => {
    const parentId = entry.note.reply_to;
    if (!parentId) return;
    if (!repliesMap[parentId]) repliesMap[parentId] = [];
    repliesMap[parentId].push(entry);
  });
  // Sort replies by date ascending (oldest first = conversation order)
  Object.values(repliesMap).forEach(replies => {
    replies.sort((a, b) => (a.note.created_at || '').localeCompare(b.note.created_at || ''));
  });

  // Sort parents: pending first, then by date (newest first)
  parentNotes.sort((a, b) => {
    if (a.note.status === 'pending' && b.note.status !== 'pending') return -1;
    if (a.note.status !== 'pending' && b.note.status === 'pending') return 1;
    return (b.note.created_at || '').localeCompare(a.note.created_at || '');
  });

  const handleStatusUpdate = async (
    eventIndex: number,
    noteId: string,
    newStatus: 'seen' | 'addressed',
    itemId?: string,
  ) => {
    const url = itemId
      ? `${getApiBaseUrl()}/couple-portal/events/${eventIndex}/order-of-events/${itemId}/notes/${noteId}`
      : `${getApiBaseUrl()}/couple-portal/events/${eventIndex}/notes/${noteId}`;

    try {
      const res = await fetch(url, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ wedding_id: weddingId, status: newStatus }),
      });
      if (res.ok) {
        toast.success(`Note marked as ${newStatus}`);
        onRefresh();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to update');
      }
    } catch {
      toast.error('Failed to connect');
    }
  };

  const handleReply = async (eventIndex: number, noteId: string, itemId?: string) => {
    if (!replyText.trim()) return;
    setSubmittingReply(true);
    const url = itemId
      ? `${getApiBaseUrl()}/couple-portal/events/${eventIndex}/order-of-events/${itemId}/notes/${noteId}/reply`
      : `${getApiBaseUrl()}/couple-portal/events/${eventIndex}/notes/${noteId}/reply`;

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ wedding_id: weddingId, text: replyText.trim() }),
      });
      if (res.ok) {
        toast.success('Reply sent');
        setReplyTarget(null);
        setReplyText('');
        onRefresh();
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || 'Failed to send reply');
      }
    } catch {
      toast.error('Failed to connect');
    } finally {
      setSubmittingReply(false);
    }
  };

  const statusIcon = (status: string) => {
    switch (status) {
      case 'pending': return <AlertCircle className="w-4 h-4 text-amber-500" />;
      case 'seen': return <Eye className="w-4 h-4 text-blue-500" />;
      case 'addressed': return <CheckCheck className="w-4 h-4 text-green-500" />;
      default: return null;
    }
  };

  const statusBadge = (status: string) => {
    const styles: Record<string, string> = {
      pending: 'bg-amber-100 text-amber-700',
      seen: 'bg-blue-100 text-blue-700',
      addressed: 'bg-green-100 text-green-700',
    };
    return styles[status] || 'bg-gray-100 text-gray-600';
  };

  const pendingCount = parentNotes.filter(n => n.note.status === 'pending').length;

  if (parentNotes.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400">
        <StickyNote className="w-10 h-10 mx-auto mb-3 opacity-50" />
        <p>No notes from the couple yet</p>
        <p className="text-sm mt-1">Notes will appear here when the couple adds feedback to the program</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-200">
          Couple Notes
          {pendingCount > 0 && (
            <span className="ml-2 text-sm font-normal text-amber-600 dark:text-amber-400">
              ({pendingCount} pending)
            </span>
          )}
        </h2>
      </div>

      <div className="space-y-3">
        {parentNotes.map(({ note, context, eventIndex, itemId, noteId }) => {
          const replies = repliesMap[noteId] || [];
          const isReplyOpen = replyTarget === noteId;

          return (
            <div
              key={noteId}
              className={`bg-white dark:bg-slate-800 rounded-xl shadow-sm border p-4 ${
                note.status === 'pending' ? 'border-amber-200 dark:border-amber-700' : 'border-gray-200 dark:border-gray-700'
              }`}
            >
              {/* Parent note */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    {statusIcon(note.status)}
                    <span className="text-xs text-gray-500 dark:text-gray-400">{context}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded-full ${statusBadge(note.status)}`}>
                      {note.status}
                    </span>
                  </div>
                  <p className="text-sm text-gray-800 dark:text-gray-200">{note.text}</p>
                  <div className="flex items-center gap-2 mt-2 text-xs text-gray-400 dark:text-gray-500">
                    <span>{note.author_name || note.author_role}</span>
                    {note.created_at && (
                      <span>· {new Date(note.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span>
                    )}
                  </div>
                </div>

                <div className="flex gap-1 flex-shrink-0">
                  {/* Status actions */}
                  {note.status !== 'addressed' && (
                    <>
                      {note.status === 'pending' && (
                        <button
                          onClick={() => handleStatusUpdate(eventIndex, noteId, 'seen', itemId)}
                          className="p-1.5 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
                          title="Mark as seen"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                      )}
                      <button
                        onClick={() => handleStatusUpdate(eventIndex, noteId, 'addressed', itemId)}
                        className="p-1.5 text-green-500 hover:bg-green-50 dark:hover:bg-green-900/30 rounded-lg transition-colors"
                        title="Mark as addressed"
                      >
                        <CheckCheck className="w-4 h-4" />
                      </button>
                    </>
                  )}
                  {/* Reply button */}
                  <button
                    onClick={() => { setReplyTarget(isReplyOpen ? null : noteId); setReplyText(''); }}
                    className={`p-1.5 rounded-lg transition-colors ${
                      isReplyOpen ? 'text-[#1e3a5f] bg-blue-50 dark:bg-blue-900/30' : 'text-gray-400 hover:bg-gray-50 dark:hover:bg-slate-700 hover:text-gray-600 dark:hover:text-gray-300'
                    }`}
                    title="Reply to note"
                  >
                    <MessageCircle className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Threaded replies */}
              {replies.length > 0 && (
                <div className="mt-3 ml-4 border-l-2 border-blue-100 dark:border-blue-800 pl-3 space-y-2">
                  {replies.map(({ note: reply }) => (
                    <div key={reply.id} className="bg-blue-50/50 dark:bg-blue-900/20 rounded-lg p-2.5">
                      <p className="text-sm text-gray-700 dark:text-gray-300">{reply.text}</p>
                      <div className="flex items-center gap-2 mt-1.5 text-xs text-gray-400 dark:text-gray-500">
                        <span className="text-[#1e3a5f] dark:text-blue-400 font-medium">Planner</span>
                        {reply.created_at && (
                          <span>· {new Date(reply.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Reply input */}
              {isReplyOpen && (
                <div className="mt-3 ml-4 border-l-2 border-blue-200 dark:border-blue-700 pl-3">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={replyText}
                      onChange={(e) => setReplyText(e.target.value)}
                      placeholder="Type your reply..."
                      className="flex-1 px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:border-[#1e3a5f] bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200"
                      autoFocus
                      onKeyDown={(e) => e.key === 'Enter' && !submittingReply && handleReply(eventIndex, noteId, itemId)}
                    />
                    <button
                      onClick={() => handleReply(eventIndex, noteId, itemId)}
                      disabled={submittingReply || !replyText.trim()}
                      className="px-3 py-2 bg-[#1e3a5f] text-white rounded-lg text-sm disabled:opacity-50 flex items-center gap-1"
                    >
                      {submittingReply ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={() => { setReplyTarget(null); setReplyText(''); }}
                      className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-400 text-sm"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}


// ============================================================================
// PLANNER MESSAGES SECTION (Sprint 3)
// ============================================================================

interface PlannerMessageItem {
  id: string;
  sender_role: 'couple' | 'planner';
  sender_name: string;
  content: string;
  read_by_couple: boolean;
  created_at?: string;
}

function PlannerMessagesSection({ weddingId, token }: { weddingId: string; token: string }) {
  const [messages, setMessages] = useState<PlannerMessageItem[]>([]);
  const [msgLoading, setMsgLoading] = useState(true);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [sendingDigest, setSendingDigest] = useState(false);

  const fetchMessages = useCallback(async () => {
    if (!weddingId || !token) return;
    try {
      const res = await fetch(`${getApiBaseUrl()}/couple-portal/messages?wedding_id=${weddingId}&limit=100`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
      }
    } catch {
      toast.error('Failed to load messages');
    } finally {
      setMsgLoading(false);
    }
  }, [weddingId, token]);

  useEffect(() => {
    setMsgLoading(true);
    fetchMessages();
  }, [fetchMessages]);

  const handleSend = async () => {
    if (!newMessage.trim() || sending) return;
    setSending(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/couple-portal/messages`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ wedding_id: weddingId, content: newMessage.trim() }),
      });
      if (res.ok) {
        setNewMessage('');
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

  const handleSendDigest = async () => {
    setSendingDigest(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/couple-portal/send-digest?wedding_id=${weddingId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (res.ok) {
        if (data.sent) {
          toast.success('Digest email sent to the couple');
        } else {
          toast.info(data.message || 'No new activity to report');
        }
      } else {
        toast.error(data.detail || 'Failed to send digest');
      }
    } catch {
      toast.error('Failed to send digest');
    } finally {
      setSendingDigest(false);
    }
  };

  if (msgLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Send Digest Button */}
      <div className="flex justify-end">
        <button
          onClick={handleSendDigest}
          disabled={sendingDigest}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-700 rounded-lg hover:bg-amber-100 dark:hover:bg-amber-900/50 transition-colors disabled:opacity-50"
        >
          {sendingDigest ? <Loader2 className="w-4 h-4 animate-spin" /> : <Bell className="w-4 h-4" />}
          Send Digest Email
        </button>
      </div>

      {/* Chat container */}
      <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm flex flex-col" style={{ height: '55vh', minHeight: '350px' }}>
        {/* Messages area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 dark:text-gray-500">
              <MessageCircle className="w-12 h-12 mb-3 opacity-50" />
              <p className="text-sm">No messages yet</p>
              <p className="text-xs mt-1">Start a conversation with your couple</p>
            </div>
          ) : (
            messages.map((msg) => {
              const isPlanner = msg.sender_role === 'planner';
              return (
                <div key={msg.id} className={`flex ${isPlanner ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${
                    isPlanner
                      ? 'bg-blue-600 text-white rounded-br-md'
                      : 'bg-gray-100 dark:bg-slate-700 text-gray-800 dark:text-gray-200 rounded-bl-md'
                  }`}>
                    {!isPlanner && (
                      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{msg.sender_name}</p>
                    )}
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    <div className={`flex items-center gap-1.5 mt-1 ${isPlanner ? 'justify-end' : ''}`}>
                      <span className={`text-xs ${isPlanner ? 'text-white/50' : 'text-gray-400 dark:text-gray-500'}`}>
                        {msg.created_at ? new Date(msg.created_at).toLocaleTimeString('en-US', {
                          hour: 'numeric', minute: '2-digit', hour12: true,
                        }) : ''}
                      </span>
                      {isPlanner && msg.read_by_couple && (
                        <Eye className="w-3 h-3 text-white/50" />
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Input area */}
        <div className="border-t border-gray-200 dark:border-gray-700 p-3 flex gap-2">
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
            placeholder="Type a message to the couple..."
            className="flex-1 px-4 py-2.5 border border-gray-200 dark:border-gray-600 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200"
            disabled={sending}
          />
          <button
            onClick={handleSend}
            disabled={!newMessage.trim() || sending}
            className="w-10 h-10 flex items-center justify-center bg-blue-600 text-white rounded-full hover:bg-blue-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}


// ============================================================================
// ARCHIVE BUTTON (Sprint 4)
// ============================================================================

function ArchiveButton({ weddingId, token, onArchived }: { weddingId: string; token: string; onArchived: () => void }) {
  const [archiving, setArchiving] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const handleArchive = async () => {
    setArchiving(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/couple-portal/archive?wedding_id=${weddingId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        toast.success('Wedding archived successfully');
        setShowConfirm(false);
        onArchived();
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || 'Failed to archive wedding');
      }
    } catch {
      toast.error('Failed to connect to server');
    } finally {
      setArchiving(false);
    }
  };

  return (
    <>
      <button
        onClick={() => setShowConfirm(true)}
        className="flex items-center gap-2 px-3 py-2 text-sm text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-700 rounded-lg hover:bg-amber-100 dark:hover:bg-amber-900/50 transition-colors"
      >
        <Archive className="w-4 h-4" />
        Archive Wedding
      </button>

      {showConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-amber-50 dark:bg-amber-900/30 flex items-center justify-center">
                <Archive className="w-5 h-5 text-amber-600 dark:text-amber-400" />
              </div>
              <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200">Archive This Wedding?</h3>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
              Archiving will snapshot all wedding data (guests, contracts, forms, messages) and mark the couple portal as read-only.
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
              The couple can still log in and view their archived details, but won&apos;t be able to send messages, submit forms, or add notes.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={handleArchive}
                disabled={archiving}
                className="px-4 py-2 text-sm text-white bg-amber-600 rounded-lg hover:bg-amber-700 disabled:opacity-50 flex items-center gap-2"
              >
                {archiving && <Loader2 className="w-4 h-4 animate-spin" />}
                Archive Wedding
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}


// ============================================================================
// FORM TEMPLATES SECTION (Sprint 4)
// ============================================================================

interface CustomTemplate {
  id: string;
  name: string;
  description?: string;
  category?: string;
  field_count: number;
  created_at?: string;
}

function FormTemplatesSection({ weddingId, token }: { weddingId: string; token: string }) {
  const [templates, setTemplates] = useState<CustomTemplate[]>([]);
  const [tplLoading, setTplLoading] = useState(true);
  const [creatingFrom, setCreatingFrom] = useState<string | null>(null);
  const [newFormName, setNewFormName] = useState('');

  const fetchTemplates = useCallback(async () => {
    try {
      const res = await fetch(`${getApiBaseUrl()}/couple-portal/form-templates`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setTemplates(data.templates || []);
      }
    } catch {
      toast.error('Failed to load templates');
    } finally {
      setTplLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const handleCreateFromTemplate = async (templateId: string) => {
    if (!newFormName.trim()) {
      toast.error('Please enter a form name');
      return;
    }
    try {
      const res = await fetch(`${getApiBaseUrl()}/couple-portal/form-templates/create-form`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          template_id: templateId,
          form_name: newFormName.trim(),
          wedding_id: weddingId,
        }),
      });
      if (res.ok) {
        toast.success(`Form "${newFormName.trim()}" created from template`);
        setCreatingFrom(null);
        setNewFormName('');
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to create form');
      }
    } catch {
      toast.error('Failed to connect');
    }
  };

  const handleDelete = async (templateId: string, templateName: string) => {
    if (!confirm(`Delete template "${templateName}"? This cannot be undone.`)) return;

    try {
      const res = await fetch(`${getApiBaseUrl()}/couple-portal/form-templates/${templateId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        toast.success('Template deleted');
        setTemplates(prev => prev.filter(t => t.id !== templateId));
      } else {
        toast.error('Failed to delete template');
      }
    } catch {
      toast.error('Failed to connect');
    }
  };

  if (tplLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-xl font-semibold text-gray-800 dark:text-gray-200">Custom Form Templates</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Save forms as reusable templates to quickly create new forms for any wedding.</p>
      </div>

      {templates.length === 0 ? (
        <div className="bg-white dark:bg-slate-800 border border-gray-200 dark:border-gray-700 rounded-xl p-8 text-center">
          <Copy className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-gray-400 text-sm">No custom templates yet</p>
          <p className="text-gray-400 dark:text-gray-500 text-xs mt-1">Save any form as a template from the Forms page to reuse it across weddings.</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {templates.map((tpl) => (
            <div key={tpl.id} className="bg-white dark:bg-slate-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h4 className="font-medium text-gray-800 dark:text-gray-200">{tpl.name}</h4>
                  {tpl.description && <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{tpl.description}</p>}
                  <div className="flex items-center gap-3 mt-2 text-xs text-gray-400 dark:text-gray-500">
                    <span>{tpl.field_count} fields</span>
                    {tpl.category && <span className="bg-gray-100 dark:bg-slate-700 px-2 py-0.5 rounded">{tpl.category}</span>}
                    {tpl.created_at && <span>{new Date(tpl.created_at).toLocaleDateString()}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2 ml-4">
                  <button
                    onClick={() => { setCreatingFrom(tpl.id); setNewFormName(''); }}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
                  >
                    <FileText className="w-3.5 h-3.5" />
                    Use Template
                  </button>
                  <button
                    onClick={() => handleDelete(tpl.id, tpl.name)}
                    className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-red-500 dark:hover:text-red-400 transition-colors"
                    title="Delete template"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {creatingFrom === tpl.id && (
                <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700 flex gap-2">
                  <input
                    type="text"
                    value={newFormName}
                    onChange={(e) => setNewFormName(e.target.value)}
                    placeholder="New form name..."
                    className="flex-1 px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200"
                    onKeyDown={(e) => { if (e.key === 'Enter') handleCreateFromTemplate(tpl.id); }}
                  />
                  <button
                    onClick={() => handleCreateFromTemplate(tpl.id)}
                    className="px-3 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700"
                  >
                    Create
                  </button>
                  <button
                    onClick={() => setCreatingFrom(null)}
                    className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700"
                  >
                    Cancel
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
// MEETINGS SECTION — Schedule meetings with couples
// ============================================================================

interface Meeting {
  id: string;
  title: string;
  description?: string;
  start_date: string;
  end_date?: string;
  is_recurring: boolean;
  recurrence_rule?: string;
  reminder_minutes?: number;
  synced_to_google: boolean;
  status: string;
}

function MeetingsSection({ weddingId, token }: { weddingId: string; token: string }) {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [startDate, setStartDate] = useState('');
  const [startTime, setStartTime] = useState('10:00');
  const [endTime, setEndTime] = useState('11:00');
  const [isRecurring, setIsRecurring] = useState(false);
  const [recurrencePreset, setRecurrencePreset] = useState('weekly');
  const [recurrenceCount, setRecurrenceCount] = useState(8);
  const [reminderMinutes, setReminderMinutes] = useState(30);
  const [syncToGoogle, setSyncToGoogle] = useState(true);

  const fetchMeetings = useCallback(async () => {
    try {
      const res = await fetch(
        `${getApiBaseUrl()}/couple-portal/meetings?wedding_id=${weddingId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        const data = await res.json();
        setMeetings(data.meetings || []);
      }
    } catch {
      toast.error('Failed to load meetings');
    } finally {
      setLoading(false);
    }
  }, [weddingId, token]);

  useEffect(() => {
    if (weddingId && token) fetchMeetings();
  }, [weddingId, token, fetchMeetings]);

  // Reset form state when wedding changes
  useEffect(() => {
    setShowForm(false);
    setTitle(''); setDescription(''); setStartDate('');
    setStartTime('10:00'); setEndTime('11:00');
    setIsRecurring(false); setRecurrencePreset('weekly');
    setRecurrenceCount(8); setReminderMinutes(30); setSyncToGoogle(true);
  }, [weddingId]);

  const buildRecurrenceRule = (): string | null => {
    if (!isRecurring) return null;
    const dayMap: Record<string, string> = {
      '0': 'SU', '1': 'MO', '2': 'TU', '3': 'WE', '4': 'TH', '5': 'FR', '6': 'SA',
    };
    const startDayOfWeek = startDate
      ? dayMap[new Date(startDate + 'T' + startTime).getDay().toString()] || 'MO'
      : 'MO';
    switch (recurrencePreset) {
      case 'weekly':
        return `FREQ=WEEKLY;BYDAY=${startDayOfWeek};COUNT=${recurrenceCount}`;
      case 'biweekly':
        return `FREQ=WEEKLY;INTERVAL=2;BYDAY=${startDayOfWeek};COUNT=${recurrenceCount}`;
      case 'monthly':
        return `FREQ=MONTHLY;COUNT=${recurrenceCount}`;
      default:
        return `FREQ=WEEKLY;BYDAY=${startDayOfWeek};COUNT=${recurrenceCount}`;
    }
  };

  const handleSchedule = async () => {
    if (!title.trim() || !startDate) {
      toast.error('Title and start date are required');
      return;
    }
    if (endTime <= startTime) {
      toast.error('End time must be after start time');
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/couple-portal/meetings`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          wedding_id: weddingId,
          title: title.trim(),
          description: description.trim() || null,
          start_date: `${startDate}T${startTime}:00`,
          end_date: `${startDate}T${endTime}:00`,
          is_recurring: isRecurring,
          recurrence_rule: buildRecurrenceRule(),
          reminder_minutes: reminderMinutes,
          sync_to_google: syncToGoogle,
        }),
      });
      if (res.ok) {
        toast.success('Meeting scheduled');
        setShowForm(false);
        setTitle(''); setDescription(''); setStartDate('');
        setStartTime('10:00'); setEndTime('11:00');
        setIsRecurring(false); setRecurrencePreset('weekly');
        setRecurrenceCount(8); setReminderMinutes(30); setSyncToGoogle(true);
        fetchMeetings();
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || 'Failed to schedule meeting');
      }
    } catch {
      toast.error('Failed to connect');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancelMeeting = async (meetingId: string) => {
    if (!confirm('Cancel this meeting?')) return;
    try {
      const res = await fetch(
        `${getApiBaseUrl()}/couple-portal/meetings/${meetingId}?wedding_id=${weddingId}`,
        { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        toast.success('Meeting cancelled');
        fetchMeetings();
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || 'Failed to cancel');
      }
    } catch {
      toast.error('Failed to connect');
    }
  };

  const fmtDate = (iso: string) => new Date(iso).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
  const fmtTime = (iso: string) => new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });

  if (loading) {
    return <div className="flex items-center justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-blue-500" /></div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-200">Meetings</h2>
        <button onClick={() => setShowForm(!showForm)} className="flex items-center gap-1.5 px-3 py-2 bg-[#1e3a5f] text-white rounded-lg text-sm hover:bg-[#2a4f7f] transition-colors">
          <Plus className="w-4 h-4" /> Schedule Meeting
        </button>
      </div>

      {showForm && (
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 mb-4 space-y-3">
          <div>
            <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Title *</label>
            <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g., Weekly Check-in" className="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:border-[#1e3a5f] bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200" />
          </div>
          <div>
            <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Description</label>
            <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Meeting agenda or notes..." className="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:border-[#1e3a5f] bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Date *</label>
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:border-[#1e3a5f] bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200" />
            </div>
            <div>
              <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Start Time</label>
              <input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} className="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:border-[#1e3a5f] bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200" />
            </div>
            <div>
              <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">End Time</label>
              <input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} className="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:border-[#1e3a5f] bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200" />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={isRecurring} onChange={(e) => setIsRecurring(e.target.checked)} className="rounded border-gray-300 dark:border-gray-600" />
              <span className="text-sm text-gray-700 dark:text-gray-300 flex items-center gap-1"><Repeat className="w-4 h-4" /> Recurring</span>
            </label>
          </div>
          {isRecurring && (
            <div className="grid grid-cols-2 gap-3 pl-6">
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Frequency</label>
                <select value={recurrencePreset} onChange={(e) => setRecurrencePreset(e.target.value)} className="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:border-[#1e3a5f] bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200">
                  <option value="weekly">Weekly</option>
                  <option value="biweekly">Every 2 weeks</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Number of meetings</label>
                <input type="number" value={recurrenceCount} onChange={(e) => setRecurrenceCount(parseInt(e.target.value) || 1)} min={1} max={52} className="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:border-[#1e3a5f] bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200" />
              </div>
            </div>
          )}
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={syncToGoogle} onChange={(e) => setSyncToGoogle(e.target.checked)} className="rounded border-gray-300 dark:border-gray-600" />
              <span className="text-sm text-gray-600 dark:text-gray-400">Sync to Google Calendar</span>
            </label>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">Remind</span>
              <select value={reminderMinutes} onChange={(e) => setReminderMinutes(parseInt(e.target.value))} className="px-2 py-1 border border-gray-200 dark:border-gray-600 rounded text-sm bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200">
                <option value={15}>15 min</option>
                <option value={30}>30 min</option>
                <option value={60}>1 hour</option>
                <option value={1440}>1 day</option>
              </select>
              <span className="text-sm text-gray-600 dark:text-gray-400">before</span>
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <button onClick={handleSchedule} disabled={submitting || !title.trim() || !startDate} className="px-4 py-2 bg-[#1e3a5f] text-white rounded-lg text-sm disabled:opacity-50 flex items-center gap-1">
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Calendar className="w-4 h-4" />} Schedule
            </button>
            <button onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700">Cancel</button>
          </div>
        </div>
      )}

      {meetings.length === 0 ? (
        <div className="text-center py-12 text-gray-400 dark:text-gray-500">
          <Calendar className="w-10 h-10 mx-auto mb-3 opacity-50" />
          <p>No meetings scheduled</p>
          <p className="text-sm mt-1">Schedule a check-in with the couple to stay aligned</p>
        </div>
      ) : (
        <div className="space-y-2">
          {meetings.map((m) => (
            <div key={m.id} className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-medium text-gray-800 dark:text-gray-200">{m.title}</h3>
                  {m.is_recurring && <span className="text-xs px-1.5 py-0.5 rounded-full bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 flex items-center gap-0.5"><Repeat className="w-3 h-3" /> Recurring</span>}
                  {m.synced_to_google && <span className="text-xs px-1.5 py-0.5 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400">Google Cal</span>}
                </div>
                {m.description && <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{m.description}</p>}
                <div className="flex items-center gap-2 mt-1 text-xs text-gray-400 dark:text-gray-500">
                  <Clock className="w-3 h-3" />
                  <span>{fmtDate(m.start_date)}</span>
                  <span>{fmtTime(m.start_date)}</span>
                  {m.end_date && <span>– {fmtTime(m.end_date)}</span>}
                </div>
              </div>
              <button onClick={() => handleCancelMeeting(m.id)} className="p-1.5 text-red-400 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition-colors" title="Cancel meeting">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
