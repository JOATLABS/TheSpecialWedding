'use client';

import { useState, useEffect } from 'react';
import { useAdmin } from '../../contexts/AdminContext';

interface Wedding {
  id?: string;
  _id?: string;
  couple_names: string;
  date: string;
  slug: string;
  events?: Array<{
    type: string;
    date: string;
  }>;
}

interface Guest {
  id?: string;
  _id?: string;
  wedding_id: string;
  name: string;
  token: string;
  phone?: string;
  email?: string;
  role: string;
  group_id?: string;
  plus_one_allowed: boolean;
  number_of_plus_ones_allowed?: number;
  plus_one_submitted: boolean;
  created_at?: string;
  updated_at?: string;
}

interface RSVP {
  _id?: string;
  guest_id: string;
  attending: string[];
  dietary?: string;
  submitted_at: string;
}

interface PlusOne {
  _id?: string;
  guest_id: string;
  name: string;
  dietary?: string;
  attending: string[];
}

export default function AdminGuestsPage() {
  const { token } = useAdmin();
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [selectedWedding, setSelectedWedding] = useState<string>('');
  const [guests, setGuests] = useState<Guest[]>([]);
  const [rsvps, setRsvps] = useState<RSVP[]>([]);
  const [plusOnes, setPlusOnes] = useState<PlusOne[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'all' | 'rsvp' | 'pending'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedGuest, setExpandedGuest] = useState<string | null>(null);
  const [editingGuest, setEditingGuest] = useState<Guest | null>(null);
  const [editForm, setEditForm] = useState({
    name: '',
    email: '',
    phone: '',
    role: 'guest',
    plus_one_allowed: false,
    number_of_plus_ones_allowed: 0
  });
  const [showAddModal, setShowAddModal] = useState(false);
  const [addForm, setAddForm] = useState({
    name: '',
    email: '',
    phone: '',
    role: 'guest',
    plus_one_allowed: false,
    number_of_plus_ones_allowed: 0
  });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetchWeddings();
  }, []);

  useEffect(() => {
    if (selectedWedding) {
      fetchGuestData();
    }
  }, [selectedWedding]);

  const fetchWeddings = async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/admin/weddings`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      const data = await response.json();
      setWeddings(Array.isArray(data) ? data : []);
    } catch (err) {
      setError('Failed to load weddings');
    }
  };

  const fetchGuestData = async () => {
    setLoading(true);
    try {
      // Fetch guests
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const guestsResponse = await fetch(
        `${baseUrl}/admin/guests?wedding_id=${selectedWedding}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        }
      );
      
      if (!guestsResponse.ok) {
        console.error('Failed to fetch guests:', guestsResponse.status);
        throw new Error('Failed to fetch guests');
      }
      
      const guestsData = await guestsResponse.json();
      console.log('Guests data:', guestsData); // Debug log
      console.log('Selected wedding ID:', selectedWedding); // Debug log
      setGuests(Array.isArray(guestsData) ? guestsData : []);

      // Fetch RSVPs
      try {
        const rsvpsResponse = await fetch(
          `${baseUrl}/admin/rsvps?wedding_id=${selectedWedding}`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          }
        );
        if (rsvpsResponse.ok) {
          const rsvpsData = await rsvpsResponse.json();
          console.log('RSVPs data:', rsvpsData); // Debug log
          setRsvps(Array.isArray(rsvpsData) ? rsvpsData : []);
        } else {
          console.log('RSVPs endpoint failed:', rsvpsResponse.status);
          setRsvps([]);
        }
      } catch (rsvpError) {
        console.log('RSVPs fetch error:', rsvpError);
        setRsvps([]);
      }

      // Fetch plus ones for all guests
      try {
        const plusOnesResponse = await Promise.all(
          guests.map(async (guest: any) => {
            try {
              const response = await fetch(`${baseUrl}/plus_one/plus-ones/${guest.id}`, {
                headers: {
                  'Authorization': `Bearer ${token}`,
                  'Content-Type': 'application/json',
                },
              });
              
              if (response.ok) {
                const guestPlusOnes = await response.json();
                return guestPlusOnes.map((po: any) => ({
                  ...po,
                  guest_id: guest.id,
                  guest_name: guest.name
                }));
              }
              return [];
            } catch (error) {
              console.log(`Plus-ones fetch error for guest ${guest.id}:`, error);
              return [];
            }
          })
        );
        
        // Flatten the array of arrays
        const allPlusOnes = plusOnesResponse.flat();
        setPlusOnes(allPlusOnes);
        console.log('Plus-ones loaded:', allPlusOnes.length);
      } catch (error) {
        console.log('Plus-ones fetch error:', error);
        setPlusOnes([]);
      }
      
    } catch (err) {
      console.error('Error fetching data:', err);
      setError('Failed to load guest data');
    } finally {
      setLoading(false);
    }
  };

  const handleSendReminder = async (guestId: string) => {
    try {
      const guest = guests.find(g => (g.id || g._id) === guestId);
      if (!guest) return;
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/admin/reminders/send`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          guest_tokens: [guest.token],
          message: `Hi ${guest.name}, please RSVP for the wedding!`,
        }),
      });

      if (response.ok) {
        alert('Reminder sent successfully!');
      } else {
        throw new Error('Failed to send reminder');
      }
    } catch (err) {
      alert('Failed to send reminder');
    }
  };

  const handleEditGuest = (guest: Guest) => {
    setEditingGuest(guest);
    setEditForm({
      name: guest.name,
      email: guest.email || '',
      phone: guest.phone || '',
      role: guest.role,
      plus_one_allowed: guest.plus_one_allowed,
      number_of_plus_ones_allowed: guest.number_of_plus_ones_allowed || 0
    });
  };

  const handleSaveGuest = async () => {
    if (!editingGuest) return;
    
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/admin/guests/${editingGuest.id || editingGuest._id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(editForm),
      });
      
      if (response.ok) {
        setEditingGuest(null);
        fetchGuestData(); // Refresh all data
      } else {
        setError('Failed to update guest');
      }
    } catch (err) {
      setError('Failed to update guest');
    }
  };

  const handleDeleteGuest = async (guestId: string) => {
    if (!confirm('Are you sure you want to delete this guest? This will also delete their RSVP and plus-ones.')) return;

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/admin/guests/${guestId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        fetchGuestData(); // Refresh all data
      } else {
        setError('Failed to delete guest');
      }
    } catch (err) {
      setError('Failed to delete guest');
    }
  };

  const handleCreateGuest = async () => {
    if (!selectedWedding) return;

    setCreating(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const guestData = {
        ...addForm,
        wedding_id: selectedWedding
      };

      const response = await fetch(`${baseUrl}/admin/guests`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(guestData),
      });

      if (response.ok) {
        setShowAddModal(false);
        setAddForm({
          name: '',
          email: '',
          phone: '',
          role: 'guest',
          plus_one_allowed: false,
          number_of_plus_ones_allowed: 0
        });
        fetchGuestData(); // Refresh all data
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to create guest');
      }
    } catch (err) {
      setError('Failed to create guest');
    } finally {
      setCreating(false);
    }
  };

  // Helper function to normalize ID comparison
  const normalizeId = (id: string | undefined) => {
    return id?.toString() || '';
  };

  // Filter guests based on tab and search
  const filteredGuests = guests.filter(guest => {
    const matchesSearch = guest.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         guest.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         guest.phone?.includes(searchTerm);
    
    if (!matchesSearch) return false;

    const guestId = normalizeId(guest.id || guest._id);
    const hasRSVP = rsvps.some(r => {
      const rsvpGuestId = normalizeId(r.guest_id);
      return rsvpGuestId === guestId;
    });
    
    switch (activeTab) {
      case 'rsvp':
        return hasRSVP;
      case 'pending':
        return !hasRSVP;
      default:
        return true;
    }
  });

  const getRSVPForGuest = (guestId: string) => {
    const normalizedGuestId = normalizeId(guestId);
    return rsvps.find(r => normalizeId(r.guest_id) === normalizedGuestId);
  };

  const getPlusOnesForGuest = (guestId: string) => {
    const normalizedGuestId = normalizeId(guestId);
    return plusOnes.filter(p => normalizeId(p.guest_id) === normalizedGuestId);
  };

  const selectedWeddingData = weddings.find(w => (w.id || w._id) === selectedWedding);

  return (
    <div className="min-h-screen bg-gradient-to-br from-wedding-ivory to-rose-50 dark:from-gray-900 dark:to-gray-800 p-4 sm:p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl overflow-hidden mb-8">
          <div className="bg-gradient-to-r from-wedding-navy to-wedding-gold px-4 sm:px-8 py-6">
            <h1 className="text-2xl sm:text-3xl font-bold text-white">Guest Management</h1>
            <p className="text-blue-100 dark:text-blue-200 mt-2">View and manage all wedding guests, RSVPs, and plus-ones</p>
          </div>
        </div>

        {/* Wedding Selection */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 mb-6">
          <label htmlFor="wedding" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Select Wedding
          </label>
          <select
            id="wedding"
            value={selectedWedding}
            onChange={(e) => setSelectedWedding(e.target.value)}
            className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
          >
            <option value="">Choose a wedding...</option>
            {weddings.map((wedding) => (
              <option key={wedding.id || wedding._id} value={wedding.id || wedding._id}>
                {wedding.couple_names} - {wedding.date}
              </option>
            ))}
          </select>
        </div>

        {selectedWedding && (
          <>
            {/* Stats Overview */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Guests</h3>
                <p className="text-3xl font-bold text-wedding-navy dark:text-gray-100 mt-2">{guests.length}</p>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">RSVPs Received</h3>
                <p className="text-3xl font-bold text-green-600 dark:text-green-400 mt-2">{rsvps.length}</p>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Pending RSVPs</h3>
                <p className="text-3xl font-bold text-orange-600 dark:text-orange-400 mt-2">{guests.length - rsvps.length}</p>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Plus Ones</h3>
                <p className="text-3xl font-bold text-wedding-sage dark:text-green-400 mt-2">{plusOnes.length}</p>
              </div>
            </div>

            {/* Controls */}
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 mb-8">
              <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
                {/* Tabs */}
                <div className="flex gap-2">
                  <button
                    onClick={() => setActiveTab('all')}
                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                      activeTab === 'all'
                        ? 'bg-wedding-navy text-white'
                        : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-500'
                    }`}
                  >
                    All Guests ({guests.length})
                  </button>
                  <button
                    onClick={() => setActiveTab('rsvp')}
                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                      activeTab === 'rsvp'
                        ? 'bg-wedding-navy text-white'
                        : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-500'
                    }`}
                  >
                    RSVP'd ({rsvps.length})
                  </button>
                  <button
                    onClick={() => setActiveTab('pending')}
                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                      activeTab === 'pending'
                        ? 'bg-wedding-navy text-white'
                        : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-500'
                    }`}
                  >
                    Pending ({guests.length - rsvps.length})
                  </button>
                </div>

                {/* Search and Add Guest */}
                <div className="flex gap-3">
                  <input
                    type="text"
                    placeholder="Search guests..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="px-4 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  />
                  <button
                    onClick={() => setShowAddModal(true)}
                    className="px-4 py-2 bg-wedding-rose text-white rounded-lg hover:bg-wedding-rose/90 transition-colors font-medium"
                  >
                    Add Guest
                  </button>
                </div>
              </div>
            </div>

            {/* Guest List */}
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg overflow-hidden">
              {loading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="animate-spin h-8 w-8 border-4 border-wedding-rose border-t-transparent rounded-full"></div>
                  <span className="ml-3 text-gray-600 dark:text-gray-300">Loading guests...</span>
                </div>
              ) : filteredGuests.length === 0 ? (
                <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                  <p>No guests found.</p>
                </div>
              ) : (
                <div className="divide-y divide-gray-200 dark:divide-gray-700">
                  {filteredGuests.map((guest) => {
                    const guestId = guest.id || guest._id || '';
                    const rsvp = getRSVPForGuest(guestId);
                    const guestPlusOnes = getPlusOnesForGuest(guestId);
                    const isExpanded = expandedGuest === guestId;

                    return (
                      <div key={guestId} className="hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
                        {/* Guest Row */}
                        <div className="p-6">
                          <div className="flex items-center justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-4">
                                <div>
                                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{guest.name}</h3>
                                  <div className="flex gap-4 text-sm text-gray-600 dark:text-gray-300 mt-1">
                                    {guest.email && <span>{guest.email}</span>}
                                    {guest.phone && <span>{guest.phone}</span>}
                                  </div>
                                </div>
                                <span className={`px-3 py-1 text-xs font-semibold rounded-full ${
                                  guest.role === 'admin' ? 'bg-purple-100 dark:bg-purple-900 text-purple-800 dark:text-purple-200' : 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200'
                                }`}>
                                  {guest.role}
                                </span>
                                {rsvp && (
                                  <span className="px-3 py-1 text-xs font-semibold rounded-full bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200">
                                    RSVP'd
                                  </span>
                                )}
                              </div>

                              {/* RSVP Details */}
                              {rsvp && (
                                <div className="mt-3 p-3 bg-gray-50 dark:bg-gray-600 rounded-lg">
                                  <div className="flex gap-6 text-sm">
                                    <div>
                                      <span className="font-medium text-gray-700 dark:text-gray-200">Attending:</span>
                                      <span className="ml-2">{rsvp.attending.join(', ')}</span>
                                    </div>
                                    {rsvp.dietary && (
                                      <div>
                                        <span className="font-medium text-gray-700 dark:text-gray-200">Dietary:</span>
                                        <span className="ml-2">{rsvp.dietary}</span>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              )}

                              {/* Plus One Status */}
                              {guest.plus_one_allowed && (
                                <div className="mt-2 text-sm text-gray-600 dark:text-gray-300">
                                  Plus Ones: {guestPlusOnes.length} / {guest.number_of_plus_ones_allowed || 0}
                                </div>
                              )}
                            </div>

                            {/* Actions */}
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => setExpandedGuest(isExpanded ? null : guestId)}
                                className="px-3 py-1 text-sm bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-500 transition-colors"
                              >
                                {isExpanded ? 'Hide' : 'Details'}
                              </button>
                              <button
                                onClick={() => handleEditGuest(guest)}
                                className="px-3 py-1 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                              >
                                Edit
                              </button>
                              {!rsvp && (
                                <button
                                  onClick={() => handleSendReminder(guestId)}
                                  className="px-3 py-1 text-sm bg-wedding-sage text-white rounded-lg hover:bg-opacity-90 transition-colors"
                                >
                                  Send Reminder
                                </button>
                              )}
                              <button
                                onClick={() => handleDeleteGuest(guestId)}
                                className="px-3 py-1 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
                              >
                                Delete
                              </button>
                            </div>
                          </div>
                        </div>

                        {/* Expanded Details */}
                        {isExpanded && (
                          <div className="px-6 pb-6">
                            <div className="border-t pt-4 grid grid-cols-1 md:grid-cols-2 gap-6">
                              {/* Guest Info */}
                              <div>
                                <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-2">Guest Information</h4>
                                <dl className="space-y-1 text-sm">
                                  <div>
                                    <dt className="inline font-medium text-gray-700 dark:text-gray-200">Token:</dt>
                                    <dd className="inline ml-2 font-mono text-xs bg-gray-100 dark:bg-gray-600 px-2 py-1 rounded">
                                      {guest.token}
                                    </dd>
                                  </div>
                                  {guest.group_id && (
                                    <div>
                                      <dt className="inline font-medium text-gray-700 dark:text-gray-200">Group:</dt>
                                      <dd className="inline ml-2">{guest.group_id}</dd>
                                    </div>
                                  )}
                                  <div>
                                    <dt className="inline font-medium text-gray-700 dark:text-gray-200">Plus Ones Allowed:</dt>
                                    <dd className="inline ml-2">
                                      {guest.plus_one_allowed ? `Yes (${guest.number_of_plus_ones_allowed || 0})` : 'No'}
                                    </dd>
                                  </div>
                                </dl>
                              </div>

                              {/* Plus Ones List */}
                              {guest.plus_one_allowed && guestPlusOnes.length > 0 && (
                                <div>
                                  <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-2">Plus Ones</h4>
                                  <ul className="space-y-2">
                                    {guestPlusOnes.map((plusOne, idx) => (
                                      <li key={plusOne._id || idx} className="text-sm bg-gray-50 dark:bg-gray-600 p-2 rounded">
                                        <div className="font-medium">{plusOne.name}</div>
                                        <div className="text-gray-600 dark:text-gray-300">
                                          Attending: {plusOne.attending.join(', ')}
                                          {plusOne.dietary && ` • Dietary: ${plusOne.dietary}`}
                                        </div>
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>

                            {/* Wedding Events for this guest */}
                            {selectedWeddingData?.events && (
                              <div className="mt-4">
                                <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-2">Wedding Events</h4>
                                <div className="flex gap-2">
                                  {selectedWeddingData.events.map((event, idx) => (
                                    <span
                                      key={idx}
                                      className={`px-3 py-1 text-xs rounded-full ${
                                        rsvp?.attending.includes(event.type)
                                          ? 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200'
                                          : 'bg-gray-100 dark:bg-gray-600 text-gray-600 dark:text-gray-300'
                                      }`}
                                    >
                                      {event.type.replace('_', ' ')} - {event.date}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </>
        )}
        
        {/* Edit Guest Modal */}
        {editingGuest && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl max-w-md w-full p-6 border border-gray-200 dark:border-gray-700">
              <h2 className="text-2xl font-bold text-wedding-navy dark:text-gray-100 mb-4">Edit Guest</h2>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name</label>
                  <input
                    type="text"
                    value={editForm.name}
                    onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
                  <input
                    type="email"
                    value={editForm.email}
                    onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Phone</label>
                  <input
                    type="tel"
                    value={editForm.phone}
                    onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Role</label>
                  <select
                    value={editForm.role}
                    onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  >
                    <option value="guest">Guest</option>
                    <option value="admin">Admin</option>
                    <option value="groom">Groom</option>
                    <option value="bride">Bride</option>
                  </select>
                </div>
                
                <div>
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={editForm.plus_one_allowed}
                      onChange={(e) => setEditForm({ ...editForm, plus_one_allowed: e.target.checked })}
                      className="rounded text-wedding-rose focus:ring-wedding-rose"
                    />
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-200">Allow Plus Ones</span>
                  </label>
                </div>
                
                {editForm.plus_one_allowed && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Number of Plus Ones Allowed</label>
                    <input
                      type="number"
                      min="0"
                      max="10"
                      value={editForm.number_of_plus_ones_allowed}
                      onChange={(e) => setEditForm({ ...editForm, number_of_plus_ones_allowed: parseInt(e.target.value) || 0 })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    />
                  </div>
                )}
              </div>
              
              <div className="flex gap-3 mt-6">
                <button
                  onClick={handleSaveGuest}
                  className="flex-1 bg-wedding-navy text-white px-4 py-2 rounded-lg hover:bg-opacity-90 transition-colors"
                >
                  Save Changes
                </button>
                <button
                  onClick={() => setEditingGuest(null)}
                  className="flex-1 bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 px-4 py-2 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-500 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Add Guest Modal */}
        {showAddModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
              <div className="p-6">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Add New Guest</h2>
                  <button
                    onClick={() => setShowAddModal(false)}
                    className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                  >
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <form onSubmit={(e) => { e.preventDefault(); handleCreateGuest(); }} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Name <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={addForm.name}
                      onChange={(e) => setAddForm({ ...addForm, name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                      placeholder="Enter guest name"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Email
                    </label>
                    <input
                      type="email"
                      value={addForm.email}
                      onChange={(e) => setAddForm({ ...addForm, email: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                      placeholder="Enter email address"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Phone Number
                    </label>
                    <input
                      type="tel"
                      value={addForm.phone}
                      onChange={(e) => setAddForm({ ...addForm, phone: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                      placeholder="Enter phone number"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Role
                    </label>
                    <select
                      value={addForm.role}
                      onChange={(e) => setAddForm({ ...addForm, role: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    >
                      <option value="guest">Guest</option>
                      <option value="family">Family</option>
                      <option value="friend">Friend</option>
                      <option value="colleague">Colleague</option>
                    </select>
                  </div>

                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      id="plus_one_allowed"
                      checked={addForm.plus_one_allowed}
                      onChange={(e) => setAddForm({
                        ...addForm,
                        plus_one_allowed: e.target.checked,
                        number_of_plus_ones_allowed: e.target.checked ? addForm.number_of_plus_ones_allowed : 0
                      })}
                      className="rounded border-gray-300 dark:border-gray-600 text-wedding-rose focus:ring-wedding-rose"
                    />
                    <label htmlFor="plus_one_allowed" className="text-sm text-gray-700 dark:text-gray-300">
                      Allow plus ones
                    </label>
                  </div>

                  {addForm.plus_one_allowed && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Number of Plus Ones Allowed
                      </label>
                      <input
                        type="number"
                        min="0"
                        max="5"
                        value={addForm.number_of_plus_ones_allowed}
                        onChange={(e) => setAddForm({ ...addForm, number_of_plus_ones_allowed: parseInt(e.target.value) || 0 })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-md focus:outline-none focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                      />
                    </div>
                  )}

                  <div className="text-sm text-gray-600 dark:text-gray-400 bg-blue-50 dark:bg-blue-900/20 p-3 rounded-md">
                    <strong>Note:</strong> At least one contact method (email or phone) is required.
                  </div>

                  {error && (
                    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                      <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
                    </div>
                  )}

                  <div className="flex space-x-3 pt-4">
                    <button
                      type="button"
                      onClick={() => setShowAddModal(false)}
                      className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={creating || !addForm.name || (!addForm.email && !addForm.phone)}
                      className="flex-1 px-4 py-2 bg-wedding-rose text-white rounded-lg hover:bg-wedding-rose/90 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                    >
                      {creating ? 'Creating...' : 'Create Guest'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}