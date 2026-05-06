'use client';

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { useSSE } from '@/hooks/useSSE';
import { BUILT_IN_WEDDING_EVENT_OPTIONS, getWeddingEventLabel, getWeddingEventOptions } from '@/utils/weddingEvents';
import { getApiBaseUrl } from '@/utils/env';
import PageHeader from '../components/PageHeader';
import WeddingPicker from '../components/WeddingPicker';
import { MessageEnrichment } from '@/components/ui/MessageEnrichment';
import { usePagination } from '@/admin/hooks/usePagination';
import { GlassPagination } from '@/admin/components/ui/glass/GlassPagination';
import {
  EMPTY_GUEST_LIST_FILTER_OPTIONS,
  EMPTY_GUEST_LIST_SUMMARY,
  extractGuestListResponse,
  type GuestListFilterOptions,
  type GuestListSummary,
} from '@/admin/utils/guestListResponse';
import { loadGuestActivityItems } from '@/admin/utils/guestActivityResponse';

// ==================== INTERFACES ====================

interface Wedding {
  id?: string;
  _id?: string;
  couple_names: string;
  date: string;
  slug: string;
  events?: Array<{
    type: string;
    custom_type_label?: string;
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
  sms_opt_in?: boolean | null;
  email_opt_in?: boolean | null;
  invite_sent?: boolean;
  invite_sent_date?: string;
  created_at?: string;
  updated_at?: string;
}

interface RSVP {
  _id?: string;
  guest_id: string;
  attending: string[];
  dietary?: string;
  submitted_at: string;
  confirmed_by_admin?: boolean;
}

interface PlusOne {
  _id?: string;
  guest_id: string;
  name: string;
  phone?: string;
  email?: string;
  dietary?: string;
  attending: string[];
  sms_opt_in?: boolean | null;
  email_opt_in?: boolean | null;
}

type SortField = 'name' | 'email' | 'phone' | 'role' | 'group_id' | 'rsvp_status' | 'plus_ones';
type SortDirection = 'asc' | 'desc';
type ViewMode = 'table' | 'cards';
type RsvpStatusFilter = 'all' | 'responded' | 'pending' | 'not_invited';
type PlusOneStatusFilter = 'all' | 'allowed' | 'submitted' | 'none';
type PhoneIssueFilter = 'all' | 'invalid_or_unreachable' | 'no_contact';
type SmsStatusFilter = 'all' | 'opted_in' | 'opted_out';

interface GuestColumnFilters {
  name: string;
  email: string;
  phone: string;
  groupId: string;
  role: string;
  rsvpStatus: RsvpStatusFilter;
  plusOneStatus: PlusOneStatusFilter;
  phoneIssue: PhoneIssueFilter;
  smsStatus: SmsStatusFilter;
}

// Preset guest groups
const PRESET_GROUPS = [
  { id: 'family_bride', label: "Family of the Bride" },
  { id: 'family_groom', label: "Family of the Groom" },
  { id: 'maid_of_honor', label: "Maid of Honor", isWeddingParty: true, side: 'bride' as const },
  { id: 'bridesmaids', label: "Bridesmaids", isWeddingParty: true, side: 'bride' as const },
  { id: 'best_man', label: "Best Man", isWeddingParty: true, side: 'groom' as const },
  { id: 'groomsmen', label: "Groomsmen", isWeddingParty: true, side: 'groom' as const },
  { id: 'friends_bride', label: "Friends of the Bride" },
  { id: 'friends_groom', label: "Friends of the Groom" },
  { id: 'coworkers', label: "Coworkers" },
  { id: 'neighbors', label: "Neighbors" },
  { id: 'vip', label: "VIP Guests" },
];

// Wedding party group IDs for sync feature (bridesmaids, groomsmen, maid of honor, best man)
const WEDDING_PARTY_GROUP_IDS = ['maid_of_honor', 'bridesmaids', 'best_man', 'groomsmen'];

// ==================== MAIN COMPONENT ====================

export default function AdminGuestsPage() {
  const { token, apiRequest } = useAdmin();
  const router = useRouter();
  const apiBaseUrl = getApiBaseUrl();
  const searchParams = useSearchParams();
  const didHydrateFiltersFromUrl = useRef(false);

  // Data state
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [selectedWedding, setSelectedWedding] = useState<string>('');
  const [guests, setGuests] = useState<Guest[]>([]);
  const [rsvps, setRsvps] = useState<RSVP[]>([]);
  const [plusOnes, setPlusOnes] = useState<PlusOne[]>([]);
  const [summary, setSummary] = useState<GuestListSummary>(EMPTY_GUEST_LIST_SUMMARY);
  const [filterOptions, setFilterOptions] = useState<GuestListFilterOptions>(EMPTY_GUEST_LIST_FILTER_OPTIONS);

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [successMessage, setSuccessMessage] = useState<string>('');
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [expandedGuest, setExpandedGuest] = useState<string | null>(null);

  // Sorting state
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  // Filter state
  const [filters, setFilters] = useState<GuestColumnFilters>({
    name: '',
    email: '',
    phone: '',
    groupId: '',
    role: '',
    rsvpStatus: 'all',
    plusOneStatus: 'all',
    phoneIssue: 'all',
    smsStatus: 'all',
  });
  const [debouncedFilters, setDebouncedFilters] = useState<GuestColumnFilters>({
    name: '',
    email: '',
    phone: '',
    groupId: '',
    role: '',
    rsvpStatus: 'all',
    plusOneStatus: 'all',
    phoneIssue: 'all',
    smsStatus: 'all',
  });

  // Selection state for bulk actions
  const [selectedGuests, setSelectedGuests] = useState<Set<string>>(new Set());
  const [selectAll, setSelectAll] = useState(false);

  // Pagination state
  const pagination = usePagination({ initialItemsPerPage: 50 });
  const {
    currentPage,
    itemsPerPage,
    setPage: setPaginationPage,
    setTotalItems: setPaginationTotalItems,
  } = pagination;

  // Modal states
  const [editingGuest, setEditingGuest] = useState<Guest | null>(null);
  const [addingGuest, setAddingGuest] = useState(false);
  const [bulkActionModal, setBulkActionModal] = useState<'group' | null>(null);

  // Edit form state (includes RSVP)
  const [editForm, setEditForm] = useState({
    name: '',
    email: '',
    phone: '',
    role: 'guest',
    group_id: '',
    plus_one_allowed: false,
    number_of_plus_ones_allowed: 0,
    // RSVP fields
    rsvp_attending: [] as string[],
    rsvp_dietary: '',
  });

  // Add guest form state
  const [addForm, setAddForm] = useState({
    name: '',
    email: '',
    phone: '',
    role: 'guest',
    group_id: '',
    plus_one_allowed: false,
    number_of_plus_ones_allowed: 0,
  });

  // Bulk action state
  const [bulkGroupId, setBulkGroupId] = useState('');

  // QR preview modal state
  const [qrModalGuest, setQrModalGuest] = useState<Guest | null>(null);
  const [qrImageUrl, setQrImageUrl] = useState<string | null>(null);
  const [qrImageLoading, setQrImageLoading] = useState(false);

  // Quick Remind modal state — sends a one-off message to a single guest
  // without leaving the Guests page.
  const [reminderGuest, setReminderGuest] = useState<Guest | null>(null);
  const [reminderChannel, setReminderChannel] = useState<'sms' | 'email' | 'both'>('both');
  const [reminderMessage, setReminderMessage] = useState('');
  const [reminderSending, setReminderSending] = useState(false);

  // Export dropdown state
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);

  // Show/hide the secondary filter row (Role, phone health, SMS prefs).
  // Collapsed by default since most planners only use the primary filters.
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);

  // Guest activity log state
  const [guestActivity, setGuestActivity] = useState<Record<string, any[]>>({});
  const [guestActivityErrors, setGuestActivityErrors] = useState<Record<string, string>>(
    {}
  );
  const [activityLoading, setActivityLoading] = useState<string | null>(null);

  // ==================== DATA FETCHING ====================

  const fetchWeddings = useCallback(async () => {
    if (!token) return;
    try {
      const baseUrl = apiBaseUrl;
      const response = await fetch(`${baseUrl}/admin/planner/weddings`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      const data = await response.json();
      setWeddings(Array.isArray(data) ? data : []);
    } catch {
      setError('Failed to load weddings');
    }
  }, [apiBaseUrl, token]);

  const fetchGuestData = useCallback(async () => {
    if (!selectedWedding) return;

    setLoading(true);
    try {
      const baseUrl = apiBaseUrl;
      const guestParams = new URLSearchParams({
        wedding_id: selectedWedding,
        page: String(currentPage),
        limit: String(itemsPerPage),
        sort_field: sortField,
        sort_direction: sortDirection,
      });

      if (debouncedFilters.name) guestParams.set('name', debouncedFilters.name);
      if (debouncedFilters.email) guestParams.set('email', debouncedFilters.email);
      if (debouncedFilters.phone) guestParams.set('phone', debouncedFilters.phone);
      if (debouncedFilters.groupId) guestParams.set('group_id', debouncedFilters.groupId);
      if (debouncedFilters.role) guestParams.set('role', debouncedFilters.role);
      if (debouncedFilters.rsvpStatus !== 'all') guestParams.set('rsvp_status', debouncedFilters.rsvpStatus);
      if (debouncedFilters.plusOneStatus !== 'all') guestParams.set('plus_one_status', debouncedFilters.plusOneStatus);
      if (debouncedFilters.phoneIssue !== 'all') guestParams.set('phone_issue', debouncedFilters.phoneIssue);
      if (debouncedFilters.smsStatus !== 'all') guestParams.set('sms_status', debouncedFilters.smsStatus);

      // Fetch guests with pagination
      const guestsResponse = await fetch(
        `${baseUrl}/admin/guests?${guestParams.toString()}`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );

      let normalizedGuests: Guest[] = [];
      if (guestsResponse.ok) {
        const guestsData = extractGuestListResponse<Guest>(await guestsResponse.json());
        normalizedGuests = guestsData.guests;
        setGuests(normalizedGuests);
        setPaginationTotalItems(guestsData.total || normalizedGuests.length);
        setSummary(guestsData.summary ?? EMPTY_GUEST_LIST_SUMMARY);
        setFilterOptions(guestsData.filter_options ?? EMPTY_GUEST_LIST_FILTER_OPTIONS);
      } else {
        setGuests([]);
        setPaginationTotalItems(0);
        setSummary(EMPTY_GUEST_LIST_SUMMARY);
        setFilterOptions(EMPTY_GUEST_LIST_FILTER_OPTIONS);
      }

      const guestIds = normalizedGuests
        .map((guest) => guest.id || guest._id)
        .filter((guestId): guestId is string => Boolean(guestId));

      if (guestIds.length === 0) {
        setRsvps([]);
        setPlusOnes([]);
        return;
      }

      const guestIdsQuery = encodeURIComponent(guestIds.join(','));
      const [rsvpsResult, plusOnesResult] = await Promise.allSettled([
        fetch(`${baseUrl}/admin/rsvps?wedding_id=${selectedWedding}&guest_ids=${guestIdsQuery}`, {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
        fetch(`${baseUrl}/admin/plus-one/wedding/${selectedWedding}?guest_ids=${guestIdsQuery}`, {
          headers: { 'Authorization': `Bearer ${token}` },
        }),
      ]);

      if (rsvpsResult.status === 'fulfilled' && rsvpsResult.value.ok) {
        const rsvpsData = await rsvpsResult.value.json();
        setRsvps(Array.isArray(rsvpsData) ? rsvpsData : []);
      } else {
        setRsvps([]);
      }

      if (plusOnesResult.status === 'fulfilled' && plusOnesResult.value.ok) {
        const allPlusOnes = await plusOnesResult.value.json();
        setPlusOnes(Array.isArray(allPlusOnes) ? allPlusOnes : []);
      } else {
        if (plusOnesResult.status === 'fulfilled') {
          console.error('[PlusOnes] Fetch failed:', plusOnesResult.value.status);
        } else {
          console.error('[PlusOnes] Fetch error:', plusOnesResult.reason);
        }
        setPlusOnes([]);
      }

    } catch {
      setError('Failed to load guest data');
      setGuests([]);
      setPaginationTotalItems(0);
      setSummary(EMPTY_GUEST_LIST_SUMMARY);
      setFilterOptions(EMPTY_GUEST_LIST_FILTER_OPTIONS);
    } finally {
      setLoading(false);
    }
  }, [
    apiBaseUrl,
    selectedWedding,
    token,
    currentPage,
    itemsPerPage,
    sortField,
    sortDirection,
    debouncedFilters,
    setPaginationTotalItems,
  ]);

  useEffect(() => {
    fetchWeddings();
  }, [fetchWeddings]);

  useEffect(() => {
    if (didHydrateFiltersFromUrl.current) return;

    const requestedWeddingId = searchParams.get('wedding_id') || '';
    setFilters({
      name: searchParams.get('name') || '',
      email: searchParams.get('email') || '',
      phone: searchParams.get('phone') || '',
      groupId: searchParams.get('group_id') || '',
      role: searchParams.get('role') || '',
      rsvpStatus: (searchParams.get('rsvp_status') as RsvpStatusFilter) || 'all',
      plusOneStatus: (searchParams.get('plus_one_status') as PlusOneStatusFilter) || 'all',
      phoneIssue: (searchParams.get('phone_issue') as PhoneIssueFilter) || 'all',
      smsStatus: (searchParams.get('sms_status') as SmsStatusFilter) || 'all',
    });
    setDebouncedFilters({
      name: searchParams.get('name') || '',
      email: searchParams.get('email') || '',
      phone: searchParams.get('phone') || '',
      groupId: searchParams.get('group_id') || '',
      role: searchParams.get('role') || '',
      rsvpStatus: (searchParams.get('rsvp_status') as RsvpStatusFilter) || 'all',
      plusOneStatus: (searchParams.get('plus_one_status') as PlusOneStatusFilter) || 'all',
      phoneIssue: (searchParams.get('phone_issue') as PhoneIssueFilter) || 'all',
      smsStatus: (searchParams.get('sms_status') as SmsStatusFilter) || 'all',
    });
    if (requestedWeddingId) {
      setSelectedWedding(requestedWeddingId);
    }
    didHydrateFiltersFromUrl.current = true;
  }, [searchParams]);

  useEffect(() => {
    if (!weddings.length) return;
    const hasSelectedWedding = weddings.some((wedding) => (wedding.id || wedding._id) === selectedWedding);
    if (hasSelectedWedding) return;
    const requestedWeddingId = searchParams.get('wedding_id');
    const matchingWedding = requestedWeddingId
      ? weddings.find((wedding) => (wedding.id || wedding._id) === requestedWeddingId)
      : null;
    const nextWeddingId = matchingWedding?.id || matchingWedding?._id || weddings[0].id || weddings[0]._id || '';
    if (nextWeddingId) {
      setSelectedWedding(nextWeddingId);
    }
  }, [searchParams, selectedWedding, weddings]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setDebouncedFilters(filters);
    }, 250);

    return () => window.clearTimeout(timeoutId);
  }, [filters]);

  useEffect(() => {
    if (selectedWedding) {
      fetchGuestData();
    }
  }, [fetchGuestData, selectedWedding]);

  useEffect(() => {
    setSelectedGuests(new Set());
    setSelectAll(false);
  }, [selectedWedding, currentPage, itemsPerPage, debouncedFilters, sortField, sortDirection]);

  // Real-time updates via SSE — refetch guest data when the server
  // signals a change to guests, RSVPs, plus-ones, or invites for
  // the currently selected wedding.
  useSSE({
    resources: ['guest', 'rsvp', 'plus_one', 'invite'],
    weddingId: selectedWedding,
    onDataChange: fetchGuestData,
    enabled: !!selectedWedding,
  });

  // Fetch QR code with authentication when modal opens
  useEffect(() => {
    if (!qrModalGuest || !selectedWedding || !token) {
      setQrImageUrl(null);
      return;
    }

    const fetchQrCode = async () => {
      setQrImageLoading(true);
      try {
        const guestId = qrModalGuest.id || qrModalGuest._id;
        const baseUrl = apiBaseUrl;
        const response = await fetch(
          `${baseUrl}/admin/guests/${guestId}/qr?wedding_id=${selectedWedding}`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          }
        );

        if (!response.ok) {
          throw new Error('Failed to fetch QR code');
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        setQrImageUrl(url);
      } catch (err) {
        console.error('Error fetching QR code:', err);
        setQrImageUrl(null);
      } finally {
        setQrImageLoading(false);
      }
    };

    fetchQrCode();

    // Cleanup blob URL when modal closes
    return () => {
      if (qrImageUrl) {
        URL.revokeObjectURL(qrImageUrl);
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBaseUrl, qrModalGuest, selectedWedding, token]);

  // Fetch guest activity when a guest is expanded
  const fetchGuestActivity = useCallback(async (guestId: string) => {
    const hasCachedActivity = Object.prototype.hasOwnProperty.call(
      guestActivity,
      guestId
    );
    if (!token || !guestId || hasCachedActivity) return;
    setActivityLoading(guestId);
    setGuestActivityErrors(prev => {
      const next = { ...prev };
      delete next[guestId];
      return next;
    });
    try {
      const activities = await loadGuestActivityItems({ apiBaseUrl, token, guestId });
      setGuestActivity(prev => ({ ...prev, [guestId]: activities }));
    } catch (err) {
      console.error('Error fetching guest activity:', err);
      setGuestActivityErrors(prev => ({
        ...prev,
        [guestId]: err instanceof Error ? err.message : 'Failed to load activity',
      }));
    } finally {
      setActivityLoading(null);
    }
  }, [apiBaseUrl, token, guestActivity]);

  // Trigger activity fetch when guest is expanded
  useEffect(() => {
    if (expandedGuest) {
      fetchGuestActivity(expandedGuest);
    }
  }, [expandedGuest, fetchGuestActivity]);

  // ==================== HELPER FUNCTIONS ====================

  const normalizeId = (id: string | undefined) => id?.toString() || '';

  const rsvpByGuestId = useMemo(() => {
    const lookup = new Map<string, RSVP>();
    for (const rsvp of rsvps) {
      lookup.set(normalizeId(rsvp.guest_id), rsvp);
    }
    return lookup;
  }, [rsvps]);

  const plusOnesByGuestId = useMemo(() => {
    const lookup = new Map<string, PlusOne[]>();
    for (const plusOne of plusOnes) {
      const guestId = normalizeId(plusOne.guest_id);
      const existing = lookup.get(guestId);
      if (existing) {
        existing.push(plusOne);
      } else {
        lookup.set(guestId, [plusOne]);
      }
    }
    return lookup;
  }, [plusOnes]);

  const getRSVPForGuest = (guestId: string) => {
    return rsvpByGuestId.get(normalizeId(guestId));
  };

  const getPlusOnesForGuest = useCallback((guestId: string) => {
    return plusOnesByGuestId.get(normalizeId(guestId)) ?? [];
  }, [plusOnesByGuestId]);

  const getGroupLabel = (groupId: string | undefined) => {
    if (!groupId) return '-';
    const preset = PRESET_GROUPS.find(g => g.id === groupId);
    return preset ? preset.label : groupId;
  };

  const showSuccess = (message: string) => {
    setSuccessMessage(message);
    setTimeout(() => setSuccessMessage(''), 3000);
  };

  // Notification status helper
  const getNotificationStatus = (guest: Guest) => {
    const smsStatus = guest.sms_opt_in === true ? 'in' : guest.sms_opt_in === false ? 'out' : 'pending';
    const emailStatus = guest.email_opt_in === true ? 'in' : guest.email_opt_in === false ? 'out' : 'pending';
    return { sms: smsStatus, email: emailStatus, inviteSent: guest.invite_sent };
  };

  // Notification icons component
  const NotificationIcons = ({ guest }: { guest: Guest }) => {
    const status = getNotificationStatus(guest);
    return (
      <div className="flex gap-1 mt-1">
        {/* SMS Status */}
        <span
          title={`SMS: ${status.sms === 'in' ? 'Opted In' : status.sms === 'out' ? 'Opted Out' : 'Not Set'}`}
          className={`inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded ${
            status.sms === 'in' ? 'bg-green-100 text-green-700' :
            status.sms === 'out' ? 'bg-red-100 text-red-700' :
            'bg-gray-100 text-gray-500'
          }`}
        >
          📱{status.sms === 'in' ? '✓' : status.sms === 'out' ? '✗' : '?'}
        </span>
        {/* Email Status */}
        <span
          title={`Email: ${status.email === 'in' ? 'Opted In' : status.email === 'out' ? 'Opted Out' : 'Not Set'}`}
          className={`inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded ${
            status.email === 'in' ? 'bg-green-100 text-green-700' :
            status.email === 'out' ? 'bg-red-100 text-red-700' :
            'bg-gray-100 text-gray-500'
          }`}
        >
          ✉️{status.email === 'in' ? '✓' : status.email === 'out' ? '✗' : '?'}
        </span>
        {/* Invite Sent */}
        {status.inviteSent && (
          <span
            title="Invite Sent"
            className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded bg-blue-100 text-blue-700"
          >
            📨
          </span>
        )}
      </div>
    );
  };

  // ==================== FILTERING & SORTING ====================

  // Reset pagination to page 1 when filters or sorting change
  useEffect(() => {
    setPaginationPage(1);
  }, [filters, sortField, sortDirection, setPaginationPage]);

  const filteredAndSortedGuests = guests;
  const hasActiveFilters = useMemo(
    () =>
      Boolean(
        filters.name ||
          filters.email ||
          filters.phone ||
          filters.groupId ||
          filters.role ||
          filters.rsvpStatus !== 'all' ||
          filters.plusOneStatus !== 'all' ||
          filters.phoneIssue !== 'all' ||
          filters.smsStatus !== 'all'
      ),
    [filters]
  );

  const updateFilter = <K extends keyof GuestColumnFilters>(key: K, value: GuestColumnFilters[K]) => {
    setFilters((current) => ({ ...current, [key]: value }));
  };

  const resetFilters = () => {
    setFilters({
      name: '',
      email: '',
      phone: '',
      groupId: '',
      role: '',
      rsvpStatus: 'all',
      plusOneStatus: 'all',
      phoneIssue: 'all',
      smsStatus: 'all',
    });
  };

  // ==================== SELECTION HANDLERS ====================

  const handleSelectAll = () => {
    if (selectAll) {
      setSelectedGuests(new Set());
    } else {
      const allIds = new Set(filteredAndSortedGuests.map(g => g.id || g._id || ''));
      setSelectedGuests(allIds);
    }
    setSelectAll(!selectAll);
  };

  const handleSelectGuest = (guestId: string) => {
    const newSelected = new Set(selectedGuests);
    if (newSelected.has(guestId)) {
      newSelected.delete(guestId);
    } else {
      newSelected.add(guestId);
    }
    setSelectedGuests(newSelected);
    setSelectAll(newSelected.size === filteredAndSortedGuests.length);
  };

  // ==================== SORT HANDLER ====================

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <span className="text-gray-400 ml-1">↕</span>;
    return <span className="text-wedding-navy ml-1">{sortDirection === 'asc' ? '↑' : '↓'}</span>;
  };

  // ==================== CRUD HANDLERS ====================

  const handleAddGuest = async () => {
    if (!addForm.name.trim()) {
      setError('Name is required');
      return;
    }
    if (!addForm.email && !addForm.phone) {
      setError('Either email or phone is required');
      return;
    }

    try {
      const baseUrl = apiBaseUrl;
      const response = await fetch(`${baseUrl}/admin/guests?wedding_id=${selectedWedding}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: addForm.name,
          email: addForm.email || null,
          phone: addForm.phone || null,
          role: addForm.role,
          group_id: addForm.group_id || null,
          plus_one_allowed: addForm.plus_one_allowed,
          number_of_plus_ones_allowed: addForm.plus_one_allowed ? addForm.number_of_plus_ones_allowed : 0,
        }),
      });

      if (response.ok) {
        setAddingGuest(false);
        setAddForm({
          name: '',
          email: '',
          phone: '',
          role: 'guest',
          group_id: '',
          plus_one_allowed: false,
          number_of_plus_ones_allowed: 0,
        });
        fetchGuestData();
        showSuccess('Guest added successfully!');
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to add guest');
      }
    } catch {
      setError('Failed to add guest');
    }
  };

  const handleEditGuest = (guest: Guest) => {
    const rsvp = getRSVPForGuest(guest.id || guest._id || '');
    setEditingGuest(guest);
    setEditForm({
      name: guest.name,
      email: guest.email || '',
      phone: guest.phone || '',
      role: guest.role,
      group_id: guest.group_id || '',
      plus_one_allowed: guest.plus_one_allowed,
      number_of_plus_ones_allowed: guest.number_of_plus_ones_allowed || 0,
      rsvp_attending: rsvp?.attending || [],
      rsvp_dietary: rsvp?.dietary || '',
    });
  };

  const handleSaveGuest = async () => {
    if (!editingGuest) return;

    const guestId = editingGuest.id || editingGuest._id;

    try {
      const baseUrl = apiBaseUrl;

      // Update guest info
      const guestResponse = await fetch(`${baseUrl}/admin/guests/${guestId}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: editForm.name,
          email: editForm.email || null,
          phone: editForm.phone || null,
          role: editForm.role,
          group_id: editForm.group_id || null,
          plus_one_allowed: editForm.plus_one_allowed,
          number_of_plus_ones_allowed: editForm.plus_one_allowed ? editForm.number_of_plus_ones_allowed : 0,
        }),
      });

      if (!guestResponse.ok) {
        throw new Error('Failed to update guest');
      }

      // Update RSVP if attending events are specified
      if (editForm.rsvp_attending.length > 0 || editForm.rsvp_dietary) {
        const rsvpResponse = await fetch(`${baseUrl}/admin/rsvps/${guestId}`, {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            attending: editForm.rsvp_attending,
            dietary: editForm.rsvp_dietary || null,
            confirmed_by_admin: true,
          }),
        });

        if (!rsvpResponse.ok) {
          console.warn('Failed to update RSVP, but guest was updated');
        }
      }

      setEditingGuest(null);
      fetchGuestData();
      showSuccess('Guest updated successfully!');
    } catch {
      setError('Failed to update guest');
    }
  };

  const handleDeleteGuest = async (guestId: string) => {
    if (!confirm('Are you sure you want to delete this guest? This will also delete their RSVP and plus-ones.')) return;

    try {
      const baseUrl = apiBaseUrl;
      const response = await fetch(`${baseUrl}/admin/guests/${guestId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (response.ok) {
        fetchGuestData();
        showSuccess('Guest deleted successfully!');
      } else {
        setError('Failed to delete guest');
      }
    } catch {
      setError('Failed to delete guest');
    }
  };

  const buildImportRoute = useCallback(() => {
    if (!selectedWedding) {
      return '/admin/import';
    }

    const params = new URLSearchParams({ wedding_id: selectedWedding });
    return `/admin/import?${params.toString()}`;
  }, [selectedWedding]);

  const buildCommunicationsRoute = useCallback(
    (guestTokens: string[], template?: 'rsvp_link') => {
      const params = new URLSearchParams();

      if (selectedWedding) {
        params.set('wedding_id', selectedWedding);
      }

      if (guestTokens.length > 0) {
        params.set(
          'recipients',
          guestTokens.map((guestToken) => `guest:${guestToken}`).join(',')
        );
      }

      params.set('channel', 'both');

      if (template) {
        params.set('template', template);
      }

      const queryString = params.toString();
      return queryString
        ? `/admin/communications/individual?${queryString}`
        : '/admin/communications/individual';
    },
    [selectedWedding]
  );

  const openGuestMessaging = useCallback(
    (guestTokens: string[], template?: 'rsvp_link') => {
      if (guestTokens.length === 0) {
        setError('Select at least one guest to continue to Communications.');
        return;
      }

      router.push(buildCommunicationsRoute(guestTokens, template));
    },
    [buildCommunicationsRoute, router]
  );

  const openReminderModal = (guest: Guest) => {
    const hasPhone = Boolean(guest.phone && guest.phone.trim() !== '');
    const hasEmail = Boolean(guest.email && guest.email.trim() !== '');
    if (!hasPhone && !hasEmail) {
      setError('This guest needs a phone number or email before you can send a reminder.');
      return;
    }

    const defaultChannel: 'sms' | 'email' | 'both' = hasPhone && hasEmail
      ? 'both'
      : hasPhone
        ? 'sms'
        : 'email';

    const wedding = weddings.find((w) => (w.id || w._id) === selectedWedding);
    const origin = typeof window !== 'undefined' ? window.location.origin : '';
    const prefill = wedding?.slug
      ? `Hi ${guest.name}, you're invited to our wedding! Please RSVP at: ${origin}/${wedding.slug}/invite/${guest.token}`
      : `Hi ${guest.name}, just a friendly reminder to RSVP for our wedding.`;

    setReminderChannel(defaultChannel);
    setReminderMessage(prefill);
    setReminderGuest(guest);
  };

  const closeReminderModal = () => {
    setReminderGuest(null);
    setReminderMessage('');
    setReminderSending(false);
  };

  const handleSendReminder = async () => {
    if (!reminderGuest) return;
    const message = reminderMessage.trim();
    if (!message) {
      setError('Please enter a message before sending.');
      return;
    }

    const wedding = weddings.find((w) => (w.id || w._id) === selectedWedding);
    const hasPhone = Boolean(reminderGuest.phone && reminderGuest.phone.trim() !== '');
    const hasEmail = Boolean(reminderGuest.email && reminderGuest.email.trim() !== '');
    const wantsSms = reminderChannel !== 'email' && hasPhone;
    const wantsEmail = reminderChannel !== 'sms' && hasEmail;

    if (!wantsSms && !wantsEmail) {
      setError('This guest cannot be reached on the selected channel.');
      return;
    }

    if (wantsEmail && !wedding?.slug) {
      setError('Email reminders require a wedding to be selected.');
      return;
    }

    // wedding and wedding.slug are both guaranteed to be defined here when
    // wantsEmail is true: the guard above returns early otherwise.
    // Capture in a const so the async task closures below can reference it
    // without optional chaining (TypeScript cannot narrow across async boundaries).
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    const weddingSlug = wedding!.slug!;

    setReminderSending(true);

    // We route both sends through AdminContext.apiRequest rather than raw
    // fetch so the centralized 401/402 handling fires for us — apiRequest
    // returns ``undefined`` after it has already triggered logout (401 or
    // team-member 402) or hard-redirected the planner to billing (402). In
    // that case we MUST bail without surfacing a generic "Failed to send"
    // toast that would race the navigation and confuse the user.
    type SendOutcome =
      | { kind: 'ok' }
      | { kind: 'fail'; reason: string }
      | { kind: 'authHandled' };

    const tasks: Array<Promise<SendOutcome>> = [];

    if (wantsSms) {
      tasks.push(
        (async () => {
          try {
            const result = await apiRequest<{
              sent?: number;
              failed?: number;
              failure_reasons?: string[];
            }>('/admin/reminders/send-to-guests', 'POST', {
              guest_tokens: [reminderGuest.token],
              message,
            });
            if (result === undefined) {
              return { kind: 'authHandled' };
            }
            if ((result.sent ?? 0) > 0) {
              return { kind: 'ok' };
            }
            const reason = Array.isArray(result.failure_reasons) && result.failure_reasons.length > 0
              ? result.failure_reasons[0]
              : 'SMS was not delivered';
            return { kind: 'fail', reason };
          } catch (err) {
            return {
              kind: 'fail',
              reason: err instanceof Error && err.message ? err.message : 'Failed to send SMS',
            };
          }
        })()
      );
    }

    if (wantsEmail) {
      tasks.push(
        (async () => {
          try {
            const body = await apiRequest<{
              sent?: boolean;
              success?: boolean;
              error?: string;
            }>('/admin/email/send-reminder-individual', 'POST', {
              wedding_slug: weddingSlug,
              guest_email: reminderGuest.email,
              guest_name: reminderGuest.name,
              guest_token: reminderGuest.token,
              custom_message: message,
            });
            if (body === undefined) {
              return { kind: 'authHandled' };
            }
            if (body.sent || body.success) {
              return { kind: 'ok' };
            }
            return { kind: 'fail', reason: body.error || 'Email was not delivered' };
          } catch (err) {
            return {
              kind: 'fail',
              reason: err instanceof Error && err.message ? err.message : 'Failed to send email',
            };
          }
        })()
      );
    }

    const results = await Promise.all(tasks);

    // If apiRequest already kicked off a logout or billing redirect for any
    // call, defer to it: clear local state quietly and let navigation take
    // over.
    if (results.some((r) => r.kind === 'authHandled')) {
      closeReminderModal();
      return;
    }

    const okCount = results.filter((r) => r.kind === 'ok').length;
    const failures = results.filter((r): r is { kind: 'fail'; reason: string } => r.kind === 'fail');

    if (okCount > 0 && failures.length === 0) {
      showSuccess(`Reminder sent to ${reminderGuest.name}.`);
      closeReminderModal();
    } else if (okCount > 0) {
      showSuccess(
        `Reminder partially sent to ${reminderGuest.name}. Issues: ${failures.map((f) => f.reason).join('; ')}`
      );
      closeReminderModal();
    } else {
      setError(
        `Failed to send reminder to ${reminderGuest.name}. ${failures.map((f) => f.reason).filter(Boolean).join('; ')}`
      );
      setReminderSending(false);
    }
  };

  // ==================== EXPORT FUNCTIONS ====================

  const handleExportPDF = async () => {
    if (!selectedWedding) return;

    setExportLoading(true);
    setExportMenuOpen(false);
    try {
      const baseUrl = apiBaseUrl;
      const response = await fetch(
        `${baseUrl}/admin/guests/export/pdf?wedding_id=${selectedWedding}`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );

      if (!response.ok) throw new Error('Failed to export PDF');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'guest_list.pdf';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      showSuccess('Guest list PDF downloaded!');
    } catch {
      setError('Failed to export PDF. PDF generation may not be available.');
    } finally {
      setExportLoading(false);
    }
  };

  const handleExportCSV = () => {
    setExportMenuOpen(false);
    // Generate CSV from current guest data
    const headers = ['Name', 'Email', 'Phone', 'Group', 'Role', 'RSVP Status', 'Dietary'];
    const rows = filteredAndSortedGuests.map(guest => {
      const guestId = guest.id || guest._id || '';
      const rsvp = getRSVPForGuest(guestId);
      const status = rsvp ? 'RSVP\'d' : guest.invite_sent ? 'Pending' : 'Not Invited';
      return [
        guest.name,
        guest.email || '',
        guest.phone || '',
        getGroupLabel(guest.group_id),
        guest.role,
        status,
        rsvp?.dietary || ''
      ].map(field => `"${String(field).replace(/"/g, '""')}"`).join(',');
    });

    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'guest_list.csv';
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    showSuccess('Guest list CSV downloaded!');
  };

  const handleExportAllQRZip = async () => {
    if (!selectedWedding) return;

    setExportLoading(true);
    setExportMenuOpen(false);
    try {
      const baseUrl = apiBaseUrl;
      const response = await fetch(`${baseUrl}/admin/guests/export/qr-zip`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          guest_ids: [],  // Empty means all guests
          wedding_id: selectedWedding,
        }),
      });

      if (!response.ok) throw new Error('Failed to export QR codes');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'qr_codes.zip';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      showSuccess('QR codes ZIP downloaded!');
    } catch {
      setError('Failed to export QR codes');
    } finally {
      setExportLoading(false);
    }
  };

  const handleExportSelectedQRZip = async () => {
    if (!selectedWedding || selectedGuests.size === 0) return;

    setExportLoading(true);
    try {
      const baseUrl = apiBaseUrl;
      const response = await fetch(`${baseUrl}/admin/guests/export/qr-zip`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          guest_ids: Array.from(selectedGuests),
          wedding_id: selectedWedding,
        }),
      });

      if (!response.ok) throw new Error('Failed to export QR codes');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'selected_qr_codes.zip';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      showSuccess(`${selectedGuests.size} QR codes downloaded!`);
    } catch {
      setError('Failed to export QR codes');
    } finally {
      setExportLoading(false);
    }
  };

  const downloadSingleQR = async (guest: Guest) => {
    const guestId = guest.id || guest._id || '';
    if (!selectedWedding || !guestId) return;

    try {
      const baseUrl = apiBaseUrl;
      const response = await fetch(
        `${baseUrl}/admin/guests/${guestId}/qr/download?wedding_id=${selectedWedding}`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );

      if (!response.ok) throw new Error('Failed to download QR code');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${guest.name.replace(/\s+/g, '_')}_qr.png`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch {
      setError('Failed to download QR code');
    }
  };

  // ==================== BULK ACTIONS ====================

  const handleBulkAssignGroup = async () => {
    if (!bulkGroupId) {
      setError('Please select a group');
      return;
    }

    try {
      const baseUrl = apiBaseUrl;
      const promises = Array.from(selectedGuests).map(guestId =>
        fetch(`${baseUrl}/admin/guests/${guestId}`, {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ group_id: bulkGroupId }),
        })
      );

      await Promise.all(promises);
      setBulkActionModal(null);
      setBulkGroupId('');
      setSelectedGuests(new Set());
      setSelectAll(false);
      fetchGuestData();
      showSuccess(`${selectedGuests.size} guests assigned to group!`);
    } catch {
      setError('Failed to assign group to some guests');
    }
  };

  const handleBulkSendMessage = () => {
    const selectedGuestTokens = guests
      .filter((guest) => selectedGuests.has(guest.id || guest._id || ''))
      .filter((guest) => guest.phone || guest.email)
      .map((guest) => guest.token);

    if (selectedGuestTokens.length === 0) {
      setError('Select at least one guest with a phone number or email address to message them from Communications.');
      return;
    }

    openGuestMessaging(selectedGuestTokens);
  };

  // ==================== RSVP EVENT TOGGLE ====================

  const toggleRSVPEvent = (event: string) => {
    setEditForm(prev => {
      const attending = prev.rsvp_attending.includes(event)
        ? prev.rsvp_attending.filter(e => e !== event)
        : [...prev.rsvp_attending, event];
      return { ...prev, rsvp_attending: attending };
    });
  };

  // ==================== COMPUTED VALUES ====================

  const selectedWeddingData = weddings.find(w => (w.id || w._id) === selectedWedding);
  const selectedWeddingEventOptions = useMemo(() => {
    if (selectedWeddingData?.events?.length) {
      return getWeddingEventOptions(selectedWeddingData.events);
    }
    return BUILT_IN_WEDDING_EVENT_OPTIONS.map((option) => ({ value: option.value, label: option.label }));
  }, [selectedWeddingData]);
  const getSelectedWeddingEventLabel = useCallback(
    (eventType: string) =>
      getWeddingEventLabel(
        eventType,
        selectedWeddingData?.events?.find((event) => event.type === eventType)?.custom_type_label
      ),
    [selectedWeddingData]
  );
  const availableGroups = filterOptions.groups;
  const availableRoles = filterOptions.roles;

  // Activity icon and color mapping
  const activityStyle: Record<string, { color: string; icon: string }> = {
    rsvp_received: { color: 'bg-green-500', icon: '✓' },
    rsvp_updated: { color: 'bg-blue-500', icon: '↺' },
    guest_added: { color: 'bg-purple-500', icon: '+' },
    guest_updated: { color: 'bg-yellow-500', icon: '✎' },
    guest_deleted: { color: 'bg-red-500', icon: '×' },
    guest_imported: { color: 'bg-indigo-500', icon: '↓' },
    sms_sent: { color: 'bg-teal-500', icon: '✉' },
    email_sent: { color: 'bg-sky-500', icon: '✉' },
    reminder_sent: { color: 'bg-orange-500', icon: '🔔' },
  };

  const renderActivityTimeline = (guestId: string) => {
    const activities = guestActivity[guestId];
    const activityError = guestActivityErrors[guestId];
    const isLoading = activityLoading === guestId;

    return (
      <div>
        <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">Activity</h4>
        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <div className="animate-spin h-4 w-4 border-2 border-gray-300 border-t-gray-600 rounded-full" />
            Loading activity...
          </div>
        ) : activityError && !activities ? (
          <p className="text-sm text-red-600 dark:text-red-400">Failed to load activity</p>
        ) : !activities || activities.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-gray-500 italic">No activity recorded yet</p>
        ) : (
          <div className="relative space-y-0">
            {/* Timeline line */}
            <div className="absolute left-[7px] top-2 bottom-2 w-px bg-gray-200 dark:bg-gray-600" />
            {activities.map((activity: any, idx: number) => {
              const style = activityStyle[activity.type] || { color: 'bg-gray-400', icon: '•' };
              const date = activity.timestamp ? new Date(activity.timestamp) : null;
              return (
                <div key={activity.id || idx} className="relative flex items-start gap-3 pb-3">
                  <div className={`relative z-10 w-4 h-4 rounded-full ${style.color} flex items-center justify-center flex-shrink-0 mt-0.5`}>
                    <span className="text-white text-[8px] font-bold leading-none">{style.icon}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800 dark:text-gray-200 leading-tight">{activity.message}</p>
                    {date && (
                      <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                        {date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                        {' '}
                        {date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  // ==================== RENDER ====================

  return (
    <div className="space-y-6">
        <PageHeader
          title="Guest Management"
          description="View and manage all wedding guests, RSVPs, and plus-ones"
        />

        {/* Success/Error Messages */}
        {successMessage && (
          <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
            <p className="text-green-700 dark:text-green-300">{successMessage}</p>
          </div>
        )}
        {error && (
          <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-red-700 dark:text-red-300">{error}</p>
            <button onClick={() => setError('')} className="text-sm text-red-500 hover:text-red-700 mt-1">Dismiss</button>
          </div>
        )}

        {/* Wedding picker — shared compact pill (see WeddingPicker.tsx) */}
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500 dark:text-gray-400">Wedding:</span>
          <WeddingPicker
            options={weddings.map((w) => ({
              id: (w.id || w._id) as string,
              label: `${w.couple_names} — ${w.date}`,
            }))}
            value={selectedWedding}
            onChange={setSelectedWedding}
            placeholder="Choose a wedding…"
          />
        </div>

        {selectedWedding && (() => {
          return (
          <>
            {/* Stats Overview — compact 9-metric grid. Each tile reads
                label-on-top, number-below at a tighter grain than before;
                related metrics share a color so the eye groups them.
                Plus-one metrics live in their own subgroup at the end. */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2 mb-6">
              {/* Total guest records — the universe everything else slices */}
              <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2">
                <p className="text-xs text-gray-500 dark:text-gray-400">Total records</p>
                <p className="text-xl font-bold text-wedding-navy dark:text-white">{summary.totalGuests}</p>
              </div>
              {/* Invited — anyone marked invite_sent OR who has responded */}
              <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2">
                <p className="text-xs text-gray-500 dark:text-gray-400">Invited</p>
                <p className="text-xl font-bold text-blue-600 dark:text-blue-400">{summary.invitedGuests}</p>
              </div>
              {/* Not invited */}
              <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2">
                <p className="text-xs text-gray-500 dark:text-gray-400">Not invited</p>
                <p className="text-xl font-bold text-gray-500 dark:text-gray-400">{summary.notInvitedGuests}</p>
              </div>
              {/* Responded — total who have an RSVP record (confirmed + declined) */}
              <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2">
                <p className="text-xs text-gray-500 dark:text-gray-400">Responded</p>
                <p className="text-xl font-bold text-emerald-600 dark:text-emerald-400">{summary.respondedGuests}</p>
              </div>
              {/* Pending — invited, no RSVP yet */}
              <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2">
                <p className="text-xs text-gray-500 dark:text-gray-400">Pending response</p>
                <p className="text-xl font-bold text-yellow-600 dark:text-yellow-400">{summary.pendingGuests}</p>
              </div>
              {/* Confirmed — responded with attending events */}
              <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2">
                <p className="text-xs text-gray-500 dark:text-gray-400">Confirmed</p>
                <p className="text-xl font-bold text-green-600 dark:text-green-400">{summary.confirmedGuests}</p>
              </div>
              {/* Declined — responded with attending=[] */}
              <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2">
                <p className="text-xs text-gray-500 dark:text-gray-400">Declined</p>
                <p className="text-xl font-bold text-red-600 dark:text-red-400">{summary.declinedGuests}</p>
              </div>
              {/* Plus-one capacity — sum of `number_of_plus_ones_allowed` */}
              <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2">
                <p className="text-xs text-gray-500 dark:text-gray-400">Plus-one capacity</p>
                <p className="text-xl font-bold text-purple-600 dark:text-purple-400">{summary.totalPlusOneSlots}</p>
              </div>
              {/* Submitted plus-ones — actual plus_one_docs created */}
              <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2">
                <p className="text-xs text-gray-500 dark:text-gray-400">Submitted plus-ones</p>
                <p className="text-xl font-bold text-wedding-sage dark:text-emerald-300">{summary.submittedPlusOnes}</p>
              </div>
            </div>

            {/* Controls */}
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 mb-8">
              <div className="flex flex-col gap-4">
                {/* Top row: Results and Actions */}
                <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200">
                      Showing {guests.length} of {pagination.totalItems} matching guests
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Filters, sorting, and pagination are now applied server-side for the full wedding guest list.
                    </p>
                  </div>

                  {/* Action buttons */}
                  <div className="flex gap-2 flex-wrap justify-end">
                    {hasActiveFilters && (
                      <button
                        onClick={resetFilters}
                        className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
                      >
                        Clear Filters
                      </button>
                    )}
                    <button
                      onClick={() => router.push(buildImportRoute())}
                      className="px-4 py-2 rounded-lg font-medium transition-colors bg-gray-200 text-gray-700 hover:bg-gray-300"
                    >
                      Import CSV
                    </button>
                    <button
                      onClick={() => setAddingGuest(true)}
                      className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium"
                    >
                      + Add Guest
                    </button>
                    <button
                      onClick={() => setViewMode(viewMode === 'table' ? 'cards' : 'table')}
                      className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
                    >
                      {viewMode === 'table' ? 'Card View' : 'Table View'}
                    </button>
                    {/* Export dropdown */}
                    <div className="relative">
                      <button
                        onClick={() => setExportMenuOpen(!exportMenuOpen)}
                        disabled={exportLoading || guests.length === 0}
                        className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                      >
                        {exportLoading ? (
                          <>
                            <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></span>
                            Exporting...
                          </>
                        ) : (
                          <>
                            Export
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </>
                        )}
                      </button>
                      {exportMenuOpen && (
                        <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-slate-700 rounded-lg shadow-lg border border-gray-200 dark:border-slate-600 z-20">
                          <button
                            onClick={handleExportPDF}
                            className="w-full px-4 py-3 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-slate-600 first:rounded-t-lg flex items-center gap-3"
                          >
                            <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                            </svg>
                            Export Guest List (PDF)
                          </button>
                          <button
                            onClick={handleExportCSV}
                            className="w-full px-4 py-3 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-slate-600 flex items-center gap-3"
                          >
                            <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            Export Guest List (CSV)
                          </button>
                          <hr className="border-gray-200 dark:border-slate-600" />
                          <button
                            onClick={handleExportAllQRZip}
                            className="w-full px-4 py-3 text-left text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-slate-600 last:rounded-b-lg flex items-center gap-3"
                          >
                            <svg className="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
                            </svg>
                            Download All QR Codes (ZIP)
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Filters — single inline row (wraps on narrow viewports).
                    Primary filters always visible; rare ones (Role, phone
                    health, SMS prefs) collapsed behind a "More" toggle so
                    the bar stays scannable. */}
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="text"
                    placeholder="Filter name"
                    value={filters.name}
                    onChange={(e) => updateFilter('name', e.target.value)}
                    className="flex-1 min-w-[140px] px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  />
                  <input
                    type="text"
                    placeholder="Filter email"
                    value={filters.email}
                    onChange={(e) => updateFilter('email', e.target.value)}
                    className="flex-1 min-w-[140px] px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  />
                  <input
                    type="text"
                    placeholder="Filter phone"
                    value={filters.phone}
                    onChange={(e) => updateFilter('phone', e.target.value)}
                    className="flex-1 min-w-[120px] px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  />
                  <select
                    value={filters.groupId}
                    onChange={(e) => updateFilter('groupId', e.target.value)}
                    className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  >
                    <option value="">All Groups</option>
                    {PRESET_GROUPS.map((group) => (
                      <option key={group.id} value={group.id}>{group.label}</option>
                    ))}
                    {availableGroups
                      .filter((group) => !PRESET_GROUPS.find((preset) => preset.id === group))
                      .map((group) => (
                        <option key={group} value={group}>{group}</option>
                      ))}
                  </select>
                  <select
                    value={filters.rsvpStatus}
                    onChange={(e) => updateFilter('rsvpStatus', e.target.value as RsvpStatusFilter)}
                    className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  >
                    <option value="all">All RSVP states</option>
                    <option value="responded">RSVP&apos;d</option>
                    <option value="pending">Awaiting RSVP</option>
                    <option value="not_invited">Not invited</option>
                  </select>
                  <select
                    value={filters.plusOneStatus}
                    onChange={(e) => updateFilter('plusOneStatus', e.target.value as PlusOneStatusFilter)}
                    className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  >
                    <option value="all">All plus-one states</option>
                    <option value="submitted">Has plus-ones submitted</option>
                    <option value="allowed">Plus-ones allowed</option>
                    <option value="none">No plus-ones</option>
                  </select>
                  <button
                    type="button"
                    onClick={() => setShowAdvancedFilters((v) => !v)}
                    className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-slate-600 transition-colors flex items-center gap-1"
                    aria-expanded={showAdvancedFilters}
                  >
                    {showAdvancedFilters ? 'Less' : 'More'}
                    <svg className={`w-3 h-3 transition-transform ${showAdvancedFilters ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                </div>

                {/* Advanced filters — collapsed by default. Rare enough that
                    they shouldn't take up real estate until the planner
                    asks. Same compact sizing as the primary row. */}
                {showAdvancedFilters && (
                  <div className="flex flex-wrap items-center gap-2">
                    <select
                      value={filters.role}
                      onChange={(e) => updateFilter('role', e.target.value)}
                      className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                    >
                      <option value="">All Roles</option>
                      {availableRoles.map((role) => (
                        <option key={role} value={role}>{role}</option>
                      ))}
                    </select>
                    <select
                      value={filters.phoneIssue}
                      onChange={(e) => updateFilter('phoneIssue', e.target.value as PhoneIssueFilter)}
                      className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                    >
                      <option value="all">All phone health</option>
                      <option value="invalid_or_unreachable">Invalid or unreachable phone</option>
                      <option value="no_contact">No phone and no email</option>
                    </select>
                    <select
                      value={filters.smsStatus}
                      onChange={(e) => updateFilter('smsStatus', e.target.value as SmsStatusFilter)}
                      className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                    >
                      <option value="all">All SMS preferences</option>
                      <option value="opted_in">SMS opted in</option>
                      <option value="opted_out">SMS opted out</option>
                    </select>
                  </div>
                )}

                {/* Fourth row: Bulk actions (shown when guests selected) */}
                {selectedGuests.size > 0 && (
                  <div className="flex items-center gap-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                    <span className="text-sm font-medium text-blue-700 dark:text-blue-300">
                      {selectedGuests.size} guest{selectedGuests.size > 1 ? 's' : ''} selected
                    </span>
                    <button
                      onClick={() => setBulkActionModal('group')}
                      className="px-3 py-1 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
                    >
                      Assign Group
                    </button>
                    <button
                      onClick={handleBulkSendMessage}
                      className="px-3 py-1 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700"
                    >
                      Message via Communications
                    </button>
                    <button
                      onClick={handleExportSelectedQRZip}
                      disabled={exportLoading}
                      className="px-3 py-1 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-1"
                    >
                      {exportLoading ? (
                        <span className="animate-spin h-3 w-3 border-2 border-white border-t-transparent rounded-full"></span>
                      ) : (
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
                        </svg>
                      )}
                      Download QR Codes
                    </button>
                    <button
                      onClick={() => { setSelectedGuests(new Set()); setSelectAll(false); }}
                      className="px-3 py-1 bg-gray-500 text-white text-sm rounded-lg hover:bg-gray-600"
                    >
                      Clear Selection
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Guest List */}
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg overflow-hidden">
                {loading ? (
                  <div className="flex items-center justify-center py-12">
                    <div className="animate-spin h-8 w-8 border-4 border-wedding-rose border-t-transparent rounded-full"></div>
                    <span className="ml-3 text-gray-600 dark:text-gray-400">Loading guests...</span>
                  </div>
                ) : filteredAndSortedGuests.length === 0 ? (
                  <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                    <p>No guests found.</p>
                    <button
                      onClick={() => setAddingGuest(true)}
                      className="mt-4 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                    >
                      + Add Your First Guest
                    </button>
                  </div>
                ) : viewMode === 'table' ? (
                  /* TABLE VIEW */
                  <div className="space-y-4">
                    <GlassPagination
                      currentPage={pagination.currentPage}
                      totalPages={pagination.totalPages}
                      totalItems={pagination.totalItems}
                      itemsPerPage={pagination.itemsPerPage}
                      onPageChange={pagination.setPage}
                      variant="compact"
                      itemLabel="guests"
                    />
                    <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-gray-50 dark:bg-slate-700">
                        <tr>
                          <th className="px-4 py-3 text-left">
                            <input
                              type="checkbox"
                              checked={selectAll}
                              onChange={handleSelectAll}
                              className="rounded text-wedding-rose focus:ring-wedding-rose"
                            />
                          </th>
                          <th
                            className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-100 dark:hover:bg-slate-600"
                            onClick={() => handleSort('name')}
                          >
                            Name <SortIcon field="name" />
                          </th>
                          <th
                            className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-100 dark:hover:bg-slate-600"
                            onClick={() => handleSort('email')}
                          >
                            Email <SortIcon field="email" />
                          </th>
                          <th
                            className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-100 dark:hover:bg-slate-600"
                            onClick={() => handleSort('phone')}
                          >
                            Phone <SortIcon field="phone" />
                          </th>
                          <th
                            className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-100 dark:hover:bg-slate-600"
                            onClick={() => handleSort('group_id')}
                          >
                            Group <SortIcon field="group_id" />
                          </th>
                          <th
                            className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-100 dark:hover:bg-slate-600"
                            onClick={() => handleSort('rsvp_status')}
                          >
                            RSVP <SortIcon field="rsvp_status" />
                          </th>
                          <th
                            className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-gray-300 cursor-pointer hover:bg-gray-100 dark:hover:bg-slate-600"
                            onClick={() => handleSort('plus_ones')}
                          >
                            Plus Ones <SortIcon field="plus_ones" />
                          </th>
                          <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700 dark:text-gray-300">
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                        {filteredAndSortedGuests.map((guest) => {
                          const guestId = guest.id || guest._id || '';
                          const rsvp = getRSVPForGuest(guestId);
                          const guestPlusOnes = getPlusOnesForGuest(guestId);
                          const isSelected = selectedGuests.has(guestId);
                          const isExpanded = expandedGuest === guestId;

                          return (
                            <React.Fragment key={guestId}>
                              <tr
                                className={`hover:bg-gray-50 dark:hover:bg-slate-700 ${isSelected ? 'bg-blue-50 dark:bg-blue-900/20' : ''} ${isExpanded ? 'bg-blue-50/50 dark:bg-slate-600/30' : ''}`}
                              >
                                <td className="px-4 py-3">
                                  <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={() => handleSelectGuest(guestId)}
                                    className="rounded text-wedding-rose focus:ring-wedding-rose"
                                  />
                                </td>
                                <td className="px-4 py-3">
                                  <div className="font-medium text-gray-900 dark:text-gray-100">{guest.name}</div>
                                  <div className="text-xs text-gray-500">{guest.role}</div>
                                  <NotificationIcons guest={guest} />
                                </td>
                                <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                                  {guest.email || '-'}
                                </td>
                                <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                                  {guest.phone || '-'}
                                </td>
                                <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                                  {getGroupLabel(guest.group_id)}
                                </td>
                                <td className="px-4 py-3">
                                  {rsvp ? (
                                    <span className="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">
                                      {rsvp.confirmed_by_admin ? 'Confirmed' : 'RSVP\'d'}
                                    </span>
                                  ) : guest.invite_sent ? (
                                    <span className="px-2 py-1 text-xs font-semibold rounded-full bg-yellow-100 text-yellow-800">
                                      Pending
                                    </span>
                                  ) : (
                                    <span className="px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                                      Not Invited
                                    </span>
                                  )}
                                </td>
                                <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                                  {guest.plus_one_allowed ? (
                                    <span>{guestPlusOnes.length} / {guest.number_of_plus_ones_allowed}</span>
                                  ) : (
                                    <span className="text-gray-400">N/A</span>
                                  )}
                                </td>
                                <td className="px-4 py-3">
                                  <div className="flex justify-end gap-2">
                                    <button
                                      onClick={() => setExpandedGuest(isExpanded ? null : guestId)}
                                      className={`px-2 py-1 text-xs rounded ${isExpanded ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
                                    >
                                      {isExpanded ? 'Hide' : 'View'}
                                    </button>
                                    <button
                                      onClick={() => handleEditGuest(guest)}
                                      className="px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600"
                                    >
                                      Edit
                                    </button>
                                    <button
                                      onClick={() => setQrModalGuest(guest)}
                                      className="px-2 py-1 text-xs bg-purple-500 text-white rounded hover:bg-purple-600"
                                      title="View QR Code"
                                    >
                                      QR
                                    </button>
                                    {!rsvp && (
                                      <button
                                        onClick={() => openReminderModal(guest)}
                                        className="px-2 py-1 text-xs bg-wedding-sage text-white rounded hover:bg-opacity-90"
                                      >
                                        Remind
                                      </button>
                                    )}
                                    <button
                                      onClick={() => handleDeleteGuest(guestId)}
                                      className="px-2 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600"
                                    >
                                      Delete
                                    </button>
                                  </div>
                                </td>
                              </tr>
                              {/* Inline Expanded Details Row */}
                              {isExpanded && (
                                <tr key={`${guestId}-details`} className="bg-gray-50 dark:bg-slate-700/50">
                                  <td colSpan={8} className="px-6 py-4">
                                    <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
                                      {/* Left: Guest info */}
                                      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                        <div>
                                          <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Guest Details</h4>
                                          <dl className="space-y-1 text-sm">
                                            <div><dt className="inline font-medium text-gray-700 dark:text-gray-300">Token:</dt> <dd className="inline ml-2 font-mono text-xs bg-gray-200 dark:bg-slate-600 px-2 py-1 rounded">{guest.token}</dd></div>
                                            <div><dt className="inline font-medium text-gray-700 dark:text-gray-300">Group:</dt> <dd className="inline ml-2 text-gray-600 dark:text-gray-400">{getGroupLabel(guest.group_id)}</dd></div>
                                            <div><dt className="inline font-medium text-gray-700 dark:text-gray-300">Plus Ones Allowed:</dt> <dd className="inline ml-2 text-gray-600 dark:text-gray-400">{guest.plus_one_allowed ? `Yes (${guest.number_of_plus_ones_allowed})` : 'No'}</dd></div>
                                          </dl>
                                          <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 mt-4">Notification Preferences</h4>
                                          <dl className="space-y-1 text-sm">
                                            <div className="flex items-center gap-2">
                                              <dt className="font-medium text-gray-700 dark:text-gray-300">SMS:</dt>
                                              <dd className={`px-2 py-0.5 text-xs font-medium rounded ${
                                                guest.sms_opt_in === true ? 'bg-green-100 text-green-700' :
                                                guest.sms_opt_in === false ? 'bg-red-100 text-red-700' :
                                                'bg-gray-100 text-gray-500'
                                              }`}>
                                                {guest.sms_opt_in === true ? 'Opted In' : guest.sms_opt_in === false ? 'Opted Out' : 'Not Set'}
                                              </dd>
                                            </div>
                                            <div className="flex items-center gap-2">
                                              <dt className="font-medium text-gray-700 dark:text-gray-300">Email:</dt>
                                              <dd className={`px-2 py-0.5 text-xs font-medium rounded ${
                                                guest.email_opt_in === true ? 'bg-green-100 text-green-700' :
                                                guest.email_opt_in === false ? 'bg-red-100 text-red-700' :
                                                'bg-gray-100 text-gray-500'
                                              }`}>
                                                {guest.email_opt_in === true ? 'Opted In' : guest.email_opt_in === false ? 'Opted Out' : 'Not Set'}
                                              </dd>
                                            </div>
                                            <div className="flex items-center gap-2">
                                              <dt className="font-medium text-gray-700 dark:text-gray-300">Invite Sent:</dt>
                                              <dd className={`px-2 py-0.5 text-xs font-medium rounded ${
                                                guest.invite_sent ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'
                                              }`}>
                                                {guest.invite_sent ? 'Yes' : 'No'}
                                              </dd>
                                            </div>
                                          </dl>
                                        </div>
                                        {rsvp && (
                                          <div>
                                            <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">RSVP Details</h4>
                                            <dl className="space-y-1 text-sm">
                                              <div><dt className="inline font-medium text-gray-700 dark:text-gray-300">Attending:</dt> <dd className="inline ml-2 text-gray-600 dark:text-gray-400">{rsvp.attending.map(getSelectedWeddingEventLabel).join(', ') || 'None'}</dd></div>
                                              <div><dt className="inline font-medium text-gray-700 dark:text-gray-300">Dietary:</dt> <dd className="inline ml-2 text-gray-600 dark:text-gray-400">{rsvp.dietary || 'None'}</dd></div>
                                              {rsvp.confirmed_by_admin && <div className="text-xs text-blue-500">(Confirmed by admin)</div>}
                                            </dl>
                                          </div>
                                        )}
                                        {guestPlusOnes.length > 0 && (
                                          <div>
                                            <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Plus Ones ({guestPlusOnes.length})</h4>
                                            <ul className="space-y-2">
                                              {guestPlusOnes.map((po, idx) => (
                                                <li key={po._id || idx} className="text-sm bg-white dark:bg-slate-600 p-2 rounded shadow-sm">
                                                  <div className="font-medium text-gray-900 dark:text-gray-100">{po.name}</div>
                                                  <div className="text-gray-500 dark:text-gray-400 text-xs">
                                                    {po.phone && <span>Phone: {po.phone} | </span>}
                                                    {po.email && <span>Email: {po.email} | </span>}
                                                    Attending: {po.attending?.join(', ') || 'None'}
                                                    {po.dietary && ` | Dietary: ${po.dietary}`}
                                                  </div>
                                                  <div className="flex gap-2 mt-1">
                                                    {po.sms_opt_in && (
                                                      <span className="inline-flex px-2 py-0.5 text-xs font-medium rounded bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                                                        SMS ✓
                                                      </span>
                                                    )}
                                                    {po.email_opt_in && (
                                                      <span className="inline-flex px-2 py-0.5 text-xs font-medium rounded bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                                                        Email ✓
                                                      </span>
                                                    )}
                                                  </div>
                                                </li>
                                              ))}
                                            </ul>
                                          </div>
                                        )}
                                      </div>
                                      {/* Right: Activity Timeline */}
                                      <div className="border-l border-gray-200 dark:border-gray-600 pl-4">
                                        {renderActivityTimeline(guestId)}
                                      </div>
                                    </div>
                                  </td>
                                </tr>
                              )}
                            </React.Fragment>
                          );
                        })}
                      </tbody>
                    </table>
                    </div>
                    <GlassPagination
                      currentPage={pagination.currentPage}
                      totalPages={pagination.totalPages}
                      totalItems={pagination.totalItems}
                      itemsPerPage={pagination.itemsPerPage}
                      onPageChange={pagination.setPage}
                      onItemsPerPageChange={pagination.setItemsPerPage}
                      itemLabel="guests"
                    />
                  </div>
                ) : (
                  /* CARD VIEW */
                  <div>
                    <div className="divide-y divide-gray-200 dark:divide-gray-700">
                    {filteredAndSortedGuests.map((guest) => {
                      const guestId = guest.id || guest._id || '';
                      const rsvp = getRSVPForGuest(guestId);
                      const guestPlusOnes = getPlusOnesForGuest(guestId);
                      const isExpanded = expandedGuest === guestId;
                      const isSelected = selectedGuests.has(guestId);

                      return (
                        <div key={guestId} className={`hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors ${isSelected ? 'bg-blue-50 dark:bg-blue-900/20' : ''}`}>
                          <div className="p-6">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-4">
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={() => handleSelectGuest(guestId)}
                                  className="rounded text-wedding-rose focus:ring-wedding-rose"
                                />
                                <div className="flex-1">
                                  <div className="flex items-center gap-3">
                                    <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{guest.name}</h3>
                                    <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                                      guest.role === 'planner' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'
                                    }`}>
                                      {guest.role}
                                    </span>
                                    {rsvp && (
                                      <span className="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">
                                        {rsvp.confirmed_by_admin ? 'Confirmed' : 'RSVP\'d'}
                                      </span>
                                    )}
                                  </div>
                                  <div className="flex gap-4 text-sm text-gray-600 dark:text-gray-400 mt-1">
                                    {guest.email && <span>{guest.email}</span>}
                                    {guest.phone && <span>{guest.phone}</span>}
                                    {guest.group_id && <span className="text-wedding-sage">{getGroupLabel(guest.group_id)}</span>}
                                  </div>
                                </div>
                              </div>

                              <div className="flex items-center gap-2">
                                <button
                                  onClick={() => setExpandedGuest(isExpanded ? null : guestId)}
                                  className="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
                                >
                                  {isExpanded ? 'Hide' : 'Details'}
                                </button>
                                <button
                                  onClick={() => handleEditGuest(guest)}
                                  className="px-3 py-1 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600"
                                >
                                  Edit
                                </button>
                                <button
                                  onClick={() => setQrModalGuest(guest)}
                                  className="px-3 py-1 text-sm bg-purple-500 text-white rounded-lg hover:bg-purple-600"
                                  title="View QR Code"
                                >
                                  QR
                                </button>
                                {!rsvp && (
                                  <button
                                    onClick={() => openReminderModal(guest)}
                                    className="px-3 py-1 text-sm bg-wedding-sage text-white rounded-lg hover:bg-opacity-90"
                                  >
                                    Remind
                                  </button>
                                )}
                                <button
                                  onClick={() => handleDeleteGuest(guestId)}
                                  className="px-3 py-1 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600"
                                >
                                  Delete
                                </button>
                              </div>
                            </div>

                            {/* RSVP Quick Info */}
                            {rsvp && (
                              <div className="mt-3 p-3 bg-gray-50 dark:bg-slate-700/50 rounded-lg">
                                <div className="flex gap-6 text-sm">
                                  <div>
                                    <span className="font-medium text-gray-700 dark:text-gray-300">Attending:</span>
                                    <span className="ml-2">{rsvp.attending.map(getSelectedWeddingEventLabel).join(', ') || 'None'}</span>
                                  </div>
                                  {rsvp.dietary && (
                                    <div>
                                      <span className="font-medium text-gray-700 dark:text-gray-300">Dietary:</span>
                                      <span className="ml-2">{rsvp.dietary}</span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}

                            {/* Plus Ones Quick Info */}
                            {guest.plus_one_allowed && (
                              <div className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                                Plus Ones: {guestPlusOnes.length} / {guest.number_of_plus_ones_allowed || 0}
                              </div>
                            )}
                          </div>

                          {/* Expanded Details */}
                          {isExpanded && (
                            <div className="px-6 pb-6">
                              <div className="border-t pt-4 grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
                                {/* Left: Guest info */}
                                <div>
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <div>
                                      <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-2">Guest Information</h4>
                                      <dl className="space-y-1 text-sm">
                                        <div>
                                          <dt className="inline font-medium text-gray-700 dark:text-gray-300">Token:</dt>
                                          <dd className="inline ml-2 font-mono text-xs bg-gray-100 dark:bg-slate-700 px-2 py-1 rounded">
                                            {guest.token}
                                          </dd>
                                        </div>
                                        <div>
                                          <dt className="inline font-medium text-gray-700 dark:text-gray-300">Group:</dt>
                                          <dd className="inline ml-2">{getGroupLabel(guest.group_id)}</dd>
                                        </div>
                                        <div>
                                          <dt className="inline font-medium text-gray-700 dark:text-gray-300">Plus Ones Allowed:</dt>
                                          <dd className="inline ml-2">
                                            {guest.plus_one_allowed ? `Yes (${guest.number_of_plus_ones_allowed || 0})` : 'No'}
                                          </dd>
                                        </div>
                                      </dl>
                                    </div>

                                    {guestPlusOnes.length > 0 && (
                                      <div>
                                        <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-2">Plus Ones</h4>
                                        <ul className="space-y-2">
                                          {guestPlusOnes.map((plusOne, idx) => (
                                            <li key={plusOne._id || idx} className="text-sm bg-gray-50 dark:bg-slate-700 p-2 rounded">
                                              <div className="font-medium">{plusOne.name}</div>
                                              <div className="text-gray-600 dark:text-gray-400">
                                                {plusOne.phone && <span>Phone: {plusOne.phone} | </span>}
                                                {plusOne.email && <span>Email: {plusOne.email} | </span>}
                                                Attending: {plusOne.attending?.map(getSelectedWeddingEventLabel).join(', ') || 'None'}
                                                {plusOne.dietary && ` | Dietary: ${plusOne.dietary}`}
                                              </div>
                                              <div className="flex gap-2 mt-1">
                                                {plusOne.sms_opt_in && (
                                                  <span className="inline-flex px-2 py-0.5 text-xs font-medium rounded bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                                                    SMS ✓
                                                  </span>
                                                )}
                                                {plusOne.email_opt_in && (
                                                  <span className="inline-flex px-2 py-0.5 text-xs font-medium rounded bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
                                                    Email ✓
                                                  </span>
                                                )}
                                              </div>
                                            </li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                  </div>

                                  {selectedWeddingData?.events && (
                                    <div className="mt-4">
                                      <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-2">Wedding Events</h4>
                                      <div className="flex gap-2 flex-wrap">
                                        {selectedWeddingData.events.map((event, idx) => (
                                          <span
                                            key={idx}
                                            className={`px-3 py-1 text-xs rounded-full ${
                                              rsvp?.attending.includes(event.type)
                                                ? 'bg-green-100 text-green-800'
                                                : 'bg-gray-100 text-gray-600'
                                            }`}
                                          >
                                            {getWeddingEventLabel(event.type, event.custom_type_label)} - {event.date}
                                          </span>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                </div>

                                {/* Right: Activity Timeline */}
                                <div className="border-l border-gray-200 dark:border-gray-600 pl-4">
                                  {renderActivityTimeline(guestId)}
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                    </div>
                    <GlassPagination
                      currentPage={pagination.currentPage}
                      totalPages={pagination.totalPages}
                      totalItems={pagination.totalItems}
                      itemsPerPage={pagination.itemsPerPage}
                      onPageChange={pagination.setPage}
                      onItemsPerPageChange={pagination.setItemsPerPage}
                      itemLabel="guests"
                    />
                  </div>
                )}
              </div>
          </>
          );
        })()}

        {/* ==================== MODALS ==================== */}

        {/* Add Guest Modal */}
        {addingGuest && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl max-w-md w-full p-6 max-h-[90vh] overflow-y-auto">
              <h2 className="text-2xl font-bold text-wedding-navy dark:text-white mb-4">Add New Guest</h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name *</label>
                  <input
                    type="text"
                    value={addForm.name}
                    onChange={(e) => setAddForm({ ...addForm, name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    placeholder="Guest name"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
                  <input
                    type="email"
                    value={addForm.email}
                    onChange={(e) => setAddForm({ ...addForm, email: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    placeholder="guest@email.com"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Phone</label>
                  <input
                    type="tel"
                    value={addForm.phone}
                    onChange={(e) => setAddForm({ ...addForm, phone: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    placeholder="1234567890"
                  />
                </div>

                <p className="text-xs text-gray-500 dark:text-gray-400">* Either email or phone is required</p>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Role</label>
                  <select
                    value={addForm.role}
                    onChange={(e) => setAddForm({ ...addForm, role: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  >
                    <option value="guest">Guest</option>
                    <option value="planner">Planner</option>
                    <option value="groom">Groom</option>
                    <option value="bride">Bride</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Group</label>
                  <select
                    value={addForm.group_id}
                    onChange={(e) => setAddForm({ ...addForm, group_id: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  >
                    <option value="">No Group</option>
                    {PRESET_GROUPS.map(group => (
                      <option key={group.id} value={group.id}>{group.label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={addForm.plus_one_allowed}
                      onChange={(e) => setAddForm({ ...addForm, plus_one_allowed: e.target.checked })}
                      className="rounded text-wedding-rose focus:ring-wedding-rose"
                    />
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Allow Plus Ones</span>
                  </label>
                </div>

                {addForm.plus_one_allowed && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Number of Plus Ones Allowed</label>
                    <input
                      type="number"
                      min="0"
                      max="10"
                      value={addForm.number_of_plus_ones_allowed}
                      onChange={(e) => setAddForm({ ...addForm, number_of_plus_ones_allowed: parseInt(e.target.value) || 0 })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    />
                  </div>
                )}
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  onClick={handleAddGuest}
                  className="flex-1 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors"
                >
                  Add Guest
                </button>
                <button
                  onClick={() => setAddingGuest(false)}
                  className="flex-1 bg-gray-200 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-300 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Edit Guest Modal (with RSVP) */}
        {editingGuest && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl max-w-lg w-full p-6 max-h-[90vh] overflow-y-auto">
              <h2 className="text-2xl font-bold text-wedding-navy dark:text-white mb-4">Edit Guest</h2>

              <div className="space-y-4">
                {/* Guest Info Section */}
                <div className="border-b pb-4">
                  <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">Guest Information</h3>

                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name</label>
                      <input
                        type="text"
                        value={editForm.name}
                        onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
                        <input
                          type="email"
                          value={editForm.email}
                          onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Phone</label>
                        <input
                          type="tel"
                          value={editForm.phone}
                          onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Role</label>
                        <select
                          value={editForm.role}
                          onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                        >
                          <option value="guest">Guest</option>
                          <option value="planner">Planner</option>
                          <option value="groom">Groom</option>
                          <option value="bride">Bride</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Group</label>
                        <select
                          value={editForm.group_id}
                          onChange={(e) => setEditForm({ ...editForm, group_id: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                        >
                          <option value="">No Group</option>
                          {PRESET_GROUPS.map(group => (
                            <option key={group.id} value={group.id}>{group.label}</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={editForm.plus_one_allowed}
                          onChange={(e) => setEditForm({ ...editForm, plus_one_allowed: e.target.checked })}
                          className="rounded text-wedding-rose focus:ring-wedding-rose"
                        />
                        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Allow Plus Ones</span>
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
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                        />
                      </div>
                    )}
                  </div>
                </div>

                {/* RSVP Section */}
                <div>
                  <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">
                    RSVP Status
                    <span className="ml-2 text-sm font-normal text-gray-500">(Manual confirmation)</span>
                  </h3>

                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Attending Events</label>
                      <div className="space-y-2">
                        {selectedWeddingEventOptions.map(event => (
                          <label key={event.value} className="flex items-center space-x-2">
                            <input
                              type="checkbox"
                              checked={editForm.rsvp_attending.includes(event.value)}
                              onChange={() => toggleRSVPEvent(event.value)}
                              className="rounded text-wedding-rose focus:ring-wedding-rose"
                            />
                            <span className="text-sm text-gray-700 dark:text-gray-300">{event.label}</span>
                          </label>
                        ))}
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Dietary Restrictions</label>
                      <input
                        type="text"
                        value={editForm.rsvp_dietary}
                        onChange={(e) => setEditForm({ ...editForm, rsvp_dietary: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                        placeholder="e.g., Vegetarian, Gluten-free"
                      />
                    </div>

                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Setting attending events will mark this guest as RSVP&apos;d (confirmed by admin).
                    </p>
                  </div>
                </div>
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
                  className="flex-1 bg-gray-200 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-300 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Bulk Assign Group Modal */}
        {bulkActionModal === 'group' && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl max-w-md w-full p-6">
              <h2 className="text-2xl font-bold text-wedding-navy dark:text-white mb-4">Assign Group to {selectedGuests.size} Guests</h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Select Group</label>
                  <select
                    value={bulkGroupId}
                    onChange={(e) => setBulkGroupId(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  >
                    <option value="">Select a group...</option>
                    {PRESET_GROUPS.map(group => (
                      <option key={group.id} value={group.id}>{group.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  onClick={handleBulkAssignGroup}
                  disabled={!bulkGroupId}
                  className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Assign Group
                </button>
                <button
                  onClick={() => { setBulkActionModal(null); setBulkGroupId(''); }}
                  className="flex-1 bg-gray-200 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-300 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* QR Code Preview Modal */}
        {qrModalGuest && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl max-w-sm w-full p-6 text-center">
              <h2 className="text-xl font-bold text-wedding-navy dark:text-white mb-2">
                {qrModalGuest.name}
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Scan to open RSVP page
              </p>

              {/* QR Code Image */}
              <div className="flex justify-center mb-4">
                <div className="w-48 h-48 border border-gray-200 dark:border-slate-600 rounded-lg bg-white flex items-center justify-center">
                  {qrImageLoading ? (
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
                  ) : qrImageUrl ? (
                    <img
                      src={qrImageUrl}
                      alt={`QR Code for ${qrModalGuest.name}`}
                      className="w-full h-full rounded-lg"
                    />
                  ) : (
                    <div className="text-gray-400 text-sm text-center px-4">
                      <svg className="w-8 h-8 mx-auto mb-2 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      Failed to load QR code
                    </div>
                  )}
                </div>
              </div>

              {/* Guest Info */}
              <div className="text-left mb-4 p-3 bg-gray-50 dark:bg-slate-700 rounded-lg text-sm">
                <p className="text-gray-600 dark:text-gray-300">
                  <span className="font-medium">Token:</span>{' '}
                  <span className="font-mono text-xs">{qrModalGuest.token}</span>
                </p>
                {qrModalGuest.phone && (
                  <p className="text-gray-600 dark:text-gray-300">
                    <span className="font-medium">Phone:</span> {qrModalGuest.phone}
                  </p>
                )}
                {qrModalGuest.email && (
                  <p className="text-gray-600 dark:text-gray-300">
                    <span className="font-medium">Email:</span> {qrModalGuest.email}
                  </p>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex gap-3">
                <button
                  onClick={() => downloadSingleQR(qrModalGuest)}
                  className="flex-1 bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 transition-colors flex items-center justify-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Download PNG
                </button>
                <button
                  onClick={() => setQrModalGuest(null)}
                  className="flex-1 bg-gray-200 dark:bg-slate-600 text-gray-700 dark:text-gray-200 px-4 py-2 rounded-lg hover:bg-gray-300 dark:hover:bg-slate-500 transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Quick Remind Modal */}
        {reminderGuest && (() => {
          const hasPhone = Boolean(reminderGuest.phone && reminderGuest.phone.trim() !== '');
          const hasEmail = Boolean(reminderGuest.email && reminderGuest.email.trim() !== '');
          const channelOptions: Array<{ value: 'sms' | 'email' | 'both'; label: string; disabled: boolean; hint?: string }> = [
            { value: 'sms', label: 'SMS', disabled: !hasPhone, hint: hasPhone ? undefined : 'No phone' },
            { value: 'email', label: 'Email', disabled: !hasEmail, hint: hasEmail ? undefined : 'No email' },
            { value: 'both', label: 'Both', disabled: !(hasPhone && hasEmail), hint: hasPhone && hasEmail ? undefined : 'Needs phone & email' },
          ];

          return (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl max-w-lg w-full p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h2 className="text-xl font-bold text-wedding-navy dark:text-white">
                      Send Reminder
                    </h2>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                      To {reminderGuest.name}
                      {reminderGuest.phone && <span className="ml-2 text-xs">· {reminderGuest.phone}</span>}
                      {reminderGuest.email && <span className="ml-2 text-xs">· {reminderGuest.email}</span>}
                    </p>
                  </div>
                  <button
                    onClick={closeReminderModal}
                    className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                    aria-label="Close"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Channel
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {channelOptions.map((opt) => (
                      <label
                        key={opt.value}
                        className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer text-sm ${
                          reminderChannel === opt.value
                            ? 'border-wedding-rose bg-wedding-rose/10 text-wedding-rose dark:text-wedding-rose-light'
                            : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300'
                        } ${opt.disabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-wedding-rose/5'}`}
                      >
                        <input
                          type="radio"
                          name="reminder-channel"
                          value={opt.value}
                          checked={reminderChannel === opt.value}
                          disabled={opt.disabled}
                          onChange={() => setReminderChannel(opt.value)}
                          className="text-wedding-rose focus:ring-wedding-rose"
                        />
                        <span>{opt.label}</span>
                        {opt.hint && (
                          <span className="text-xs text-gray-400">({opt.hint})</span>
                        )}
                      </label>
                    ))}
                  </div>
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Add to Message
                  </label>
                  <MessageEnrichment
                    onInsert={(text) =>
                      setReminderMessage((prev) => (prev ? `${prev}\n${text}` : text))
                    }
                  />
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Message
                  </label>
                  <textarea
                    value={reminderMessage}
                    onChange={(e) => setReminderMessage(e.target.value)}
                    rows={5}
                    className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent resize-none"
                  />
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={handleSendReminder}
                    disabled={reminderSending || !reminderMessage.trim()}
                    className="flex-1 bg-gradient-to-r from-wedding-navy to-wedding-sage text-white px-4 py-2 rounded-lg font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  >
                    {reminderSending ? 'Sending...' : 'Send Reminder'}
                  </button>
                  <button
                    onClick={closeReminderModal}
                    disabled={reminderSending}
                    className="flex-1 bg-gray-200 dark:bg-slate-600 text-gray-700 dark:text-gray-200 px-4 py-2 rounded-lg hover:bg-gray-300 dark:hover:bg-slate-500 transition-colors disabled:opacity-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          );
        })()}
    </div>
  );
}
