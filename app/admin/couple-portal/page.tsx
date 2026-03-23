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
  ListOrdered, StickyNote, ShieldOff, ShieldCheck, AlertCircle
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
  const [activeSection, setActiveSection] = useState<'couples' | 'program' | 'notes'>('couples');

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
        ? `${getApiBaseUrl()}/couple-portal/couples?wedding_id=${selectedWeddingId}`
        : `${getApiBaseUrl()}/couple-portal/couples`;
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
      const res = await fetch(`${getApiBaseUrl()}/couple-portal/invite`, {
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
      const res = await fetch(`${getApiBaseUrl()}/couple-portal/resend-invite`, {
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
  ];

  return (
    <div className="p-4 sm:p-6 max-w-6xl mx-auto">
      <PageHeader
        title="Couple Portal"
        description="Manage couple access, program details, and collaborative notes"
      />

      {/* Wedding Selector */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-1">Select Wedding</label>
        <select
          value={selectedWeddingId}
          onChange={(e) => setSelectedWeddingId(e.target.value)}
          className="w-full sm:w-80 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          {weddings.map((w) => (
            <option key={w.id} value={w.id}>{w.couple_names} — {w.date}</option>
          ))}
        </select>
      </div>

      {/* Section Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {sectionTabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveSection(tab.key)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeSection === tab.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
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

      {/* Invite Modal */}
      {showInviteForm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Invite Couple</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-600 mb-1">Email *</label>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
                  placeholder="couple@email.com"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">Partner 1 Name *</label>
                <input
                  type="text"
                  value={invitePartner1}
                  onChange={(e) => setInvitePartner1(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">Partner 2 Name</label>
                <input
                  type="text"
                  value={invitePartner2}
                  onChange={(e) => setInvitePartner2(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowInviteForm(false)}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
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
        <h2 className="text-lg font-semibold text-gray-800">Couple Accounts</h2>
        <button
          onClick={onInvite}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" />
          Invite Couple
        </button>
      </div>

      {couples.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <Users className="w-10 h-10 mx-auto mb-3 opacity-50" />
          <p>No couples invited yet</p>
          <p className="text-sm mt-1">Click "Invite Couple" to get started</p>
        </div>
      ) : (
        <div className="space-y-3">
          {couples.map((couple) => (
            <div key={couple.id} className="bg-white rounded-lg border border-gray-200 p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-medium ${
                  couple.is_active ? 'bg-green-500' : couple.setup_completed ? 'bg-red-400' : 'bg-amber-400'
                }`}>
                  {(couple.partner1_name || 'C').charAt(0)}
                </div>
                <div>
                  <p className="font-medium text-gray-800 text-sm">
                    {couple.partner1_name}{couple.partner2_name ? ` & ${couple.partner2_name}` : ''}
                  </p>
                  <p className="text-xs text-gray-500">{couple.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2 py-1 rounded-full ${
                  couple.is_active
                    ? 'bg-green-100 text-green-700'
                    : couple.setup_completed
                    ? 'bg-red-100 text-red-700'
                    : 'bg-amber-100 text-amber-700'
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
                  <span className="text-xs text-gray-400" title="Last login">
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
      <div className="text-center py-12 text-gray-400">
        <ListOrdered className="w-10 h-10 mx-auto mb-3 opacity-50" />
        <p>No events in this wedding yet</p>
        <p className="text-sm mt-1">Add events to the wedding first, then manage the run of show here</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500 mb-2">
        Build the detailed run of show for each ceremony. Couples will see this in their portal and can leave notes.
      </p>

      {events.map((event, eventIdx) => (
        <div key={eventIdx} className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          {/* Event Header */}
          <button
            onClick={() => setExpandedEvent(expandedEvent === eventIdx ? null : eventIdx)}
            className="w-full flex items-center justify-between px-5 py-3 hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <ListOrdered className="w-5 h-5 text-blue-500" />
              <div className="text-left">
                <p className="font-medium text-gray-800">{eventTypeLabel(event.type)}</p>
                <p className="text-xs text-gray-500">
                  {event.date} · {event.order_of_events?.length || 0} items
                </p>
              </div>
            </div>
            {expandedEvent === eventIdx ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
          </button>

          {/* Expanded: Order of Events List */}
          {expandedEvent === eventIdx && (
            <div className="border-t border-gray-100 px-5 py-4">
              {(event.order_of_events || []).length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-4">No program items yet</p>
              ) : (
                <div className="space-y-2 mb-4">
                  {(event.order_of_events || [])
                    .sort((a, b) => a.order - b.order)
                    .map((item) => (
                      <div
                        key={item.id}
                        className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg group"
                      >
                        <GripVertical className="w-4 h-4 text-gray-300 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="font-medium text-gray-800 text-sm">{item.title}</p>
                            {item.time && (
                              <span className="text-xs text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
                                {item.time}
                              </span>
                            )}
                            {item.duration_minutes && (
                              <span className="text-xs text-gray-400">{item.duration_minutes}min</span>
                            )}
                          </div>
                          {item.description && (
                            <p className="text-xs text-gray-500 mt-0.5">{item.description}</p>
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
                <div className="border border-blue-200 rounded-lg p-4 bg-blue-50/50">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="col-span-2">
                      <input
                        type="text"
                        placeholder="Title (e.g. First Dance)"
                        value={newTitle}
                        onChange={(e) => setNewTitle(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
                        autoFocus
                      />
                    </div>
                    <input
                      type="text"
                      placeholder="Time (e.g. 6:30 PM)"
                      value={newTime}
                      onChange={(e) => setNewTime(e.target.value)}
                      className="px-3 py-2 border border-gray-200 rounded-lg text-sm"
                    />
                    <input
                      type="number"
                      placeholder="Duration (min)"
                      value={newDuration}
                      onChange={(e) => setNewDuration(e.target.value)}
                      className="px-3 py-2 border border-gray-200 rounded-lg text-sm"
                      min="1"
                    />
                    <div className="col-span-2">
                      <textarea
                        placeholder="Description (optional)"
                        value={newDescription}
                        onChange={(e) => setNewDescription(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm resize-none"
                        rows={2}
                      />
                    </div>
                  </div>
                  <div className="flex justify-end gap-2 mt-3">
                    <button
                      onClick={() => setAddingToEvent(null)}
                      className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800"
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
                  className="w-full py-2 border border-dashed border-gray-300 rounded-lg text-sm text-gray-500 hover:border-blue-400 hover:text-blue-600 transition-colors flex items-center justify-center gap-1"
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
  // Collect all notes across all events and items
  const allNotes: {
    note: EventNote;
    context: string;
    eventIndex: number;
    itemId?: string;
    noteId: string;
  }[] = [];

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

  // Sort: pending first, then by date (newest first)
  allNotes.sort((a, b) => {
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

  const pendingCount = allNotes.filter(n => n.note.status === 'pending').length;

  if (allNotes.length === 0) {
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
        <h2 className="text-lg font-semibold text-gray-800">
          Couple Notes
          {pendingCount > 0 && (
            <span className="ml-2 text-sm font-normal text-amber-600">
              ({pendingCount} pending)
            </span>
          )}
        </h2>
      </div>

      <div className="space-y-3">
        {allNotes.map(({ note, context, eventIndex, itemId, noteId }) => (
          <div
            key={noteId}
            className={`bg-white rounded-lg border p-4 ${
              note.status === 'pending' ? 'border-amber-200' : 'border-gray-200'
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  {statusIcon(note.status)}
                  <span className="text-xs text-gray-500">{context}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded-full ${statusBadge(note.status)}`}>
                    {note.status}
                  </span>
                </div>
                <p className="text-sm text-gray-800">{note.text}</p>
                <div className="flex items-center gap-2 mt-2 text-xs text-gray-400">
                  <span>{note.author_name || note.author_role}</span>
                  {note.created_at && (
                    <span>· {new Date(note.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span>
                  )}
                </div>
              </div>

              {/* Status actions */}
              {note.status !== 'addressed' && (
                <div className="flex gap-1 flex-shrink-0">
                  {note.status === 'pending' && (
                    <button
                      onClick={() => handleStatusUpdate(eventIndex, noteId, 'seen', itemId)}
                      className="p-1.5 text-blue-500 hover:bg-blue-50 rounded-lg transition-colors"
                      title="Mark as seen"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  )}
                  <button
                    onClick={() => handleStatusUpdate(eventIndex, noteId, 'addressed', itemId)}
                    className="p-1.5 text-green-500 hover:bg-green-50 rounded-lg transition-colors"
                    title="Mark as addressed"
                  >
                    <CheckCheck className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
