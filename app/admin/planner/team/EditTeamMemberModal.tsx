'use client';

import React, { useState, useEffect, useRef } from 'react';
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
  const resetForm = () => {
    setRole(member.role);
    setPermissions({ ...member.permissions });
    setWeddingAccess(member.wedding_access as 'all' | 'assigned');
    setAssignedWeddingIds([...member.assigned_wedding_ids]);
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
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        data-testid="edit-modal"
        className="relative z-[10000] bg-slate-800 border border-slate-700/50 rounded-2xl w-full max-w-[560px] max-h-[85vh] overflow-y-auto shadow-2xl mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 pb-0">
          <div>
            <h2 id="modal-title" className="text-xl font-bold text-slate-100">Edit Team Member</h2>
            <p className="text-sm text-slate-500 mt-0.5">{memberName}</p>
          </div>
          <button
            onClick={handleClose}
            aria-label="Close modal"
            className="w-8 h-8 rounded-lg bg-slate-700/50 flex items-center justify-center text-slate-400 hover:text-slate-200 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5">
          {/* Role Selector */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5">Role</label>
            <div className="grid grid-cols-3 gap-2.5" data-testid="role-selector">
              {ROLES.map((r) => (
                <button
                  key={r.value}
                  onClick={() => handleRoleChange(r.value)}
                  className={`border-2 rounded-xl p-3.5 text-center transition-all ${
                    role === r.value
                      ? 'border-wedding-rose bg-wedding-rose/5'
                      : 'border-slate-700/30 hover:border-slate-600/50'
                  }`}
                >
                  <p className={`font-semibold text-sm ${r.color}`}>{r.label}</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">{r.desc}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Permissions */}
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2.5">
              Permissions
            </p>
            <div className="grid grid-cols-2 gap-2">
              {ALL_PERMISSIONS.map((perm) => (
                <button
                  key={perm.key}
                  onClick={() => togglePermission(perm.key)}
                  className="flex items-center gap-2.5 p-2.5 rounded-lg bg-slate-900/40 border border-slate-700/20 text-sm text-left"
                >
                  <div
                    className={`w-8 h-[18px] rounded-full relative transition-colors flex-shrink-0 ${
                      permissions[perm.key] ? 'bg-wedding-rose' : 'bg-slate-600'
                    }`}
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
          </div>

          {/* Wedding Access */}
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2.5">
              Wedding Access
            </p>
            <div className="grid grid-cols-2 gap-2.5">
              <button
                onClick={() => setWeddingAccess('all')}
                className={`border-2 rounded-xl p-3 text-center transition-all ${
                  weddingAccess === 'all'
                    ? 'border-wedding-sage bg-wedding-sage/5'
                    : 'border-slate-700/30 hover:border-slate-600/50'
                }`}
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
              >
                <p className="font-semibold text-sm text-wedding-sage">Specific Weddings</p>
                <p className="text-[11px] text-slate-500 mt-0.5">Choose which weddings</p>
              </button>
            </div>
          </div>

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
