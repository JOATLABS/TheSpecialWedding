'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import { X, Loader2 } from 'lucide-react';
import { ROLES, ALL_PERMISSIONS, ROLE_DEFAULTS } from './teamConstants';

interface Props {
  onClose: () => void;
  onSuccess: () => void;
}

interface Wedding {
  _id: string;
  title?: string;
  slug?: string;
  partner1_name?: string;
  partner2_name?: string;
}

export default function InviteTeamMemberModal({ onClose, onSuccess }: Props) {
  const { token } = useAdmin();
  const baseUrl = getApiBaseUrl();
  const modalRef = useRef<HTMLDivElement>(null);

  const [email, setEmail] = useState('');
  const [role, setRole] = useState('editor');
  const [permissions, setPermissions] = useState<Record<string, boolean>>(ROLE_DEFAULTS.editor);
  const [weddingAccess, setWeddingAccess] = useState<'all' | 'assigned'>('all');
  const [assignedWeddingIds, setAssignedWeddingIds] = useState<string[]>([]);
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [showWeddingPicker, setShowWeddingPicker] = useState(false);

  // Fetch weddings for assignment
  useEffect(() => {
    const fetchWeddings = async () => {
      try {
        const response = await fetch(`${baseUrl}/admin/weddings`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: 'no-store',
        });
        if (response.ok) {
          const data = await response.json();
          setWeddings(Array.isArray(data) ? data : data.weddings || []);
        }
      } catch {
        // Silently fail — weddings list is optional
      }
    };
    fetchWeddings();
  }, [baseUrl, token]);

  // Form reset function
  const resetForm = useCallback(() => {
    setEmail('');
    setRole('editor');
    setPermissions({ ...ROLE_DEFAULTS.editor });
    setWeddingAccess('all');
    setAssignedWeddingIds([]);
    setShowWeddingPicker(false);
    setSubmitting(false);
  }, []);

  // Close handler that resets form state
  const handleClose = useCallback(() => {
    resetForm();
    onClose();
  }, [onClose, resetForm]);

  // Focus trap and keyboard handling
  useEffect(() => {
    const modal = modalRef.current;
    if (!modal) return;

    const focusableElements = modal.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const firstElement = focusableElements[0] as HTMLElement;
    const lastElement = focusableElements[focusableElements.length - 1] as HTMLElement;

    firstElement?.focus();

    const handleTab = (e: KeyboardEvent) => {
      if (e.key === 'Tab') {
        if (e.shiftKey && document.activeElement === firstElement) {
          e.preventDefault();
          lastElement?.focus();
        } else if (!e.shiftKey && document.activeElement === lastElement) {
          e.preventDefault();
          firstElement?.focus();
        }
      }
      if (e.key === 'Escape') {
        handleClose();
      }
    };

    modal.addEventListener('keydown', handleTab);
    return () => modal.removeEventListener('keydown', handleTab);
  }, [handleClose]);

  const handleRoleChange = (newRole: string) => {
    setRole(newRole);
    setPermissions({ ...ROLE_DEFAULTS[newRole] });
  };

  const togglePermission = (key: string) => {
    setPermissions((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const getWeddingName = (w: Wedding) => {
    if (w.title) return w.title;
    if (w.partner1_name && w.partner2_name) return `${w.partner1_name} & ${w.partner2_name}`;
    return w.slug || w._id;
  };

  const handleSubmit = async () => {
    if (!email.trim()) {
      toast.error('Please enter an email address.');
      return;
    }

    if (weddingAccess === 'assigned' && assignedWeddingIds.length === 0) {
      toast.error('Please select at least one wedding.');
      return;
    }

    setSubmitting(true);
    try {
      const body: any = {
        email: email.trim().toLowerCase(),
        role,
        wedding_access: weddingAccess,
      };

      // Only send custom permissions if they differ from role defaults
      const defaults = ROLE_DEFAULTS[role];
      const hasCustom = ALL_PERMISSIONS.some((p) => permissions[p.key] !== defaults[p.key]);
      if (hasCustom) {
        body.custom_permissions = permissions;
      }

      if (weddingAccess === 'assigned') {
        body.assigned_wedding_ids = assignedWeddingIds;
      }

      const response = await fetch(`${baseUrl}/admin/team/invite`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to send invitation.');
      }

      toast.success(`Invitation sent to ${email}`);
      resetForm();
      onSuccess();
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const modalContent = (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center" onClick={handleClose} role="presentation">
      <div className="absolute inset-0 bg-slate-950/45 backdrop-blur-sm dark:bg-black/60" aria-hidden="true" />
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        aria-describedby="modal-description"
        data-testid="invite-modal"
        className="relative z-[10000] mx-4 max-h-[85vh] w-full max-w-[560px] overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700/50 dark:bg-slate-800"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 pb-0">
          <div>
            <h2 id="modal-title" className="text-xl font-bold text-slate-900 dark:text-slate-100">Invite Team Member</h2>
            <p id="modal-description" className="mt-1 text-sm text-slate-600 dark:text-slate-400">Add a new team member to collaborate on wedding planning</p>
          </div>
          <button
            onClick={handleClose}
            aria-label="Close invite team member modal"
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-500 transition-colors hover:bg-slate-200 hover:text-slate-700 dark:bg-slate-700/50 dark:text-slate-400 dark:hover:bg-slate-700 dark:hover:text-slate-200"
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5">
          {/* Email */}
          <div>
            <label htmlFor="team-member-email" className="mb-1.5 block text-xs font-medium text-slate-700 dark:text-slate-400">Email Address</label>
            <input
              id="team-member-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="teammate@company.com"
              data-testid="invite-email"
              className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 transition-colors focus:border-wedding-rose focus:outline-none dark:border-slate-700/50 dark:bg-slate-900/60 dark:text-slate-200 dark:placeholder:text-slate-600"
              aria-required="true"
            />
          </div>

          {/* Role Selector */}
          <div>
            <fieldset>
              <legend className="mb-1.5 block text-xs font-medium text-slate-700 dark:text-slate-400">Role</legend>
              <div className="grid grid-cols-3 gap-2.5" role="group">
                {ROLES.map((r) => (
                  <button
                    key={r.value}
                    onClick={() => handleRoleChange(r.value)}
                    className={`border-2 rounded-xl p-3.5 text-center transition-all ${
                      role === r.value
                        ? 'border-wedding-rose bg-rose-50 dark:bg-wedding-rose/5'
                        : 'border-slate-200 hover:border-slate-300 dark:border-slate-700/30 dark:hover:border-slate-600/50'
                    }`}
                    role="radio"
                    aria-checked={role === r.value}
                    aria-label={`${r.label} - ${r.desc}`}
                  >
                    <p className={`font-semibold text-sm ${r.color}`}>{r.label}</p>
                    <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">{r.desc}</p>
                  </button>
                ))}
              </div>
            </fieldset>
          </div>

          {/* Permissions */}
          <fieldset>
            <legend className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Customize Permissions
            </legend>
            <div className="grid grid-cols-2 gap-2">
              {ALL_PERMISSIONS.map((perm) => (
                <button
                  key={perm.key}
                  onClick={() => togglePermission(perm.key)}
                  className="flex items-center gap-2.5 rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-left text-sm transition-colors hover:border-slate-300 dark:border-slate-700/20 dark:bg-slate-900/40 dark:hover:border-slate-600/40"
                  role="switch"
                  aria-checked={permissions[perm.key]}
                  aria-label={`${perm.label} - ${permissions[perm.key] ? 'enabled' : 'disabled'}`}
                >
                  <div
                    className={`w-8 h-[18px] rounded-full relative transition-colors flex-shrink-0 ${
                      permissions[perm.key] ? 'bg-wedding-rose' : 'bg-slate-300 dark:bg-slate-600'
                    }`}
                    aria-hidden="true"
                  >
                    <div
                      className={`w-3.5 h-3.5 rounded-full bg-white absolute top-[2px] transition-all ${
                        permissions[perm.key] ? 'left-[18px]' : 'left-[2px]'
                      }`}
                    />
                  </div>
                  <span className="text-xs text-slate-700 dark:text-slate-300">{perm.label}</span>
                </button>
              ))}
            </div>
          </fieldset>

          {/* Wedding Access */}
          <fieldset>
            <legend className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Wedding Access
            </legend>
            <div className="grid grid-cols-2 gap-2.5" role="group">
              <button
                onClick={() => setWeddingAccess('all')}
                className={`border-2 rounded-xl p-3 text-center transition-all ${
                  weddingAccess === 'all'
                    ? 'border-wedding-sage bg-emerald-50 dark:bg-wedding-sage/5'
                    : 'border-slate-200 hover:border-slate-300 dark:border-slate-700/30 dark:hover:border-slate-600/50'
                }`}
                role="radio"
                aria-checked={weddingAccess === 'all'}
                aria-label="All weddings - access every wedding"
              >
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-200">All Weddings</p>
                <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">Access every wedding</p>
              </button>
              <button
                onClick={() => setWeddingAccess('assigned')}
                className={`border-2 rounded-xl p-3 text-center transition-all ${
                  weddingAccess === 'assigned'
                    ? 'border-wedding-sage bg-emerald-50 dark:bg-wedding-sage/5'
                    : 'border-slate-200 hover:border-slate-300 dark:border-slate-700/30 dark:hover:border-slate-600/50'
                }`}
                role="radio"
                aria-checked={weddingAccess === 'assigned'}
                aria-label="Specific weddings - choose which weddings"
              >
                <p className="text-sm font-semibold text-teal-700 dark:text-wedding-sage">Specific Weddings</p>
                <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">Choose which weddings</p>
              </button>
            </div>
          </fieldset>

          {/* Wedding picker */}
          {weddingAccess === 'assigned' && (
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-700 dark:text-slate-400">Select Weddings</label>
              <div className="flex flex-wrap gap-2">
                {assignedWeddingIds.map((wId) => {
                  const w = weddings.find((w) => w._id === wId);
                  return (
                    <span
                      key={wId}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs text-emerald-700 dark:border-wedding-sage/20 dark:bg-wedding-sage/10 dark:text-wedding-sage"
                    >
                      {w ? getWeddingName(w) : wId}
                      <button
                        onClick={() => setAssignedWeddingIds((prev) => prev.filter((id) => id !== wId))}
                        className="opacity-60 hover:opacity-100"
                      >
                        <X size={12} />
                      </button>
                    </span>
                  );
                })}
                <div className="relative">
                  <button
                    onClick={() => setShowWeddingPicker(!showWeddingPicker)}
                    className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-xs text-slate-600 transition-colors hover:bg-slate-200 hover:text-slate-900 dark:border-slate-700/30 dark:bg-slate-700/30 dark:text-slate-400 dark:hover:bg-slate-700/50 dark:hover:text-slate-200"
                  >
                    + Add wedding
                  </button>
                  {showWeddingPicker && (
                    <div className="absolute left-0 top-full z-10 mt-1 max-h-48 min-w-[200px] overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-xl dark:border-slate-700/50 dark:bg-slate-800">
                      {weddings
                        .filter((w) => !assignedWeddingIds.includes(w._id))
                        .map((w) => (
                          <button
                            key={w._id}
                            onClick={() => {
                              setAssignedWeddingIds((prev) => [...prev, w._id]);
                              setShowWeddingPicker(false);
                            }}
                            className="w-full px-3 py-2 text-left text-sm text-slate-700 transition-colors hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-700/50"
                          >
                            {getWeddingName(w)}
                          </button>
                        ))}
                      {weddings.filter((w) => !assignedWeddingIds.includes(w._id)).length === 0 && (
                        <p className="px-3 py-2 text-xs text-slate-500 dark:text-slate-400">No more weddings to add</p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-6 pt-0">
          <button
            onClick={handleClose}
            data-testid="modal-cancel"
            className="rounded-xl border border-slate-300 px-5 py-2.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900 dark:border-slate-700/50 dark:text-slate-400 dark:hover:bg-slate-700/20 dark:hover:text-slate-200"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            data-testid="modal-submit"
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-wedding-rose to-[#c48e8e] px-6 py-2.5 text-sm font-semibold text-slate-950 transition-all hover:shadow-lg hover:shadow-wedding-rose/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Sending...
              </>
            ) : (
              'Send Invitation'
            )}
          </button>
        </div>
      </div>
    </div>
  );

  if (typeof window === 'undefined') return null;
  return createPortal(modalContent, document.body);
}
