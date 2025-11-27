'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter } from 'next/navigation';
import { formatDate as formatUtcDate, formatDateTime } from '@/utils/dateFormat';

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
 confirmed: number;
 declined: number;
 pending: number;
}

export default function WeddingPlannerDashboard() {
 const { token, userProfile, fetchUserProfile } = useAdmin();
 const router = useRouter();
 const [weddings, setWeddings] = useState<Wedding[]>([]);
 const [stats, setStats] = useState<RSVPStats>({ total_guests: 0, confirmed: 0, declined: 0, pending: 0 });
 const [loading, setLoading] = useState(true);
 const [error, setError] = useState('');
 const [recentActivity, setRecentActivity] = useState<any[]>([]);

 const fetchMyWeddings = useCallback(async () => {
 try {
 const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

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
 confirmed: data.summary.confirmed_rsvps,
 declined: data.summary.declined_rsvps,
 pending: data.summary.pending_rsvps
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

 useEffect(() => {
 if (!token) {
 router.push('/admin/login');
 return;
 }

 if (!userProfile) {
 fetchUserProfile();
 return;
 }

 if (userProfile && !userProfile.is_wedding_planner) {
 router.push('/admin');
 return;
 }

 fetchMyWeddings();
 }, [fetchMyWeddings, fetchUserProfile, router, token, userProfile]);

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
 <p className="text-gray-600">Loading your weddings...</p>
 </div>
 </div>
 );
 }

 return (
 <div className="space-y-6">
 {/* Welcome Header */}
 <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
 <h1 className="text-2xl font-bold text-gray-900 mb-2">
 Welcome back, {userProfile?.user_data?.company_name || userProfile?.email}!
 </h1>
        <p className="text-gray-600">Here’s what’s happening with your weddings today.</p>
 </div>

 {/* Stats Cards */}
 <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
 <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
 <div className="flex items-center">
 <div className="flex-shrink-0">
 <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
 <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
 </svg>
 </div>
 </div>
 <div className="ml-4">
 <p className="text-sm font-medium text-gray-500">Active Weddings</p>
 <p className="text-2xl font-semibold text-gray-900">{weddings.length}</p>
 </div>
 </div>
 </div>

 <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
 <div className="flex items-center">
 <div className="flex-shrink-0">
 <div className="w-8 h-8 bg-green-500 rounded-lg flex items-center justify-center">
 <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
 </svg>
 </div>
 </div>
 <div className="ml-4">
 <p className="text-sm font-medium text-gray-500">RSVPs Confirmed</p>
 <p className="text-2xl font-semibold text-gray-900">{stats.confirmed}</p>
 </div>
 </div>
 </div>

 <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
 <div className="flex items-center">
 <div className="flex-shrink-0">
 <div className="w-8 h-8 bg-yellow-500 rounded-lg flex items-center justify-center">
 <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
 </svg>
 </div>
 </div>
 <div className="ml-4">
 <p className="text-sm font-medium text-gray-500">Pending RSVPs</p>
 <p className="text-2xl font-semibold text-gray-900">{stats.pending}</p>
 </div>
 </div>
 </div>

 <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
 <div className="flex items-center">
 <div className="flex-shrink-0">
 <div className="w-8 h-8 bg-purple-500 rounded-lg flex items-center justify-center">
 <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
 </svg>
 </div>
 </div>
 <div className="ml-4">
 <p className="text-sm font-medium text-gray-500">Total Guests</p>
 <p className="text-2xl font-semibold text-gray-900">{stats.total_guests}</p>
 </div>
 </div>
 </div>
 </div>

 {/* Weddings List */}
 <div className="bg-white rounded-lg shadow-sm border border-gray-200">
 <div className="px-6 py-4 border-b border-gray-200">
 <div className="flex items-center justify-between">
 <h2 className="text-lg font-semibold text-gray-900">Your Weddings</h2>
 <button
 onClick={() => router.push('/admin/weddings')}
 className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-indigo-700 transition-colors"
 >
 View All
 </button>
 </div>
 </div>

 {error && (
 <div className="p-6 text-red-600 bg-red-50 border-b border-red-200">
 {error}
 </div>
 )}

 <div className="divide-y divide-gray-200">
 {weddings.length === 0 ? (
 <div className="p-6 text-center text-gray-500">
 <svg className="w-12 h-12 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
 </svg>
 <h3 className="text-lg font-medium text-gray-900 mb-2">No weddings assigned</h3>
 <p className="text-gray-500">Contact your administrator to get weddings assigned to you.</p>
 </div>
 ) : (
 weddings.map((wedding) => (
 <div key={wedding.id} className="p-6 hover:bg-gray-50 transition-colors">
 <div className="flex items-center justify-between">
 <div className="flex-1">
 <h3 className="text-lg font-semibold text-gray-900 mb-1">
 {wedding.couple_names}
 </h3>
 <div className="flex items-center space-x-4 text-sm text-gray-500">
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
 className="bg-blue-100 text-blue-700 px-3 py-1 rounded-lg text-sm hover:bg-blue-200 transition-colors"
 >
 Manage
 </button>
 <a
 href={`/${wedding.slug}`}
 target="_blank"
 className="bg-gray-100 text-gray-700 px-3 py-1 rounded-lg text-sm hover:bg-gray-200 transition-colors inline-block"
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
 <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
 <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
 <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
 <button
 onClick={() => router.push('/admin/guests')}
 className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
 >
 <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center mr-3">
 <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
 </svg>
 </div>
 <div className="text-left">
 <p className="font-medium text-gray-900">Manage Guests</p>
 <p className="text-sm text-gray-500">View and edit guest lists</p>
 </div>
 </button>

 <button
 onClick={() => router.push('/admin/reminders')}
 className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
 >
 <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center mr-3">
 <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 7.89a2 2 0 002.82 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
 </svg>
 </div>
 <div className="text-left">
 <p className="font-medium text-gray-900">Send Reminders</p>
 <p className="text-sm text-gray-500">Email and SMS notifications</p>
 </div>
 </button>

 <button
 onClick={() => router.push('/admin/gallery/upload')}
 className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
 >
 <div className="w-8 h-8 bg-purple-100 rounded-lg flex items-center justify-center mr-3">
 <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
 </svg>
 </div>
 <div className="text-left">
 <p className="font-medium text-gray-900">Upload Photos</p>
 <p className="text-sm text-gray-500">Add to wedding galleries</p>
 </div>
 </button>
 </div>
 </div>

 {/* Recent Activity & Progress Tracking */}
 <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
 {/* Progress Overview */}
 <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
 <h2 className="text-lg font-semibold text-gray-900 mb-4">Wedding Progress</h2>
 <div className="space-y-4">
 {weddings.slice(0, 3).map((wedding) => {
 const progressPercentage = wedding.progress_percentage || 0;
 const daysUntilWedding = wedding.days_until_wedding || 0;

 return (
 <div key={wedding.id} className="border-b border-gray-100 pb-4 last:border-b-0">
 <div className="flex items-center justify-between mb-2">
 <h4 className="font-medium text-gray-900">{wedding.couple_names}</h4>
 <span className="text-sm text-gray-500">
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
 <div className="flex justify-between text-sm text-gray-500">
 <span>{progressPercentage}% complete</span>
 <span>{wedding.rsvp_stats?.confirmed || 0} / {wedding.guest_count || 0} RSVPs</span>
 </div>
 </div>
 );
 })}
 </div>
 </div>

 {/* Recent Activity */}
 <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
 <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Activity</h2>
 <div className="space-y-4">
 {recentActivity.length > 0 ? recentActivity.map((activity, index) => (
 <div key={index} className="flex items-start space-x-3">
 <div className={`w-2 h-2 rounded-full mt-2 ${
 activity.type === 'rsvp_received' ? 'bg-green-500' :
 activity.type === 'guest_updated' ? 'bg-blue-500' :
 activity.type === 'email_sent' ? 'bg-yellow-500' :
 'bg-purple-500'
 }`}></div>
 <div>
 <p className="text-sm text-gray-900">{activity.message}</p>
          <p className="text-xs text-gray-500">
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
 <div className="text-center text-gray-500 py-4">
 <p className="text-sm">No recent activity</p>
 </div>
 )}
 </div>
 <button
 className="mt-4 text-sm text-indigo-600 hover:text-indigo-800 transition-colors"
 onClick={() => router.push('/admin/activity-log')}
 >
 View all activity →
 </button>
 </div>
 </div>
 </div>
 );
}