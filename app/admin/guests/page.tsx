'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useSSE } from '@/hooks/useSSE';
import { BUILT_IN_WEDDING_EVENT_OPTIONS, getWeddingEventLabel, getWeddingEventOptions } from '@/utils/weddingEvents';
import { getApiBaseUrl } from '@/utils/env';
import PageHeader from '../components/PageHeader';
import { usePagination } from '@/admin/hooks/usePagination';
import { GlassPagination } from '@/admin/components/ui/glass/GlassPagination';

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

interface GuestImportResult {
  imported: number;
  tokens: string[];
  warnings?: string[];
}

type SortField = 'name' | 'email' | 'phone' | 'role' | 'group_id' | 'rsvp_status' | 'plus_ones';
type SortDirection = 'asc' | 'desc';
type ViewMode = 'table' | 'cards';

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
  const { token } = useAdmin();
  const apiBaseUrl = getApiBaseUrl();

  // Data state
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [selectedWedding, setSelectedWedding] = useState<string>('');
  const [guests, setGuests] = useState<Guest[]>([]);
  const [rsvps, setRsvps] = useState<RSVP[]>([]);
  const [plusOnes, setPlusOnes] = useState<PlusOne[]>([]);

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [successMessage, setSuccessMessage] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'all' | 'rsvp' | 'pending' | 'not_invited' | 'import'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [expandedGuest, setExpandedGuest] = useState<string | null>(null);

  // Sorting state
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  // Filter state
  const [filterGroup, setFilterGroup] = useState<string>('');
  const [filterRole, setFilterRole] = useState<string>('');

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
  const [bulkActionModal, setBulkActionModal] = useState<'group' | 'form' | null>(null);

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

  // Import state
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState<GuestImportResult | null>(null);
  const [importError, setImportError] = useState<string>('');

  // Bulk action state
  const [bulkGroupId, setBulkGroupId] = useState('');
  const [bulkFormMessage, setBulkFormMessage] = useState('');

  // Reminder modal state
  const [reminderModal, setReminderModal] = useState<{ guest: Guest; weddingSlug: string } | null>(null);
  const [reminderMessage, setReminderMessage] = useState('');
  const [sendingReminder, setSendingReminder] = useState(false);
  const [reminderChannel, setReminderChannel] = useState<'sms' | 'email' | 'both'>('both');

  // QR preview modal state
  const [qrModalGuest, setQrModalGuest] = useState<Guest | null>(null);
  const [qrImageUrl, setQrImageUrl] = useState<string | null>(null);
  const [qrImageLoading, setQrImageLoading] = useState(false);

  // Export dropdown state
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);

  // Guest activity log state
  const [guestActivity, setGuestActivity] = useState<Record<string, any[]>>({});
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

      // Fetch guests with pagination
      const guestsResponse = await fetch(
        `${baseUrl}/admin/guests?wedding_id=${selectedWedding}&page=${currentPage}&limit=${itemsPerPage}`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );

      let normalizedGuests: Guest[] = [];
      if (guestsResponse.ok) {
        const guestsData = await guestsResponse.json();
        const guestData = guestsData.guests || guestsData || [];
        normalizedGuests = Array.isArray(guestData) ? guestData : [];
        setGuests(normalizedGuests);
        setPaginationTotalItems(guestsData.total || normalizedGuests.length);
      } else {
        setGuests([]);
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
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl, selectedWedding, token, currentPage, itemsPerPage, setPaginationTotalItems]);

  useEffect(() => {
    fetchWeddings();
  }, [fetchWeddings]);

  useEffect(() => {
    if (selectedWedding) {
      fetchGuestData();
      // Clear selections when wedding changes
      setSelectedGuests(new Set());
      setSelectAll(false);
    }
  }, [fetchGuestData, selectedWedding]);

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
    if (!token || !guestId || guestActivity[guestId]) return;
    setActivityLoading(guestId);
    try {
      const baseUrl = apiBaseUrl;
      const response = await fetch(`${baseUrl}/admin/guests/${guestId}/activity`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      if (response.ok) {
        const data = await response.json();
        setGuestActivity(prev => ({ ...prev, [guestId]: data.activities || [] }));
      }
    } catch (err) {
      console.error('Error fetching guest activity:', err);
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

  const rsvpGuestIds = useMemo(() => new Set(rsvpByGuestId.keys()), [rsvpByGuestId]);

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

  // Reset pagination to page 1 when filters change
  useEffect(() => {
    setPaginationPage(1);
  }, [searchTerm, activeTab, filterGroup, filterRole, setPaginationPage]);

  const filteredAndSortedGuests = useMemo(() => {
    let result = guests.filter(guest => {
      // Search filter
      const matchesSearch =
        guest.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        guest.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        guest.phone?.includes(searchTerm);

      if (!matchesSearch) return false;

      // Tab filter
      const guestId = normalizeId(guest.id || guest._id);
      const hasRSVP = rsvpGuestIds.has(guestId);

      if (activeTab === 'rsvp' && !hasRSVP) return false;
      if (activeTab === 'pending' && (!guest.invite_sent || hasRSVP)) return false;
      if (activeTab === 'not_invited' && (guest.invite_sent || hasRSVP)) return false;

      // Group filter
      if (filterGroup && guest.group_id !== filterGroup) return false;

      // Role filter
      if (filterRole && guest.role !== filterRole) return false;

      return true;
    });

    // Sorting
    result.sort((a, b) => {
      let aValue: string | number = '';
      let bValue: string | number = '';

      switch (sortField) {
        case 'name':
          aValue = a.name.toLowerCase();
          bValue = b.name.toLowerCase();
          break;
        case 'email':
          aValue = (a.email || '').toLowerCase();
          bValue = (b.email || '').toLowerCase();
          break;
        case 'phone':
          aValue = a.phone || '';
          bValue = b.phone || '';
          break;
        case 'role':
          aValue = a.role;
          bValue = b.role;
          break;
        case 'group_id':
          aValue = getGroupLabel(a.group_id);
          bValue = getGroupLabel(b.group_id);
          break;
        case 'rsvp_status':
          // RSVP status priority: 0 = Not Invited, 1 = Pending (invited), 2 = RSVP'd
          const aHasRSVP = rsvpGuestIds.has(normalizeId(a.id || a._id));
          const bHasRSVP = rsvpGuestIds.has(normalizeId(b.id || b._id));
          aValue = aHasRSVP ? 2 : (a.invite_sent ? 1 : 0);
          bValue = bHasRSVP ? 2 : (b.invite_sent ? 1 : 0);
          break;
        case 'plus_ones':
          aValue = (plusOnesByGuestId.get(normalizeId(a.id || a._id || '')) ?? []).length;
          bValue = (plusOnesByGuestId.get(normalizeId(b.id || b._id || '')) ?? []).length;
          break;
      }

      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    return result;
  }, [guests, searchTerm, activeTab, filterGroup, filterRole, sortField, sortDirection, rsvpGuestIds, plusOnesByGuestId]);

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

  const openReminderModal = (guestId: string) => {
    const guest = guests.find(g => (g.id || g._id) === guestId);
    if (!guest) return;

    // Get the wedding slug for RSVP link
    const wedding = weddings.find(w => (w.id || w._id) === selectedWedding);
    const weddingSlug = wedding?.slug || '';

    // Set default message with personalization
    const defaultMessage = `Hi ${guest.name}, you're invited to our wedding! Please RSVP at: ${window.location.origin}/${weddingSlug}/invite/${guest.token}`;

    setReminderMessage(defaultMessage);
    // Auto-select best channel based on guest contact info
    if (guest.phone && guest.email) setReminderChannel('both');
    else if (guest.phone) setReminderChannel('sms');
    else setReminderChannel('email');
    setReminderModal({ guest, weddingSlug });
  };

  const handleSendReminder = async () => {
    if (!reminderModal || !reminderMessage.trim()) return;

    const guest = reminderModal.guest;
    const hasPhone = !!guest.phone;
    const hasEmail = !!guest.email;
    const sendSms = hasPhone && (reminderChannel === 'sms' || reminderChannel === 'both');
    const sendEmail = hasEmail && (reminderChannel === 'email' || reminderChannel === 'both');

    if (!sendSms && !sendEmail) {
      setError('Cannot send — guest is missing the selected contact method.');
      return;
    }

    setSendingReminder(true);
    try {
      const baseUrl = apiBaseUrl;
      let smsSent = 0;
      let emailSent = 0;
      let smsError = '';
      let emailError = '';

      // Send SMS if selected and guest has phone
      if (sendSms) {
        try {
          const response = await fetch(`${baseUrl}/admin/reminders/send-to-guests`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              guest_tokens: [guest.token],
              message: reminderMessage,
            }),
          });

          if (response.ok) {
            const result = await response.json();
            smsSent = result.sent || 0;
            if (smsSent === 0 && result.failure_reasons?.length > 0) {
              smsError = result.failure_reasons.join('. ');
            }
          } else {
            const errorData = await response.json().catch(() => ({}));
            smsError = errorData.detail || 'SMS send failed';
          }
        } catch {
          smsError = 'SMS send failed';
        }
      }

      // Send email if selected and guest has email
      if (sendEmail) {
        try {
          const wedding = weddings.find(w => (w.id || w._id) === selectedWedding);
          const weddingSlug = wedding?.slug || reminderModal.weddingSlug;

          const response = await fetch(`${baseUrl}/admin/email/send-reminder-individual`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              wedding_slug: weddingSlug,
              guest_email: guest.email,
              guest_name: guest.name,
              guest_token: guest.token,
              custom_message: reminderMessage,
            }),
          });

          if (response.ok) {
            const result = await response.json();
            emailSent = result.sent || (result.success ? 1 : 0);
          } else {
            const errorData = await response.json().catch(() => ({}));
            emailError = errorData.detail || 'Email send failed';
          }
        } catch {
          emailError = 'Email send failed';
        }
      }

      const totalSent = smsSent + emailSent;
      if (totalSent > 0) {
        const channels: string[] = [];
        if (smsSent > 0) channels.push('SMS');
        if (emailSent > 0) channels.push('email');
        showSuccess(`Reminder sent via ${channels.join(' and ')}!`);
        setReminderModal(null);
        setReminderMessage('');
      } else {
        const errors = [smsError, emailError].filter(Boolean);
        setError(errors.length > 0 ? errors.join('. ') : 'Failed to send reminder.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send reminder');
    } finally {
      setSendingReminder(false);
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

  const handleBulkSendForm = async () => {
    if (!bulkFormMessage.trim()) {
      setError('Please enter a message');
      return;
    }

    try {
      const selectedGuestsList = guests.filter(g => selectedGuests.has(g.id || g._id || ''));
      const tokens = selectedGuestsList.map(g => g.token);

      const baseUrl = apiBaseUrl;
      const response = await fetch(`${baseUrl}/admin/reminders/send-to-guests`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          guest_tokens: tokens,
          message: bulkFormMessage,
        }),
      });

      if (response.ok) {
        const result = await response.json();
        setBulkActionModal(null);
        setBulkFormMessage('');
        setSelectedGuests(new Set());
        setSelectAll(false);
        if (result.sent > 0) {
          showSuccess(`Message sent to ${result.sent} guests!${result.failed > 0 ? ` (${result.failed} failed)` : ''}`);
        } else {
          setError('No messages sent. Guests may have opted out or have no phone numbers.');
        }
      } else {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to send message');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message to some guests');
    }
  };

  // ==================== IMPORT HANDLERS ====================

  const handleImportFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile && selectedFile.type === 'text/csv') {
      setImportFile(selectedFile);
      setImportError('');
    } else {
      setImportError('Please select a valid CSV file');
      setImportFile(null);
    }
  };

  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!importFile || !selectedWedding) {
      setImportError('Please select both a CSV file and a wedding');
      return;
    }

    setImportLoading(true);
    setImportError('');
    setImportResult(null);

    try {
      const formData = new FormData();
      formData.append('file', importFile);

      const baseUrl = apiBaseUrl;
      const response = await fetch(
        `${baseUrl}/admin/guests/import?wedding_id=${selectedWedding}`,
        {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
          body: formData,
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Import failed');
      }

      const data = await response.json();
      setImportResult(data);
      setImportFile(null);

      const fileInput = document.getElementById('csvFile') as HTMLInputElement;
      if (fileInput) fileInput.value = '';

      fetchGuestData();
      setTimeout(() => setActiveTab('all'), 1500);

    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setImportLoading(false);
    }
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
  const uniqueGroups = Array.from(new Set(guests.map(g => g.group_id).filter((g): g is string => Boolean(g))));
  const uniqueRoles = Array.from(new Set(guests.map(g => g.role).filter((r): r is string => Boolean(r))));

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
    const isLoading = activityLoading === guestId;

    return (
      <div>
        <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">Activity</h4>
        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <div className="animate-spin h-4 w-4 border-2 border-gray-300 border-t-gray-600 rounded-full" />
            Loading activity...
          </div>
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

        {/* Wedding Selection */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex flex-col sm:flex-row gap-4 items-center">
            <label htmlFor="wedding" className="font-medium text-slate-700 dark:text-gray-200 whitespace-nowrap">
              Select Wedding:
            </label>
            <select
              id="wedding"
              value={selectedWedding}
              onChange={(e) => setSelectedWedding(e.target.value)}
              className="flex-1 px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
            >
              <option value="">Choose a wedding...</option>
              {weddings.map((wedding) => (
                <option key={wedding.id || wedding._id} value={wedding.id || wedding._id}>
                  {wedding.couple_names} - {wedding.date}
                </option>
              ))}
            </select>
          </div>
        </div>

        {selectedWedding && (() => {
          // Calculate stats once for use in both stat cards and tabs
          const guestsWithRsvp = new Set(rsvps.map(r => normalizeId(r.guest_id)));
          const invitedNoRsvpGuests = guests.filter(g => g.invite_sent && !guestsWithRsvp.has(normalizeId(g.id || g._id)));
          const invitedNoRsvp = invitedNoRsvpGuests.length;
          const notInvited = guests.filter(g => !g.invite_sent && !guestsWithRsvp.has(normalizeId(g.id || g._id))).length;

          // Plus-one calculations
          const totalPlusOnesAllowed = guests.reduce((sum, g) => sum + (g.number_of_plus_ones_allowed || 0), 0);
          const confirmedGuests = guests.filter(g => guestsWithRsvp.has(normalizeId(g.id || g._id)) && rsvps.find(r => normalizeId(r.guest_id) === normalizeId(g.id || g._id) && r.attending && r.attending.length > 0));
          const confirmedPlusOnesAllowed = confirmedGuests.reduce((sum, g) => sum + (g.number_of_plus_ones_allowed || 0), 0);
          const pendingPlusOnesAllowed = invitedNoRsvpGuests.reduce((sum, g) => sum + (g.number_of_plus_ones_allowed || 0), 0);

          // Count actual plus-ones submitted by confirmed guests
          const confirmedGuestIds = new Set(confirmedGuests.map(g => normalizeId(g.id || g._id)));
          const confirmedPlusOnesSubmitted = plusOnes.filter(po => confirmedGuestIds.has(normalizeId(po.guest_id))).length;

          return (
          <>
            {/* Stats Overview */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
                  {/* Total Guests */}
                  <div onClick={() => setActiveTab('all')} className={`bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 cursor-pointer transition-all hover:ring-2 hover:ring-wedding-navy/30 ${activeTab === 'all' ? 'ring-2 ring-wedding-navy' : ''}`}>
                    <div className="flex flex-col items-center text-center">
                      <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">Total Guests</h3>
                      <div className="flex items-baseline gap-2 justify-center">
                        <div>
                          <p className="text-3xl font-bold text-wedding-navy">{guests.length}</p>
                          <p className="text-xs text-gray-400">guests</p>
                        </div>
                        {totalPlusOnesAllowed > 0 && (
                          <div className="border-l border-gray-200 dark:border-gray-600 pl-2">
                            <p className="text-lg font-semibold text-purple-600 dark:text-purple-400">+{totalPlusOnesAllowed}</p>
                            <p className="text-xs text-gray-400">plus-ones</p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                  {/* RSVPs Received */}
                  <div onClick={() => setActiveTab('rsvp')} className={`bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 cursor-pointer transition-all hover:ring-2 hover:ring-green-500/30 ${activeTab === 'rsvp' ? 'ring-2 ring-green-500' : ''}`}>
                    <div className="flex flex-col items-center text-center">
                      <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">RSVPs Confirmed</h3>
                      <div className="flex items-baseline gap-2 justify-center">
                        <div>
                          <p className="text-3xl font-bold text-green-600 dark:text-green-300">{confirmedGuests.length}</p>
                          <p className="text-xs text-gray-400">guests</p>
                        </div>
                        {confirmedPlusOnesSubmitted > 0 && (
                          <div className="border-l border-gray-200 dark:border-gray-600 pl-2">
                            <p className="text-lg font-semibold text-green-600 dark:text-green-400">+{confirmedPlusOnesSubmitted}</p>
                            <p className="text-xs text-gray-400">plus-ones</p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                  {/* Awaiting Response */}
                  <div onClick={() => setActiveTab('pending')} className={`bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 cursor-pointer transition-all hover:ring-2 hover:ring-yellow-500/30 ${activeTab === 'pending' ? 'ring-2 ring-yellow-500' : ''}`}>
                    <div className="flex flex-col items-center text-center">
                      <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">Awaiting Response</h3>
                      <div className="flex items-baseline gap-2 justify-center">
                        <div>
                          <p className="text-3xl font-bold text-yellow-600">{invitedNoRsvp}</p>
                          <p className="text-xs text-gray-400">guests</p>
                        </div>
                        {pendingPlusOnesAllowed > 0 && (
                          <div className="border-l border-gray-200 dark:border-gray-600 pl-2">
                            <p className="text-lg font-semibold text-yellow-600 dark:text-yellow-400">+{pendingPlusOnesAllowed}</p>
                            <p className="text-xs text-gray-400">plus-ones</p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                  {/* Not Invited */}
                  <div onClick={() => setActiveTab('not_invited')} className={`bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 cursor-pointer transition-all hover:ring-2 hover:ring-gray-400/30 ${activeTab === 'not_invited' ? 'ring-2 ring-gray-400' : ''}`}>
                    <div className="flex flex-col items-center text-center">
                      <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">Not Invited</h3>
                      <p className="text-3xl font-bold text-gray-500 mt-1">{notInvited}</p>
                    </div>
                  </div>
                  {/* Plus Ones Submitted */}
                  <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6">
                    <div className="flex flex-col items-center text-center">
                      <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">Plus Ones</h3>
                      <p className="text-3xl font-bold text-wedding-sage mt-1">{plusOnes.length}</p>
                    </div>
                  </div>
                </div>

            {/* Controls */}
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 mb-8">
              <div className="flex flex-col gap-4">
                {/* Top row: Tabs and Actions */}
                <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
                  {/* Tabs */}
                  <div className="flex gap-2 flex-wrap">
                    <button
                      onClick={() => setActiveTab('all')}
                      className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                        activeTab === 'all'
                          ? 'bg-wedding-navy text-white'
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                    >
                      All ({guests.length})
                    </button>
                    <button
                      onClick={() => setActiveTab('rsvp')}
                      className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                        activeTab === 'rsvp'
                          ? 'bg-wedding-navy text-white'
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                    >
                      RSVP&apos;d ({rsvps.length})
                    </button>
                    <button
                      onClick={() => setActiveTab('pending')}
                      className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                        activeTab === 'pending'
                          ? 'bg-yellow-500 text-white'
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                    >
                      Pending ({invitedNoRsvp})
                    </button>
                    <button
                      onClick={() => setActiveTab('not_invited')}
                      className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                        activeTab === 'not_invited'
                          ? 'bg-gray-500 text-white'
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                    >
                      Not Invited ({notInvited})
                    </button>
                    <button
                      onClick={() => setActiveTab('import')}
                      className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                        activeTab === 'import'
                          ? 'bg-wedding-sage text-white'
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                    >
                      Import
                    </button>
                  </div>

                  {/* Action buttons */}
                  <div className="flex gap-2">
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

                {/* Second row: Search and Filters */}
                <div className="flex flex-col md:flex-row gap-4">
                  <input
                    type="text"
                    placeholder="Search guests..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                  />
                  <select
                    value={filterGroup}
                    onChange={(e) => setFilterGroup(e.target.value)}
                    className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  >
                    <option value="">All Groups</option>
                    {PRESET_GROUPS.map(group => (
                      <option key={group.id} value={group.id}>{group.label}</option>
                    ))}
                    {uniqueGroups.filter(g => !PRESET_GROUPS.find(p => p.id === g)).map(group => (
                      <option key={group} value={group}>{group}</option>
                    ))}
                  </select>
                  <select
                    value={filterRole}
                    onChange={(e) => setFilterRole(e.target.value)}
                    className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  >
                    <option value="">All Roles</option>
                    {uniqueRoles.map(role => (
                      <option key={role} value={role}>{role}</option>
                    ))}
                  </select>
                </div>

                {/* Third row: Bulk actions (shown when guests selected) */}
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
                      onClick={() => setBulkActionModal('form')}
                      className="px-3 py-1 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700"
                    >
                      Send Message
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

            {/* Import Form */}
            {activeTab === 'import' && (
              <div className="bg-white dark:bg-slate-800/95 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden mb-8">
                <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700">
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white">Import Guests from CSV</h2>
                  <p className="text-slate-600 dark:text-slate-400 mt-1">Upload a CSV file to bulk import guests</p>
                </div>
                <div className="p-6 space-y-6">
                  <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                    <h3 className="text-lg font-semibold text-blue-900 mb-2">CSV Format Requirements</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-blue-800">
                      <div>
                        <strong>Required columns:</strong>
                        <ul className="ml-4 mt-1 list-disc">
                          <li>name (min. 2 characters)</li>
                          <li>phone OR email (at least one)</li>
                        </ul>
                      </div>
                      <div>
                        <strong>Optional columns:</strong>
                        <ul className="ml-4 mt-1 list-disc">
                          <li>role (default: &quot;guest&quot;)</li>
                          <li>plus_one_allowed (true/false)</li>
                          <li>number_of_plus_ones_allowed (number)</li>
                          <li>group_id (for grouping)</li>
                        </ul>
                      </div>
                    </div>
                  </div>

                  <form onSubmit={handleImport} className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        CSV File
                      </label>
                      <input
                        id="csvFile"
                        type="file"
                        accept=".csv"
                        onChange={handleImportFileChange}
                        className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-sage focus:border-transparent file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-wedding-sage file:text-white hover:file:bg-wedding-gold"
                        required
                      />
                      {importFile && (
                        <p className="mt-2 text-sm text-green-600 dark:text-green-300">Selected: {importFile.name}</p>
                      )}
                    </div>

                    {importError && (
                      <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                        <p className="text-red-700 dark:text-red-300">{importError}</p>
                      </div>
                    )}

                    {importResult && (
                      <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                        <p className="text-green-700 dark:text-green-300 font-semibold">
                          Successfully imported {importResult.imported} guests!
                        </p>
                        {importResult.warnings && importResult.warnings.length > 0 && (
                          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-700 dark:bg-amber-900/20">
                            <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                              {importResult.warnings.length} row{importResult.warnings.length === 1 ? '' : 's'} skipped during import.
                            </p>
                            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-700 dark:text-amber-300">
                              {importResult.warnings.map((warning, index) => (
                                <li key={`${warning}-${index}`}>{warning}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}

                    <button
                      type="submit"
                      disabled={importLoading || !importFile}
                      className="w-full py-3 rounded-lg bg-gradient-to-r from-wedding-sage to-wedding-gold text-white font-semibold hover:from-wedding-rose hover:to-wedding-gold focus:outline-none focus:ring-2 focus:ring-wedding-sage disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                    >
                      {importLoading ? 'Importing...' : 'Import Guests'}
                    </button>
                  </form>
                </div>
              </div>
            )}

            {/* Guest List */}
            {activeTab !== 'import' && (
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
                                        onClick={() => openReminderModal(guestId)}
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
                                    onClick={() => openReminderModal(guestId)}
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
                )}
              </div>
            )}
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

        {/* Bulk Send Message Modal */}
        {bulkActionModal === 'form' && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl max-w-md w-full p-6">
              <h2 className="text-2xl font-bold text-wedding-navy dark:text-white mb-4">Send Message to {selectedGuests.size} Guests</h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Message</label>
                  <textarea
                    value={bulkFormMessage}
                    onChange={(e) => setBulkFormMessage(e.target.value)}
                    rows={4}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    placeholder="Enter your message..."
                  />
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  This will send an SMS/email reminder to all selected guests.
                </p>
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  onClick={handleBulkSendForm}
                  disabled={!bulkFormMessage.trim()}
                  className="flex-1 bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Send Message
                </button>
                <button
                  onClick={() => { setBulkActionModal(null); setBulkFormMessage(''); }}
                  className="flex-1 bg-gray-200 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-300 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Send Reminder Modal */}
        {reminderModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl max-w-lg w-full p-6">
              <h2 className="text-2xl font-bold text-wedding-navy dark:text-white mb-4">
                Send Reminder to {reminderModal.guest.name}
              </h2>

              <div className="space-y-4">
                {/* Guest Info */}
                <div className="bg-gray-50 dark:bg-slate-700 rounded-lg p-3">
                  <p className="text-sm text-gray-600 dark:text-gray-300">
                    <span className="font-medium">Phone:</span> {reminderModal.guest.phone || 'No phone number'}
                  </p>
                  {reminderModal.guest.email && (
                    <p className="text-sm text-gray-600 dark:text-gray-300">
                      <span className="font-medium">Email:</span> {reminderModal.guest.email}
                    </p>
                  )}
                </div>

                {/* Message Input */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Message
                  </label>
                  <textarea
                    value={reminderMessage}
                    onChange={(e) => setReminderMessage(e.target.value)}
                    rows={5}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-sage focus:border-transparent"
                    placeholder="Enter your reminder message..."
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {reminderMessage.length} characters
                  </p>
                </div>

                {/* Quick Templates */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Quick Templates
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => setReminderMessage(`Hi ${reminderModal.guest.name}, please RSVP for our wedding! We'd love to have you celebrate with us.`)}
                      className="px-3 py-1 text-xs bg-gray-100 dark:bg-slate-600 text-gray-700 dark:text-gray-200 rounded-full hover:bg-gray-200 dark:hover:bg-slate-500"
                    >
                      RSVP Reminder
                    </button>
                    <button
                      type="button"
                      onClick={() => setReminderMessage(`Hi ${reminderModal.guest.name}, just a friendly reminder about our upcoming wedding. We can't wait to see you there!`)}
                      className="px-3 py-1 text-xs bg-gray-100 dark:bg-slate-600 text-gray-700 dark:text-gray-200 rounded-full hover:bg-gray-200 dark:hover:bg-slate-500"
                    >
                      Event Reminder
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setReminderMessage(`Hi ${reminderModal.guest.name}, you're invited to our wedding! RSVP here: ${window.location.origin}/${reminderModal.weddingSlug}/invite/${reminderModal.guest.token}`);
                      }}
                      className="px-3 py-1 text-xs bg-gray-100 dark:bg-slate-600 text-gray-700 dark:text-gray-200 rounded-full hover:bg-gray-200 dark:hover:bg-slate-500"
                    >
                      With RSVP Link
                    </button>
                  </div>
                </div>

                {/* Channel Picker */}
                {!reminderModal.guest.phone && !reminderModal.guest.email ? (
                  <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                    <p className="text-sm text-red-700 dark:text-red-300">
                      This guest has no phone number or email. Cannot send reminder.
                    </p>
                  </div>
                ) : (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Send via
                    </label>
                    <div className="flex gap-2">
                      {reminderModal.guest.phone && (
                        <button
                          type="button"
                          onClick={() => setReminderChannel('sms')}
                          className={`flex-1 px-3 py-2 text-sm rounded-lg border transition-colors ${
                            reminderChannel === 'sms'
                              ? 'bg-wedding-sage text-white border-wedding-sage'
                              : 'bg-white dark:bg-slate-700 text-gray-700 dark:text-gray-200 border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-slate-600'
                          }`}
                        >
                          SMS
                        </button>
                      )}
                      {reminderModal.guest.email && (
                        <button
                          type="button"
                          onClick={() => setReminderChannel('email')}
                          className={`flex-1 px-3 py-2 text-sm rounded-lg border transition-colors ${
                            reminderChannel === 'email'
                              ? 'bg-wedding-sage text-white border-wedding-sage'
                              : 'bg-white dark:bg-slate-700 text-gray-700 dark:text-gray-200 border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-slate-600'
                          }`}
                        >
                          Email
                        </button>
                      )}
                      {reminderModal.guest.phone && reminderModal.guest.email && (
                        <button
                          type="button"
                          onClick={() => setReminderChannel('both')}
                          className={`flex-1 px-3 py-2 text-sm rounded-lg border transition-colors ${
                            reminderChannel === 'both'
                              ? 'bg-wedding-sage text-white border-wedding-sage'
                              : 'bg-white dark:bg-slate-700 text-gray-700 dark:text-gray-200 border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-slate-600'
                          }`}
                        >
                          Both
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  onClick={handleSendReminder}
                  disabled={sendingReminder || !reminderMessage.trim() || (!reminderModal.guest.phone && !reminderModal.guest.email)}
                  className="flex-1 bg-wedding-sage text-white px-4 py-2 rounded-lg hover:bg-opacity-90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {sendingReminder ? 'Sending...' : `Send via ${reminderChannel === 'both' ? 'SMS & Email' : reminderChannel === 'sms' ? 'SMS' : 'Email'}`}
                </button>
                <button
                  onClick={() => { setReminderModal(null); setReminderMessage(''); }}
                  className="flex-1 bg-gray-200 dark:bg-slate-600 text-gray-700 dark:text-gray-200 px-4 py-2 rounded-lg hover:bg-gray-300 dark:hover:bg-slate-500 transition-colors"
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
    </div>
  );
}
