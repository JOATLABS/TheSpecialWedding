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
  plus_one_allowed: boolean;
}

interface MessageLog {
  phone: string;
  guest_id: string;
  message: string;
  target_type: 'guest' | 'plus-one';
  event_type: string;
  status: string;
  sent_at: string;
}

export default function AdminRemindersPage() {
  const { token } = useAdmin();
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [selectedWedding, setSelectedWedding] = useState<string>('');
  const [guests, setGuests] = useState<Guest[]>([]);
  const [messageHistory, setMessageHistory] = useState<MessageLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [success, setSuccess] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'invites' | 'reminders' | 'individual' | 'history'>('invites');

  // Form states
  const [eventType, setEventType] = useState<string>('traditional');
  const [targetGroup, setTargetGroup] = useState<string>('guests');
  const [customMessage, setCustomMessage] = useState<string>('');
  const [inviteMessage, setInviteMessage] = useState<string>('');
  const [selectedGuests, setSelectedGuests] = useState<string[]>([]);

  useEffect(() => {
    fetchWeddings();
    if (token) {
      fetchMessageHistory();
    }
  }, [token]);

  useEffect(() => {
    if (selectedWedding && token) {
      fetchGuests();
    }
  }, [selectedWedding, token]);

  const fetchWeddings = async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/weddings`);
      const data = await response.json();
      setWeddings(Array.isArray(data) ? data : []);
    } catch (err) {
      setError('Failed to load weddings');
    }
  };

  const fetchGuests = async () => {
    if (!selectedWedding || !token) return;
    
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(
        `${baseUrl}/admin/guests?wedding_id=${selectedWedding}`,
        {
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );
      
      if (!response.ok) {
        console.error('Failed to fetch guests:', response.status);
        return;
      }
      
      const data = await response.json();
      console.log('Fetched guests:', data.length, 'guests');
      setGuests(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load guests:', err);
    }
  };

  const fetchMessageHistory = async () => {
    if (!token) return;
    
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/admin/reminders/logs`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      
      if (!response.ok) {
        console.error('Failed to fetch message history:', response.status);
        return;
      }
      
      const data = await response.json();
      setMessageHistory(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load message history:', err);
    }
  };

  const handleSendInviteLinks = async () => {
    if (!selectedWedding) {
      setError('Please select a wedding');
      return;
    }

    const selectedWeddingData = weddings.find(w => (w.id || w._id) === selectedWedding);
    if (!selectedWeddingData?.slug) {
      setError('Wedding slug not found');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/admin/admin/reminders/send-personalized-links`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          slug: selectedWeddingData.slug,
          custom_message: inviteMessage.trim() || null
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to send invites');
      }

      const result = await response.json();
      setSuccess(`Successfully sent ${result.sent} invite links!`);
      fetchMessageHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send invites');
    } finally {
      setLoading(false);
    }
  };

  const handleSendEventReminder = async () => {
    if (!customMessage.trim()) {
      setError('Please enter a message');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const params = new URLSearchParams({
        event_type: eventType,
        message: customMessage,
        target_group: targetGroup,
      });

      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/admin/reminders/send?${params}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to send reminders');
      }

      const result = await response.json();
      if (result.sent === 0) {
        setError('No reminders sent. Make sure guests have RSVP\'d for the selected event type.');
      } else {
        setSuccess(`Successfully sent ${result.sent} reminders!`);
        setCustomMessage('');
        fetchMessageHistory();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send reminders');
    } finally {
      setLoading(false);
    }
  };

  const handleSendIndividualMessage = async () => {
    if (!customMessage.trim() || selectedGuests.length === 0) {
      setError('Please select guests and enter a message');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/admin/reminders/send`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          guest_tokens: selectedGuests,
          message: customMessage,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to send messages');
      }

      setSuccess(`Successfully sent messages to ${selectedGuests.length} guests!`);
      setCustomMessage('');
      setSelectedGuests([]);
      fetchMessageHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send messages');
    } finally {
      setLoading(false);
    }
  };

  const selectedWeddingData = weddings.find(w => (w.id || w._id) === selectedWedding);
  const guestsWithPhone = guests.filter(g => g.phone && g.phone.trim() !== '');
  console.log('All guests:', guests);
  console.log('Guests with phone:', guestsWithPhone);
  console.log('Selected wedding:', selectedWedding);
  console.log('Token exists:', !!token);

  return (
    <div className="min-h-screen bg-wedding-ivory p-4 sm:p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden mb-8">
          <div className="bg-gradient-to-r from-wedding-navy to-wedding-gold px-8 py-6">
            <h1 className="text-3xl font-bold text-white">SMS Reminders & Invites</h1>
            <p className="text-blue-100 mt-2">Send invitations and reminders via SMS using Twilio</p>
          </div>
        </div>

        {/* Wedding Selection */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <label htmlFor="wedding" className="block text-sm font-medium text-gray-700 mb-2">
            Select Wedding
          </label>
          <select
            id="wedding"
            value={selectedWedding}
            onChange={(e) => setSelectedWedding(e.target.value)}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
          >
            <option value="">Choose a wedding...</option>
            {weddings.map((wedding) => (
              <option key={wedding.id || wedding._id} value={wedding.id || wedding._id}>
                {wedding.couple_names} - {wedding.date}
              </option>
            ))}
          </select>
        </div>

        {/* Status Messages */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-700">{error}</p>
          </div>
        )}
        {success && (
          <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
            <p className="text-green-700">{success}</p>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-4 mb-8">
          <button
            onClick={() => setActiveTab('invites')}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              activeTab === 'invites'
                ? 'bg-wedding-navy text-white'
                : 'bg-white text-wedding-navy hover:bg-wedding-ivory'
            }`}
          >
            Send Invites
          </button>
          <button
            onClick={() => setActiveTab('reminders')}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              activeTab === 'reminders'
                ? 'bg-wedding-navy text-white'
                : 'bg-white text-wedding-navy hover:bg-wedding-ivory'
            }`}
          >
            Event Reminders
          </button>
          <button
            onClick={() => setActiveTab('individual')}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              activeTab === 'individual'
                ? 'bg-wedding-navy text-white'
                : 'bg-white text-wedding-navy hover:bg-wedding-ivory'
            }`}
          >
            Individual Messages
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              activeTab === 'history'
                ? 'bg-wedding-navy text-white'
                : 'bg-white text-wedding-navy hover:bg-wedding-ivory'
            }`}
          >
            Message History ({messageHistory.length})
          </button>
        </div>

        {/* Send Invite Links Tab */}
        {activeTab === 'invites' && (
          <div className="bg-white rounded-xl shadow-lg p-4 sm:p-6 md:p-8">
            <h2 className="text-2xl font-bold text-wedding-navy mb-6">Send Wedding Invitations</h2>
            
            {selectedWedding ? (
              <div className="space-y-6">
                <div className="p-6 bg-wedding-ivory rounded-lg">
                  <h3 className="font-semibold text-wedding-navy mb-2">Wedding Details:</h3>
                  <p className="text-wedding-navy">{selectedWeddingData?.couple_names}</p>
                  <p className="text-sm text-gray-600">Date: {selectedWeddingData?.date}</p>
                  <p className="text-sm text-gray-600">Slug: {selectedWeddingData?.slug}</p>
                  <p className="text-sm text-gray-600">Guests with phone numbers: {guestsWithPhone.length}</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Custom Invitation Message (Optional)
                  </label>
                  <textarea
                    value={inviteMessage}
                    onChange={(e) => setInviteMessage(e.target.value)}
                    placeholder="Enter custom invitation message..."
                    rows={3}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  />
                  <p className="text-sm text-gray-500 mt-1">
                    Use {"{url}"} for the RSVP link and {"{name}"} for the guest's name. Leave empty to use default message.
                  </p>
                </div>

                <div className="p-6 bg-blue-50 rounded-lg">
                  <h4 className="font-medium text-blue-900 mb-2">Message Preview:</h4>
                  <p className="text-blue-700 text-sm">
                    {inviteMessage.trim() ? (
                      <>"{inviteMessage.replace('{url}', `https://thespecialwedding.com/${selectedWeddingData?.slug}/invite/[token]`).replace('{name}', '[Guest Name]')}"</>
                    ) : (
                      <>"You're invited! RSVP here: https://thespecialwedding.com/{selectedWeddingData?.slug}/invite/[token]"</>
                    )}
                  </p>
                </div>

                <button
                  onClick={handleSendInviteLinks}
                  disabled={loading || !selectedWedding}
                  className="w-full bg-gradient-to-r from-wedding-sage to-wedding-gold text-white py-3 px-6 rounded-lg font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                >
                  {loading ? 'Sending...' : `Send Invites to ${guestsWithPhone.length} Guests`}
                </button>
              </div>
            ) : (
              <p className="text-gray-500">Please select a wedding to send invitations.</p>
            )}
          </div>
        )}

        {/* Event Reminders Tab */}
        {activeTab === 'reminders' && (
          <div className="bg-white rounded-xl shadow-lg p-4 sm:p-6 md:p-8">
            <h2 className="text-2xl font-bold text-wedding-navy mb-6">Send Event Reminders</h2>
            
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Event Type</label>
                  <select
                    value={eventType}
                    onChange={(e) => setEventType(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  >
                    <option value="traditional">Traditional</option>
                    <option value="white_wedding">White Wedding</option>
                    <option value="reception">Reception</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Target Audience</label>
                  <select
                    value={targetGroup}
                    onChange={(e) => setTargetGroup(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  >
                    <option value="guests">Guests Only</option>
                    <option value="plus-ones">Plus-Ones Only</option>
                    <option value="all">All (Guests + Plus-Ones)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Custom Message</label>
                <textarea
                  value={customMessage}
                  onChange={(e) => setCustomMessage(e.target.value)}
                  placeholder="Enter your reminder message..."
                  rows={4}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                />
                <p className="text-sm text-gray-500 mt-1">
                  This will be sent to guests who have RSVP'd for the {eventType.replace('_', ' ')} event.
                </p>
                <p className="text-sm text-yellow-600 mt-1">
                  💡 Note: If no messages are sent, guests may not have RSVP'd yet. Use "Send Invites" first to get responses.
                </p>
              </div>

              <button
                onClick={handleSendEventReminder}
                disabled={loading || !customMessage.trim()}
                className="w-full bg-gradient-to-r from-wedding-rose to-wedding-gold text-white py-3 px-6 rounded-lg font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
              >
                {loading ? 'Sending...' : 'Send Event Reminder'}
              </button>
            </div>
          </div>
        )}

        {/* Individual Messages Tab */}
        {activeTab === 'individual' && (
          <div className="bg-white rounded-xl shadow-lg p-4 sm:p-6 md:p-8">
            <h2 className="text-2xl font-bold text-wedding-navy mb-6">Send Individual Messages</h2>
            
            {selectedWedding ? (
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Select Guests ({selectedGuests.length} selected)
                  </label>
                  <div className="max-h-64 overflow-y-auto border border-gray-300 rounded-lg p-4">
                    {guestsWithPhone.map((guest) => (
                      <label key={guest.id || guest._id} className="flex items-center space-x-3 py-2">
                        <input
                          type="checkbox"
                          checked={selectedGuests.includes(guest.token)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedGuests([...selectedGuests, guest.token]);
                            } else {
                              setSelectedGuests(selectedGuests.filter(token => token !== guest.token));
                            }
                          }}
                          className="rounded border-gray-300 text-wedding-rose focus:ring-wedding-rose"
                        />
                        <span className="text-sm">
                          {guest.name} ({guest.phone})
                        </span>
                      </label>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Message</label>
                  <textarea
                    value={customMessage}
                    onChange={(e) => setCustomMessage(e.target.value)}
                    placeholder="Enter your custom message..."
                    rows={4}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  />
                </div>

                <button
                  onClick={handleSendIndividualMessage}
                  disabled={loading || !customMessage.trim() || selectedGuests.length === 0}
                  className="w-full bg-gradient-to-r from-wedding-navy to-wedding-sage text-white py-3 px-6 rounded-lg font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                >
                  {loading ? 'Sending...' : `Send Message to ${selectedGuests.length} Guest(s)`}
                </button>
              </div>
            ) : (
              <p className="text-gray-500">Please select a wedding to send individual messages.</p>
            )}
          </div>
        )}

        {/* Message History Tab */}
        {activeTab === 'history' && (
          <div className="bg-white rounded-xl shadow-lg p-4 sm:p-6 md:p-8">
            <h2 className="text-2xl font-bold text-wedding-navy mb-6">Message History</h2>
            
            {messageHistory.length === 0 ? (
              <p className="text-gray-500">No messages sent yet.</p>
            ) : (
              <>
                {/* Mobile Card View */}
                <div className="md:hidden space-y-4">
                  {messageHistory.map((log, index) => (
                    <div key={index} className="bg-gray-50 rounded-lg p-4 space-y-2">
                      <div className="flex justify-between items-start">
                        <div className="text-xs text-gray-500">
                          {new Date(log.sent_at).toLocaleString()}
                        </div>
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          log.status === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                        }`}>
                          {log.status}
                        </span>
                      </div>
                      <div className="font-semibold text-sm">{log.phone}</div>
                      <div className="flex gap-2">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          log.target_type === 'guest' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'
                        }`}>
                          {log.target_type}
                        </span>
                        <span className="text-xs text-gray-600">{log.event_type}</span>
                      </div>
                      <div className="text-sm text-gray-700 break-words">{log.message}</div>
                    </div>
                  ))}
                </div>

                {/* Desktop Table View */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Date/Time
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Phone
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Type
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Event
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Status
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Message
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {messageHistory.map((log, index) => (
                        <tr key={index}>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {new Date(log.sent_at).toLocaleString()}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {log.phone}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                              log.target_type === 'guest' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'
                            }`}>
                              {log.target_type}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {log.event_type}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                              log.status === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                            }`}>
                              {log.status}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-900 max-w-xs truncate">
                            {log.message}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}