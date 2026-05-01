'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';

const API_BASE_URL = getApiBaseUrl();

export default function VerifyEmailChangePage() {
  const params = useParams();
  const router = useRouter();
  const token = params.token as string;
  const missingToken = !token;
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>(
    missingToken ? 'error' : 'loading'
  );
  const [message, setMessage] = useState(
    missingToken ? 'Invalid email-change verification link.' : ''
  );

  useEffect(() => {
    if (!token) {
      return;
    }

    const verifyEmailChange = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/verify-email-change/${token}`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        const data = await response.json();

        if (response.ok) {
          setStatus('success');
          setMessage(data.message || 'Your email address was updated successfully.');
          setTimeout(() => {
            router.push('/admin/profile');
          }, 3000);
        } else {
          setStatus('error');
          setMessage(data.detail || 'Email-change verification failed.');
        }
      } catch {
        setStatus('error');
        setMessage('An error occurred while verifying your email change. Please try again.');
      }
    };

    void verifyEmailChange();
  }, [token, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-8 text-center shadow-lg">
        {status === 'loading' && (
          <>
            <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 border-blue-600" />
            <h1 className="mb-2 text-2xl font-bold text-gray-900">Verifying Your Email Change</h1>
            <p className="text-gray-600">Please wait while we confirm your new email address...</p>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="mb-4 text-green-500">
              <svg className="mx-auto h-16 w-16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <h1 className="mb-4 text-2xl font-bold text-green-600">Email Change Verified</h1>
            <p className="mb-6 text-gray-600">{message}</p>
            <p className="mb-4 text-sm text-gray-500">
              You will be redirected to your profile in a few seconds...
            </p>
            <button
              onClick={() => router.push('/admin/profile')}
              className="w-full rounded-lg bg-blue-600 px-4 py-3 font-medium text-white transition-colors hover:bg-blue-700"
            >
              Go to Profile Now
            </button>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="mb-4 text-red-500">
              <svg className="mx-auto h-16 w-16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <h1 className="mb-4 text-2xl font-bold text-red-600">Verification Failed</h1>
            <p className="mb-6 text-gray-600">{message}</p>
            <div className="space-y-3">
              <button
                onClick={() => router.push('/admin/login')}
                className="w-full rounded-lg bg-blue-600 px-4 py-3 font-medium text-white transition-colors hover:bg-blue-700"
              >
                Go to Login
              </button>
              <button
                onClick={() => router.push('/')}
                className="w-full rounded-lg border border-gray-300 px-4 py-3 font-medium text-gray-700 transition-colors hover:bg-gray-50"
              >
                Back to Home
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
