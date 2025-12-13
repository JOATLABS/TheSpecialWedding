'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Users,
  UserPlus,
  Search,
  MoreHorizontal,
  Shield,
  Calendar,
  Mail,
  Phone,
  Building2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Heart,
  Sparkles,
  TrendingUp,
  Eye,
  UserX,
  Trash2,
  RefreshCw,
  X
} from 'lucide-react';

interface Planner {
  id?: string;
  _id?: string;
  email: string;
  name: string;
  first_name?: string;
  last_name?: string;
  company_name?: string;
  phone?: string;
  role: string;
  is_active: boolean;
  is_suspended?: boolean;
  created_at?: string;
  wedding_count?: number;
  subscription_tier?: string;
  subscription_plan_id?: string;
  organization?: string;
}

interface InviteFormData {
  email: string;
  name: string;
  phone: string;
  organization: string;
}

export default function AdminUsersPage() {
  const { token } = useAdmin();
  const [planners, setPlanners] = useState<Planner[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'active' | 'suspended'>('all');
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteForm, setInviteForm] = useState<InviteFormData>({
    email: '',
    name: '',
    phone: '',
    organization: ''
  });
  const [actionMenuOpen, setActionMenuOpen] = useState<string | null>(null);

  const fetchPlanners = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    setError('');

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/users?role=wedding_planner`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch planners');
      }

      const data = await response.json();
      setPlanners(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Error fetching planners:', err);
      setError('Failed to load planners. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchPlanners();
  }, [fetchPlanners]);

  // Close action menu when clicking outside
  useEffect(() => {
    const handleClickOutside = () => setActionMenuOpen(null);
    if (actionMenuOpen) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [actionMenuOpen]);

  const handleInvitePlanner = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviteLoading(true);

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/users/invite`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...inviteForm,
          role: 'wedding_planner'
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to invite planner');
      }

      setShowInviteModal(false);
      setInviteForm({ email: '', name: '', phone: '', organization: '' });
      fetchPlanners();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to invite planner');
    } finally {
      setInviteLoading(false);
    }
  };

  const handleSuspendUser = async (userId: string) => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/users/${userId}/suspend`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) throw new Error('Failed to suspend user');

      fetchPlanners();
      setActionMenuOpen(null);
    } catch (err) {
      setError('Failed to suspend user');
    }
  };

  const handleActivateUser = async (userId: string) => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/users/${userId}/activate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) throw new Error('Failed to activate user');

      fetchPlanners();
      setActionMenuOpen(null);
    } catch (err) {
      setError('Failed to activate user');
    }
  };

  const handleDeleteUser = async (userId: string) => {
    if (!confirm('Are you sure you want to delete this planner? This action cannot be undone.')) {
      return;
    }

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/users/${userId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) throw new Error('Failed to delete user');

      fetchPlanners();
      setActionMenuOpen(null);
    } catch (err) {
      setError('Failed to delete user');
    }
  };

  // Filter planners based on search and status
  const filteredPlanners = planners.filter(planner => {
    const displayName = planner.name || `${planner.first_name || ''} ${planner.last_name || ''}`.trim() || planner.email;
    const matchesSearch =
      displayName?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      planner.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      planner.company_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      planner.organization?.toLowerCase().includes(searchTerm.toLowerCase());

    if (!matchesSearch) return false;

    switch (filterStatus) {
      case 'active':
        return planner.is_active && !planner.is_suspended;
      case 'suspended':
        return planner.is_suspended;
      default:
        return true;
    }
  });

  // Stats calculations
  const totalPlanners = planners.length;
  const activePlanners = planners.filter(p => p.is_active && !p.is_suspended).length;
  const suspendedPlanners = planners.filter(p => p.is_suspended).length;

  // Get display name for planner
  const getPlannerDisplayName = (planner: Planner) => {
    return planner.name || `${planner.first_name || ''} ${planner.last_name || ''}`.trim() || 'Unnamed Planner';
  };

  // Get initials for avatar
  const getInitials = (planner: Planner) => {
    const name = getPlannerDisplayName(planner);
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  // Get subscription badge styling
  const getSubscriptionStyle = (tier: string | undefined) => {
    switch (tier?.toLowerCase()) {
      case 'signature':
      case 'premium':
        return 'bg-gradient-to-r from-amber-500 to-yellow-400 text-white shadow-lg shadow-amber-500/20';
      case 'boutique':
      case 'pro':
        return 'bg-gradient-to-r from-violet-500 to-purple-500 text-white shadow-lg shadow-violet-500/20';
      case 'essential':
      case 'basic':
        return 'bg-gradient-to-r from-slate-500 to-slate-600 text-white';
      default:
        return 'bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300';
    }
  };

  return (
    <div className="min-h-screen">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Hero Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-8 md:p-10"
        >
          {/* Decorative elements */}
          <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-br from-primary-500/20 to-secondary-500/20 rounded-full blur-3xl" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-gradient-to-tr from-amber-500/10 to-rose-500/10 rounded-full blur-2xl" />

          <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-6">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-500 to-secondary-500 flex items-center justify-center shadow-lg shadow-primary-500/30">
                <Users className="w-8 h-8 text-white" />
              </div>
              <div>
                <h1 className="text-3xl md:text-4xl font-bold text-white">
                  Planner Management
                </h1>
                <p className="text-slate-400 mt-1 flex items-center gap-2">
                  <Sparkles className="w-4 h-4" />
                  Manage your wedding planning team
                </p>
              </div>
            </div>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => setShowInviteModal(true)}
              className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-primary-500 to-secondary-500 text-white rounded-xl font-semibold shadow-lg shadow-primary-500/30 hover:shadow-xl hover:shadow-primary-500/40 transition-all"
            >
              <UserPlus className="w-5 h-5" />
              Invite Planner
            </motion.button>
          </div>
        </motion.div>

        {/* Error Display */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="bg-red-500/10 border border-red-500/20 backdrop-blur-sm rounded-2xl p-4"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-red-500/20 flex items-center justify-center">
                  <AlertCircle className="w-5 h-5 text-red-400" />
                </div>
                <p className="text-red-300 flex-1">{error}</p>
                <button onClick={() => setError('')} className="text-red-400 hover:text-red-300">
                  <X className="w-5 h-5" />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="group relative overflow-hidden rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 p-6 hover:bg-white/10 transition-all"
          >
            <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-blue-500/20 to-cyan-500/20 rounded-full blur-2xl group-hover:scale-150 transition-transform" />
            <div className="relative flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-blue-500/30">
                <Users className="w-7 h-7 text-white" />
              </div>
              <div>
                <p className="text-sm text-slate-400 font-medium">Total Planners</p>
                <p className="text-4xl font-bold text-white">{totalPlanners}</p>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="group relative overflow-hidden rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 p-6 hover:bg-white/10 transition-all"
          >
            <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-emerald-500/20 to-green-500/20 rounded-full blur-2xl group-hover:scale-150 transition-transform" />
            <div className="relative flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-emerald-500 to-green-500 flex items-center justify-center shadow-lg shadow-emerald-500/30">
                <CheckCircle2 className="w-7 h-7 text-white" />
              </div>
              <div>
                <p className="text-sm text-slate-400 font-medium">Active</p>
                <p className="text-4xl font-bold text-emerald-400">{activePlanners}</p>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="group relative overflow-hidden rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 p-6 hover:bg-white/10 transition-all"
          >
            <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-amber-500/20 to-orange-500/20 rounded-full blur-2xl group-hover:scale-150 transition-transform" />
            <div className="relative flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center shadow-lg shadow-amber-500/30">
                <XCircle className="w-7 h-7 text-white" />
              </div>
              <div>
                <p className="text-sm text-slate-400 font-medium">Suspended</p>
                <p className="text-4xl font-bold text-amber-400">{suspendedPlanners}</p>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Filters & Search */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 p-6"
        >
          <div className="flex flex-col lg:flex-row gap-4 items-center justify-between">
            {/* Search */}
            <div className="relative w-full lg:w-96">
              <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                placeholder="Search by name, email, or company..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50 transition-all"
              />
            </div>

            {/* Filter Buttons */}
            <div className="flex items-center gap-2">
              <div className="flex bg-white/5 rounded-xl p-1 border border-white/10">
                {(['all', 'active', 'suspended'] as const).map((status) => (
                  <button
                    key={status}
                    onClick={() => setFilterStatus(status)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      filterStatus === status
                        ? status === 'active'
                          ? 'bg-emerald-500 text-white shadow-lg'
                          : status === 'suspended'
                          ? 'bg-amber-500 text-white shadow-lg'
                          : 'bg-white/20 text-white shadow-lg'
                        : 'text-slate-400 hover:text-white hover:bg-white/10'
                    }`}
                  >
                    {status.charAt(0).toUpperCase() + status.slice(1)}
                  </button>
                ))}
              </div>

              <button
                onClick={fetchPlanners}
                className="p-3 bg-white/5 border border-white/10 rounded-xl text-slate-400 hover:text-white hover:bg-white/10 transition-all"
                title="Refresh"
              >
                <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </motion.div>

        {/* Planners Grid/Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 overflow-hidden"
        >
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="w-16 h-16 rounded-full border-4 border-primary-500/30 border-t-primary-500 animate-spin mb-4" />
              <p className="text-slate-400">Loading planners...</p>
            </div>
          ) : filteredPlanners.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="w-20 h-20 rounded-full bg-slate-800 flex items-center justify-center mb-4">
                <Users className="w-10 h-10 text-slate-600" />
              </div>
              <p className="text-slate-400 mb-2">No planners found</p>
              <p className="text-slate-500 text-sm mb-6">Get started by inviting your first planner</p>
              <button
                onClick={() => setShowInviteModal(true)}
                className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-primary-500 to-secondary-500 text-white rounded-xl font-semibold"
              >
                <UserPlus className="w-5 h-5" />
                Invite Planner
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Planner
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Contact
                    </th>
                    <th className="px-6 py-4 text-center text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-4 text-center text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Weddings
                    </th>
                    <th className="px-6 py-4 text-center text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Plan
                    </th>
                    <th className="px-6 py-4 text-center text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Joined
                    </th>
                    <th className="px-6 py-4 text-right text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {filteredPlanners.map((planner, index) => {
                    const plannerId = planner.id || planner._id || '';
                    const displayName = getPlannerDisplayName(planner);
                    const initials = getInitials(planner);
                    const company = planner.company_name || planner.organization;

                    return (
                      <motion.tr
                        key={plannerId}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.05 }}
                        className="group hover:bg-white/5 transition-colors"
                      >
                        {/* Planner Info */}
                        <td className="px-6 py-5">
                          <div className="flex items-center gap-4">
                            <div className="relative">
                              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary-500 to-secondary-500 flex items-center justify-center text-white font-bold text-lg shadow-lg">
                                {initials}
                              </div>
                              {planner.is_active && !planner.is_suspended && (
                                <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-emerald-500 rounded-full border-2 border-slate-900" />
                              )}
                            </div>
                            <div>
                              <p className="font-semibold text-white group-hover:text-primary-400 transition-colors">
                                {displayName}
                              </p>
                              {company && (
                                <p className="text-sm text-slate-500 flex items-center gap-1.5 mt-0.5">
                                  <Building2 className="w-3.5 h-3.5" />
                                  {company}
                                </p>
                              )}
                            </div>
                          </div>
                        </td>

                        {/* Contact */}
                        <td className="px-6 py-5">
                          <div className="space-y-1.5">
                            <p className="text-sm text-slate-300 flex items-center gap-2">
                              <Mail className="w-4 h-4 text-slate-500" />
                              {planner.email}
                            </p>
                            {planner.phone && (
                              <p className="text-sm text-slate-400 flex items-center gap-2">
                                <Phone className="w-4 h-4 text-slate-500" />
                                {planner.phone}
                              </p>
                            )}
                          </div>
                        </td>

                        {/* Status */}
                        <td className="px-6 py-5 text-center">
                          {planner.is_suspended ? (
                            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30">
                              <XCircle className="w-3.5 h-3.5" />
                              Suspended
                            </span>
                          ) : planner.is_active ? (
                            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-slate-500/20 text-slate-400 border border-slate-500/30">
                              Inactive
                            </span>
                          )}
                        </td>

                        {/* Weddings */}
                        <td className="px-6 py-5 text-center">
                          <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10">
                            <Heart className="w-4 h-4 text-rose-400" />
                            <span className="font-semibold text-white">{planner.wedding_count || 0}</span>
                          </div>
                        </td>

                        {/* Subscription */}
                        <td className="px-6 py-5 text-center">
                          <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold ${getSubscriptionStyle(planner.subscription_tier || planner.subscription_plan_id)}`}>
                            <Shield className="w-3.5 h-3.5" />
                            {planner.subscription_tier || planner.subscription_plan_id || 'Free'}
                          </span>
                        </td>

                        {/* Joined Date */}
                        <td className="px-6 py-5 text-center">
                          <div className="flex items-center justify-center gap-1.5 text-sm text-slate-400">
                            <Calendar className="w-4 h-4" />
                            {planner.created_at
                              ? new Date(planner.created_at).toLocaleDateString('en-US', {
                                  month: 'short',
                                  day: 'numeric',
                                  year: 'numeric'
                                })
                              : 'N/A'
                            }
                          </div>
                        </td>

                        {/* Actions */}
                        <td className="px-6 py-5 text-right">
                          <div className="relative inline-block">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setActionMenuOpen(actionMenuOpen === plannerId ? null : plannerId);
                              }}
                              className="p-2 rounded-lg bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition-all"
                            >
                              <MoreHorizontal className="w-5 h-5" />
                            </button>

                            <AnimatePresence>
                              {actionMenuOpen === plannerId && (
                                <motion.div
                                  initial={{ opacity: 0, scale: 0.95, y: -10 }}
                                  animate={{ opacity: 1, scale: 1, y: 0 }}
                                  exit={{ opacity: 0, scale: 0.95, y: -10 }}
                                  className="absolute right-0 mt-2 w-52 bg-slate-800 rounded-xl shadow-2xl border border-white/10 overflow-hidden z-50"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <div className="p-1">
                                    <button
                                      className="w-full flex items-center gap-3 px-4 py-3 text-sm text-slate-300 hover:bg-white/10 rounded-lg transition-colors"
                                    >
                                      <Eye className="w-4 h-4" />
                                      View Details
                                    </button>

                                    {planner.is_suspended ? (
                                      <button
                                        onClick={() => handleActivateUser(plannerId)}
                                        className="w-full flex items-center gap-3 px-4 py-3 text-sm text-emerald-400 hover:bg-emerald-500/10 rounded-lg transition-colors"
                                      >
                                        <CheckCircle2 className="w-4 h-4" />
                                        Activate User
                                      </button>
                                    ) : (
                                      <button
                                        onClick={() => handleSuspendUser(plannerId)}
                                        className="w-full flex items-center gap-3 px-4 py-3 text-sm text-amber-400 hover:bg-amber-500/10 rounded-lg transition-colors"
                                      >
                                        <UserX className="w-4 h-4" />
                                        Suspend User
                                      </button>
                                    )}

                                    <div className="my-1 border-t border-white/10" />

                                    <button
                                      onClick={() => handleDeleteUser(plannerId)}
                                      className="w-full flex items-center gap-3 px-4 py-3 text-sm text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                                    >
                                      <Trash2 className="w-4 h-4" />
                                      Delete User
                                    </button>
                                  </div>
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </div>
                        </td>
                      </motion.tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Table Footer */}
          {filteredPlanners.length > 0 && (
            <div className="px-6 py-4 border-t border-white/10 flex items-center justify-between">
              <p className="text-sm text-slate-500">
                Showing <span className="text-white font-medium">{filteredPlanners.length}</span> of{' '}
                <span className="text-white font-medium">{totalPlanners}</span> planners
              </p>
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                {activePlanners} active this period
              </div>
            </div>
          )}
        </motion.div>

        {/* Invite Modal */}
        <AnimatePresence>
          {showInviteModal && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50"
              onClick={() => setShowInviteModal(false)}
            >
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 20 }}
                className="bg-slate-900 border border-white/10 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden"
                onClick={(e) => e.stopPropagation()}
              >
                {/* Modal Header */}
                <div className="relative overflow-hidden px-6 pt-6 pb-4">
                  <div className="absolute top-0 right-0 w-40 h-40 bg-gradient-to-br from-primary-500/20 to-secondary-500/20 rounded-full blur-2xl" />
                  <div className="relative flex items-center gap-4">
                    <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-primary-500 to-secondary-500 flex items-center justify-center shadow-lg shadow-primary-500/30">
                      <UserPlus className="w-7 h-7 text-white" />
                    </div>
                    <div>
                      <h2 className="text-2xl font-bold text-white">Invite Planner</h2>
                      <p className="text-slate-400 text-sm">Send an invitation to join your platform</p>
                    </div>
                  </div>
                </div>

                {/* Modal Body */}
                <form onSubmit={handleInvitePlanner} className="p-6 pt-2 space-y-5">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      Full Name <span className="text-red-400">*</span>
                    </label>
                    <input
                      type="text"
                      value={inviteForm.name}
                      onChange={(e) => setInviteForm({ ...inviteForm, name: e.target.value })}
                      className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50 transition-all"
                      placeholder="Jane Smith"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      Email Address <span className="text-red-400">*</span>
                    </label>
                    <input
                      type="email"
                      value={inviteForm.email}
                      onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
                      className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50 transition-all"
                      placeholder="jane@company.com"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      Phone Number
                    </label>
                    <input
                      type="tel"
                      value={inviteForm.phone}
                      onChange={(e) => setInviteForm({ ...inviteForm, phone: e.target.value })}
                      className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50 transition-all"
                      placeholder="+1 (555) 000-0000"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      Company / Organization
                    </label>
                    <input
                      type="text"
                      value={inviteForm.organization}
                      onChange={(e) => setInviteForm({ ...inviteForm, organization: e.target.value })}
                      className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50 transition-all"
                      placeholder="Wedding Planning Co."
                    />
                  </div>

                  <div className="flex gap-3 pt-4">
                    <button
                      type="button"
                      onClick={() => {
                        setShowInviteModal(false);
                        setInviteForm({ email: '', name: '', phone: '', organization: '' });
                      }}
                      className="flex-1 px-4 py-3 bg-white/5 border border-white/10 text-slate-300 rounded-xl font-medium hover:bg-white/10 transition-all"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={inviteLoading}
                      className="flex-1 px-4 py-3 bg-gradient-to-r from-primary-500 to-secondary-500 text-white rounded-xl font-semibold shadow-lg shadow-primary-500/30 hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
                    >
                      {inviteLoading ? (
                        <>
                          <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                          Sending...
                        </>
                      ) : (
                        <>
                          <Mail className="w-5 h-5" />
                          Send Invite
                        </>
                      )}
                    </button>
                  </div>
                </form>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}