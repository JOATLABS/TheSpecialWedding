'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useAdmin } from '../../contexts/AdminContext';

interface Wedding {
  id: string;
  _id: string;
  couple_names: string;
  date: string;
  slug: string;
  assigned_planner_email?: string;
  assigned_planner_id?: string;
  status?: string;
  venue?: string;
  guest_count?: number;
  created_at?: string;
  events?: Array<{
    type: string;
    date: string;
  }>;
}

interface WeddingForm {
  couple_names: string;
  date: string;
  slug: string;
  assigned_planner_email?: string;
  venue?: string;
  status?: string;
  events: Array<{
    type: string;
    date: string;
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
  
  const [formData, setFormData] = useState<WeddingForm>({
    couple_names: '',
    date: '',
    slug: '',
    assigned_planner_email: '',
    venue: '',
    status: 'active',
    events: []
  });

  useEffect(() => {
    if (!userProfile) {
      fetchUserProfile();
    } else {
      fetchWeddings();
      if (userProfile.is_root_admin) {
        fetchPlanners();
      }
    }
  }, [userProfile]);

  useEffect(() => {
    filterWeddings();
  }, [allWeddings, filter, userProfile]);

  const fetchWeddings = async () => {
    setLoading(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      
      // Choose API endpoint based on user role
      const endpoint = userProfile?.is_root_admin 
        ? `${baseUrl}/admin/weddings` // ROOT_ADMIN sees all weddings
        : `${baseUrl}/admin/planner/weddings`; // Planners see only assigned weddings
      
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
      // Ensure data is an array
      const weddingList = Array.isArray(data) ? data : [];
      setAllWeddings(weddingList);
    } catch (err) {
      console.error('Error fetching weddings:', err);
      setError('Failed to load weddings');
      setAllWeddings([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchPlanners = async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
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
          id: user._id
        }));
        setPlanners(plannerOptions);
      }
    } catch (err) {
      console.error('Error fetching planners:', err);
    }
  };

  const filterWeddings = () => {
    if (!userProfile) return;

    let filtered = [...allWeddings];

    // Apply role-based filtering
    if (!userProfile.is_root_admin) {
      // Wedding planners only see their assigned weddings
      filtered = filtered.filter(wedding => 
        wedding.assigned_planner_email === userProfile.email
      );
    } else {
      // ROOT_ADMIN can filter by assignment status
      if (filter === 'assigned') {
        filtered = filtered.filter(wedding => wedding.assigned_planner_email);
      } else if (filter === 'unassigned') {
        filtered = filtered.filter(wedding => !wedding.assigned_planner_email);
      }
    }

    setWeddings(filtered);
  };

  const generateSlug = (coupleNames: string) => {
    return coupleNames
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .trim();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
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
            created_at: new Date().toISOString()
          };

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
        events: []
      });
      setShowForm(false);
      setEditingId(null);
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
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
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
      events: wedding.events || []
    });
    setEditingId(wedding._id);
    setShowForm(true);
  };

  const addEvent = () => {
    setFormData({
      ...formData,
      events: [...formData.events, { type: '', date: '' }]
    });
  };

  const removeEvent = (index: number) => {
    setFormData({
      ...formData,
      events: formData.events.filter((_, i) => i !== index)
    });
  };

  const updateEvent = (index: number, field: 'type' | 'date', value: string) => {
    const newEvents = [...formData.events];
    newEvents[index][field] = value;
    setFormData({ ...formData, events: newEvents });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-wedding-ivory to-rose-50 p-4 sm:p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden mb-8">
          <div className="bg-gradient-to-r from-wedding-navy to-wedding-gold px-4 sm:px-8 py-4 sm:py-6">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
              <div>
                <h1 className="text-2xl sm:text-3xl font-bold text-white">
                  {userProfile?.is_root_admin ? 'Wedding Management' : 'My Weddings'}
                </h1>
                <p className="text-blue-100 mt-1 sm:mt-2 text-sm sm:text-base">
                  {userProfile?.is_root_admin 
                    ? 'Create and manage wedding events for all planners' 
                    : 'Manage your assigned wedding events'
                  }
                </p>
              </div>
              <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
                {userProfile?.is_root_admin && (
                  <select
                    value={filter}
                    onChange={(e) => setFilter(e.target.value as 'all' | 'assigned' | 'unassigned')}
                    className="bg-white text-wedding-navy px-4 py-2 rounded-lg border-0 text-sm focus:ring-2 focus:ring-blue-300"
                  >
                    <option value="all">All Weddings ({allWeddings.length})</option>
                    <option value="assigned">Assigned ({allWeddings.filter(w => w.assigned_planner_email).length})</option>
                    <option value="unassigned">Unassigned ({allWeddings.filter(w => !w.assigned_planner_email).length})</option>
                  </select>
                )}
                {userProfile?.is_root_admin && (
                  <button
                    onClick={() => {
                      setShowForm(!showForm);
                      setEditingId(null);
                      setFormData({
                        couple_names: '',
                        date: '',
                        slug: '',
                        assigned_planner_email: '',
                        venue: '',
                        status: 'active',
                        events: []
                      });
                    }}
                    className="bg-white text-wedding-navy px-4 sm:px-6 py-2 sm:py-3 rounded-lg font-semibold hover:bg-wedding-ivory transition-colors text-sm sm:text-base w-full sm:w-auto"
                  >
                    {showForm ? 'Cancel' : 'Create Wedding'}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Wedding Form */}
        {showForm && (
          <div className="bg-white rounded-2xl shadow-xl overflow-hidden mb-8">
            <div className="p-4 sm:p-8">
              <h2 className="text-xl sm:text-2xl font-bold text-wedding-navy mb-4 sm:mb-6">
                {editingId ? 'Edit Wedding' : 'Create New Wedding'}
              </h2>
              
              <form onSubmit={handleSubmit} className="space-y-6">
                {/* Couple Names */}
                <div>
                  <label htmlFor="couple_names" className="block text-sm font-medium text-gray-700 mb-2">
                    Couple Names
                  </label>
                  <input
                    type="text"
                    id="couple_names"
                    value={formData.couple_names}
                    onChange={(e) => {
                      setFormData({
                        ...formData,
                        couple_names: e.target.value,
                        slug: generateSlug(e.target.value)
                      });
                    }}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    placeholder="John & Jane"
                    required
                  />
                </div>

                {/* Wedding Date */}
                <div>
                  <label htmlFor="date" className="block text-sm font-medium text-gray-700 mb-2">
                    Main Wedding Date
                  </label>
                  <input
                    type="date"
                    id="date"
                    value={formData.date}
                    onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    required
                  />
                </div>

                {/* URL Slug */}
                <div>
                  <label htmlFor="slug" className="block text-sm font-medium text-gray-700 mb-2">
                    URL Slug
                  </label>
                  <input
                    type="text"
                    id="slug"
                    value={formData.slug}
                    onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    placeholder="john-jane-wedding"
                    required
                  />
                  <p className="mt-1 text-sm text-gray-500">
                    This will be used in the URL: thespecialwedding.com/{formData.slug || 'your-wedding'}
                  </p>
                </div>

                {/* Venue */}
                <div>
                  <label htmlFor="venue" className="block text-sm font-medium text-gray-700 mb-2">
                    Venue (Optional)
                  </label>
                  <input
                    type="text"
                    id="venue"
                    value={formData.venue}
                    onChange={(e) => setFormData({ ...formData, venue: e.target.value })}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    placeholder="Wedding Venue Name"
                  />
                </div>

                {/* Assigned Planner (ROOT_ADMIN only) */}
                {userProfile?.is_root_admin && (
                  <div>
                    <label htmlFor="assigned_planner" className="block text-sm font-medium text-gray-700 mb-2">
                      Assign Wedding Planner
                    </label>
                    <select
                      id="assigned_planner"
                      value={formData.assigned_planner_email}
                      onChange={(e) => setFormData({ ...formData, assigned_planner_email: e.target.value })}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    >
                      <option value="">Select a wedding planner...</option>
                      {planners.map((planner) => (
                        <option key={planner.id} value={planner.email}>
                          {planner.name} ({planner.email})
                        </option>
                      ))}
                    </select>
                    <p className="mt-1 text-sm text-gray-500">
                      Choose which wedding planner will manage this wedding
                    </p>
                  </div>
                )}

                {/* Status */}
                <div>
                  <label htmlFor="status" className="block text-sm font-medium text-gray-700 mb-2">
                    Wedding Status
                  </label>
                  <select
                    id="status"
                    value={formData.status}
                    onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  >
                    <option value="active">Active</option>
                    <option value="planning">Planning</option>
                    <option value="completed">Completed</option>
                    <option value="cancelled">Cancelled</option>
                  </select>
                </div>

                {/* Events Section */}
                <div>
                  <div className="flex justify-between items-center mb-4">
                    <label className="block text-sm font-medium text-gray-700">
                      Wedding Events
                    </label>
                    <button
                      type="button"
                      onClick={addEvent}
                      className="text-sm bg-wedding-sage text-white px-4 py-2 rounded-lg hover:bg-opacity-90 transition-colors"
                    >
                      Add Event
                    </button>
                  </div>

                  {formData.events.map((event, index) => (
                    <div key={index} className="flex flex-col sm:flex-row gap-2 sm:gap-4 mb-3">
                      <select
                        value={event.type}
                        onChange={(e) => updateEvent(index, 'type', e.target.value)}
                        className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                        required
                      >
                        <option value="">Select event type</option>
                        <option value="traditional">Traditional</option>
                        <option value="white_wedding">White Wedding</option>
                        <option value="reception">Reception</option>
                        <option value="engagement">Engagement</option>
                        <option value="rehearsal">Rehearsal Dinner</option>
                      </select>
                      <input
                        type="date"
                        value={event.date}
                        onChange={(e) => updateEvent(index, 'date', e.target.value)}
                        className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => removeEvent(index)}
                        className="px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors self-start sm:self-auto"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-gradient-to-r from-wedding-rose to-wedding-gold text-white py-3 px-6 rounded-lg font-semibold hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-wedding-rose focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                >
                  {loading ? 'Saving...' : editingId ? 'Update Wedding' : 'Create Wedding'}
                </button>
              </form>
            </div>
          </div>
        )}

        {/* Weddings List */}
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden">
          <div className="p-4 sm:p-8">
            {loading && !showForm ? (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin h-8 w-8 border-4 border-wedding-rose border-t-transparent rounded-full"></div>
                <span className="ml-3 text-gray-600">Loading weddings...</span>
              </div>
            ) : weddings.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <p className="text-lg">No weddings found.</p>
                <p className="text-sm mt-2">Click "Create Wedding" to get started.</p>
              </div>
            ) : (
              <div className="grid gap-6">
                {weddings.map((wedding) => (
                  <div key={wedding._id} className="border border-gray-200 rounded-xl p-4 sm:p-6 hover:shadow-lg transition-shadow">
                    <div className="flex flex-col space-y-4">
                      <div className="flex-1">
                        <div className="flex items-start justify-between">
                          <h3 className="text-lg sm:text-xl font-bold text-wedding-navy">{wedding.couple_names}</h3>
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                            wedding.status === 'active' ? 'bg-green-100 text-green-800' :
                            wedding.status === 'planning' ? 'bg-blue-100 text-blue-800' :
                            wedding.status === 'completed' ? 'bg-gray-100 text-gray-800' :
                            'bg-red-100 text-red-800'
                          }`}>
                            {wedding.status || 'active'}
                          </span>
                        </div>
                        <p className="text-gray-600 mt-1 text-sm sm:text-base">📅 {wedding.date}</p>
                        {wedding.venue && (
                          <p className="text-gray-600 text-sm">📍 {wedding.venue}</p>
                        )}
                        <p className="text-xs sm:text-sm text-gray-500 mt-1 break-all">
                          🔗 thespecialwedding.com/{wedding.slug}
                        </p>
                        
                        {/* Planner Assignment */}
                        {userProfile?.is_root_admin && (
                          <div className="mt-2">
                            {wedding.assigned_planner_email ? (
                              <p className="text-sm text-green-600">
                                👤 Assigned to: {wedding.assigned_planner_email}
                              </p>
                            ) : (
                              <p className="text-sm text-orange-600">
                                ⚠️ No planner assigned
                              </p>
                            )}
                          </div>
                        )}

                        {wedding.events && wedding.events.length > 0 && (
                          <div className="mt-3">
                            <p className="text-sm font-medium text-gray-700">Events:</p>
                            <div className="flex flex-wrap gap-2 mt-1">
                              {wedding.events.map((event, index) => (
                                <span 
                                  key={index}
                                  className="inline-flex px-2 sm:px-3 py-1 text-xs font-semibold rounded-full bg-wedding-sage bg-opacity-20 text-wedding-navy"
                                >
                                  {event.type.replace('_', ' ')} - {event.date}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                      <div className="flex flex-col sm:flex-row gap-2 w-full">
                        <Link
                          href={`/admin/weddings/${wedding._id}`}
                          className="w-full sm:w-auto px-4 py-2 text-sm bg-wedding-rose text-white rounded-lg hover:bg-opacity-90 transition-colors text-center"
                        >
                          Configure
                        </Link>
                        <button
                          onClick={() => handleEdit(wedding)}
                          className="w-full sm:w-auto px-4 py-2 text-sm bg-wedding-sage text-white rounded-lg hover:bg-opacity-90 transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(wedding._id)}
                          className="w-full sm:w-auto px-4 py-2 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
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
    </div>
  );
}