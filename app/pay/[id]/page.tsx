'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import type { Stripe } from '@stripe/stripe-js';
import { Elements, PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { Loader2 } from 'lucide-react';
import { getApiBaseUrl } from '@/utils/env';
import { getStripeClient, preloadStripeClient } from '@/utils/stripeClient';

// Checkout Form Component
function CheckoutForm({
  amount,
  currency,
  clientSecret,
  paymentToken,
}: {
  amount: number;
  currency: string;
  clientSecret: string;
  paymentToken: string;
}) {
  const router = useRouter();
  const stripe = useStripe();
  const elements = useElements();
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!stripe || !elements) return;

    setLoading(true);
    setErrorMessage(null);

    const { error, paymentIntent } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: `${window.location.origin}/pay/success?payment_token=${encodeURIComponent(paymentToken)}`,
      },
      redirect: 'if_required',
    });

    if (error) {
      setErrorMessage(error.message || 'Payment failed');
      setLoading(false);
      return;
    }

    if (paymentIntent) {
      router.push(`/pay/success?payment_token=${encodeURIComponent(paymentToken)}`);
      return;
    }

    setLoading(false);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="bg-gray-50 dark:bg-slate-700 p-4 rounded-lg mb-6">
        <div className="flex justify-between items-center mb-2">
          <span className="text-gray-600 dark:text-gray-300">Total Amount</span>
          <span className="text-xl font-bold text-gray-900 dark:text-white">
            ${amount.toFixed(2)} <span className="text-sm font-normal text-gray-500 uppercase">{currency}</span>
          </span>
        </div>
      </div>

      <PaymentElement />

      {errorMessage && (
        <div className="p-3 bg-red-50 text-red-600 rounded-md text-sm">
          {errorMessage}
        </div>
      )}

      <button
        type="submit"
        disabled={!stripe || loading}
        className="w-full py-3 px-4 bg-wedding-rose hover:bg-wedding-rose/90 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {loading ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            Processing...
          </>
        ) : (
          `Pay $${amount.toFixed(2)}`
        )}
      </button>
    </form>
  );
}

// Main Page Component
export default function PaymentPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [paymentToken, setPaymentToken] = useState<string | null>(null);

  useEffect(() => {
    params.then((p) => setPaymentToken(p.id));
  }, [params]);
  const [amount, setAmount] = useState<number>(0);
  const [currency, setCurrency] = useState<string>('usd');
  const [paymentStatus, setPaymentStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stripePromiseState, setStripePromiseState] = useState<Promise<Stripe | null> | null>(null);

  useEffect(() => {
    const fetchPaymentDetails = async () => {
      if (!paymentToken) return;
      try {
        const stripe = getStripeClient();
        setStripePromiseState(stripe);
        preloadStripeClient().catch(() => undefined);

        const res = await fetch(`${getApiBaseUrl()}/stripe/payment-request/${paymentToken}`);

        if (!res.ok) {
           throw new Error("Payment link invalid or expired");
        }

        const data = await res.json();
        setPaymentStatus(data.status);
        setClientSecret(data.client_secret);
        setAmount(data.amount);
        setCurrency(data.currency);

        if (data.status === 'succeeded' || data.status === 'processing') {
          router.replace(`/pay/success?payment_token=${encodeURIComponent(paymentToken)}`);
          return;
        }

        if (!data.client_secret) {
          throw new Error('This payment request is no longer payable. Please contact your wedding planner.');
        }
      } catch (err: any) {
        console.error(err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchPaymentDetails();
  }, [paymentToken, router]);


  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-slate-900">
        <Loader2 className="w-12 h-12 text-wedding-rose animate-spin" />
      </div>
    );
  }

  if (paymentStatus === 'succeeded' || paymentStatus === 'processing') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-slate-900 p-4">
        <div className="max-w-md w-full bg-white dark:bg-slate-800 p-8 rounded-2xl shadow-xl text-center">
          <Loader2 className="w-12 h-12 text-wedding-rose animate-spin mx-auto mb-4" />
          <h1 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Redirecting to payment status…</h1>
          <p className="text-gray-600 dark:text-gray-300">
            This payment is already being processed. We&apos;re loading the latest status now.
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-slate-900 p-4">
        <div className="max-w-md w-full bg-white dark:bg-slate-800 p-8 rounded-2xl shadow-xl text-center">
          <div className="w-16 h-16 bg-red-100 text-red-500 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Payment Error</h1>
          <p className="text-gray-600 dark:text-gray-300">{error}</p>
        </div>
      </div>
    );
  }

  if (!paymentToken || !clientSecret || !stripePromiseState) return null;

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 dark:bg-slate-900 p-4 py-12">
      <div className="w-full max-w-md">
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl overflow-hidden">
          <div className="bg-gradient-to-r from-wedding-rose to-wedding-gold p-6 text-center text-white">
            <h1 className="text-2xl font-bold">Complete Your Payment</h1>
            <p className="opacity-90 mt-1">Secure payment processing</p>
          </div>

          <div className="p-6">
            <Elements stripe={stripePromiseState} options={{ clientSecret, appearance: { theme: 'stripe' } }}>
              <CheckoutForm amount={amount} currency={currency} clientSecret={clientSecret} paymentToken={paymentToken} />
            </Elements>
          </div>
        </div>

        <div className="text-center mt-6 text-sm text-gray-500">
          <p>Payments powered by Stripe. Secure and encrypted.</p>
        </div>
      </div>
    </div>
  );
}
