"use client";

import React, { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { useAdmin } from '@/contexts/AdminContext';
import { CheckCircle2, Loader2, ArrowRight } from 'lucide-react';

export default function BillingSuccessPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { token } = useAdmin();
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const sessionId = searchParams.get('session_id');

    if (!sessionId) {
      setError('No session ID provided');
      setLoading(false);
      return;
    }

    // Verify the checkout session
    const verifySession = async () => {
      try {
        if (!token) {
          throw new Error('Not authenticated');
        }

        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_BASE_URL}/stripe/checkout-session/${sessionId}`,
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            credentials: 'include'
          }
        );

        if (!response.ok) {
          throw new Error('Failed to verify session');
        }

        const data = await response.json();
        setSession(data.session);
      } catch (err: any) {
        console.error('Error verifying session:', err);
        setError(err.message || 'Failed to verify payment');
      } finally {
        setLoading(false);
      }
    };

    verifySession();
  }, [searchParams, token]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400 dark:text-gray-400">Verifying your payment...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container max-w-2xl mx-auto py-16 px-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-red-600 dark:text-red-300">Payment Verification Failed</CardTitle>
            <CardDescription>
              We encountered an issue verifying your payment
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-gray-600 dark:text-gray-400 dark:text-gray-400">{error}</p>
          </CardContent>
          <CardFooter>
            <Button onClick={() => router.push('/admin/billing')}>
              Return to Billing
            </Button>
          </CardFooter>
        </Card>
      </div>
    );
  }

  return (
    <div className="container max-w-2xl mx-auto py-16 px-4">
      <Card className="border-green-200 dark:border-green-800">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center">
            <CheckCircle2 className="w-10 h-10 text-green-600 dark:text-green-300 dark:text-green-400" />
          </div>
          <CardTitle className="text-2xl text-green-600 dark:text-green-300 dark:text-green-400">
            Payment Successful!
          </CardTitle>
          <CardDescription>
            Your subscription has been activated
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-6 space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-gray-600 dark:text-gray-400 dark:text-gray-400">Payment Status</span>
              <span className="font-semibold capitalize">
                {session?.payment_status || 'Paid'}
              </span>
            </div>
            {session?.amount_total && (
              <div className="flex justify-between items-center">
                <span className="text-gray-600 dark:text-gray-400 dark:text-gray-400">Amount Paid</span>
                <span className="font-semibold">
                  ${session.amount_total.toFixed(2)} {session.currency?.toUpperCase()}
                </span>
              </div>
            )}
            <div className="flex justify-between items-center">
              <span className="text-gray-600 dark:text-gray-400 dark:text-gray-400">Subscription ID</span>
              <span className="font-mono text-sm">
                {session?.subscription || 'Processing...'}
              </span>
            </div>
          </div>

          <div className="space-y-2">
            <h3 className="font-semibold">What happens next?</h3>
            <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-400 dark:text-gray-400">
              <li className="flex items-start">
                <CheckCircle2 className="w-4 h-4 mr-2 mt-0.5 text-green-600 dark:text-green-300" />
                Your subscription is now active and ready to use
              </li>
              <li className="flex items-start">
                <CheckCircle2 className="w-4 h-4 mr-2 mt-0.5 text-green-600 dark:text-green-300" />
                You&apos;ll receive a confirmation email shortly
              </li>
              <li className="flex items-start">
                <CheckCircle2 className="w-4 h-4 mr-2 mt-0.5 text-green-600 dark:text-green-300" />
                You can now access all features included in your plan
              </li>
              <li className="flex items-start">
                <CheckCircle2 className="w-4 h-4 mr-2 mt-0.5 text-green-600 dark:text-green-300" />
                Manage your subscription anytime from the billing page
              </li>
            </ul>
          </div>
        </CardContent>
        <CardFooter className="flex gap-3">
          <Button
            onClick={() => router.push('/admin/dashboard')}
            className="flex-1"
          >
            Go to Dashboard
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
          <Button
            onClick={() => router.push('/admin/billing')}
            variant="outline"
            className="flex-1"
          >
            View Billing Details
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
