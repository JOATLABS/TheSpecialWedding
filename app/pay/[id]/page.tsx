'use client';

import React, { useState, useEffect } from 'react';
import { loadStripe, type Stripe } from '@stripe/stripe-js';
import { Elements, PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';

// Helper to get Stripe promise (only initialize once)
let stripePromise: Promise<Stripe | null> | null = null;
const getStripePromise = (): Promise<Stripe | null> | null => {
  if (!stripePromise) {
    const init = async (): Promise<Stripe | null> => {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/stripe/config`);
      if (res.ok) {
        const { publishable_key } = await res.json();
        return loadStripe(publishable_key);
      }
      return null;
    };
    stripePromise = init();
  }
  return stripePromise;
};

// Checkout Form Component
function CheckoutForm({ clientSecret, amount, currency }: { clientSecret: string; amount: number; currency: string }) {
  const stripe = useStripe();
  const elements = useElements();
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!stripe || !elements) return;

    setLoading(true);
    setErrorMessage(null);

    const { error } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: `${window.location.origin}/pay/success`,
      },
    });

    if (error) {
      setErrorMessage(error.message || 'Payment failed');
      setLoading(false);
    }
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
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [id, setId] = useState<string | null>(null);

  useEffect(() => {
    params.then(p => setId(p.id));
  }, [params]);
  const [amount, setAmount] = useState<number>(0);
  const [currency, setCurrency] = useState<string>('usd');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stripePromiseState, setStripePromiseState] = useState<Promise<Stripe | null> | null>(null);

  useEffect(() => {
    // 1. Initialize Stripe - store the promise directly (not awaited)
    const promise = getStripePromise();
    if (promise) {
      setStripePromiseState(promise);
    }

    // 2. Fetch Payment Intent Details (via public endpoint or just assume ID is valid and retrieve via Stripe SDK if possible,
    //    but usually we need client_secret from backend. The ID in URL is payment_intent_id, but we need client_secret to render Elements)
    //
    //    Wait, the modal generated a link with payment_intent_id. We need an endpoint to retrieve the client_secret
    //    given the ID (if we don't store it in the URL).
    //    Stripe Payment Intents are secure; we can retrieve it if we have a backend endpoint.

    //    Let's check if we have an endpoint to get PI details by ID.
    //    Currently, the backend creates it and returns client_secret. The frontend modal generates the link.
    //    We need a way to re-fetch the client_secret or pass it in the URL. passing secret in URL is okay but long.
    //    Better to have an endpoint: GET /api/payments/{id} -> returns client_secret

    //    I will assume for now I need to create such endpoint or use an existing one.
    //    I see `get_checkout_session` but not `get_payment_intent`.

    //    I will create a temporary fetch logic assuming I need to add an endpoint.

    const fetchPaymentDetails = async () => {
      if (!id) return;
      try {
        // We need a public endpoint to retrieve payment intent details (amount, currency, client_secret)
        // without authentication, because the couple pays without logging in.
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/stripe/payment-intent/${id}`);

        if (!res.ok) {
           // Fallback: Check if we can use a server action or different endpoint
           throw new Error("Payment link invalid or expired");
        }

        const data = await res.json();
        setClientSecret(data.client_secret);
        setAmount(data.amount);
        setCurrency(data.currency);
      } catch (err: any) {
        console.error(err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchPaymentDetails();
  }, [id]);


  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-slate-900">
        <Loader2 className="w-12 h-12 text-wedding-rose animate-spin" />
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

  if (!clientSecret || !stripePromiseState) return null;

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
              <CheckoutForm clientSecret={clientSecret} amount={amount} currency={currency} />
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
