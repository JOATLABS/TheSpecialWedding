"use client";

import React, { useEffect, useState, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { useAdmin } from '@/contexts/AdminContext';
import {
  CheckCircle2,
  Loader2,
  ArrowRight,
  Download,
  ExternalLink,
  Calendar,
  CreditCard,
  Sparkles,
  Users,
  Database,
  Zap,
} from 'lucide-react';
import { getApiBaseUrl } from '@/utils/env';

/** Auto-redirect delay in seconds */
const REDIRECT_DELAY_SECONDS = 15;

interface PlanDetails {
  name: string;
  description?: string;
  max_weddings?: number;
  max_guests_per_wedding?: number;
  ai_credits_monthly?: number;
  storage_gb?: number;
  staff_seats?: number;
  features?: Record<string, boolean>;
}

interface InvoiceDetails {
  id: string;
  number?: string;
  invoice_pdf?: string;
  hosted_invoice_url?: string;
  status: string;
  amount_paid: number;
}

interface EnrichedSession {
  id: string;
  payment_status: string;
  customer?: string;
  subscription?: string;
  subscription_status?: string;
  billing_interval?: string;
  amount_total: number;
  currency?: string;
  next_billing_date?: number;
  trial_end?: number;
  plan?: PlanDetails;
  invoice?: InvoiceDetails;
}

function formatDate(unixTs: number): string {
  return new Date(unixTs * 1000).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

function formatCurrency(amount: number, currency?: string): string {
  const cur = (currency || 'usd').toUpperCase();
  return `$${amount.toFixed(2)} ${cur}`;
}

export default function BillingSuccessPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { token } = useAdmin();
  const apiBaseUrl = getApiBaseUrl();
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState<EnrichedSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(REDIRECT_DELAY_SECONDS);
  const [redirectPaused, setRedirectPaused] = useState(false);

  // ── Verify checkout session ────────────────────────────────────
  useEffect(() => {
    const sessionId = searchParams.get('session_id');

    if (!sessionId) {
      setError('No session ID provided');
      setLoading(false);
      return;
    }

    const verifySession = async () => {
      try {
        if (!token) {
          throw new Error('Not authenticated');
        }

        const response = await fetch(
          `${apiBaseUrl}/stripe/checkout-session/${sessionId}`,
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
  }, [apiBaseUrl, searchParams, token]);

  // ── Auto-redirect countdown ────────────────────────────────────
  useEffect(() => {
    if (loading || error || redirectPaused) return;

    if (countdown <= 0) {
      router.push('/admin/dashboard');
      return;
    }

    const timer = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [countdown, loading, error, redirectPaused, router]);

  const handlePauseRedirect = useCallback(() => {
    setRedirectPaused(true);
  }, []);

  // ── Loading state ──────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Verifying your payment...</p>
        </div>
      </div>
    );
  }

  // ── Error state ────────────────────────────────────────────────
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
            <p className="text-gray-600 dark:text-gray-400">{error}</p>
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

  const plan = session?.plan;
  const invoice = session?.invoice;
  const isTrial = session?.subscription_status === 'trialing' && session?.trial_end;

  return (
    <div className="container max-w-2xl mx-auto py-16 px-4">
      <Card className="border-green-200 dark:border-green-800">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center">
            <CheckCircle2 className="w-10 h-10 text-green-600 dark:text-green-400" />
          </div>
          <CardTitle className="text-2xl text-green-600 dark:text-green-400">
            {isTrial ? 'Trial Activated!' : 'Payment Successful!'}
          </CardTitle>
          <CardDescription>
            {plan?.name
              ? `Your ${plan.name} subscription is now active`
              : 'Your subscription has been activated'}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* ── Payment / Trial Summary ───────────────────────── */}
          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-6 space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-600 dark:text-gray-400 flex items-center gap-2">
                <CreditCard className="w-4 h-4" />
                Payment Status
              </span>
              <span className="font-semibold capitalize text-green-600 dark:text-green-400">
                {session?.payment_status || 'Paid'}
              </span>
            </div>

            {session?.amount_total != null && session.amount_total > 0 && (
              <div className="flex justify-between items-center">
                <span className="text-gray-600 dark:text-gray-400">Amount Paid</span>
                <span className="font-semibold">
                  {formatCurrency(session.amount_total, session.currency)}
                </span>
              </div>
            )}

            {invoice?.number && (
              <div className="flex justify-between items-center">
                <span className="text-gray-600 dark:text-gray-400">Invoice</span>
                <span className="font-mono text-sm">{invoice.number}</span>
              </div>
            )}

            {session?.billing_interval && (
              <div className="flex justify-between items-center">
                <span className="text-gray-600 dark:text-gray-400">Billing Cycle</span>
                <span className="font-semibold capitalize">{session.billing_interval}</span>
              </div>
            )}

            {isTrial && session.trial_end && (
              <div className="flex justify-between items-center">
                <span className="text-gray-600 dark:text-gray-400 flex items-center gap-2">
                  <Calendar className="w-4 h-4" />
                  Trial Ends
                </span>
                <span className="font-semibold">{formatDate(session.trial_end)}</span>
              </div>
            )}

            {session?.next_billing_date && !isTrial && (
              <div className="flex justify-between items-center">
                <span className="text-gray-600 dark:text-gray-400 flex items-center gap-2">
                  <Calendar className="w-4 h-4" />
                  Next Billing Date
                </span>
                <span className="font-semibold">{formatDate(session.next_billing_date)}</span>
              </div>
            )}
          </div>

          {/* ── Invoice Actions ────────────────────────────────── */}
          {invoice && (invoice.invoice_pdf || invoice.hosted_invoice_url) && (
            <div className="flex flex-wrap gap-3">
              {invoice.invoice_pdf && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => window.open(invoice.invoice_pdf, '_blank')}
                  className="flex items-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  Download Invoice PDF
                </Button>
              )}
              {invoice.hosted_invoice_url && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => window.open(invoice.hosted_invoice_url, '_blank')}
                  className="flex items-center gap-2"
                >
                  <ExternalLink className="w-4 h-4" />
                  View Invoice Online
                </Button>
              )}
            </div>
          )}

          {/* ── Plan Features ─────────────────────────────────── */}
          {plan && (
            <div className="space-y-3">
              <h3 className="font-semibold text-sm text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                Your Plan Includes
              </h3>
              <div className="grid grid-cols-2 gap-3">
                {plan.max_weddings != null && (
                  <div className="flex items-center gap-2 text-sm">
                    <Sparkles className="w-4 h-4 text-blue-500" />
                    <span>{plan.max_weddings === -1 ? 'Unlimited' : plan.max_weddings} wedding{plan.max_weddings !== 1 ? 's' : ''}</span>
                  </div>
                )}
                {plan.max_guests_per_wedding != null && (
                  <div className="flex items-center gap-2 text-sm">
                    <Users className="w-4 h-4 text-blue-500" />
                    <span>Up to {plan.max_guests_per_wedding} guests</span>
                  </div>
                )}
                {plan.ai_credits_monthly != null && (
                  <div className="flex items-center gap-2 text-sm">
                    <Zap className="w-4 h-4 text-blue-500" />
                    <span>{plan.ai_credits_monthly} AI credits/mo</span>
                  </div>
                )}
                {plan.storage_gb != null && (
                  <div className="flex items-center gap-2 text-sm">
                    <Database className="w-4 h-4 text-blue-500" />
                    <span>{plan.storage_gb} GB storage</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── What Happens Next ─────────────────────────────── */}
          <div className="space-y-2">
            <h3 className="font-semibold">What happens next?</h3>
            <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-400">
              <li className="flex items-start">
                <CheckCircle2 className="w-4 h-4 mr-2 mt-0.5 text-green-600 dark:text-green-300 shrink-0" />
                {isTrial
                  ? 'Your trial is active — explore all features risk-free'
                  : 'Your subscription is now active and ready to use'}
              </li>
              <li className="flex items-start">
                <CheckCircle2 className="w-4 h-4 mr-2 mt-0.5 text-green-600 dark:text-green-300 shrink-0" />
                A confirmation email with your invoice has been sent
              </li>
              <li className="flex items-start">
                <CheckCircle2 className="w-4 h-4 mr-2 mt-0.5 text-green-600 dark:text-green-300 shrink-0" />
                Manage your subscription anytime from the billing page
              </li>
            </ul>
          </div>
        </CardContent>

        <CardFooter className="flex flex-col gap-3">
          <div className="flex gap-3 w-full">
            <Button
              onClick={() => router.push('/admin/dashboard')}
              className="flex-1"
            >
              Go to Dashboard
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
            <Button
              onClick={() => router.push('/admin/planner/billing')}
              variant="outline"
              className="flex-1"
            >
              View Billing Details
            </Button>
          </div>

          {/* ── Auto-redirect indicator ──────────────────────── */}
          {!redirectPaused && (
            <p className="text-xs text-gray-400 dark:text-gray-500 text-center">
              Redirecting to dashboard in {countdown}s{' '}
              <button
                onClick={handlePauseRedirect}
                className="underline hover:text-gray-600 dark:hover:text-gray-300"
              >
                Stay on this page
              </button>
            </p>
          )}
        </CardFooter>
      </Card>
    </div>
  );
}
