'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';

interface Analytics {
  form_id: string;
  form_name: string;
  total_responses: number;
  distribution_stats: {
    sent: number;
    opened: number;
    clicked: number;
    submitted: number;
    open_rate: number;
    click_rate: number;
    completion_rate: number;
  };
  created_at: string;
  last_response?: string;
}

interface Form {
  id: string;
  name: string;
  settings: {
    title: string;
    description?: string;
  };
  fields: any[];
}

export default function FormAnalyticsPage() {
  const params = useParams();
  const router = useRouter();
  const { token } = useAdmin();
  const formId = params.id as string;

  const [form, setForm] = useState<Form | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token || !formId) return;
    fetchFormAndAnalytics();
  }, [token, formId]);

  const fetchFormAndAnalytics = async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      
      // Fetch form details and analytics in parallel
      const [formResponse, analyticsResponse] = await Promise.all([
        fetch(`${baseUrl}/admin/forms/${formId}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }),
        fetch(`${baseUrl}/admin/forms/${formId}/analytics`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        })
      ]);

      if (formResponse.ok && analyticsResponse.ok) {
        const formData = await formResponse.json();
        const analyticsData = await analyticsResponse.json();
        
        setForm(formData);
        setAnalytics(analyticsData);
      } else {
        setError('Failed to load form analytics');
      }
    } catch (error) {
      setError('Failed to load analytics data');
    } finally {
      setLoading(false);
    }
  };

  const AnalyticsCard = ({ 
    title, 
    value, 
    subtitle, 
    icon, 
    color = 'blue' 
  }: { 
    title: string; 
    value: string | number; 
    subtitle?: string; 
    icon: React.ReactNode; 
    color?: 'blue' | 'green' | 'purple' | 'orange' | 'red';
  }) => {
    const colorClasses = {
      blue: 'bg-blue-500 text-blue-100',
      green: 'bg-green-500 text-green-100',
      purple: 'bg-purple-500 text-purple-100',
      orange: 'bg-orange-500 text-orange-100',
      red: 'bg-red-500 text-red-100'
    };

    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700 p-6">
        <div className="flex items-center">
          <div className={`p-3 rounded-lg ${colorClasses[color]} mr-4`}>
            {icon}
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-600 dark:text-gray-300 dark:text-gray-300">{title}</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-gray-100 dark:text-gray-100">{value}</p>
            {subtitle && <p className="text-sm text-gray-500 dark:text-gray-400 dark:text-gray-400">{subtitle}</p>}
          </div>
        </div>
      </div>
    );
  };

  const ProgressBar = ({ percentage, color = 'blue' }: { percentage: number; color?: string }) => {
    const colorClasses = {
      blue: 'bg-blue-600',
      green: 'bg-green-600',
      purple: 'bg-purple-600',
      orange: 'bg-orange-600'
    };

    return (
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div 
          className={`h-2 rounded-full transition-all duration-300 ${colorClasses[color as keyof typeof colorClasses]}`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        ></div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-300 dark:text-gray-300">Loading analytics...</p>
        </div>
      </div>
    );
  }

  if (error || !form || !analytics) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error || 'Analytics not found'}</p>
          <button
            onClick={() => router.push('/admin/forms')}
            className="text-blue-600 hover:text-blue-800"
          >
            ← Back to Forms
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto py-8 px-4">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => router.push('/admin/forms')}
              className="flex items-center text-gray-600 dark:text-gray-300 dark:text-gray-300 hover:text-gray-800 dark:hover:text-gray-100"
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Back to Forms
            </button>
            
            <div className="flex space-x-3">
              <button
                onClick={() => router.push(`/admin/forms/${formId}/responses`)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                View Responses
              </button>
              <button
                onClick={() => router.push(`/admin/forms/${formId}/send`)}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
              >
                Send Form
              </button>
            </div>
          </div>
          
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700 p-6">
            <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 dark:text-gray-100 mb-2">Form Analytics</h1>
            <div className="flex items-center text-gray-600 dark:text-gray-300 dark:text-gray-300">
              <span className="text-lg font-medium">{form.name}</span>
              <span className="mx-2">•</span>
              <span>{form.settings.title}</span>
            </div>
            {form.settings.description && (
              <p className="text-gray-500 dark:text-gray-400 dark:text-gray-400 mt-2">{form.settings.description}</p>
            )}
          </div>
        </div>

        {/* Overview Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <AnalyticsCard
            title="Total Responses"
            value={analytics.total_responses}
            icon={
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            }
            color="green"
          />
          
          <AnalyticsCard
            title="Forms Sent"
            value={analytics.distribution_stats.sent}
            icon={
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                <path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z" />
                <path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z" />
              </svg>
            }
            color="blue"
          />
          
          <AnalyticsCard
            title="Completion Rate"
            value={`${analytics.distribution_stats.completion_rate}%`}
            subtitle={`${analytics.distribution_stats.submitted} of ${analytics.distribution_stats.sent} sent`}
            icon={
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            }
            color="purple"
          />
          
          <AnalyticsCard
            title="Open Rate"
            value={`${analytics.distribution_stats.open_rate}%`}
            subtitle={`${analytics.distribution_stats.opened} emails opened`}
            icon={
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
              </svg>
            }
            color="orange"
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Email Performance */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700 p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-6">Email Performance</h3>
            
            <div className="space-y-6">
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Emails Sent</span>
                  <span className="text-sm text-gray-900 dark:text-gray-100">{analytics.distribution_stats.sent}</span>
                </div>
                <ProgressBar percentage={100} color="blue" />
              </div>
              
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Emails Opened</span>
                  <span className="text-sm text-gray-900 dark:text-gray-100">
                    {analytics.distribution_stats.opened} ({analytics.distribution_stats.open_rate}%)
                  </span>
                </div>
                <ProgressBar 
                  percentage={analytics.distribution_stats.open_rate} 
                  color="orange" 
                />
              </div>
              
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Form Link Clicked</span>
                  <span className="text-sm text-gray-900 dark:text-gray-100">
                    {analytics.distribution_stats.clicked} ({analytics.distribution_stats.click_rate}%)
                  </span>
                </div>
                <ProgressBar 
                  percentage={analytics.distribution_stats.click_rate} 
                  color="purple" 
                />
              </div>
              
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Form Completed</span>
                  <span className="text-sm text-gray-900 dark:text-gray-100">
                    {analytics.distribution_stats.submitted} ({analytics.distribution_stats.completion_rate}%)
                  </span>
                </div>
                <ProgressBar 
                  percentage={analytics.distribution_stats.completion_rate} 
                  color="green" 
                />
              </div>
            </div>
          </div>

          {/* Form Insights */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700 p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-6">Form Insights</h3>
            
            <div className="space-y-4">
              <div className="flex justify-between items-center p-4 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100">Form Fields</p>
                  <p className="text-sm text-gray-600 dark:text-gray-300">Total questions in form</p>
                </div>
                <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {form.fields.length}
                </div>
              </div>
              
              <div className="flex justify-between items-center p-4 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100">Form Created</p>
                  <p className="text-sm text-gray-600 dark:text-gray-300">Initial creation date</p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-gray-900 dark:text-gray-100">
                    {new Date(analytics.created_at).toLocaleDateString()}
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-300">
                    {new Date(analytics.created_at).toLocaleDateString('en-US', { 
                      weekday: 'long', 
                      year: 'numeric', 
                      month: 'long', 
                      day: 'numeric' 
                    })}
                  </p>
                </div>
              </div>

              {analytics.last_response && (
                <div className="flex justify-between items-center p-4 bg-gray-50 rounded-lg">
                  <div>
                    <p className="font-medium text-gray-900 dark:text-gray-100">Last Response</p>
                    <p className="text-sm text-gray-600 dark:text-gray-300">Most recent submission</p>
                  </div>
                  <div className="text-right">
                    <p className="font-bold text-gray-900 dark:text-gray-100">
                      {new Date(analytics.last_response).toLocaleDateString()}
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-300">
                      {new Date(analytics.last_response).toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Performance Tips */}
        <div className="mt-8 bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Performance Tips</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {analytics.distribution_stats.open_rate < 50 && (
              <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                <div className="flex items-start">
                  <svg className="w-5 h-5 text-yellow-600 mr-2 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  <div>
                    <h4 className="font-medium text-yellow-800">Low Open Rate</h4>
                    <p className="text-sm text-yellow-700">Consider improving your email subject line to increase opens.</p>
                  </div>
                </div>
              </div>
            )}

            {analytics.distribution_stats.click_rate < 30 && analytics.distribution_stats.open_rate > 0 && (
              <div className="p-4 bg-orange-50 border border-orange-200 rounded-lg">
                <div className="flex items-start">
                  <svg className="w-5 h-5 text-orange-600 mr-2 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                  </svg>
                  <div>
                    <h4 className="font-medium text-orange-800">Low Click Rate</h4>
                    <p className="text-sm text-orange-700">Your email message could be more compelling to encourage clicks.</p>
                  </div>
                </div>
              </div>
            )}

            {analytics.distribution_stats.completion_rate < 50 && analytics.distribution_stats.click_rate > 0 && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                <div className="flex items-start">
                  <svg className="w-5 h-5 text-red-600 mr-2 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                  <div>
                    <h4 className="font-medium text-red-800">Low Completion Rate</h4>
                    <p className="text-sm text-red-700">Consider shortening your form or making fields optional to improve completion.</p>
                  </div>
                </div>
              </div>
            )}

            {analytics.distribution_stats.completion_rate >= 70 && (
              <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex items-start">
                  <svg className="w-5 h-5 text-green-600 mr-2 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <div>
                    <h4 className="font-medium text-green-800">Great Performance!</h4>
                    <p className="text-sm text-green-700">Your form has an excellent completion rate. Keep up the good work!</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}