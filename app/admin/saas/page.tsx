'use client';

import React, { useState, useEffect } from 'react';
import { Card } from '../../components/ui/Card';
import { ContentEditModal } from '../components/ContentEditModal';

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
 is_featured: boolean;
 is_active: boolean;
 display_order: number;
 created_by: string;
 created_at: string;
 updated_at: string;
}

interface SaasContentSection {
 id: string;
 section: string;
 content: any;
 isActive: boolean;
 displayOrder: number;
 updatedBy: string;
 updatedAt: string;
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
}

interface ThemeConfig {
 primary_color: string;
 secondary_color: string;
 background_image?: string;
 fallback_images: string[];
}

interface SaasFullConfig {
 hero_title: string;
 hero_subtitle: string;
 hero_description: string;
 hero_cta_primary: string;
 hero_cta_secondary: string;
 trust_indicators: string[];
 statistics: Array<{
 label: string;
 value: string;
 }>;
 features: Array<{
 title: string;
 description: string;
 status: 'available' | 'coming_soon';
 order: number;
 }>;
 benefits: Array<{
 title: string;
 description: string;
 order: number;
 }>;
 testimonials: Array<{
 name: string;
 company: string;
 role: string;
 content: string;
 order: number;
 }>;
 features_enabled: boolean;
 benefits_enabled: boolean;
 testimonials_enabled: boolean;
 statistics_enabled: boolean;
 subscription_enabled: boolean;
 contact_form_enabled: boolean;
 theme: ThemeConfig;
}

const SaasAdminDashboard = () => {
 const [activeTab, setActiveTab] = useState<'overview' | 'plans' | 'content' | 'theme' | 'planners'>('overview');
 const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
 const [contentSections, setContentSections] = useState<SaasContentSection[]>([]);
 const [planners, setPlanners] = useState<WeddingPlanner[]>([]);
 const [saasConfig, setSaasConfig] = useState<SaasFullConfig | null>(null);
 const [loading, setLoading] = useState(true);
 const [showCreatePlanModal, setShowCreatePlanModal] = useState(false);
 const [editingPlan, setEditingPlan] = useState<SubscriptionPlan | null>(null);
 const [error, setError] = useState<string | null>(null);
 const [editModalOpen, setEditModalOpen] = useState(false);
 const [editingSectionType, setEditingSectionType] = useState<string>('');
 const [editingSectionData, setEditingSectionData] = useState<any>(null);

 // Fetch real data from API
 useEffect(() => {
 const fetchData = async () => {
 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
 
 if (!token) {
 setLoading(false);
 return;
 }

 const headers = {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 };

 // Fetch subscription plans
 const plansResponse = await fetch(`${baseUrl}/admin/subscription-plans`, { headers });
 if (plansResponse.ok) {
 const plansData = await plansResponse.json();
 setPlans(plansData);
 }

 // Fetch wedding planners
 const plannersResponse = await fetch(`${baseUrl}/saas/wedding-planners`, { headers });
 if (plannersResponse.ok) {
 const plannersData = await plannersResponse.json();
 setPlanners(plannersData.map((planner: any) => ({
 id: planner.id,
 email: planner.email,
 companyName: planner.company_name,
 subscriptionPlanId: planner.subscription_plan_id,
 subscriptionStatus: planner.subscription_status,
 maxWeddings: planner.max_weddings,
 is_active: planner.is_active,
 createdAt: planner.created_at,
 lastLogin: planner.last_login
 })));
 }

 // Fetch SAAS configuration
 const configResponse = await fetch(`${baseUrl}/admin/saas-config`, { headers });
 if (configResponse.ok) {
 const configData = await configResponse.json();
 setSaasConfig(configData);
 } else {
 // Set default config if API fails
 setSaasConfig({
 hero_title: "Welcome to Special Wedding",
 hero_subtitle: "Wedding Planning Made Simple",
 hero_description: "The ultimate wedding planning platform for professional wedding planners. Manage multiple weddings, coordinate with vendors, and create beautiful wedding websites with AI-powered tools.",
 hero_cta_primary: "Start Free Trial",
 hero_cta_secondary: "Watch Demo",
 trust_indicators: ["Free 30-day trial", "No setup fees", "Cancel anytime"],
 statistics: [
 { label: "Wedding Planners Trust Us", value: "500+" },
 { label: "Weddings Managed", value: "10K+" },
 { label: "Uptime Guarantee", value: "99.9%" }
 ],
 features: [
 {
 title: "Complete Wedding Management",
 description: "Manage multiple weddings with ease. Track guests, RSVPs, vendors, and timelines all in one place.",
 status: "available" as const,
 order: 1
 },
 {
 title: "AI Presentation Generator",
 description: "Create stunning wedding presentations in minutes with our AI-powered design tools.",
 status: "coming_soon" as const,
 order: 5
 }
 ],
 benefits: [
 {
 title: "Save Time",
 description: "Automate repetitive tasks and streamline wedding planning operations",
 order: 1
 },
 {
 title: "Scale Your Business",
 description: "Manage multiple weddings efficiently and grow your planning business",
 order: 2
 }
 ],
 testimonials: [
 {
 name: "Sarah Johnson",
 company: "Elegant Events Planning",
 role: "Senior Wedding Planner",
 content: "Special Wedding has revolutionized how I manage my clients' weddings. The AI tools save me hours every week!",
 order: 1
 }
 ],
 features_enabled: true,
 benefits_enabled: true,
 testimonials_enabled: true,
 statistics_enabled: true,
 subscription_enabled: true,
 contact_form_enabled: false,
 theme: {
 primary_color: "#1e3a5f",
 secondary_color: "#d4af37",
 fallback_images: [
 "/wedding-images/wedding-ceremony.jpg",
 "/wedding-images/wedding-reception.jpg"
 ]
 }
 });
 }

 // Fetch content sections
 const sectionsResponse = await fetch(`${baseUrl}/admin/content-sections`, { headers });
 if (sectionsResponse.ok) {
 const sectionsData = await sectionsResponse.json();
 setContentSections(sectionsData.map((section: any) => ({
 id: section._id || section.id,
 section: section.section,
 content: section.content,
 isActive: section.is_active,
 displayOrder: section.display_order,
 updatedBy: section.updated_by,
 updatedAt: section.updated_at
 })));
 }

 } catch (error) {
 console.error('Error fetching SAAS data:', error);
 // Set default saasConfig if there's an error
 if (!saasConfig) {
 setSaasConfig({
 hero_title: "Welcome to Special Wedding",
 hero_subtitle: "Wedding Planning Made Simple",
 hero_description: "The ultimate wedding planning platform for professional wedding planners.",
 hero_cta_primary: "Start Free Trial",
 hero_cta_secondary: "Watch Demo",
 trust_indicators: ["Free 30-day trial", "No setup fees", "Cancel anytime"],
 statistics: [
 { label: "Wedding Planners Trust Us", value: "500+" },
 { label: "Weddings Managed", value: "10K+" },
 { label: "Uptime Guarantee", value: "99.9%" }
 ],
 features: [],
 benefits: [],
 testimonials: [],
 features_enabled: true,
 benefits_enabled: true,
 testimonials_enabled: true,
 statistics_enabled: true,
 subscription_enabled: true,
 contact_form_enabled: false,
 theme: {
 primary_color: "#1e3a5f",
 secondary_color: "#d4af37",
 fallback_images: [
 "/wedding-images/wedding-ceremony.jpg",
 "/wedding-images/wedding-reception.jpg"
 ]
 }
 });
 }
 } finally {
 setLoading(false);
 }
 };

 fetchData();
 }, []);

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
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
 
 const response = await fetch(`${baseUrl}/admin/subscription-plans/${planId}`, {
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
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
 
 const isEditing = !!editingPlan;
 const url = isEditing 
 ? `${baseUrl}/admin/subscription-plans/${editingPlan._id}`
 : `${baseUrl}/admin/subscription-plans`;
 
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
 const plansResponse = await fetch(`${baseUrl}/admin/subscription-plans`, {
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

 const handleSaveSaasConfig = async (configToSave?: SaasFullConfig | React.MouseEvent) => {
 // Handle both direct config object and mouse event from button clicks
 const configData = (configToSave && 'hero_title' in configToSave) ? configToSave : saasConfig;
 
 if (!configData) {
 alert('No configuration data to save');
 return;
 }

 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
 
 if (!token) {
 alert('Authentication token not found. Please log in again.');
 return;
 }

 // Create a clean copy of the config to avoid circular references
 const cleanConfig: SaasFullConfig = {
 hero_title: configData.hero_title,
 hero_subtitle: configData.hero_subtitle,
 hero_description: configData.hero_description,
 hero_cta_primary: configData.hero_cta_primary,
 hero_cta_secondary: configData.hero_cta_secondary,
 trust_indicators: configData.trust_indicators || [],
 statistics: configData.statistics || [],
 features: configData.features || [],
 benefits: configData.benefits || [],
 testimonials: configData.testimonials || [],
 features_enabled: configData.features_enabled,
 benefits_enabled: configData.benefits_enabled,
 testimonials_enabled: configData.testimonials_enabled,
 statistics_enabled: configData.statistics_enabled,
 subscription_enabled: configData.subscription_enabled,
 contact_form_enabled: configData.contact_form_enabled,
 theme: {
 primary_color: configData.theme.primary_color,
 secondary_color: configData.theme.secondary_color,
 background_image: configData.theme.background_image,
 fallback_images: configData.theme.fallback_images || []
 }
 };

 console.log('Saving SAAS config:', cleanConfig);
 
 const response = await fetch(`${baseUrl}/admin/saas-config`, {
 method: 'PUT',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 },
 body: JSON.stringify(cleanConfig)
 });

 const responseData = await response.text();
 console.log('Response status:', response.status);
 console.log('Response data:', responseData);

 if (response.ok) {
 alert('SAAS configuration saved successfully');
 } else {
 let errorMessage = 'Failed to save configuration';
 try {
 const errorData = JSON.parse(responseData);
 errorMessage = errorData.detail || errorMessage;
 } catch (parseError) {
 errorMessage = responseData || errorMessage;
 }
 throw new Error(errorMessage);
 }
 } catch (error) {
 console.error('Error saving SAAS config:', error);
 const errorMessage = error instanceof Error ? error.message : String(error);
 alert(`Failed to save SAAS configuration: ${errorMessage}`);
 throw error; // Re-throw so caller can handle it
 }
 };

 const handleEditContent = (sectionType: string) => {
 if (!saasConfig) return;
 
 let sectionData = {};
 
 switch (sectionType) {
 case 'hero':
 sectionData = {
 hero_title: saasConfig.hero_title,
 hero_subtitle: saasConfig.hero_subtitle,
 hero_description: saasConfig.hero_description,
 hero_cta_primary: saasConfig.hero_cta_primary,
 hero_cta_secondary: saasConfig.hero_cta_secondary
 };
 break;
 case 'statistics':
 sectionData = {
 statistics: saasConfig.statistics || []
 };
 break;
 case 'trust_indicators':
 sectionData = {
 trust_indicators: saasConfig.trust_indicators || []
 };
 break;
 default:
 console.warn('Unknown section type:', sectionType);
 return;
 }
 
 setEditingSectionType(sectionType);
 setEditingSectionData(sectionData);
 setEditModalOpen(true);
 };

 const handleCreatePlanner = async () => {
 const email = prompt('Enter planner email:');
 const companyName = prompt('Enter company name:');
 
 if (!email || !companyName) return;

 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
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
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
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
 const subscriptionResponse = await fetch(`${baseUrl}/admin/users/${plannerId}/subscription`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 },
 body: JSON.stringify({
 plan_id: defaultPlan._id,
 billing_interval: 'monthly',
 trial_days: 14
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
 await fetch(`${baseUrl}/admin/users/${plannerId}/subscription`, {
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
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
 const token = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
 
 // First, cancel existing subscription if any
 try {
 await fetch(`${baseUrl}/admin/users/${plannerId}/subscription`, {
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
 const response = await fetch(`${baseUrl}/admin/users/${plannerId}/subscription`, {
 method: 'POST',
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json'
 },
 body: JSON.stringify({
 plan_id: planId,
 billing_interval: 'monthly',
 trial_days: 14
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
 <div className="min-h-screen bg-gray-50 flex items-center justify-center">
 <div className="text-center">
 <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
 <p className="text-gray-600">Loading SAAS Dashboard...</p>
 </div>
 </div>
 );
 }

 return (
 <div className="min-h-screen bg-gray-50">
 {/* Header */}
 <div className="bg-white shadow-sm border-b">
 <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
 <div className="flex justify-between items-center py-6">
 <div>
 <h1 className="text-3xl font-bold text-gray-900">SAAS Admin Dashboard</h1>
 <p className="text-gray-600">Manage your wedding planning platform</p>
 </div>
 <div className="flex items-center space-x-4">
 <span className="text-sm text-gray-500">ROOT_ADMIN</span>
 <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
 <span className="text-white font-semibold">TD</span>
 </div>
 </div>
 </div>
 </div>
 </div>

 {/* Navigation Tabs */}
 <div className="bg-white border-b">
 <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
 <nav className="flex space-x-8">
 {[
 { key: 'overview', label: 'Overview' },
 { key: 'plans', label: 'Subscription Plans' },
 { key: 'content', label: 'SAAS Content' },
 { key: 'theme', label: 'Theme & Design' },
 { key: 'planners', label: 'Wedding Planners' }
 ].map((tab) => (
 <button
 key={tab.key}
 onClick={() => setActiveTab(tab.key as any)}
 className={`py-4 px-1 border-b-2 font-medium text-sm ${
 activeTab === tab.key
 ? 'border-blue-500 text-blue-600'
 : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
 }`}
 >
 {tab.label}
 </button>
 ))}
 </nav>
 </div>
 </div>

 {/* Content */}
 <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
 <dt className="text-sm font-medium text-gray-500 truncate">Total Planners</dt>
 <dd className="text-lg font-medium text-gray-900">{planners.length}</dd>
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
 <dt className="text-sm font-medium text-gray-500 truncate">Active Plans</dt>
 <dd className="text-lg font-medium text-gray-900">{plans.filter(p => p.is_active).length}</dd>
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
 <dt className="text-sm font-medium text-gray-500 truncate">Total Weddings</dt>
 <dd className="text-lg font-medium text-gray-900">12</dd>
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
 <dt className="text-sm font-medium text-gray-500 truncate">Monthly Revenue</dt>
 <dd className="text-lg font-medium text-gray-900">$247</dd>
 </dl>
 </div>
 </div>
 </Card>
 </div>

 <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
 <Card className="p-6">
 <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Signups</h3>
 <div className="space-y-3">
 {planners.slice(0, 3).map((planner) => (
 <div key={planner.id} className="flex items-center justify-between">
 <div>
 <p className="text-sm font-medium text-gray-900">{planner.companyName}</p>
 <p className="text-sm text-gray-500">{planner.email}</p>
 </div>
 <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
 Active
 </span>
 </div>
 ))}
 </div>
 </Card>

 <Card className="p-6">
 <h3 className="text-lg font-medium text-gray-900 mb-4">Plan Distribution</h3>
 <div className="space-y-3">
 {plans.map((plan) => (
 <div key={plan._id} className="flex items-center justify-between">
 <span className="text-sm text-gray-900">{plan.name}</span>
 <span className="text-sm text-gray-500">
 {plan.name === 'Professional' ? '1 user' : '0 users'}
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
 <h2 className="text-2xl font-bold text-gray-900">Subscription Plans</h2>
 <button
 onClick={handleCreatePlan}
 className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
 >
 Create New Plan
 </button>
 </div>

 <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
 {plans.map((plan) => {
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
 <p className="text-sm text-gray-600 mb-3">{plan.description}</p>
 )}
 
 <div className="text-3xl font-bold text-blue-600 mb-4">
 {plan.price_monthly === 0 ? 'Free' : `$${plan.price_monthly}/month`}
 </div>
 
 <ul className="space-y-2 mb-6">
 {featuresArray.slice(0, 4).map((feature, idx) => (
 <li key={idx} className="text-sm text-gray-600 flex items-center">
 <span className="text-green-500 mr-2"></span>
 {feature}
 </li>
 ))}
 {featuresArray.length > 4 && (
 <li className="text-sm text-gray-500">
 +{featuresArray.length - 4} more features
 </li>
 )}
 </ul>
 
 <div className="text-xs text-gray-500 space-y-1 mb-4">
 <p>Max Weddings: {plan.max_weddings === -1 ? 'Unlimited' : plan.max_weddings}</p>
 <p>AI Credits: {plan.ai_credits_monthly}/month</p>
 <p>Storage: {plan.storage_gb}GB</p>
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

 {activeTab === 'content' && saasConfig && (
 <div className="space-y-6">
 <div className="flex justify-between items-center">
 <h2 className="text-2xl font-bold text-gray-900">SAAS Landing Page Content</h2>
 <button 
 onClick={handleSaveSaasConfig}
 className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
 >
 Save All Changes
 </button>
 </div>

 <div className="space-y-6">
 {/* Hero Section Editor */}
 <Card className="p-6">
 <div className="flex justify-between items-center mb-4">
 <h3 className="text-lg font-semibold">Hero Section</h3>
 <button
 onClick={() => handleEditContent('hero')}
 className="text-blue-600 hover:text-blue-700 text-sm font-medium"
 >
 Edit in Modal
 </button>
 </div>
 <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-2">Title</label>
 <input
 type="text"
 value={saasConfig.hero_title}
 onChange={(e) => setSaasConfig({...saasConfig, hero_title: e.target.value})}
 className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-2">Subtitle</label>
 <input
 type="text"
 value={saasConfig.hero_subtitle}
 onChange={(e) => setSaasConfig({...saasConfig, hero_subtitle: e.target.value})}
 className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 <div className="lg:col-span-2">
 <label className="block text-sm font-medium text-gray-700 mb-2">Description</label>
 <textarea
 value={saasConfig.hero_description}
 onChange={(e) => setSaasConfig({...saasConfig, hero_description: e.target.value})}
 rows={3}
 className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-2">Primary CTA</label>
 <input
 type="text"
 value={saasConfig.hero_cta_primary}
 onChange={(e) => setSaasConfig({...saasConfig, hero_cta_primary: e.target.value})}
 className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-2">Secondary CTA</label>
 <input
 type="text"
 value={saasConfig.hero_cta_secondary}
 onChange={(e) => setSaasConfig({...saasConfig, hero_cta_secondary: e.target.value})}
 className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 </div>
 </Card>

 {/* Statistics Section */}
 <Card className="p-6">
 <div className="flex justify-between items-center mb-4">
 <h3 className="text-lg font-semibold">Statistics</h3>
 <div className="flex items-center space-x-4">
 <button
 onClick={() => handleEditContent('statistics')}
 className="text-blue-600 hover:text-blue-700 text-sm font-medium"
 >
 Edit in Modal
 </button>
 <label className="flex items-center">
 <input
 type="checkbox"
 checked={saasConfig.statistics_enabled}
 onChange={(e) => setSaasConfig({...saasConfig, statistics_enabled: e.target.checked})}
 className="mr-2"
 />
 Enable Section
 </label>
 </div>
 </div>
 <div className="space-y-3">
 {saasConfig.statistics.map((stat, index) => (
 <div key={index} className="flex items-center space-x-3">
 <input
 type="text"
 value={stat.value}
 onChange={(e) => {
 const newStats = [...saasConfig.statistics];
 newStats[index] = {...stat, value: e.target.value};
 setSaasConfig({...saasConfig, statistics: newStats});
 }}
 placeholder="500+"
 className="w-24 px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 <input
 type="text"
 value={stat.label}
 onChange={(e) => {
 const newStats = [...saasConfig.statistics];
 newStats[index] = {...stat, label: e.target.value};
 setSaasConfig({...saasConfig, statistics: newStats});
 }}
 placeholder="Label"
 className="flex-1 px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 <button
 onClick={() => {
 const newStats = saasConfig.statistics.filter((_, i) => i !== index);
 setSaasConfig({...saasConfig, statistics: newStats});
 }}
 className="text-red-600 hover:text-red-800"
 >
 Remove
 </button>
 </div>
 ))}
 <button
 onClick={() => setSaasConfig({
 ...saasConfig,
 statistics: [...saasConfig.statistics, {label: '', value: ''}]
 })}
 className="text-blue-600 hover:text-blue-800 text-sm"
 >
 + Add Statistic
 </button>
 </div>
 </Card>

 {/* Trust Indicators */}
 <Card className="p-6">
 <div className="flex justify-between items-center mb-4">
 <h3 className="text-lg font-semibold">Trust Indicators</h3>
 <button
 onClick={() => handleEditContent('trust_indicators')}
 className="text-blue-600 hover:text-blue-700 text-sm font-medium"
 >
 Edit in Modal
 </button>
 </div>
 <div className="space-y-3">
 {saasConfig.trust_indicators.map((indicator, index) => (
 <div key={index} className="flex items-center space-x-3">
 <input
 type="text"
 value={indicator}
 onChange={(e) => {
 const newIndicators = [...saasConfig.trust_indicators];
 newIndicators[index] = e.target.value;
 setSaasConfig({...saasConfig, trust_indicators: newIndicators});
 }}
 className="flex-1 px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 placeholder="Free 30-day trial"
 />
 <button
 onClick={() => {
 const newIndicators = saasConfig.trust_indicators.filter((_, i) => i !== index);
 setSaasConfig({...saasConfig, trust_indicators: newIndicators});
 }}
 className="text-red-600 hover:text-red-800"
 >
 Remove
 </button>
 </div>
 ))}
 <button
 onClick={() => setSaasConfig({
 ...saasConfig,
 trust_indicators: [...saasConfig.trust_indicators, '']
 })}
 className="text-blue-600 hover:text-blue-800 text-sm"
 >
 + Add Trust Indicator
 </button>
 </div>
 </Card>

 {/* Subscription Settings */}
 <Card className="p-6">
 <div className="flex justify-between items-center mb-4">
 <h3 className="text-lg font-semibold">Subscription & Contact Settings</h3>
 </div>
 <div className="space-y-4">
 <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
 <div>
 <h4 className="font-medium text-gray-900">Subscription Section</h4>
 <p className="text-sm text-gray-600">Show pricing plans and subscription options</p>
 </div>
 <label className="flex items-center">
 <input
 type="checkbox"
 checked={saasConfig.subscription_enabled}
 onChange={(e) => setSaasConfig({...saasConfig, subscription_enabled: e.target.checked, contact_form_enabled: !e.target.checked})}
 className="mr-2"
 />
 Enable Subscription
 </label>
 </div>
 <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
 <div>
 <h4 className="font-medium text-gray-900">Contact Form</h4>
 <p className="text-sm text-gray-600">Replace subscription section with contact form for inquiries</p>
 </div>
 <label className="flex items-center">
 <input
 type="checkbox"
 checked={saasConfig.contact_form_enabled}
 onChange={(e) => setSaasConfig({...saasConfig, contact_form_enabled: e.target.checked, subscription_enabled: !e.target.checked})}
 className="mr-2"
 />
 Enable Contact Form
 </label>
 </div>
 <div className="mt-4 p-3 bg-blue-50 rounded-lg">
 <p className="text-sm text-blue-800">
 <strong>Note:</strong> Only one option can be enabled at a time. The contact form will replace the subscription section when enabled.
 </p>
 </div>
 </div>
 </Card>
 </div>
 </div>
 )}

 {activeTab === 'theme' && saasConfig && (
 <div className="space-y-6">
 <div className="flex justify-between items-center">
 <h2 className="text-2xl font-bold text-gray-900">Theme & Design</h2>
 <button 
 onClick={handleSaveSaasConfig}
 className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
 >
 Save Changes
 </button>
 </div>

 <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
 {/* Theme Colors */}
 <Card className="p-6">
 <h3 className="text-lg font-semibold mb-4">Brand Colors</h3>
 <div className="space-y-4">
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-2">
 Primary Color
 </label>
 <div className="flex items-center space-x-3">
 <input
 type="color"
 value={saasConfig.theme.primary_color}
 onChange={(e) => setSaasConfig({
 ...saasConfig,
 theme: { ...saasConfig.theme, primary_color: e.target.value }
 })}
 className="w-12 h-12 rounded border-2 border-gray-300 cursor-pointer"
 />
 <input
 type="text"
 value={saasConfig.theme.primary_color}
 onChange={(e) => setSaasConfig({
 ...saasConfig,
 theme: { ...saasConfig.theme, primary_color: e.target.value }
 })}
 className="flex-1 px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 placeholder="#1e3a5f"
 />
 </div>
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 mb-2">
 Secondary Color
 </label>
 <div className="flex items-center space-x-3">
 <input
 type="color"
 value={saasConfig.theme.secondary_color}
 onChange={(e) => setSaasConfig({
 ...saasConfig,
 theme: { ...saasConfig.theme, secondary_color: e.target.value }
 })}
 className="w-12 h-12 rounded border-2 border-gray-300 cursor-pointer"
 />
 <input
 type="text"
 value={saasConfig.theme.secondary_color}
 onChange={(e) => setSaasConfig({
 ...saasConfig,
 theme: { ...saasConfig.theme, secondary_color: e.target.value }
 })}
 className="flex-1 px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 placeholder="#d4af37"
 />
 </div>
 </div>

 {/* Color Preview */}
 <div className="mt-6 p-4 rounded-lg border-2 border-gray-200">
 <h4 className="text-sm font-medium text-gray-700 mb-3">Preview</h4>
 <div className="flex space-x-4">
 <div 
 className="w-16 h-16 rounded-lg shadow-md flex items-center justify-center text-white text-xs font-medium"
 style={{ backgroundColor: saasConfig.theme.primary_color }}
 >
 Primary
 </div>
 <div 
 className="w-16 h-16 rounded-lg shadow-md flex items-center justify-center text-white text-xs font-medium"
 style={{ backgroundColor: saasConfig.theme.secondary_color }}
 >
 Secondary
 </div>
 <div 
 className="w-16 h-16 rounded-lg shadow-md flex items-center justify-center text-white text-xs font-medium"
 style={{ 
 background: `linear-gradient(135deg, ${saasConfig.theme.primary_color}, ${saasConfig.theme.secondary_color})`
 }}
 >
 Gradient
 </div>
 </div>
 </div>
 </div>
 </Card>

 {/* Background Settings */}
 <Card className="p-6">
 <h3 className="text-lg font-semibold mb-4">Background Settings</h3>
 <div className="space-y-4">
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-2">
 Custom Background Image URL
 </label>
 <input
 type="url"
 value={saasConfig.theme.background_image || ''}
 onChange={(e) => setSaasConfig({
 ...saasConfig,
 theme: { ...saasConfig.theme, background_image: e.target.value }
 })}
 className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 placeholder="https://example.com/image.jpg"
 />
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 mb-2">
 Fallback Images
 </label>
 <div className="space-y-2">
 {saasConfig.theme.fallback_images.map((image, index) => (
 <div key={index} className="flex items-center space-x-2">
 <input
 type="text"
 value={image}
 onChange={(e) => {
 const newImages = [...saasConfig.theme.fallback_images];
 newImages[index] = e.target.value;
 setSaasConfig({
 ...saasConfig,
 theme: { ...saasConfig.theme, fallback_images: newImages }
 });
 }}
 className="flex-1 px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 placeholder="/path/to/image.jpg"
 />
 <button
 onClick={() => {
 const newImages = saasConfig.theme.fallback_images.filter((_, i) => i !== index);
 setSaasConfig({
 ...saasConfig,
 theme: { ...saasConfig.theme, fallback_images: newImages }
 });
 }}
 className="text-red-600 hover:text-red-800"
 >
 Remove
 </button>
 </div>
 ))}
 <button
 onClick={() => setSaasConfig({
 ...saasConfig,
 theme: { 
 ...saasConfig.theme, 
 fallback_images: [...saasConfig.theme.fallback_images, ''] 
 }
 })}
 className="text-blue-600 hover:text-blue-800 text-sm"
 >
 + Add Fallback Image
 </button>
 </div>
 </div>
 </div>
 </Card>
 </div>

 {/* Live Preview Button */}
 <Card className="p-6">
 <div className="flex justify-between items-center">
 <div>
 <h3 className="text-lg font-semibold">Live Preview</h3>
 <p className="text-gray-600 text-sm">See how your changes look on the landing page</p>
 </div>
 <button
 onClick={() => window.open('/', '_blank')}
 className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors"
 >
 Open Landing Page
 </button>
 </div>
 </Card>
 </div>
 )}

 {activeTab === 'planners' && (
 <div className="space-y-6">
 <div className="flex justify-between items-center">
 <h2 className="text-2xl font-bold text-gray-900">Wedding Planners</h2>
 <button
 onClick={handleCreatePlanner}
 className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
 >
 Create New Planner
 </button>
 </div>

 <Card className="overflow-hidden">
 <div className="overflow-x-auto">
 <table className="min-w-full divide-y divide-gray-200">
 <thead className="bg-gray-50">
 <tr>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
 Company & Email
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
 Plan
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
 Status
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
 Last Login
 </th>
 <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
 Actions
 </th>
 </tr>
 </thead>
 <tbody className="bg-white divide-y divide-gray-200">
 {planners.map((planner) => (
 <tr key={planner.id}>
 <td className="px-6 py-4 whitespace-nowrap">
 <div>
 <div className="text-sm font-medium text-gray-900">{planner.companyName}</div>
 <div className="text-sm text-gray-500">{planner.email}</div>
 </div>
 </td>
 <td className="px-6 py-4 whitespace-nowrap">
 <div className="flex items-center space-x-2">
 <select
 value={planner.subscriptionPlanId || ''}
 onChange={(e) => handleAssignPlan(planner.id, e.target.value)}
 className="text-xs px-2 py-1 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
 >
 <option value="">Select Plan</option>
 {plans.filter(p => p.is_active).map(plan => (
 <option key={plan._id} value={plan._id}>
 {plan.name}
 </option>
 ))}
 </select>
 <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
 {plans.find(p => p._id === planner.subscriptionPlanId)?.name || 'Unknown'}
 </span>
 </div>
 </td>
 <td className="px-6 py-4 whitespace-nowrap">
 <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
 planner.is_active && planner.subscriptionStatus === 'active'
 ? 'bg-green-100 text-green-800'
 : 'bg-red-100 text-red-800'
 }`}>
 {planner.is_active && planner.subscriptionStatus === 'active' ? 'Active' : 'Inactive'}
 </span>
 </td>
 <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
 {planner.lastLogin 
 ? new Date(planner.lastLogin).toLocaleDateString()
 : 'Never'
 }
 </td>
 <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
 <button
 onClick={() => handleTogglePlannerStatus(planner.id)}
 className={`${
 planner.is_active ? 'text-red-600 hover:text-red-900' : 'text-green-600 hover:text-green-900'
 }`}
 >
 {planner.is_active ? 'Deactivate' : 'Activate'}
 </button>
 <button className="text-blue-600 hover:text-blue-900">
 Edit
 </button>
 <button className="text-gray-600 hover:text-gray-900">
 View Weddings
 </button>
 </td>
 </tr>
 ))}
 </tbody>
 </table>
 </div>
 </Card>
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
 
 {/* Content Edit Modal */}
 <ContentEditModal
 isOpen={editModalOpen}
 onClose={() => {
 setEditModalOpen(false);
 setEditingSectionType('');
 setEditingSectionData(null);
 }}
 sectionType={editingSectionType}
 sectionData={editingSectionData}
 onSave={async (updatedData) => {
 if (!saasConfig) return;
 
 try {
 // Update the saasConfig with the new data
 const updatedConfig = { ...saasConfig };
 
 switch (editingSectionType) {
 case 'hero':
 Object.assign(updatedConfig, updatedData);
 break;
 case 'statistics':
 updatedConfig.statistics = updatedData.statistics;
 break;
 case 'trust_indicators':
 updatedConfig.trust_indicators = updatedData.trust_indicators;
 break;
 }
 
 // Save to backend with the updated config
 await handleSaveSaasConfig(updatedConfig);
 
 // Only update state and close modal if save was successful
 setSaasConfig(updatedConfig);
 setEditModalOpen(false);
 setEditingSectionType('');
 setEditingSectionData(null);
 } catch (error) {
 console.error('Error in modal save:', error);
 // Don't close modal if save failed, so user can retry
 }
 }}
 />
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
 is_featured: plan?.is_featured || false,
 is_active: plan?.is_active !== false,
 display_order: plan?.display_order || 0,
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
 <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
 <h2 className="text-2xl font-bold mb-4">
 {isEditing ? 'Edit Plan' : 'Create New Plan'}
 </h2>
 
 <form onSubmit={handleSubmit} className="space-y-4">
 <div className="grid grid-cols-2 gap-4">
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">Plan Name</label>
 <input
 type="text"
 required
 value={formData.name}
 onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
 className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">Monthly Price ($)</label>
 <input
 type="number"
 step="0.01"
 min="0"
 value={formData.price_monthly}
 onChange={(e) => setFormData(prev => ({ ...prev, price_monthly: parseFloat(e.target.value) || 0 }))}
 className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
 <textarea
 value={formData.description}
 onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
 className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 rows={2}
 />
 </div>

 <div className="grid grid-cols-3 gap-4">
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">Max Weddings</label>
 <input
 type="number"
 min="-1"
 value={formData.max_weddings}
 onChange={(e) => setFormData(prev => ({ ...prev, max_weddings: parseInt(e.target.value) || 0 }))}
 className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 placeholder="-1 for unlimited"
 />
 </div>
 
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">AI Credits/Month</label>
 <input
 type="number"
 min="0"
 value={formData.ai_credits_monthly}
 onChange={(e) => setFormData(prev => ({ ...prev, ai_credits_monthly: parseInt(e.target.value) || 0 }))}
 className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 
 <div>
 <label className="block text-sm font-medium text-gray-700 mb-1">Storage (GB)</label>
 <input
 type="number"
 min="0"
 value={formData.storage_gb}
 onChange={(e) => setFormData(prev => ({ ...prev, storage_gb: parseInt(e.target.value) || 0 }))}
 className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
 />
 </div>
 </div>

 <div>
 <label className="block text-sm font-medium text-gray-700 mb-2">Features</label>
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
 className="px-4 py-2 text-gray-600 border border-gray-300 rounded hover:bg-gray-50"
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