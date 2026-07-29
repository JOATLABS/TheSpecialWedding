'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import {
  INCLUDED_WITH_PLANNER_PLANS_COPY,
  isCouplePlan,
} from '@/admin/utils/planAccess';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
import { usePagination } from '@/admin/hooks/usePagination';
import { GlassPagination } from '@/admin/components/ui/glass/GlassPagination';
import {
  Users,
  UserPlus,
  Search,
  Pencil,
  Ban,
  RotateCcw,
  Trash2,
  Send,
  Loader2,
} from 'lucide-react';
import { useConfirmDialog } from '@/components/ui/ConfirmDialog';
import InviteTeamMemberModal from './InviteTeamMemberModal';
import EditTeamMemberModal from './EditTeamMemberModal';

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
  created_at: string;
  invited_at?: string;
  accepted_at?: string;
  deactivated_at?: string;
  last_active_at?: string;
  updated_at?: string;
  user_id?: string;
  owner_email?: string;
}

interface SeatsInfo {
  total_seats: number;
  used_seats: number;
  available_seats: number;
  members_by_status?: Record<string, number>;
}

export default function TeamManagementPage() {
  const { token, userProfile } = useAdmin();
  const baseUrl = getApiBaseUrl();
  const { confirm } = useConfirmDialog();
  const pagination = usePagination({ initialItemsPerPage: 50 });

  const [members, setMembers] = useState<TeamMember[]>([]);
  const [seatsInfo, setSeatsInfo] = useState<SeatsInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'pending' | 'deactivated'>('all');
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});

  // Modal state
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [editMember, setEditMember] = useState<TeamMember | null>(null);

  const fetchData = useCallback(async () => {
    if (!token) return;

    try {
      const headers = {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      };

      const [membersRes, seatsRes] = await Promise.all([
        fetch(`${baseUrl}/admin/team/members?skip=${pagination.skip}&limit=${pagination.itemsPerPage}`, { headers, cache: 'no-store' }),
        fetch(`${baseUrl}/admin/team/seats`, { headers, cache: 'no-store' }),
      ]);

      if (membersRes.ok) {
        const data = await membersRes.json();
        // API returns { members: [...], total, skip, limit }
        const membersList = Array.isArray(data) ? data : data.members ?? [];
        setMembers(membersList);
        if (data.total !== undefined) {
          pagination.setTotalItems(data.total);
        }
      }

      if (seatsRes.ok) {
        const data = await seatsRes.json();
        setSeatsInfo(data);
      }
    } catch (err) {
      console.error('Failed to fetch team data');
      toast.error('Failed to load team data.');
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, baseUrl, pagination.skip, pagination.itemsPerPage]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleResendInvite = async (memberId: string) => {
    if (actionLoading[memberId]) return;
    setActionLoading(prev => ({ ...prev, [memberId]: true }));
    try {
      const response = await fetch(`${baseUrl}/admin/team/members/${memberId}/resend-invite`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to resend invite.');
      }
      toast.success('Invitation resent successfully.');
      fetchData();
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setActionLoading(prev => ({ ...prev, [memberId]: false }));
    }
  };

  const handleDeactivate = async (memberId: string) => {
    const confirmed = await confirm({
      title: 'Deactivate Team Member',
      message: 'Are you sure you want to deactivate this team member? They will lose access immediately.',
      variant: 'danger',
      confirmText: 'Deactivate',
      cancelText: 'Cancel',
    });
    if (!confirmed) return;
    if (actionLoading[memberId]) return;

    const prevMembers = [...members];
    // Optimistic update
    setMembers(prev => prev.map(m =>
      m.id === memberId ? { ...m, status: 'deactivated' } : m
    ));

    setActionLoading(prev => ({ ...prev, [memberId]: true }));
    try {
      const response = await fetch(`${baseUrl}/admin/team/members/${memberId}/deactivate`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to deactivate member.');
      }
      toast.success('Team member deactivated.');
      fetchData();
    } catch (err: any) {
      // Revert on failure
      setMembers(prevMembers);
      toast.error(err.message);
    } finally {
      setActionLoading(prev => ({ ...prev, [memberId]: false }));
    }
  };

  const handleReactivate = async (memberId: string) => {
    if (actionLoading[memberId]) return;

    const prevMembers = [...members];
    // Optimistic update
    setMembers(prev => prev.map(m =>
      m.id === memberId ? { ...m, status: 'active' } : m
    ));

    setActionLoading(prev => ({ ...prev, [memberId]: true }));
    try {
      const response = await fetch(`${baseUrl}/admin/team/members/${memberId}/reactivate`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to reactivate member.');
      }
      toast.success('Team member reactivated.');
      fetchData();
    } catch (err: any) {
      // Revert on failure
      setMembers(prevMembers);
      toast.error(err.message);
    } finally {
      setActionLoading(prev => ({ ...prev, [memberId]: false }));
    }
  };

  const handleRemove = async (memberId: string) => {
    const confirmed = await confirm({
      title: 'Remove Team Member',
      message: 'Are you sure you want to remove this team member? This action cannot be undone.',
      variant: 'danger',
      confirmText: 'Remove',
      cancelText: 'Cancel',
    });
    if (!confirmed) return;
    if (actionLoading[memberId]) return;

    const prevMembers = [...members];
    // Optimistic update - filter out the member
    setMembers(prev => prev.filter(m => m.id !== memberId));

    setActionLoading(prev => ({ ...prev, [memberId]: true }));
    try {
      const response = await fetch(`${baseUrl}/admin/team/members/${memberId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to remove member.');
      }
      toast.success('Team member removed.');
    } catch (err: any) {
      // Revert on failure
      setMembers(prevMembers);
      toast.error(err.message);
    } finally {
      setActionLoading(prev => ({ ...prev, [memberId]: false }));
    }
  };

  // Filter members
  const filteredMembers = useMemo(() => {
    return members.filter((m) => {
      const matchesSearch =
        !searchQuery ||
        m.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (m.first_name && m.first_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (m.last_name && m.last_name.toLowerCase().includes(searchQuery.toLowerCase()));

      const matchesStatus = statusFilter === 'all' || m.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [members, searchQuery, statusFilter]);

  // Stats
  const activeCount = members.filter((m) => m.status === 'active').length;
  const pendingCount = members.filter((m) => m.status === 'pending').length;
  const deactivatedCount = members.filter((m) => m.status === 'deactivated').length;

  const getInitials = (member: TeamMember) => {
    if (member.first_name && member.last_name) {
      return `${member.first_name[0]}${member.last_name[0]}`.toUpperCase();
    }
    return member.email.substring(0, 2).toUpperCase();
  };

  const avatarColors: Record<string, string> = {
    admin: 'bg-gradient-to-br from-wedding-rose to-[#c48e8e]',
    editor: 'bg-gradient-to-br from-wedding-sage to-[#7ec8cc]',
    viewer: 'bg-gradient-to-br from-wedding-gold to-[#d4a843]',
  };

  const roleStyles: Record<string, string> = {
    admin: 'bg-rose-50 text-rose-700 dark:bg-wedding-rose/15 dark:text-wedding-rose',
    editor: 'bg-teal-50 text-teal-700 dark:bg-wedding-sage/15 dark:text-wedding-sage',
    viewer: 'bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-400',
  };

  const statusDotColors: Record<string, string> = {
    active: 'bg-green-400',
    pending: 'bg-wedding-gold',
    deactivated: 'bg-red-400',
  };

  const surfaceCardClass =
    'rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700/30 dark:bg-slate-800/50 dark:shadow-none dark:backdrop-blur-sm';

  const iconActionClass =
    'w-8 h-8 rounded-lg border border-slate-200 bg-white flex items-center justify-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed dark:border-slate-700/50 dark:bg-slate-900/40';

  const formatLastActive = (member: TeamMember) => {
    if (member.status === 'pending') {
      const days = Math.floor(
        (Date.now() - new Date(member.created_at).getTime()) / (1000 * 60 * 60 * 24)
      );
      return days === 0 ? 'Invited today' : `Invited ${days}d ago`;
    }
    if (!member.last_active_at) return '—';
    const diff = Date.now() - new Date(member.last_active_at).getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    if (hours < 1) return 'Just now';
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days === 1) return 'Yesterday';
    return `${days}d ago`;
  };

  // Couple-plan workspaces have no team seats. The sidebar never links
  // here, but a direct URL visit gets a clear explanation instead of the
  // backend's 403.
  if (isCouplePlan(userProfile)) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center max-w-md">
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
            Team management
          </h1>
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
            {INCLUDED_WITH_PLANNER_PLANS_COPY} The couple plan is a personal
            workspace for your own wedding and doesn&apos;t include team seats.
          </p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-wedding-rose mx-auto" />
          <p className="mt-3 text-sm text-slate-600 dark:text-slate-400">Loading team...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 sm:text-3xl">Team Management</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">Manage your team members, roles, and permissions</p>
        </div>
        <div className="flex items-center gap-3">
          {seatsInfo && (
            <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700 dark:border-wedding-rose/20 dark:bg-wedding-rose/10 dark:text-wedding-rose">
              <Users size={16} />
              <span>
                <strong className="text-lg font-semibold">{seatsInfo.used_seats}</strong> / {seatsInfo.total_seats} seats
              </span>
            </div>
          )}
          <div className="relative group">
            <button
              onClick={() => setShowInviteModal(true)}
              disabled={seatsInfo ? seatsInfo.available_seats <= 0 : false}
              data-testid="invite-member-btn"
              className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-wedding-rose to-[#c48e8e] px-5 py-2.5 text-sm font-semibold text-slate-950 shadow-sm transition-all hover:shadow-lg hover:shadow-wedding-rose/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <UserPlus size={16} />
              Invite Team Member
            </button>
            {seatsInfo && seatsInfo.available_seats <= 0 && (
              <div className="pointer-events-none absolute bottom-full left-1/2 mb-2 -translate-x-1/2 whitespace-nowrap rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-100 opacity-0 shadow-lg transition-opacity group-hover:opacity-100 dark:border-slate-700 dark:bg-slate-900">
                No seats available. Upgrade your plan or remove a member.
                <div className="absolute left-1/2 top-full -mt-px -translate-x-1/2 border-4 border-transparent border-t-slate-950 dark:border-t-slate-900" />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className={`${surfaceCardClass} p-5`} data-testid="stat-total">
          <p className="mb-1.5 text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">Total Members</p>
          <p className="text-2xl font-bold text-wedding-rose">{members.length}</p>
        </div>
        <div className={`${surfaceCardClass} p-5`} data-testid="stat-active">
          <p className="mb-1.5 text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">Active</p>
          <p className="text-2xl font-bold text-wedding-sage">{activeCount}</p>
        </div>
        <div className={`${surfaceCardClass} p-5`} data-testid="stat-pending">
          <p className="mb-1.5 text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">Pending Invites</p>
          <p className="text-2xl font-bold text-wedding-gold">{pendingCount}</p>
        </div>
        <div className={`${surfaceCardClass} p-5`} data-testid="stat-remaining">
          <p className="mb-1.5 text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400">Seats Remaining</p>
          <p className="text-2xl font-bold text-slate-700 dark:text-slate-300">{seatsInfo ? seatsInfo.available_seats : '—'}</p>
        </div>
      </div>

      {/* Table */}
      <div className={`${surfaceCardClass} overflow-hidden`}>
        {/* Table header bar */}
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 dark:border-slate-700/30 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <h2 className="font-semibold text-slate-900 dark:text-slate-200">Team Members</h2>
            <div className="flex rounded-lg border border-slate-200 bg-slate-100 p-0.5 dark:border-slate-700/30 dark:bg-slate-900/60">
              {(['all', 'active', 'pending', 'deactivated'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => {
                    setStatusFilter(tab);
                    pagination.setPage(1);
                  }}
                  data-testid={`tab-${tab}`}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-colors capitalize ${
                    statusFilter === tab
                      ? 'bg-white text-wedding-rose shadow-sm dark:bg-wedding-rose/15 dark:text-wedding-rose dark:shadow-none'
                      : 'text-slate-500 hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-300'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700/30 dark:bg-slate-900/60">
            <Search size={14} className="text-slate-400 dark:text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                pagination.setPage(1);
              }}
              placeholder="Search members..."
              data-testid="member-search"
              className="w-48 border-none bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400 dark:text-slate-200 dark:placeholder:text-slate-600"
            />
          </div>
        </div>

        {/* Table content */}
        {filteredMembers.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Users className="mb-3 h-10 w-10 text-slate-300 dark:text-slate-600" />
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {members.length === 0 ? 'No team members yet. Invite your first teammate!' : 'No members match your filters.'}
            </p>
          </div>
        ) : (
          <>
            <GlassPagination
              currentPage={pagination.currentPage}
              totalPages={pagination.totalPages}
              totalItems={pagination.totalItems}
              itemsPerPage={pagination.itemsPerPage}
              onPageChange={pagination.setPage}
              variant="compact"
              itemLabel="members"
            />
            <div className="overflow-x-auto">
              <table className="w-full">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700/30">
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">Member</th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">Role</th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">Status</th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">Wedding Access</th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">Last Active</th>
                  <th className="px-5 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredMembers.map((member) => (
                  <tr key={member.id} data-testid={`member-row-${member.id}`} className="border-b border-slate-100 transition-colors hover:bg-slate-50 dark:border-slate-700/10 dark:hover:bg-slate-700/10">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-9 h-9 rounded-full flex items-center justify-center text-xs font-semibold text-slate-900 ${
                            avatarColors[member.role] || 'bg-gradient-to-br from-slate-400 to-slate-500'
                          }`}
                        >
                          {getInitials(member)}
                        </div>
                        <div>
                          <p className="text-sm font-medium text-slate-900 dark:text-slate-200">
                            {member.first_name && member.last_name
                              ? `${member.first_name} ${member.last_name}`
                              : '—'}
                          </p>
                          <p className="text-xs text-slate-500 dark:text-slate-400">{member.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${
                          roleStyles[member.role] || 'bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-400'
                        }`}
                      >
                        {member.role.charAt(0).toUpperCase() + member.role.slice(1)}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span className="inline-flex items-center gap-1.5 text-sm">
                        <span
                          className={`w-2 h-2 rounded-full ${statusDotColors[member.status] || 'bg-slate-500'}`}
                          aria-label={`Status: ${member.status}`}
                        />
                        <span className="capitalize text-slate-700 dark:text-slate-300">{member.status}</span>
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-sm text-slate-500 dark:text-slate-400">
                        {member.wedding_access === 'all' ? (
                          <><strong className="text-slate-900 dark:text-slate-200">All</strong> weddings</>
                        ) : (
                          <><strong className="text-slate-900 dark:text-slate-200">{member.assigned_wedding_ids.length}</strong> assigned</>
                        )}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-xs text-slate-500 dark:text-slate-400">{formatLastActive(member)}</span>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-1.5">
                        {actionLoading[member.id] ? (
                          <Loader2 size={16} className="animate-spin text-slate-500 dark:text-slate-400" />
                        ) : (
                          <>
                            {member.status === 'pending' && (
                              <>
                                <button
                                  onClick={() => handleResendInvite(member.id)}
                                  disabled={actionLoading[member.id]}
                                  title="Resend Invite"
                                  data-testid={`resend-${member.id}`}
                                  aria-label={`Resend invite to ${member.email}`}
                                  className={`${iconActionClass} text-amber-600 hover:border-amber-200 hover:bg-amber-50 dark:text-wedding-gold dark:hover:border-slate-600/50 dark:hover:bg-slate-700/30`}
                                >
                                  <Send size={14} />
                                </button>
                                <button
                                  onClick={() => handleRemove(member.id)}
                                  disabled={actionLoading[member.id]}
                                  title="Remove"
                                  data-testid={`remove-${member.id}`}
                                  aria-label={`Remove ${member.email}`}
                                  className={`${iconActionClass} text-slate-500 hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600 dark:text-slate-400 dark:hover:border-slate-600/50 dark:hover:bg-slate-700/30 dark:hover:text-red-400`}
                                >
                                  <Trash2 size={14} />
                                </button>
                              </>
                            )}
                            {member.status === 'active' && (
                              <>
                                <button
                                  onClick={() => setEditMember(member)}
                                  disabled={actionLoading[member.id]}
                                  title="Edit"
                                  data-testid={`edit-${member.id}`}
                                  aria-label={`Edit ${member.email}`}
                                  className={`${iconActionClass} text-slate-500 hover:border-slate-300 hover:bg-slate-50 hover:text-slate-700 dark:text-slate-400 dark:hover:border-slate-600/50 dark:hover:bg-slate-700/30 dark:hover:text-slate-200`}
                                >
                                  <Pencil size={14} />
                                </button>
                                <button
                                  onClick={() => handleDeactivate(member.id)}
                                  disabled={actionLoading[member.id]}
                                  title="Deactivate"
                                  data-testid={`deactivate-${member.id}`}
                                  aria-label={`Deactivate ${member.email}`}
                                  className={`${iconActionClass} text-slate-500 hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600 dark:text-slate-400 dark:hover:border-slate-600/50 dark:hover:bg-slate-700/30 dark:hover:text-red-400`}
                                >
                                  <Ban size={14} />
                                </button>
                              </>
                            )}
                            {member.status === 'deactivated' && (
                              <>
                                <button
                                  onClick={() => handleReactivate(member.id)}
                                  disabled={actionLoading[member.id]}
                                  title="Reactivate"
                                  data-testid={`reactivate-${member.id}`}
                                  aria-label={`Reactivate ${member.email}`}
                                  className={`${iconActionClass} text-slate-500 hover:border-emerald-200 hover:bg-emerald-50 hover:text-emerald-600 dark:text-slate-400 dark:hover:border-slate-600/50 dark:hover:bg-slate-700/30 dark:hover:text-green-400`}
                                >
                                  <RotateCcw size={14} />
                                </button>
                                <button
                                  onClick={() => handleRemove(member.id)}
                                  disabled={actionLoading[member.id]}
                                  title="Remove"
                                  data-testid={`remove-${member.id}`}
                                  aria-label={`Remove ${member.email}`}
                                  className={`${iconActionClass} text-slate-500 hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600 dark:text-slate-400 dark:hover:border-slate-600/50 dark:hover:bg-slate-700/30 dark:hover:text-red-400`}
                                >
                                  <Trash2 size={14} />
                                </button>
                              </>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </>
        )}
      </div>

      {/* Pagination */}
      <GlassPagination
        currentPage={pagination.currentPage}
        totalPages={pagination.totalPages}
        totalItems={pagination.totalItems}
        itemsPerPage={pagination.itemsPerPage}
        onPageChange={pagination.setPage}
        onItemsPerPageChange={pagination.setItemsPerPage}
        itemLabel="members"
      />

      {/* Modals */}
      {showInviteModal && (
        <InviteTeamMemberModal
          onClose={() => setShowInviteModal(false)}
          onSuccess={() => {
            setShowInviteModal(false);
            fetchData();
          }}
        />
      )}

      {editMember && (
        <EditTeamMemberModal
          member={editMember}
          onClose={() => setEditMember(null)}
          onSuccess={() => {
            setEditMember(null);
            fetchData();
          }}
        />
      )}
    </div>
  );
}
