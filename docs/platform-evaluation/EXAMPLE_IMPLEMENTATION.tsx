/**
 * EXAMPLE IMPLEMENTATION: Using the new error handling system
 *
 * This file demonstrates how to implement a modern page using the new
 * error handling hooks. This is a simplified version of the guests page
 * showing the key patterns.
 *
 * This is meant as a reference implementation, not production code.
 * Study this example, then apply the patterns to actual pages.
 */

'use client';

import React, { useState, useCallback } from 'react';
import { useFetch, useCreateMutation, useDeleteMutation } from '@/hooks';
import { useAuth } from '@/contexts/AuthContext';
import { toast } from 'sonner';

// ============================================================================
// TYPES
// ============================================================================

interface Wedding {
  id: string;
  couple_names: string;
  date: string;
  slug: string;
}

interface Guest {
  id?: string;
  _id?: string;
  name: string;
  email?: string;
  phone?: string;
  wedding_id: string;
  role: string;
  plus_one_allowed: boolean;
}

interface CreateGuestInput {
  name: string;
  email?: string;
  phone?: string;
  role: string;
  plus_one_allowed: boolean;
}

// ============================================================================
// COMPONENT
// ============================================================================

export default function AdminGuestsPage() {
  const { isAuthenticated } = useAuth();
  const [selectedWedding, setSelectedWedding] = useState<string>('');

  // ========================================================================
  // DATA FETCHING
  // ========================================================================

  // Load list of weddings on mount
  const {
    data: weddings,
    loading: weddingsLoading,
    error: weddingsError,
  } = useFetch<Wedding[]>(
    '/admin/planner/weddings',
    [],
    { skip: !isAuthenticated }
  );

  // Load guests when a wedding is selected
  const {
    data: guests,
    loading: guestsLoading,
    error: guestsError,
    refetch: refetchGuests,
  } = useFetch<Guest[]>(
    `/admin/guests?wedding_id=${selectedWedding}`,
    [selectedWedding],
    { skip: !selectedWedding }
  );

  // ========================================================================
  // MUTATIONS
  // ========================================================================

  // Create a new guest
  const {
    mutate: createGuest,
    loading: createLoading,
    error: createError,
  } = useCreateMutation('/admin/guests', {
    onSuccess: async () => {
      // Refresh the guests list after successful creation
      await refetchGuests();
      setFormData({ name: '', email: '', phone: '', role: 'guest', plus_one_allowed: false });
    },
  });

  // Delete a guest
  const {
    mutate: deleteGuest,
    loading: deleteLoading,
  } = useDeleteMutation('/admin/guests/{id}', {
    onSuccess: async () => {
      // Refresh the guests list after successful deletion
      await refetchGuests();
    },
  });

  // ========================================================================
  // LOCAL STATE
  // ========================================================================

  const [formData, setFormData] = useState<CreateGuestInput>({
    name: '',
    email: '',
    phone: '',
    role: 'guest',
    plus_one_allowed: false,
  });

  const [showForm, setShowForm] = useState(false);

  // ========================================================================
  // HANDLERS
  // ========================================================================

  const handleWeddingChange = useCallback((weddingId: string) => {
    setSelectedWedding(weddingId);
    // Selection automatically triggers refetch via useFetch dependency
  }, []);

  const handleFormChange = useCallback(
    (field: keyof CreateGuestInput, value: any) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
    },
    []
  );

  const handleCreateGuest = useCallback(async () => {
    // Validate
    if (!formData.name.trim()) {
      toast.error('Guest name is required');
      return;
    }

    if (!selectedWedding) {
      toast.error('Please select a wedding');
      return;
    }

    // Mutate with wedding context
    const { error } = await createGuest({
      ...formData,
      wedding_id: selectedWedding,
    });

    if (!error) {
      toast.success('Guest created successfully');
    }
  }, [formData, selectedWedding, createGuest]);

  const handleDeleteGuest = useCallback(
    async (guestId: string) => {
      if (!window.confirm('Are you sure?')) return;

      const { error } = await deleteGuest(undefined, {
        showErrorToast: true,
      });

      if (!error) {
        toast.success('Guest deleted successfully');
      }
    },
    [deleteGuest]
  );

  // ========================================================================
  // RENDER
  // ========================================================================

  // Guard: User must be authenticated
  if (!isAuthenticated) {
    return <div className="text-center p-8">Please log in</div>;
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto p-4">
      {/* HEADER */}
      <div>
        <h1 className="text-3xl font-bold">Guest Management</h1>
        <p className="text-slate-600">Manage wedding guests and RSVPs</p>
      </div>

      {/* WEDDING SELECTOR */}
      <div className="bg-white rounded-lg shadow p-6">
        <label className="block text-sm font-medium mb-2">Select Wedding</label>

        {weddingsLoading && (
          <div className="text-slate-500">Loading weddings...</div>
        )}

        {weddingsError && (
          <div className="text-red-500 text-sm">{weddingsError}</div>
        )}

        {!weddingsLoading && !weddingsError && (
          <select
            className="w-full border border-slate-300 rounded px-3 py-2"
            value={selectedWedding}
            onChange={(e) => handleWeddingChange(e.target.value)}
          >
            <option value="">-- Select a wedding --</option>
            {(weddings || []).map((wedding) => (
              <option key={wedding.id} value={wedding.id}>
                {wedding.couple_names} - {new Date(wedding.date).toLocaleDateString()}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* EARLY EXIT: No wedding selected */}
      {!selectedWedding && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-6 text-center text-slate-600">
          Select a wedding to view and manage guests
        </div>
      )}

      {/* GUEST LIST SECTION */}
      {selectedWedding && (
        <>
          {/* ADD GUEST FORM */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Add New Guest</h2>
              <button
                onClick={() => setShowForm(!showForm)}
                className="text-blue-600 hover:underline"
              >
                {showForm ? 'Hide Form' : 'Show Form'}
              </button>
            </div>

            {showForm && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleCreateGuest();
                }}
                className="space-y-4"
              >
                {/* Name field */}
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Guest Name *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => handleFormChange('name', e.target.value)}
                    className="w-full border border-slate-300 rounded px-3 py-2"
                    disabled={createLoading}
                  />
                </div>

                {/* Email field */}
                <div>
                  <label className="block text-sm font-medium mb-1">Email</label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => handleFormChange('email', e.target.value)}
                    className="w-full border border-slate-300 rounded px-3 py-2"
                    disabled={createLoading}
                  />
                </div>

                {/* Phone field */}
                <div>
                  <label className="block text-sm font-medium mb-1">Phone</label>
                  <input
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => handleFormChange('phone', e.target.value)}
                    className="w-full border border-slate-300 rounded px-3 py-2"
                    disabled={createLoading}
                  />
                </div>

                {/* Role field */}
                <div>
                  <label className="block text-sm font-medium mb-1">Role</label>
                  <select
                    value={formData.role}
                    onChange={(e) => handleFormChange('role', e.target.value)}
                    className="w-full border border-slate-300 rounded px-3 py-2"
                    disabled={createLoading}
                  >
                    <option value="guest">Guest</option>
                    <option value="family">Family</option>
                    <option value="wedding_party">Wedding Party</option>
                  </select>
                </div>

                {/* Plus one toggle */}
                <div>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formData.plus_one_allowed}
                      onChange={(e) =>
                        handleFormChange('plus_one_allowed', e.target.checked)
                      }
                      disabled={createLoading}
                    />
                    <span className="text-sm font-medium">
                      Allow Plus One
                    </span>
                  </label>
                </div>

                {/* Error message */}
                {createError && (
                  <div className="text-red-500 text-sm">{createError}</div>
                )}

                {/* Submit button */}
                <button
                  type="submit"
                  disabled={createLoading}
                  className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 disabled:bg-slate-400"
                >
                  {createLoading ? 'Creating...' : 'Add Guest'}
                </button>
              </form>
            )}
          </div>

          {/* GUESTS LIST */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">
                Guests ({(guests || []).length})
              </h2>
              <button
                onClick={() => refetchGuests()}
                className="text-blue-600 hover:underline text-sm"
              >
                Refresh
              </button>
            </div>

            {/* Loading state */}
            {guestsLoading && (
              <div className="text-center py-8 text-slate-500">
                Loading guests...
              </div>
            )}

            {/* Error state */}
            {guestsError && (
              <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded">
                {guestsError}
              </div>
            )}

            {/* Empty state */}
            {!guestsLoading && !guestsError && (!guests || guests.length === 0) && (
              <div className="text-center py-8 text-slate-500">
                No guests added yet
              </div>
            )}

            {/* Guest list */}
            {!guestsLoading && !guestsError && guests && guests.length > 0 && (
              <div className="space-y-2">
                {guests.map((guest) => {
                  const guestId = guest.id || guest._id;
                  return (
                    <div
                      key={guestId}
                      className="flex justify-between items-center p-4 border border-slate-200 rounded hover:bg-slate-50"
                    >
                      <div>
                        <p className="font-medium">{guest.name}</p>
                        <p className="text-sm text-slate-500">
                          {guest.email || 'No email'}
                        </p>
                      </div>
                      <button
                        onClick={() => handleDeleteGuest(guestId!)}
                        disabled={deleteLoading}
                        className="text-red-600 hover:underline text-sm disabled:text-slate-400"
                      >
                        {deleteLoading ? 'Deleting...' : 'Delete'}
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ============================================================================
// KEY PATTERNS DEMONSTRATED
// ============================================================================

/**
 * 1. IMPORTING HOOKS
 *    - Import from @/hooks (central export)
 *    - Each hook is specialized for its purpose
 *
 * 2. AUTO-FETCHING DATA
 *    - useFetch automatically fetches on mount
 *    - Dependencies trigger refetch automatically
 *    - skip option to defer fetching
 *
 * 3. ERROR HANDLING
 *    - Errors shown in UI alongside loading state
 *    - Automatic toasts from mutations
 *    - Form submission can validate before mutate
 *
 * 4. REFETCH PATTERN
 *    - refetch() available from useFetch
 *    - onSuccess callback in mutations refetches
 *    - Manual refresh button also available
 *
 * 5. FORM HANDLING
 *    - Form state separate from API state
 *    - Mutations don't duplicate formData
 *    - Loading state disables inputs
 *
 * 6. CONDITIONAL RENDERING
 *    - Show loading skeletons
 *    - Show error messages
 *    - Show empty states
 *    - Show success after mutation
 */

// ============================================================================
// WHAT TO STUDY
// ============================================================================

/**
 * 1. How useFetch works:
 *    - Line 67-76: Weddings load on mount
 *    - Line 79-88: Guests load when wedding selected
 *    - Line 88: skip option prevents early fetch
 *    - Line 88: dependency array triggers refetch
 *
 * 2. How mutations work:
 *    - Line 91-101: Create mutation with onSuccess
 *    - Line 104-110: Delete mutation
 *    - Line 95-96: onSuccess refetches list
 *
 * 3. How errors are shown:
 *    - Line 201: Wedding error display
 *    - Line 278: Guest error display
 *    - Line 254: Form error display
 *    - Toast messages auto-appear
 *
 * 4. How loading is handled:
 *    - Line 197: Wedding loading
 *    - Line 276: Guest loading
 *    - Line 259: Form loading
 *
 * 5. How refetch works:
 *    - Line 96: In onSuccess callback
 *    - Line 293: Manual refresh button
 */
