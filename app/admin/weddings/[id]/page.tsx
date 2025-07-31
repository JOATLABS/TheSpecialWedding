'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAdmin } from '../../../contexts/AdminContext';
import { Wedding, WeddingEvent, RegistryItem, FAQItem } from '@/types/wedding';

export default function WeddingDetailsPage() {
  const { token } = useAdmin();
  const params = useParams();
  const router = useRouter();
  const weddingId = params.id as string;
  
  const [wedding, setWedding] = useState<Wedding | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'events' | 'rsvp' | 'registry' | 'faq' | 'theme'>('events');

  useEffect(() => {
    fetchWedding();
  }, [weddingId]);

  const fetchWedding = async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/weddings`);
      if (!response.ok) throw new Error('Failed to fetch weddings');
      
      const weddings = await response.json();
      const wedding = weddings.find((w: any) => (w.id || w._id) === weddingId);
      
      if (wedding) {
        // Initialize default values if not present
        setWedding({
          ...wedding,
          rsvp_config: wedding.rsvp_config || {
            greeting: "Join us in celebrating our special day! Please let us know if you'll be attending.",
            help_text: "Check your phone for your personal invitation link, or contact us directly.",
            phone_numbers: ["(319) 529-6088", "(405) 708-1076"]
          },
          registries: wedding.registries || [],
          faqs: wedding.faqs || [],
          theme_config: wedding.theme_config || {
            primary_color: "#1e3a5f",
            secondary_color: "#d4af37",
            accent_color: "#c8847e",
            background_style: "gradient",
            font_style: "elegant"
          }
        });
      } else {
        setError('Wedding not found');
      }
    } catch (err) {
      setError('Failed to load wedding details');
    } finally {
      setLoading(false);
    }
  };

  const saveWedding = async () => {
    if (!wedding) return;
    
    setSaving(true);
    setError('');
    
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/admin/weddings/${weddingId}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(wedding),
      });

      if (!response.ok) {
        throw new Error('Failed to save wedding details');
      }

      // Show success message
      alert('Wedding details saved successfully!');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  // Event management functions
  const updateEvent = (index: number, event: WeddingEvent) => {
    if (!wedding) return;
    const newEvents = [...wedding.events];
    newEvents[index] = event;
    setWedding({ ...wedding, events: newEvents });
  };

  const addEvent = () => {
    if (!wedding) return;
    setWedding({
      ...wedding,
      events: [...wedding.events, { type: 'reception', date: '', details: {} }]
    });
  };

  const removeEvent = (index: number) => {
    if (!wedding) return;
    setWedding({
      ...wedding,
      events: wedding.events.filter((_, i) => i !== index)
    });
  };

  // Registry management functions
  const addRegistry = () => {
    if (!wedding) return;
    setWedding({
      ...wedding,
      registries: [...(wedding.registries || []), { name: '', url: '', color: 'bg-gray-600' }]
    });
  };

  const updateRegistry = (index: number, registry: RegistryItem) => {
    if (!wedding) return;
    const newRegistries = [...(wedding.registries || [])];
    newRegistries[index] = registry;
    setWedding({ ...wedding, registries: newRegistries });
  };

  const removeRegistry = (index: number) => {
    if (!wedding) return;
    setWedding({
      ...wedding,
      registries: (wedding.registries || []).filter((_, i) => i !== index)
    });
  };

  // FAQ management functions
  const addFAQ = () => {
    if (!wedding) return;
    setWedding({
      ...wedding,
      faqs: [...(wedding.faqs || []), { question: '', answer: '' }]
    });
  };

  const updateFAQ = (index: number, faq: FAQItem) => {
    if (!wedding) return;
    const newFAQs = [...(wedding.faqs || [])];
    newFAQs[index] = faq;
    setWedding({ ...wedding, faqs: newFAQs });
  };

  const removeFAQ = (index: number) => {
    if (!wedding) return;
    setWedding({
      ...wedding,
      faqs: (wedding.faqs || []).filter((_, i) => i !== index)
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-wedding-ivory to-rose-50 p-6 flex items-center justify-center">
        <div className="animate-spin h-12 w-12 border-4 border-wedding-rose border-t-transparent rounded-full"></div>
      </div>
    );
  }

  if (!wedding) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-wedding-ivory to-rose-50 p-6">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-3xl font-bold text-wedding-navy mb-4">Wedding Not Found</h1>
          <Link href="/admin/weddings" className="text-wedding-rose hover:underline">
            Back to Weddings
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-wedding-ivory to-rose-50 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden mb-8">
          <div className="bg-gradient-to-r from-wedding-navy to-wedding-gold px-8 py-6">
            <div className="flex justify-between items-center">
              <div>
                <h1 className="text-3xl font-bold text-white">{wedding.couple_names}</h1>
                <p className="text-blue-100 mt-2">Configure wedding details and content</p>
              </div>
              <div className="flex gap-3">
                <Link
                  href="/admin/weddings"
                  className="bg-white/20 text-white px-6 py-3 rounded-lg font-semibold hover:bg-white/30 transition-colors"
                >
                  Back
                </Link>
                <button
                  onClick={saveWedding}
                  disabled={saving}
                  className="bg-white text-wedding-navy px-6 py-3 rounded-lg font-semibold hover:bg-wedding-ivory transition-colors disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
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

        {/* Tabs */}
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden mb-8">
          <div className="border-b border-gray-200">
            <nav className="flex">
              {(['events', 'rsvp', 'registry', 'faq', 'theme'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-6 py-4 text-sm font-medium capitalize ${
                    activeTab === tab
                      ? 'text-wedding-navy border-b-2 border-wedding-rose'
                      : 'text-gray-600 hover:text-wedding-navy'
                  }`}
                >
                  {tab === 'rsvp' ? 'RSVP Settings' : tab === 'faq' ? 'FAQ' : tab}
                </button>
              ))}
            </nav>
          </div>

          <div className="p-8">
            {/* Events Tab */}
            {activeTab === 'events' && (
              <div className="space-y-6">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-2xl font-bold text-wedding-navy">Event Details</h2>
                  <button
                    onClick={addEvent}
                    className="bg-wedding-sage text-white px-4 py-2 rounded-lg hover:bg-opacity-90"
                  >
                    Add Event
                  </button>
                </div>

                {wedding.events.map((event, index) => (
                  <div key={index} className="border border-gray-200 rounded-lg p-6 space-y-4">
                    <div className="flex justify-between items-start">
                      <h3 className="text-lg font-semibold capitalize">
                        {event.type.replace('_', ' ')} - {event.date}
                      </h3>
                      <button
                        onClick={() => removeEvent(index)}
                        className="text-red-600 hover:bg-red-50 px-3 py-1 rounded"
                      >
                        Remove
                      </button>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Event Type
                        </label>
                        <select
                          value={event.type}
                          onChange={(e) => updateEvent(index, { ...event, type: e.target.value as any })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                        >
                          <option value="traditional">Traditional</option>
                          <option value="white_wedding">White Wedding</option>
                          <option value="reception">Reception</option>
                          <option value="engagement">Engagement</option>
                          <option value="rehearsal">Rehearsal Dinner</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Date
                        </label>
                        <input
                          type="date"
                          value={event.date}
                          onChange={(e) => updateEvent(index, { ...event, date: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Venue Name
                        </label>
                        <input
                          type="text"
                          value={event.details?.venue_name || ''}
                          onChange={(e) => updateEvent(index, {
                            ...event,
                            details: { ...event.details, venue_name: e.target.value }
                          })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                          placeholder="e.g., Grand Ballroom"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Time
                        </label>
                        <input
                          type="text"
                          value={event.details?.time || ''}
                          onChange={(e) => updateEvent(index, {
                            ...event,
                            details: { ...event.details, time: e.target.value }
                          })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                          placeholder="e.g., 3:00 PM"
                        />
                      </div>

                      <div className="col-span-2">
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Location/Address
                        </label>
                        <input
                          type="text"
                          value={event.details?.location || ''}
                          onChange={(e) => updateEvent(index, {
                            ...event,
                            details: { ...event.details, location: e.target.value }
                          })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                          placeholder="e.g., 123 Main Street, Lagos"
                        />
                      </div>

                      <div className="col-span-2">
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Dress Code/Attire
                        </label>
                        <input
                          type="text"
                          value={event.details?.attire || ''}
                          onChange={(e) => updateEvent(index, {
                            ...event,
                            details: { ...event.details, attire: e.target.value }
                          })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                          placeholder="e.g., Formal attire, Traditional Nigerian attire"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* RSVP Tab */}
            {activeTab === 'rsvp' && wedding.rsvp_config && (
              <div className="space-y-6">
                <h2 className="text-2xl font-bold text-wedding-navy mb-4">RSVP Configuration</h2>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Greeting Message
                  </label>
                  <textarea
                    value={wedding.rsvp_config.greeting}
                    onChange={(e) => setWedding({
                      ...wedding,
                      rsvp_config: { ...wedding.rsvp_config!, greeting: e.target.value }
                    })}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg"
                    rows={3}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Help Text
                  </label>
                  <textarea
                    value={wedding.rsvp_config.help_text}
                    onChange={(e) => setWedding({
                      ...wedding,
                      rsvp_config: { ...wedding.rsvp_config!, help_text: e.target.value }
                    })}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg"
                    rows={2}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Contact Phone Numbers
                  </label>
                  <div className="space-y-2">
                    {wedding.rsvp_config.phone_numbers.map((phone, index) => (
                      <div key={index} className="flex gap-2">
                        <input
                          type="text"
                          value={phone}
                          onChange={(e) => {
                            const newPhones = [...wedding.rsvp_config!.phone_numbers];
                            newPhones[index] = e.target.value;
                            setWedding({
                              ...wedding,
                              rsvp_config: { ...wedding.rsvp_config!, phone_numbers: newPhones }
                            });
                          }}
                          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg"
                        />
                        <button
                          onClick={() => {
                            setWedding({
                              ...wedding,
                              rsvp_config: {
                                ...wedding.rsvp_config!,
                                phone_numbers: wedding.rsvp_config!.phone_numbers.filter((_, i) => i !== index)
                              }
                            });
                          }}
                          className="px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg"
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                    <button
                      onClick={() => setWedding({
                        ...wedding,
                        rsvp_config: {
                          ...wedding.rsvp_config!,
                          phone_numbers: [...wedding.rsvp_config!.phone_numbers, '']
                        }
                      })}
                      className="text-sm bg-wedding-sage text-white px-4 py-2 rounded-lg hover:bg-opacity-90"
                    >
                      Add Phone Number
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Registry Tab */}
            {activeTab === 'registry' && (
              <div className="space-y-6">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-2xl font-bold text-wedding-navy">Wedding Registry</h2>
                  <button
                    onClick={addRegistry}
                    className="bg-wedding-sage text-white px-4 py-2 rounded-lg hover:bg-opacity-90"
                  >
                    Add Registry
                  </button>
                </div>

                {(wedding.registries || []).map((registry, index) => (
                  <div key={index} className="border border-gray-200 rounded-lg p-4 space-y-4">
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Registry Name
                        </label>
                        <input
                          type="text"
                          value={registry.name}
                          onChange={(e) => updateRegistry(index, { ...registry, name: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                          placeholder="e.g., Target, Amazon"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Registry URL
                        </label>
                        <input
                          type="url"
                          value={registry.url}
                          onChange={(e) => updateRegistry(index, { ...registry, url: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                          placeholder="https://..."
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Button Color
                        </label>
                        <select
                          value={registry.color || 'bg-gray-600'}
                          onChange={(e) => updateRegistry(index, { ...registry, color: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                        >
                          <option value="bg-gray-600">Gray</option>
                          <option value="bg-red-600">Red</option>
                          <option value="bg-orange-500">Orange</option>
                          <option value="bg-blue-600">Blue</option>
                          <option value="bg-green-600">Green</option>
                          <option value="bg-purple-600">Purple</option>
                        </select>
                      </div>
                    </div>

                    <button
                      onClick={() => removeRegistry(index)}
                      className="text-red-600 hover:bg-red-50 px-3 py-1 rounded"
                    >
                      Remove Registry
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* FAQ Tab */}
            {activeTab === 'faq' && (
              <div className="space-y-6">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-2xl font-bold text-wedding-navy">Frequently Asked Questions</h2>
                  <button
                    onClick={addFAQ}
                    className="bg-wedding-sage text-white px-4 py-2 rounded-lg hover:bg-opacity-90"
                  >
                    Add FAQ
                  </button>
                </div>

                {(wedding.faqs || []).map((faq, index) => (
                  <div key={index} className="border border-gray-200 rounded-lg p-4 space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Question
                      </label>
                      <input
                        type="text"
                        value={faq.question}
                        onChange={(e) => updateFAQ(index, { ...faq, question: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                        placeholder="e.g., What should I wear?"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Answer
                      </label>
                      <textarea
                        value={faq.answer}
                        onChange={(e) => updateFAQ(index, { ...faq, answer: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                        rows={2}
                        placeholder="e.g., We recommend semi-formal attire..."
                      />
                    </div>

                    <button
                      onClick={() => removeFAQ(index)}
                      className="text-red-600 hover:bg-red-50 px-3 py-1 rounded"
                    >
                      Remove FAQ
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Theme Tab */}
            {activeTab === 'theme' && wedding.theme_config && (
              <div className="space-y-6">
                <h2 className="text-2xl font-bold text-wedding-navy mb-4">Theme Configuration</h2>

                {/* Color Presets */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Quick Theme Presets
                  </label>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                    {[
                      { name: 'Classic Navy & Gold', primary: '#1e3a5f', secondary: '#d4af37', accent: '#c8847e' },
                      { name: 'Romantic Rose', primary: '#c8847e', secondary: '#f5e6e0', accent: '#d4af37' },
                      { name: 'Garden Green', primary: '#4a5d3a', secondary: '#d4af37', accent: '#e8c4b8' },
                      { name: 'Royal Purple', primary: '#4a3a5f', secondary: '#d4af37', accent: '#c8847e' },
                      { name: 'Ocean Blue', primary: '#2c5985', secondary: '#f5e6e0', accent: '#d4af37' },
                      { name: 'Sunset Orange', primary: '#d97638', secondary: '#f5e6e0', accent: '#4a5d3a' },
                      { name: 'Vintage Burgundy', primary: '#800020', secondary: '#d4af37', accent: '#f5e6e0' },
                      { name: 'Modern Minimal', primary: '#333333', secondary: '#666666', accent: '#999999' }
                    ].map((preset) => (
                      <button
                        key={preset.name}
                        onClick={() => setWedding({
                          ...wedding,
                          theme_config: {
                            ...wedding.theme_config!,
                            primary_color: preset.primary,
                            secondary_color: preset.secondary,
                            accent_color: preset.accent
                          }
                        })}
                        className="p-3 border border-gray-200 rounded-lg hover:border-wedding-rose transition-colors"
                      >
                        <div className="flex gap-2 mb-2">
                          <div 
                            className="w-6 h-6 rounded"
                            style={{ backgroundColor: preset.primary }}
                          />
                          <div 
                            className="w-6 h-6 rounded"
                            style={{ backgroundColor: preset.secondary }}
                          />
                          <div 
                            className="w-6 h-6 rounded"
                            style={{ backgroundColor: preset.accent }}
                          />
                        </div>
                        <p className="text-xs text-gray-700">{preset.name}</p>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Custom Colors */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Primary Color
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="color"
                        value={wedding.theme_config.primary_color}
                        onChange={(e) => setWedding({
                          ...wedding,
                          theme_config: { ...wedding.theme_config!, primary_color: e.target.value }
                        })}
                        className="h-10 w-20"
                      />
                      <input
                        type="text"
                        value={wedding.theme_config.primary_color}
                        onChange={(e) => setWedding({
                          ...wedding,
                          theme_config: { ...wedding.theme_config!, primary_color: e.target.value }
                        })}
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-lg"
                        placeholder="#1e3a5f"
                      />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">Used for headers and main elements</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Secondary Color
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="color"
                        value={wedding.theme_config.secondary_color}
                        onChange={(e) => setWedding({
                          ...wedding,
                          theme_config: { ...wedding.theme_config!, secondary_color: e.target.value }
                        })}
                        className="h-10 w-20"
                      />
                      <input
                        type="text"
                        value={wedding.theme_config.secondary_color}
                        onChange={(e) => setWedding({
                          ...wedding,
                          theme_config: { ...wedding.theme_config!, secondary_color: e.target.value }
                        })}
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-lg"
                        placeholder="#d4af37"
                      />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">Used for accents and highlights</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Accent Color
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="color"
                        value={wedding.theme_config.accent_color}
                        onChange={(e) => setWedding({
                          ...wedding,
                          theme_config: { ...wedding.theme_config!, accent_color: e.target.value }
                        })}
                        className="h-10 w-20"
                      />
                      <input
                        type="text"
                        value={wedding.theme_config.accent_color}
                        onChange={(e) => setWedding({
                          ...wedding,
                          theme_config: { ...wedding.theme_config!, accent_color: e.target.value }
                        })}
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-lg"
                        placeholder="#c8847e"
                      />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">Used for buttons and call-to-actions</p>
                  </div>
                </div>

                {/* Style Options */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Background Style
                    </label>
                    <select
                      value={wedding.theme_config.background_style}
                      onChange={(e) => setWedding({
                        ...wedding,
                        theme_config: { ...wedding.theme_config!, background_style: e.target.value as any }
                      })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    >
                      <option value="gradient">Gradient</option>
                      <option value="solid">Solid Color</option>
                      <option value="image">Background Image</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Font Style
                    </label>
                    <select
                      value={wedding.theme_config.font_style}
                      onChange={(e) => setWedding({
                        ...wedding,
                        theme_config: { ...wedding.theme_config!, font_style: e.target.value as any }
                      })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    >
                      <option value="elegant">Elegant (Serif)</option>
                      <option value="modern">Modern (Sans-serif)</option>
                      <option value="classic">Classic (Traditional)</option>
                      <option value="playful">Playful (Decorative)</option>
                    </select>
                  </div>
                </div>

                {/* Preview */}
                <div className="mt-6">
                  <h3 className="text-lg font-semibold mb-3">Preview</h3>
                  <div 
                    className="p-6 rounded-lg"
                    style={{
                      background: wedding.theme_config.background_style === 'gradient' 
                        ? `linear-gradient(135deg, ${wedding.theme_config.primary_color}20, ${wedding.theme_config.secondary_color}20)`
                        : `${wedding.theme_config.primary_color}10`
                    }}
                  >
                    <h4 
                      className="text-2xl font-bold mb-2"
                      style={{ color: wedding.theme_config.primary_color }}
                    >
                      {wedding.couple_names}
                    </h4>
                    <p 
                      className="mb-4"
                      style={{ color: wedding.theme_config.secondary_color }}
                    >
                      {wedding.date}
                    </p>
                    <button 
                      className="px-6 py-2 rounded-lg text-white"
                      style={{ backgroundColor: wedding.theme_config.accent_color }}
                    >
                      Sample Button
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}