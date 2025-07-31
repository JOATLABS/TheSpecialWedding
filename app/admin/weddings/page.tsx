'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useAdmin } from '../../contexts/AdminContext';

interface Wedding {
  id: string;
  couple_names: string;
  date: string;
  slug: string;
  events?: Array<{
    type: string;
    date: string;
  }>;
}

interface WeddingForm {
  couple_names: string;
  date: string;
  slug: string;
  events: Array<{
    type: string;
    date: string;
  }>;
}

export default function AdminWeddingsPage() {
  const { token } = useAdmin();
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  
  const [formData, setFormData] = useState<WeddingForm>({
    couple_names: '',
    date: '',
    slug: '',
    events: []
  });

  useEffect(() => {
    fetchWeddings();
  }, []);

  const fetchWeddings = async () => {
    setLoading(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/weddings`);
      if (!response.ok) {
        throw new Error('Failed to fetch weddings');
      }
      const data = await response.json();
      // Ensure data is an array
      setWeddings(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Error fetching weddings:', err);
      setError('Failed to load weddings');
      setWeddings([]); // Set to empty array on error
    } finally {
      setLoading(false);
    }
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
      events: wedding.events || []
    });
    setEditingId(wedding.id);
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
    <div className="min-h-screen bg-gradient-to-br from-wedding-ivory to-rose-50 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden mb-8">
          <div className="bg-gradient-to-r from-wedding-navy to-wedding-gold px-8 py-6">
            <div className="flex justify-between items-center">
              <div>
                <h1 className="text-3xl font-bold text-white">Wedding Management</h1>
                <p className="text-blue-100 mt-2">Create and manage wedding events</p>
              </div>
              <button
                onClick={() => {
                  setShowForm(!showForm);
                  setEditingId(null);
                  setFormData({
                    couple_names: '',
                    date: '',
                    slug: '',
                    events: []
                  });
                }}
                className="bg-white text-wedding-navy px-6 py-3 rounded-lg font-semibold hover:bg-wedding-ivory transition-colors"
              >
                {showForm ? 'Cancel' : 'Create Wedding'}
              </button>
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
            <div className="p-8">
              <h2 className="text-2xl font-bold text-wedding-navy mb-6">
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
                    <div key={index} className="flex gap-4 mb-3">
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
                        className="px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
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
          <div className="p-8">
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
                  <div key={wedding.id || wedding._id} className="border border-gray-200 rounded-xl p-6 hover:shadow-lg transition-shadow">
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <h3 className="text-xl font-bold text-wedding-navy">{wedding.couple_names}</h3>
                        <p className="text-gray-600 mt-1">Date: {wedding.date}</p>
                        <p className="text-sm text-gray-500 mt-1">
                          URL: thespecialwedding.com/{wedding.slug}
                        </p>
                        {wedding.events && wedding.events.length > 0 && (
                          <div className="mt-3">
                            <p className="text-sm font-medium text-gray-700">Events:</p>
                            <div className="flex flex-wrap gap-2 mt-1">
                              {wedding.events.map((event, index) => (
                                <span 
                                  key={index}
                                  className="inline-flex px-3 py-1 text-xs font-semibold rounded-full bg-wedding-sage bg-opacity-20 text-wedding-navy"
                                >
                                  {event.type.replace('_', ' ')} - {event.date}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                      <div className="flex gap-2 ml-4">
                        <Link
                          href={`/admin/weddings/${wedding.id || wedding._id}`}
                          className="px-4 py-2 text-sm bg-wedding-rose text-white rounded-lg hover:bg-opacity-90 transition-colors"
                        >
                          Configure
                        </Link>
                        <button
                          onClick={() => handleEdit(wedding)}
                          className="px-4 py-2 text-sm bg-wedding-sage text-white rounded-lg hover:bg-opacity-90 transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(wedding.id || wedding._id)}
                          className="px-4 py-2 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
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