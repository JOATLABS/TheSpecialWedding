'use client';

import { useState, useEffect, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import Link from 'next/link';
import { useAdmin } from '@/contexts/AdminContext';
import { formatDate } from '@/utils/dateFormat';

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
      const endpoint = `${baseUrl}/admin/planner/weddings`;
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
      const weddingList = Array.isArray(data) ? data : [];
      setAllWeddings(weddingList);
    } catch (err) {
      console.error('Error fetching weddings:', err);
      setError('Failed to load weddings');
      setAllWeddings([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

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

  const filterWeddings = useCallback(() => {
    if (!userProfile) return;

    let filtered = [...allWeddings];

    // Role-based filtering is handled by backend, but we can add client-side filters
    if (userProfile.is_root_admin) {
      // Root admin can see all weddings and filter by assignment
      if (filter === 'assigned') {
        filtered = filtered.filter(w => w.assigned_planner_email);
      } else if (filter === 'unassigned') {
        filtered = filtered.filter(w => !w.assigned_planner_email);
      }
    }

    // Search filter
    if (searchTerm) {
      filtered = filtered.filter(w =>
        w.couple_names.toLowerCase().includes(searchTerm.toLowerCase()) ||
        w.venue?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        w.assigned_planner_email?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Status filter
    if (statusFilter !== 'all') {
      filtered = filtered.filter(w => w.status === statusFilter);
    }

    // Date filter
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

    setWeddings(filtered);
  }, [allWeddings, dateFilter, filter, searchTerm, statusFilter, userProfile]);

  useEffect(() => {
    filterWeddings();
  }, [filterWeddings]);

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
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-sans font-bold text-slate-900 dark:text-white">
              {userProfile?.is_root_admin ? 'All Weddings' : 'My Weddings'}
            </h1>
            <p className="text-slate-600 dark:text-slate-400 mt-1">
              {userProfile?.is_root_admin
                ? 'Manage all wedding events and assignments'
                : 'Manage your wedding events and client details'
              }
            </p>
          </div>
          <button
            onClick={() => setShowForm(true)}
            className="px-4 py-2 bg-wedding-rose text-white font-semibold rounded-lg hover:bg-wedding-gold transition"
          >
            + Add Wedding
          </button>
        </div>

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
                            Last billed: {new Date(wedding.last_billed_at).toLocaleString()}
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
                    <div className="flex gap-2 ml-4">
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
      </div>
    </div>
  );
}
