'use client';

import React, { useState, useEffect, useRef } from 'react';
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
  const resetForm = () => {
    setEmail('');
    setRole('editor');
    setPermissions({ ...ROLE_DEFAULTS.editor });
    setWeddingAccess('all');
    setAssignedWeddingIds([]);
    setShowWeddingPicker(false);
    setSubmitting(false);
  };

  // Close handler that resets form state
  const handleClose = () => {
    resetForm();
    onClose();
  };

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
  }, []);

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
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" aria-hidden="true" />
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        aria-describedby="modal-description"
        data-testid="invite-modal"
        className="relative z-[10000] bg-slate-800 border border-slate-700/50 rounded-2xl w-full max-w-[560px] max-h-[85vh] overflow-y-auto shadow-2xl mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 pb-0">
          <div>
            <h2 id="modal-title" className="text-xl font-bold text-slate-100">Invite Team Member</h2>
            <p id="modal-description" className="text-sm text-slate-400 mt-1">Add a new team member to collaborate on wedding planning</p>
          </div>
          <button
            onClick={handleClose}
            aria-label="Close invite team member modal"
            className="w-8 h-8 rounded-lg bg-slate-700/50 flex items-center justify-center text-slate-400 hover:text-slate-200 transition-colors"
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5">
          {/* Email */}
          <div>
            <label htmlFor="team-member-email" className="block text-xs font-medium text-slate-400 mb-1.5">Email Address</label>
            <input
              id="team-member-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="teammate@company.com"
              data-testid="invite-email"
              className="w-full bg-slate-900/60 border border-slate-700/50 rounded-lg px-3.5 py-2.5 text-sm text-slate-200 placeholder:text-slate-600 focus:border-wedding-rose focus:outline-none transition-colors"
              aria-required="true"
            />
          </div>

          {/* Role Selector */}
          <div>
            <fieldset>
              <legend className="block text-xs font-medium text-slate-400 mb-1.5">Role</legend>
              <div className="grid grid-cols-3 gap-2.5" role="group">
                {ROLES.map((r) => (
                  <button
                    key={r.value}
                    onClick={() => handleRoleChange(r.value)}
                    className={`border-2 rounded-xl p-3.5 text-center transition-all ${
                      role === r.value
                        ? 'border-wedding-rose bg-wedding-rose/5'
                        : 'border-slate-700/30 hover:border-slate-600/50'
                    }`}
                    role="radio"
                    aria-checked={role === r.value}
                    aria-label={`${r.label} - ${r.desc}`}
                  >
                    <p className={`font-semibold text-sm ${r.color}`}>{r.label}</p>
                    <p className="text-[11px] text-slate-500 mt-0.5">{r.desc}</p>
                  </button>
                ))}
              </div>
            </fieldset>
          </div>

          {/* Permissions */}
          <fieldset>
            <legend className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2.5">
              Customize Permissions
            </legend>
            <div className="grid grid-cols-2 gap-2">
              {ALL_PERMISSIONS.map((perm) => (
                <button
                  key={perm.key}
                  onClick={() => togglePermission(perm.key)}
                  className="flex items-center gap-2.5 p-2.5 rounded-lg bg-slate-900/40 border border-slate-700/20 text-sm text-left hover:border-slate-600/40 transition-colors"
                  role="switch"
                  aria-checked={permissions[perm.key]}
                  aria-label={`${perm.label} - ${permissions[perm.key] ? 'enabled' : 'disabled'}`}
                >
                  <div
                    className={`w-8 h-[18px] rounded-full relative transition-colors flex-shrink-0 ${
                      permissions[perm.key] ? 'bg-wedding-rose' : 'bg-slate-600'
                    }`}
                    aria-hidden="true"
                  >
                    <div
                      className={`w-3.5 h-3.5 rounded-full bg-white absolute top-[2px] transition-all ${
                        permissions[perm.key] ? 'left-[18px]' : 'left-[2px]'
                      }`}
                    />
                  </div>
                  <span className="text-slate-300 text-xs">{perm.label}</span>
                </button>
              ))}
            </div>
          </fieldset>

          {/* Wedding Access */}
          <fieldset>
            <legend className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2.5">
              Wedding Access
            </legend>
            <div className="grid grid-cols-2 gap-2.5" role="group">
              <button
                onClick={() => setWeddingAccess('all')}
                className={`border-2 rounded-xl p-3 text-center transition-all ${
                  weddingAccess === 'all'
                    ? 'border-wedding-sage bg-wedding-sage/5'
                    : 'border-slate-700/30 hover:border-slate-600/50'
                }`}
                role="radio"
                aria-checked={weddingAccess === 'all'}
                aria-label="All weddings - access every wedding"
              >
                <p className="font-semibold text-sm text-slate-200">All Weddings</p>
                <p className="text-[11px] text-slate-500 mt-0.5">Access every wedding</p>
              </button>
              <button
                onClick={() => setWeddingAccess('assigned')}
                className={`border-2 rounded-xl p-3 text-center transition-all ${
                  weddingAccess === 'assigned'
                    ? 'border-wedding-sage bg-wedding-sage/5'
                    : 'border-slate-700/30 hover:border-slate-600/50'
                }`}
                role="radio"
                aria-checked={weddingAccess === 'assigned'}
                aria-label="Specific weddings - choose which weddings"
              >
                <p className="font-semibold text-sm text-wedding-sage">Specific Weddings</p>
                <p className="text-[11px] text-slate-500 mt-0.5">Choose which weddings</p>
              </button>
            </div>
          </fieldset>

          {/* Wedding picker */}
          {weddingAccess === 'assigned' && (
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Select Weddings</label>
              <div className="flex flex-wrap gap-2">
                {assignedWeddingIds.map((wId) => {
                  const w = weddings.find((w) => w._id === wId);
                  return (
                    <span
                      key={wId}
                      className="inline-flex items-center gap-1.5 bg-wedding-sage/10 border border-wedding-sage/20 px-3 py-1.5 rounded-lg text-xs text-wedding-sage"
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
                    className="inline-flex items-center gap-1 bg-slate-700/30 border border-slate-700/30 px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-slate-200 transition-colors"
                  >
                    + Add wedding
                  </button>
                  {showWeddingPicker && (
                    <div className="absolute top-full left-0 mt-1 bg-slate-800 border border-slate-700/50 rounded-lg shadow-xl z-10 max-h-48 overflow-y-auto min-w-[200px]">
                      {weddings
                        .filter((w) => !assignedWeddingIds.includes(w._id))
                        .map((w) => (
                          <button
                            key={w._id}
                            onClick={() => {
                              setAssignedWeddingIds((prev) => [...prev, w._id]);
                              setShowWeddingPicker(false);
                            }}
                            className="w-full text-left px-3 py-2 text-sm text-slate-300 hover:bg-slate-700/50 transition-colors"
                          >
                            {getWeddingName(w)}
                          </button>
                        ))}
                      {weddings.filter((w) => !assignedWeddingIds.includes(w._id)).length === 0 && (
                        <p className="px-3 py-2 text-xs text-slate-500">No more weddings to add</p>
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
            className="px-5 py-2.5 rounded-xl border border-slate-700/50 text-sm text-slate-400 font-medium hover:text-slate-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            data-testid="modal-submit"
            className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-wedding-rose to-[#c48e8e] text-slate-900 text-sm font-semibold hover:shadow-lg hover:shadow-wedding-rose/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
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
