'use client';

import React from 'react';
import { useRouter } from 'next/navigation';

export default function PaymentSuccessPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-slate-900 p-4">
      <div className="max-w-md w-full bg-white dark:bg-slate-800 p-8 rounded-2xl shadow-xl text-center">
        <div className="w-20 h-20 bg-green-100 text-green-500 rounded-full flex items-center justify-center mx-auto mb-6">
          <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        </div>

        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">Payment Successful!</h1>
        <p className="text-gray-600 dark:text-gray-300 mb-8">
          Thank you for your payment. A confirmation has been sent to your email.
        </p>

        <button
          onClick={() => router.push('/')}
          className="w-full py-3 px-4 bg-gray-900 dark:bg-gray-700 hover:bg-gray-800 text-white rounded-lg font-medium transition-colors"
        >
          Return Home
        </button>
      </div>
    </div>
  );
}
