'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { X, Link2, Unlink, Plus, Users, AlertTriangle, Check, Loader2 } from 'lucide-react';
import { Guest, SeatingConstraintsResponse } from '@/types/table';

interface SeatingConstraintsModalProps {
  isOpen: boolean;
  onClose: () => void;
  weddingId: string;
  guests: Guest[];
  token: string;
  onConstraintsUpdated: () => void;
}

type ConstraintType = 'must_sit_together' | 'must_sit_apart';

interface NewConstraint {
  guest1Id: string;
  guest2Id: string;
  type: ConstraintType;
}

export function SeatingConstraintsModal({
  isOpen,
  onClose,
  weddingId,
  guests,
  token,
  onConstraintsUpdated
}: SeatingConstraintsModalProps) {
  const [constraints, setConstraints] = useState<SeatingConstraintsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // New constraint form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newConstraint, setNewConstraint] = useState<NewConstraint>({
    guest1Id: '',
    guest2Id: '',
    type: 'must_sit_together'
  });

  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';

  // Fetch existing constraints
  const fetchConstraints = useCallback(async () => {
    if (!weddingId || !token) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${baseUrl}/admin/guests/seating-constraints?wedding_id=${weddingId}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (!response.ok) {
        throw new Error('Failed to fetch seating constraints');
      }

      const data = await response.json();
      setConstraints(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load constraints');
    } finally {
      setLoading(false);
    }
  }, [weddingId, token, baseUrl]);

  useEffect(() => {
    if (isOpen && weddingId) {
      fetchConstraints();
    }
  }, [isOpen, weddingId, fetchConstraints]);

  // Add new constraint
  const handleAddConstraint = async () => {
    if (!newConstraint.guest1Id || !newConstraint.guest2Id) {
      setError('Please select both guests');
      return;
    }

    if (newConstraint.guest1Id === newConstraint.guest2Id) {
      setError('Please select two different guests');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const response = await fetch(
        `${baseUrl}/admin/guests/seating-constraints?wedding_id=${weddingId}`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            constraints: [{
              guest_id_1: newConstraint.guest1Id,
              guest_id_2: newConstraint.guest2Id,
              constraint_type: newConstraint.type,
              action: 'add'
            }]
          })
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to add constraint');
      }

      setSuccess('Constraint added successfully');
      setNewConstraint({ guest1Id: '', guest2Id: '', type: 'must_sit_together' });
      setShowAddForm(false);
      await fetchConstraints();
      onConstraintsUpdated();

      setTimeout(() => setSuccess(null), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add constraint');
    } finally {
      setSaving(false);
    }
  };

  // Remove constraint
  const handleRemoveConstraint = async (
    guest1Id: string,
    guest2Id: string,
    type: ConstraintType
  ) => {
    setSaving(true);
    setError(null);

    try {
      const response = await fetch(
        `${baseUrl}/admin/guests/seating-constraints?wedding_id=${weddingId}`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            constraints: [{
              guest_id_1: guest1Id,
              guest_id_2: guest2Id,
              constraint_type: type,
              action: 'remove'
            }]
          })
        }
      );

      if (!response.ok) {
        throw new Error('Failed to remove constraint');
      }

      setSuccess('Constraint removed');
      await fetchConstraints();
      onConstraintsUpdated();

      setTimeout(() => setSuccess(null), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to remove constraint');
    } finally {
      setSaving(false);
    }
  };

  // Get guest name by ID
  const getGuestName = (guestId: string): string => {
    const guest = guests.find(g => g.id === guestId);
    return guest?.name || 'Unknown Guest';
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl max-w-3xl w-full max-h-[85vh] overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-emerald-600 to-teal-600 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-white" />
            <h2 className="text-lg font-semibold text-white">Seating Constraints</h2>
          </div>
          <button
            onClick={onClose}
            className="text-white/80 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[65vh]">
          {/* Error/Success Messages */}
          {error && (
            <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-2 text-red-700 dark:text-red-400">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span className="text-sm">{error}</span>
              <button onClick={() => setError(null)} className="ml-auto">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {success && (
            <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg flex items-center gap-2 text-green-700 dark:text-green-400">
              <Check className="w-4 h-4 flex-shrink-0" />
              <span className="text-sm">{success}</span>
            </div>
          )}

          {/* Loading State */}
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-emerald-600" />
            </div>
          ) : (
            <>
              {/* Add New Constraint Button */}
              {!showAddForm && (
                <button
                  onClick={() => setShowAddForm(true)}
                  className="mb-6 flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  Add Constraint
                </button>
              )}

              {/* Add Constraint Form */}
              {showAddForm && (
                <div className="mb-6 p-4 bg-gray-50 dark:bg-slate-700/50 rounded-lg border border-gray-200 dark:border-slate-600">
                  <h3 className="font-medium text-gray-900 dark:text-white mb-4">
                    Add New Seating Constraint
                  </h3>

                  <div className="space-y-4">
                    {/* Constraint Type */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Constraint Type
                      </label>
                      <div className="flex gap-4">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="radio"
                            name="constraintType"
                            checked={newConstraint.type === 'must_sit_together'}
                            onChange={() => setNewConstraint(prev => ({ ...prev, type: 'must_sit_together' }))}
                            className="text-emerald-600 focus:ring-emerald-500"
                          />
                          <span className="flex items-center gap-1 text-sm text-gray-700 dark:text-gray-300">
                            <Link2 className="w-4 h-4 text-emerald-600" />
                            Must Sit Together
                          </span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="radio"
                            name="constraintType"
                            checked={newConstraint.type === 'must_sit_apart'}
                            onChange={() => setNewConstraint(prev => ({ ...prev, type: 'must_sit_apart' }))}
                            className="text-red-600 focus:ring-red-500"
                          />
                          <span className="flex items-center gap-1 text-sm text-gray-700 dark:text-gray-300">
                            <Unlink className="w-4 h-4 text-red-600" />
                            Must Sit Apart
                          </span>
                        </label>
                      </div>
                    </div>

                    {/* Guest Selection */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          First Guest
                        </label>
                        <select
                          value={newConstraint.guest1Id}
                          onChange={(e) => setNewConstraint(prev => ({ ...prev, guest1Id: e.target.value }))}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-emerald-500"
                        >
                          <option value="">Select guest...</option>
                          {guests
                            .filter(g => g.id !== newConstraint.guest2Id)
                            .sort((a, b) => a.name.localeCompare(b.name))
                            .map(guest => (
                              <option key={guest.id} value={guest.id}>
                                {guest.name} {guest.role ? `(${guest.role})` : ''}
                              </option>
                            ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Second Guest
                        </label>
                        <select
                          value={newConstraint.guest2Id}
                          onChange={(e) => setNewConstraint(prev => ({ ...prev, guest2Id: e.target.value }))}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-emerald-500"
                        >
                          <option value="">Select guest...</option>
                          {guests
                            .filter(g => g.id !== newConstraint.guest1Id)
                            .sort((a, b) => a.name.localeCompare(b.name))
                            .map(guest => (
                              <option key={guest.id} value={guest.id}>
                                {guest.name} {guest.role ? `(${guest.role})` : ''}
                              </option>
                            ))}
                        </select>
                      </div>
                    </div>

                    {/* Form Actions */}
                    <div className="flex justify-end gap-3 pt-2">
                      <button
                        onClick={() => {
                          setShowAddForm(false);
                          setNewConstraint({ guest1Id: '', guest2Id: '', type: 'must_sit_together' });
                        }}
                        className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleAddConstraint}
                        disabled={saving || !newConstraint.guest1Id || !newConstraint.guest2Id}
                        className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-400 text-white rounded-lg flex items-center gap-2 transition-colors"
                      >
                        {saving ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Plus className="w-4 h-4" />
                        )}
                        Add Constraint
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Existing Constraints */}
              {constraints && (
                <div className="space-y-6">
                  {/* Must Sit Together */}
                  <div>
                    <h3 className="flex items-center gap-2 font-medium text-gray-900 dark:text-white mb-3">
                      <Link2 className="w-4 h-4 text-emerald-600" />
                      Must Sit Together ({constraints.summary.total_must_sit_together})
                    </h3>

                    {constraints.must_sit_together.length === 0 ? (
                      <p className="text-sm text-gray-500 dark:text-gray-400 italic">
                        No &quot;must sit together&quot; constraints defined
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {constraints.must_sit_together.map((constraint, idx) => (
                          <div
                            key={`together-${idx}`}
                            className="flex items-center justify-between p-3 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg"
                          >
                            <div className="flex items-center gap-2 text-sm">
                              <span className="font-medium text-gray-900 dark:text-gray-100">
                                {constraint.guest_1.name}
                              </span>
                              <Link2 className="w-4 h-4 text-emerald-600" />
                              <span className="font-medium text-gray-900 dark:text-gray-100">
                                {constraint.guest_2.name}
                              </span>
                            </div>
                            <button
                              onClick={() => handleRemoveConstraint(
                                constraint.guest_1.id,
                                constraint.guest_2.id,
                                'must_sit_together'
                              )}
                              disabled={saving}
                              className="p-1 text-red-500 hover:text-red-700 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-colors"
                              title="Remove constraint"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Must Sit Apart */}
                  <div>
                    <h3 className="flex items-center gap-2 font-medium text-gray-900 dark:text-white mb-3">
                      <Unlink className="w-4 h-4 text-red-600" />
                      Must Sit Apart ({constraints.summary.total_must_sit_apart})
                    </h3>

                    {constraints.must_sit_apart.length === 0 ? (
                      <p className="text-sm text-gray-500 dark:text-gray-400 italic">
                        No &quot;must sit apart&quot; constraints defined
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {constraints.must_sit_apart.map((constraint, idx) => (
                          <div
                            key={`apart-${idx}`}
                            className="flex items-center justify-between p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg"
                          >
                            <div className="flex items-center gap-2 text-sm">
                              <span className="font-medium text-gray-900 dark:text-gray-100">
                                {constraint.guest_1.name}
                              </span>
                              <Unlink className="w-4 h-4 text-red-600" />
                              <span className="font-medium text-gray-900 dark:text-gray-100">
                                {constraint.guest_2.name}
                              </span>
                            </div>
                            <button
                              onClick={() => handleRemoveConstraint(
                                constraint.guest_1.id,
                                constraint.guest_2.id,
                                'must_sit_apart'
                              )}
                              disabled={saving}
                              className="p-1 text-red-500 hover:text-red-700 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-colors"
                              title="Remove constraint"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Summary */}
                  <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      <strong>{constraints.summary.guests_with_constraints}</strong> guests have seating constraints.
                      These will be considered when using AI Suggest.
                    </p>
                  </div>
                </div>
              )}

              {/* Empty State */}
              {!loading && constraints &&
               constraints.must_sit_together.length === 0 &&
               constraints.must_sit_apart.length === 0 && (
                <div className="text-center py-8">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-100 dark:bg-slate-700 flex items-center justify-center">
                    <Users className="w-8 h-8 text-gray-400" />
                  </div>
                  <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-1">
                    No Constraints Yet
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                    Add constraints to ensure specific guests sit together or apart
                  </p>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 dark:border-gray-700 px-6 py-4 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-200 dark:bg-slate-600 hover:bg-gray-300 dark:hover:bg-slate-500 text-gray-800 dark:text-gray-200 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default SeatingConstraintsModal;
