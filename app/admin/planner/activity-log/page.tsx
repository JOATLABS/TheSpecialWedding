'use client';

import { useCallback, useEffect, useState } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { formatDateTime } from '@/utils/dateFormat';

type ActivityItem = {
  id: string;
  type: string;
  message: string;
  timestamp: string;
  wedding_id?: string | null;
  metadata?: Record<string, unknown>;
};

export default function PlannerActivityLogPage() {
  const { token, userProfile, fetchUserProfile } = useAdmin();
  const router = useRouter();
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [limit] = useState<number>(100);

  const fetchActivities = useCallback(async () => {
    if (!token) return;

    try {
      setLoading(true);
      setError(null);
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/planner/activity-log?limit=${limit}`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache',
        },
        cache: 'no-store',
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || 'Failed to fetch activity log');
      }

      const data = await response.json();
      setActivities(data.activities || []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch activity log');
    } finally {
      setLoading(false);
    }
  }, [limit, token]);

  useEffect(() => {
    if (!token) {
      router.push('/admin/login');
      return;
    }

    if (!userProfile) {
      fetchUserProfile();
      return;
    }

    // Only wedding planners can access activity log (strict role separation)
    if (userProfile && !userProfile.is_wedding_planner) {
      router.push('/admin');
      return;
    }

    fetchActivities();
  }, [fetchActivities, fetchUserProfile, router, token, userProfile]);

  const renderStatusDot = (type: string) => {
    const color =
      type === 'rsvp_received'
        ? 'bg-green-500'
        : type === 'guest_updated'
        ? 'bg-blue-500'
        : type === 'email_sent'
        ? 'bg-yellow-500'
        : 'bg-purple-500';
    return <span className={`inline-block w-2 h-2 rounded-full ${color}`} />;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-semibold leading-tight text-slate-900 dark:text-white">Planner Activity Log</h1>
          <p className="text-gray-600 dark:text-gray-400">Detailed activity across weddings you manage.</p>
        </div>
        <button
          onClick={fetchActivities}
          className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 transition-colors"
        >
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 text-center text-gray-600 dark:text-gray-400">
          Loading activity...
        </div>
      ) : error ? (
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-red-200 p-6">
          <p className="text-red-700 dark:text-red-300 font-medium mb-2">Failed to load activity</p>
          <p className="text-red-600 dark:text-red-300 text-sm">{error}</p>
        </div>
      ) : activities.length === 0 ? (
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 text-center text-gray-600 dark:text-gray-400">
          No activity recorded yet.
        </div>
      ) : (
        <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
          <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Latest activity</h2>
            <span className="text-sm text-gray-500 dark:text-gray-400">{activities.length} items</span>
          </div>
          <ul className="divide-y divide-gray-200 dark:divide-gray-700">
            {activities.map((activity) => (
              <li key={activity.id} className="px-6 py-4 flex items-start space-x-3">
                <div className="mt-1">{renderStatusDot(activity.type)}</div>
                <div className="flex-1">
                  <p className="text-sm text-gray-900 dark:text-gray-100">{activity.message || 'Activity'}</p>
                  <div className="mt-1 text-xs text-gray-500 dark:text-gray-400 flex flex-wrap gap-2">
                    <span>
                      {formatDateTime(activity.timestamp, {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                        hour: 'numeric',
                        minute: '2-digit',
                      })}
                    </span>
                    {activity.wedding_id && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-gray-400">
                        Wedding: {activity.wedding_id}
                      </span>
                    )}
                    {activity.type && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700">
                        Type: {activity.type}
                      </span>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
