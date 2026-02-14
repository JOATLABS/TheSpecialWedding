'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  getGoogleCalendarStatus,
  getGoogleAuthUrl,
  disconnectGoogleCalendar,
  GoogleCalendarStatus,
} from '@/services/calendarApi';
import { useAdmin } from '@/contexts/AdminContext';
import { formatAdminTimestamp, DEFAULT_TIMEZONE } from '@/utils/dateFormat';

interface GoogleCalendarConnectProps {
  onStatusChange?: (status: GoogleCalendarStatus) => void;
}

export default function GoogleCalendarConnect({
  onStatusChange,
}: GoogleCalendarConnectProps) {
  const { token } = useAdmin();
  const [status, setStatus] = useState<GoogleCalendarStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchStatus = useCallback(async () => {
    if (!token) return;

    try {
      setLoading(true);
      const calendarStatus = await getGoogleCalendarStatus(token);
      setStatus(calendarStatus);
      onStatusChange?.(calendarStatus);
    } catch (err) {
      console.error('Failed to fetch calendar status:', err);
    } finally {
      setLoading(false);
    }
  }, [token, onStatusChange]);

  useEffect(() => {
    if (token) {
      fetchStatus();
    }
  }, [token, fetchStatus]);

  const handleConnect = async () => {
    if (!token) return;

    try {
      setActionLoading(true);
      setError('');
      const { auth_url } = await getGoogleAuthUrl(token);
      // Redirect to Google OAuth consent screen
      window.location.href = auth_url;
    } catch (err) {
      setError('Failed to initiate Google Calendar connection');
      setActionLoading(false);
    }
  };

  const handleDisconnect = async () => {
    if (!token) return;

    const confirmed = window.confirm(
      'Are you sure you want to disconnect Google Calendar? Your tasks will be preserved but no longer sync.'
    );

    if (!confirmed) return;

    try {
      setActionLoading(true);
      setError('');
      await disconnectGoogleCalendar(token);
      await fetchStatus();
    } catch (err) {
      setError('Failed to disconnect Google Calendar');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <div className="flex items-center gap-3">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-indigo-600"></div>
          <span className="text-gray-600 dark:text-gray-400">
            Checking Google Calendar connection...
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          {/* Google Calendar Icon */}
          <div className="flex-shrink-0">
            <div
              className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                status?.connected
                  ? 'bg-green-100 dark:bg-green-900/30'
                  : 'bg-gray-100 dark:bg-gray-700'
              }`}
            >
              <svg
                className={`w-7 h-7 ${
                  status?.connected
                    ? 'text-green-600 dark:text-green-400'
                    : 'text-gray-400 dark:text-gray-500'
                }`}
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M19.5 3h-15A1.5 1.5 0 003 4.5v15A1.5 1.5 0 004.5 21h15a1.5 1.5 0 001.5-1.5v-15A1.5 1.5 0 0019.5 3zM12 17.25a5.25 5.25 0 110-10.5 5.25 5.25 0 010 10.5z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </div>
          </div>

          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Google Calendar
            </h3>
            {status?.connected ? (
              <div className="mt-1 space-y-1">
                <p className="text-sm text-green-600 dark:text-green-400 flex items-center gap-1">
                  <svg
                    className="w-4 h-4"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                      clipRule="evenodd"
                    />
                  </svg>
                  Connected
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Calendar: {status.calendar_id || 'Primary'}
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {status.events_synced} events synced
                </p>
                {status.last_sync && (
                  <p className="text-xs text-gray-400 dark:text-gray-500">
                    Last sync:{' '}
                    {formatAdminTimestamp(status.last_sync)}
                  </p>
                )}
              </div>
            ) : (
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Connect your Google Calendar to sync tasks and events
              </p>
            )}
          </div>
        </div>

        <div className="flex-shrink-0">
          {status?.connected ? (
            <button
              onClick={handleDisconnect}
              disabled={actionLoading}
              className="px-4 py-2 text-red-600 dark:text-red-400 border border-red-300 dark:border-red-700 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm"
            >
              {actionLoading ? 'Disconnecting...' : 'Disconnect'}
            </button>
          ) : (
            <button
              onClick={handleConnect}
              disabled={actionLoading}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm flex items-center gap-2"
            >
              {actionLoading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  Connecting...
                </>
              ) : (
                <>
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
                    />
                  </svg>
                  Connect
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      )}

      {/* Features description when not connected */}
      {!status?.connected && (
        <div className="mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
          <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-3">
            What you can do with Google Calendar:
          </h4>
          <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-400">
            <li className="flex items-center gap-2">
              <svg
                className="w-4 h-4 text-green-500"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
              Sync wedding tasks to your Google Calendar
            </li>
            <li className="flex items-center gap-2">
              <svg
                className="w-4 h-4 text-green-500"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
              Get reminders on your phone
            </li>
            <li className="flex items-center gap-2">
              <svg
                className="w-4 h-4 text-green-500"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
              View wedding events alongside your personal calendar
            </li>
            <li className="flex items-center gap-2">
              <svg
                className="w-4 h-4 text-green-500"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clipRule="evenodd"
                />
              </svg>
              Share availability with vendors and clients
            </li>
          </ul>
        </div>
      )}
    </div>
  );
}
