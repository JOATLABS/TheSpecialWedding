'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useAdmin } from '@/contexts/AdminContext';

// ==================== INTERFACES ====================

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
  dietary?: string;
  attending: string[];
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

const EVENT_OPTIONS = [
  { value: 'traditional', label: 'Traditional Ceremony' },
  { value: 'white_wedding', label: 'White Wedding' },
  { value: 'reception', label: 'Reception' },
];

// ==================== MAIN COMPONENT ====================

export default function AdminGuestsPage() {
  const { token } = useAdmin();

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
  const [activeTab, setActiveTab] = useState<'all' | 'rsvp' | 'pending' | 'import'>('all');
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
  const [importResult, setImportResult] = useState<{ imported: number; tokens: string[] } | null>(null);
  const [importError, setImportError] = useState<string>('');

  // Bulk action state
  const [bulkGroupId, setBulkGroupId] = useState('');
  const [bulkFormMessage, setBulkFormMessage] = useState('');

  // Reminder modal state
  const [reminderModal, setReminderModal] = useState<{ guest: Guest; weddingSlug: string } | null>(null);
  const [reminderMessage, setReminderMessage] = useState('');
  const [sendingReminder, setSendingReminder] = useState(false);

  // ==================== DATA FETCHING ====================

  const fetchWeddings = useCallback(async () => {
    if (!token) return;
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
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
  }, [token]);

  const fetchGuestData = useCallback(async () => {
    if (!selectedWedding) return;

    setLoading(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';

      // Fetch guests
      const guestsResponse = await fetch(
        `${baseUrl}/admin/guests?wedding_id=${selectedWedding}`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );

      let normalizedGuests: Guest[] = [];
      if (guestsResponse.ok) {
        const guestsData = await guestsResponse.json();
        normalizedGuests = Array.isArray(guestsData) ? guestsData : [];
      }
      setGuests(normalizedGuests);

      // Fetch RSVPs
      try {
        const rsvpsResponse = await fetch(
          `${baseUrl}/admin/rsvps?wedding_id=${selectedWedding}`,
          { headers: { 'Authorization': `Bearer ${token}` } }
        );
        if (rsvpsResponse.ok) {
          const rsvpsData = await rsvpsResponse.json();
          setRsvps(Array.isArray(rsvpsData) ? rsvpsData : []);
        } else {
          setRsvps([]);
        }
      } catch {
        setRsvps([]);
      }

      // Fetch plus ones for all guests
      try {
        const plusOnesResponse = await Promise.all(
          normalizedGuests.map(async (guest) => {
            try {
              const response = await fetch(`${baseUrl}/plus_one/plus-ones/${guest.id}`, {
                headers: { 'Authorization': `Bearer ${token}` },
              });
              if (response.ok) {
                const guestPlusOnes = await response.json();
                return guestPlusOnes.map((po: PlusOne) => ({
                  ...po,
                  guest_id: guest.id,
                }));
              }
              return [];
            } catch {
              return [];
            }
          })
        );
        setPlusOnes(plusOnesResponse.flat());
      } catch {
        setPlusOnes([]);
      }

    } catch {
      setError('Failed to load guest data');
    } finally {
      setLoading(false);
    }
  }, [selectedWedding, token]);

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

  // ==================== HELPER FUNCTIONS ====================

  const normalizeId = (id: string | undefined) => id?.toString() || '';

  const getRSVPForGuest = (guestId: string) => {
    const normalizedGuestId = normalizeId(guestId);
    return rsvps.find(r => normalizeId(r.guest_id) === normalizedGuestId);
  };

  const getPlusOnesForGuest = (guestId: string) => {
    const normalizedGuestId = normalizeId(guestId);
    return plusOnes.filter(p => normalizeId(p.guest_id) === normalizedGuestId);
  };

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
      const hasRSVP = rsvps.some(r => normalizeId(r.guest_id) === guestId);

      if (activeTab === 'rsvp' && !hasRSVP) return false;
      if (activeTab === 'pending' && hasRSVP) return false;

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
          const aHasRSVP = rsvps.some(r => normalizeId(r.guest_id) === normalizeId(a.id || a._id));
          const bHasRSVP = rsvps.some(r => normalizeId(r.guest_id) === normalizeId(b.id || b._id));
          aValue = aHasRSVP ? 2 : (a.invite_sent ? 1 : 0);
          bValue = bHasRSVP ? 2 : (b.invite_sent ? 1 : 0);
          break;
        case 'plus_ones':
          aValue = getPlusOnesForGuest(a.id || a._id || '').length;
          bValue = getPlusOnesForGuest(b.id || b._id || '').length;
          break;
      }

      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    return result;
  }, [guests, searchTerm, activeTab, filterGroup, filterRole, sortField, sortDirection, rsvps, plusOnes]);

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
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
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
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';

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
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
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
    const defaultMessage = `Hi ${guest.name}, you're invited to our wedding! Please RSVP at: ${process.env.NEXT_PUBLIC_FRONTEND_URL || ''}/${weddingSlug}/invite/${guest.token}`;

    setReminderMessage(defaultMessage);
    setReminderModal({ guest, weddingSlug });
  };

  const handleSendReminder = async () => {
    if (!reminderModal || !reminderMessage.trim()) return;

    setSendingReminder(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const response = await fetch(`${baseUrl}/admin/reminders/send-to-guests`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          guest_tokens: [reminderModal.guest.token],
          message: reminderMessage,
        }),
      });

      if (response.ok) {
        const result = await response.json();
        if (result.sent > 0) {
          showSuccess('Reminder sent successfully!');
          setReminderModal(null);
          setReminderMessage('');
        } else {
          // Display specific failure reasons from backend
          let errorMsg = 'Failed to send reminder.';
          if (result.failure_reasons && result.failure_reasons.length > 0) {
            errorMsg = result.failure_reasons.join('. ');
          } else if (!reminderModal?.guest.phone) {
            errorMsg = 'Guest has no phone number.';
          }
          setError(errorMsg);
        }
      } else {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to send reminder');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send reminder');
    } finally {
      setSendingReminder(false);
    }
  };

  // ==================== BULK ACTIONS ====================

  const handleBulkAssignGroup = async () => {
    if (!bulkGroupId) {
      setError('Please select a group');
      return;
    }

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
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

      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
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

      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
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
  const uniqueGroups = Array.from(new Set(guests.map(g => g.group_id).filter((g): g is string => Boolean(g))));
  const uniqueRoles = Array.from(new Set(guests.map(g => g.role).filter((r): r is string => Boolean(r))));

  // ==================== RENDER ====================

  return (
    <div className="space-y-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl overflow-hidden mb-8">
          <div className="bg-gradient-to-r from-wedding-navy to-wedding-gold px-8 py-6">
            <h1 className="text-3xl font-bold text-white">Guest Management</h1>
            <p className="text-blue-100 mt-2">View and manage all wedding guests, RSVPs, and plus-ones</p>
          </div>
        </div>

        {/* Success/Error Messages */}
        {successMessage && (
          <div className="mb-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
            <p className="text-green-700 dark:text-green-300">{successMessage}</p>
          </div>
        )}
        {error && (
          <div className="mb-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-red-700 dark:text-red-300">{error}</p>
            <button onClick={() => setError('')} className="text-sm text-red-500 hover:text-red-700 mt-1">Dismiss</button>
          </div>
        )}

        {/* Wedding Selection */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 mb-6">
          <label htmlFor="wedding" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Select Wedding
          </label>
          <select
            id="wedding"
            value={selectedWedding}
            onChange={(e) => setSelectedWedding(e.target.value)}
            className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
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
            {(() => {
              const guestsWithRsvp = new Set(rsvps.map(r => normalizeId(r.guest_id)));
              const invitedNoRsvp = guests.filter(g => g.invite_sent && !guestsWithRsvp.has(normalizeId(g.id || g._id))).length;
              const notInvited = guests.filter(g => !g.invite_sent && !guestsWithRsvp.has(normalizeId(g.id || g._id))).length;
              return (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
                  <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6">
                    <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Guests</h3>
                    <p className="text-3xl font-bold text-wedding-navy mt-2">{guests.length}</p>
                  </div>
                  <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6">
                    <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">RSVPs Received</h3>
                    <p className="text-3xl font-bold text-green-600 dark:text-green-300 mt-2">{rsvps.length}</p>
                  </div>
                  <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6">
                    <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Awaiting Response</h3>
                    <p className="text-3xl font-bold text-yellow-600 mt-2">{invitedNoRsvp}</p>
                  </div>
                  <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6">
                    <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Not Invited</h3>
                    <p className="text-3xl font-bold text-gray-500 mt-2">{notInvited}</p>
                  </div>
                  <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6">
                    <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Plus Ones</h3>
                    <p className="text-3xl font-bold text-wedding-sage mt-2">{plusOnes.length}</p>
                  </div>
                </div>
              );
            })()}

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
                          ? 'bg-wedding-navy text-white'
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                    >
                      Awaiting RSVP ({guests.length - rsvps.length})
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
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg overflow-hidden mb-8">
                <div className="bg-gradient-to-r from-wedding-sage to-wedding-gold px-8 py-6">
                  <h2 className="text-2xl font-bold text-white">Import Guests from CSV</h2>
                  <p className="text-white/80 mt-1">Upload a CSV file to bulk import guests</p>
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
                                            <div><dt className="inline font-medium text-gray-700 dark:text-gray-300">Attending:</dt> <dd className="inline ml-2 text-gray-600 dark:text-gray-400">{rsvp.attending.join(', ') || 'None'}</dd></div>
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
                                                  {po.attending.join(', ')} {po.dietary && `| ${po.dietary}`}
                                                </div>
                                              </li>
                                            ))}
                                          </ul>
                                        </div>
                                      )}
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
                                      guest.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'
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
                                    <span className="ml-2">{rsvp.attending.join(', ') || 'None'}</span>
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
                              <div className="border-t pt-4 grid grid-cols-1 md:grid-cols-2 gap-6">
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
                                            Attending: {plusOne.attending.join(', ')}
                                            {plusOne.dietary && ` | Dietary: ${plusOne.dietary}`}
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
            )}
          </>
        )}

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
                    <option value="admin">Admin</option>
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
                          <option value="admin">Admin</option>
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
                        {EVENT_OPTIONS.map(event => (
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
                    Message (SMS)
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
                        const frontendUrl = process.env.NEXT_PUBLIC_FRONTEND_URL || 'https://thespecialwedding.com';
                        setReminderMessage(`Hi ${reminderModal.guest.name}, you're invited to our wedding! RSVP here: ${frontendUrl}/${reminderModal.weddingSlug}/invite/${reminderModal.guest.token}`);
                      }}
                      className="px-3 py-1 text-xs bg-gray-100 dark:bg-slate-600 text-gray-700 dark:text-gray-200 rounded-full hover:bg-gray-200 dark:hover:bg-slate-500"
                    >
                      With RSVP Link
                    </button>
                  </div>
                </div>

                {!reminderModal.guest.phone && (
                  <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3">
                    <p className="text-sm text-yellow-700 dark:text-yellow-300">
                      This guest has no phone number. SMS cannot be sent.
                    </p>
                  </div>
                )}
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  onClick={handleSendReminder}
                  disabled={sendingReminder || !reminderMessage.trim() || !reminderModal.guest.phone}
                  className="flex-1 bg-wedding-sage text-white px-4 py-2 rounded-lg hover:bg-opacity-90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {sendingReminder ? 'Sending...' : 'Send Reminder'}
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
      </div>
    </div>
  );
}
