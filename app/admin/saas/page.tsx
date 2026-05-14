'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { Card } from '../../components/ui/Card';
import { formatDate, formatDateTime } from '@/utils/dateFormat';
import PageHeader from '../components/PageHeader';
import { toast } from 'sonner';
import { Settings, Download, Database, RefreshCw, Save, TrendingUp, TrendingDown, Minus, Activity, Users, Zap, DollarSign, Upload, Store, Trash2, Search, ChevronDown, ChevronUp, ExternalLink, Pencil, X } from 'lucide-react';
import { fetchBehavioralAnalytics, type BehavioralAnalyticsResponse } from '@/services/behavioralAnalyticsApi';
import VendorImportModal from '@/components/vendor/VendorImportModal';
import { getVendorDirectory, deleteVendorProfile, updateVendorProfile, type VendorProfile } from '@/services/vendorManagementApi';
import {
  getAdminConfig,
  getAdminPipelineStatus,
  exportAdminData,
  updateAdminConfig,
  type PlatformConfig,
  type PipelineStatus,
} from '@/services/campaignAdvertisingApi';
import {
  buildPlanFeatureState,
  formatFeatureListInput,
  getPlanFeatureEntries,
  getPlanFeatureLabel,
  parseFeatureListInput,
} from './planFeatureConfig';

interface SubscriptionPlan {
 _id: string;
 name: string;
 description?: string;
 price_monthly: number;
 price_yearly?: number;
 max_weddings: number;
 max_guests_per_wedding: number;
 ai_credits_monthly: number;
 storage_gb: number;
 staff_seats: number;
 features: {
 [key: string]: boolean;
 };
 features_list?: string[];
 // Metered billing
 billing_model?: 'flat_rate' | 'metered';
 is_metered?: boolean;
 meter_event_name?: string;
 meter_id?: string;
 // Display
 is_featured: boolean;
 is_active: boolean;
 display_order: number;
 sort_order?: number;
 trial_days?: number;
 created_by: string;
 created_at: string;
 updated_at: string;
}

interface WeddingPlanner {
 id: string;
 email: string;
 companyName: string;
 subscriptionPlanId: string;
 subscriptionStatus: string;
 maxWeddings: number;
 is_active: boolean;
 createdAt: string;
 lastLogin?: string;
 timezone?: string;
}

// ---------- Platform Metrics types (merged from Business Analytics) ----------

interface RoleBreakdown {
  [role: string]: number;
}

interface PlatformMetricsResponse {
  generated_at: string;
  timeframe: string;
  users: {
    total: number;
    active: number;
    new_in_period: number;
    growth_rate: number;
    role_breakdown: RoleBreakdown;
  };
  subscriptions: {
    total: number;
    status_breakdown: {
      trial: number;
      active: number;
      cancelled: number;
      expired: number;
      [status: string]: number;
    };
    active_plans: number;
    monthly_recurring_revenue: number;
    yearly_recurring_revenue: number;
    projected_annual_revenue: number;
    plan_breakdown: {
      [planId: string]: {
        name: string;
        monthly_revenue: number;
        annual_revenue: number;
        active_users: number;
        trial_users: number;
      };
    };
  };
  operations: {
    weddings: {
      total: number;
      active: number;
      upcoming: number;
      created_in_period: number;
      guest_total: number;
      rsvp_total: number;
    };
    forms: {
      total: number;
      new_in_period: number;
      responses_total: number;
      responses_in_period: number;
    };
    communications: {
      notifications_sent: number;
      notifications_in_period: number;
      email_logs_total: number;
      emails_sent_in_period: number;
      ai_events_total: number;
      ai_events_in_period: number;
    };
  };
}

type TimeframeKey = '7d' | '30d' | '90d' | '1y';

const TIMEFRAME_OPTIONS: Array<{ value: TimeframeKey; label: string }> = [
  { value: '7d', label: 'Last 7 Days' },
  { value: '30d', label: 'Last 30 Days' },
  { value: '90d', label: 'Last 90 Days' },
  { value: '1y', label: 'Last 12 Months' },
];

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatNumber(amount: number): string {
  return new Intl.NumberFormat('en-US').format(amount);
}

function formatBillingModel(plan: Pick<SubscriptionPlan, 'is_metered' | 'meter_event_name'>): string {
  if (plan.is_metered) {
    return `Metered (${plan.meter_event_name || 'wedding_active'})`;
  }
  return 'Flat-rate';
}

/* Landing page content (hero, features, stats, theme, etc.) is now hardcoded
   in app/page.tsx for performance. The SaaS Content and Theme tabs have been
   removed. Subscription plans, analytics, and customer reviews remain admin-configurable. */

interface Testimonial {
  _id: string;
  name: string;
  company: string;
  role: string;
  quote: string;
  avatar_url?: string;
  is_active: boolean;
  display_order: number;
  created_at?: string;
  updated_at?: string;
  created_by?: string;
}

const EMPTY_BEHAVIORAL_METRICS: BehavioralAnalyticsResponse = {
  generated_at: '',
  timeframe: '30d',
  weekly_active_users: {
    current: 0,
    previous_week: 0,
    change: 0,
    change_percent: 0,
    mau: 0,
    stickiness_ratio: 0,
  },
  activation_funnel: {
    period: 'last_30_days',
    steps: [],
    conversion_rate: 0,
    signups_90d: 0,
  },
  retention_cohorts: { cohorts: [] },
  engagement_signals: {
    rsvp_velocity: {
      current_7d: 0,
      previous_7d: 0,
      change: 0,
      trend: 'flat',
    },
    platform_response_rate: 0,
    active_engaged_weddings: 0,
    north_star_metric: 0,
  },
  mrr_movement: {
    current_mrr: 0,
    new_mrr: 0,
    churned_mrr: 0,
    net_change: 0,
    net_change_percent: 0,
    trial_conversions: 0,
    trial_conversion_rate: 0,
  },
  week_over_week: {
    new_users: { current: 0, previous: 0, change: 0, change_percent: 0, trend: 'flat' },
    new_weddings: { current: 0, previous: 0, change: 0, change_percent: 0, trend: 'flat' },
    new_rsvps: { current: 0, previous: 0, change: 0, change_percent: 0, trend: 'flat' },
    active_users: { current: 0, previous: 0, change: 0, change_percent: 0, trend: 'flat' },
  },
};

const SaasAdminDashboard = () => {
 const router = useRouter();
 const searchParams = useSearchParams();
 const { userProfile, token, expireSession, apiRequest } = useAdmin();
 const [activeTab, setActiveTab] = useState<'overview' | 'plans' | 'reviews' | 'ad-config' | 'vendor-data'>('overview');
 const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
 const [planners, setPlanners] = useState<WeddingPlanner[]>([]);
 const [loading, setLoading] = useState(true);
 const [showCreatePlanModal, setShowCreatePlanModal] = useState(false);
 const [editingPlan, setEditingPlan] = useState<SubscriptionPlan | null>(null);
 const [error, setError] = useState<string | null>(null);
 // Platform metrics state (merged from Business Analytics)
 const [metrics, setMetrics] = useState<PlatformMetricsResponse | null>(null);
 const [metricsTimeframe, setMetricsTimeframe] = useState<TimeframeKey>('30d');
 const [metricsLoading, setMetricsLoading] = useState(false);
	 const [behavioralMetrics, setBehavioralMetrics] = useState<BehavioralAnalyticsResponse | null>(null);
	 const [behavioralLoading, setBehavioralLoading] = useState(false);
	 const safeBehavioralMetrics = behavioralMetrics ? {
	   ...EMPTY_BEHAVIORAL_METRICS,
	   ...behavioralMetrics,
	   weekly_active_users: behavioralMetrics.weekly_active_users ?? EMPTY_BEHAVIORAL_METRICS.weekly_active_users,
	   activation_funnel: {
	     ...EMPTY_BEHAVIORAL_METRICS.activation_funnel,
	     ...behavioralMetrics.activation_funnel,
	     steps: behavioralMetrics.activation_funnel?.steps ?? EMPTY_BEHAVIORAL_METRICS.activation_funnel.steps,
	   },
	   retention_cohorts: {
	     cohorts: behavioralMetrics.retention_cohorts?.cohorts ?? EMPTY_BEHAVIORAL_METRICS.retention_cohorts.cohorts,
	   },
	   engagement_signals: {
	     ...EMPTY_BEHAVIORAL_METRICS.engagement_signals,
	     ...behavioralMetrics.engagement_signals,
	     rsvp_velocity: behavioralMetrics.engagement_signals?.rsvp_velocity ?? EMPTY_BEHAVIORAL_METRICS.engagement_signals.rsvp_velocity,
	   },
	   mrr_movement: behavioralMetrics.mrr_movement ?? EMPTY_BEHAVIORAL_METRICS.mrr_movement,
	   week_over_week: behavioralMetrics.week_over_week ?? EMPTY_BEHAVIORAL_METRICS.week_over_week,
	 } : null;

  // ROOT_ADMIN access control - redirect non-root admins
  useEffect(() => {
    if (userProfile && !userProfile.is_root_admin) {
      router.push('/admin');
    }
  }, [userProfile, router]);
  const fetchData = useCallback(async () => {
    try {
      const baseUrl = getApiBaseUrl();

      if (!token) {
        setLoading(false);
        return;
      }

      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };

      const plansResponse = await fetch(`${baseUrl}/subscription-plans?include_inactive=true`, { headers, credentials: 'include' });
      if (plansResponse.status === 401) {
        expireSession();
        return;
      }
      if (plansResponse.ok) {
        const plansData = await plansResponse.json();
        console.log('[SaaS Admin] Subscription plans loaded:', plansData.length, 'plans');
        setPlans(plansData);
      } else {
        console.error('[SaaS Admin] Failed to load subscription plans:', plansResponse.status, plansResponse.statusText);
        const errorText = await plansResponse.text();
        console.error('[SaaS Admin] Error details:', errorText);
      }

      const plannersResponse = await fetch(`${baseUrl}/saas/wedding-planners`, { headers, credentials: 'include' });
      if (plannersResponse.status === 401) {
        expireSession();
        return;
      }
      if (plannersResponse.ok) {
        const plannersData = await plannersResponse.json();
        setPlanners(plannersData.map((planner: any) => ({
          id: planner.id,
          email: planner.email,
          companyName: planner.company_name,
          subscriptionPlanId: planner.plan_id,
          subscriptionStatus: planner.subscription_status,
          maxWeddings: planner.max_weddings,
          is_active: planner.is_active,
          createdAt: planner.created_at,
          lastLogin: planner.last_login
        })) );
      }

      // Fetch platform metrics for the Overview tab (replaces old analytics/overview + revenue calls)
      const metricsResponse = await fetch(`${baseUrl}/saas/analytics/platform?timeframe=${metricsTimeframe}`, { headers, credentials: 'include' });
      if (metricsResponse.status === 401) {
        expireSession();
        return;
      }
      if (metricsResponse.ok) {
        const metricsData = await metricsResponse.json();
        setMetrics(metricsData);
      }

      // Fetch behavioral analytics (WAU, funnels, retention, MRR movement)
      try {
        setBehavioralLoading(true);
        const behavioralData = await fetchBehavioralAnalytics(apiRequest, metricsTimeframe);
        if (behavioralData) {
          setBehavioralMetrics(behavioralData);
        }
      } catch (err) {
        console.error('[SaaS Admin] Failed to load behavioral analytics:', err);
      } finally {
        setBehavioralLoading(false);
      }
    } catch (error) {
      console.error('Error fetching SaaS data:', error);
      setError('Failed to load SaaS admin data. Using sample data.');
      setPlans([
        {
          _id: 'plan-1',
          name: 'Studio Growth',
          description: 'Grow your planning studio with advanced automation and analytics.',
          price_monthly: 179,
          price_yearly: 1890,
          max_weddings: 15,
          max_guests_per_wedding: 500,
          ai_credits_monthly: 800,
          storage_gb: 150,
          staff_seats: 10,
          features: {
            timeline: true,
            guest_management: true,
            vendor_portal: true,
            budgeting: true,
            ai_email: true,
            ai_design: true,
            analytics: true
          },
          is_featured: true,
          is_active: true,
          display_order: 1,
          created_by: 'system',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        },
        {
          _id: 'plan-2',
          name: 'Signature',
          description: 'Collaborate with unlimited vendors and automate client touchpoints.',
          price_monthly: 289,
          price_yearly: 3090,
          max_weddings: 30,
          max_guests_per_wedding: 1200,
          ai_credits_monthly: 2000,
          storage_gb: 500,
          staff_seats: 25,
          features: {
            timeline: true,
            guest_management: true,
            vendor_portal: true,
            budgeting: true,
            ai_email: true,
            ai_design: true,
            analytics: true
          },
          is_featured: false,
          is_active: true,
          display_order: 2,
          created_by: 'system',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
      ]);

      setPlanners([
        {
          id: 'planner-1',
          email: 'alicia@luxeplanners.com',
          companyName: 'Luxe Planners',
          subscriptionPlanId: 'plan-1',
          subscriptionStatus: 'active',
          maxWeddings: 15,
          is_active: true,
          createdAt: new Date().toISOString(),
          lastLogin: new Date().toISOString()
        },
        {
          id: 'planner-2',
          email: 'jordan@everafterstudio.com',
          companyName: 'EverAfter Studio',
          subscriptionPlanId: 'plan-2',
          subscriptionStatus: 'trial',
          maxWeddings: 30,
          is_active: true,
          createdAt: new Date().toISOString(),
          lastLogin: new Date().toISOString()
        }
      ]);

    } finally {
      setLoading(false);
    }
  }, [apiRequest, expireSession, metricsTimeframe, token]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    const requestedTab = searchParams.get('tab');
    if (requestedTab === 'overview' || requestedTab === 'plans' || requestedTab === 'reviews' || requestedTab === 'ad-config' || requestedTab === 'vendor-data') {
      setActiveTab(requestedTab);
    }
  }, [searchParams]);

  // Refetch only platform metrics when timeframe changes (without re-fetching plans/planners)
  const fetchMetricsOnly = useCallback(async (tf: TimeframeKey) => {
    try {
      setMetricsLoading(true);
      const baseUrl = getApiBaseUrl();
      if (!token) return;
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };
      const res = await fetch(`${baseUrl}/saas/analytics/platform?timeframe=${tf}`, { headers, credentials: 'include' });
      if (res.status === 401) {
        expireSession();
        return;
      }
      if (res.ok) {
        setMetrics(await res.json());
      }
    } catch (err) {
      console.error('Failed to refresh platform metrics', err);
    } finally {
      setMetricsLoading(false);
    }
  }, [expireSession, token]);

  const handleTimeframeChange = useCallback((tf: TimeframeKey) => {
    setMetricsTimeframe(tf);
    fetchMetricsOnly(tf);
  }, [fetchMetricsOnly]);

  const openAccountsDirectory = useCallback((role?: string) => {
    if (!role || role === 'all') {
      router.push('/admin/users');
      return;
    }
    router.push(`/admin/users?role=${encodeURIComponent(role)}`);
  }, [router]);

  // Memoised derived data for the overview tab
  const roleBreakdown = useMemo(() => {
    if (!metrics) return [] as Array<{ role: string; count: number }>;
    return Object.entries(metrics.users.role_breakdown)
      .map(([role, count]) => ({ role, count }))
      .sort((a, b) => b.count - a.count);
  }, [metrics]);

  const statusBreakdown = useMemo(() => {
    if (!metrics) return [] as Array<{ status: string; count: number }>;
    return Object.entries(metrics.subscriptions.status_breakdown).map(([status, count]) => ({
      status,
      count,
    }));
  }, [metrics]);

 const handleCreatePlan = () => {
 setEditingPlan(null);
 setShowCreatePlanModal(true);
 };

 const handleEditPlan = (plan: SubscriptionPlan) => {
 setEditingPlan(plan);
 setShowCreatePlanModal(true);
 };

 const handleDeletePlan = async (planId: string) => {
 if (!confirm('Are you sure you want to delete this subscription plan?')) {
 return;
 }

 try {
 const baseUrl = getApiBaseUrl();
 const response = await fetch(`${baseUrl}/subscription-plans/${planId}`, {
 method: 'DELETE',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 },
 credentials: 'include',
 });

 if (response.ok) {
 setPlans(prev => prev.filter(plan => plan._id !== planId));
 alert('Subscription plan deleted successfully');
 } else {
 throw new Error('Failed to delete plan');
 }
 } catch (error) {
 console.error('Error deleting plan:', error);
 alert('Failed to delete subscription plan');
 }
 };

 const handleSavePlan = async (planData: any) => {
 try {
 const baseUrl = getApiBaseUrl();

 const isEditing = !!editingPlan;
 const url = isEditing
 ? `${baseUrl}/subscription-plans/${editingPlan._id}`
 : `${baseUrl}/subscription-plans`;

 const method = isEditing ? 'PUT' : 'POST';

 const response = await fetch(url, {
 method,
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 },
 credentials: 'include',
 body: JSON.stringify(planData)
 });

 if (response.ok) {
 // Refresh plans data — MUST pass include_inactive=true here so that a
 // plan the admin just toggled to Inactive does NOT disappear from the
 // admin list view. The page-load fetch uses the same query param
 // (see initial loadDashboardData()), and the admin list filter logic
 // depends on is_active being a flag, not a presence test.
 const plansResponse = await fetch(`${baseUrl}/subscription-plans?include_inactive=true`, {
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 },
 credentials: 'include',
 });
 if (plansResponse.ok) {
 const updatedPlans = await plansResponse.json();
 setPlans(updatedPlans);
 }

 setShowCreatePlanModal(false);
 setEditingPlan(null);
 alert(`Subscription plan ${isEditing ? 'updated' : 'created'} successfully`);
 } else {
 throw new Error(`Failed to ${isEditing ? 'update' : 'create'} plan`);
 }
 } catch (error) {
 console.error('Error saving plan:', error);
 alert(`Failed to ${editingPlan ? 'update' : 'create'} subscription plan`);
 }
 };

 const handleCreatePlanner = async () => {
 const email = prompt('Enter planner email:');
 const companyName = prompt('Enter company name:');
 if (!email || !companyName) return;

 try {
 const baseUrl = getApiBaseUrl();
 const response = await fetch(`${baseUrl}/saas/wedding-planners`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 },
 credentials: 'include',
 body: JSON.stringify({
 email,
 company_name: companyName
 })
 });

 if (response.ok) {
 alert('Wedding planner created successfully');
 // Refresh planners data
 window.location.reload();
 } else {
 const error = await response.json();
 throw new Error(error.detail || 'Failed to create planner');
 }
 } catch (error: any) {
 console.error('Error creating planner:', error);
 alert(`Failed to create wedding planner: ${error.message}`);
 }
 };

 const handleTogglePlannerStatus = async (plannerId: string) => {
 try {
 const baseUrl = getApiBaseUrl();
 // Find the planner to get current status
 const planner = planners.find(p => p.id === plannerId);
 if (!planner) {
 alert('Planner not found');
 return;
 }

 const isActivating = !planner.is_active;

 // First toggle the user status
 const statusResponse = await fetch(`${baseUrl}/saas/wedding-planners/${plannerId}/status`, {
 method: 'PUT',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 },
 credentials: 'include',
 });

 if (!statusResponse.ok) {
 throw new Error('Failed to update planner status');
 }

 const statusResult = await statusResponse.json();

 // If activating and no subscription plan assigned, assign default plan
 if (isActivating) {
 // Find a default plan (preferably Free Trial or the first active plan)
 const defaultPlan = plans.find(p => p.name.toLowerCase().includes('trial')) ||
 plans.find(p => p.is_active) ||
 plans[0];

 if (defaultPlan) {
 try {
 // Create subscription for the planner
 const subscriptionResponse = await fetch(`${baseUrl}/users/${plannerId}/subscription`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 },
 credentials: 'include',
 body: JSON.stringify({
 plan_id: defaultPlan._id,
 billing_interval: 'monthly',
 trial_days: parseInt(prompt('Enter trial days (0 for no trial, 150 for 5 months):') || '14', 10)
 })
 });

 if (!subscriptionResponse.ok) {
 // If subscription creation fails, don't fail the whole operation
 // The user might already have a subscription
 const subError = await subscriptionResponse.text();
 console.warn('Subscription creation failed:', subError);
 }
 } catch (subError) {
 console.warn('Error creating subscription:', subError);
 }
 }
 } else {
 // If deactivating, cancel the subscription
 try {
 await fetch(`${baseUrl}/users/${plannerId}/subscription`, {
 method: 'DELETE',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 },
 credentials: 'include',
 });
 } catch (subError) {
 console.warn('Error cancelling subscription:', subError);
 }
 }

 // Update local state
 setPlanners(prev => prev.map(p =>
 p.id === plannerId
 ? { ...p, is_active: statusResult.new_status }
 : p
 ));

 alert(`Planner ${isActivating ? 'activated' : 'deactivated'} successfully`);

 // Refresh data to get updated subscription info
 setTimeout(() => window.location.reload(), 1000);

 } catch (error) {
 console.error('Error updating planner status:', error);
 alert('Failed to update planner status');
 }
 };

 const handleAssignPlan = async (plannerId: string, planId: string) => {
 try {
 const baseUrl = getApiBaseUrl();
 // First, cancel existing subscription if any
 try {
 await fetch(`${baseUrl}/users/${plannerId}/subscription`, {
 method: 'DELETE',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 },
 credentials: 'include',
 });
 } catch (error) {
 // Ignore if no existing subscription
 }
 // Assign new subscription
 const response = await fetch(`${baseUrl}/users/${plannerId}/subscription`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 },
 credentials: 'include',
 body: JSON.stringify({
 plan_id: planId,
 billing_interval: 'monthly',
 trial_days: parseInt(prompt('Enter trial days (0 for no trial, 150 for 5 months):') || '14', 10)
 })
 });

 if (response.ok) {
 alert('Plan assigned successfully');
 // Refresh to get updated data
 window.location.reload();
 } else {
 const error = await response.text();
 throw new Error(error);
 }
 } catch (error) {
 console.error('Error assigning plan:', error);
 alert('Failed to assign plan');
 }
 };

 if (loading) {
 return (
 <div className="flex items-center justify-center py-24">
 <div className="text-center">
 <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
 <p className="text-gray-600 dark:text-gray-400">Loading SAAS Dashboard...</p>
 </div>
 </div>
 );
 }

 return (
 <div className="space-y-6">
 <PageHeader
 title="SaaS Management"
 description="Platform analytics, subscription plans, and configuration"
 />

 {/* Navigation Tabs */}
 <div className="border-b border-gray-200 dark:border-gray-700">
 <nav className="flex space-x-8">
 {[
 { key: 'overview', label: 'Overview' },
 { key: 'plans', label: 'Subscription Plans' },
 { key: 'reviews', label: 'Customer Reviews' },
 { key: 'ad-config', label: 'Ad Platform' },
 { key: 'vendor-data', label: 'Vendor Data' }
 ].map((tab) => (
 <button
 key={tab.key}
 onClick={() => setActiveTab(tab.key as any)}
 className={`py-4 px-1 border-b-2 font-medium text-sm ${
 activeTab === tab.key
 ? 'border-wedding-rose text-wedding-rose'
 : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
 }`}
 >
 {tab.label}
 </button>
 ))}
 </nav>
 </div>

 {/* Content */}
 <div>
 {activeTab === 'overview' && (
 <div className="space-y-6">
   {/* Timeframe selector */}
   <div className="flex items-center justify-between">
     <p className="text-sm text-gray-500 dark:text-gray-400">
       {metrics ? (
         <>
           Updated {formatDateTime(metrics.generated_at, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })}
           {' · '}
           {TIMEFRAME_OPTIONS.find((o) => o.value === metrics.timeframe)?.label || metrics.timeframe}
         </>
       ) : 'Loading analytics…'}
     </p>
     <select
       value={metricsTimeframe}
       onChange={(e) => handleTimeframeChange(e.target.value as TimeframeKey)}
       className="rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 px-4 py-2 text-sm font-medium text-slate-900 dark:text-white shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
     >
       {TIMEFRAME_OPTIONS.map((option) => (
         <option key={option.value} value={option.value}>{option.label}</option>
       ))}
     </select>
   </div>

   {metricsLoading && (
     <div className="flex items-center justify-center py-4">
       <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
     </div>
   )}

   {metrics && (
     <>
       {/* ── User Growth ── */}
       <section className="space-y-4">
         <h2 className="text-xl font-semibold text-gray-900 dark:text-white">User Growth</h2>
         <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
           <button
             type="button"
             onClick={() => openAccountsDirectory('all')}
             className="w-full text-left"
           >
           <Card className="p-6 transition-shadow hover:shadow-xl">
             <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Accounts</p>
             <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{formatNumber(metrics.users.total)}</p>
             <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Active Roles: {roleBreakdown.length}</p>
           </Card>
           </button>
           <Card className="p-6">
             <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Active This Period</p>
             <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{formatNumber(metrics.users.active)}</p>
             <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Signed in during the selected timeframe</p>
           </Card>
           <Card className="p-6">
             <p className="text-sm font-medium text-gray-500 dark:text-gray-400">New Accounts</p>
             <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{formatNumber(metrics.users.new_in_period)}</p>
             <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Within selected timeframe</p>
           </Card>
           <Card className="p-6">
             <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Role Distribution</p>
             <div className="mt-3 flex flex-wrap gap-2 text-xs">
               {roleBreakdown.map(({ role, count }) => (
                 <button
                   key={role}
                   type="button"
                   onClick={() => openAccountsDirectory(role)}
                   className="rounded-full bg-gray-100 dark:bg-slate-700 px-3 py-1 text-gray-900 dark:text-white shadow-sm transition-colors hover:bg-gray-200 dark:hover:bg-slate-600"
                 >
                   {role.replace('_', ' ')} · {formatNumber(count)}
                 </button>
               ))}
               {roleBreakdown.length === 0 && <span className="text-gray-500 dark:text-gray-400">No accounts recorded.</span>}
             </div>
           </Card>
         </div>
       </section>

       {/* ── Subscription & Revenue ── */}
       <section className="space-y-4">
         <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Subscription &amp; Revenue</h2>
         <div className="grid gap-6 lg:grid-cols-3">
           <Card className="p-6">
             <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Active Subscriptions</p>
             <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">
               {formatNumber(metrics.subscriptions.status_breakdown.active)}
             </p>
             <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
               Total subscription records {formatNumber(metrics.subscriptions.total)}
             </p>
             <ul className="mt-3 space-y-1 text-sm text-gray-600 dark:text-gray-400">
               {statusBreakdown.map(({ status, count }) => (
                 <li key={status} className="flex justify-between">
                   <span className="capitalize">{status.replace('_', ' ')}</span>
                   <span>{formatNumber(count)}</span>
                 </li>
               ))}
             </ul>
           </Card>
           <Card className="p-6">
             <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Recurring Revenue</p>
             <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">
               {formatCurrency(metrics.subscriptions.monthly_recurring_revenue)}
             </p>
             <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
               Annual Projection {formatCurrency(metrics.subscriptions.projected_annual_revenue)}
             </p>
             <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
               Yearly Contracts {formatCurrency(metrics.subscriptions.yearly_recurring_revenue)}
             </p>
             <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
               Trials excluded from recurring revenue totals
             </p>
           </Card>
           <Card className="p-6">
             <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Subscription Plans</p>
             <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{metrics.subscriptions.active_plans}</p>
             <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Active plans available to assign</p>
           </Card>
         </div>

         {/* Plan Breakdown table */}
         <Card className="overflow-hidden">
           <div className="border-b border-gray-200 dark:border-slate-700 px-6 py-4">
             <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Plan Breakdown</h3>
           </div>
           <div className="overflow-x-auto">
             <table className="min-w-full divide-y divide-gray-200 dark:divide-slate-700 text-sm">
               <thead className="bg-gray-50 dark:bg-slate-700 text-left text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                 <tr>
                   <th className="px-6 py-3">Plan</th>
                   <th className="px-6 py-3">Active Users</th>
                   <th className="px-6 py-3">Trial Users</th>
                   <th className="px-6 py-3">MRR</th>
                   <th className="px-6 py-3">ARR</th>
                 </tr>
               </thead>
               <tbody className="divide-y divide-gray-200 dark:divide-slate-700 text-gray-700 dark:text-gray-300">
                 {Object.keys(metrics.subscriptions.plan_breakdown).length === 0 && (
                   <tr>
                     <td className="px-6 py-4" colSpan={5}>
                       No subscription plan activity recorded yet.
                     </td>
                   </tr>
                 )}
                 {Object.entries(metrics.subscriptions.plan_breakdown).map(([planId, plan]) => (
                   <tr key={planId} className="hover:bg-gray-50 dark:hover:bg-slate-700">
                     <td className="px-6 py-4 font-medium text-gray-900 dark:text-white">
                       {plan.name || planId}
                     </td>
                     <td className="px-6 py-4">{formatNumber(plan.active_users ?? 0)}</td>
                     <td className="px-6 py-4">{formatNumber(plan.trial_users ?? 0)}</td>
                     <td className="px-6 py-4">{formatCurrency(plan.monthly_revenue)}</td>
                     <td className="px-6 py-4">{formatCurrency(plan.annual_revenue)}</td>
                   </tr>
                 ))}
               </tbody>
             </table>
           </div>
         </Card>
       </section>

       {/* ── Operational Load ── */}
       <section className="space-y-4">
         <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Operational Load</h2>
         <div className="grid gap-6 lg:grid-cols-2">
           <Card className="p-6">
             <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Wedding Projects</h3>
             <div className="mt-4 grid grid-cols-2 gap-4 text-sm text-gray-600 dark:text-gray-400">
               <div>
                 <p className="font-medium text-gray-900 dark:text-white">Total Weddings</p>
                 <p className="text-2xl font-semibold text-gray-900 dark:text-white">{formatNumber(metrics.operations.weddings.total)}</p>
               </div>
               <div>
                 <p className="font-medium text-gray-900 dark:text-white">Active</p>
                 <p className="text-2xl font-semibold text-gray-900 dark:text-white">{formatNumber(metrics.operations.weddings.active)}</p>
               </div>
               <div>
                 <p className="font-medium text-gray-900 dark:text-white">Upcoming</p>
                 <p className="text-2xl font-semibold text-gray-900 dark:text-white">{formatNumber(metrics.operations.weddings.upcoming)}</p>
               </div>
               <div>
                 <p className="font-medium text-gray-900 dark:text-white">New This Period</p>
                 <p className="text-2xl font-semibold text-gray-900 dark:text-white">{formatNumber(metrics.operations.weddings.created_in_period)}</p>
               </div>
             </div>
             <div className="mt-4 rounded-lg bg-gray-50 dark:bg-slate-700 px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
               <p>Guests managed: {formatNumber(metrics.operations.weddings.guest_total)}</p>
               <p>RSVP records: {formatNumber(metrics.operations.weddings.rsvp_total)}</p>
             </div>
           </Card>

           <Card className="p-6">
             <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Form Engagement</h3>
             <div className="mt-4 grid grid-cols-2 gap-4 text-sm text-gray-600 dark:text-gray-400">
               <div>
                 <p className="font-medium text-gray-900 dark:text-white">Active Forms</p>
                 <p className="text-2xl font-semibold text-gray-900 dark:text-white">{formatNumber(metrics.operations.forms.total)}</p>
               </div>
               <div>
                 <p className="font-medium text-gray-900 dark:text-white">New Forms</p>
                 <p className="text-2xl font-semibold text-gray-900 dark:text-white">{formatNumber(metrics.operations.forms.new_in_period)}</p>
               </div>
               <div>
                 <p className="font-medium text-gray-900 dark:text-white">Responses</p>
                 <p className="text-2xl font-semibold text-gray-900 dark:text-white">{formatNumber(metrics.operations.forms.responses_total)}</p>
               </div>
               <div>
                 <p className="font-medium text-gray-900 dark:text-white">Responses This Period</p>
                 <p className="text-2xl font-semibold text-gray-900 dark:text-white">{formatNumber(metrics.operations.forms.responses_in_period)}</p>
               </div>
             </div>
           </Card>
         </div>

         <Card className="p-6">
           <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Communication Volume</h3>
           <div className="mt-4 grid gap-6 md:grid-cols-3 text-sm text-gray-600 dark:text-gray-400">
             <div>
               <p className="font-medium text-gray-900 dark:text-white">Notifications Sent</p>
               <p className="text-2xl font-semibold text-gray-900 dark:text-white">{formatNumber(metrics.operations.communications.notifications_sent)}</p>
               <p className="text-xs text-gray-500 dark:text-gray-400">
                 +{formatNumber(metrics.operations.communications.notifications_in_period)} this timeframe
               </p>
             </div>
             <div>
               <p className="font-medium text-gray-900 dark:text-white">Email Logs</p>
               <p className="text-2xl font-semibold text-gray-900 dark:text-white">{formatNumber(metrics.operations.communications.email_logs_total)}</p>
               <p className="text-xs text-gray-500 dark:text-gray-400">
                 {formatNumber(metrics.operations.communications.emails_sent_in_period)} successful deliveries
               </p>
             </div>
             <div>
               <p className="font-medium text-gray-900 dark:text-white">AI Automations</p>
               <p className="text-2xl font-semibold text-gray-900 dark:text-white">{formatNumber(metrics.operations.communications.ai_events_total)}</p>
               <p className="text-xs text-gray-500 dark:text-gray-400">
                 {formatNumber(metrics.operations.communications.ai_events_in_period)} requests this timeframe
               </p>
             </div>
           </div>
         </Card>
       </section>

       {/* ── Recent Signups (kept from original overview) ── */}
       {planners.length > 0 && (
         <section className="space-y-4">
           <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Recent Signups</h2>
           <Card className="p-6">
             <div className="space-y-3">
               {planners.slice(0, 5).map((planner) => (
                 <div key={planner.id} className="flex items-center justify-between">
                   <div>
                     <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{planner.companyName}</p>
                     <p className="text-sm text-gray-500 dark:text-gray-400">{planner.email}</p>
                   </div>
                   <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                     planner.is_active
                       ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                       : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-400'
                   }`}>
                     {planner.is_active ? 'Active' : 'Inactive'}
                   </span>
                 </div>
               ))}
             </div>
           </Card>
         </section>
       )}

       {/* ── Product Health (Behavioral Analytics) ── */}
       {behavioralLoading && (
         <div className="flex items-center justify-center py-4">
           <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-600"></div>
           <span className="ml-2 text-sm text-gray-500">Loading product metrics...</span>
         </div>
       )}

       {safeBehavioralMetrics && (
         <>
           {/* North Star + WAU + Stickiness */}
           <section className="space-y-4">
             <h2 className="text-xl font-semibold text-gray-900 dark:text-white flex items-center gap-2">
               <Activity className="h-5 w-5 text-indigo-600" />
               Product Health
             </h2>
             <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
               <Card className="p-6 border-l-4 border-l-indigo-600">
                 <p className="text-sm font-medium text-gray-500 dark:text-gray-400">North Star: Active Engaged Weddings</p>
	                 <p className="mt-2 text-3xl font-bold text-indigo-600">{safeBehavioralMetrics.engagement_signals.north_star_metric}</p>
                 <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Weddings with guest activity this week</p>
               </Card>
               <Card className="p-6">
                 <div className="flex items-center justify-between">
                   <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Weekly Active Users</p>
	                   {safeBehavioralMetrics.weekly_active_users.change !== 0 && (
	                     <span className={`flex items-center gap-1 text-xs font-medium ${
	                       safeBehavioralMetrics.weekly_active_users.change > 0 ? 'text-green-600' : 'text-red-600'
	                     }`}>
	                       {safeBehavioralMetrics.weekly_active_users.change > 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
	                       {safeBehavioralMetrics.weekly_active_users.change > 0 ? '+' : ''}{safeBehavioralMetrics.weekly_active_users.change_percent}%
	                     </span>
	                   )}
	                 </div>
	                 <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{safeBehavioralMetrics.weekly_active_users.current}</p>
	                 <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">vs {safeBehavioralMetrics.weekly_active_users.previous_week} last week</p>
               </Card>
               <Card className="p-6">
                 <p className="text-sm font-medium text-gray-500 dark:text-gray-400">MAU</p>
	                 <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{safeBehavioralMetrics.weekly_active_users.mau}</p>
                 <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Monthly active users</p>
               </Card>
               <Card className="p-6">
                 <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Stickiness (WAU/MAU)</p>
	                 <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{safeBehavioralMetrics.weekly_active_users.stickiness_ratio}%</p>
                 <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Higher = more engaged user base</p>
               </Card>
             </div>
           </section>

           {/* Activation Funnel */}
           <section className="space-y-4">
             <h2 className="text-xl font-semibold text-gray-900 dark:text-white flex items-center gap-2">
               <Zap className="h-5 w-5 text-amber-500" />
               Activation Funnel
               <span className="text-sm font-normal text-gray-500 dark:text-gray-400">(Last 30 Days)</span>
             </h2>
             <Card className="p-6">
               <div className="space-y-4">
	                 {safeBehavioralMetrics.activation_funnel.steps.map((step, idx) => (
                   <div key={step.name}>
                     <div className="flex items-center justify-between mb-1">
                       <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{step.name}</span>
                       <span className="text-sm text-gray-500 dark:text-gray-400">{step.count} ({step.rate}%)</span>
                     </div>
                     <div className="w-full bg-gray-200 dark:bg-slate-700 rounded-full h-3">
                       <div
                         className={`h-3 rounded-full transition-all duration-500 ${
                           idx === 0 ? 'bg-indigo-600' :
                           idx === 1 ? 'bg-indigo-500' :
                           idx === 2 ? 'bg-blue-500' :
                           idx === 3 ? 'bg-cyan-500' :
                           'bg-emerald-500'
                         }`}
                         style={{ width: `${Math.max(step.rate, 2)}%` }}
                       />
                     </div>
                   </div>
                 ))}
                 <div className="pt-3 border-t border-gray-200 dark:border-slate-700">
                   <p className="text-sm text-gray-600 dark:text-gray-400">
	                     Signup → Value conversion: <strong className="text-gray-900 dark:text-white">{safeBehavioralMetrics.activation_funnel.conversion_rate}%</strong>
                   </p>
                 </div>
               </div>
             </Card>
           </section>

           {/* Retention Cohorts + MRR Movement side by side */}
           <section className="space-y-4">
             <div className="grid gap-6 lg:grid-cols-2">
               {/* Retention Cohorts */}
               <Card className="p-6">
                 <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2 mb-4">
                   <Users className="h-5 w-5 text-blue-600" />
                   Retention Cohorts
                 </h3>
                 <div className="overflow-x-auto">
                   <table className="w-full text-sm">
                     <thead>
                       <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-slate-700">
                         <th className="pb-2 pr-4 font-medium">Cohort</th>
                         <th className="pb-2 pr-4 font-medium text-center">Size</th>
                         <th className="pb-2 pr-4 font-medium text-center">D7</th>
                         <th className="pb-2 pr-4 font-medium text-center">D30</th>
                         <th className="pb-2 pr-4 font-medium text-center">D60</th>
                         <th className="pb-2 font-medium text-center">D90</th>
                       </tr>
                     </thead>
                     <tbody>
	                       {safeBehavioralMetrics.retention_cohorts.cohorts.map((cohort) => (
                         <tr key={cohort.month} className="border-b border-gray-100 dark:border-slate-700/50 last:border-0">
                           <td className="py-2 pr-4 font-medium text-gray-900 dark:text-white">{cohort.month}</td>
                           <td className="py-2 pr-4 text-center text-gray-600 dark:text-gray-400">{cohort.cohort_size}</td>
                           {['d7', 'd30', 'd60', 'd90'].map((key) => {
                             const val = cohort[key as keyof typeof cohort] as number | null;
                             return (
                               <td key={key} className="py-2 pr-4 text-center">
                                 {val === null ? (
                                   <span className="text-gray-400">—</span>
                                 ) : (
                                   <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                                     val >= 60 ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                                     val >= 30 ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' :
                                     'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                                   }`}>
                                     {val}%
                                   </span>
                                 )}
                               </td>
                             );
                           })}
                         </tr>
                       ))}
                     </tbody>
                   </table>
                 </div>
               </Card>

               {/* MRR Movement */}
               <Card className="p-6">
                 <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2 mb-4">
                   <DollarSign className="h-5 w-5 text-green-600" />
                   MRR Movement
                   <span className="text-sm font-normal text-gray-500 dark:text-gray-400">(Last 30 Days)</span>
                 </h3>
                 <div className="space-y-4">
                   <div className="flex items-center justify-between">
                     <span className="text-sm text-gray-600 dark:text-gray-400">Current MRR</span>
	                     <span className="text-2xl font-bold text-gray-900 dark:text-white">${safeBehavioralMetrics.mrr_movement.current_mrr.toLocaleString()}</span>
                   </div>
                   <div className="space-y-2 pt-3 border-t border-gray-200 dark:border-slate-700">
                     <div className="flex items-center justify-between">
                       <span className="text-sm text-gray-600 dark:text-gray-400 flex items-center gap-2">
                         <span className="inline-block w-2 h-2 rounded-full bg-green-500" /> New MRR
                       </span>
	                       <span className="text-sm font-medium text-green-600">+${safeBehavioralMetrics.mrr_movement.new_mrr.toLocaleString()}</span>
                     </div>
                     <div className="flex items-center justify-between">
                       <span className="text-sm text-gray-600 dark:text-gray-400 flex items-center gap-2">
                         <span className="inline-block w-2 h-2 rounded-full bg-red-500" /> Churned MRR
                       </span>
	                       <span className="text-sm font-medium text-red-600">-${safeBehavioralMetrics.mrr_movement.churned_mrr.toLocaleString()}</span>
                     </div>
                     <div className="flex items-center justify-between pt-2 border-t border-gray-200 dark:border-slate-700">
                       <span className="text-sm font-medium text-gray-900 dark:text-white">Net Change</span>
	                       <span className={`text-sm font-bold ${safeBehavioralMetrics.mrr_movement.net_change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
	                         {safeBehavioralMetrics.mrr_movement.net_change >= 0 ? '+' : ''}${safeBehavioralMetrics.mrr_movement.net_change.toLocaleString()}
	                         <span className="text-xs ml-1">({safeBehavioralMetrics.mrr_movement.net_change_percent}%)</span>
	                       </span>
                     </div>
                   </div>
                   <div className="pt-3 border-t border-gray-200 dark:border-slate-700">
                     <div className="flex items-center justify-between">
                       <span className="text-sm text-gray-600 dark:text-gray-400">Trial → Paid Conversions</span>
	                       <span className="text-sm font-medium text-gray-900 dark:text-white">{safeBehavioralMetrics.mrr_movement.trial_conversions}</span>
                     </div>
                     <div className="flex items-center justify-between mt-1">
                       <span className="text-sm text-gray-600 dark:text-gray-400">Conversion Rate</span>
	                       <span className="text-sm font-medium text-gray-900 dark:text-white">{safeBehavioralMetrics.mrr_movement.trial_conversion_rate}%</span>
                     </div>
                   </div>
                 </div>
               </Card>
             </div>
           </section>

           {/* RSVP Velocity + Platform Response Rate */}
           <section className="space-y-4">
             <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Engagement Velocity</h2>
             <div className="grid gap-6 md:grid-cols-3">
               <Card className="p-6">
                 <div className="flex items-center justify-between">
                   <p className="text-sm font-medium text-gray-500 dark:text-gray-400">RSVPs This Week</p>
	                   {safeBehavioralMetrics.engagement_signals.rsvp_velocity.trend !== 'flat' && (
	                     <span className={`flex items-center gap-1 text-xs font-medium ${
	                       safeBehavioralMetrics.engagement_signals.rsvp_velocity.trend === 'up' ? 'text-green-600' : 'text-red-600'
	                     }`}>
	                       {safeBehavioralMetrics.engagement_signals.rsvp_velocity.trend === 'up' ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
	                       {safeBehavioralMetrics.engagement_signals.rsvp_velocity.change > 0 ? '+' : ''}{safeBehavioralMetrics.engagement_signals.rsvp_velocity.change}
	                     </span>
	                   )}
	                 </div>
	                 <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{safeBehavioralMetrics.engagement_signals.rsvp_velocity.current_7d}</p>
	                 <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">vs {safeBehavioralMetrics.engagement_signals.rsvp_velocity.previous_7d} previous week</p>
               </Card>
               <Card className="p-6">
                 <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Platform Response Rate</p>
	                 <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{safeBehavioralMetrics.engagement_signals.platform_response_rate}%</p>
                 <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Of invited guests who responded</p>
               </Card>
               <Card className="p-6">
                 <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Active Engaged Weddings</p>
	                 <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{safeBehavioralMetrics.engagement_signals.active_engaged_weddings}</p>
                 <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">With guest activity in last 7 days</p>
               </Card>
             </div>
           </section>
         </>
       )}
     </>
   )}
 </div>
 )}

 {activeTab === 'plans' && (
 <div className="space-y-6">
 <div className="flex justify-between items-center">
 <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Subscription Plans</h2>
 <button
 onClick={handleCreatePlan}
 className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
 >
 Create New Plan
 </button>
 </div>

 <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
 {plans.length === 0 ? (
 <div className="col-span-3 text-center py-12 bg-gray-50 dark:bg-slate-700 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600">
 <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
 </svg>
 <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">No subscription plans</h3>
 <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Get started by creating your first subscription plan.</p>
 <button
 onClick={handleCreatePlan}
 className="mt-4 inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
 >
 Create Plan
 </button>
 </div>
 ) : plans.map((plan) => {
 // Convert features object to array for display
 const featuresArray = plan.features ? Object.entries(plan.features)
 .filter(([key, value]) => value === true)
 .map(([key]) => key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()))
 : [];

 return (
 <Card key={plan._id} className="p-6">
 <div className="flex justify-between items-start mb-4">
 <h3 className="text-xl font-semibold">{plan.name}</h3>
 <span className={`px-2 py-1 rounded text-xs ${
 plan.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
 }`}>
 {plan.is_active ? 'Active' : 'Inactive'}
 </span>
 </div>

 {plan.description && (
 <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">{plan.description}</p>
 )}

 <div className="text-3xl font-bold text-blue-600 mb-4">
 {plan.price_monthly === 0 ? 'Free' : `$${plan.price_monthly}/month`}
 </div>

 <ul className="space-y-2 mb-6">
 {featuresArray.slice(0, 4).map((feature, idx) => (
 <li key={idx} className="text-sm text-gray-600 dark:text-gray-400 flex items-center">
 <span className="text-green-500 mr-2"></span>
 {feature}
 </li>
 ))}
 {featuresArray.length > 4 && (
 <li className="text-sm text-gray-500 dark:text-gray-400">
 +{featuresArray.length - 4} more features
 </li>
 )}
 </ul>
 <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1 mb-4">
 <p>Max Weddings: {plan.max_weddings === -1 ? 'Unlimited' : plan.max_weddings}</p>
 <p>AI Credits: {plan.ai_credits_monthly}/month</p>
 <p>Storage: {plan.storage_gb}GB</p>
 <p>
 Billing Model:{' '}
 <span className={plan.is_metered ? 'text-blue-600 dark:text-blue-400 font-medium' : 'text-emerald-700 dark:text-emerald-300 font-medium'}>
 {formatBillingModel(plan)}
 </span>
 </p>
 </div>

 <div className="space-y-2">
 <button
 onClick={() => handleEditPlan(plan)}
 className="w-full bg-blue-100 text-blue-800 py-2 px-4 rounded hover:bg-blue-200 transition-colors"
 >
 Edit Plan
 </button>
 <button
 onClick={() => handleDeletePlan(plan._id)}
 className="w-full bg-red-100 text-red-800 py-2 px-4 rounded hover:bg-red-200 transition-colors"
 >
 Delete Plan
 </button>
 </div>
 </Card>
 );
 })}
 </div>
 </div>
 )}

 {activeTab === 'reviews' && (
   <CustomerReviewsTab />
 )}

 {activeTab === 'ad-config' && (
   <AdPlatformConfigTab />
 )}

 {activeTab === 'vendor-data' && (
   <VendorDataTab />
 )}

 </div>

 {/* Create/Edit Plan Modal */}
 {showCreatePlanModal && (
 <PlanModal
 isEditing={!!editingPlan}
 plan={editingPlan}
 onSave={handleSavePlan}
 onClose={() => {
 setShowCreatePlanModal(false);
 setEditingPlan(null);
 }}
 />
 )}
 </div>
 );
};

// Simple Plan Modal Component
const PlanModal = ({ isEditing, plan, onSave, onClose }: {
 isEditing: boolean;
 plan: SubscriptionPlan | null;
 onSave: (planData: any) => void;
 onClose: () => void;
}) => {
 const [formData, setFormData] = useState({
 name: plan?.name || '',
 description: plan?.description || '',
 price_monthly: plan?.price_monthly || 0,
 price_yearly: plan?.price_yearly || 0,
 max_weddings: plan?.max_weddings || 1,
 max_guests_per_wedding: plan?.max_guests_per_wedding || 100,
 ai_credits_monthly: plan?.ai_credits_monthly || 10,
 storage_gb: plan?.storage_gb || 1,
 staff_seats: plan?.staff_seats || 0,
 trial_days: (plan as any)?.trial_days || 0,
 is_featured: plan?.is_featured || false,
 is_active: plan?.is_active !== false,
 display_order: plan?.display_order ?? plan?.sort_order ?? 0,
 // Metered billing configuration.
 // 2026-05-09: defaults flipped to flat. New plans default to flat-rate
 // billing — match the new pricing strategy. Operator can flip to metered
 // per-plan by checking the box.
 is_metered: (plan as any)?.is_metered === true,
 meter_event_name: (plan as any)?.meter_event_name || '',
 meter_id: (plan as any)?.meter_id || '',
 features: buildPlanFeatureState(plan?.features),
 features_list_text: formatFeatureListInput(plan?.features_list),
 });
 const featureEntries = useMemo(
 () => getPlanFeatureEntries(formData.features),
 [formData.features],
 );

 const handleSubmit = (e: React.FormEvent) => {
 e.preventDefault();
 const { features_list_text, ...planPayload } = formData;
 onSave({
 ...planPayload,
 billing_model: formData.is_metered ? 'metered' : 'flat_rate',
 meter_event_name: formData.is_metered ? formData.meter_event_name : null,
 meter_id: formData.is_metered ? formData.meter_id || null : null,
 features_list: parseFeatureListInput(features_list_text),
 sort_order: formData.display_order,
 });
 };

 return (
 <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
 <div className="bg-white dark:bg-slate-800 rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
 <h2 className="text-2xl font-bold mb-4">
 {isEditing ? 'Edit Plan' : 'Create New Plan'}
 </h2>
 <div className="mb-4 rounded border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-100">
 Billing model: {formData.is_metered ? `Metered (${formData.meter_event_name || 'wedding_active'})` : 'Flat-rate'}
 <span className="block text-xs text-blue-800 dark:text-blue-200">
 {/* SYNC-WITH-SEED: pricing strategy — flat-rate is current default per 2026-05-09 refresh */}
 Flat-rate is the current production pricing model. The metering infrastructure remains available — flip <strong>Enable metered billing</strong> below to opt this single plan into per-wedding billing. Backend guards block unsafe flat-to-metered or metered-to-flat flips while active subscriptions exist.
 </span>
 </div>
 <form onSubmit={handleSubmit} className="space-y-4">
 <div className="grid grid-cols-3 gap-4">
 <div>
<label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Plan Name</label>
 <input
 type="text"
 required
 value={formData.name}
 onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Monthly Price ($)</label>
 <input
 type="number"
 step="0.01"
 min="0"
 value={formData.price_monthly}
 onChange={(e) => setFormData(prev => ({ ...prev, price_monthly: parseFloat(e.target.value) || 0 }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Yearly Price ($)</label>
 <input
 type="number"
 step="0.01"
 min="0"
 value={formData.price_yearly}
 onChange={(e) => setFormData(prev => ({ ...prev, price_yearly: parseFloat(e.target.value) || 0 }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
 <textarea
 value={formData.description}
 onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
 rows={2}
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Free Trial (days)</label>
 <input
 type="number"
 min="0"
 max="365"
 value={formData.trial_days}
 onChange={(e) => setFormData(prev => ({ ...prev, trial_days: parseInt(e.target.value) || 0 }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
 placeholder="0 = no trial"
 />
 <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Set to 0 to disable free trial for this plan</p>
 </div>

 <div className="grid grid-cols-3 gap-4">
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">Max Weddings</label>
 <input
 type="number"
 min="-1"
 value={formData.max_weddings}
 onChange={(e) => setFormData(prev => ({ ...prev, max_weddings: parseInt(e.target.value) || 0 }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
 placeholder="-1 for unlimited"
 />
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Max Guests/Wedding</label>
 <input
 type="number"
 min="-1"
 value={formData.max_guests_per_wedding}
 onChange={(e) => setFormData(prev => ({ ...prev, max_guests_per_wedding: parseInt(e.target.value) || 0 }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
 placeholder="-1 for unlimited"
 />
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">AI Credits/Month</label>
 <input
 type="number"
 min="0"
 value={formData.ai_credits_monthly}
 onChange={(e) => setFormData(prev => ({ ...prev, ai_credits_monthly: parseInt(e.target.value) || 0 }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">Storage (GB)</label>
 <input
 type="number"
 min="0"
 value={formData.storage_gb}
 onChange={(e) => setFormData(prev => ({ ...prev, storage_gb: parseInt(e.target.value) || 0 }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Staff Seats</label>
 <input
 type="number"
 min="0"
 value={formData.staff_seats}
 onChange={(e) => setFormData(prev => ({ ...prev, staff_seats: parseInt(e.target.value) || 0 }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Display Order</label>
 <input
 type="number"
 min="0"
 value={formData.display_order}
 onChange={(e) => setFormData(prev => ({ ...prev, display_order: parseInt(e.target.value) || 0 }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 </div>

 {/* Metered Billing Configuration */}
 <div className="border-t border-gray-200 dark:border-gray-600 pt-4 mt-4">
 <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center">
 <span className="mr-2">Metered Billing</span>
 <span className="text-xs font-normal text-gray-500">(per-wedding billing)</span>
 </h4>
 <div className="space-y-3">
 <label className="flex items-center space-x-2">
 <input
 type="checkbox"
 checked={formData.is_metered}
 onChange={(e) => setFormData(prev => ({ ...prev, is_metered: e.target.checked }))}
 className="rounded"
 />
 <span className="text-sm">Enable metered billing</span>
 </label>
 {formData.is_metered && (
 <div className="grid grid-cols-2 gap-4 ml-6">
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Meter Event Name
 </label>
 <input
 type="text"
 value={formData.meter_event_name}
 onChange={(e) => setFormData(prev => ({ ...prev, meter_event_name: e.target.value }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
 placeholder="wedding_active"
 />
 <p className="text-xs text-gray-500 mt-1">Must match Stripe Billing Meter event name</p>
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Stripe Meter ID
 </label>
 <input
 type="text"
 value={formData.meter_id}
 onChange={(e) => setFormData(prev => ({ ...prev, meter_id: e.target.value }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
 placeholder="mtr_..."
 />
 <p className="text-xs text-gray-500 mt-1">From Stripe Dashboard → Billing → Meters</p>
 </div>
 </div>
 )}
 </div>
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-2">Features</label>
 <div className="grid grid-cols-2 gap-2">
 {featureEntries.map(({ key, label }) => (
 <label key={key} className="flex items-center space-x-2">
 <input
 type="checkbox"
 checked={Boolean(formData.features[key])}
 onChange={(e) => setFormData(prev => ({
 ...prev,
 features: { ...prev.features, [key]: e.target.checked }
 }))}
 className="rounded"
 />
 <span className="text-sm">{label || getPlanFeatureLabel(key)}</span>
 </label>
 ))}
 </div>
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
 Public Feature Highlights
 </label>
 <textarea
 value={formData.features_list_text}
 onChange={(e) => setFormData(prev => ({ ...prev, features_list_text: e.target.value }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
 rows={5}
 placeholder={'One public pricing highlight per line'}
 />
 <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
 These lines appear on public pricing cards and in signup plan selection.
 </p>
 </div>

 <div className="flex items-center space-x-4">
 <label className="flex items-center space-x-2">
 <input
 type="checkbox"
 checked={formData.is_active}
 onChange={(e) => setFormData(prev => ({ ...prev, is_active: e.target.checked }))}
 className="rounded"
 />
 <span className="text-sm">Active</span>
 </label>
 <label className="flex items-center space-x-2">
 <input
 type="checkbox"
 checked={formData.is_featured}
 onChange={(e) => setFormData(prev => ({ ...prev, is_featured: e.target.checked }))}
 className="rounded"
 />
 <span className="text-sm">Featured</span>
 </label>
 </div>

 <div className="flex justify-end space-x-3 pt-4">
 <button
 type="button"
 onClick={onClose}
 className="px-4 py-2 text-gray-600 dark:text-gray-400 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100 hover:bg-gray-50 dark:bg-slate-700"
 >
 Cancel
 </button>
 <button
 type="submit"
 className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
 >
 {isEditing ? 'Update Plan' : 'Create Plan'}
 </button>
 </div>
 </form>
 </div>
 </div>
 );
};

// =============================================================================
// Customer Reviews Tab
// =============================================================================

function CustomerReviewsTab() {
  const { token } = useAdmin();
  const [testimonials, setTestimonials] = useState<Testimonial[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingTestimonial, setEditingTestimonial] = useState<Testimonial | null>(null);
  const [saving, setSaving] = useState(false);

  const fetchTestimonials = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${getApiBaseUrl()}/saas/testimonials`, {
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (res.ok) {
        setTestimonials(await res.json());
      }
    } catch (err) {
      console.error('Failed to fetch testimonials:', err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchTestimonials(); }, [fetchTestimonials]);

  const handleToggle = async (id: string) => {
    try {
      const res = await fetch(`${getApiBaseUrl()}/saas/testimonials/${id}/toggle`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        setTestimonials(prev =>
          prev.map(t => t._id === id ? { ...t, is_active: data.is_active } : t)
        );
        toast.success(data.message);
      }
    } catch (err) {
      toast.error('Failed to toggle testimonial');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this testimonial permanently?')) return;
    try {
      const res = await fetch(`${getApiBaseUrl()}/saas/testimonials/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (res.ok) {
        setTestimonials(prev => prev.filter(t => t._id !== id));
        toast.success('Testimonial deleted');
      }
    } catch (err) {
      toast.error('Failed to delete testimonial');
    }
  };

  const handleSave = async (data: Partial<Testimonial>) => {
    setSaving(true);
    try {
      const isEdit = !!editingTestimonial;
      const url = isEdit
        ? `${getApiBaseUrl()}/saas/testimonials/${editingTestimonial!._id}`
        : `${getApiBaseUrl()}/saas/testimonials`;
      const res = await fetch(url, {
        method: isEdit ? 'PUT' : 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        credentials: 'include',
        body: JSON.stringify(data),
      });
      if (res.ok) {
        toast.success(isEdit ? 'Testimonial updated' : 'Testimonial created');
        setShowModal(false);
        setEditingTestimonial(null);
        fetchTestimonials();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Save failed');
      }
    } catch (err) {
      toast.error('Failed to save testimonial');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Customer Reviews</h2>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Manage testimonials displayed on the SaaS landing page.
          </p>
        </div>
        <button
          onClick={() => { setEditingTestimonial(null); setShowModal(true); }}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          Add Testimonial
        </button>
      </div>

      {testimonials.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 dark:bg-slate-700 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">No testimonials yet</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Add your first customer testimonial to display on the landing page.</p>
          <button
            onClick={() => { setEditingTestimonial(null); setShowModal(true); }}
            className="mt-4 inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
          >
            Add Testimonial
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {testimonials.map((t) => (
            <Card key={t._id} className="p-5">
              <div className="flex justify-between items-start mb-3">
                <div className="flex-1 min-w-0">
                  <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">{t.name}</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {t.role}{t.company ? `, ${t.company}` : ''}
                  </p>
                </div>
                <span className={`flex-shrink-0 ml-2 px-2 py-0.5 rounded text-xs font-medium ${
                  t.is_active
                    ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                    : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                }`}>
                  {t.is_active ? 'Active' : 'Hidden'}
                </span>
              </div>

              <blockquote className="text-sm text-gray-700 dark:text-gray-300 italic mb-4 line-clamp-3">
                &ldquo;{t.quote}&rdquo;
              </blockquote>

              <div className="flex items-center gap-2 text-xs text-gray-400 mb-3">
                <span>Order: {t.display_order}</span>
                {t.updated_at && <span>· Updated {new Date(t.updated_at).toLocaleDateString()}</span>}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => { setEditingTestimonial(t); setShowModal(true); }}
                  className="flex-1 bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400 py-1.5 px-3 rounded text-sm hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors"
                >
                  Edit
                </button>
                <button
                  onClick={() => handleToggle(t._id)}
                  className="flex-1 bg-yellow-50 text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-400 py-1.5 px-3 rounded text-sm hover:bg-yellow-100 dark:hover:bg-yellow-900/30 transition-colors"
                >
                  {t.is_active ? 'Hide' : 'Show'}
                </button>
                <button
                  onClick={() => handleDelete(t._id)}
                  className="flex-1 bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400 py-1.5 px-3 rounded text-sm hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"
                >
                  Delete
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create / Edit Testimonial Modal */}
      {showModal && (
        <TestimonialModal
          testimonial={editingTestimonial}
          saving={saving}
          onSave={handleSave}
          onClose={() => { setShowModal(false); setEditingTestimonial(null); }}
        />
      )}
    </div>
  );
}

function TestimonialModal({
  testimonial,
  saving,
  onSave,
  onClose,
}: {
  testimonial: Testimonial | null;
  saving: boolean;
  onSave: (data: Partial<Testimonial>) => void;
  onClose: () => void;
}) {
  const [form, setForm] = useState({
    name: testimonial?.name || '',
    company: testimonial?.company || '',
    role: testimonial?.role || '',
    quote: testimonial?.quote || '',
    display_order: testimonial?.display_order ?? 0,
    is_active: testimonial?.is_active ?? true,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(form);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
            {testimonial ? 'Edit Testimonial' : 'Add Testimonial'}
          </h3>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name *</label>
              <input
                type="text"
                required
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                placeholder="Maya Glenn"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Role</label>
                <input
                  type="text"
                  value={form.role}
                  onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
                  className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  placeholder="Director of Events"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Company</label>
                <input
                  type="text"
                  value={form.company}
                  onChange={e => setForm(f => ({ ...f, company: e.target.value }))}
                  className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  placeholder="Aurora Collective"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Quote *</label>
              <textarea
                required
                rows={4}
                value={form.quote}
                onChange={e => setForm(f => ({ ...f, quote: e.target.value }))}
                className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                placeholder="The Special Wedding replaced five subscriptions overnight..."
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Display Order</label>
                <input
                  type="number"
                  value={form.display_order}
                  onChange={e => setForm(f => ({ ...f, display_order: parseInt(e.target.value) || 0 }))}
                  className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
                  min={0}
                />
              </div>
              <div className="flex items-end pb-1">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))}
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">Active on landing page</span>
                </label>
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 text-sm font-medium"
              >
                {saving ? 'Saving...' : testimonial ? 'Update' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Ad Platform Configuration Tab
// =============================================================================

type AdConfigSubTab = 'settings' | 'export' | 'pipeline';

const AD_EXPORT_DATASETS = [
  { value: 'vendor_accounts', label: 'Vendor Accounts (all vendors)' },
  { value: 'active_campaigns', label: 'Active Campaigns' },
  { value: 'all_campaigns', label: 'All Campaigns (incl. completed)' },
  { value: 'campaign_performance', label: 'Campaign Performance Metrics' },
  { value: 'ad_events', label: 'Ad Events (raw)' },
  { value: 'ad_leads', label: 'Ad Leads' },
  { value: 'marketing_leads', label: 'Marketing Leads (template downloads)' },
  { value: 'planner_feedback', label: 'Planner Feedback (hides/suppressions)' },
  { value: 'campaign_daily_stats', label: 'Campaign Daily Stats (rollups)' },
  { value: 'placement_daily_stats', label: 'Placement Daily Stats' },
  { value: 'fraud_signals', label: 'Fraud Signals' },
];

const AD_EXPORT_DATE_RANGES = [
  { value: 'last_7_days', label: 'Last 7 days' },
  { value: 'last_30_days', label: 'Last 30 days' },
  { value: 'last_90_days', label: 'Last 90 days' },
  { value: 'all_time', label: 'All time' },
];

function AdPlatformConfigTab() {
  const { token, apiRequest } = useAdmin();
  const [subTab, setSubTab] = useState<AdConfigSubTab>('settings');
  const [config, setConfig] = useState<PlatformConfig | null>(null);
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editedConfig, setEditedConfig] = useState<Partial<PlatformConfig>>({});
  const [exportDataset, setExportDataset] = useState('vendor_accounts');
  const [exportDateRange, setExportDateRange] = useState('last_30_days');
  const [exportResult, setExportResult] = useState<Awaited<ReturnType<typeof exportAdminData>> | null>(null);
  const [exporting, setExporting] = useState(false);

  const loadData = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const data = await getAdminConfig(apiRequest);
      if (!data) {
        return;
      }
      setConfig(data);
      setEditedConfig(data);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [apiRequest, token]);

  useEffect(() => { loadData(); }, [loadData]);

  const loadPipeline = useCallback(async () => {
    if (!token) {
      return;
    }

    try {
      const data = await getAdminPipelineStatus(apiRequest);
      if (!data) {
        return;
      }
      setPipeline(data);
    } catch (err: any) {
      toast.error(err.message);
    }
  }, [apiRequest, token]);

  useEffect(() => {
    if (subTab === 'pipeline') {
      loadPipeline();
    }
  }, [loadPipeline, subTab]);

  const isDirty = useMemo(() => {
    if (!config) return false;
    return JSON.stringify(editedConfig) !== JSON.stringify(config);
  }, [config, editedConfig]);

  const handleSave = async () => {
    if (!token) {
      toast.error('Authentication required');
      return;
    }

    try {
      setSaving(true);
      const updated = await updateAdminConfig(apiRequest, editedConfig);
      if (!updated) {
        return;
      }
      setConfig(updated);
      setEditedConfig(updated);
      toast.success('Configuration saved');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading ad platform config...</p>
        </div>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="text-center py-12 bg-gray-50 dark:bg-slate-700 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600">
        <Settings className="mx-auto h-12 w-12 text-gray-400 mb-2" />
        <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">No configuration</h3>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Ad platform configuration not available.</p>
      </div>
    );
  }

  const toggleField = (key: keyof PlatformConfig) => {
    setEditedConfig((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const setNumberField = (key: keyof PlatformConfig, value: string) => {
    const num = parseInt(value, 10);
    if (!isNaN(num)) {
      setEditedConfig((prev) => ({ ...prev, [key]: num }));
    }
  };

  const setStringField = (key: keyof PlatformConfig, value: string) => {
    setEditedConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handleExport = async () => {
    if (!token) {
      toast.error('Authentication required');
      return;
    }

    try {
      setExporting(true);
      const result = await exportAdminData(apiRequest, exportDataset, exportDateRange, 'json');
      if (!result) {
        return;
      }
      setExportResult(result);
      toast.success(`Exported ${result.row_count} rows`);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setExporting(false);
    }
  };

  const downloadExport = () => {
    if (!exportResult) return;
    const blob = new Blob([JSON.stringify(exportResult.rows, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${exportResult.dataset}_${exportResult.date_range}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="scrollbar-thin -mb-px flex min-w-max overflow-x-auto border-b border-gray-200 dark:border-gray-700">
          {(['settings', 'export', 'pipeline'] as AdConfigSubTab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setSubTab(tab)}
              className={`-mb-px shrink-0 whitespace-nowrap border-b-2 px-5 py-2.5 text-sm font-medium ${
                subTab === tab
                  ? 'border-wedding-rose text-wedding-rose'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200'
              }`}
            >
              {tab === 'settings' ? 'Settings' : tab === 'export' ? 'Data Export' : 'Data Pipeline'}
            </button>
          ))}
        </div>

        {subTab === 'settings' && (
          <button
            onClick={handleSave}
            disabled={!isDirty || saving}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        )}
      </div>

      {subTab === 'settings' && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <Card className="p-6">
            <h3 className="mb-4 text-lg font-medium text-gray-900 dark:text-gray-100">Feature Flags</h3>
            <div className="space-y-4">
              {[
                ['ads_enabled', 'Ads Enabled', 'Master toggle for the advertising platform'],
                ['show_sponsored_badge', 'Show Sponsored Badge', 'Display “Sponsored” labels on placement cards'],
                ['enable_event_tracking', 'Enable Event Tracking', 'Track impressions, clicks, and conversions'],
                ['require_creative_review', 'Require Creative Review', 'Require campaign review before ads go live'],
                ['auto_approve_returning_vendors', 'Auto-Approve Returning Vendors', 'Skip review for previously approved vendors'],
              ].map(([field, label, hint]) => (
                <div key={field} className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200">{label}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">{hint}</p>
                  </div>
                  <button
                    onClick={() => toggleField(field as keyof PlatformConfig)}
                    className={`relative h-6 w-11 rounded-full transition-colors ${
                      editedConfig[field as keyof PlatformConfig] ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
                    }`}
                  >
                    <span
                      className={`absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
                        editedConfig[field as keyof PlatformConfig] ? 'translate-x-5' : ''
                      }`}
                    />
                  </button>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="mb-4 text-lg font-medium text-gray-900 dark:text-gray-100">Serving Limits</h3>
            <div className="space-y-4">
              {[
                ['max_sponsored_per_page', 'Max Sponsored Per Page', 1, 10],
                ['impressions_per_session', 'Impressions Per Session', 1, 50],
                ['freq_cap_per_campaign_planner_day', 'Frequency Cap Per Planner / Day', 1, 20],
                ['review_sla_hours', 'Review SLA (hours)', 1, 168],
                ['max_campaigns_per_vendor', 'Max Campaigns Per Vendor', 1, 50],
              ].map(([field, label, min, max]) => (
                <div key={field} className="flex items-center justify-between gap-4">
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-200">{label}</p>
                  <input
                    type="number"
                    value={editedConfig[field as keyof PlatformConfig] ?? ''}
                    onChange={(e) => setNumberField(field as keyof PlatformConfig, e.target.value)}
                    className="w-24 rounded-lg border border-gray-300 bg-white px-2 py-1.5 text-right text-sm text-gray-900 dark:border-gray-600 dark:bg-slate-700 dark:text-gray-100"
                    min={min as number}
                    max={max as number}
                  />
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="mb-4 text-lg font-medium text-gray-900 dark:text-gray-100">Fraud Detection</h3>
            <div className="space-y-4">
              {[
                ['max_clicks_per_planner_campaign_hour', 'Max Clicks / Planner / Campaign / Hour'],
                ['hide_rate_auto_pause_threshold', 'Hide Rate Auto-Pause Threshold'],
                ['click_velocity_window_minutes', 'Click Velocity Window (minutes)'],
              ].map(([field, label]) => (
                <div key={field} className="flex items-center justify-between gap-4">
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-200">{label}</p>
                  <input
                    type="number"
                    value={editedConfig[field as keyof PlatformConfig] ?? ''}
                    onChange={(e) => setNumberField(field as keyof PlatformConfig, e.target.value)}
                    className="w-24 rounded-lg border border-gray-300 bg-white px-2 py-1.5 text-right text-sm text-gray-900 dark:border-gray-600 dark:bg-slate-700 dark:text-gray-100"
                  />
                </div>
              ))}
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-200">Auto-Void Suspicious Clicks</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Automatically void clicks from suspected fraud patterns</p>
                </div>
                <button
                  onClick={() => toggleField('auto_void_suspicious_clicks')}
                  className={`relative h-6 w-11 rounded-full transition-colors ${
                    editedConfig.auto_void_suspicious_clicks ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
                  }`}
                >
                  <span className={`absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${editedConfig.auto_void_suspicious_clicks ? 'translate-x-5' : ''}`} />
                </button>
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="mb-4 text-lg font-medium text-gray-900 dark:text-gray-100">Vendor Signup</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-200">Vendor Domain</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Domain used to route approved vendors into the ad portal</p>
                </div>
                <input
                  type="text"
                  value={editedConfig.vendor_domain ?? ''}
                  onChange={(e) => setStringField('vendor_domain', e.target.value)}
                  className="w-64 rounded-lg border border-gray-300 bg-white px-2 py-1.5 text-right text-sm text-gray-900 dark:border-gray-600 dark:bg-slate-700 dark:text-gray-100"
                />
              </div>
              {[
                ['auto_approve_signups', 'Auto-Approve Signups', 'Approve new advertising vendors without manual review'],
                ['require_profile_completion', 'Require Profile Completion', 'Block campaign creation until onboarding profile is complete'],
              ].map(([field, label, hint]) => (
                <div key={field} className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200">{label}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">{hint}</p>
                  </div>
                  <button
                    onClick={() => toggleField(field as keyof PlatformConfig)}
                    className={`relative h-6 w-11 rounded-full transition-colors ${
                      editedConfig[field as keyof PlatformConfig] ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
                    }`}
                  >
                    <span
                      className={`absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
                        editedConfig[field as keyof PlatformConfig] ? 'translate-x-5' : ''
                      }`}
                    />
                  </button>
                </div>
              ))}
              <div className="flex items-center justify-between gap-4">
                <p className="text-sm font-medium text-gray-700 dark:text-gray-200">Minimum Images Per Campaign</p>
                <input
                  type="number"
                  value={editedConfig.min_images_for_campaign ?? ''}
                  onChange={(e) => setNumberField('min_images_for_campaign', e.target.value)}
                  className="w-24 rounded-lg border border-gray-300 bg-white px-2 py-1.5 text-right text-sm text-gray-900 dark:border-gray-600 dark:bg-slate-700 dark:text-gray-100"
                  min={0}
                  max={20}
                />
              </div>
            </div>
          </Card>
        </div>
      )}

      {subTab === 'export' && (
        <div className="space-y-6">
          <Card className="p-6">
            <div className="mb-5 flex flex-wrap items-end gap-4">
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  Data Set
                </label>
                <select
                  value={exportDataset}
                  onChange={(e) => setExportDataset(e.target.value)}
                  className="min-w-[240px] rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-slate-700 dark:text-gray-100"
                >
                  {AD_EXPORT_DATASETS.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  Date Range
                </label>
                <select
                  value={exportDateRange}
                  onChange={(e) => setExportDateRange(e.target.value)}
                  className="min-w-[180px] rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-slate-700 dark:text-gray-100"
                >
                  {AD_EXPORT_DATE_RANGES.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </div>
              <button
                onClick={handleExport}
                disabled={exporting}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Download className="h-4 w-4" />
                {exporting ? 'Exporting...' : 'Export JSON'}
              </button>
            </div>

            {exportResult ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {exportResult.row_count} rows exported from {exportResult.dataset} ({exportResult.date_range})
                  </p>
                  <button
                    onClick={downloadExport}
                    className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
                  >
                    Download file
                  </button>
                </div>
                <div className="max-h-80 overflow-auto rounded-lg border border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-slate-800">
                  <pre className="p-4 text-xs text-gray-700 dark:text-gray-200">
                    {JSON.stringify(exportResult.rows.slice(0, 5), null, 2)}
                    {exportResult.rows.length > 5 ? `\n\n... and ${exportResult.rows.length - 5} more rows` : ''}
                  </pre>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Export marketing and ad-platform data sets as JSON from this central SaaS configuration tab.
              </p>
            )}
          </Card>
        </div>
      )}

      {subTab === 'pipeline' && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <Card className="p-6">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">Rollup Pipeline Status</h3>
              <button
                onClick={loadPipeline}
                className="rounded-lg p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-slate-700 dark:hover:text-gray-200"
                title="Refresh pipeline status"
              >
                <RefreshCw className="h-4 w-4" />
              </button>
            </div>
            {pipeline ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500 dark:text-gray-400">Health</span>
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    pipeline.rollup_health === 'healthy'
                      ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                      : pipeline.rollup_health === 'stale'
                        ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                        : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                  }`}>
                    {pipeline.rollup_health}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500 dark:text-gray-400">Last Rollup</span>
                  <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                    {pipeline.last_rollup_at ? new Date(pipeline.last_rollup_at).toLocaleString() : 'Never'}
                  </span>
                </div>
                {Object.entries(pipeline.ttl_policies ?? {}).map(([collection, days]) => (
                  <div key={collection} className="flex items-center justify-between">
                    <span className="text-sm text-gray-500 dark:text-gray-400">TTL ({collection})</span>
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{days} days</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400">Pipeline status not available.</p>
            )}
          </Card>

          <Card className="p-6">
            <div className="mb-4 flex items-center gap-2">
              <Database className="h-5 w-5 text-gray-500 dark:text-gray-400" />
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">Collection Stats</h3>
            </div>
            {pipeline?.collections ? (
              <div className="space-y-2">
                {Object.entries(pipeline.collections).map(([name, stats]) => (
                  <div key={name} className="flex items-center justify-between">
                    <span className="font-mono text-sm text-gray-500 dark:text-gray-400">{name}</span>
                    <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{formatNumber(stats.count)} docs</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400">Collection stats not available.</p>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

// ─── Vendor Data Tab ────────────────────────────────────────────────────────

const VENDOR_PAGE_SIZE = 25;

const vendorCategoryLabel = (cat: string) =>
  cat.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

function VendorDataTab() {
  const { token } = useAdmin();
  const [showImportModal, setShowImportModal] = useState(false);
  const [vendors, setVendors] = useState<VendorProfile[]>([]);
  const [vendorLoading, setVendorLoading] = useState(false);
  const [vendorSearch, setVendorSearch] = useState('');
  const [vendorCategoryFilter, setVendorCategoryFilter] = useState('');
  const [vendorPage, setVendorPage] = useState(0);
  const [expandedVendorId, setExpandedVendorId] = useState<string | null>(null);
  const [deletingVendorId, setDeletingVendorId] = useState<string | null>(null);
  const [editingVendorId, setEditingVendorId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<VendorProfile>>({});
  const [savingEdit, setSavingEdit] = useState(false);

  const fetchVendors = useCallback(async () => {
    if (!token) return;
    try {
      setVendorLoading(true);
      const PAGE = 100;
      let all: VendorProfile[] = [];
      let skip = 0;
      // Paginate through all vendors (backend caps at 100 per request)
      while (true) {
        const batch = await getVendorDirectory(token, { limit: PAGE, skip });
        all = all.concat(batch);
        if (batch.length < PAGE) break;
        skip += PAGE;
      }
      setVendors(all);
    } catch (err: any) {
      console.error('Failed to fetch vendors:', err);
      toast.error(err.message || 'Failed to load vendor directory');
    } finally {
      setVendorLoading(false);
    }
  }, [token]);

  // Auto-fetch on mount
  useEffect(() => {
    fetchVendors();
  }, [fetchVendors]);

  const handleDeleteVendor = useCallback(async (vendorId: string, businessName: string) => {
    if (!token) return;
    if (!confirm(`Delete "${businessName}" from the vendor directory? This cannot be undone.`)) return;
    try {
      setDeletingVendorId(vendorId);
      await deleteVendorProfile(token, vendorId);
      setVendors((prev) => prev.filter((v) => v._id !== vendorId));
      toast.success(`Deleted "${businessName}"`);
    } catch (err: any) {
      toast.error(err.message || 'Failed to delete vendor');
    } finally {
      setDeletingVendorId(null);
    }
  }, [token]);

  const startEditing = useCallback((v: VendorProfile) => {
    setEditingVendorId(v._id);
    setEditForm({
      business_name: v.business_name,
      email: v.email,
      phone: v.phone || '',
      website: v.website || '',
      address: v.address || '',
      city: v.city || '',
      state: v.state || '',
      service_category: v.service_category,
      service_description: v.service_description || '',
      is_preferred: v.is_preferred,
    });
  }, []);

  const cancelEditing = useCallback(() => {
    setEditingVendorId(null);
    setEditForm({});
  }, []);

  const handleSaveEdit = useCallback(async () => {
    if (!token || !editingVendorId) return;
    try {
      setSavingEdit(true);
      const updated = await updateVendorProfile(token, editingVendorId, editForm);
      setVendors((prev) => prev.map((v) => v._id === editingVendorId ? { ...v, ...updated } : v));
      toast.success('Vendor updated');
      setEditingVendorId(null);
      setEditForm({});
    } catch (err: any) {
      toast.error(err.message || 'Failed to update vendor');
    } finally {
      setSavingEdit(false);
    }
  }, [token, editingVendorId, editForm]);

  const vendorStats = useMemo(() => {
    const byCategory: Record<string, number> = {};
    const byState: Record<string, number> = {};
    for (const v of vendors) {
      const cat = v.service_category || 'unknown';
      byCategory[cat] = (byCategory[cat] || 0) + 1;
      const st = v.state || 'Unknown';
      byState[st] = (byState[st] || 0) + 1;
    }
    return {
      total: vendors.length,
      categories: Object.keys(byCategory).length,
      states: Object.keys(byState).length,
      byCategory: Object.entries(byCategory).sort((a, b) => b[1] - a[1]),
      byState: Object.entries(byState).sort((a, b) => b[1] - a[1]),
    };
  }, [vendors]);

  const filteredVendors = useMemo(() => {
    let list = vendors;
    if (vendorCategoryFilter) {
      list = list.filter((v) => v.service_category === vendorCategoryFilter);
    }
    if (vendorSearch.trim()) {
      const q = vendorSearch.toLowerCase();
      list = list.filter(
        (v) =>
          v.business_name.toLowerCase().includes(q) ||
          (v.city || '').toLowerCase().includes(q) ||
          (v.state || '').toLowerCase().includes(q) ||
          (v.email || '').toLowerCase().includes(q)
      );
    }
    return list;
  }, [vendors, vendorCategoryFilter, vendorSearch]);

  const pagedVendors = useMemo(() => {
    const start = vendorPage * VENDOR_PAGE_SIZE;
    return filteredVendors.slice(start, start + VENDOR_PAGE_SIZE);
  }, [filteredVendors, vendorPage]);

  const vendorTotalPages = Math.max(1, Math.ceil(filteredVendors.length / VENDOR_PAGE_SIZE));

  return (
    <div className="space-y-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Vendor Directory</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Import scraped vendor JSON or manage existing vendors.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchVendors}
            disabled={vendorLoading}
            className="flex items-center gap-2 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${vendorLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={() => setShowImportModal(true)}
            className="flex items-center gap-2 px-4 py-2 border-2 border-dashed border-rose-300 text-rose-500 rounded-lg text-sm font-semibold hover:bg-rose-50 transition-colors dark:border-rose-700 dark:text-rose-400 dark:hover:bg-rose-900/20"
          >
            <Upload className="w-4 h-4" />
            Import Vendors (JSON)
          </button>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="p-4">
          <div className="text-sm text-gray-500 dark:text-gray-400">Total Vendors</div>
          <div className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">
            {vendorLoading ? '...' : vendorStats.total.toLocaleString()}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-500 dark:text-gray-400">Categories</div>
          <div className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">
            {vendorLoading ? '...' : vendorStats.categories}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-500 dark:text-gray-400">States</div>
          <div className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">
            {vendorLoading ? '...' : vendorStats.states}
          </div>
        </Card>
      </div>

      {/* Category breakdown */}
      {vendorStats.byCategory.length > 0 && (
        <Card className="p-4">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">By Category</h4>
          <div className="flex flex-wrap gap-2">
            {vendorStats.byCategory.map(([cat, count]) => (
              <button
                key={cat}
                onClick={() => { setVendorCategoryFilter(vendorCategoryFilter === cat ? '' : cat); setVendorPage(0); }}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  vendorCategoryFilter === cat
                    ? 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300'
                    : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                }`}
              >
                {vendorCategoryLabel(cat)}
                <span className="text-[10px] opacity-70">({count})</span>
              </button>
            ))}
          </div>
        </Card>
      )}

      {/* Search bar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name, city, state, or email..."
            value={vendorSearch}
            onChange={(e) => { setVendorSearch(e.target.value); setVendorPage(0); }}
            className="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:ring-2 focus:ring-rose-500 focus:border-transparent"
          />
        </div>
        <span className="text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap">
          {filteredVendors.length} vendor{filteredVendors.length !== 1 ? 's' : ''}
          {vendorCategoryFilter && (
            <button onClick={() => { setVendorCategoryFilter(''); setVendorPage(0); }} className="ml-2 text-rose-500 hover:text-rose-600 underline">
              clear filter
            </button>
          )}
        </span>
      </div>

      {/* Vendor list */}
      {vendorLoading ? (
        <div className="flex items-center justify-center py-16">
          <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
          <span className="ml-3 text-sm text-gray-500">Loading vendors...</span>
        </div>
      ) : pagedVendors.length === 0 ? (
        <Card className="p-8 text-center">
          <Store className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {vendors.length === 0
              ? 'No vendors imported yet. Use the Import button above to upload a JSON export.'
              : 'No vendors match your search / filter.'}
          </p>
        </Card>
      ) : (
        <div className="space-y-2">
          {pagedVendors.map((v) => {
            const isExpanded = expandedVendorId === v._id;
            return (
              <Card key={v._id} className="overflow-hidden">
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => setExpandedVendorId(isExpanded ? null : v._id)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpandedVendorId(isExpanded ? null : v._id); } }}
                  className="w-full flex items-center gap-4 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors cursor-pointer"
                >
                  {v.logo_url ? (
                    <img src={v.logo_url} alt="" className="w-8 h-8 rounded-full object-cover flex-shrink-0 bg-gray-100" />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center flex-shrink-0">
                      <Store className="w-4 h-4 text-gray-400" />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{v.business_name}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                      {[v.city, v.state].filter(Boolean).join(', ') || 'No location'}
                      {' · '}
                      {vendorCategoryLabel(v.service_category)}
                    </div>
                  </div>
                  {v.website && (
                    <a
                      href={v.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-gray-400 hover:text-rose-500 transition-colors"
                      title="Open website"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); setExpandedVendorId(v._id); startEditing(v); }}
                    className="text-gray-400 hover:text-blue-500 transition-colors p-1"
                    title="Edit vendor"
                  >
                    <Pencil className="w-4 h-4" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteVendor(v._id, v.business_name); }}
                    disabled={deletingVendorId === v._id}
                    className="text-gray-400 hover:text-red-500 transition-colors p-1"
                    title="Delete vendor"
                  >
                    <Trash2 className={`w-4 h-4 ${deletingVendorId === v._id ? 'animate-pulse' : ''}`} />
                  </button>
                  {isExpanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                </div>
                {isExpanded && editingVendorId === v._id ? (
                  /* ── Inline Edit Form ── */
                  <div className="px-4 pb-4 pt-3 border-t border-gray-100 dark:border-gray-700 space-y-3">
                    <div className="grid grid-cols-2 gap-4">
                      <label className="block">
                        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Business Name</span>
                        <input type="text" value={editForm.business_name || ''} onChange={(e) => setEditForm((f) => ({ ...f, business_name: e.target.value }))}
                          className="mt-1 w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-rose-500 focus:border-transparent" />
                      </label>
                      <label className="block">
                        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Email</span>
                        <input type="email" value={editForm.email || ''} onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
                          className="mt-1 w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-rose-500 focus:border-transparent" />
                      </label>
                      <label className="block">
                        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Phone</span>
                        <input type="text" value={editForm.phone || ''} onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value }))}
                          className="mt-1 w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-rose-500 focus:border-transparent" />
                      </label>
                      <label className="block">
                        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Website</span>
                        <input type="url" value={editForm.website || ''} onChange={(e) => setEditForm((f) => ({ ...f, website: e.target.value }))}
                          className="mt-1 w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-rose-500 focus:border-transparent" />
                      </label>
                      <label className="block">
                        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Address</span>
                        <input type="text" value={editForm.address || ''} onChange={(e) => setEditForm((f) => ({ ...f, address: e.target.value }))}
                          className="mt-1 w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-rose-500 focus:border-transparent" />
                      </label>
                      <div className="grid grid-cols-2 gap-3">
                        <label className="block">
                          <span className="text-xs font-medium text-gray-500 dark:text-gray-400">City</span>
                          <input type="text" value={editForm.city || ''} onChange={(e) => setEditForm((f) => ({ ...f, city: e.target.value }))}
                            className="mt-1 w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-rose-500 focus:border-transparent" />
                        </label>
                        <label className="block">
                          <span className="text-xs font-medium text-gray-500 dark:text-gray-400">State</span>
                          <input type="text" value={editForm.state || ''} onChange={(e) => setEditForm((f) => ({ ...f, state: e.target.value }))}
                            className="mt-1 w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-rose-500 focus:border-transparent" />
                        </label>
                      </div>
                      <label className="block">
                        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Service Category</span>
                        <input type="text" value={editForm.service_category || ''} onChange={(e) => setEditForm((f) => ({ ...f, service_category: e.target.value as VendorProfile['service_category'] }))}
                          className="mt-1 w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-rose-500 focus:border-transparent" />
                      </label>
                      <label className="flex items-center gap-2 self-end pb-1">
                        <input type="checkbox" checked={editForm.is_preferred || false} onChange={(e) => setEditForm((f) => ({ ...f, is_preferred: e.target.checked }))}
                          className="rounded border-gray-300 text-rose-500 focus:ring-rose-500" />
                        <span className="text-sm text-gray-700 dark:text-gray-300">Preferred Vendor</span>
                      </label>
                    </div>
                    <label className="block">
                      <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Service Description</span>
                      <textarea value={editForm.service_description || ''} onChange={(e) => setEditForm((f) => ({ ...f, service_description: e.target.value }))} rows={3}
                        className="mt-1 w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-rose-500 focus:border-transparent resize-none" />
                    </label>
                    <div className="flex items-center gap-3 pt-1">
                      <button onClick={handleSaveEdit} disabled={savingEdit}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-rose-500 hover:bg-rose-600 rounded-lg transition-colors disabled:opacity-50">
                        <Save className="w-4 h-4" />
                        {savingEdit ? 'Saving...' : 'Save Changes'}
                      </button>
                      <button onClick={cancelEditing} disabled={savingEdit}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg transition-colors disabled:opacity-50">
                        <X className="w-4 h-4" />
                        Cancel
                      </button>
                    </div>
                    <div className="text-xs text-gray-400 mt-1">ID: {v._id} · Created: {v.created_at ? new Date(v.created_at).toLocaleDateString() : '—'}</div>
                  </div>
                ) : isExpanded ? (
                  /* ── Read-only Detail View ── */
                  <div className="px-4 pb-4 pt-1 border-t border-gray-100 dark:border-gray-700 grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
                    <div><span className="text-gray-500 dark:text-gray-400">Email:</span> <span className="text-gray-900 dark:text-gray-100">{v.email || '—'}</span></div>
                    <div><span className="text-gray-500 dark:text-gray-400">Phone:</span> <span className="text-gray-900 dark:text-gray-100">{v.phone || '—'}</span></div>
                    <div><span className="text-gray-500 dark:text-gray-400">Address:</span> <span className="text-gray-900 dark:text-gray-100">{v.address || '—'}</span></div>
                    <div><span className="text-gray-500 dark:text-gray-400">Website:</span> {v.website ? <a href={v.website} target="_blank" rel="noopener noreferrer" className="text-rose-500 hover:underline truncate inline-block max-w-[200px] align-bottom">{v.website.replace(/^https?:\/\//, '')}</a> : <span className="text-gray-900 dark:text-gray-100">—</span>}</div>
                    <div><span className="text-gray-500 dark:text-gray-400">Category:</span> <span className="text-gray-900 dark:text-gray-100">{vendorCategoryLabel(v.service_category)}</span></div>
                    <div><span className="text-gray-500 dark:text-gray-400">Preferred:</span> <span className="text-gray-900 dark:text-gray-100">{v.is_preferred ? 'Yes' : 'No'}</span></div>
                    {v.service_description && (
                      <div className="col-span-2"><span className="text-gray-500 dark:text-gray-400">Description:</span> <span className="text-gray-900 dark:text-gray-100">{v.service_description}</span></div>
                    )}
                    {v.tags && v.tags.length > 0 && (
                      <div className="col-span-2 flex items-center gap-1.5 flex-wrap">
                        <span className="text-gray-500 dark:text-gray-400">Tags:</span>
                        {v.tags.map((t) => (
                          <span key={t} className="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-xs text-gray-600 dark:text-gray-300">{t}</span>
                        ))}
                      </div>
                    )}
                    <div className="col-span-2 text-xs text-gray-400 mt-1">ID: {v._id} · Created: {v.created_at ? new Date(v.created_at).toLocaleDateString() : '—'}</div>
                  </div>
                ) : null}
              </Card>
            );
          })}

          {/* Pagination */}
          {vendorTotalPages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <button
                disabled={vendorPage === 0}
                onClick={() => setVendorPage((p) => Math.max(0, p - 1))}
                className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              >
                Previous
              </button>
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Page {vendorPage + 1} of {vendorTotalPages}
              </span>
              <button
                disabled={vendorPage >= vendorTotalPages - 1}
                onClick={() => setVendorPage((p) => p + 1)}
                className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}

      {/* Import Modal */}
      {token && (
        <VendorImportModal
          isOpen={showImportModal}
          onClose={() => setShowImportModal(false)}
          token={token}
          onImportComplete={(result) => {
            toast.success(
              `Import complete: ${result.inserted} inserted, ${result.updated} updated` +
              (result.errors > 0 ? `, ${result.errors} errors` : '')
            );
            fetchVendors();
            setShowImportModal(false);
          }}
        />
      )}
    </div>
  );
}

export default SaasAdminDashboard;
