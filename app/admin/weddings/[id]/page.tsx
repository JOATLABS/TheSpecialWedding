'use client';

import { useState, useEffect, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAdmin } from '@/contexts/AdminContext';
import { Wedding, WeddingEvent, RegistryItem, FAQItem, OurStory, WeddingPartyMember, PrivacySettings, WeddingPartySyncSettings } from '@/types/wedding';

// Wedding party group mappings for sync
// Wedding party = bridesmaids, groomsmen, maid of honor, best man
const WEDDING_PARTY_GROUPS = {
  maid_of_honor: { role: 'maid_of_honor', side: 'bride' as const },
  bridesmaids: { role: 'bridesmaid', side: 'bride' as const },
  best_man: { role: 'best_man', side: 'groom' as const },
  groomsmen: { role: 'groomsman', side: 'groom' as const },
};

interface Guest {
  id?: string;
  _id?: string;
  name: string;
  email?: string;
  phone?: string;
  group_id?: string;
}

export default function WeddingDetailsPage() {
 const { token } = useAdmin();
 const params = useParams();
 const router = useRouter();
 const weddingId = params.id as string;

 const [wedding, setWedding] = useState<Wedding | null>(null);
 const [loading, setLoading] = useState(true);
 const [saving, setSaving] = useState(false);
 const [error, setError] = useState<string>('');
 const [activeTab, setActiveTab] = useState<'events' | 'rsvp' | 'privacy' | 'registry' | 'faq' | 'theme' | 'story'>('events');
 const [syncing, setSyncing] = useState(false);
 const [guests, setGuests] = useState<Guest[]>([]);

 const fetchWedding = useCallback(async () => {
 try {
 const baseUrl = getApiBaseUrl();
 // Use authenticated planner endpoint to get assigned weddings
 const response = await fetch(`${baseUrl}/admin/planner/weddings`, {
   headers: {
     'Authorization': `Bearer ${token}`,
     'Content-Type': 'application/json'
   }
 });
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
 privacy_settings: wedding.privacy_settings || {
 privacy_mode: "private",
 guest_auth_required: true,
 password_protection: "",
 allow_guest_sharing: false,
 require_phone_verification: true,
 require_name_verification: true
 },
 registries: wedding.registries || [],
 faqs: wedding.faqs || [],
 theme_config: wedding.theme_config || {
 primary_color: "#1e3a5f",
 secondary_color: "#d4af37",
 accent_color: "#c8847e",
 background_style: "gradient",
 font_style: "elegant"
 },
 our_story: wedding.our_story || {
 text: "",
 image_url: "",
 image_shape: "circle"
 },
 wedding_party: wedding.wedding_party || [],
 wedding_party_sync: wedding.wedding_party_sync || {
   sync_enabled: false,
   sync_mode: 'manual',
   last_synced_at: undefined
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
 }, [token, weddingId]);

 useEffect(() => {
 fetchWedding();
 }, [fetchWedding]);

 // Fetch guests for wedding party sync
 const fetchGuests = useCallback(async () => {
   if (!weddingId) return;
   try {
     const baseUrl = getApiBaseUrl();
     const response = await fetch(`${baseUrl}/admin/guests/${weddingId}`, {
       headers: {
         'Authorization': `Bearer ${token}`,
         'Content-Type': 'application/json'
       }
     });
     if (response.ok) {
       const data = await response.json();
       setGuests(data);
     }
   } catch (err) {
     console.error('Failed to fetch guests:', err);
   }
 }, [token, weddingId]);

 // Fetch guests when story tab is active (for sync feature)
 useEffect(() => {
   if (activeTab === 'story') {
     fetchGuests();
   }
 }, [activeTab, fetchGuests]);

 // Sync wedding party from guests
 const syncWeddingPartyFromGuests = async () => {
   if (!wedding) return;

   setSyncing(true);
   try {
     // Fetch latest guests
     const baseUrl = getApiBaseUrl();
     const response = await fetch(`${baseUrl}/admin/guests/${weddingId}`, {
       headers: {
         'Authorization': `Bearer ${token}`,
         'Content-Type': 'application/json'
       }
     });

     if (!response.ok) throw new Error('Failed to fetch guests');
     const guestList: Guest[] = await response.json();

     // Filter guests with wedding party groups
     const weddingPartyGuests = guestList.filter(guest =>
       guest.group_id && Object.keys(WEDDING_PARTY_GROUPS).includes(guest.group_id)
     );

     // Convert to wedding party members
     const newMembers: WeddingPartyMember[] = weddingPartyGuests.map((guest, index) => {
       const groupConfig = WEDDING_PARTY_GROUPS[guest.group_id as keyof typeof WEDDING_PARTY_GROUPS];
       const existingMember = wedding.wedding_party?.find(
         m => m.linked_guest_id === (guest.id || guest._id) || m.linked_guest_email === guest.email
       );

       return {
         id: existingMember?.id || `synced-${guest.id || guest._id}`,
         name: guest.name,
         role: groupConfig?.role || 'wedding_party',
         side: groupConfig?.side || 'bride',
         image_url: existingMember?.image_url || '',
         display_order: existingMember?.display_order || index,
         linked_guest_id: guest.id || guest._id,
         linked_guest_email: guest.email
       };
     });

     // Merge with existing members (keep manually added ones)
     const manualMembers = wedding.wedding_party?.filter(
       m => !m.linked_guest_id && !weddingPartyGuests.some(g => g.name === m.name)
     ) || [];

     const mergedMembers = [...newMembers, ...manualMembers];

     setWedding({
       ...wedding,
       wedding_party: mergedMembers,
       wedding_party_sync: {
         ...wedding.wedding_party_sync!,
         last_synced_at: new Date().toISOString()
       }
     });

     alert(`Synced ${newMembers.length} wedding party members from guests!`);
   } catch (err) {
     setError('Failed to sync wedding party');
   } finally {
     setSyncing(false);
   }
 };

 const saveWedding = async () => {
 if (!wedding) return;

 setSaving(true);
 setError('');

 try {
 const baseUrl = getApiBaseUrl();
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
 <div className="min-h-screen bg-gradient-to-br from-wedding-ivory to-rose-50 dark:from-slate-900 dark:to-slate-800 p-6 flex items-center justify-center">
 <div className="animate-spin h-12 w-12 border-4 border-wedding-rose border-t-transparent rounded-full"></div>
 </div>
 );
 }

 if (!wedding) {
 return (
 <div className="min-h-screen bg-gradient-to-br from-wedding-ivory to-rose-50 dark:from-slate-900 dark:to-slate-800 p-6">
 <div className="max-w-4xl mx-auto text-center">
 <h1 className="text-3xl font-bold text-wedding-navy dark:text-gray-100 mb-4">Wedding Not Found</h1>
 <Link href="/admin/weddings" className="text-wedding-rose hover:underline">
 Back to Weddings
 </Link>
 </div>
 </div>
 );
 }

 return (
 <div className="min-h-screen bg-gradient-to-br from-wedding-ivory to-rose-50 dark:from-slate-900 dark:to-slate-800 p-4 sm:p-6">
 <div className="max-w-6xl mx-auto">
 {/* Header */}
 <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl overflow-hidden mb-8">
 <div className="bg-gradient-to-r from-wedding-navy to-wedding-gold px-4 sm:px-8 py-4 sm:py-6">
 <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
 <div>
 <h1 className="text-xl sm:text-3xl font-bold text-white break-words">{wedding.couple_names}</h1>
 <p className="text-blue-100 mt-1 sm:mt-2 text-sm sm:text-base">Configure wedding details and content</p>
 </div>
 <div className="flex gap-2 sm:gap-3 w-full sm:w-auto">
 <Link
 href="/admin/weddings"
 className="bg-white/20 text-white px-4 sm:px-6 py-2 sm:py-3 rounded-lg font-semibold hover:bg-white/30 transition-colors text-sm sm:text-base flex-1 sm:flex-initial text-center"
 >
 Back
 </Link>
 <button
 onClick={saveWedding}
 disabled={saving}
 className="bg-white text-wedding-navy px-4 sm:px-6 py-2 sm:py-3 rounded-lg font-semibold hover:bg-gray-50 dark:bg-transparent transition-colors disabled:opacity-50 text-sm sm:text-base flex-1 sm:flex-initial"
 >
 {saving ? 'Saving...' : 'Save Changes'}
 </button>
 </div>
 </div>
 </div>
 </div>

 {/* Error Display */}
 {error && (
 <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
 <p className="text-red-700 dark:text-red-300">{error}</p>
 </div>
 )}

 {/* Tabs */}
 <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl overflow-hidden mb-8">
 <div className="border-b border-gray-200 dark:border-gray-700">
 <nav className="flex overflow-x-auto scrollbar-hide">
 {(['events', 'rsvp', 'privacy', 'registry', 'faq', 'theme', 'story'] as const).map((tab) => (
 <button
 key={tab}
 onClick={() => setActiveTab(tab)}
 className={`px-3 sm:px-6 py-3 sm:py-4 text-xs sm:text-sm font-medium capitalize whitespace-nowrap ${
 activeTab === tab
 ? 'text-wedding-navy dark:text-wedding-gold border-b-2 border-wedding-rose dark:border-wedding-gold'
 : 'text-gray-600 dark:text-gray-400 hover:text-wedding-navy dark:hover:text-gray-200'
 }`}
 >
 {tab === 'rsvp' ? 'RSVP' : tab === 'faq' ? 'FAQ' : tab === 'story' ? 'Story' : tab}
 </button>
 ))}
 </nav>
 </div>

 <div className="p-4 sm:p-8">
 {/* Events Tab */}
 {activeTab === 'events' && (
 <div className="space-y-6">
 <div className="flex justify-between items-center mb-4">
 <h2 className="text-2xl font-bold text-wedding-navy dark:text-gray-100">Event Details</h2>
 <button
 onClick={addEvent}
 className="bg-wedding-sage text-white px-4 py-2 rounded-lg hover:bg-opacity-90"
 >
 Add Event
 </button>
 </div>

 {wedding.events.map((event, index) => (
 <div key={index} className="border border-gray-200 dark:border-gray-700 rounded-lg p-6 space-y-4">
 <div className="flex justify-between items-start">
 <h3 className="text-lg font-semibold capitalize text-gray-900 dark:text-gray-100">
 {event.type.replace('_', ' ')} - {event.date}
 </h3>
 <button
 onClick={() => removeEvent(index)}
 className="text-red-600 dark:text-red-300 hover:bg-red-50 px-3 py-1 rounded"
 >
 Remove
 </button>
 </div>

 <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Event Type
 </label>
 <select
 value={event.type}
 onChange={(e) => updateEvent(index, { ...event, type: e.target.value as any })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 >
 <option value="traditional">Traditional</option>
 <option value="white_wedding">White Wedding</option>
 <option value="reception">Reception</option>
 <option value="engagement">Engagement</option>
 <option value="rehearsal">Rehearsal Dinner</option>
 </select>
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Date
 </label>
 <input
 type="date"
 value={event.date}
 onChange={(e) => updateEvent(index, { ...event, date: e.target.value })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Venue Name
 </label>
 <input
 type="text"
 value={event.details?.venue_name || ''}
 onChange={(e) => updateEvent(index, {
 ...event,
 details: { ...event.details, venue_name: e.target.value }
 })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 placeholder="e.g., Grand Ballroom"
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Time
 </label>
 <input
 type="text"
 value={event.details?.time || ''}
 onChange={(e) => updateEvent(index, {
 ...event,
 details: { ...event.details, time: e.target.value }
 })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 placeholder="e.g., 3:00 PM"
 />
 </div>

 <div className="lg:col-span-2">
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Location/Address
 </label>
 <input
 type="text"
 value={event.details?.location || ''}
 onChange={(e) => updateEvent(index, {
 ...event,
 details: { ...event.details, location: e.target.value }
 })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 placeholder="e.g., 123 Main Street, Lagos"
 />
 </div>

 <div className="lg:col-span-2">
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Dress Code/Attire
 </label>
 <input
 type="text"
 value={event.details?.attire || ''}
 onChange={(e) => updateEvent(index, {
 ...event,
 details: { ...event.details, attire: e.target.value }
 })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
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
 <h2 className="text-2xl font-bold text-wedding-navy dark:text-gray-100 mb-4">RSVP Configuration</h2>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
 Greeting Message
 </label>
 <textarea
 value={wedding.rsvp_config.greeting}
 onChange={(e) => setWedding({
 ...wedding,
 rsvp_config: { ...wedding.rsvp_config!, greeting: e.target.value }
 })}
 className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 rows={3}
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
 Help Text
 </label>
 <textarea
 value={wedding.rsvp_config.help_text}
 onChange={(e) => setWedding({
 ...wedding,
 rsvp_config: { ...wedding.rsvp_config!, help_text: e.target.value }
 })}
 className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 rows={2}
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
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
 className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
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
 className="px-3 py-2 text-red-600 dark:text-red-300 hover:bg-red-50 rounded-lg"
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

 {/* Privacy Tab */}
 {activeTab === 'privacy' && wedding.privacy_settings && (
 <div className="space-y-6">
 <h2 className="text-2xl font-bold text-wedding-navy dark:text-gray-100 mb-4">Privacy & Access Settings</h2>

 {/* Privacy Mode */}
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
 Privacy Mode
 </label>
 <select
 value={wedding.privacy_settings.privacy_mode}
 onChange={(e) => setWedding({
 ...wedding,
 privacy_settings: { ...wedding.privacy_settings!, privacy_mode: e.target.value as any }
 })}
 className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 >
 <option value="private">Private - Only invited guests can access</option>
 <option value="password">Password Protected - Anyone with password can view</option>
 <option value="public">Public - Anyone with link can view</option>
 </select>
 <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
 {wedding.privacy_settings.privacy_mode === 'private' && 'Guests must verify their identity to access the wedding page.'}
 {wedding.privacy_settings.privacy_mode === 'password' && 'Anyone with the password can view the wedding page without verification.'}
 {wedding.privacy_settings.privacy_mode === 'public' && 'The wedding page is publicly accessible to anyone with the link.'}
 </p>
 </div>

 {/* Password Protection (only shown for password mode) */}
 {wedding.privacy_settings.privacy_mode === 'password' && (
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
 Access Password
 </label>
 <input
 type="text"
 value={wedding.privacy_settings.password_protection || ''}
 onChange={(e) => setWedding({
 ...wedding,
 privacy_settings: { ...wedding.privacy_settings!, password_protection: e.target.value }
 })}
 className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 placeholder="Enter access password"
 />
 <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
 Share this password with guests who should be able to view the wedding page.
 </p>
 </div>
 )}

 {/* Guest Authentication Required */}
 <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-slate-700/50 rounded-lg">
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
 Require Guest Authentication
 </label>
 <p className="text-sm text-gray-500 dark:text-gray-400">
 Guests must verify their identity before accessing the RSVP form
 </p>
 </div>
 <label className="relative inline-flex items-center cursor-pointer">
 <input
 type="checkbox"
 checked={wedding.privacy_settings.guest_auth_required}
 onChange={(e) => setWedding({
 ...wedding,
 privacy_settings: { ...wedding.privacy_settings!, guest_auth_required: e.target.checked }
 })}
 className="sr-only peer"
 />
 <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-wedding-gold/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-wedding-gold"></div>
 </label>
 </div>

 {/* Verification Methods */}
 <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-4">
 <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200">Verification Methods</h3>
 <p className="text-sm text-gray-500 dark:text-gray-400">Choose how guests can verify their identity</p>

 <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-slate-700/50 rounded-lg">
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
 Phone Number Verification
 </label>
 <p className="text-xs text-gray-500 dark:text-gray-400">
 Guests verify via phone number lookup
 </p>
 </div>
 <label className="relative inline-flex items-center cursor-pointer">
 <input
 type="checkbox"
 checked={wedding.privacy_settings.require_phone_verification}
 onChange={(e) => setWedding({
 ...wedding,
 privacy_settings: { ...wedding.privacy_settings!, require_phone_verification: e.target.checked }
 })}
 className="sr-only peer"
 />
 <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-wedding-gold/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-wedding-gold"></div>
 </label>
 </div>

 <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-slate-700/50 rounded-lg">
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
 Name Verification
 </label>
 <p className="text-xs text-gray-500 dark:text-gray-400">
 Guests verify via name lookup
 </p>
 </div>
 <label className="relative inline-flex items-center cursor-pointer">
 <input
 type="checkbox"
 checked={wedding.privacy_settings.require_name_verification}
 onChange={(e) => setWedding({
 ...wedding,
 privacy_settings: { ...wedding.privacy_settings!, require_name_verification: e.target.checked }
 })}
 className="sr-only peer"
 />
 <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-wedding-gold/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-wedding-gold"></div>
 </label>
 </div>
 </div>

 {/* Allow Guest Sharing */}
 <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-slate-700/50 rounded-lg">
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
 Allow Guest Sharing
 </label>
 <p className="text-sm text-gray-500 dark:text-gray-400">
 Enable guests to share their RSVP links with others
 </p>
 </div>
 <label className="relative inline-flex items-center cursor-pointer">
 <input
 type="checkbox"
 checked={wedding.privacy_settings.allow_guest_sharing}
 onChange={(e) => setWedding({
 ...wedding,
 privacy_settings: { ...wedding.privacy_settings!, allow_guest_sharing: e.target.checked }
 })}
 className="sr-only peer"
 />
 <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-wedding-gold/20 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-wedding-gold"></div>
 </label>
 </div>

 {/* Info Box */}
 <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
 <h4 className="font-semibold text-blue-900 dark:text-blue-200 mb-2">Privacy Tips</h4>
 <ul className="text-sm text-blue-800 dark:text-blue-300 space-y-1">
 <li>• <strong>Private mode</strong> is recommended for most weddings to ensure only invited guests can RSVP</li>
 <li>• <strong>Password mode</strong> is useful for sharing with a wider circle while maintaining some access control</li>
 <li>• <strong>Public mode</strong> makes your wedding page visible to anyone with the link</li>
 <li>• Enable both phone and name verification for maximum security</li>
 </ul>
 </div>
 </div>
 )}

 {/* Registry Tab */}
 {activeTab === 'registry' && (
 <div className="space-y-6">
 <div className="flex justify-between items-center mb-4">
 <h2 className="text-2xl font-bold text-wedding-navy dark:text-gray-100">Wedding Registry</h2>
 <button
 onClick={addRegistry}
 className="bg-wedding-sage text-white px-4 py-2 rounded-lg hover:bg-opacity-90"
 >
 Add Registry
 </button>
 </div>

 {(wedding.registries || []).map((registry, index) => (
 <div key={index} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-4">
 <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Registry Name
 </label>
 <input
 type="text"
 value={registry.name}
 onChange={(e) => updateRegistry(index, { ...registry, name: e.target.value })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 placeholder="e.g., Target, Amazon"
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Registry URL
 </label>
 <input
 type="url"
 value={registry.url}
 onChange={(e) => updateRegistry(index, { ...registry, url: e.target.value })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 placeholder="https://..."
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Button Color
 </label>
 <select
 value={registry.color || 'bg-gray-600'}
 onChange={(e) => updateRegistry(index, { ...registry, color: e.target.value })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
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
 className="text-red-600 dark:text-red-300 hover:bg-red-50 px-3 py-1 rounded"
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
 <h2 className="text-2xl font-bold text-wedding-navy dark:text-gray-100">Frequently Asked Questions</h2>
 <button
 onClick={addFAQ}
 className="bg-wedding-sage text-white px-4 py-2 rounded-lg hover:bg-opacity-90"
 >
 Add FAQ
 </button>
 </div>

 {(wedding.faqs || []).map((faq, index) => (
 <div key={index} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-4">
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Question
 </label>
 <input
 type="text"
 value={faq.question}
 onChange={(e) => updateFAQ(index, { ...faq, question: e.target.value })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 placeholder="e.g., What should I wear?"
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Answer
 </label>
 <textarea
 value={faq.answer}
 onChange={(e) => updateFAQ(index, { ...faq, answer: e.target.value })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 rows={2}
 placeholder="e.g., We recommend semi-formal attire..."
 />
 </div>

 {/* Optional Link/Button */}
 <div className="border-t border-gray-200 dark:border-gray-600 pt-4 mt-2">
 <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
 Optional: Add a button link (e.g., for hotel booking)
 </p>
 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
 <div>
 <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
 Button Label
 </label>
 <input
 type="text"
 value={faq.link_label || ''}
 onChange={(e) => updateFAQ(index, { ...faq, link_label: e.target.value || undefined })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 text-sm"
 placeholder="e.g., Book Hotel Room"
 />
 </div>
 <div>
 <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
 Button URL
 </label>
 <input
 type="url"
 value={faq.link_url || ''}
 onChange={(e) => updateFAQ(index, { ...faq, link_url: e.target.value || undefined })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 text-sm"
 placeholder="https://..."
 />
 </div>
 </div>
 </div>

 <button
 onClick={() => removeFAQ(index)}
 className="text-red-600 dark:text-red-300 hover:bg-red-50 px-3 py-1 rounded"
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
 <h2 className="text-2xl font-bold text-wedding-navy dark:text-gray-100 mb-4">Theme Configuration</h2>

 {/* Color Presets */}
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
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
 className="p-3 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-wedding-rose transition-colors"
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
 <p className="text-xs text-gray-700 dark:text-gray-300">{preset.name}</p>
 </button>
 ))}
 </div>
 </div>

 {/* Custom Colors */}
 <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
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
 className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 placeholder="#1e3a5f"
 />
 </div>
 <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Used for headers and main elements</p>
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
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
 className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 placeholder="#d4af37"
 />
 </div>
 <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Used for accents and highlights</p>
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
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
 className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 placeholder="#c8847e"
 />
 </div>
 <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Used for buttons and call-to-actions</p>
 </div>
 </div>

 {/* Style Options */}
 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
 Background Style
 </label>
 <select
 value={wedding.theme_config.background_style}
 onChange={(e) => setWedding({
 ...wedding,
 theme_config: { ...wedding.theme_config!, background_style: e.target.value as any }
 })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 >
 <option value="gradient">Frosted Glass with Gradient</option>
 <option value="solid">Frosted Glass with Solid Color</option>
 <option value="image">Pure Image (No Overlay)</option>
 </select>
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
 Font Style
 </label>
 <select
 value={wedding.theme_config.font_style}
 onChange={(e) => setWedding({
 ...wedding,
 theme_config: { ...wedding.theme_config!, font_style: e.target.value as any }
 })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
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
 <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">Preview</h3>
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

 {/* Story & Party Tab */}
 {activeTab === 'story' && (
 <div className="space-y-6">
 <h2 className="text-2xl font-bold text-wedding-navy dark:text-gray-100 mb-4">Story & Wedding Party</h2>
 {/* Info Box */}
 <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-6">
 <h4 className="font-semibold text-blue-900 dark:text-blue-200 mb-2">Image Organization</h4>
 <p className="text-sm text-blue-800 dark:text-blue-300 mb-2">
 To keep wedding party photos separate from the public gallery, use these folder structures:
 </p>
 <ul className="text-sm text-blue-700 dark:text-blue-300 space-y-1">
 <li>• <code className="bg-blue-100 dark:bg-blue-800/50 px-1 rounded">gallery/{wedding.slug}/</code> - Public gallery photos</li>
 <li>• <code className="bg-blue-100 dark:bg-blue-800/50 px-1 rounded">our-story/{wedding.slug}/</code> - Couple photos for story section</li>
 <li>• <code className="bg-blue-100 dark:bg-blue-800/50 px-1 rounded">wedding-party/{wedding.slug}/</code> - Wedding party member photos</li>
 </ul>
 </div>

 {/* Our Story Section */}
 <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-6">
 <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Our Story</h3>

 <div className="space-y-4">
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
 Story Text
 </label>
 <textarea
 value={wedding.our_story?.text || ''}
 onChange={(e) => setWedding({
 ...wedding,
 our_story: { ...wedding.our_story!, text: e.target.value }
 })}
 rows={6}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 resize-none"
 placeholder="Tell your love story..."
 />
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
 Image Shape
 </label>
 <select
 value={wedding.our_story?.image_shape || 'circle'}
 onChange={(e) => setWedding({
 ...wedding,
 our_story: { ...wedding.our_story!, image_shape: e.target.value as any }
 })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 >
 <option value="circle">Circle</option>
 <option value="heart">Heart</option>
 <option value="square">Square (Rounded)</option>
 <option value="hexagon">Hexagon</option>
 </select>
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
 Couple Photo
 </label>
 <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
 Upload to gallery, then use format: our-story/{wedding.slug}/filename.jpg
 </p>
 <input
 type="text"
 value={wedding.our_story?.image_url || ''}
 onChange={(e) => setWedding({
 ...wedding,
 our_story: { ...wedding.our_story!, image_url: e.target.value }
 })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 placeholder="our-story/wedding-slug/image.jpg"
 />
 </div>
 </div>
 </div>
 {/* Wedding Party Section */}
 <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-6">
 {/* Sync Settings */}
 <div className="bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg p-4 mb-6">
 <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
 <div>
 <h4 className="font-semibold text-purple-900 dark:text-purple-200 mb-1">Guest Sync</h4>
 <p className="text-sm text-purple-700 dark:text-purple-300">
 Sync wedding party from guests with groups like Bridesmaid, Groomsman, etc.
 </p>
 </div>
 <div className="flex items-center gap-3">
 <div className="flex items-center gap-2">
 <label className="text-sm text-purple-700 dark:text-purple-300">Mode:</label>
 <select
 value={wedding.wedding_party_sync?.sync_mode || 'manual'}
 onChange={(e) => setWedding({
 ...wedding,
 wedding_party_sync: {
 ...wedding.wedding_party_sync!,
 sync_enabled: true,
 sync_mode: e.target.value as 'auto' | 'manual'
 }
 })}
 className="px-2 py-1 text-sm border border-purple-300 dark:border-purple-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 >
 <option value="manual">Manual</option>
 <option value="auto">Auto</option>
 </select>
 </div>
 <button
 onClick={syncWeddingPartyFromGuests}
 disabled={syncing}
 className="bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2"
 >
 {syncing ? (
 <>
 <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
 Syncing...
 </>
 ) : (
 <>
 <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
 </svg>
 Sync from Guests
 </>
 )}
 </button>
 </div>
 </div>
 {wedding.wedding_party_sync?.last_synced_at && (
 <p className="text-xs text-purple-600 dark:text-purple-400 mt-2">
 Last synced: {new Date(wedding.wedding_party_sync.last_synced_at).toLocaleString()}
 </p>
 )}
 </div>

 <div className="flex justify-between items-center mb-4">
 <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Wedding Party Members</h3>
 <button
 onClick={() => {
 const newMember: WeddingPartyMember = {
 id: Date.now().toString(),
 name: '',
 role: 'bridesmaid',
 side: 'bride',
 display_order: wedding.wedding_party?.length || 0
 };
 setWedding({
 ...wedding,
 wedding_party: [...(wedding.wedding_party || []), newMember]
 });
 }}
 className="bg-wedding-sage text-white px-4 py-2 rounded-lg hover:bg-opacity-90"
 >
 Add Member
 </button>
 </div>
 <div className="space-y-4">
 {wedding.wedding_party?.map((member, index) => (
 <div key={member.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
 <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Name
 </label>
 <input
 type="text"
 value={member.name}
 onChange={(e) => {
 const updated = [...wedding.wedding_party!];
 updated[index] = { ...member, name: e.target.value };
 setWedding({ ...wedding, wedding_party: updated });
 }}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 placeholder="John Doe"
 />
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Side
 </label>
 <select
 value={member.side}
 onChange={(e) => {
 const updated = [...wedding.wedding_party!];
 updated[index] = { ...member, side: e.target.value as 'bride' | 'groom' };
 setWedding({ ...wedding, wedding_party: updated });
 }}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 >
 <option value="bride">Bride</option>
 <option value="groom">Groom</option>
 </select>
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Role
 </label>
 <select
 value={member.role}
 onChange={(e) => {
 const updated = [...wedding.wedding_party!];
 updated[index] = { ...member, role: e.target.value };
 setWedding({ ...wedding, wedding_party: updated });
 }}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 >
 <optgroup label="Bride's Side">
 <option value="maid_of_honor">Maid of Honor</option>
 <option value="bridesmaid">Bridesmaid</option>
 </optgroup>
 <optgroup label="Groom's Side">
 <option value="best_man">Best Man</option>
 <option value="groomsman">Groomsman</option>
 </optgroup>
 </select>
 </div>
 <div className="md:col-span-2">
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Photo (optional) - Use format: wedding-party/{wedding.slug}/name.jpg
 </label>
 <input
 type="text"
 value={member.image_url || ''}
 onChange={(e) => {
 const updated = [...wedding.wedding_party!];
 updated[index] = { ...member, image_url: e.target.value };
 setWedding({ ...wedding, wedding_party: updated });
 }}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 placeholder="wedding-party/wedding-slug/member-photo.jpg"
 />
 </div>
 <div className="flex items-end">
 <button
 onClick={() => {
 setWedding({
 ...wedding,
 wedding_party: wedding.wedding_party!.filter((_, i) => i !== index)
 });
 }}
 className="bg-red-500 text-white px-4 py-2 rounded-lg hover:bg-red-600 w-full"
 >
 Remove
 </button>
 </div>
 </div>
 </div>
 ))}
 {(!wedding.wedding_party || wedding.wedding_party.length === 0) && (
 <p className="text-gray-500 dark:text-gray-400 text-center py-8">
            No wedding party members added yet. Click “Add Member” to get started.
 </p>
 )}
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