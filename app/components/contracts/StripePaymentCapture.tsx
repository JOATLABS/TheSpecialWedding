'use client';

import { useState, useEffect } from 'react';
import { loadStripe, Stripe, StripeElements } from '@stripe/stripe-js';
import {
  Elements,
  PaymentElement,
  useStripe,
  useElements
} from '@stripe/react-stripe-js';
import { CreditCard, Lock, CheckCircle, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '../ui/Button';

// Load Stripe outside component to avoid recreating on each render
let stripePromise: Promise<Stripe | null> | null = null;

const getStripe = () => {
  if (!stripePromise) {
    const key = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;
    if (key) {
      stripePromise = loadStripe(key);
    }
  }
  return stripePromise;
};

interface PaymentCaptureFormProps {
  clientSecret: string;
  onPaymentMethodCaptured: (paymentData: PaymentMethodData) => void;
  onError: (error: string) => void;
  disabled?: boolean;
}

export interface PaymentMethodData {
  customerId: string;
  paymentMethodId: string;
  last4: string;
  brand: string;
}

function PaymentCaptureForm({
  clientSecret,
  onPaymentMethodCaptured,
  onError,
  disabled = false
}: PaymentCaptureFormProps) {
  const stripe = useStripe();
  const elements = useElements();
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const [captured, setCaptured] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!stripe || !elements) {
      return;
    }

    setLoading(true);
    setError('');

    try {
      // Confirm the SetupIntent to save the payment method
      const { error: stripeError, setupIntent } = await stripe.confirmSetup({
        elements,
        confirmParams: {
          return_url: window.location.href, // Not used for embedded flow
        },
        redirect: 'if_required'
      });

      if (stripeError) {
        setError(stripeError.message || 'An error occurred');
        onError(stripeError.message || 'Payment setup failed');
        setLoading(false);
        return;
      }

      if (setupIntent && setupIntent.status === 'succeeded') {
        // Get payment method details
        const paymentMethodId = setupIntent.payment_method;

        if (typeof paymentMethodId === 'string') {
          // Retrieve payment method details from API
          const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
          const response = await fetch(`${baseUrl}/public/payment-method/${paymentMethodId}`);

          if (response.ok) {
            const pmData = await response.json();
            setCaptured(true);
            onPaymentMethodCaptured({
              customerId: setupIntent.customer as string || '',
              paymentMethodId: paymentMethodId,
              last4: pmData.card?.last4 || '****',
              brand: pmData.card?.brand || 'card'
            });
          } else {
            // Fallback if we can't get details
            setCaptured(true);
            onPaymentMethodCaptured({
              customerId: setupIntent.customer as string || '',
              paymentMethodId: paymentMethodId,
              last4: '****',
              brand: 'card'
            });
          }
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Payment setup failed';
      setError(message);
      onError(message);
    } finally {
      setLoading(false);
    }
  };

  if (captured) {
    return (
      <div className="p-6 bg-green-50 dark:bg-green-900/20 rounded-xl border border-green-200 dark:border-green-800">
        <div className="flex items-center gap-3">
          <CheckCircle className="text-green-500" size={24} />
          <div>
            <p className="font-medium text-green-700 dark:text-green-300">
              Payment method saved
            </p>
            <p className="text-sm text-green-600 dark:text-green-400">
              Your card has been securely saved for scheduled payments
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="p-6 bg-slate-50 dark:bg-slate-800 rounded-xl">
        <div className="flex items-center gap-2 mb-4">
          <CreditCard className="text-primary-500" size={20} />
          <h3 className="font-medium text-slate-900 dark:text-white">
            Payment Method
          </h3>
        </div>

        <PaymentElement
          onReady={() => setReady(true)}
          options={{
            layout: 'tabs',
            wallets: {
              applePay: 'auto',
              googlePay: 'auto'
            }
          }}
        />
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
          <AlertCircle className="text-red-500 flex-shrink-0" size={18} />
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      )}

      <Button
        type="submit"
        disabled={!stripe || !ready || loading || disabled}
        className="w-full py-4 flex items-center justify-center gap-2"
      >
        {loading ? (
          <>
            <Loader2 className="animate-spin" size={20} />
            Saving payment method...
          </>
        ) : (
          <>
            <Lock size={18} />
            Save Payment Method
          </>
        )}
      </Button>

      <div className="flex items-center justify-center gap-2 text-xs text-slate-500 dark:text-slate-400">
        <Lock size={14} />
        <span>Secured by Stripe. Your card details are encrypted.</span>
      </div>
    </form>
  );
}

interface StripePaymentCaptureProps {
  clientSecret: string;
  onPaymentMethodCaptured: (paymentData: PaymentMethodData) => void;
  onError: (error: string) => void;
  disabled?: boolean;
}

export default function StripePaymentCapture({
  clientSecret,
  onPaymentMethodCaptured,
  onError,
  disabled = false
}: StripePaymentCaptureProps) {
  const [stripeLoaded, setStripeLoaded] = useState(false);

  useEffect(() => {
    getStripe()?.then(() => setStripeLoaded(true));
  }, []);

  if (!clientSecret) {
    return (
      <div className="p-6 bg-amber-50 dark:bg-amber-900/20 rounded-xl border border-amber-200 dark:border-amber-800">
        <div className="flex items-center gap-3">
          <AlertCircle className="text-amber-500" size={24} />
          <div>
            <p className="font-medium text-amber-700 dark:text-amber-300">
              Payment setup unavailable
            </p>
            <p className="text-sm text-amber-600 dark:text-amber-400">
              Unable to initialize payment. Please contact the wedding planner.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (!stripeLoaded) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="animate-spin text-primary-500" size={32} />
      </div>
    );
  }

  return (
    <Elements
      stripe={getStripe()}
      options={{
        clientSecret,
        appearance: {
          theme: 'stripe',
          variables: {
            colorPrimary: '#6366f1',
            colorBackground: '#ffffff',
            colorText: '#1e293b',
            colorDanger: '#ef4444',
            fontFamily: 'system-ui, sans-serif',
            spacingUnit: '4px',
            borderRadius: '8px'
          }
        }
      }}
    >
      <PaymentCaptureForm
        clientSecret={clientSecret}
        onPaymentMethodCaptured={onPaymentMethodCaptured}
        onError={onError}
        disabled={disabled}
      />
    </Elements>
  );
}
