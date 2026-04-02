'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { toast } from 'sonner';
import { getApiBaseUrl } from '@/utils/env';
import { useAdmin } from '@/contexts/AdminContext';
import { motion, AnimatePresence } from 'framer-motion';
import { formatAdminTimestamp, formatAdminDate, DEFAULT_TIMEZONE } from '@/utils/dateFormat';
import PageHeader from '../components/PageHeader';
import { usePagination } from '@/admin/hooks/usePagination';
import { GlassPagination } from '@/admin/components/ui/glass/GlassPagination';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
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
  TrendingUp,
  Eye,
  UserX,
  Trash2,
  RefreshCw,
  X,
  Clock,
  CreditCard,
  Gift,
  Send,
  Ban,
  CheckCircle,
  AlertTriangle,
  type LucideIcon
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
  plan_id?: string;
  organization?: string;
  timezone?: string;
}

interface SubscriptionPlan {
  _id: string;
  name: string;
  description?: string;
  price_monthly: number;
  is_active: boolean;
}

interface InviteFormData {
  email: string;
  name: string;
  phone: string;
  organization: string;
  plan_id: string;
  trial_days: number;
  trial_end_behavior: 'pause' | 'cancel';
  admin_notes: string;
}

interface PendingInvitation {
  _id: string;
  email: string;
  invite_data: {
    plan_id?: string;
    trial_days?: number;
    company_name?: string;
    admin_notes?: string;
  };
  invited_by: string;
  created_at: string;
  expires_at: string;
  status: 'pending' | 'completed' | 'expired' | 'cancelled';
  email_status: 'pending' | 'sent' | 'failed';
  resend_count: number;
  plan_name?: string;
}

interface InvitationStats {
  pending: number;
  completed: number;
  expired: number;
  cancelled: number;
  total: number;
}

interface PlannerDetail extends Planner {
  subscription_status?: string;
  trial_end_date?: string;
  updated_at?: string;
  last_login?: string;
  email_verified?: boolean;
  max_weddings?: number;
  support_phone?: string;
}

interface DirectorySummary {
  total: number;
  active: number;
  suspended: number;
  inactive: number;
}

interface UserDirectoryResponse {
  users: Planner[];
  total: number;
  page: number;
  pages: number;
  limit: number;
  summary?: DirectorySummary;
  role_breakdown?: Record<string, number>;
}

type RoleScope = 'all' | 'wedding_planner' | 'team_member' | 'ROOT_ADMIN' | 'vendor' | 'advertising_vendor';

const ROLE_LABELS: Record<string, string> = {
  all: 'All accounts',
  wedding_planner: 'Planners',
  team_member: 'Team members',
  ROOT_ADMIN: 'Root admins',
  vendor: 'Vendors',
  advertising_vendor: 'Ad vendors',
};

const ROLE_DESCRIPTIONS: Record<string, string> = {
  all: 'Review every authenticated account on the platform in one place.',
  wedding_planner: 'Manage planner accounts, plan access, and account health.',
  team_member: 'Review scoped staff accounts attached to planner teams.',
  ROOT_ADMIN: 'Review platform owner accounts and protected admin access.',
  vendor: 'Review vendor accounts provisioned inside the main platform.',
  advertising_vendor: 'Review advertising portal vendor accounts and access.',
};

const CORE_ROLE_SCOPES: RoleScope[] = ['all', 'wedding_planner', 'team_member', 'ROOT_ADMIN'];

function normalizeRoleScope(value: string | null): RoleScope {
  if (!value || value === 'all') return 'all';
  if (value === 'wedding_planner' || value === 'team_member' || value === 'ROOT_ADMIN' || value === 'vendor' || value === 'advertising_vendor') {
    return value;
  }
  return 'all';
}

function formatRoleLabel(role: string): string {
  return ROLE_LABELS[role] || role.replace(/_/g, ' ');
}

const PLANNER_STAT_CARD_TONES: Record<
  'blue' | 'emerald' | 'amber' | 'violet',
  {
    iconWrapper: string;
    icon: string;
    value: string;
    helper: string;
  }
> = {
  blue: {
    iconWrapper: 'bg-blue-100 dark:bg-blue-900/30',
    icon: 'text-blue-600 dark:text-blue-400',
    value: 'text-slate-900 dark:text-white',
    helper: 'text-blue-600 dark:text-blue-400',
  },
  emerald: {
    iconWrapper: 'bg-emerald-100 dark:bg-emerald-900/30',
    icon: 'text-emerald-600 dark:text-emerald-400',
    value: 'text-emerald-600 dark:text-emerald-400',
    helper: 'text-emerald-600 dark:text-emerald-400',
  },
  amber: {
    iconWrapper: 'bg-amber-100 dark:bg-amber-900/30',
    icon: 'text-amber-600 dark:text-amber-400',
    value: 'text-amber-600 dark:text-amber-400',
    helper: 'text-amber-600 dark:text-amber-400',
  },
  violet: {
    iconWrapper: 'bg-violet-100 dark:bg-violet-900/30',
    icon: 'text-violet-600 dark:text-violet-400',
    value: 'text-violet-600 dark:text-violet-400',
    helper: 'text-violet-600 dark:text-violet-400',
  },
};

function PlannerMetricCard({
  label,
  value,
  helper,
  icon: Icon,
  tone,
  onClick,
}: {
  label: string;
  value: string | number;
  helper: string;
  icon: LucideIcon;
  tone: keyof typeof PLANNER_STAT_CARD_TONES;
  onClick?: () => void;
}) {
  const toneClasses = PLANNER_STAT_CARD_TONES[tone];
  const cardContent = (
    <div className="flex items-start justify-between gap-4">
      <div className="space-y-2">
        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{label}</p>
        <p className={`text-3xl font-semibold ${toneClasses.value}`}>{value}</p>
        <p className={`text-xs font-medium ${toneClasses.helper}`}>{helper}</p>
      </div>
      <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${toneClasses.iconWrapper}`}>
        <Icon className={`h-6 w-6 ${toneClasses.icon}`} />
      </div>
    </div>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="w-full appearance-none border-0 bg-transparent p-0 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-wedding-rose/40 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-950"
      >
        <Card className="h-full p-5 transition-shadow hover:shadow-xl">
          {cardContent}
        </Card>
      </button>
    );
  }

  return <Card className="h-full p-5">{cardContent}</Card>;
}

export default function AdminUsersPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { token, userProfile } = useAdmin();
  const [planners, setPlanners] = useState<Planner[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'active' | 'suspended'>('all');
  const [roleScope, setRoleScope] = useState<RoleScope>(() => normalizeRoleScope(searchParams.get('role')));
  const [directorySummary, setDirectorySummary] = useState<DirectorySummary>({
    total: 0,
    active: 0,
    suspended: 0,
    inactive: 0,
  });
  const [roleBreakdown, setRoleBreakdown] = useState<Record<string, number>>({});
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [showPlannerDetailModal, setShowPlannerDetailModal] = useState(false);
  const [plannerDetail, setPlannerDetail] = useState<PlannerDetail | null>(null);
  const [plannerDetailLoading, setPlannerDetailLoading] = useState(false);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteForm, setInviteForm] = useState<InviteFormData>({
    email: '',
    name: '',
    phone: '',
    organization: '',
    plan_id: '',
    trial_days: 14,
    trial_end_behavior: 'pause',
    admin_notes: ''
  });
  const [actionMenuOpen, setActionMenuOpen] = useState<string | null>(null);
  const [availablePlans, setAvailablePlans] = useState<SubscriptionPlan[]>([]);
  const [defaultTrialDays, setDefaultTrialDays] = useState<number>(14); // Fallback, fetched from SAAS config

  // Pending invitations state
  const [pendingInvitations, setPendingInvitations] = useState<PendingInvitation[]>([]);
  const [invitationStats, setInvitationStats] = useState<InvitationStats>({ pending: 0, completed: 0, expired: 0, cancelled: 0, total: 0 });
  const [showPendingInvitations, setShowPendingInvitations] = useState(true);
  const [resendingId, setResendingId] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const [successToast, setSuccessToast] = useState<{ message: string; emailStatus?: string } | null>(null);

  const pagination = usePagination({ initialItemsPerPage: 50 });
  const {
    currentPage,
    itemsPerPage,
    setTotalItems: setPaginationTotalItems,
  } = pagination;

  const buildInviteForm = useCallback((): InviteFormData => ({
    email: '',
    name: '',
    phone: '',
    organization: '',
    plan_id: availablePlans[0]?._id || '',
    trial_days: defaultTrialDays,
    trial_end_behavior: 'pause',
    admin_notes: ''
  }), [availablePlans, defaultTrialDays]);

  // Access control - ROOT ADMIN only
  useEffect(() => {
    if (userProfile && !userProfile.is_root_admin) {
      router.push('/admin/planner');
    }
  }, [userProfile, router]);

  useEffect(() => {
    const nextRoleScope = normalizeRoleScope(searchParams.get('role'));
    setRoleScope((current) => (current === nextRoleScope ? current : nextRoleScope));
  }, [searchParams]);

  const selectedRoleLabel = formatRoleLabel(roleScope);
  const pageTitle = roleScope === 'all' ? 'Account Management' : `${selectedRoleLabel} Directory`;
  const pageDescription = ROLE_DESCRIPTIONS[roleScope] || ROLE_DESCRIPTIONS.all;
  const tableTitle = roleScope === 'all' ? 'Account directory' : `${selectedRoleLabel} directory`;
  const emptyStateLabel = roleScope === 'all' ? 'accounts' : selectedRoleLabel.toLowerCase();
  const inviteButtonLabel = 'Invite Planner';
  const canInvitePlanners = roleScope === 'all' || roleScope === 'wedding_planner';

  const fetchPlanners = useCallback(async () => {
    if (!token) return;

    setLoading(true);
    setError('');

    try {
      const baseUrl = getApiBaseUrl();
      const params = new URLSearchParams({
        page: String(currentPage),
        limit: String(itemsPerPage),
      });

      const trimmedSearch = searchTerm.trim();
      if (roleScope !== 'all') {
        params.set('role', roleScope);
      }
      if (filterStatus !== 'all') {
        params.set('status', filterStatus);
      }
      if (trimmedSearch) {
        params.set('search', trimmedSearch);
      }

      const response = await fetch(`${baseUrl}/users?${params.toString()}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch accounts');
      }

      const data = (await response.json()) as UserDirectoryResponse;
      const users = Array.isArray(data.users) ? data.users : [];
      setPlanners(users);
      setPaginationTotalItems(data.total || users.length);
      setDirectorySummary(data.summary || {
        total: users.length,
        active: users.filter((user) => user.is_active && !user.is_suspended).length,
        suspended: users.filter((user) => user.is_suspended).length,
        inactive: users.filter((user) => !user.is_active && !user.is_suspended).length,
      });
      setRoleBreakdown(data.role_breakdown || {});
    } catch (err) {
      console.error('Error fetching accounts:', err);
      setError('Failed to load accounts. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [token, currentPage, itemsPerPage, setPaginationTotalItems, roleScope, filterStatus, searchTerm]);

  const fetchTrialSettings = useCallback(async () => {
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/saas/trial-settings`);

      if (response.ok) {
        const data = await response.json();
        const trialDays = data.default_trial_days ?? 30;
        setDefaultTrialDays(trialDays);
      }
    } catch (err) {
      console.error('Error fetching trial settings:', err);
      // Keep fallback default of 14
    }
  }, []);

  const fetchPlans = useCallback(async () => {
    if (!token) return;

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/subscription-plans`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch plans');
      }

      const data = await response.json();
      // Filter to only active plans
      const activePlans = Array.isArray(data)
        ? data.filter((plan: SubscriptionPlan) => plan.is_active)
        : [];
      setAvailablePlans(activePlans);

      // Set default plan_id to first available plan if not set
      if (activePlans.length > 0 && !inviteForm.plan_id) {
        setInviteForm(prev => ({ ...prev, plan_id: activePlans[0]._id }));
      }
    } catch (err) {
      console.error('Error fetching plans:', err);
    }
  }, [token, inviteForm.plan_id]);

  const fetchPendingInvitations = useCallback(async () => {
    if (!token) return;

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/invitations?status=pending&limit=50`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        toast.error('Failed to load invitations');
        return;
      }

      const data = await response.json();
      setPendingInvitations(data.invitations || []);
    } catch (err) {
      console.error('Error fetching pending invitations:', err);
    }
  }, [token]);

  const fetchInvitationStats = useCallback(async () => {
    if (!token) return;

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/invitations/stats`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        toast.error('Failed to load invitations');
        return;
      }

      const data = await response.json();
      setInvitationStats(data);
    } catch (err) {
      console.error('Error fetching invitation stats:', err);
    }
  }, [token]);

  const handleResendInvitation = async (invitationId: string) => {
    setResendingId(invitationId);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/invitations/${invitationId}/resend`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to resend invitation');
      }

      const result = await response.json();
      setSuccessToast({
        message: result.message || 'Invitation resent successfully',
        emailStatus: 'sent'
      });

      // Refresh data
      fetchPendingInvitations();
      fetchInvitationStats();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resend invitation');
    } finally {
      setResendingId(null);
    }
  };

  const handleCancelInvitation = async (invitationId: string) => {
    if (!confirm('Are you sure you want to cancel this invitation?')) return;

    setCancellingId(invitationId);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/invitations/${invitationId}/cancel`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ reason: 'Cancelled by admin' }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to cancel invitation');
      }

      setSuccessToast({
        message: 'Invitation cancelled successfully',
      });

      // Refresh data
      fetchPendingInvitations();
      fetchInvitationStats();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel invitation');
    } finally {
      setCancellingId(null);
    }
  };

  useEffect(() => {
    fetchPlanners();
    fetchPlans();
    fetchTrialSettings();
    fetchPendingInvitations();
    fetchInvitationStats();
  }, [fetchPlanners, fetchPlans, fetchTrialSettings, fetchPendingInvitations, fetchInvitationStats]);

  // Auto-hide success toast
  useEffect(() => {
    if (successToast) {
      const timer = setTimeout(() => setSuccessToast(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [successToast]);

  // Close action menu when clicking outside
  useEffect(() => {
    const handleClickOutside = () => setActionMenuOpen(null);
    if (actionMenuOpen) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [actionMenuOpen]);

  // Reset to page 1 when search or filter changes
  useEffect(() => {
    pagination.setPage(1);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchTerm, filterStatus, roleScope]);

  const handleInvitePlanner = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    setInviteLoading(true);

    try {
      const baseUrl = getApiBaseUrl();

      // Build request body with proper field names for backend
      const requestBody = {
        email: inviteForm.email,
        role: 'wedding_planner',
        company_name: inviteForm.organization || inviteForm.name,
        plan_id: inviteForm.plan_id || undefined,
        trial_days: inviteForm.trial_days,
        trial_end_behavior: inviteForm.trial_end_behavior,
        admin_notes: inviteForm.admin_notes || undefined
      };

      const response = await fetch(`${baseUrl}/users/invite`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to invite planner');
      }

      const result = await response.json();

      // Show success message with trial info
      const successMessage = result.trial_days > 0
        ? `Invitation sent to ${inviteForm.email} with ${result.trial_days}-day trial`
        : `Invitation sent to ${inviteForm.email}`;

      setShowInviteModal(false);
      setInviteForm(buildInviteForm());

      // Show success toast with email status
      setSuccessToast({
        message: successMessage,
        emailStatus: result.email_status || 'sent'
      });

      // Refresh all data
      fetchPlanners();
      fetchPendingInvitations();
      fetchInvitationStats();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to invite planner');
    } finally {
      setInviteLoading(false);
    }
  }, [buildInviteForm, fetchPendingInvitations, fetchPlanners, fetchInvitationStats, inviteForm.admin_notes, inviteForm.email, inviteForm.name, inviteForm.organization, inviteForm.plan_id, inviteForm.trial_days, inviteForm.trial_end_behavior, token]);

  const openInviteModal = useCallback(() => {
    setInviteForm(buildInviteForm());
    setShowInviteModal(true);
  }, [buildInviteForm]);

  const handleSuspendUser = async (userId: string) => {
    try {
      const baseUrl = getApiBaseUrl();
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
      const baseUrl = getApiBaseUrl();
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
    if (!confirm('Are you sure you want to delete this account? This action cannot be undone.')) {
      return;
    }

    try {
      const baseUrl = getApiBaseUrl();
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

  const handleViewPlannerDetails = useCallback(async (planner: Planner) => {
    if (!token) return;

      const plannerId = planner.id || planner._id;
      if (!plannerId) {
      toast.error('Account ID is missing for this record.');
      return;
    }

    setActionMenuOpen(null);
    setPlannerDetail({
      ...planner,
      id: plannerId,
      company_name: planner.company_name || planner.organization,
    });
    setShowPlannerDetailModal(true);
    setPlannerDetailLoading(true);

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/users/${plannerId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to load account details');
      }

      const detail = await response.json();
      setPlannerDetail({
        ...planner,
        ...detail,
        id: detail.id || detail._id || plannerId,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load account details';
      toast.error(message);
    } finally {
      setPlannerDetailLoading(false);
    }
  }, [token]);

  const filteredPlanners = planners;

  const totalPlanners = directorySummary.total;
  const activePlanners = directorySummary.active;
  const suspendedPlanners = directorySummary.suspended;

  const roleScopeOptions = useMemo(() => {
    const knownRoles = CORE_ROLE_SCOPES.filter(
      (scope) => scope === 'all' || roleBreakdown[scope] > 0 || roleScope === scope
    );
    const dynamicRoles = Object.keys(roleBreakdown)
      .filter((role) => !CORE_ROLE_SCOPES.includes(role as RoleScope) && role !== 'unknown')
      .sort((left, right) => (roleBreakdown[right] || 0) - (roleBreakdown[left] || 0));

    return [...knownRoles, ...dynamicRoles];
  }, [roleBreakdown, roleScope]);

  const updateRoleScope = useCallback((nextScope: RoleScope | string) => {
    const normalizedScope = normalizeRoleScope(nextScope);
    setRoleScope(normalizedScope);
    pagination.setPage(1);
    const params = new URLSearchParams(searchParams.toString());
    if (normalizedScope === 'all') {
      params.delete('role');
    } else {
      params.set('role', normalizedScope);
    }

    const nextQuery = params.toString();
    router.replace(nextQuery ? `/admin/users?${nextQuery}` : '/admin/users');
  }, [pagination, router, searchParams]);

  const canManageAccount = useCallback((account: Planner) => {
    return account.role !== 'ROOT_ADMIN' && account.email !== userProfile?.email;
  }, [userProfile?.email]);

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

  const dashboardPanelSubtleClass =
    'rounded-xl border border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/70';
  const dashboardInputClass =
    'w-full rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-slate-900 placeholder-slate-400 shadow-sm transition-colors focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/20 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:placeholder-slate-400';
  const dashboardSecondaryButtonClass =
    'rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-900 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600 dark:hover:text-white';
  const dashboardPrimaryButtonClass =
    'rounded-lg bg-wedding-rose px-4 py-2.5 text-white shadow-sm transition-colors hover:bg-wedding-gold';
  const dashboardMutedTextClass = 'text-slate-500 dark:text-slate-400';
  const plannerTimezone = plannerDetail?.timezone || DEFAULT_TIMEZONE;
  const plannerStatusLabel = plannerDetail?.is_suspended
    ? 'Suspended'
    : plannerDetail?.is_active
      ? 'Active'
      : 'Inactive';

  return (
    <div className="space-y-6">
      <PageHeader
        title={pageTitle}
        description={pageDescription}
      >
        {canInvitePlanners && (
          <Button
            onClick={openInviteModal}
            className="gap-2"
          >
            <UserPlus className="w-5 h-5" />
            {inviteButtonLabel}
          </Button>
        )}
      </PageHeader>

      <div>
        {/* Success Toast */}
        <AnimatePresence>
          {successToast && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="fixed top-4 right-4 z-50 max-w-md rounded-2xl border border-emerald-200 bg-emerald-50 p-4 shadow-lg shadow-emerald-100/80 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:shadow-none dark:backdrop-blur-sm"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 dark:bg-emerald-500/20">
                  {successToast.emailStatus === 'sent' ? (
                    <CheckCircle className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                  ) : successToast.emailStatus === 'failed' ? (
                    <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                  ) : (
                    <CheckCircle className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                  )}
                </div>
                <div className="flex-1">
                  <p className="text-emerald-800 dark:text-emerald-300">{successToast.message}</p>
                  {successToast.emailStatus && (
                    <p className="mt-1 flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                      <Mail className="h-3 w-3" />
                      Email status: {' '}
                      <span className={successToast.emailStatus === 'sent' ? 'text-emerald-400' : successToast.emailStatus === 'failed' ? 'text-red-400' : 'text-amber-400'}>
                        {successToast.emailStatus}
                      </span>
                    </p>
                  )}
                </div>
                <button onClick={() => setSuccessToast(null)} className="text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300">
                  <X className="h-5 w-5" />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Error Display */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="rounded-2xl border border-red-200 bg-red-50 p-4 shadow-sm dark:border-red-500/20 dark:bg-red-500/10 dark:shadow-none dark:backdrop-blur-sm"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-red-100 dark:bg-red-500/20">
                  <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
                </div>
                <p className="flex-1 text-red-700 dark:text-red-300">{error}</p>
                <button onClick={() => setError('')} className="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300">
                  <X className="h-5 w-5" />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <PlannerMetricCard
            label={roleScope === 'all' ? 'Total accounts' : `Total ${selectedRoleLabel.toLowerCase()}`}
            value={totalPlanners}
            helper={roleScope === 'all' ? 'Authenticated users across the platform' : `${selectedRoleLabel} in the selected scope`}
            icon={Users}
            tone="blue"
          />
          <PlannerMetricCard
            label={roleScope === 'all' ? 'Active accounts' : `Active ${selectedRoleLabel.toLowerCase()}`}
            value={activePlanners}
            helper={roleScope === 'all' ? 'Currently able to sign in and operate' : `Currently able to access ${selectedRoleLabel.toLowerCase()}`}
            icon={CheckCircle2}
            tone="emerald"
          />
          <PlannerMetricCard
            label="Suspended"
            value={suspendedPlanners}
            helper="Accounts requiring follow-up"
            icon={XCircle}
            tone="amber"
          />
          <PlannerMetricCard
            label="Pending invites"
            value={invitationStats.pending}
            helper={showPendingInvitations ? 'Hide invitation queue' : 'Review invitation queue'}
            icon={Send}
            tone="violet"
            onClick={() => setShowPendingInvitations(!showPendingInvitations)}
          />
        </div>

        {/* Pending Invitations Section */}
        <AnimatePresence>
          {showPendingInvitations && pendingInvitations.length > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.3 }}
              className="overflow-hidden"
            >
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <Card className="overflow-hidden">
                <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 dark:border-slate-700">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-100 dark:bg-violet-900/30">
                      <Send className="h-5 w-5 text-violet-600 dark:text-violet-400" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-900 dark:text-white">Pending planner invitations</h3>
                      <p className="text-sm text-slate-500 dark:text-slate-400">Invites that still need acceptance or follow-up.</p>
                    </div>
                    <span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs text-violet-700 dark:bg-violet-500/20 dark:text-violet-400">
                      {pendingInvitations.length}
                    </span>
                  </div>
                  <button
                    onClick={() => setShowPendingInvitations(false)}
                    className="text-slate-500 transition-colors hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-slate-200 bg-slate-50/80 dark:border-slate-700 dark:bg-slate-900/40">
                        <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                          Email
                        </th>
                        <th className="px-6 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                          Plan
                        </th>
                        <th className="px-6 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                          Trial
                        </th>
                        <th className="px-6 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                          Email Status
                        </th>
                        <th className="px-6 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                          Sent
                        </th>
                        <th className="px-6 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                          Expires
                        </th>
                        <th className="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-700/70">
                      {pendingInvitations.map((invitation) => (
                        <tr key={invitation._id} className="transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/60">
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-3">
                              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-100 dark:bg-violet-500/20">
                                <Mail className="h-4 w-4 text-violet-600 dark:text-violet-400" />
                              </div>
                              <div>
                                <p className="font-medium text-slate-900 dark:text-white">{invitation.email}</p>
                                {invitation.invite_data?.company_name && (
                                  <p className="text-xs text-slate-500">{invitation.invite_data.company_name}</p>
                                )}
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4 text-center">
                            <span className="rounded-lg bg-slate-100 px-2 py-1 text-xs text-slate-700 dark:bg-slate-500/20 dark:text-slate-300">
                              {invitation.plan_name || 'Default'}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-center">
                            <span className="text-sm text-slate-700 dark:text-slate-300">
                              {invitation.invite_data?.trial_days || 0} days
                            </span>
                          </td>
                          <td className="px-6 py-4 text-center">
                            <span className={`inline-flex items-center gap-1.5 px-2 py-1 text-xs rounded-full ${
                              invitation.email_status === 'sent'
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400'
                                : invitation.email_status === 'failed'
                                ? 'bg-red-50 text-red-700 dark:bg-red-500/20 dark:text-red-400'
                                : 'bg-amber-50 text-amber-700 dark:bg-amber-500/20 dark:text-amber-400'
                            }`}>
                              {invitation.email_status === 'sent' ? (
                                <CheckCircle className="w-3 h-3" />
                              ) : invitation.email_status === 'failed' ? (
                                <AlertTriangle className="w-3 h-3" />
                              ) : (
                                <Clock className="w-3 h-3" />
                              )}
                              {invitation.email_status}
                              {invitation.resend_count > 0 && (
                                <span className="ml-1 opacity-70">({invitation.resend_count}x)</span>
                              )}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-center">
                            <span className="text-sm text-slate-600 dark:text-slate-400">
                              {formatAdminTimestamp(invitation.created_at)}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-center">
                            <span className="text-sm text-slate-600 dark:text-slate-400">
                              {formatAdminDate(invitation.expires_at)}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => handleResendInvitation(invitation._id)}
                                disabled={resendingId === invitation._id}
                                className="rounded-lg bg-violet-100 p-2 text-violet-700 transition-all hover:bg-violet-200 disabled:opacity-50 dark:bg-violet-500/20 dark:text-violet-400 dark:hover:bg-violet-500/30"
                                title="Resend Invitation"
                              >
                                {resendingId === invitation._id ? (
                                  <div className="w-4 h-4 border-2 border-violet-400/30 border-t-violet-400 rounded-full animate-spin" />
                                ) : (
                                  <RefreshCw className="w-4 h-4" />
                                )}
                              </button>
                              <button
                                onClick={() => handleCancelInvitation(invitation._id)}
                                disabled={cancellingId === invitation._id}
                                className="rounded-lg bg-red-100 p-2 text-red-700 transition-all hover:bg-red-200 disabled:opacity-50 dark:bg-red-500/20 dark:text-red-400 dark:hover:bg-red-500/30"
                                title="Cancel Invitation"
                              >
                                {cancellingId === invitation._id ? (
                                  <div className="w-4 h-4 border-2 border-red-400/30 border-t-red-400 rounded-full animate-spin" />
                                ) : (
                                  <Ban className="w-4 h-4" />
                                )}
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                </Card>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Filters & Search */}
        <Card className="p-4 sm:p-5">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              {roleScopeOptions.map((scope) => {
                const isSelected = roleScope === scope;
                const count = scope === 'all' ? roleBreakdown.all ?? Object.values(roleBreakdown).reduce((sum, current) => sum + current, 0) : (roleBreakdown[scope] || 0);

                return (
                  <button
                    key={scope}
                    type="button"
                    onClick={() => updateRoleScope(scope)}
                    className={`rounded-full px-4 py-2 text-sm font-medium transition-all ${
                      isSelected
                        ? 'bg-wedding-rose text-white shadow-lg'
                        : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900 dark:border-slate-700 dark:bg-slate-900/50 dark:text-slate-300 dark:hover:text-white'
                    }`}
                  >
                    {formatRoleLabel(scope)} <span className="opacity-80">· {count}</span>
                  </button>
                );
              })}
            </div>

            <div className="flex flex-col lg:flex-row gap-4 items-center justify-between">
            {/* Search */}
            <div className="relative w-full lg:w-96">
              <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                placeholder="Search by name, email, or company..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className={`${dashboardInputClass} pl-12`}
              />
            </div>

            {/* Filter Buttons */}
            <div className="flex items-center gap-2">
              <div className="flex rounded-xl border border-slate-200 bg-slate-100 p-1 dark:border-slate-700 dark:bg-slate-900/50">
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
                          : 'bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white'
                        : 'text-slate-500 hover:text-slate-900 hover:bg-white dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-700'
                    }`}
                  >
                    {status.charAt(0).toUpperCase() + status.slice(1)}
                  </button>
                ))}
              </div>

              <button
                onClick={fetchPlanners}
                className={`${dashboardSecondaryButtonClass} p-3`}
                title="Refresh"
              >
                <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
          </div>
        </Card>

        {/* Planners Grid/Table */}
        <Card className="overflow-hidden">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="w-16 h-16 rounded-full border-4 border-primary-500/30 border-t-primary-500 animate-spin mb-4" />
              <p className={dashboardMutedTextClass}>Loading accounts...</p>
            </div>
          ) : filteredPlanners.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-800">
                <Users className="h-10 w-10 text-slate-400 dark:text-slate-600" />
              </div>
              <p className={`mb-2 ${dashboardMutedTextClass}`}>No {emptyStateLabel} found</p>
              <p className="mb-6 text-sm text-slate-500">
                {canInvitePlanners ? 'Get started by inviting your first planner.' : 'Adjust the current scope or filters to view more accounts.'}
              </p>
              {canInvitePlanners && (
                <button
                  onClick={openInviteModal}
                  className={`${dashboardPrimaryButtonClass} flex items-center gap-2 px-6 py-3 font-semibold`}
                >
                  <UserPlus className="w-5 h-5" />
                  {inviteButtonLabel}
                </button>
              )}
            </div>
          ) : (
            <div>
              <div className="flex flex-col gap-4 border-b border-slate-200 px-6 py-5 dark:border-slate-700 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-white">{tableTitle}</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    Review account status, access level, and activity in one place.
                  </p>
                </div>
                <GlassPagination
                  currentPage={pagination.currentPage}
                  totalPages={pagination.totalPages}
                  totalItems={pagination.totalItems}
                  itemsPerPage={pagination.itemsPerPage}
                  onPageChange={pagination.setPage}
                  variant="compact"
                  itemLabel="users"
                />
              </div>
              <div className="overflow-visible">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/80 dark:border-slate-700 dark:bg-slate-900/40">
                    <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                      Account
                    </th>
                    <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                      Contact
                    </th>
                    <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                      Status
                    </th>
                    <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                      Weddings
                    </th>
                    <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                      Plan
                    </th>
                    <th className="px-6 py-4 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                      Joined
                    </th>
                    <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-white/5">
                  {filteredPlanners.map((planner, index) => {
                    const plannerId = planner.id || planner._id || '';
                    const displayName = getPlannerDisplayName(planner);
                    const initials = getInitials(planner);
                    const company = planner.company_name || planner.organization;
                    const isProtectedAccount = !canManageAccount(planner);
                    const planLabel = planner.subscription_tier || planner.plan_id || (planner.role === 'wedding_planner' ? 'Free' : 'Platform access');

                    return (
                      <motion.tr
                        key={plannerId}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.05 }}
                        className="group transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/70"
                      >
                        {/* Planner Info */}
                        <td className="px-6 py-5">
                          <div className="flex items-center gap-4">
                            <div className="relative">
                              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary-500 to-secondary-500 flex items-center justify-center text-white font-bold text-lg shadow-lg">
                                {initials}
                              </div>
                              {planner.is_active && !planner.is_suspended && (
                                <div className="absolute -bottom-1 -right-1 h-4 w-4 rounded-full border-2 border-white bg-emerald-500 dark:border-slate-900" />
                              )}
                            </div>
                            <div>
                              <p className="font-semibold text-slate-900 transition-colors group-hover:text-primary-500 dark:text-white dark:group-hover:text-primary-400">
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
                            <p className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
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
                            <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/20 dark:text-amber-400">
                              <XCircle className="w-3.5 h-3.5" />
                              Suspended
                            </span>
                          ) : planner.is_active ? (
                            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/20 dark:text-emerald-400">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-600 dark:border-slate-500/30 dark:bg-slate-500/20 dark:text-slate-400">
                              Inactive
                            </span>
                          )}
                        </td>

                        {/* Weddings */}
                        <td className="px-6 py-5 text-center">
                          <div className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 dark:border-slate-700 dark:bg-slate-800/70">
                            <Heart className="w-4 h-4 text-rose-400" />
                            <span className="font-semibold text-slate-900 dark:text-white">{planner.wedding_count || 0}</span>
                          </div>
                        </td>

                        {/* Subscription */}
                        <td className="px-6 py-5 text-center">
                          <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold ${getSubscriptionStyle(planner.subscription_tier || planner.plan_id)}`}>
                            <Shield className="w-3.5 h-3.5" />
                            {planLabel}
                          </span>
                        </td>

                        {/* Joined Date */}
                        <td className="px-6 py-5 text-center">
                          <div className="flex items-center justify-center gap-1.5 text-sm text-slate-500 dark:text-slate-400">
                            <Calendar className="w-4 h-4" />
                            {planner.created_at
                              ? formatAdminDate(planner.created_at)
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
                              className={`${dashboardSecondaryButtonClass} p-2`}
                            >
                              <MoreHorizontal className="w-5 h-5" />
                            </button>

                            <AnimatePresence>
                              {actionMenuOpen === plannerId && (
                                <motion.div
                                  initial={{ opacity: 0, scale: 0.95, y: -10 }}
                                  animate={{ opacity: 1, scale: 1, y: 0 }}
                                  exit={{ opacity: 0, scale: 0.95, y: -10 }}
                                  className="absolute right-0 z-50 mt-2 w-52 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-800 dark:shadow-2xl"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <div className="p-1">
                                    <button
                                      onClick={() => handleViewPlannerDetails(planner)}
                                      className="flex w-full items-center gap-3 rounded-lg px-4 py-3 text-left text-sm text-slate-700 transition-colors hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
                                    >
                                      <Eye className="w-4 h-4" />
                                      View Details
                                    </button>

                                    {isProtectedAccount ? (
                                      <div className="rounded-lg px-4 py-3 text-left text-xs text-slate-500 dark:text-slate-400">
                                        Protected account. View access only.
                                      </div>
                                    ) : (
                                      <>
                                        {planner.is_suspended ? (
                                          <button
                                            onClick={() => handleActivateUser(plannerId)}
                                            className="flex w-full items-center gap-3 rounded-lg px-4 py-3 text-sm text-emerald-700 transition-colors hover:bg-emerald-50 dark:text-emerald-400 dark:hover:bg-emerald-500/10"
                                          >
                                            <CheckCircle2 className="w-4 h-4" />
                                            Activate User
                                          </button>
                                        ) : (
                                          <button
                                            onClick={() => handleSuspendUser(plannerId)}
                                            className="flex w-full items-center gap-3 rounded-lg px-4 py-3 text-sm text-amber-700 transition-colors hover:bg-amber-50 dark:text-amber-400 dark:hover:bg-amber-500/10"
                                          >
                                            <UserX className="w-4 h-4" />
                                            Suspend User
                                          </button>
                                        )}

                                        <div className="my-1 border-t border-slate-200 dark:border-slate-700" />

                                        <button
                                          onClick={() => handleDeleteUser(plannerId)}
                                          className="flex w-full items-center gap-3 rounded-lg px-4 py-3 text-sm text-red-700 transition-colors hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
                                        >
                                          <Trash2 className="w-4 h-4" />
                                          Delete User
                                        </button>
                                      </>
                                    )}
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
            </div>
          )}

          {/* Table Footer */}
          {filteredPlanners.length > 0 && (
            <div className="flex items-center justify-between border-t border-slate-200 px-6 py-4 dark:border-slate-700">
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Showing <span className="font-medium text-slate-900 dark:text-white">{filteredPlanners.length}</span> of{' '}
                <span className="font-medium text-slate-900 dark:text-white">{totalPlanners}</span> {roleScope === 'all' ? 'accounts' : emptyStateLabel}
              </p>
              <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                <TrendingUp className="w-4 h-4 text-emerald-500 dark:text-emerald-400" />
                {activePlanners} active in this scope
              </div>
            </div>
          )}

          {/* Pagination */}
          <GlassPagination
            currentPage={pagination.currentPage}
            totalPages={pagination.totalPages}
            totalItems={pagination.totalItems}
            itemsPerPage={pagination.itemsPerPage}
            onPageChange={pagination.setPage}
            onItemsPerPageChange={pagination.setItemsPerPage}
            itemLabel="users"
          />
        </Card>

        {/* Account Detail Modal */}
        <AnimatePresence>
          {showPlannerDetailModal && plannerDetail && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
              onClick={() => setShowPlannerDetailModal(false)}
            >
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 20 }}
                className="max-h-[75vh] w-full max-w-2xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="relative overflow-hidden border-b border-slate-200 px-6 pt-6 pb-4 dark:border-slate-700">
                  <div className="absolute top-0 right-0 h-40 w-40 rounded-full bg-gradient-to-br from-primary-500/15 to-secondary-500/15 blur-2xl" />
                  <div className="relative flex items-start justify-between gap-4">
                    <div className="flex items-center gap-4">
                      <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br from-primary-500 to-secondary-500 text-lg font-bold text-white shadow-lg shadow-primary-500/30">
                        {getInitials(plannerDetail)}
                      </div>
                      <div>
                        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">{getPlannerDisplayName(plannerDetail)}</h2>
                        <p className="text-sm text-slate-500 dark:text-slate-400">{plannerDetail.email}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => setShowPlannerDetailModal(false)}
                      className="text-slate-400 transition-colors hover:text-slate-900 dark:hover:text-white"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>
                </div>

                <div className="max-h-[calc(75vh-96px)] space-y-6 overflow-y-auto p-6">
                  {plannerDetailLoading ? (
                    <div className="flex flex-col items-center justify-center py-12">
                      <div className="mb-3 h-10 w-10 animate-spin rounded-full border-4 border-primary-500/30 border-t-primary-500" />
                      <p className="text-slate-500 dark:text-slate-400">Loading account details...</p>
                    </div>
                  ) : (
                    <>
                      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                        <div className={dashboardPanelSubtleClass + ' p-4'}>
                          <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Status</p>
                          <p className="text-lg font-semibold text-slate-900 dark:text-white">{plannerStatusLabel}</p>
                        </div>
                        <div className={dashboardPanelSubtleClass + ' p-4'}>
                          <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Plan</p>
                          <p className="text-lg font-semibold text-slate-900 dark:text-white">
                            {plannerDetail.subscription_tier || plannerDetail.plan_id || 'Free'}
                          </p>
                        </div>
                        <div className={dashboardPanelSubtleClass + ' p-4'}>
                          <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Weddings</p>
                          <p className="text-lg font-semibold text-slate-900 dark:text-white">{plannerDetail.wedding_count || 0}</p>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                        <div className={dashboardPanelSubtleClass + ' p-4'}>
                          <p className="mb-3 text-xs uppercase tracking-wide text-slate-500">Account</p>
                          <dl className="space-y-3">
                            <div>
                              <dt className="text-xs text-slate-500">Company</dt>
                              <dd className="text-sm text-slate-900 dark:text-white">{plannerDetail.company_name || plannerDetail.organization || 'Not set'}</dd>
                            </div>
                            <div>
                              <dt className="text-xs text-slate-500">Phone</dt>
                              <dd className="text-sm text-slate-900 dark:text-white">{plannerDetail.phone || 'Not set'}</dd>
                            </div>
                            <div>
                              <dt className="text-xs text-slate-500">Role</dt>
                              <dd className="text-sm text-slate-900 dark:text-white">{plannerDetail.role || 'wedding_planner'}</dd>
                            </div>
                            <div>
                              <dt className="text-xs text-slate-500">Email verified</dt>
                              <dd className="text-sm text-slate-900 dark:text-white">{plannerDetail.email_verified ? 'Yes' : 'No'}</dd>
                            </div>
                          </dl>
                        </div>

                        <div className={dashboardPanelSubtleClass + ' p-4'}>
                          <p className="mb-3 text-xs uppercase tracking-wide text-slate-500">Billing & Access</p>
                          <dl className="space-y-3">
                            <div>
                              <dt className="text-xs text-slate-500">Subscription status</dt>
                              <dd className="text-sm text-slate-900 dark:text-white">{plannerDetail.subscription_status || 'Unknown'}</dd>
                            </div>
                            <div>
                              <dt className="text-xs text-slate-500">Trial ends</dt>
                              <dd className="text-sm text-slate-900 dark:text-white">
                                {plannerDetail.trial_end_date ? formatAdminTimestamp(plannerDetail.trial_end_date, plannerTimezone) : 'N/A'}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-xs text-slate-500">Timezone</dt>
                              <dd className="text-sm text-slate-900 dark:text-white">{plannerTimezone}</dd>
                            </div>
                            <div>
                              <dt className="text-xs text-slate-500">Max weddings</dt>
                              <dd className="text-sm text-slate-900 dark:text-white">
                                {typeof plannerDetail.max_weddings === 'number' ? plannerDetail.max_weddings : 'Not set'}
                              </dd>
                            </div>
                          </dl>
                        </div>
                      </div>

                      <div className={dashboardPanelSubtleClass + ' p-4'}>
                        <p className="mb-3 text-xs uppercase tracking-wide text-slate-500">Timestamps</p>
                        <dl className="grid grid-cols-1 gap-4 md:grid-cols-3">
                          <div>
                            <dt className="text-xs text-slate-500">Joined</dt>
                            <dd className="text-sm text-slate-900 dark:text-white">
                              {plannerDetail.created_at ? formatAdminTimestamp(plannerDetail.created_at, plannerTimezone) : 'N/A'}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs text-slate-500">Updated</dt>
                            <dd className="text-sm text-slate-900 dark:text-white">
                              {plannerDetail.updated_at ? formatAdminTimestamp(plannerDetail.updated_at, plannerTimezone) : 'N/A'}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs text-slate-500">Last login</dt>
                            <dd className="text-sm text-slate-900 dark:text-white">
                              {plannerDetail.last_login ? formatAdminTimestamp(plannerDetail.last_login, plannerTimezone) : 'N/A'}
                            </dd>
                          </div>
                        </dl>
                      </div>
                    </>
                  )}
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

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
                className="w-full max-w-md overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900"
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
                      <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Invite Planner</h2>
                      <p className="text-sm text-slate-500 dark:text-slate-400">Send an invitation to join your platform</p>
                    </div>
                  </div>
                </div>

                {/* Modal Body */}
                <form onSubmit={handleInvitePlanner} className="p-6 pt-2 space-y-4 max-h-[70vh] overflow-y-auto">
                  {/* Basic Info Section */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="col-span-2">
                      <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        Email Address <span className="text-red-400">*</span>
                      </label>
                      <input
                        type="email"
                        value={inviteForm.email}
                        onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
                        className={dashboardInputClass}
                        placeholder="jane@company.com"
                        required
                      />
                    </div>

                    <div>
                      <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        Full Name
                      </label>
                      <input
                        type="text"
                        value={inviteForm.name}
                        onChange={(e) => setInviteForm({ ...inviteForm, name: e.target.value })}
                        className={dashboardInputClass}
                        placeholder="Jane Smith"
                      />
                    </div>

                    <div>
                      <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
                        Company
                      </label>
                      <input
                        type="text"
                        value={inviteForm.organization}
                        onChange={(e) => setInviteForm({ ...inviteForm, organization: e.target.value })}
                        className={dashboardInputClass}
                        placeholder="Wedding Co."
                      />
                    </div>
                  </div>

                  {/* Trial Configuration Section */}
                  <div className="border-t border-slate-200 pt-4 dark:border-slate-700">
                    <div className="flex items-center gap-2 mb-4">
                      <Gift className="w-5 h-5 text-primary-400" />
                      <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Trial Configuration</h3>
                    </div>

                    <div className="space-y-4">
                      {/* Plan Selection */}
                      <div>
                        <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          <CreditCard className="w-4 h-4 inline mr-1" />
                          Subscription Plan <span className="text-red-400">*</span>
                        </label>
                        <select
                          value={inviteForm.plan_id}
                          onChange={(e) => setInviteForm({ ...inviteForm, plan_id: e.target.value })}
                          className={dashboardInputClass}
                          required
                        >
                          <option value="" className="bg-white text-slate-900 dark:bg-slate-800 dark:text-white">Select a plan...</option>
                          {availablePlans.map((plan) => (
                            <option key={plan._id} value={plan._id} className="bg-white text-slate-900 dark:bg-slate-800 dark:text-white">
                              {plan.name} - ${plan.price_monthly}/mo
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Trial Days */}
                      <div>
                        <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          <Clock className="w-4 h-4 inline mr-1" />
                          Trial Duration (days)
                        </label>
                        <div className="flex items-center gap-3">
                          <input
                            type="range"
                            min="0"
                            max="180"
                            step="7"
                            value={inviteForm.trial_days}
                            onChange={(e) => setInviteForm({ ...inviteForm, trial_days: parseInt(e.target.value) })}
                            className="h-2 flex-1 cursor-pointer appearance-none rounded-lg bg-slate-200 accent-primary-500 dark:bg-slate-700"
                          />
                          <input
                            type="number"
                            min="0"
                            max="730"
                            value={inviteForm.trial_days}
                            onChange={(e) => setInviteForm({ ...inviteForm, trial_days: parseInt(e.target.value) || 0 })}
                            className="w-20 rounded-lg border border-slate-200 bg-white px-3 py-2 text-center text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500/50 dark:border-slate-600 dark:bg-slate-700 dark:text-white dark:shadow-none"
                          />
                        </div>
                        <p className="text-xs text-slate-500 mt-1">
                          {inviteForm.trial_days === 0 ? 'No trial - user must pay immediately' :
                           inviteForm.trial_days === 1 ? '1 day trial' :
                           `${inviteForm.trial_days} days trial (${Math.round(inviteForm.trial_days / 30)} months)`}
                        </p>
                      </div>

                      {/* Trial End Behavior */}
                      {inviteForm.trial_days > 0 && (
                        <div>
                          <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
                            When Trial Ends Without Payment
                          </label>
                          <div className="grid grid-cols-2 gap-3">
                            <button
                              type="button"
                              onClick={() => setInviteForm({ ...inviteForm, trial_end_behavior: 'pause' })}
                              className={`p-3 rounded-xl border transition-all ${
                                inviteForm.trial_end_behavior === 'pause'
                                  ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-primary-500/20 dark:text-white'
                                  : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
                              }`}
                            >
                              <div className="font-medium">Pause</div>
                              <div className="text-xs opacity-70">User can resume later</div>
                            </button>
                            <button
                              type="button"
                              onClick={() => setInviteForm({ ...inviteForm, trial_end_behavior: 'cancel' })}
                              className={`p-3 rounded-xl border transition-all ${
                                inviteForm.trial_end_behavior === 'cancel'
                                  ? 'border-amber-500 bg-amber-50 text-amber-700 dark:bg-amber-500/20 dark:text-white'
                                  : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
                              }`}
                            >
                              <div className="font-medium">Cancel</div>
                              <div className="text-xs opacity-70">Subscription ends</div>
                            </button>
                          </div>
                        </div>
                      )}

                      {/* Admin Notes */}
                      <div>
                        <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
                          Internal Notes (optional)
                        </label>
                        <textarea
                          value={inviteForm.admin_notes}
                          onChange={(e) => setInviteForm({ ...inviteForm, admin_notes: e.target.value })}
                          className={`${dashboardInputClass} resize-none`}
                          placeholder="Partnership deal, beta tester, etc."
                          rows={2}
                          maxLength={500}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Summary */}
                  {inviteForm.plan_id && inviteForm.trial_days > 0 && (
                    <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 dark:border-primary-500/20 dark:bg-primary-500/10">
                      <div className="flex items-start gap-3">
                        <Gift className="w-5 h-5 text-primary-400 mt-0.5" />
                        <div className="text-sm">
                          <p className="font-medium text-slate-900 dark:text-white">Trial Summary</p>
                          <p className="text-slate-600 dark:text-slate-400">
                            User will receive a <span className="text-primary-400">{inviteForm.trial_days}-day</span> free trial
                            on the <span className="text-primary-400">{availablePlans.find(p => p._id === inviteForm.plan_id)?.name}</span> plan.
                            After trial ends, subscription will <span className="text-primary-400">{inviteForm.trial_end_behavior}</span> if no payment method is added.
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="flex gap-3 pt-4">
                    <button
                      type="button"
                      onClick={() => {
                        setShowInviteModal(false);
                        setInviteForm(buildInviteForm());
                      }}
                      className={`flex-1 px-4 py-3 font-medium ${dashboardSecondaryButtonClass}`}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={inviteLoading}
                      className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-wedding-rose px-4 py-3 font-semibold text-white shadow-sm transition-colors hover:bg-wedding-gold disabled:cursor-not-allowed disabled:opacity-50"
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
