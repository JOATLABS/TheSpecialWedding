'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { Card } from '../../components/ui/Card';
import { formatDate } from '@/utils/dateFormat';
import PageHeader from '../components/PageHeader';

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

interface AnalyticsOverview {
  total_planners: number;
  active_planners: number;
  total_weddings: number;
  active_plans: number;
  monthly_revenue: number;
  yearly_revenue: number;
  projected_annual_revenue: number;
}

interface PlanBreakdown {
  plan_id: string;
  plan_name: string;
  active_users: number;
  trial_users: number;
}

/* Landing page content (hero, features, stats, theme, etc.) is now hardcoded
   in app/page.tsx for performance. The SaaS Content and Theme tabs have been
   removed. Only subscription plans & analytics remain admin-configurable. */

const SaasAdminDashboard = () => {
 const router = useRouter();
 const { userProfile } = useAdmin();
 const [activeTab, setActiveTab] = useState<'overview' | 'plans' | 'planners'>('overview');
 const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
 const [planners, setPlanners] = useState<WeddingPlanner[]>([]);
 const [loading, setLoading] = useState(true);
 const [showCreatePlanModal, setShowCreatePlanModal] = useState(false);
 const [editingPlan, setEditingPlan] = useState<SubscriptionPlan | null>(null);
 const [error, setError] = useState<string | null>(null);
 const [analyticsOverview, setAnalyticsOverview] = useState<AnalyticsOverview | null>(null);
 const [planBreakdown, setPlanBreakdown] = useState<PlanBreakdown[]>([]);

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

      // Fetch analytics overview for dashboard statistics
      const analyticsResponse = await fetch(`${baseUrl}/saas/analytics/overview`, { headers });
      if (analyticsResponse.ok) {
        const analyticsData = await analyticsResponse.json();
        setAnalyticsOverview(analyticsData);
      }

      // Fetch revenue breakdown for per-plan user counts
      const revenueResponse = await fetch(`${baseUrl}/saas/analytics/revenue`, { headers });
      if (revenueResponse.ok) {
        const revenueData = await revenueResponse.json();
        if (revenueData.plan_breakdown) {
          setPlanBreakdown(revenueData.plan_breakdown);
        }
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
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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
 <div className="min-h-screen flex items-center justify-center">
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
 title="SAAS Admin Dashboard"
 description="Manage your wedding planning platform"
 />

 {/* Navigation Tabs */}
 <div className="border-b border-slate-200 dark:border-slate-700">
 <nav className="flex space-x-8">
 {[
 { key: 'overview', label: 'Overview' },
 { key: 'plans', label: 'Subscription Plans' }
 ].map((tab) => (
 <button
 key={tab.key}
 onClick={() => setActiveTab(tab.key as any)}
 className={`py-4 px-1 border-b-2 font-medium text-sm ${
 activeTab === tab.key
 ? 'border-blue-500 text-blue-600 dark:text-blue-400'
 : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300 hover:border-slate-300'
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
 <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
 <Card className="p-6">
 <div className="flex items-center">
 <div className="flex-shrink-0">
 <div className="w-8 h-8 bg-blue-100 rounded-md flex items-center justify-center">
 <div className="w-4 h-4 bg-blue-600 rounded"></div>
 </div>
 </div>
 <div className="ml-5 w-0 flex-1">
 <dl>
 <dt className="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">Total Planners</dt>
 <dd className="text-lg font-medium text-gray-900 dark:text-gray-100">{planners.length}</dd>
 </dl>
 </div>
 </div>
 </Card>

 <Card className="p-6">
 <div className="flex items-center">
 <div className="flex-shrink-0">
 <div className="w-8 h-8 bg-green-100 rounded-md flex items-center justify-center">
 <div className="w-4 h-4 bg-green-600 rounded"></div>
 </div>
 </div>
 <div className="ml-5 w-0 flex-1">
 <dl>
 <dt className="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">Active Plans</dt>
 <dd className="text-lg font-medium text-gray-900 dark:text-gray-100">{plans.filter(p => p.is_active).length}</dd>
 </dl>
 </div>
 </div>
 </Card>

 <Card className="p-6">
 <div className="flex items-center">
 <div className="flex-shrink-0">
 <div className="w-8 h-8 bg-purple-100 rounded-md flex items-center justify-center">
 <div className="w-4 h-4 bg-purple-600 rounded"></div>
 </div>
 </div>
 <div className="ml-5 w-0 flex-1">
 <dl>
 <dt className="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">Total Weddings</dt>
 <dd className="text-lg font-medium text-gray-900 dark:text-gray-100">{analyticsOverview?.total_weddings ?? 0}</dd>
 </dl>
 </div>
 </div>
 </Card>

 <Card className="p-6">
 <div className="flex items-center">
 <div className="flex-shrink-0">
 <div className="w-8 h-8 bg-yellow-100 rounded-md flex items-center justify-center">
 <div className="w-4 h-4 bg-yellow-600 rounded"></div>
 </div>
 </div>
 <div className="ml-5 w-0 flex-1">
 <dl>
 <dt className="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">Monthly Revenue</dt>
 <dd className="text-lg font-medium text-gray-900 dark:text-gray-100">${analyticsOverview?.monthly_revenue ?? 0}</dd>
 </dl>
 </div>
 </div>
 </Card>
 </div>

 <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
 <Card className="p-6">
 <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Recent Signups</h3>
 <div className="space-y-3">
 {planners.slice(0, 3).map((planner) => (
 <div key={planner.id} className="flex items-center justify-between">
 <div>
 <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{planner.companyName}</p>
 <p className="text-sm text-gray-500 dark:text-gray-400">{planner.email}</p>
 </div>
 <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
 Active
 </span>
 </div>
 ))}
 </div>
 </Card>

 <Card className="p-6">
 <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Plan Distribution</h3>
 <div className="space-y-3">
 {plans.map((plan) => (
 <div key={plan._id} className="flex items-center justify-between">
 <span className="text-sm text-gray-900 dark:text-gray-100">{plan.name}</span>
 <span className="text-sm text-gray-500 dark:text-gray-400">
 {(() => {
  const breakdown = planBreakdown.find(b => b.plan_id === plan._id || b.plan_name === plan.name);
  const count = breakdown ? breakdown.active_users + breakdown.trial_users : 0;
  return `${count} user${count !== 1 ? 's' : ''}`;
})()}
 </span>
 </div>
 ))}
 </div>
 </Card>
 </div>
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
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">Plan Name</label>
 <input
 type="text"
 required
 value={formData.name}
 onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">Monthly Price ($)</label>
 <input
 type="number"
 step="0.01"
 min="0"
 value={formData.price_monthly}
 onChange={(e) => setFormData(prev => ({ ...prev, price_monthly: parseFloat(e.target.value) || 0 }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">Description</label>
 <textarea
 value={formData.description}
 onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
 className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
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
 <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 dark:text-gray-300 mb-1">AI Credits/Month</label>
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

export default SaasAdminDashboard;