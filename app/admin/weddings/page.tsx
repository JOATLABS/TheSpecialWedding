'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import Link from 'next/link';
import { useAdmin } from '@/contexts/AdminContext';
import { formatDate, formatAdminTimestamp, DEFAULT_TIMEZONE } from '@/utils/dateFormat';
import PageHeader from '../components/PageHeader';
import { usePagination } from '@/admin/hooks/usePagination';
import { GlassPagination } from '@/admin/components/ui/glass/GlassPagination';
import { toast } from 'sonner';
import {
  ListOrdered, StickyNote, Plus, GripVertical, Trash2, Loader2,
  ChevronDown, ChevronUp, MessageSquare, Eye, CheckCheck, AlertCircle,
  MessageCircle, Send, X
} from 'lucide-react';

interface Wedding {
  _id: string;
  couple_names: string;
  date: string;
  slug: string;
  assigned_planner_email?: string;
  assigned_planner_id?: string;
  status?: string;
  venue?: string;
  guest_count?: number;
  total_budget?: number;
  created_at?: string;
  billed_period?: string;
  last_billed_at?: string;
  meter_pending?: boolean;
  meter_pending_reason?: string;
  events?: Array<{
    type: string;
    date: string;
    details?: {
      venue_name?: string;
      location?: string;
      time?: string;
      attire?: string;
    };
  }>;
}

interface WeddingForm {
  couple_names: string;
  date: string;
  slug: string;
  assigned_planner_email?: string;
  venue?: string;
  status?: string;
  guest_count?: number;
  total_budget?: number;
  events: Array<{
    type: string;
    date: string;
    details?: {
      venue_name?: string;
      location?: string;
      time?: string;
      attire?: string;
    };
  }>;
}

interface UserProfile {
  email: string;
  role: string;
  is_root_admin: boolean;
  is_wedding_planner: boolean;
  user_data?: any;
}

interface PlannerOption {
  email: string;
  name: string;
  id: string;
}

// Types for Program/Notes modals
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

export default function AdminWeddingsPage() {
  const { token, userProfile, fetchUserProfile } = useAdmin();
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [allWeddings, setAllWeddings] = useState<Wedding[]>([]);
  const [planners, setPlanners] = useState<PlannerOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'assigned' | 'unassigned'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [dateFilter, setDateFilter] = useState<'all' | 'upcoming' | 'past' | 'this_month' | 'this_year'>('all');
  const [selectedWeddings, setSelectedWeddings] = useState<string[]>([]);
  const [showBulkActions, setShowBulkActions] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [showEventDetails, setShowEventDetails] = useState(false);

  // Program & Notes modal state
  const [programModalWedding, setProgramModalWedding] = useState<Wedding | null>(null);
  const [notesModalWedding, setNotesModalWedding] = useState<Wedding | null>(null);
  const [modalEvents, setModalEvents] = useState<WeddingEvent[]>([]);
  const [modalEventsLoading, setModalEventsLoading] = useState(false);

  const pagination = usePagination({ initialItemsPerPage: 50 });

  // Wedding templates
  const weddingTemplates = [
    {
      id: 'traditional-nigerian',
      name: 'Traditional Nigerian Wedding',
      description: 'Complete traditional Nigerian wedding with engagement and white wedding',
      events: [
        { type: 'engagement', date: '', details: {} },
        { type: 'traditional', date: '', details: {} },
        { type: 'white_wedding', date: '', details: {} },
        { type: 'reception', date: '', details: {} }
      ],
      status: 'planning'
    },
    {
      id: 'simple-ceremony',
      name: 'Simple Wedding Ceremony',
      description: 'Intimate ceremony with reception',
      events: [
        { type: 'white_wedding', date: '', details: {} },
        { type: 'reception', date: '', details: {} }
      ],
      status: 'planning'
    },
    {
      id: 'destination-wedding',
      name: 'Destination Wedding',
      description: 'Wedding ceremony and reception at destination venue',
      events: [
        { type: 'rehearsal', date: '', details: {} },
        { type: 'white_wedding', date: '', details: {} },
        { type: 'reception', date: '', details: {} }
      ],
      status: 'planning'
    },
    {
      id: 'court-wedding',
      name: 'Court Wedding',
      description: 'Simple court ceremony with small reception',
      events: [
        { type: 'white_wedding', date: '', details: {} },
        { type: 'reception', date: '', details: {} }
      ],
      status: 'active'
    }
  ];
  
  const [formData, setFormData] = useState<WeddingForm>({
    couple_names: '',
    date: '',
    slug: '',
    assigned_planner_email: '',
    venue: '',
    status: 'active',
    guest_count: 0,
    total_budget: 0,
    events: []
  });

  const fetchWeddings = useCallback(async () => {
    setLoading(true);
    try {
      const baseUrl = getApiBaseUrl();
      // Use authenticated planner endpoint to get assigned weddings
      const endpoint = `${baseUrl}/admin/planner/weddings?page=${pagination.currentPage}&limit=${pagination.itemsPerPage}`;
      const response = await fetch(endpoint, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch weddings');
      }
      const data = await response.json();
      const weddingList = data.weddings || data || [];
      setAllWeddings(weddingList);
      pagination.setTotalItems(data.total || weddingList.length);
    } catch (err) {
      console.error('Error fetching weddings:', err);
      setError('Failed to load weddings');
      setAllWeddings([]);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, pagination.currentPage, pagination.itemsPerPage]);

  const fetchPlanners = useCallback(async () => {
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/users?role=wedding_planner`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        const plannerOptions = data.map((user: any) => ({
          email: user.email,
          name: user.user_data?.company_name || `${user.user_data?.first_name || ''} ${user.user_data?.last_name || ''}`.trim() || user.email,
          id: user._id,
        }));
        setPlanners(plannerOptions);
      }
    } catch (err) {
      console.error('Error fetching planners:', err);
    }
  }, [token]);

  useEffect(() => {
    if (!userProfile) {
      fetchUserProfile();
    } else {
      fetchWeddings();
      if (userProfile.is_root_admin) {
        fetchPlanners();
      }
    }
  }, [fetchPlanners, fetchUserProfile, fetchWeddings, userProfile]);

  // Reset to page 1 only when user changes filter inputs (not when data changes)
  useEffect(() => {
    pagination.setPage(1);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchTerm, statusFilter, dateFilter, filter]);

  // Client-side filtering as a memo (no side effects, no loops)
  const filteredWeddings = useMemo(() => {
    if (!userProfile) return [];

    let filtered = [...allWeddings];

    if (userProfile.is_root_admin) {
      if (filter === 'assigned') {
        filtered = filtered.filter(w => w.assigned_planner_email);
      } else if (filter === 'unassigned') {
        filtered = filtered.filter(w => !w.assigned_planner_email);
      }
    }

    if (searchTerm) {
      filtered = filtered.filter(w =>
        w.couple_names.toLowerCase().includes(searchTerm.toLowerCase()) ||
        w.venue?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        w.assigned_planner_email?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    if (statusFilter !== 'all') {
      filtered = filtered.filter(w => w.status === statusFilter);
    }

    const now = new Date();
    if (dateFilter !== 'all') {
      filtered = filtered.filter(w => {
        const weddingDate = new Date(w.date);
        switch (dateFilter) {
          case 'upcoming':
            return weddingDate >= now;
          case 'past':
            return weddingDate < now;
          case 'this_month':
            return weddingDate.getMonth() === now.getMonth() && weddingDate.getFullYear() === now.getFullYear();
          case 'this_year':
            return weddingDate.getFullYear() === now.getFullYear();
          default:
            return true;
        }
      });
    }

    return filtered;
  }, [allWeddings, dateFilter, filter, searchTerm, statusFilter, userProfile]);

  useEffect(() => {
    setWeddings(filteredWeddings);
  }, [filteredWeddings]);

  // Auto-enable event details toggle when status is active or editing wedding with details
  useEffect(() => {
    if (formData.status === 'active') {
      setShowEventDetails(true);
    } else if (editingId && formData.events.some(event =>
      event.details && (event.details.venue_name || event.details.location || event.details.time || event.details.attire)
    )) {
      setShowEventDetails(true);
    }
  }, [editingId, formData.events, formData.status]);

  const generateSlug = (coupleName: string): string => {
    return coupleName.toLowerCase()
      .replace(/[^a-z0-9\s]/g, '')
      .replace(/\s+/g, '-')
      .substring(0, 50);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const baseUrl = getApiBaseUrl();
      const url = editingId 
        ? `${baseUrl}/admin/weddings/${editingId}`
        : `${baseUrl}/admin/weddings`;

      const method = editingId ? 'PUT' : 'POST';

      // Prepare the wedding data
      const weddingData = editingId 
        ? formData 
        : {
          _id: `wedding_${Date.now()}`,
          ...formData,
          slug: generateSlug(formData.couple_names),
          created_at: new Date().toISOString()
        };

      // For wedding planners, don't set assigned_planner_email - backend will auto-assign
      if (!userProfile?.is_root_admin) {
        delete weddingData.assigned_planner_email;
      }

      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(weddingData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save wedding');
      }

      // Reset form and refresh list
      setFormData({
        couple_names: '',
        date: '',
        slug: '',
        assigned_planner_email: '',
        venue: '',
        status: 'active',
        guest_count: 0,
        total_budget: 0,
        events: []
      });
      setShowForm(false);
      setEditingId(null);
      setShowEventDetails(false);
      fetchWeddings();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save wedding');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (weddingId: string) => {
    if (!confirm('Are you sure you want to delete this wedding? This will also delete all associated guests.')) {
      return;
    }

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/weddings/${weddingId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        fetchWeddings();
      } else {
        setError('Failed to delete wedding');
      }
    } catch (err) {
      setError('Failed to delete wedding');
    }
  };

  // Fetch events for Program/Notes modals
  const fetchWeddingEvents = async (weddingId: string) => {
    if (!token) return;
    setModalEventsLoading(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/admin/weddings/${weddingId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const wedding = await res.json();
        setModalEvents(wedding.events || []);
      } else {
        console.error('Failed to fetch wedding events:', res.status);
        toast.error('Failed to load events');
      }
    } catch (err) {
      console.error('Failed to fetch events:', err);
    } finally {
      setModalEventsLoading(false);
    }
  };

  const openProgramModal = (wedding: Wedding) => {
    setProgramModalWedding(wedding);
    fetchWeddingEvents(wedding._id);
  };

  const openNotesModal = (wedding: Wedding) => {
    setNotesModalWedding(wedding);
    fetchWeddingEvents(wedding._id);
  };

  const handleEdit = (wedding: Wedding) => {
    setFormData({
      couple_names: wedding.couple_names,
      date: wedding.date,
      slug: wedding.slug,
      assigned_planner_email: wedding.assigned_planner_email || '',
      venue: wedding.venue || '',
      status: wedding.status || 'active',
      guest_count: wedding.guest_count || 0,
      total_budget: wedding.total_budget || 0,
      events: wedding.events || []
    });
    setEditingId(wedding._id);
    setShowForm(true);
  };

  const addEvent = () => {
    setFormData({
      ...formData,
      events: [...formData.events, { type: '', date: '', details: {} }]
    });
  };

  const removeEvent = (index: number) => {
    setFormData({
      ...formData,
      events: formData.events.filter((_, i) => i !== index)
    });
  };

  const applyTemplate = (template: any) => {
    setFormData({
      ...formData,
      events: template.events,
      status: template.status
    });
    setShowTemplates(false);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={userProfile?.is_root_admin ? 'All Weddings' : 'My Weddings'}
        description={userProfile?.is_root_admin
          ? 'Manage all wedding events and assignments'
          : 'Manage your wedding events and client details'
        }
      >
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-wedding-rose text-white font-semibold rounded-lg hover:bg-wedding-gold transition"
        >
          + Add Wedding
        </button>
      </PageHeader>
      <div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6">
            <p className="text-red-700 dark:text-red-300">{error}</p>
          </div>
        )}

        {/* Add/Edit Wedding Form */}
        {showForm && (
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 mb-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">
                {editingId ? 'Edit Wedding' : 'Add New Wedding'}
              </h2>
              <button
                onClick={() => setShowTemplates(!showTemplates)}
                className="px-4 py-2 bg-wedding-sage text-white rounded-lg hover:bg-opacity-90"
              >
                Use Template
              </button>
            </div>

            {/* Template Selection */}
            {showTemplates && (
              <div className="mb-6 p-4 bg-gray-50 dark:bg-slate-700/50 rounded-lg">
                <h3 className="text-lg font-medium mb-3">Choose a Template:</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {weddingTemplates.map((template) => (
                    <div key={template.id} className="p-3 bg-white dark:bg-slate-800 rounded border hover:border-wedding-gold cursor-pointer" onClick={() => applyTemplate(template)}>
                      <h4 className="font-medium">{template.name}</h4>
                      <p className="text-sm text-gray-600 dark:text-gray-400">{template.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                    Couple Names *
                  </label>
                  <input
                    type="text"
                    value={formData.couple_names}
                    onChange={(e) => setFormData({...formData, couple_names: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:outline-none focus:ring-2 focus:ring-wedding-gold"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                    Wedding Date *
                  </label>
                  <input
                    type="date"
                    value={formData.date}
                    onChange={(e) => setFormData({...formData, date: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:outline-none focus:ring-2 focus:ring-wedding-gold"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                    Venue
                  </label>
                  <input
                    type="text"
                    value={formData.venue}
                    onChange={(e) => setFormData({...formData, venue: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:outline-none focus:ring-2 focus:ring-wedding-gold"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                    Guest Count
                  </label>
                  <input
                    type="number"
                    value={formData.guest_count}
                    onChange={(e) => setFormData({...formData, guest_count: parseInt(e.target.value) || 0})}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:outline-none focus:ring-2 focus:ring-wedding-gold"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                    Total Budget
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.total_budget}
                    onChange={(e) => setFormData({...formData, total_budget: parseFloat(e.target.value) || 0})}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:outline-none focus:ring-2 focus:ring-wedding-gold"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                    Status
                  </label>
                  <select
                    value={formData.status}
                    onChange={(e) => setFormData({...formData, status: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:outline-none focus:ring-2 focus:ring-wedding-gold"
                  >
                    <option value="active">Active</option>
                    <option value="planning">Planning</option>
                    <option value="completed">Completed</option>
                    <option value="cancelled">Cancelled</option>
                  </select>
                </div>

                {/* Only show planner assignment for root admin */}
                {userProfile?.is_root_admin && (
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">
                      Assign to Planner
                    </label>
                    <select
                      value={formData.assigned_planner_email}
                      onChange={(e) => setFormData({...formData, assigned_planner_email: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg focus:outline-none focus:ring-2 focus:ring-wedding-gold"
                    >
                      <option value="">Unassigned</option>
                      {planners.map((planner) => (
                        <option key={planner.id} value={planner.email}>
                          {planner.name} ({planner.email})
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              {/* Events Section */}
              <div>
                <div className="flex justify-between items-center mb-3">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300">
                    Events
                  </label>
                  <div className="flex gap-2">
                    {formData.status !== 'active' && (
                      <button
                        type="button"
                        onClick={() => setShowEventDetails(!showEventDetails)}
                        className={`px-3 py-1 text-sm rounded transition ${
                          showEventDetails
                            ? 'bg-wedding-gold text-white'
                            : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                        }`}
                      >
                        {showEventDetails ? 'Hide Details' : 'Show Details'}
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={addEvent}
                      className="px-3 py-1 bg-wedding-sage text-white text-sm rounded hover:bg-opacity-90"
                    >
                      Add Event
                    </button>
                  </div>
                </div>
                {formData.status === 'active' && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                    Event details are automatically shown for active weddings
                  </p>
                )}
                {formData.events.map((event, index) => (
                  showEventDetails || formData.status === 'active' ? (
                    // Detailed card layout
                    <div key={index} className="mb-4 p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Event Type</label>
                          <select
                            value={event.type}
                            onChange={(e) => {
                              const newEvents = [...formData.events];
                              newEvents[index].type = e.target.value;
                              setFormData({...formData, events: newEvents});
                            }}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg text-sm"
                          >
                            <option value="">Select Type</option>
                            <option value="traditional">Traditional</option>
                            <option value="white_wedding">White Wedding</option>
                            <option value="reception">Reception</option>
                            <option value="engagement">Engagement</option>
                            <option value="rehearsal">Rehearsal</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Date</label>
                          <input
                            type="date"
                            value={event.date}
                            onChange={(e) => {
                              const newEvents = [...formData.events];
                              newEvents[index].date = e.target.value;
                              setFormData({...formData, events: newEvents});
                            }}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg text-sm"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Venue Name</label>
                          <input
                            type="text"
                            value={event.details?.venue_name || ''}
                            onChange={(e) => {
                              const newEvents = [...formData.events];
                              if (!newEvents[index].details) newEvents[index].details = {};
                              newEvents[index].details!.venue_name = e.target.value;
                              setFormData({...formData, events: newEvents});
                            }}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg text-sm"
                            placeholder="e.g., St. Mary's Church"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Time</label>
                          <input
                            type="text"
                            value={event.details?.time || ''}
                            onChange={(e) => {
                              const newEvents = [...formData.events];
                              if (!newEvents[index].details) newEvents[index].details = {};
                              newEvents[index].details!.time = e.target.value;
                              setFormData({...formData, events: newEvents});
                            }}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg text-sm"
                            placeholder="e.g., 3:00 PM"
                          />
                        </div>
                        <div className="md:col-span-2">
                          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Location/Address</label>
                          <input
                            type="text"
                            value={event.details?.location || ''}
                            onChange={(e) => {
                              const newEvents = [...formData.events];
                              if (!newEvents[index].details) newEvents[index].details = {};
                              newEvents[index].details!.location = e.target.value;
                              setFormData({...formData, events: newEvents});
                            }}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg text-sm"
                            placeholder="e.g., 123 Main St, City, State"
                          />
                        </div>
                        <div className="md:col-span-2">
                          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Attire/Dress Code</label>
                          <input
                            type="text"
                            value={event.details?.attire || ''}
                            onChange={(e) => {
                              const newEvents = [...formData.events];
                              if (!newEvents[index].details) newEvents[index].details = {};
                              newEvents[index].details!.attire = e.target.value;
                              setFormData({...formData, events: newEvents});
                            }}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg text-sm"
                            placeholder="e.g., Formal attire, Traditional wear"
                          />
                        </div>
                      </div>
                      <div className="mt-3 flex justify-end">
                        <button
                          type="button"
                          onClick={() => removeEvent(index)}
                          className="px-3 py-1 bg-red-500 text-white text-sm rounded hover:bg-red-600"
                        >
                          Remove Event
                        </button>
                      </div>
                    </div>
                  ) : (
                    // Compact inline layout
                    <div key={index} className="flex gap-2 mb-2">
                      <select
                        value={event.type}
                        onChange={(e) => {
                          const newEvents = [...formData.events];
                          newEvents[index].type = e.target.value;
                          setFormData({...formData, events: newEvents});
                        }}
                        className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg"
                      >
                        <option value="">Select Type</option>
                        <option value="traditional">Traditional</option>
                        <option value="white_wedding">White Wedding</option>
                        <option value="reception">Reception</option>
                        <option value="engagement">Engagement</option>
                        <option value="rehearsal">Rehearsal</option>
                      </select>
                      <input
                        type="date"
                        value={event.date}
                        onChange={(e) => {
                          const newEvents = [...formData.events];
                          newEvents[index].date = e.target.value;
                          setFormData({...formData, events: newEvents});
                        }}
                        className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg"
                      />
                      <button
                        type="button"
                        onClick={() => removeEvent(index)}
                        className="px-3 py-2 bg-red-500 text-white rounded hover:bg-red-600"
                      >
                        Remove
                      </button>
                    </div>
                  )
                ))}
              </div>

              <div className="flex gap-4">
                <button
                  type="submit"
                  disabled={loading}
                  className="px-6 py-2 bg-wedding-gold text-white font-semibold rounded-lg hover:bg-wedding-rose transition disabled:opacity-50"
                >
                  {loading ? (editingId ? 'Updating...' : 'Creating...') : (editingId ? 'Update Wedding' : 'Create Wedding')}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowForm(false);
                    setEditingId(null);
                    setFormData({
                      couple_names: '',
                      date: '',
                      slug: '',
                      assigned_planner_email: '',
                      venue: '',
                      status: 'active',
                      guest_count: 0,
                      total_budget: 0,
                      events: []
                    });
                    setShowEventDetails(false);
                  }}
                  className="px-6 py-2 bg-gray-500 text-white font-semibold rounded-lg hover:bg-gray-600 transition"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Filters */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <input
              type="text"
              placeholder="Search weddings..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg"
            />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg"
            >
              <option value="all">All Status</option>
              <option value="active">Active</option>
              <option value="planning">Planning</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <select
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value as any)}
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg"
            >
              <option value="all">All Dates</option>
              <option value="upcoming">Upcoming</option>
              <option value="past">Past</option>
              <option value="this_month">This Month</option>
              <option value="this_year">This Year</option>
            </select>
            {/* Only show assignment filter for root admin */}
            {userProfile?.is_root_admin && (
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value as any)}
                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100-lg"
              >
                <option value="all">All Weddings</option>
                <option value="assigned">Assigned</option>
                <option value="unassigned">Unassigned</option>
              </select>
            )}
          </div>
        </div>

        {/* Compact Pagination */}
        {!loading && weddings.length > 0 && (
          <div className="mb-4">
            <GlassPagination
              currentPage={pagination.currentPage}
              totalPages={pagination.totalPages}
              totalItems={pagination.totalItems}
              itemsPerPage={pagination.itemsPerPage}
              onPageChange={pagination.setPage}
              variant="compact"
              itemLabel="weddings"
            />
          </div>
        )}

        {/* Weddings List */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-200">
              {userProfile?.is_root_admin ? 'All Weddings' : 'Your Weddings'} ({weddings.length})
            </h2>
          </div>
          {loading && (
            <div className="p-6 text-center">
              <p className="text-gray-600 dark:text-gray-400">Loading weddings...</p>
            </div>
          )}

          {!loading && weddings.length === 0 && (
            <div className="p-6 text-center">
              <p className="text-gray-600 dark:text-gray-400">
                {userProfile?.is_root_admin
                  ? 'No weddings found.'
                  : 'No weddings found. Create your first wedding to get started.'
                }
              </p>
            </div>
          )}
          {!loading && weddings.length > 0 && (
            <div className="divide-y divide-gray-200 dark:divide-gray-700">
              {weddings.map((wedding) => (
                <div key={wedding._id} className="p-6 hover:bg-gray-50 dark:hover:bg-slate-700 transition">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200">
                        {wedding.couple_names}
                      </h3>
                      <p className="text-gray-600 dark:text-gray-400">
                        {formatDate(wedding.date)}
                        {wedding.venue && ` • ${wedding.venue}`}
                      </p>
                      <div className="flex gap-4 mt-2 text-sm text-gray-500 dark:text-gray-400 flex-wrap">
                        {wedding.guest_count && (
                          <span>{wedding.guest_count} guests</span>
                        )}
                        {wedding.total_budget && (
                          <span>${wedding.total_budget.toLocaleString()} budget</span>
                        )}
                        <span className="capitalize">{wedding.status || 'active'}</span>
                        {wedding.billed_period && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700">
                            Billed: {wedding.billed_period}
                          </span>
                        )}
                        {wedding.last_billed_at && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-green-50 text-green-700 dark:text-green-300">
                            Last billed: {formatAdminTimestamp(wedding.last_billed_at)}
                          </span>
                        )}
                        {wedding.meter_pending && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-yellow-50 text-yellow-800">
                            Meter pending{wedding.meter_pending_reason ? `: ${wedding.meter_pending_reason}` : ''}
                          </span>
                        )}
                      </div>
                      {userProfile?.is_root_admin && wedding.assigned_planner_email && (
                        <p className="text-sm text-blue-600 mt-1">
                          Assigned to: {wedding.assigned_planner_email}
                        </p>
                      )}
                    </div>
                    <div className="flex gap-2 ml-4 flex-wrap">
                      <button
                        onClick={() => openProgramModal(wedding)}
                        className="px-3 py-1 text-sm bg-indigo-500 text-white rounded hover:bg-indigo-600 transition"
                      >
                        Program
                      </button>
                      <button
                        onClick={() => openNotesModal(wedding)}
                        className="px-3 py-1 text-sm bg-amber-500 text-white rounded hover:bg-amber-600 transition"
                      >
                        Notes
                      </button>
                      <Link
                        href={`/admin/weddings/${wedding._id}`}
                        className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 transition"
                      >
                        Configure
                      </Link>
                      <button
                        onClick={() => handleEdit(wedding)}
                        className="px-3 py-1 text-sm bg-wedding-gold text-white rounded hover:bg-wedding-rose transition"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(wedding._id)}
                        className="px-3 py-1 text-sm bg-red-500 text-white rounded hover:bg-red-600 transition"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Pagination */}
        {!loading && weddings.length > 0 && (
          <div className="mt-6">
            <GlassPagination
              currentPage={pagination.currentPage}
              totalPages={pagination.totalPages}
              totalItems={pagination.totalItems}
              itemsPerPage={pagination.itemsPerPage}
              onPageChange={pagination.setPage}
              onItemsPerPageChange={pagination.setItemsPerPage}
              itemLabel="weddings"
            />
          </div>
        )}
      </div>

      {/* ==================== PROGRAM MODAL ==================== */}
      {programModalWedding && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setProgramModalWedding(null)}>
          <div
            className="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-700">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Program / Run of Show</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">{programModalWedding.couple_names}</p>
              </div>
              <button onClick={() => setProgramModalWedding(null)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-5 py-4">
              {modalEventsLoading ? (
                <div className="text-center py-8 text-gray-400">
                  <Loader2 className="w-6 h-6 mx-auto mb-2 animate-spin" />
                  <p>Loading events...</p>
                </div>
              ) : (
                <ProgramModalContent
                  key={JSON.stringify(modalEvents.map(e => (e.order_of_events || []).map(i => i.id)))}
                  events={modalEvents}
                  weddingId={programModalWedding._id}
                  token={token || ''}
                  onRefresh={() => fetchWeddingEvents(programModalWedding._id)}
                />
              )}
            </div>
          </div>
        </div>
      )}

      {/* ==================== NOTES MODAL ==================== */}
      {notesModalWedding && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setNotesModalWedding(null)}>
          <div
            className="bg-white dark:bg-slate-800 rounded-xl shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-700">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Couple Notes</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">{notesModalWedding.couple_names}</p>
              </div>
              <button onClick={() => setNotesModalWedding(null)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-5 py-4">
              {modalEventsLoading ? (
                <div className="text-center py-8 text-gray-400">
                  <Loader2 className="w-6 h-6 mx-auto mb-2 animate-spin" />
                  <p>Loading notes...</p>
                </div>
              ) : (
                <NotesModalContent
                  events={modalEvents}
                  weddingId={notesModalWedding._id}
                  token={token || ''}
                  onRefresh={() => fetchWeddingEvents(notesModalWedding._id)}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


// ============================================================================
// PROGRAM MODAL CONTENT
// ============================================================================

function ProgramModalContent({
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
    if (!newTitle.trim()) { toast.error('Title is required'); return; }
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
        setNewTitle(''); setNewTime(''); setNewDuration(''); setNewDescription('');
        onRefresh();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to add item');
      }
    } catch { toast.error('Failed to connect'); }
    finally { setSaving(false); }
  };

  const handleDeleteItem = async (eventIndex: number, itemId: string) => {
    try {
      const res = await fetch(
        `${getApiBaseUrl()}/couple-portal/events/${eventIndex}/order-of-events/${itemId}?wedding_id=${weddingId}`,
        { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) { toast.success('Item removed'); onRefresh(); }
      else { const err = await res.json(); toast.error(err.detail || 'Failed to delete'); }
    } catch { toast.error('Failed to connect'); }
  };

  if (events.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        <ListOrdered className="w-10 h-10 mx-auto mb-3 opacity-50" />
        <p>No events in this wedding yet</p>
        <p className="text-sm mt-1">Add events to the wedding first, then manage the run of show here</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {events.map((event, eventIdx) => (
        <div key={eventIdx} className="bg-gray-50 dark:bg-slate-700/50 rounded-lg overflow-hidden">
          <button
            onClick={() => setExpandedEvent(expandedEvent === eventIdx ? null : eventIdx)}
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors"
          >
            <div className="flex items-center gap-2">
              <ListOrdered className="w-4 h-4 text-indigo-500" />
              <div className="text-left">
                <p className="font-medium text-sm text-gray-800 dark:text-gray-200">{eventTypeLabel(event.type)}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">{event.date} · {event.order_of_events?.length || 0} items</p>
              </div>
            </div>
            {expandedEvent === eventIdx ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
          </button>

          {expandedEvent === eventIdx && (
            <div className="border-t border-gray-200 dark:border-gray-600 px-4 py-3">
              {(event.order_of_events || []).length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-3">No program items yet</p>
              ) : (
                <div className="space-y-2 mb-3">
                  {(event.order_of_events || []).sort((a, b) => a.order - b.order).map((item) => (
                    <div key={item.id} className="flex items-center gap-2 p-2.5 bg-white dark:bg-slate-800 rounded-lg group">
                      <GripVertical className="w-3.5 h-3.5 text-gray-300 dark:text-gray-600 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="font-medium text-gray-800 dark:text-gray-200 text-sm">{item.title}</p>
                          {item.time && <span className="text-xs text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/30 px-1.5 py-0.5 rounded">{item.time}</span>}
                          {item.duration_minutes && <span className="text-xs text-gray-400">{item.duration_minutes}min</span>}
                        </div>
                        {item.description && <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{item.description}</p>}
                        {item.notes.length > 0 && (
                          <div className="flex items-center gap-1 mt-1">
                            <MessageSquare className="w-3 h-3 text-amber-500" />
                            <span className="text-xs text-amber-600">{item.notes.length} note{item.notes.length > 1 ? 's' : ''}</span>
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

              {addingToEvent === eventIdx ? (
                <div className="border border-indigo-200 dark:border-indigo-700 rounded-lg p-3 bg-indigo-50/50 dark:bg-indigo-900/20">
                  <div className="grid grid-cols-2 gap-2">
                    <div className="col-span-2">
                      <input type="text" placeholder="Title (e.g. First Dance)" value={newTitle} onChange={(e) => setNewTitle(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200" autoFocus />
                    </div>
                    <input type="text" placeholder="Time (e.g. 6:30 PM)" value={newTime} onChange={(e) => setNewTime(e.target.value)}
                      className="px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200" />
                    <input type="number" placeholder="Duration (min)" value={newDuration} onChange={(e) => setNewDuration(e.target.value)}
                      className="px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200" min="1" />
                    <div className="col-span-2">
                      <textarea placeholder="Description (optional)" value={newDescription} onChange={(e) => setNewDescription(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm resize-none bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200" rows={2} />
                    </div>
                  </div>
                  <div className="flex justify-end gap-2 mt-2">
                    <button onClick={() => setAddingToEvent(null)} className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800">Cancel</button>
                    <button onClick={() => handleAddItem(eventIdx)} disabled={saving}
                      className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-1">
                      {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />} Add
                    </button>
                  </div>
                </div>
              ) : (
                <button onClick={() => setAddingToEvent(eventIdx)}
                  className="w-full py-2 border border-dashed border-gray-300 dark:border-gray-600 rounded-lg text-sm text-gray-500 hover:border-indigo-400 hover:text-indigo-600 transition-colors flex items-center justify-center gap-1">
                  <Plus className="w-4 h-4" /> Add Program Item
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
// NOTES MODAL CONTENT
// ============================================================================

function NotesModalContent({
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

  type NoteEntry = { note: EventNote; context: string; eventIndex: number; itemId?: string; noteId: string; };
  const allNotes: NoteEntry[] = [];

  events.forEach((event, eventIdx) => {
    const eventLabel = {
      traditional: 'Traditional Ceremony', white_wedding: 'White Wedding', reception: 'Reception',
      engagement: 'Engagement Party', rehearsal: 'Rehearsal Dinner',
    }[event.type] || event.type;

    (event.event_notes || []).forEach((note) => {
      allNotes.push({ note, context: eventLabel, eventIndex: eventIdx, noteId: note.id });
    });
    (event.order_of_events || []).forEach((item) => {
      (item.notes || []).forEach((note) => {
        allNotes.push({ note, context: `${eventLabel} → ${item.title}`, eventIndex: eventIdx, itemId: item.id, noteId: note.id });
      });
    });
  });

  const parentNotes = allNotes.filter(n => !n.note.reply_to);
  const replyNotes = allNotes.filter(n => !!n.note.reply_to);
  const repliesMap: Record<string, NoteEntry[]> = {};
  replyNotes.forEach(entry => {
    const parentId = entry.note.reply_to;
    if (!parentId) return;
    if (!repliesMap[parentId]) repliesMap[parentId] = [];
    repliesMap[parentId].push(entry);
  });
  Object.values(repliesMap).forEach(replies => replies.sort((a, b) => (a.note.created_at || '').localeCompare(b.note.created_at || '')));
  parentNotes.sort((a, b) => {
    if (a.note.status === 'pending' && b.note.status !== 'pending') return -1;
    if (a.note.status !== 'pending' && b.note.status === 'pending') return 1;
    return (b.note.created_at || '').localeCompare(a.note.created_at || '');
  });

  const handleStatusUpdate = async (eventIndex: number, noteId: string, newStatus: 'seen' | 'addressed', itemId?: string) => {
    const url = itemId
      ? `${getApiBaseUrl()}/couple-portal/events/${eventIndex}/order-of-events/${itemId}/notes/${noteId}`
      : `${getApiBaseUrl()}/couple-portal/events/${eventIndex}/notes/${noteId}`;
    try {
      const res = await fetch(url, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ wedding_id: weddingId, status: newStatus }),
      });
      if (res.ok) { toast.success(`Note marked as ${newStatus}`); onRefresh(); }
      else { const err = await res.json(); toast.error(err.detail || 'Failed to update'); }
    } catch { toast.error('Failed to connect'); }
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
      if (res.ok) { toast.success('Reply sent'); setReplyTarget(null); setReplyText(''); onRefresh(); }
      else { const err = await res.json().catch(() => ({})); toast.error(err.detail || 'Failed to send reply'); }
    } catch { toast.error('Failed to connect'); }
    finally { setSubmittingReply(false); }
  };

  const statusBadge = (status: string) => {
    const styles: Record<string, string> = { pending: 'bg-amber-100 text-amber-700', seen: 'bg-blue-100 text-blue-700', addressed: 'bg-green-100 text-green-700' };
    return styles[status] || 'bg-gray-100 text-gray-600';
  };

  const pendingCount = parentNotes.filter(n => n.note.status === 'pending').length;

  if (parentNotes.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        <StickyNote className="w-10 h-10 mx-auto mb-3 opacity-50" />
        <p>No notes from the couple yet</p>
        <p className="text-sm mt-1">Notes will appear here when the couple adds feedback</p>
      </div>
    );
  }

  return (
    <div>
      {pendingCount > 0 && (
        <p className="text-sm text-amber-600 dark:text-amber-400 mb-3">{pendingCount} pending note{pendingCount > 1 ? 's' : ''}</p>
      )}
      <div className="space-y-3">
        {parentNotes.map(({ note, context, eventIndex, itemId, noteId }) => {
          const replies = repliesMap[noteId] || [];
          const isReplyOpen = replyTarget === noteId;

          return (
            <div key={noteId} className={`bg-gray-50 dark:bg-slate-700/50 rounded-lg p-3 ${note.status === 'pending' ? 'border border-amber-200 dark:border-amber-700' : ''}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    {note.status === 'pending' && <AlertCircle className="w-3.5 h-3.5 text-amber-500" />}
                    {note.status === 'seen' && <Eye className="w-3.5 h-3.5 text-blue-500" />}
                    {note.status === 'addressed' && <CheckCheck className="w-3.5 h-3.5 text-green-500" />}
                    <span className="text-xs text-gray-500 dark:text-gray-400">{context}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded-full ${statusBadge(note.status)}`}>{note.status}</span>
                  </div>
                  <p className="text-sm text-gray-800 dark:text-gray-200">{note.text}</p>
                  <div className="flex items-center gap-2 mt-1.5 text-xs text-gray-400">
                    <span>{note.author_name || note.author_role}</span>
                    {note.created_at && <span>· {new Date(note.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span>}
                  </div>
                </div>
                <div className="flex gap-1 flex-shrink-0">
                  {note.status === 'pending' && (
                    <button onClick={() => handleStatusUpdate(eventIndex, noteId, 'seen', itemId)}
                      className="p-1 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded transition-colors" title="Mark as seen">
                      <Eye className="w-3.5 h-3.5" />
                    </button>
                  )}
                  {note.status !== 'addressed' && (
                    <button onClick={() => handleStatusUpdate(eventIndex, noteId, 'addressed', itemId)}
                      className="p-1 text-green-500 hover:bg-green-50 dark:hover:bg-green-900/30 rounded transition-colors" title="Mark as addressed">
                      <CheckCheck className="w-3.5 h-3.5" />
                    </button>
                  )}
                  <button onClick={() => { setReplyTarget(isReplyOpen ? null : noteId); setReplyText(''); }}
                    className={`p-1 rounded transition-colors ${isReplyOpen ? 'text-indigo-600 bg-indigo-50 dark:bg-indigo-900/30' : 'text-gray-400 hover:bg-gray-100 dark:hover:bg-slate-700'}`}
                    title="Reply">
                    <MessageCircle className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {replies.length > 0 && (
                <div className="mt-2 ml-3 border-l-2 border-indigo-100 dark:border-indigo-800 pl-3 space-y-1.5">
                  {replies.map(({ note: reply }) => (
                    <div key={reply.id} className="bg-white dark:bg-slate-800 rounded p-2">
                      <p className="text-sm text-gray-700 dark:text-gray-300">{reply.text}</p>
                      <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
                        <span className="text-indigo-600 dark:text-indigo-400 font-medium">Planner</span>
                        {reply.created_at && <span>· {new Date(reply.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {isReplyOpen && (
                <div className="mt-2 ml-3 border-l-2 border-indigo-200 dark:border-indigo-700 pl-3">
                  <div className="flex gap-2">
                    <input type="text" value={replyText} onChange={(e) => setReplyText(e.target.value)}
                      placeholder="Type your reply..." autoFocus
                      onKeyDown={(e) => e.key === 'Enter' && !submittingReply && handleReply(eventIndex, noteId, itemId)}
                      className="flex-1 px-3 py-1.5 border border-gray-200 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200" />
                    <button onClick={() => handleReply(eventIndex, noteId, itemId)} disabled={submittingReply || !replyText.trim()}
                      className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-sm disabled:opacity-50 flex items-center gap-1">
                      {submittingReply ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
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
