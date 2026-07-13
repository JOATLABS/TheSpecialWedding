'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAdmin } from '@/contexts/AdminContext';
import { canManageCouplePortal } from '@/admin/utils/teamAccess';
import { extractGuestList } from '@/admin/utils/guestListResponse';
import { Wedding, WeddingEvent, RegistryItem, FAQItem, WeddingPartyMember } from '@/types/wedding';
import { formatAdminTimestamp, DEFAULT_TIMEZONE } from '@/utils/dateFormat';
import { EVENT_TIME_FORMAT_HINT, getEventTimeValidationMessage, normalizeEventTimeInput } from '@/utils/eventTime';
import { resolveMediaUrl } from '@/utils/mediaUrl';
import {
  createCustomWeddingEventTypeKey,
  getWeddingEventLabel,
  getWeddingEventSelectValue,
  WEDDING_EVENT_SELECT_OPTIONS,
} from '@/utils/weddingEvents';
import { PaymentCollectionButton } from '@/components/payments/PaymentCollectionButton';
import { CampaignSponsoredRail } from '../../vendors/components/CampaignSponsoredRail';
import { getWeddingVendors, type VendorAssignment } from '@/services/vendorManagementApi';
import { budgetApi } from '@/services/budgetApi';
import type { BudgetCategory } from '@/types/budget';
import { PrivacyModeSelector } from './PrivacyModeSelector';
import {
  DEFAULT_PRIVACY_SETTINGS,
  getPrivacyModeCallout,
  getPrivacyModeSummary,
  normalizePrivacySettingsForMode,
  type PrivacyMode,
} from './privacySettings';
import { WeddingSetupGuide } from './WeddingSetupGuide';
import {
  buildWeddingSetupSummary,
  isWeddingSetupTab,
  type WeddingSetupStatus,
  type WeddingSetupTab,
} from '../setupGuide';
// Direct imports — avoids Turbopack barrel-evaluation bug with lucide-react
// (Turbopack instantiates ALL 900+ icon module factories when importing from the barrel,
// and message-circle.js factory fails during this process)
import Users from 'lucide-react/dist/esm/icons/users';
import Mail from 'lucide-react/dist/esm/icons/mail';
import Send from 'lucide-react/dist/esm/icons/send';
import RefreshCw from 'lucide-react/dist/esm/icons/refresh-cw';
import Copy from 'lucide-react/dist/esm/icons/copy';
import Plus from 'lucide-react/dist/esm/icons/plus';
import Loader2 from 'lucide-react/dist/esm/icons/loader-2';
import ShieldOff from 'lucide-react/dist/esm/icons/shield-off';
import ShieldCheck from 'lucide-react/dist/esm/icons/shield-check';
import HeartHandshake from 'lucide-react/dist/esm/icons/heart-handshake';
import { toast } from 'sonner';

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

interface WeddingMediaItem {
  key: string;
  url?: string;
  size?: number;
}

interface WeddingMediaOption {
  value: string;
  label: string;
}

const STORY_MEDIA_FOLDERS = ['our-story', 'wedding-party'] as const;

const buildMediaLabel = (value: string) => {
  const parts = value.split('/').filter(Boolean);
  const filename = parts[parts.length - 1] || value;
  return parts.length >= 2 ? `${filename} (${parts[0]})` : filename;
};

const buildMediaOptions = (
  items: WeddingMediaItem[],
  currentValue?: string,
): WeddingMediaOption[] => {
  const options = items.map((item) => ({
    value: item.key,
    label: buildMediaLabel(item.key),
  }));

  const normalizedCurrentValue = currentValue?.trim();
  if (
    normalizedCurrentValue &&
    !options.some((option) => option.value === normalizedCurrentValue)
  ) {
    options.unshift({
      value: normalizedCurrentValue,
      label: `Current selection: ${buildMediaLabel(normalizedCurrentValue)}`,
    });
  }

  return options;
};

const getSetupStatusDotClass = (status?: WeddingSetupStatus) => {
  if (status === 'complete') {
    return 'bg-emerald-500 dark:bg-emerald-400';
  }

  if (status === 'attention') {
    return 'bg-amber-500 dark:bg-amber-400';
  }

  return 'bg-slate-300 dark:bg-slate-600';
};

export default function WeddingDetailsPage() {
 const { token, userProfile, isLoading: authLoading } = useAdmin();
 const params = useParams();
 const router = useRouter();
 const searchParams = useSearchParams();
 const weddingId = params.id as string;

 const [wedding, setWedding] = useState<Wedding | null>(null);
	 const [loading, setLoading] = useState(true);
	 const [saving, setSaving] = useState(false);
	 const [error, setError] = useState<string>('');
	 const [eventTimeErrors, setEventTimeErrors] = useState<Record<number, string>>({});
	 const [activeTab, setActiveTab] = useState<WeddingSetupTab>('events');
 const [syncing, setSyncing] = useState(false);
 const [guests, setGuests] = useState<Guest[]>([]);
 const [uploadedMedia, setUploadedMedia] = useState<WeddingMediaItem[]>([]);
 const [loadingUploadedMedia, setLoadingUploadedMedia] = useState(false);
 const [showAdRail, setShowAdRail] = useState(false);
 const canViewCoupleTab = canManageCouplePortal(userProfile);

 // Vendors tab state — fetched lazily when the tab is activated.
 const [vendorAssignments, setVendorAssignments] = useState<VendorAssignment[]>([]);
 const [vendorAssignmentsLoading, setVendorAssignmentsLoading] = useState(false);
 const [vendorAssignmentsError, setVendorAssignmentsError] = useState<string | null>(null);
 const [vendorBudgetCategories, setVendorBudgetCategories] = useState<BudgetCategory[]>([]);

 useEffect(() => {
 const setupTab = searchParams.get('setupTab');
 if (!isWeddingSetupTab(setupTab)) {
 return;
 }
 if (setupTab === 'couple' && !canViewCoupleTab) {
 return;
 }
 setActiveTab(setupTab);
 }, [canViewCoupleTab, searchParams]);

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
 rsvp_config: {
 greeting: "Join us in celebrating our special day! Please let us know if you'll be attending.",
 help_text: "Check your phone for your personal invitation link. If you need help, use the Get Help button and our planner will text you.",
 phone_numbers: [],
 hide_phone_numbers: true,
 help_button_label: "Get Help",
 ...(wedding.rsvp_config || {})
 },
 privacy_settings: normalizePrivacySettingsForMode(
 wedding.privacy_settings,
 wedding.privacy_settings?.privacy_mode ?? DEFAULT_PRIVACY_SETTINGS.privacy_mode
 ),
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
 if (authLoading || !userProfile) return;

 if (userProfile.is_root_admin) {
 router.replace('/admin/weddings');
 return;
 }

 fetchWedding();
	 }, [authLoading, fetchWedding, router, userProfile]);

 useEffect(() => {
 if (activeTab === 'couple' && !canViewCoupleTab) {
 setActiveTab('events');
 }
 }, [activeTab, canViewCoupleTab]);

	 const buildEventTimeErrors = (events: WeddingEvent[]): Record<number, string> => {
	 return events.reduce<Record<number, string>>((acc, event, index) => {
	 const message = getEventTimeValidationMessage(event.details?.time);
	 if (message) acc[index] = message;
	 return acc;
	 }, {});
	 };

	 const clearEventTimeError = (index: number) => {
	 setEventTimeErrors((prev) => {
	 if (!(index in prev)) return prev;
	 const next = { ...prev };
	 delete next[index];
	 return next;
	 });
	 };

	 const reindexEventTimeErrorsAfterRemoval = (index: number) => {
	 setEventTimeErrors((prev) => {
	 const next: Record<number, string> = {};
	 Object.entries(prev).forEach(([key, value]) => {
	 const numericKey = Number(key);
	 if (numericKey < index) next[numericKey] = value;
	 if (numericKey > index) next[numericKey - 1] = value;
	 });
	 return next;
	 });
	 };

 const handlePrivacyModeChange = (mode: PrivacyMode) => {
 if (!wedding) return;

 setWedding({
 ...wedding,
 privacy_settings: normalizePrivacySettingsForMode(wedding.privacy_settings, mode),
 });
 };

 // Fetch guests for wedding party sync
 const fetchGuests = useCallback(async () => {
   if (!weddingId) return;
   try {
     const baseUrl = getApiBaseUrl();
     const response = await fetch(`${baseUrl}/admin/guests?wedding_id=${weddingId}&fetch_all=true`, {
       headers: {
         'Authorization': `Bearer ${token}`,
         'Content-Type': 'application/json'
       }
     });
     if (response.ok) {
       const data = await response.json();
       setGuests(extractGuestList<Guest>(data));
     }
   } catch (err) {
     console.error('Failed to fetch guests:', err);
   }
 }, [token, weddingId]);

 const fetchUploadedMedia = useCallback(async (weddingSlug: string) => {
   if (!token) return;

   setLoadingUploadedMedia(true);
   try {
     const baseUrl = getApiBaseUrl();
     const nextMedia: WeddingMediaItem[] = [];
     const seenKeys = new Set<string>();

     for (const folder of STORY_MEDIA_FOLDERS) {
       const response = await fetch(
         `${baseUrl}/admin/gallery/list?prefix=${folder}/${weddingSlug}/`,
         {
           headers: {
             'Authorization': `Bearer ${token}`,
             'Content-Type': 'application/json',
           },
         }
       );

       if (!response.ok) {
         throw new Error(`Failed to load ${folder} media`);
       }

       const data = await response.json();
       for (const item of Array.isArray(data) ? data : []) {
         if (!item?.key || seenKeys.has(item.key)) {
           continue;
         }
         seenKeys.add(item.key);
         nextMedia.push(item);
       }
     }

     setUploadedMedia(nextMedia);
   } catch (err) {
     console.error('Failed to fetch wedding media:', err);
     setUploadedMedia([]);
     toast.error('Failed to load uploaded story and wedding-party images');
   } finally {
     setLoadingUploadedMedia(false);
   }
 }, [token]);

 // Fetch guests when story tab is active (for sync feature)
 useEffect(() => {
   if (activeTab === 'story') {
     fetchGuests();
   }
 }, [activeTab, fetchGuests]);

 useEffect(() => {
   if (activeTab === 'story' && wedding?.slug) {
     fetchUploadedMedia(wedding.slug);
   }
 }, [activeTab, fetchUploadedMedia, wedding?.slug]);

 // Fetch vendor assignments + budget categories when the vendors tab opens.
 // Both calls happen in parallel; budget-categories is a best-effort
 // lookup used to render category names (failure renders "—").
 const fetchVendorAssignments = useCallback(async () => {
   if (!token || !weddingId) return;
   setVendorAssignmentsLoading(true);
   setVendorAssignmentsError(null);
   try {
     const [assignments, categories] = await Promise.all([
       getWeddingVendors(token, weddingId),
       budgetApi.getBudgetCategories(token, weddingId).catch(() => []),
     ]);
     setVendorAssignments(Array.isArray(assignments) ? assignments : []);
     setVendorBudgetCategories(Array.isArray(categories) ? categories : []);
   } catch (err) {
     setVendorAssignmentsError(
       err instanceof Error ? err.message : 'Failed to load vendors'
     );
     setVendorAssignments([]);
   } finally {
     setVendorAssignmentsLoading(false);
   }
 }, [token, weddingId]);

 useEffect(() => {
   if (activeTab === 'vendors') {
     fetchVendorAssignments();
   }
 }, [activeTab, fetchVendorAssignments]);

 // Sync wedding party from guests
 const syncWeddingPartyFromGuests = async () => {
   if (!wedding) return;

   setSyncing(true);
   try {
     // Fetch latest guests
     const baseUrl = getApiBaseUrl();
     const response = await fetch(`${baseUrl}/admin/guests?wedding_id=${weddingId}&fetch_all=true`, {
       headers: {
         'Authorization': `Bearer ${token}`,
         'Content-Type': 'application/json'
       }
     });

     if (!response.ok) throw new Error('Failed to fetch guests');
     const guestList = extractGuestList<Guest>(await response.json());

     console.log('Fetched guests for sync:', guestList.length);
     console.log('Guests with group_id:', guestList.filter(g => g.group_id).map(g => ({ name: g.name, group_id: g.group_id })));

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

	 const hasUnnamedCustomEvent = wedding.events.some(
	 (event) => getWeddingEventSelectValue(event) === 'other' && !event.custom_type_label?.trim()
	 );
	 if (hasUnnamedCustomEvent) {
	 setError('Give every custom event a name before saving.');
	 toast.error('Give every custom event a name before saving.');
	 return;
	 }

	 const nextEventTimeErrors = buildEventTimeErrors(wedding.events);
	 if (Object.keys(nextEventTimeErrors).length > 0) {
	 setEventTimeErrors(nextEventTimeErrors);
	 setError('Fix the invalid event time fields before saving.');
	 toast.error('Fix the invalid event time fields before saving.');
	 return;
	 }

 const normalizedPrivacySettings = normalizePrivacySettingsForMode(
 wedding.privacy_settings,
 wedding.privacy_settings?.privacy_mode ?? DEFAULT_PRIVACY_SETTINGS.privacy_mode
 );

 if (
 normalizedPrivacySettings.privacy_mode === 'password' &&
 !normalizedPrivacySettings.password_protection?.trim()
 ) {
 setError('Add a password before saving password-protected access.');
 toast.error('Add a password before saving password-protected access.');
 return;
 }

	 setSaving(true);
	 setError('');

	 try {
	 const normalizedWedding = {
	 ...wedding,
 privacy_settings: normalizedPrivacySettings,
	 events: wedding.events.map((event) => ({
	 ...event,
	 details: event.details
	 ? { ...event.details, time: normalizeEventTimeInput(event.details.time) || undefined }
	 : event.details,
	 })),
	 };
	 setWedding(normalizedWedding);

	 const baseUrl = getApiBaseUrl();
	 const response = await fetch(`${baseUrl}/admin/weddings/${weddingId}`, {
	 method: 'PUT',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
	 body: JSON.stringify(normalizedWedding),
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

 const ourStoryImages = uploadedMedia.filter((image) => image.key.startsWith('our-story/'));
 const weddingPartyImages = uploadedMedia.filter((image) => image.key.startsWith('wedding-party/'));

 // Event management functions
	 const updateEvent = (index: number, event: WeddingEvent) => {
	 if (!wedding) return;
	 const newEvents = [...wedding.events];
	 newEvents[index] = event;
	 setWedding({ ...wedding, events: newEvents });
	 if (eventTimeErrors[index]) {
	 const message = getEventTimeValidationMessage(event.details?.time);
	 if (message) {
	 setEventTimeErrors((prev) => ({ ...prev, [index]: message }));
	 } else {
	 clearEventTimeError(index);
	 }
	 }
	 };

const addEvent = () => {
 if (!wedding) return;
 setWedding({
 ...wedding,
 events: [...wedding.events, { type: 'reception', date: '', details: {} }]
 });
 };

 const updateEventTypeSelection = (index: number, selectedValue: string) => {
 if (!wedding) return;

 const nextEvents = [...wedding.events];
 const currentEvent = nextEvents[index];

 if (selectedValue === 'other') {
 nextEvents[index] = {
 ...currentEvent,
 type: currentEvent.custom_type_label
 ? currentEvent.type
 : createCustomWeddingEventTypeKey('custom_event'),
 custom_type_label: currentEvent.custom_type_label || '',
 };
 } else {
 nextEvents[index] = {
 ...currentEvent,
 type: selectedValue,
 custom_type_label: undefined,
 };
 }

 setWedding({
 ...wedding,
 events: nextEvents,
 });
 };

 const updateCustomEventLabel = (index: number, customLabel: string) => {
 if (!wedding) return;

 const nextEvents = [...wedding.events];
 const currentEvent = nextEvents[index];
 nextEvents[index] = {
 ...currentEvent,
 type: currentEvent.custom_type_label
 ? currentEvent.type
 : createCustomWeddingEventTypeKey(customLabel || 'custom_event'),
 custom_type_label: customLabel,
 };

 setWedding({
 ...wedding,
 events: nextEvents,
 });
 };

	 const removeEvent = (index: number) => {
	 if (!wedding) return;
	 reindexEventTimeErrorsAfterRemoval(index);
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

 if (authLoading || userProfile?.is_root_admin || loading) {
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

 const setupSummary = buildWeddingSetupSummary(wedding, {
 canViewCoupleTab,
 vendorAssignmentCount: vendorAssignments.length,
 });
 const setupStepByTab = new Map(
 setupSummary.steps.map((step) => [step.tab, step])
 );

 return (
 <div className="min-h-screen bg-gradient-to-br from-wedding-ivory to-rose-50 dark:from-slate-900 dark:to-slate-800 p-4 sm:p-6">
 <div className="max-w-7xl mx-auto">
 <div className={`grid grid-cols-1 ${showAdRail ? 'lg:grid-cols-4' : ''} gap-6`}>
 <div className={showAdRail ? 'lg:col-span-3' : ''}>
 {/* Header */}
 <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl overflow-hidden mb-8">
 <div className="bg-gradient-to-r from-wedding-navy to-wedding-gold px-4 sm:px-8 py-4 sm:py-6">
 <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
 <div>
 <h1 className="text-xl sm:text-3xl font-bold text-white break-words">{wedding.couple_names}</h1>
 <p className="text-blue-100 mt-1 sm:mt-2 text-sm sm:text-base">Configure wedding details and content</p>
 </div>
 <div className="grid w-full grid-cols-2 gap-2 sm:flex sm:w-auto sm:gap-3">
 <Link
 href="/admin/weddings"
 className="rounded-lg border border-white/70 bg-white/90 px-4 py-2 text-center text-sm font-semibold text-wedding-navy shadow-sm transition-colors hover:bg-white sm:flex-initial sm:px-6 sm:py-3 sm:text-base dark:border-white/20 dark:bg-white/10 dark:text-white dark:hover:bg-white/20"
 >
 Back
 </Link>
 <Link
 href={`/admin/seating?weddingId=${weddingId}`}
 className="rounded-lg bg-wedding-sage/80 px-4 py-2 text-center text-sm font-semibold text-white transition-colors hover:bg-wedding-sage sm:flex-initial sm:px-6 sm:py-3 sm:text-base"
 >
 Seating Plan
 </Link>
 <PaymentCollectionButton
 weddingId={weddingId}
 weddingTitle={wedding?.couple_names || 'Wedding'}
 variant="outline"
 size="default"
 className="w-full justify-center border-white/70 bg-white/90 text-sm text-wedding-navy hover:bg-white sm:w-auto sm:text-base dark:border-white/20 dark:bg-white/10 dark:text-white dark:hover:bg-white/20"
 />
 <button
 onClick={saveWedding}
 disabled={saving}
 className="w-full rounded-lg bg-wedding-navy px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-wedding-navy/90 disabled:opacity-50 sm:w-auto sm:flex-initial sm:px-6 sm:py-3 sm:text-base dark:bg-white dark:text-wedding-navy dark:hover:bg-slate-100"
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

 <WeddingSetupGuide
 wedding={wedding}
 activeTab={activeTab}
 canViewCoupleTab={canViewCoupleTab}
 vendorAssignmentCount={vendorAssignments.length}
 onSelectTab={(tab) => setActiveTab(tab)}
 />

 {/* Tabs */}
 <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl overflow-hidden mb-8">
 <div className="border-b border-gray-200 dark:border-gray-700">
 <nav className="flex overflow-x-auto scrollbar-hide">
 {([
 'events',
 'vendors',
 'rsvp',
 'privacy',
 'registry',
 'faq',
 'theme',
 'story',
 ...(canViewCoupleTab ? (['couple'] as const) : []),
 ] as const).map((tab) => {
 const setupStep = setupStepByTab.get(tab);
 return (
 <button
 key={tab}
 onClick={() => setActiveTab(tab)}
 className={`px-3 sm:px-6 py-3 sm:py-4 text-xs sm:text-sm font-medium capitalize whitespace-nowrap flex items-center gap-1.5 ${
 activeTab === tab
 ? 'text-wedding-navy dark:text-wedding-gold border-b-2 border-wedding-rose dark:border-wedding-gold'
 : 'text-gray-600 dark:text-gray-400 hover:text-wedding-navy dark:hover:text-gray-200'
 }`}
 >
 {tab === 'couple' && <HeartHandshake className="w-4 h-4" />}
 {tab === 'rsvp' ? 'RSVP' : tab === 'faq' ? 'FAQ' : tab === 'story' ? 'Story' : tab === 'couple' ? 'Couple' : tab}
 {setupStep && (
 <span
 aria-hidden="true"
 className={`h-2 w-2 rounded-full ${getSetupStatusDotClass(setupStep.status)}`}
 />
 )}
 {setupStep && <span className="sr-only"> {setupStep.statusLabel}</span>}
 </button>
 );
 })}
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
 {getWeddingEventLabel(event.type, event.custom_type_label)} - {event.date}
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
 value={getWeddingEventSelectValue(event)}
 onChange={(e) => updateEventTypeSelection(index, e.target.value)}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 >
 {WEDDING_EVENT_SELECT_OPTIONS.map((option) => (
 <option key={option.value} value={option.value}>{option.label}</option>
 ))}
 </select>
 </div>

 {getWeddingEventSelectValue(event) === 'other' && (
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Custom Event Name
 </label>
 <input
 type="text"
 value={event.custom_type_label || ''}
 onChange={(e) => updateCustomEventLabel(index, e.target.value)}
 placeholder="e.g., Welcome Party"
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 />
 </div>
 )}

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
	 onBlur={(e) => {
	 const normalizedTime = normalizeEventTimeInput(e.target.value);
	 updateEvent(index, {
	 ...event,
	 details: { ...event.details, time: normalizedTime }
	 });
	 const message = getEventTimeValidationMessage(normalizedTime);
	 if (message) {
	 setEventTimeErrors((prev) => ({ ...prev, [index]: message }));
	 } else {
	 clearEventTimeError(index);
	 }
	 }}
	 aria-invalid={Boolean(eventTimeErrors[index])}
	 className={`w-full px-3 py-2 border rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 ${
	 eventTimeErrors[index]
	 ? 'border-red-500 dark:border-red-400'
	 : 'border-gray-300 dark:border-gray-600'
	 }`}
	 placeholder="e.g., 3:00 PM"
	 title={EVENT_TIME_FORMAT_HINT}
	 />
	 {eventTimeErrors[index] && (
	 <p className="mt-1 text-xs text-red-600 dark:text-red-300">{eventTimeErrors[index]}</p>
	 )}
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

 {/* Vendors Tab */}
 {activeTab === 'vendors' && (
 <div className="space-y-6">
 <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-4">
 <div>
 <h2 className="text-2xl font-bold text-wedding-navy dark:text-gray-100">Vendors</h2>
 <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
 Vendors assigned to this wedding, with their contracts and payment status.
 </p>
 </div>
 <Link
 href="/admin/vendors"
 className="bg-wedding-sage text-white px-4 py-2 rounded-lg hover:bg-opacity-90 text-center whitespace-nowrap"
 >
 Manage directory
 </Link>
 </div>

 {vendorAssignmentsLoading && (
 <div className="flex items-center justify-center py-12 text-gray-500 dark:text-gray-400">
 <Loader2 className="w-5 h-5 animate-spin mr-2" />
 Loading vendors...
 </div>
 )}

 {!vendorAssignmentsLoading && vendorAssignmentsError && (
 <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-900/20 dark:text-red-200">
 {vendorAssignmentsError}
 </div>
 )}

 {!vendorAssignmentsLoading && !vendorAssignmentsError && vendorAssignments.length === 0 && (
 <div className="rounded-xl border border-dashed border-gray-300 dark:border-gray-700 px-6 py-10 text-center">
 <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
 No vendors assigned to this wedding yet
 </h3>
 <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
 Add a vendor from the directory to start tracking quotes, contracts, and payments for this wedding.
 </p>
 <Link
 href="/admin/vendors"
 className="inline-flex items-center bg-wedding-rose text-white px-4 py-2 rounded-lg hover:bg-opacity-90"
 >
 Add vendor
 </Link>
 </div>
 )}

 {!vendorAssignmentsLoading && !vendorAssignmentsError && vendorAssignments.length > 0 && (
 <div className="space-y-3">
 {[...vendorAssignments]
 .sort((a, b) => {
 // Action-required statuses float to the top.
 const order: Record<string, number> = {
 inquiry: 0, quoted: 1, contracted: 2, confirmed: 3, completed: 4, cancelled: 5,
 };
 const ai = order[a.status] ?? 99;
 const bi = order[b.status] ?? 99;
 if (ai !== bi) return ai - bi;
 return (a.vendor_name || '').localeCompare(b.vendor_name || '');
 })
 .map((assignment) => {
 const assignmentId = assignment._id;
 const categoryName = assignment.budget_category_id
 ? vendorBudgetCategories.find(
 (c) => c.id === assignment.budget_category_id
 )?.name
 : null;
 const statusClass = (() => {
 switch (assignment.status) {
 case 'completed':
 return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200';
 case 'cancelled':
 return 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300';
 case 'confirmed':
 case 'contracted':
 return 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200';
 case 'quoted':
 return 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200';
 case 'inquiry':
 default:
 return 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-200';
 }
 })();
 const fmt = (n: number) =>
 new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n);

 return (
 <div
 key={assignmentId}
 className="border border-gray-200 dark:border-gray-700 rounded-xl p-4 hover:shadow-lg transition-shadow"
 >
 <div className="flex items-start justify-between gap-3">
 <div className="flex items-center gap-3 min-w-0 flex-1">
 <div className="w-12 h-12 bg-gradient-to-br from-wedding-rose to-wedding-gold rounded-lg flex items-center justify-center text-white font-bold shrink-0">
 {(assignment.vendor_name || '?').charAt(0)}
 </div>
 <div className="min-w-0 flex-1">
 <div className="font-semibold text-gray-900 dark:text-gray-100 truncate" title={assignment.vendor_name}>
 {assignment.vendor_name}
 </div>
 <div className="text-sm text-gray-500 dark:text-gray-400 truncate capitalize">
 {assignment.service_category}
 </div>
 </div>
 </div>
 <span className={`px-3 py-1 text-xs font-medium rounded-full whitespace-nowrap shrink-0 capitalize ${statusClass}`}>
 {assignment.status}
 </span>
 </div>

 <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
 <div>
 <div className="text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide mb-0.5">Budget category</div>
 <div className="text-gray-900 dark:text-gray-100 truncate" title={categoryName || ''}>
 {categoryName || <span className="text-gray-400">—</span>}
 </div>
 </div>
 <div>
 <div className="text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide mb-0.5">Contracted</div>
 <div className="text-gray-900 dark:text-gray-100">
 {assignment.contracted_amount != null
 ? fmt(assignment.contracted_amount)
 : <span className="text-gray-400">—</span>}
 </div>
 </div>
 <div>
 <div className="text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide mb-0.5">Paid</div>
 <div className="text-green-600 dark:text-green-400">
 {fmt(assignment.paid_amount || 0)}
 </div>
 </div>
 </div>

 {assignment.contract_id && (
 <div className="mt-4 pt-3 border-t border-gray-200 dark:border-gray-700">
 <Link
 href={`/admin/vendors/contracts/${assignment.contract_id}`}
 className="text-sm text-wedding-rose hover:opacity-80 font-medium"
 >
 View contract →
 </Link>
 </div>
 )}
 </div>
 );
 })}
 </div>
 )}
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
 Help Button Label
 </label>
 <input
 type="text"
 value={wedding.rsvp_config.help_button_label || 'Get Help'}
 onChange={(e) => setWedding({
 ...wedding,
 rsvp_config: { ...wedding.rsvp_config!, help_button_label: e.target.value }
 })}
 className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 maxLength={40}
 />
 </div>

 <label className="flex items-start gap-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-slate-800/70 p-4">
 <input
 type="checkbox"
 checked={wedding.rsvp_config.hide_phone_numbers ?? true}
 onChange={(e) => setWedding({
 ...wedding,
 rsvp_config: { ...wedding.rsvp_config!, hide_phone_numbers: e.target.checked }
 })}
 className="mt-1 h-4 w-4 rounded border-gray-300 text-wedding-rose focus:ring-wedding-rose"
 />
 <span>
 <span className="block text-sm font-medium text-gray-800 dark:text-gray-100">
 Hide public phone numbers
 </span>
 <span className="mt-1 block text-sm text-gray-500 dark:text-gray-400">
 When enabled, guests see the help button instead of planner phone numbers. Stored numbers remain available if you choose to show them later.
 </span>
 </span>
 </label>

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
 <div className="space-y-3">
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
 Privacy Mode
 </label>
 <PrivacyModeSelector
 value={wedding.privacy_settings.privacy_mode}
 onChange={handlePrivacyModeChange}
 />
 <p className="text-sm text-gray-500 dark:text-gray-400">
 {getPrivacyModeSummary(wedding.privacy_settings.privacy_mode)}
 </p>
 </div>

 {/* Password Protection (only shown for password mode) */}
 {wedding.privacy_settings.privacy_mode === 'password' && (
 <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-slate-800/70 p-4">
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

 <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 dark:border-blue-900/60 dark:bg-blue-900/20">
 <h3 className="text-base font-semibold text-blue-900 dark:text-blue-100">
 {getPrivacyModeCallout(wedding.privacy_settings.privacy_mode).title}
 </h3>
 <p className="mt-2 text-sm leading-6 text-blue-800 dark:text-blue-200">
 {getPrivacyModeCallout(wedding.privacy_settings.privacy_mode).body}
 </p>
 <p className="mt-3 text-xs text-blue-700 dark:text-blue-300">
 Privacy mode is the source of truth for guest access across the landing page, RSVP flow, and gallery.
 </p>
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
 Gallery Manager now writes planner-scoped storage paths automatically. Legacy <code className="bg-blue-100 dark:bg-blue-800/50 px-1 rounded">folder/{wedding.slug}/...</code> keys still resolve, but story and wedding-party photos should now be assigned from the uploaded media selectors below.
 </p>
 <ul className="text-sm text-blue-700 dark:text-blue-300 space-y-1">
 <li>• Gallery Manager keeps public gallery, story, and wedding-party assets separated automatically.</li>
 <li>• Existing legacy keys remain valid during the migration window.</li>
 <li>• The selectors below only show images already uploaded for this wedding’s story and wedding-party folders.</li>
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
 <select
 value={wedding.our_story?.image_url || ''}
 onChange={(e) => setWedding({
 ...wedding,
 our_story: { ...wedding.our_story!, image_url: e.target.value }
 })}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 >
 <option value="">No story image</option>
 {buildMediaOptions(ourStoryImages, wedding.our_story?.image_url).map((option) => (
 <option key={option.value} value={option.value}>
 {option.label}
 </option>
 ))}
 </select>
 <div className="mt-2 flex items-center justify-between gap-3 text-sm text-gray-500 dark:text-gray-400">
 <span>
 {loadingUploadedMedia
   ? 'Loading uploaded story images...'
   : `${ourStoryImages.length} uploaded story image${ourStoryImages.length === 1 ? '' : 's'} available`}
 </span>
 {wedding.our_story?.image_url && (
 <code className="truncate rounded bg-gray-100 px-2 py-1 text-xs dark:bg-slate-800">
 {wedding.our_story.image_url}
 </code>
 )}
 </div>
{resolveMediaUrl(wedding.our_story?.image_url) && (
<div className="mt-3 flex items-center gap-3 rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-slate-800/70">
 <img
 src={resolveMediaUrl(wedding.our_story?.image_url)}
 alt="Selected story"
 className="h-16 w-16 rounded-lg object-cover border border-gray-200 dark:border-gray-700"
 />
 <div className="min-w-0">
 <p className="text-sm font-medium text-gray-800 dark:text-gray-100">Selected story image</p>
 <p className="truncate text-xs text-gray-500 dark:text-gray-400">
 {wedding.our_story?.image_url}
 </p>
 </div>
 </div>
 )}
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
 Last synced: {formatAdminTimestamp(wedding.wedding_party_sync.last_synced_at)}
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
 Photo (optional)
 </label>
 <select
 value={member.image_url || ''}
 onChange={(e) => {
 const updated = [...wedding.wedding_party!];
 updated[index] = { ...member, image_url: e.target.value };
 setWedding({ ...wedding, wedding_party: updated });
 }}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
 >
 <option value="">No member photo</option>
 {buildMediaOptions(weddingPartyImages, member.image_url).map((option) => (
 <option key={option.value} value={option.value}>
 {option.label}
 </option>
 ))}
 </select>
 <div className="mt-2 flex items-center justify-between gap-3 text-sm text-gray-500 dark:text-gray-400">
 <span>
 {loadingUploadedMedia
   ? 'Loading uploaded wedding-party images...'
   : `${weddingPartyImages.length} uploaded wedding-party image${weddingPartyImages.length === 1 ? '' : 's'} available`}
 </span>
 {member.image_url && (
 <code className="truncate rounded bg-gray-100 px-2 py-1 text-xs dark:bg-slate-800">
 {member.image_url}
 </code>
 )}
 </div>
{resolveMediaUrl(member.image_url) && (
<div className="mt-3 flex items-center gap-3 rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-slate-800/70">
 <img
 src={resolveMediaUrl(member.image_url)}
 alt={member.name || 'Wedding party member'}
 className="h-16 w-16 rounded-full object-cover border border-gray-200 dark:border-gray-700"
 />
 <div className="min-w-0">
 <p className="text-sm font-medium text-gray-800 dark:text-gray-100">Selected member photo</p>
 <p className="truncate text-xs text-gray-500 dark:text-gray-400">
 {member.image_url}
 </p>
 </div>
 </div>
 )}
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

 {/* Couple Tab */}
 {canViewCoupleTab && activeTab === 'couple' && (
 <CoupleTab weddingId={weddingId} token={token || ''} />
 )}

 </div>

 {/* Right Sidebar - Sponsored Vendors (hidden when ads disabled) */}
 <div className={showAdRail ? 'lg:col-span-1' : 'hidden'}>
 <div className="sticky top-6">
 <CampaignSponsoredRail onVisibilityChange={setShowAdRail} />
 </div>
 </div>
 </div>
 </div>
 </div>
 </div>
 </div>
 );
}


// ============================================================================
// COUPLE TAB — Manages couple access, messaging, and digest emails
// ============================================================================

interface CoupleUser {
  id: string;
  email: string;
  partner1_name?: string;
  partner2_name?: string;
  wedding_id: string;
  is_active: boolean;
  access_state?: 'pending_setup' | 'active' | 'revoked_by_planner' | 'owner_cancelled';
  setup_completed: boolean;
  wedding_archived?: boolean;
  setup_link?: string | null;
  setup_link_expires_at?: string | null;
  last_login?: string;
  created_at?: string;
}

function CoupleTab({ weddingId, token }: { weddingId: string; token: string }) {
  const [couples, setCouples] = useState<CoupleUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [invitePartner1, setInvitePartner1] = useState('');
  const [invitePartner2, setInvitePartner2] = useState('');
  const [inviting, setInviting] = useState(false);
  const [copyingCoupleId, setCopyingCoupleId] = useState<string | null>(null);

  const resolveLifecycleState = (couple: CoupleUser) => {
    if (couple.wedding_archived) return 'archived_readonly' as const;
    if (couple.access_state) return couple.access_state;
    if (!couple.setup_completed) return 'pending_setup' as const;
    return couple.is_active ? 'active' as const : 'revoked_by_planner' as const;
  };

  const getLifecycleBadge = (couple: CoupleUser) => {
    const state = resolveLifecycleState(couple);
    switch (state) {
      case 'active':
        return {
          label: 'Active',
          avatarClass: 'bg-green-500',
          badgeClass: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
        };
      case 'revoked_by_planner':
        return {
          label: 'Revoked',
          avatarClass: 'bg-red-400',
          badgeClass: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
        };
      case 'owner_cancelled':
        return {
          label: 'Planner Inactive',
          avatarClass: 'bg-slate-400',
          badgeClass: 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-300',
        };
      case 'archived_readonly':
        return {
          label: 'Archived Read-Only',
          avatarClass: 'bg-amber-500',
          badgeClass: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
        };
      case 'pending_setup':
      default:
        return {
          label: 'Pending Setup',
          avatarClass: 'bg-amber-400',
          badgeClass: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
        };
    }
  };

  const fetchCouples = useCallback(async () => {
    if (!token || !weddingId) return;
    try {
      const res = await fetch(`${getApiBaseUrl()}/admin/couple-portal/couples?wedding_id=${weddingId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setCouples(data.couples || []);
      }
    } catch (err) {
      console.error('Failed to fetch couples', err);
    } finally {
      setLoading(false);
    }
  }, [token, weddingId]);

  useEffect(() => {
    fetchCouples();
  }, [fetchCouples]);

  // Invite couple
  const handleInvite = async () => {
    if (!inviteEmail || !invitePartner1) {
      toast.error('Email and partner name are required');
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
          wedding_id: weddingId,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.setup_link && navigator.clipboard?.writeText) {
          try {
            await navigator.clipboard.writeText(data.setup_link);
            toast.success('Invitation sent. Current setup link copied.');
          } catch {
            toast.success('Invitation sent!');
          }
        } else {
          toast.success('Invitation sent!');
        }
        setShowInviteForm(false);
        setInviteEmail('');
        setInvitePartner1('');
        setInvitePartner2('');
        await fetchCouples();
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
        const data = await res.json();
        if (data.setup_link && navigator.clipboard?.writeText) {
          try {
            await navigator.clipboard.writeText(data.setup_link);
            toast.success('Invitation resent. Current setup link copied.');
          } catch {
            toast.success('Invitation resent');
          }
        } else {
          toast.success('Invitation resent');
        }
        await fetchCouples();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to resend');
      }
    } catch {
      toast.error('Failed to connect');
    }
  };

  const handleCopySetupLink = async (couple: CoupleUser) => {
    if (!couple.setup_link) {
      toast.error('No active setup link is available for this couple.');
      return;
    }

    setCopyingCoupleId(couple.id);
    try {
      if (!navigator.clipboard?.writeText) {
        toast.error('Clipboard access is not available in this browser.');
        return;
      }

      await navigator.clipboard.writeText(couple.setup_link);
      toast.success('Current setup link copied.');
    } catch {
      toast.error('Failed to copy setup link.');
    } finally {
      setCopyingCoupleId(null);
    }
  };


  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Couple Access Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold text-wedding-navy dark:text-gray-100">Couple Access</h2>
          <button
            onClick={() => setShowInviteForm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-wedding-sage text-white text-sm rounded-lg hover:bg-opacity-90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Invite Couple
          </button>
        </div>

        {couples.length === 0 ? (
          <div className="text-center py-10 text-gray-400 dark:text-gray-500">
            <Users className="w-10 h-10 mx-auto mb-3 opacity-50" />
            <p className="font-medium">No couple linked yet</p>
            <p className="text-sm mt-1">Invite the couple so they can view and collaborate on their wedding details.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {couples.map((couple) => (
              <div key={couple.id} className="bg-gray-50 dark:bg-slate-700/50 rounded-xl p-4 flex items-center justify-between">
                {(() => {
                  const lifecycle = resolveLifecycleState(couple);
                  const badge = getLifecycleBadge(couple);
                  return (
                    <>
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-medium ${badge.avatarClass}`}>
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
                  <span className={`text-xs px-2 py-1 rounded-full ${badge.badgeClass}`}>
                    {badge.label}
                  </span>

                  {lifecycle === 'pending_setup' && (
                    <>
                      {couple.setup_link ? (
                        <button
                          onClick={() => handleCopySetupLink(couple)}
                          className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                          title="Copy the current invitation setup link"
                        >
                          {copyingCoupleId === couple.id ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                          Copy Link
                        </button>
                      ) : (
                        <span
                          className="text-xs text-amber-600 dark:text-amber-400"
                          title="The previous setup link has expired. Resend to generate a new one."
                        >
                          Link expired
                        </span>
                      )}

                      <button
                        onClick={() => handleResend(couple.id)}
                        className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                        title="Resend invitation email"
                      >
                        <RefreshCw className="w-3 h-3" />
                        Resend
                      </button>
                    </>
                  )}

                  {lifecycle === 'active' && (
                    <button
                      onClick={() => handleToggleAccess(couple.id, true)}
                      className="text-xs flex items-center gap-1 text-red-600 hover:text-red-700"
                    >
                      <><ShieldOff className="w-3 h-3" /> Revoke Access</>
                    </button>
                  )}

                  {lifecycle === 'revoked_by_planner' && (
                    <button
                      onClick={() => handleToggleAccess(couple.id, false)}
                      className="text-xs flex items-center gap-1 text-green-600 hover:text-green-700"
                    >
                      <><ShieldCheck className="w-3 h-3" /> Restore Access</>
                    </button>
                  )}

                  {lifecycle === 'owner_cancelled' && (
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      Planner subscription inactive
                    </span>
                  )}

                  {lifecycle === 'archived_readonly' && (
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      Archived portal
                    </span>
                  )}

                  {couple.last_login && (
                    <span className="text-xs text-gray-400 dark:text-gray-500" title="Last login">
                      {new Date(couple.last_login).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    </span>
                  )}
                </div>
                    </>
                  );
                })()}
              </div>
            ))}
          </div>
        )}
      </div>


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
                  placeholder="First partner's name"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">Partner 2 Name</label>
                <input
                  type="text"
                  value={invitePartner2}
                  onChange={(e) => setInvitePartner2(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-200"
                  placeholder="Second partner's name"
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
                className="px-4 py-2 bg-wedding-sage text-white text-sm rounded-lg hover:bg-opacity-90 disabled:opacity-50 flex items-center gap-2"
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
