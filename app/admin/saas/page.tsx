'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { Card } from '../../components/ui/Card';
import { formatDate, formatDateTime } from '@/utils/dateFormat';
import PageHeader from '../components/PageHeader';
import { toast } from 'sonner';
import { Settings } from 'lucide-react';
import {
  getAdminConfig,
  updateAdminConfig,
  type PlatformConfig,
} from '@/services/campaignAdvertisingApi';

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
 // Metered billing
 is_metered?: boolean;
 meter_event_name?: string;
 meter_id?: string;
 // Display
 is_featured: boolean;
 is_active: boolean;
 display_order: number;
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

function formatPercentage(value: number): string {
  return `${value.toFixed(1)}%`;
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

const SaasAdminDashboard = () => {
 const router = useRouter();
 const { userProfile } = useAdmin();
 const [activeTab, setActiveTab] = useState<'overview' | 'plans' | 'reviews' | 'ad-config'>('overview');
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

  // ROOT_ADMIN access control - redirect non-root admins
  useEffect(() => {
    if (userProfile && !userProfile.is_root_admin) {
      router.push('/admin');
    }
  }, [userProfile, router]);
  const fetchData = useCallback(async () => {
    try {
      const baseUrl = getApiBaseUrl();
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');

      if (!token) {
        setLoading(false);
        return;
      }

      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };

      const plansResponse = await fetch(`${baseUrl}/subscription-plans?include_inactive=true`, { headers });
      if (plansResponse.ok) {
        const plansData = await plansResponse.json();
        console.log('[SaaS Admin] Subscription plans loaded:', plansData.length, 'plans');
        setPlans(plansData);
      } else {
        console.error('[SaaS Admin] Failed to load subscription plans:', plansResponse.status, plansResponse.statusText);
        const errorText = await plansResponse.text();
        console.error('[SaaS Admin] Error details:', errorText);
      }

      const plannersResponse = await fetch(`${baseUrl}/saas/wedding-planners`, { headers });
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
      const metricsResponse = await fetch(`${baseUrl}/saas/analytics/platform?timeframe=${metricsTimeframe}`, { headers });
      if (metricsResponse.ok) {
        const metricsData = await metricsResponse.json();
        setMetrics(metricsData);
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
          subscriptionStatus: 'trialing',
          maxWeddings: 30,
          is_active: true,
          createdAt: new Date().toISOString(),
          lastLogin: new Date().toISOString()
        }
      ]);

    } finally {
      setLoading(false);
    }
  }, [metricsTimeframe]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Refetch only platform metrics when timeframe changes (without re-fetching plans/planners)
  const fetchMetricsOnly = useCallback(async (tf: TimeframeKey) => {
    try {
      setMetricsLoading(true);
      const baseUrl = getApiBaseUrl();
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
      if (!token) return;
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };
      const res = await fetch(`${baseUrl}/saas/analytics/platform?timeframe=${tf}`, { headers });
      if (res.ok) {
        setMetrics(await res.json());
      }
    } catch (err) {
      console.error('Failed to refresh platform metrics', err);
    } finally {
      setMetricsLoading(false);
    }
  }, []);

  const handleTimeframeChange = useCallback((tf: TimeframeKey) => {
    setMetricsTimeframe(tf);
    fetchMetricsOnly(tf);
  }, [fetchMetricsOnly]);

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
 const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
 const response = await fetch(`${baseUrl}/subscription-plans/${planId}`, {
 method: 'DELETE',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 }
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
 const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');

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
 body: JSON.stringify(planData)
 });

 if (response.ok) {
 // Refresh plans data
 const plansResponse = await fetch(`${baseUrl}/subscription-plans`, {
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 }
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
 const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
 const response = await fetch(`${baseUrl}/saas/wedding-planners`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 },
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
 const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
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
 }
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
 }
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
 const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
 // First, cancel existing subscription if any
 try {
 await fetch(`${baseUrl}/users/${plannerId}/subscription`, {
 method: 'DELETE',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 }
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
 { key: 'ad-config', label: 'Ad Platform' }
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
           <Card className="p-6">
             <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Accounts</p>
             <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{formatNumber(metrics.users.total)}</p>
             <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Active Roles: {roleBreakdown.length}</p>
           </Card>
           <Card className="p-6">
             <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Active This Period</p>
             <p className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">{formatNumber(metrics.users.active)}</p>
             <p className="mt-1 text-xs text-green-600 dark:text-green-400">Growth {formatPercentage(metrics.users.growth_rate)}</p>
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
                 <span key={role} className="rounded-full bg-gray-100 dark:bg-slate-700 px-3 py-1 text-gray-900 dark:text-white shadow-sm">
                   {role.replace('_', ' ')} · {formatNumber(count)}
                 </span>
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
 {plan.is_metered && (
 <p className="text-blue-600 dark:text-blue-400 font-medium">
 Metered: {plan.meter_event_name || 'wedding_active'}
 </p>
 )}
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
 display_order: plan?.display_order || 0,
 // Metered billing configuration
 is_metered: (plan as any)?.is_metered || false,
 meter_event_name: (plan as any)?.meter_event_name || 'wedding_active',
 meter_id: (plan as any)?.meter_id || '',
 features: {
 basic_website_builder: plan?.features?.basic_website_builder || false,
 guest_management: plan?.features?.guest_management || false,
 rsvp_system: plan?.features?.rsvp_system || false,
 ai_tools: plan?.features?.ai_tools || false,
 advanced_reporting: plan?.features?.advanced_reporting || false,
 white_label: plan?.features?.white_label || false,
 custom_integrations: plan?.features?.custom_integrations || false,
 multi_user_collaboration: plan?.features?.multi_user_collaboration || false,
 priority_support: plan?.features?.priority_support || false,
 }
 });

 const handleSubmit = (e: React.FormEvent) => {
 e.preventDefault();
 onSave(formData);
 };

 return (
 <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
 <div className="bg-white dark:bg-slate-800 rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
 <h2 className="text-2xl font-bold mb-4">
 {isEditing ? 'Edit Plan' : 'Create New Plan'}
 </h2>
 <form onSubmit={handleSubmit} className="space-y-4">
 <div className="grid grid-cols-2 gap-4">
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
 <span className="text-sm">Enable metered billing (charge per wedding created)</span>
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
 {Object.entries(formData.features).map(([key, value]) => (
 <label key={key} className="flex items-center space-x-2">
 <input
 type="checkbox"
 checked={value}
 onChange={(e) => setFormData(prev => ({
 ...prev,
 features: { ...prev.features, [key]: e.target.checked }
 }))}
 className="rounded"
 />
 <span className="text-sm">{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
 </label>
 ))}
 </div>
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
  const [testimonials, setTestimonials] = useState<Testimonial[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingTestimonial, setEditingTestimonial] = useState<Testimonial | null>(null);
  const [saving, setSaving] = useState(false);

  const fetchTestimonials = useCallback(async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
      const res = await fetch(`${getApiBaseUrl()}/saas/testimonials`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setTestimonials(await res.json());
      }
    } catch (err) {
      console.error('Failed to fetch testimonials:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchTestimonials(); }, [fetchTestimonials]);

  const handleToggle = async (id: string) => {
    try {
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
      const res = await fetch(`${getApiBaseUrl()}/saas/testimonials/${id}/toggle`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}` },
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
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
      const res = await fetch(`${getApiBaseUrl()}/saas/testimonials/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
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
      const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
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

function AdPlatformConfigTab() {
  const [config, setConfig] = useState<PlatformConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editedConfig, setEditedConfig] = useState<Partial<PlatformConfig>>({});

  const token = typeof window !== 'undefined'
    ? (localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token') || '')
    : '';

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getAdminConfig(token);
      setConfig(data);
      setEditedConfig(data);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSave = async () => {
    try {
      setSaving(true);
      const updated = await updateAdminConfig(token, editedConfig);
      setConfig(updated);
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

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Display Settings</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-200">Max Sponsored Per Page</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Maximum number of sponsored ads shown per page</p>
            </div>
            <input
              type="number"
              value={editedConfig.max_sponsored_per_page ?? 3}
              onChange={(e) => setNumberField('max_sponsored_per_page', e.target.value)}
              className="w-20 text-sm text-center border border-gray-300 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
              min={1}
              max={10}
            />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-200">Show Sponsored Badge</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Display &ldquo;Sponsored&rdquo; badge on ad cards</p>
            </div>
            <button
              onClick={() => toggleField('show_sponsored_badge')}
              className={`relative w-11 h-6 rounded-full transition-colors ${editedConfig.show_sponsored_badge ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'}`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${editedConfig.show_sponsored_badge ? 'translate-x-5' : ''}`} />
            </button>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-200">Enable Tracking</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Track impressions, clicks, and conversions</p>
            </div>
            <button
              onClick={() => toggleField('enable_tracking')}
              className={`relative w-11 h-6 rounded-full transition-colors ${editedConfig.enable_tracking ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'}`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${editedConfig.enable_tracking ? 'translate-x-5' : ''}`} />
            </button>
          </div>
        </div>
      </Card>

      <Card className="p-6">
        <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Review Settings</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-200">Require Review</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">All campaigns must be reviewed before going live</p>
            </div>
            <button
              onClick={() => toggleField('require_review')}
              className={`relative w-11 h-6 rounded-full transition-colors ${editedConfig.require_review ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'}`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${editedConfig.require_review ? 'translate-x-5' : ''}`} />
            </button>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-200">Auto-Approve Returning Vendors</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Skip review for vendors with previously approved campaigns</p>
            </div>
            <button
              onClick={() => toggleField('auto_approve_returning_vendors')}
              className={`relative w-11 h-6 rounded-full transition-colors ${editedConfig.auto_approve_returning_vendors ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'}`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${editedConfig.auto_approve_returning_vendors ? 'translate-x-5' : ''}`} />
            </button>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-200">Review SLA (hours)</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Target time to review submitted campaigns</p>
            </div>
            <input
              type="number"
              value={editedConfig.review_sla_hours ?? 24}
              onChange={(e) => setNumberField('review_sla_hours', e.target.value)}
              className="w-20 text-sm text-center border border-gray-300 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100"
              min={1}
              max={168}
            />
          </div>
        </div>
      </Card>

      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Configuration'}
        </button>
      </div>
    </div>
  );
}

export default SaasAdminDashboard;