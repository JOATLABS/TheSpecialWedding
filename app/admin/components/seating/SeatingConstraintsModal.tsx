'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { X, Link2, Unlink, Plus, Users, AlertTriangle, Check, Loader2, ChevronDown, Trash2, Info } from 'lucide-react';
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

  const totalConstraints = constraints
    ? constraints.summary.total_must_sit_together + constraints.summary.total_must_sit_apart
    : 0;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden">

        {/* Header — matches app's purple/indigo modal style */}
        <div className="bg-gradient-to-r from-purple-600 to-indigo-600 px-6 py-5 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-white/20 flex items-center justify-center">
              <Users className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Seating Constraints</h2>
              <p className="text-sm text-white/70">
                Define which guests should sit together or apart
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
          >
            <X className="w-4 h-4 text-white" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">

          {/* Error Message */}
          {error && (
            <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/50 rounded-xl flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-medium text-red-700 dark:text-red-400">{error}</p>
              </div>
              <button
                onClick={() => setError(null)}
                className="text-red-400 hover:text-red-600 dark:hover:text-red-300"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Success Message */}
          {success && (
            <div className="p-4 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800/50 rounded-xl flex items-center gap-3">
              <div className="w-6 h-6 rounded-full bg-emerald-100 dark:bg-emerald-800/50 flex items-center justify-center">
                <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
              </div>
              <p className="text-sm font-medium text-emerald-700 dark:text-emerald-400">{success}</p>
            </div>
          )}

          {/* Loading State */}
          {loading ? (
            <div className="flex flex-col items-center justify-center py-16 gap-3">
              <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
              <p className="text-sm text-gray-500 dark:text-gray-400">Loading constraints...</p>
            </div>
          ) : (
            <>
              {/* Add Constraint Section */}
              {!showAddForm ? (
                <button
                  onClick={() => setShowAddForm(true)}
                  className="w-full flex items-center justify-center gap-2 px-5 py-3.5 border-2 border-dashed border-purple-300 dark:border-purple-700/50 text-purple-600 dark:text-purple-400 rounded-xl hover:bg-purple-50 dark:hover:bg-purple-900/10 hover:border-purple-400 dark:hover:border-purple-600/50 transition-all font-medium text-sm"
                >
                  <Plus className="w-4 h-4" />
                  Add New Constraint
                </button>
              ) : (
                <div className="rounded-xl border border-gray-200 dark:border-slate-700 overflow-hidden">
                  {/* Form Header */}
                  <div className="px-5 py-4 bg-gray-50 dark:bg-slate-700/50 border-b border-gray-200 dark:border-slate-700">
                    <h3 className="font-semibold text-gray-900 dark:text-white text-sm">
                      New Seating Constraint
                    </h3>
                  </div>

                  <div className="p-5 space-y-5">
                    {/* Constraint Type Toggle */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                        Constraint Type
                      </label>
                      <div className="grid grid-cols-2 gap-3">
                        <button
                          type="button"
                          onClick={() => setNewConstraint(prev => ({ ...prev, type: 'must_sit_together' }))}
                          className={`flex items-center gap-3 px-4 py-3.5 rounded-xl border-2 transition-all text-left ${
                            newConstraint.type === 'must_sit_together'
                              ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20 dark:border-indigo-500/70'
                              : 'border-gray-200 dark:border-slate-600 hover:border-gray-300 dark:hover:border-slate-500'
                          }`}
                        >
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                            newConstraint.type === 'must_sit_together'
                              ? 'bg-indigo-100 dark:bg-indigo-800/50'
                              : 'bg-gray-100 dark:bg-slate-700'
                          }`}>
                            <Link2 className={`w-4 h-4 ${
                              newConstraint.type === 'must_sit_together'
                                ? 'text-indigo-600 dark:text-indigo-400'
                                : 'text-gray-400'
                            }`} />
                          </div>
                          <div>
                            <p className={`text-sm font-medium ${
                              newConstraint.type === 'must_sit_together'
                                ? 'text-indigo-700 dark:text-indigo-300'
                                : 'text-gray-700 dark:text-gray-300'
                            }`}>
                              Sit Together
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                              Same table
                            </p>
                          </div>
                        </button>

                        <button
                          type="button"
                          onClick={() => setNewConstraint(prev => ({ ...prev, type: 'must_sit_apart' }))}
                          className={`flex items-center gap-3 px-4 py-3.5 rounded-xl border-2 transition-all text-left ${
                            newConstraint.type === 'must_sit_apart'
                              ? 'border-rose-500 bg-rose-50 dark:bg-rose-900/20 dark:border-rose-500/70'
                              : 'border-gray-200 dark:border-slate-600 hover:border-gray-300 dark:hover:border-slate-500'
                          }`}
                        >
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                            newConstraint.type === 'must_sit_apart'
                              ? 'bg-rose-100 dark:bg-rose-800/50'
                              : 'bg-gray-100 dark:bg-slate-700'
                          }`}>
                            <Unlink className={`w-4 h-4 ${
                              newConstraint.type === 'must_sit_apart'
                                ? 'text-rose-600 dark:text-rose-400'
                                : 'text-gray-400'
                            }`} />
                          </div>
                          <div>
                            <p className={`text-sm font-medium ${
                              newConstraint.type === 'must_sit_apart'
                                ? 'text-rose-700 dark:text-rose-300'
                                : 'text-gray-700 dark:text-gray-300'
                            }`}>
                              Keep Apart
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                              Different tables
                            </p>
                          </div>
                        </button>
                      </div>
                    </div>

                    {/* Guest Selection */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                          First Guest
                        </label>
                        <div className="relative">
                          <select
                            value={newConstraint.guest1Id}
                            onChange={(e) => setNewConstraint(prev => ({ ...prev, guest1Id: e.target.value }))}
                            className="w-full px-4 py-3 border border-gray-200 dark:border-slate-600 rounded-xl bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 text-sm focus:ring-2 focus:ring-purple-500/30 focus:border-purple-500 dark:focus:border-purple-400 transition-all appearance-none pr-10"
                          >
                            <option value="">Select a guest...</option>
                            {guests
                              .filter(g => g.id !== newConstraint.guest2Id)
                              .sort((a, b) => a.name.localeCompare(b.name))
                              .map(guest => (
                                <option key={guest.id} value={guest.id}>
                                  {guest.name} {guest.role ? `(${guest.role})` : ''}
                                </option>
                              ))}
                          </select>
                          <ChevronDown className="w-4 h-4 text-gray-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                        </div>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                          Second Guest
                        </label>
                        <div className="relative">
                          <select
                            value={newConstraint.guest2Id}
                            onChange={(e) => setNewConstraint(prev => ({ ...prev, guest2Id: e.target.value }))}
                            className="w-full px-4 py-3 border border-gray-200 dark:border-slate-600 rounded-xl bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 text-sm focus:ring-2 focus:ring-purple-500/30 focus:border-purple-500 dark:focus:border-purple-400 transition-all appearance-none pr-10"
                          >
                            <option value="">Select a guest...</option>
                            {guests
                              .filter(g => g.id !== newConstraint.guest1Id)
                              .sort((a, b) => a.name.localeCompare(b.name))
                              .map(guest => (
                                <option key={guest.id} value={guest.id}>
                                  {guest.name} {guest.role ? `(${guest.role})` : ''}
                                </option>
                              ))}
                          </select>
                          <ChevronDown className="w-4 h-4 text-gray-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                        </div>
                      </div>
                    </div>

                    {/* Form Actions */}
                    <div className="flex justify-end gap-3 pt-1">
                      <button
                        onClick={() => {
                          setShowAddForm(false);
                          setNewConstraint({ guest1Id: '', guest2Id: '', type: 'must_sit_together' });
                        }}
                        className="px-5 py-2.5 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 rounded-xl hover:bg-gray-100 dark:hover:bg-slate-700 transition-all"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleAddConstraint}
                        disabled={saving || !newConstraint.guest1Id || !newConstraint.guest2Id}
                        className="px-5 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 disabled:from-gray-400 disabled:to-gray-400 text-white rounded-xl text-sm font-medium flex items-center gap-2 hover:opacity-90 disabled:opacity-50 transition-all"
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

                  {/* Must Sit Together Section */}
                  <div>
                    <div className="flex items-center gap-2 mb-4">
                      <div className="w-7 h-7 rounded-lg bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
                        <Link2 className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                      </div>
                      <h3 className="font-semibold text-gray-900 dark:text-white text-sm">
                        Must Sit Together
                      </h3>
                      <span className="ml-auto text-xs font-medium text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-slate-700 px-2.5 py-1 rounded-full">
                        {constraints.summary.total_must_sit_together}
                      </span>
                    </div>

                    {constraints.must_sit_together.length === 0 ? (
                      <p className="text-sm text-gray-400 dark:text-gray-500 italic pl-9">
                        No &quot;must sit together&quot; constraints yet
                      </p>
                    ) : (
                      <div className="space-y-2 pl-9">
                        {constraints.must_sit_together.map((constraint, idx) => (
                          <div
                            key={`together-${idx}`}
                            className="group flex items-center justify-between px-4 py-3.5 bg-indigo-50/70 dark:bg-indigo-900/10 border border-indigo-100 dark:border-indigo-800/30 rounded-xl transition-all hover:shadow-sm"
                          >
                            <div className="flex items-center gap-3 text-sm">
                              <span className="font-medium text-gray-800 dark:text-gray-200">
                                {constraint.guest_1.name}
                              </span>
                              <div className="w-6 h-6 rounded-md bg-indigo-100 dark:bg-indigo-800/40 flex items-center justify-center">
                                <Link2 className="w-3 h-3 text-indigo-500 dark:text-indigo-400" />
                              </div>
                              <span className="font-medium text-gray-800 dark:text-gray-200">
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
                              className="opacity-0 group-hover:opacity-100 p-2 text-red-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-all"
                              title="Remove constraint"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Divider */}
                  <div className="border-t border-gray-100 dark:border-slate-700/50" />

                  {/* Must Sit Apart Section */}
                  <div>
                    <div className="flex items-center gap-2 mb-4">
                      <div className="w-7 h-7 rounded-lg bg-rose-100 dark:bg-rose-900/30 flex items-center justify-center">
                        <Unlink className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400" />
                      </div>
                      <h3 className="font-semibold text-gray-900 dark:text-white text-sm">
                        Must Sit Apart
                      </h3>
                      <span className="ml-auto text-xs font-medium text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-slate-700 px-2.5 py-1 rounded-full">
                        {constraints.summary.total_must_sit_apart}
                      </span>
                    </div>

                    {constraints.must_sit_apart.length === 0 ? (
                      <p className="text-sm text-gray-400 dark:text-gray-500 italic pl-9">
                        No &quot;must sit apart&quot; constraints yet
                      </p>
                    ) : (
                      <div className="space-y-2 pl-9">
                        {constraints.must_sit_apart.map((constraint, idx) => (
                          <div
                            key={`apart-${idx}`}
                            className="group flex items-center justify-between px-4 py-3.5 bg-rose-50/70 dark:bg-rose-900/10 border border-rose-100 dark:border-rose-800/30 rounded-xl transition-all hover:shadow-sm"
                          >
                            <div className="flex items-center gap-3 text-sm">
                              <span className="font-medium text-gray-800 dark:text-gray-200">
                                {constraint.guest_1.name}
                              </span>
                              <div className="w-6 h-6 rounded-md bg-rose-100 dark:bg-rose-800/40 flex items-center justify-center">
                                <Unlink className="w-3 h-3 text-rose-500 dark:text-rose-400" />
                              </div>
                              <span className="font-medium text-gray-800 dark:text-gray-200">
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
                              className="opacity-0 group-hover:opacity-100 p-2 text-red-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-all"
                              title="Remove constraint"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Empty State */}
              {!loading && constraints &&
               constraints.must_sit_together.length === 0 &&
               constraints.must_sit_apart.length === 0 && (
                <div className="text-center py-10">
                  <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-purple-50 dark:bg-purple-900/20 flex items-center justify-center">
                    <Users className="w-7 h-7 text-purple-400 dark:text-purple-500" />
                  </div>
                  <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-2">
                    No Constraints Yet
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 max-w-xs mx-auto">
                    Add constraints to ensure specific guests sit together or apart when using AI Suggest.
                  </p>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 dark:border-slate-700 px-6 py-4 flex items-center justify-between flex-shrink-0 bg-gray-50/50 dark:bg-slate-800/50">
          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
            <Info className="w-3.5 h-3.5" />
            <span>
              {totalConstraints > 0
                ? `${constraints?.summary.guests_with_constraints || 0} guests with constraints — used by AI Suggest`
                : 'Constraints are applied when using AI Suggest'
              }
            </span>
          </div>
          <button
            onClick={onClose}
            className="px-5 py-2.5 bg-gray-200 dark:bg-slate-600 hover:bg-gray-300 dark:hover:bg-slate-500 text-gray-700 dark:text-gray-200 rounded-xl text-sm font-medium transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

export default SeatingConstraintsModal;
