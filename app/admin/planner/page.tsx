'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter } from 'next/navigation';
import { formatDate as formatUtcDate, formatDateTime } from '@/utils/dateFormat';
import PageHeader from '../components/PageHeader';
import OnboardingModal from '../components/OnboardingModal';

interface Wedding {
 id: string;
 couple_names: string;
 date: string;
 slug: string;
 venue?: string;
 guest_count?: number;
 assigned_planner_email?: string;
 status?: string;
 events?: Array<{
 type: string;
 date: string;
 details?: any;
 }>;
 created_at?: string;
 rsvp_stats?: {
 confirmed: number;
 declined: number;
 pending: number;
 response_rate: number;
 };
 progress_percentage?: number;
 days_until_wedding?: number;
}

interface RSVPStats {
 total_guests: number;
 total_plus_ones_allowed: number;
 total_plus_ones_submitted: number;
 confirmed: number;
 confirmed_plus_ones_allowed: number;
 confirmed_plus_ones_submitted: number;
 declined: number;
 pending: number;
 pending_plus_ones_allowed: number;
}

interface AIInsight {
  title: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
  action_url: string;
  icon: string;
}

export default function WeddingPlannerDashboard() {
 const { token, userProfile, fetchUserProfile } = useAdmin();
 const router = useRouter();
 const [weddings, setWeddings] = useState<Wedding[]>([]);
 const [stats, setStats] = useState<RSVPStats>({ total_guests: 0, total_plus_ones_allowed: 0, total_plus_ones_submitted: 0, confirmed: 0, confirmed_plus_ones_allowed: 0, confirmed_plus_ones_submitted: 0, declined: 0, pending: 0, pending_plus_ones_allowed: 0 });
 const [loading, setLoading] = useState(true);
 const [error, setError] = useState('');
 const [recentActivity, setRecentActivity] = useState<any[]>([]);

 // AI Insights state
 const [selectedInsightWedding, setSelectedInsightWedding] = useState<string>('');
 const [aiInsights, setAiInsights] = useState<AIInsight[]>([]);
 const [insightsLoading, setInsightsLoading] = useState(false);
 const [insightsError, setInsightsError] = useState('');

 // Onboarding modal state
 const [isOnboardingOpen, setIsOnboardingOpen] = useState(false);
 const [hasUserDismissedOnboarding, setHasUserDismissedOnboarding] = useState(false);

 const fetchMyWeddings = useCallback(async () => {
 try {
 const baseUrl = getApiBaseUrl();
 // Use the new optimized metrics API
 const response = await fetch(`${baseUrl}/admin/planner/metrics`, {
 headers: {
 'Authorization': `Bearer ${token}`,
 'Content-Type': 'application/json',
 },
 });

 if (response.ok) {
 const data = await response.json();
 setWeddings(data.weddings);
 setStats({
 total_guests: data.summary.total_guests,
 total_plus_ones_allowed: data.summary.total_plus_ones_allowed || 0,
 total_plus_ones_submitted: data.summary.total_plus_ones_submitted || 0,
 confirmed: data.summary.confirmed_rsvps,
 confirmed_plus_ones_allowed: data.summary.confirmed_plus_ones_allowed || 0,
 confirmed_plus_ones_submitted: data.summary.confirmed_plus_ones_submitted || 0,
 declined: data.summary.declined_rsvps,
 pending: data.summary.pending_rsvps,
 pending_plus_ones_allowed: data.summary.pending_plus_ones_allowed || 0,
 });
 setRecentActivity(data.recent_activity);
 } else {
 setError('Failed to fetch dashboard data');
 }
 } catch (error) {
 setError('Failed to fetch dashboard data');
 } finally {
 setLoading(false);
 }
 }, [token]);

 // Fetch AI insights for selected wedding
 const fetchAIInsights = useCallback(async (weddingId: string, forceRefresh = false) => {
   if (!weddingId || !token) return;

   setInsightsLoading(true);
   setInsightsError('');

   try {
     const baseUrl = getApiBaseUrl();
     const url = `${baseUrl}/admin/ai/weddings/${weddingId}/insights${forceRefresh ? '?force_refresh=true' : ''}`;

     const response = await fetch(url, {
       headers: {
         'Authorization': `Bearer ${token}`,
         'Content-Type': 'application/json',
       },
     });

     if (response.ok) {
       const data = await response.json();
       setAiInsights(data.insights || []);
       // Show warning if using cached fallback
       if (data.warning) {
         setInsightsError('');  // Clear any previous error
       }
     } else {
       const errorData = await response.json().catch(() => ({}));
       const detail = errorData.detail;
       const message = typeof detail === 'object' ? detail?.message : detail;

       if (response.status === 402) {
         setInsightsError(message || 'Insufficient AI credits. Upgrade your plan for more.');
       } else if (response.status === 429) {
         setInsightsError(message || 'AI is busy. Please wait a moment and try again.');
       } else if (response.status === 503) {
         setInsightsError(message || 'AI service temporarily unavailable. Try again shortly.');
       } else if (response.status === 504) {
         setInsightsError(message || 'AI request timed out. Try again.');
       } else {
         setInsightsError(message || 'Unable to load insights. Try refreshing.');
       }
       // Don't clear existing insights on error — keep showing previous insights
       // so the planner still has something useful to look at
     }
   } catch {
     setInsightsError('Network error. Check your connection and try again.');
   } finally {
     setInsightsLoading(false);
   }
 }, [token]);

 // Auto-select first wedding for insights when weddings load
 useEffect(() => {
   if (weddings.length > 0 && !selectedInsightWedding) {
     setSelectedInsightWedding(weddings[0].id);
   }
 }, [weddings, selectedInsightWedding]);

 // Fetch insights when selected wedding changes
 useEffect(() => {
   if (selectedInsightWedding) {
     fetchAIInsights(selectedInsightWedding);
   }
 }, [selectedInsightWedding, fetchAIInsights]);

 useEffect(() => {
 if (!token) {
 router.push('/admin/login');
 return;
 }

 if (!userProfile) {
 fetchUserProfile();
 return;
 }

 // Only wedding planners can access this dashboard (strict role separation)
 if (userProfile && !userProfile.is_wedding_planner) {
 router.push('/admin');
 return;
 }

 fetchMyWeddings();
 }, [fetchMyWeddings, fetchUserProfile, router, token, userProfile]);

 // Check if onboarding should be shown (one-time only for new planners)
 useEffect(() => {
   if (userProfile && userProfile.is_wedding_planner && !userProfile.onboarding_completed && !hasUserDismissedOnboarding) {
     setIsOnboardingOpen(true);
   }
 }, [userProfile, hasUserDismissedOnboarding]);

 // Handler for when onboarding is completed or skipped
 const handleOnboardingComplete = () => {
   setHasUserDismissedOnboarding(true); // Track that user dismissed it
   setIsOnboardingOpen(false);
   // Refresh user profile to get updated onboarding status
   fetchUserProfile();
 };

  const formatDisplayDate = (dateString: string) => {
    return formatUtcDate(dateString, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

 if (loading) {
 return (
 <div className="min-h-screen flex items-center justify-center">
 <div className="text-center">
 <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
 <p className="text-gray-600 dark:text-gray-400">Loading your weddings...</p>
 </div>
 </div>
 );
 }

 return (
 <div className="space-y-6">
 <PageHeader
 title={`Welcome back, ${userProfile?.user_data?.company_name || userProfile?.email}!`}
 description="Here's what's happening with your weddings today."
 />

 {/* Team Member Access Notice */}
 {userProfile?.is_team_member && userProfile?.team_wedding_access === 'assigned' && (
 <div className="text-sm text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-slate-900/50 rounded-lg px-4 py-3 border border-gray-200 dark:border-slate-700 flex items-start gap-3">
 <svg className="w-5 h-5 text-gray-400 dark:text-gray-500 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
 <path fillRule="evenodd" d="M18 5v8a2 2 0 01-2 2h-5l-5 4v-4H4a2 2 0 01-2-2V5a2 2 0 012-2h12a2 2 0 012 2zm-11-1a1 1 0 11-2 0 1 1 0 012 0zM8 9a1 1 0 100-2 1 1 0 000 2zm5-1a1 1 0 11-2 0 1 1 0 012 0z" clipRule="evenodd" />
 </svg>
 <div>
 <p className="font-medium text-gray-700 dark:text-gray-300">Filtered View</p>
 <p className="text-gray-600 dark:text-gray-400">Showing data for your {userProfile.team_assigned_wedding_ids?.length || 0} assigned wedding{(userProfile.team_assigned_wedding_ids?.length || 0) !== 1 ? 's' : ''}</p>
 </div>
 </div>
 )}

 {/* Stats Cards */}
 <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
   {/* Active Weddings */}
   <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
     <div className="flex flex-col items-center text-center">
       <div className="w-10 h-10 bg-blue-500 rounded-lg flex items-center justify-center mb-3">
         <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
           <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
         </svg>
       </div>
       <p className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">Active Weddings</p>
       <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">{weddings.length}</p>
     </div>
   </div>

   {/* RSVPs Confirmed — with plus-ones */}
   <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
     <div className="flex flex-col items-center text-center">
       <div className="w-10 h-10 bg-green-500 rounded-lg flex items-center justify-center mb-3">
         <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
           <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
         </svg>
       </div>
       <p className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">RSVPs Confirmed</p>
       <div className="flex items-baseline gap-3 justify-center">
         <div>
           <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">{stats.confirmed}</p>
           <p className="text-xs text-gray-400 dark:text-gray-500">guests</p>
         </div>
         {stats.confirmed_plus_ones_submitted > 0 && (
           <div className="border-l border-gray-200 dark:border-gray-600 pl-3">
             <p className="text-xl font-semibold text-green-600 dark:text-green-400">+{stats.confirmed_plus_ones_submitted}</p>
             <p className="text-xs text-gray-400 dark:text-gray-500">plus-ones</p>
           </div>
         )}
       </div>
     </div>
   </div>

   {/* Pending RSVPs — with plus-ones */}
   <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
     <div className="flex flex-col items-center text-center">
       <div className="w-10 h-10 bg-yellow-500 rounded-lg flex items-center justify-center mb-3">
         <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
           <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
         </svg>
       </div>
       <p className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">Pending RSVPs</p>
       <div className="flex items-baseline gap-3 justify-center">
         <div>
           <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">{stats.pending}</p>
           <p className="text-xs text-gray-400 dark:text-gray-500">guests</p>
         </div>
         {stats.pending_plus_ones_allowed > 0 && (
           <div className="border-l border-gray-200 dark:border-gray-600 pl-3">
             <p className="text-xl font-semibold text-yellow-600 dark:text-yellow-400">+{stats.pending_plus_ones_allowed}</p>
             <p className="text-xs text-gray-400 dark:text-gray-500">plus-ones</p>
           </div>
         )}
       </div>
     </div>
   </div>

   {/* Total Guests — with plus-ones */}
   <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
     <div className="flex flex-col items-center text-center">
       <div className="w-10 h-10 bg-purple-500 rounded-lg flex items-center justify-center mb-3">
         <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
           <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
         </svg>
       </div>
       <p className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">Total Guests</p>
       <div className="flex items-baseline gap-3 justify-center">
         <div>
           <p className="text-3xl font-bold text-gray-900 dark:text-gray-100">{stats.total_guests}</p>
           <p className="text-xs text-gray-400 dark:text-gray-500">guests</p>
         </div>
         {stats.total_plus_ones_allowed > 0 && (
           <div className="border-l border-gray-200 dark:border-gray-600 pl-3">
             <p className="text-xl font-semibold text-purple-600 dark:text-purple-400">+{stats.total_plus_ones_allowed}</p>
             <p className="text-xs text-gray-400 dark:text-gray-500">plus-ones</p>
           </div>
         )}
       </div>
     </div>
   </div>
 </div>

 {/* Weddings List */}
 <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
 <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
 <div className="flex items-center justify-between">
 <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Your Weddings</h2>
 <button
 onClick={() => router.push('/admin/weddings')}
 className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-indigo-700 transition-colors"
 >
 View All
 </button>
 </div>
 </div>

 {error && (
 <div className="p-6 text-red-600 dark:text-red-300 bg-red-50 border-b border-red-200">
 {error}
 </div>
 )}

 <div className="divide-y divide-gray-200 dark:divide-gray-700">
 {weddings.length === 0 ? (
 <div className="p-6 text-center text-gray-500 dark:text-gray-400">
 <svg className="w-12 h-12 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
 </svg>
 <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">No weddings assigned</h3>
 <p className="text-gray-500 dark:text-gray-400">Contact your administrator to get weddings assigned to you.</p>
 </div>
 ) : (
 weddings.map((wedding) => (
 <div key={wedding.id} className="p-6 hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors">
 <div className="flex items-center justify-between">
 <div className="flex-1">
 <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1">
 {wedding.couple_names}
 </h3>
 <div className="flex items-center space-x-4 text-sm text-gray-500 dark:text-gray-400">
 <span> {formatDisplayDate(wedding.date)}</span>
 {wedding.venue && <span> {wedding.venue}</span>}
 {wedding.guest_count && <span> {wedding.guest_count} guests</span>}
 <span className={`px-2 py-1 rounded-full text-xs ${
 wedding.status === 'active' ? 'bg-green-100 text-green-800' :
 wedding.status === 'planning' ? 'bg-yellow-100 text-yellow-800' :
 'bg-gray-100 text-gray-800'
 }`}>
 {wedding.status || 'active'}
 </span>
 </div>
 </div>
 <div className="flex space-x-2">
 <button
 onClick={() => router.push(`/admin/weddings/${wedding.id}`)}
 className="bg-blue-100 text-blue-700 dark:text-blue-300 px-3 py-1 rounded-lg text-sm hover:bg-blue-200 transition-colors"
 >
 Manage
 </button>
 <a
 href={`/${wedding.slug}`}
 target="_blank"
 className="bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-gray-300 px-3 py-1 rounded-lg text-sm hover:bg-gray-200 transition-colors inline-block"
 >
 View Site
 </a>
 </div>
 </div>
 </div>
 ))
 )}
 </div>
 </div>

 {/* Quick Actions */}
 <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
 <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Quick Actions</h2>
 <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
 <button
 onClick={() => router.push('/admin/guests')}
 className="flex items-center p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors"
 >
 <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center mr-3">
 <svg className="w-5 h-5 text-green-600 dark:text-green-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
 </svg>
 </div>
 <div className="text-left">
 <p className="font-medium text-gray-900 dark:text-gray-100">Manage Guests</p>
 <p className="text-sm text-gray-500 dark:text-gray-400">View and edit guest lists</p>
 </div>
 </button>

 <button
 onClick={() => router.push('/admin/reminders')}
 className="flex items-center p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors"
 >
 <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center mr-3">
 <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 7.89a2 2 0 002.82 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
 </svg>
 </div>
 <div className="text-left">
 <p className="font-medium text-gray-900 dark:text-gray-100">Send Reminders</p>
 <p className="text-sm text-gray-500 dark:text-gray-400">Email and SMS notifications</p>
 </div>
 </button>

 <button
 onClick={() => router.push('/admin/gallery/upload')}
 className="flex items-center p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors"
 >
 <div className="w-8 h-8 bg-purple-100 rounded-lg flex items-center justify-center mr-3">
 <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
 </svg>
 </div>
 <div className="text-left">
 <p className="font-medium text-gray-900 dark:text-gray-100">Upload Photos</p>
 <p className="text-sm text-gray-500 dark:text-gray-400">Add to wedding galleries</p>
 </div>
 </button>
 </div>
 </div>

      {/* AI Insights Card */}
      {weddings.length > 0 && (
        <div className="bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-800 dark:to-slate-900 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">AI Insights</h2>
            </div>

            <div className="flex items-center space-x-3">
              {/* Wedding Selector */}
              {weddings.length > 1 && (
                <select
                  value={selectedInsightWedding}
                  onChange={(e) => setSelectedInsightWedding(e.target.value)}
                  className="text-sm border border-slate-300 dark:border-slate-600 rounded-lg px-3 py-1.5 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500"
                >
                  {weddings.map((w) => (
                    <option key={w.id} value={w.id}>{w.couple_names}</option>
                  ))}
                </select>
              )}

              {/* Refresh Button */}
              <button
                onClick={() => fetchAIInsights(selectedInsightWedding, true)}
                disabled={insightsLoading}
                className="p-2 text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
                title="Refresh insights (uses 2 credits)"
              >
                <svg className={`w-5 h-5 ${insightsLoading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
            </div>
          </div>

          {/* Loading State */}
          {insightsLoading && (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="animate-pulse flex items-start space-x-3 p-3 bg-white dark:bg-slate-800 rounded-lg">
                  <div className="w-8 h-8 bg-slate-200 dark:bg-slate-700 rounded-lg"></div>
                  <div className="flex-1 space-y-2">
                    <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-1/3"></div>
                    <div className="h-3 bg-slate-200 dark:bg-slate-700 rounded w-2/3"></div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Error State — shown as a banner above any existing insights */}
          {insightsError && !insightsLoading && (
            <div className="mb-3 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg flex items-center justify-between">
              <div className="flex items-center gap-2">
                <svg className="w-5 h-5 text-amber-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <p className="text-sm text-amber-800 dark:text-amber-200">{insightsError}</p>
              </div>
              <button
                onClick={() => fetchAIInsights(selectedInsightWedding, true)}
                className="text-sm text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 whitespace-nowrap ml-3"
              >
                Try again
              </button>
            </div>
          )}

          {/* Empty State — only show when no insights AND no error */}
          {!insightsLoading && !insightsError && aiInsights.length === 0 && (
            <div className="text-center py-6 text-slate-500 dark:text-slate-400">
              <svg className="w-10 h-10 mx-auto mb-2 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              <p className="text-sm">No insights available yet</p>
            </div>
          )}

          {/* Insights List — show even with error banner (previous insights still useful) */}
          {!insightsLoading && aiInsights.length > 0 && (
            <div className="space-y-3">
              {aiInsights.map((insight, index) => {
                // Icon mapping
                const iconMap: Record<string, React.ReactNode> = {
                  'users': (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                    </svg>
                  ),
                  'dollar-sign': (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  ),
                  'calendar': (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  ),
                  'clock': (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  ),
                  'alert-triangle': (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  ),
                  'check-circle': (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  ),
                };

                const priorityColors = {
                  high: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
                  medium: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
                  low: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
                };

                const iconColors = {
                  high: 'bg-red-100 text-red-600 dark:bg-red-900/50 dark:text-red-400',
                  medium: 'bg-yellow-100 text-yellow-600 dark:bg-yellow-900/50 dark:text-yellow-400',
                  low: 'bg-green-100 text-green-600 dark:bg-green-900/50 dark:text-green-400',
                };

                return (
                  <button
                    key={index}
                    onClick={() => router.push(insight.action_url)}
                    className="w-full flex items-start space-x-3 p-3 bg-white dark:bg-slate-800 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors text-left border border-slate-100 dark:border-slate-700"
                  >
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${iconColors[insight.priority]}`}>
                      {iconMap[insight.icon] || iconMap['calendar']}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2 mb-1">
                        <h4 className="font-medium text-slate-900 dark:text-slate-100 truncate">{insight.title}</h4>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${priorityColors[insight.priority]}`}>
                          {insight.priority}
                        </span>
                      </div>
                      <p className="text-sm text-slate-600 dark:text-slate-400 line-clamp-2">{insight.description}</p>
                    </div>
                    <svg className="w-5 h-5 text-slate-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                );
              })}
            </div>
          )}

          <p className="text-xs text-slate-400 dark:text-slate-500 mt-4 text-center">
            Insights refresh on page load • 2 credits per refresh
          </p>
        </div>
      )}

 {/* Recent Activity & Progress Tracking */}
 <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
 {/* Progress Overview */}
 <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
 <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Wedding Progress</h2>
 <div className="space-y-4">
 {weddings.slice(0, 3).map((wedding) => {
 const progressPercentage = wedding.progress_percentage || 0;
 const daysUntilWedding = wedding.days_until_wedding || 0;
 return (
 <div key={wedding.id} className="border-b border-gray-100 pb-4 last:border-b-0">
 <div className="flex items-center justify-between mb-2">
 <h4 className="font-medium text-gray-900 dark:text-gray-100">{wedding.couple_names}</h4>
 <span className="text-sm text-gray-500 dark:text-gray-400">
 {daysUntilWedding > 0 ? `${daysUntilWedding} days left` :
 daysUntilWedding === 0 ? 'Today!' :
 'Wedding passed'}
 </span>
 </div>
 <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
 <div
 className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
 style={{ width: `${progressPercentage}%` }}
 ></div>
 </div>
 <div className="flex justify-between text-sm text-gray-500 dark:text-gray-400">
 <span>{progressPercentage}% complete</span>
 <span>{wedding.rsvp_stats?.confirmed || 0} / {wedding.guest_count || 0} RSVPs</span>
 </div>
 </div>
 );
 })}
 </div>
 </div>

 {/* Recent Activity */}
 <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
 <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Recent Activity</h2>
 <div className="space-y-4">
 {recentActivity.length > 0 ? recentActivity.map((activity, index) => (
 <div key={index} className="flex items-start space-x-3">
 <div className={`w-2 h-2 rounded-full mt-2 ${
 activity.type === 'rsvp_received' ? 'bg-green-500' :
 activity.type === 'guest_updated' ? 'bg-blue-500' :
 activity.type === 'email_sent' ? 'bg-yellow-500' :
 activity.type === 'support_ticket_created' ? 'bg-red-500' :
 'bg-purple-500'
 }`}></div>
 <div>
 <p className="text-sm text-gray-900 dark:text-gray-100">{activity.message}</p>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {formatDateTime(activity.timestamp, {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
              hour: 'numeric',
              minute: '2-digit',
            })}
          </p>
 </div>
 </div>
 )) : (
 <div className="text-center text-gray-500 dark:text-gray-400 py-4">
 <p className="text-sm">No recent activity</p>
 </div>
 )}
 </div>
 <button
 className="mt-4 text-sm text-indigo-600 hover:text-indigo-800 transition-colors"
 onClick={() => router.push('/admin/planner/activity-log')}
 >
 View all activity →
 </button>
 </div>
 </div>

      {/* Onboarding Modal - shows one-time for new planners */}
      <OnboardingModal
        isOpen={isOnboardingOpen}
        onClose={() => setIsOnboardingOpen(false)}
        onComplete={handleOnboardingComplete}
      />
 </div>
 );
}
