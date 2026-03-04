'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';
import { toast } from 'sonner';
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
  Shield,
  CheckCircle2,
  Clock,
  XCircle,
} from 'lucide-react';
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
  assigned_wedding_names?: string[];
  created_at: string;
  activated_at?: string;
  last_active_at?: string;
  user_id?: string;
}

interface SeatsInfo {
  total_seats: number;
  used_seats: number;
  available_seats: number;
  plan_name: string;
}

export default function TeamManagementPage() {
  const { token } = useAdmin();
  const baseUrl = getApiBaseUrl();

  const [members, setMembers] = useState<TeamMember[]>([]);
  const [seatsInfo, setSeatsInfo] = useState<SeatsInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'pending' | 'deactivated'>('all');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

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
        fetch(`${baseUrl}/admin/team/members`, { headers, cache: 'no-store' }),
        fetch(`${baseUrl}/admin/team/seats`, { headers, cache: 'no-store' }),
      ]);

      if (membersRes.ok) {
        const data = await membersRes.json();
        setMembers(data);
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
  }, [token, baseUrl]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleResendInvite = async (memberId: string) => {
    setActionLoading(memberId);
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
      setActionLoading(null);
    }
  };

  const handleDeactivate = async (memberId: string) => {
    if (!confirm('Are you sure you want to deactivate this team member? They will lose access immediately.')) return;
    setActionLoading(memberId);
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
      toast.error(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReactivate = async (memberId: string) => {
    setActionLoading(memberId);
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
      toast.error(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRemove = async (memberId: string) => {
    if (!confirm('Are you sure you want to remove this team member? This action cannot be undone.')) return;
    setActionLoading(memberId);
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
      fetchData();
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  // Filter members
  const filteredMembers = members.filter((m) => {
    const matchesSearch =
      !searchQuery ||
      m.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (m.first_name && m.first_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (m.last_name && m.last_name.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesStatus = statusFilter === 'all' || m.status === statusFilter;

    return matchesSearch && matchesStatus;
  });

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
    admin: 'bg-wedding-rose/15 text-wedding-rose',
    editor: 'bg-wedding-sage/15 text-wedding-sage',
    viewer: 'bg-slate-500/15 text-slate-400',
  };

  const statusDotColors: Record<string, string> = {
    active: 'bg-green-400',
    pending: 'bg-wedding-gold',
    deactivated: 'bg-red-400',
  };

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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-wedding-rose mx-auto" />
          <p className="mt-3 text-slate-400 text-sm">Loading team...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-100">Team Management</h1>
          <p className="text-sm text-slate-400 mt-1">Manage your team members, roles, and permissions</p>
        </div>
        <div className="flex items-center gap-3">
          {seatsInfo && (
            <div className="flex items-center gap-2 bg-wedding-rose/10 border border-wedding-rose/20 px-4 py-2 rounded-xl text-sm text-wedding-rose">
              <Users size={16} />
              <span>
                <strong className="text-lg">{seatsInfo.used_seats}</strong> / {seatsInfo.total_seats} seats
              </span>
            </div>
          )}
          <button
            onClick={() => setShowInviteModal(true)}
            disabled={seatsInfo ? seatsInfo.available_seats <= 0 : false}
            className="flex items-center gap-2 bg-gradient-to-r from-wedding-rose to-[#c48e8e] text-slate-900 font-semibold px-5 py-2.5 rounded-xl text-sm hover:shadow-lg hover:shadow-wedding-rose/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <UserPlus size={16} />
            Invite Team Member
          </button>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-slate-800/50 border border-slate-700/30 rounded-2xl p-5 backdrop-blur-sm">
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-1.5">Total Members</p>
          <p className="text-2xl font-bold text-wedding-rose">{members.length}</p>
        </div>
        <div className="bg-slate-800/50 border border-slate-700/30 rounded-2xl p-5 backdrop-blur-sm">
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-1.5">Active</p>
          <p className="text-2xl font-bold text-wedding-sage">{activeCount}</p>
        </div>
        <div className="bg-slate-800/50 border border-slate-700/30 rounded-2xl p-5 backdrop-blur-sm">
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-1.5">Pending Invites</p>
          <p className="text-2xl font-bold text-wedding-gold">{pendingCount}</p>
        </div>
        <div className="bg-slate-800/50 border border-slate-700/30 rounded-2xl p-5 backdrop-blur-sm">
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-1.5">Seats Remaining</p>
          <p className="text-2xl font-bold text-slate-400">{seatsInfo ? seatsInfo.available_seats : '—'}</p>
        </div>
      </div>

      {/* Table */}
      <div className="bg-slate-800/50 border border-slate-700/30 rounded-2xl backdrop-blur-sm overflow-hidden">
        {/* Table header bar */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 border-b border-slate-700/30">
          <div className="flex items-center gap-3">
            <h2 className="font-semibold text-slate-200">Team Members</h2>
            <div className="flex bg-slate-900/60 rounded-lg p-0.5 border border-slate-700/30">
              {(['all', 'active', 'pending', 'deactivated'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setStatusFilter(tab)}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-colors capitalize ${
                    statusFilter === tab
                      ? 'bg-wedding-rose/15 text-wedding-rose'
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2 bg-slate-900/60 border border-slate-700/30 rounded-lg px-3 py-2">
            <Search size={14} className="text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search members..."
              className="bg-transparent border-none text-sm text-slate-200 placeholder:text-slate-600 outline-none w-48"
            />
          </div>
        </div>

        {/* Table content */}
        {filteredMembers.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Users className="w-10 h-10 text-slate-600 mb-3" />
            <p className="text-slate-400 text-sm">
              {members.length === 0 ? 'No team members yet. Invite your first teammate!' : 'No members match your filters.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-700/30">
                  <th className="text-left px-5 py-3 text-xs uppercase tracking-wider text-slate-500 font-medium">Member</th>
                  <th className="text-left px-5 py-3 text-xs uppercase tracking-wider text-slate-500 font-medium">Role</th>
                  <th className="text-left px-5 py-3 text-xs uppercase tracking-wider text-slate-500 font-medium">Status</th>
                  <th className="text-left px-5 py-3 text-xs uppercase tracking-wider text-slate-500 font-medium">Wedding Access</th>
                  <th className="text-left px-5 py-3 text-xs uppercase tracking-wider text-slate-500 font-medium">Last Active</th>
                  <th className="text-left px-5 py-3 text-xs uppercase tracking-wider text-slate-500 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredMembers.map((member) => (
                  <tr key={member.id} className="border-b border-slate-700/10 hover:bg-slate-700/10 transition-colors">
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
                          <p className="text-sm font-medium text-slate-200">
                            {member.first_name && member.last_name
                              ? `${member.first_name} ${member.last_name}`
                              : '—'}
                          </p>
                          <p className="text-xs text-slate-500">{member.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${
                          roleStyles[member.role] || 'bg-slate-500/15 text-slate-400'
                        }`}
                      >
                        {member.role.charAt(0).toUpperCase() + member.role.slice(1)}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span className="inline-flex items-center gap-1.5 text-sm">
                        <span className={`w-2 h-2 rounded-full ${statusDotColors[member.status] || 'bg-slate-500'}`} />
                        <span className="text-slate-300 capitalize">{member.status}</span>
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-sm text-slate-400">
                        {member.wedding_access === 'all' ? (
                          <><strong className="text-slate-200">All</strong> weddings</>
                        ) : (
                          <><strong className="text-slate-200">{member.assigned_wedding_ids.length}</strong> assigned</>
                        )}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-xs text-slate-500">{formatLastActive(member)}</span>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-1.5">
                        {actionLoading === member.id ? (
                          <Loader2 size={16} className="animate-spin text-slate-400" />
                        ) : (
                          <>
                            {member.status === 'pending' && (
                              <>
                                <button
                                  onClick={() => handleResendInvite(member.id)}
                                  title="Resend Invite"
                                  className="w-8 h-8 rounded-lg border border-slate-700/50 bg-slate-900/40 flex items-center justify-center text-wedding-gold hover:bg-slate-700/30 transition-colors"
                                >
                                  <Send size={14} />
                                </button>
                                <button
                                  onClick={() => handleRemove(member.id)}
                                  title="Remove"
                                  className="w-8 h-8 rounded-lg border border-slate-700/50 bg-slate-900/40 flex items-center justify-center text-slate-400 hover:text-red-400 hover:bg-slate-700/30 transition-colors"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </>
                            )}
                            {member.status === 'active' && (
                              <>
                                <button
                                  onClick={() => setEditMember(member)}
                                  title="Edit"
                                  className="w-8 h-8 rounded-lg border border-slate-700/50 bg-slate-900/40 flex items-center justify-center text-slate-400 hover:text-slate-200 hover:bg-slate-700/30 transition-colors"
                                >
                                  <Pencil size={14} />
                                </button>
                                <button
                                  onClick={() => handleDeactivate(member.id)}
                                  title="Deactivate"
                                  className="w-8 h-8 rounded-lg border border-slate-700/50 bg-slate-900/40 flex items-center justify-center text-slate-400 hover:text-red-400 hover:bg-slate-700/30 transition-colors"
                                >
                                  <Ban size={14} />
                                </button>
                              </>
                            )}
                            {member.status === 'deactivated' && (
                              <>
                                <button
                                  onClick={() => handleReactivate(member.id)}
                                  title="Reactivate"
                                  className="w-8 h-8 rounded-lg border border-slate-700/50 bg-slate-900/40 flex items-center justify-center text-slate-400 hover:text-green-400 hover:bg-slate-700/30 transition-colors"
                                >
                                  <RotateCcw size={14} />
                                </button>
                                <button
                                  onClick={() => handleRemove(member.id)}
                                  title="Remove"
                                  className="w-8 h-8 rounded-lg border border-slate-700/50 bg-slate-900/40 flex items-center justify-center text-slate-400 hover:text-red-400 hover:bg-slate-700/30 transition-colors"
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
        )}
      </div>

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
