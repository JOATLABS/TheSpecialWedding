'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import { X, Loader2 } from 'lucide-react';
import { useConfirmDialog } from '@/components/ui/ConfirmDialog';
import { ROLES, ALL_PERMISSIONS, ROLE_DEFAULTS } from './teamConstants';

interface TeamMember {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  role: string;
  status: string;
  permissions: Record<string, boolean>;
  wedding_access: string;
  assigned_wedding_ids: string[];
}

interface Wedding {
  _id: string;
  title?: string;
  slug?: string;
  partner1_name?: string;
  partner2_name?: string;
}

interface Props {
  member: TeamMember;
  onClose: () => void;
  onSuccess: () => void;
}

export default function EditTeamMemberModal({ member, onClose, onSuccess }: Props) {
  const { token } = useAdmin();
  const baseUrl = getApiBaseUrl();
  const modalRef = useRef<HTMLDivElement>(null);
  const { confirm } = useConfirmDialog();

  const [role, setRole] = useState(member.role);
  const [permissions, setPermissions] = useState<Record<string, boolean>>({ ...member.permissions });
  const [weddingAccess, setWeddingAccess] = useState<'all' | 'assigned'>(member.wedding_access as 'all' | 'assigned');
  const [assignedWeddingIds, setAssignedWeddingIds] = useState<string[]>([...member.assigned_wedding_ids]);
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [showWeddingPicker, setShowWeddingPicker] = useState(false);

  // Re-initialize form state whenever member prop changes
  useEffect(() => {
    if (member) {
      setRole(member.role);
      setPermissions({ ...member.permissions });
      setWeddingAccess(member.wedding_access as 'all' | 'assigned');
      setAssignedWeddingIds([...member.assigned_wedding_ids]);
      setShowWeddingPicker(false);
      setSubmitting(false);
    }
  }, [member]);

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
        // Silently fail
      }
    };
    fetchWeddings();
  }, [baseUrl, token]);

  // Form reset function (resets temporary changes but next open will re-initialize from member prop)
  const resetForm = useCallback(() => {
    setRole(member.role);
    setPermissions({ ...member.permissions });
    setWeddingAccess(member.wedding_access as 'all' | 'assigned');
    setAssignedWeddingIds([...member.assigned_wedding_ids]);
    setShowWeddingPicker(false);
    setSubmitting(false);
  }, [member]);

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

  const handleRoleChange = async (newRole: string) => {
    if (newRole === role) return;
    // Check if user has customized permissions away from current role defaults
    const currentDefaults = ROLE_DEFAULTS[role] || {};
    const hasCustomPerms = ALL_PERMISSIONS.some((p) => permissions[p.key] !== currentDefaults[p.key]);

    if (hasCustomPerms) {
      const confirmed = await confirm({
        title: 'Change Role',
        message: 'Changing roles will reset permissions to the new role\'s defaults. You can customize them again after. Continue?',
        variant: 'warning',
        confirmText: 'Change Role',
        cancelText: 'Keep Current Role',
      });
      if (!confirmed) return;
    }

    setRole(newRole);
    // Reset permissions to role defaults when changing roles
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
    if (weddingAccess === 'assigned' && assignedWeddingIds.length === 0) {
      toast.error('Please select at least one wedding.');
      return;
    }

    setSubmitting(true);
    try {
      const body: any = {};

      // Only send changed fields
      if (role !== member.role) {
        body.role = role;
      }

      // Check if permissions changed
      const permChanged = ALL_PERMISSIONS.some((p) => permissions[p.key] !== member.permissions[p.key]);
      if (permChanged) {
        body.custom_permissions = permissions;
      }

      if (weddingAccess !== member.wedding_access) {
        body.wedding_access = weddingAccess;
      }

      if (weddingAccess === 'assigned') {
        const idsChanged =
          assignedWeddingIds.length !== member.assigned_wedding_ids.length ||
          assignedWeddingIds.some((id) => !member.assigned_wedding_ids.includes(id));
        if (idsChanged) {
          body.assigned_wedding_ids = assignedWeddingIds;
        }
      }

      if (Object.keys(body).length === 0) {
        toast.info('No changes to save.');
        onClose();
        return;
      }

      const response = await fetch(`${baseUrl}/admin/team/members/${member.id}`, {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to update team member.');
      }

      toast.success('Team member updated successfully.');
      onSuccess();
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const memberName =
    member.first_name && member.last_name ? `${member.first_name} ${member.last_name}` : member.email;

  const modalContent = (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center" onClick={handleClose}>
      <div className="absolute inset-0 bg-slate-950/45 backdrop-blur-sm dark:bg-black/60" />
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        data-testid="edit-modal"
        className="relative z-[10000] mx-4 max-h-[85vh] w-full max-w-[560px] overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700/50 dark:bg-slate-800"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 pb-0">
          <div>
            <h2 id="modal-title" className="text-xl font-bold text-slate-900 dark:text-slate-100">Edit Team Member</h2>
            <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">{memberName}</p>
          </div>
          <button
            onClick={handleClose}
            aria-label="Close modal"
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-500 transition-colors hover:bg-slate-200 hover:text-slate-700 dark:bg-slate-700/50 dark:text-slate-400 dark:hover:bg-slate-700 dark:hover:text-slate-200"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5">
          {/* Role Selector */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-700 dark:text-slate-400">Role</label>
            <div className="grid grid-cols-3 gap-2.5" data-testid="role-selector">
              {ROLES.map((r) => (
                <button
                  key={r.value}
                  onClick={() => handleRoleChange(r.value)}
                  className={`border-2 rounded-xl p-3.5 text-center transition-all ${
                    role === r.value
                      ? 'border-wedding-rose bg-rose-50 dark:bg-wedding-rose/5'
                      : 'border-slate-200 hover:border-slate-300 dark:border-slate-700/30 dark:hover:border-slate-600/50'
                  }`}
                >
                  <p className={`font-semibold text-sm ${r.color}`}>{r.label}</p>
                  <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">{r.desc}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Permissions */}
          <div>
            <p className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Permissions
            </p>
            <div className="grid grid-cols-2 gap-2">
              {ALL_PERMISSIONS.map((perm) => (
                <button
                  key={perm.key}
                  onClick={() => togglePermission(perm.key)}
                  className="flex items-center gap-2.5 rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-left text-sm transition-colors hover:border-slate-300 dark:border-slate-700/20 dark:bg-slate-900/40 dark:hover:border-slate-600/40"
                >
                  <div
                    className={`w-8 h-[18px] rounded-full relative transition-colors flex-shrink-0 ${
                      permissions[perm.key] ? 'bg-wedding-rose' : 'bg-slate-300 dark:bg-slate-600'
                    }`}
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
          </div>

          {/* Wedding Access */}
          <div>
            <p className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Wedding Access
            </p>
            <div className="grid grid-cols-2 gap-2.5">
              <button
                onClick={() => setWeddingAccess('all')}
                className={`border-2 rounded-xl p-3 text-center transition-all ${
                  weddingAccess === 'all'
                    ? 'border-wedding-sage bg-emerald-50 dark:bg-wedding-sage/5'
                    : 'border-slate-200 hover:border-slate-300 dark:border-slate-700/30 dark:hover:border-slate-600/50'
                }`}
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
              >
                <p className="text-sm font-semibold text-teal-700 dark:text-wedding-sage">Specific Weddings</p>
                <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">Choose which weddings</p>
              </button>
            </div>
          </div>

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
                Saving...
              </>
            ) : (
              'Save Changes'
            )}
          </button>
        </div>
      </div>
    </div>
  );

  if (typeof window === 'undefined') return null;
  return createPortal(modalContent, document.body);
}
