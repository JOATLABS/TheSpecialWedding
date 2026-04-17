'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { CheckCircle2, Clock3, Loader2, XCircle } from 'lucide-react';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { getApiBaseUrl } from '@/utils/env';

interface PaymentRequestSummary {
  payment_token: string;
  amount: number;
  currency: string;
  status: string;
  description?: string;
}

function PaymentSuccessPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [paymentRequest, setPaymentRequest] = useState<PaymentRequestSummary | null>(null);

  useEffect(() => {
    const paymentToken = searchParams.get('payment_token') || searchParams.get('payment_id');

    if (!paymentToken) {
      setError('No payment confirmation was found for this session.');
      setLoading(false);
      return;
    }

    const verifyPayment = async () => {
      try {
        const response = await fetch(
          `${getApiBaseUrl()}/stripe/payment-request/${encodeURIComponent(paymentToken)}/summary`,
        );
        if (!response.ok) {
          throw new Error('Unable to verify this payment right now.');
        }

        const publicPaymentRequest = await response.json();

        setPaymentRequest(publicPaymentRequest);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to verify this payment right now.');
      } finally {
        setLoading(false);
      }
    };

    void verifyPayment();
  }, [searchParams]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 dark:bg-slate-900">
        <div className="text-center">
          <Loader2 className="mx-auto mb-4 h-10 w-10 animate-spin text-wedding-rose" />
          <p className="text-gray-600 dark:text-gray-300">Verifying your payment…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 dark:bg-slate-900">
        <Card className="w-full max-w-lg">
          <CardHeader className="text-center">
            <XCircle className="mx-auto mb-4 h-12 w-12 text-red-500" />
            <CardTitle>Payment Confirmation Unavailable</CardTitle>
          </CardHeader>
          <CardContent className="text-center text-sm text-gray-600 dark:text-gray-300">
            {error}
          </CardContent>
          <CardFooter className="justify-center">
            <Button variant="outline" onClick={() => router.back()}>
              Go Back
            </Button>
          </CardFooter>
        </Card>
      </div>
    );
  }

  const isProcessing = paymentRequest?.status === 'processing';
  const isSucceeded = paymentRequest?.status === 'succeeded';
  const paymentToken = searchParams.get('payment_token') || searchParams.get('payment_id');
  const heading = isSucceeded
    ? 'Payment Successful'
    : isProcessing
      ? 'Payment Processing'
      : 'Payment Incomplete';
  const summary = isSucceeded
    ? 'Your payment was received successfully.'
    : isProcessing
      ? 'Stripe is still finalizing your payment. You can close this page and we will continue processing it securely.'
      : 'Your payment has not completed yet. Please retry or contact your wedding planner if the issue persists.';

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-10 dark:bg-slate-900">
      <Card className="w-full max-w-lg">
        <CardHeader className="text-center">
          {isProcessing ? (
            <Clock3 className="mx-auto mb-4 h-12 w-12 text-amber-500" />
          ) : (
            <CheckCircle2 className="mx-auto mb-4 h-12 w-12 text-green-500" />
          )}
          <CardTitle>{heading}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-center text-sm text-gray-600 dark:text-gray-300">{summary}</p>
          <div className="rounded-xl bg-gray-50 p-4 text-sm dark:bg-slate-800">
            {paymentRequest?.description && (
              <div className="mb-3 flex items-center justify-between gap-3">
                <span className="text-gray-500 dark:text-gray-400">Description</span>
                <span className="text-right font-medium text-gray-900 dark:text-white">{paymentRequest.description}</span>
              </div>
            )}
            <div className="mb-3 flex items-center justify-between gap-3">
              <span className="text-gray-500 dark:text-gray-400">Amount</span>
              <span className="font-medium text-gray-900 dark:text-white">
                ${paymentRequest?.amount?.toFixed(2)} {paymentRequest?.currency?.toUpperCase()}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-gray-500 dark:text-gray-400">Status</span>
              <span className="font-medium capitalize text-gray-900 dark:text-white">
                {paymentRequest?.status?.replace(/_/g, ' ')}
              </span>
            </div>
          </div>
          {!isSucceeded && !isProcessing && (
            <p className="text-center text-sm text-red-600 dark:text-red-400">
              This payment is not in a completed state yet. If the issue persists, contact your wedding planner.
            </p>
          )}
        </CardContent>
        <CardFooter className="justify-center">
          {paymentToken && !isSucceeded && !isProcessing ? (
            <Button variant="outline" onClick={() => router.replace(`/pay/${paymentToken}`)}>
              Try Payment Again
            </Button>
          ) : (
            <Button variant="outline" onClick={() => router.back()}>
              Done
            </Button>
          )}
        </CardFooter>
      </Card>
    </div>
  );
}

export default function PaymentSuccessPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 dark:bg-slate-900">
          <div className="text-center">
            <Loader2 className="mx-auto mb-4 h-10 w-10 animate-spin text-wedding-rose" />
            <p className="text-gray-600 dark:text-gray-300">Loading payment confirmation…</p>
          </div>
        </div>
      }
    >
      <PaymentSuccessPageContent />
    </Suspense>
  );
}
