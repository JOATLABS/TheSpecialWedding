import { loadStripe, type Stripe } from '@stripe/stripe-js';
import { getApiBaseUrl } from '@/utils/env';

let publishableKeyPromise: Promise<string> | null = null;
let stripePromise: Promise<Stripe | null> | null = null;

async function fetchPublishableKey(): Promise<string> {
  const envKey = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;
  if (envKey) {
    return envKey;
  }

  if (!publishableKeyPromise) {
    publishableKeyPromise = (async () => {
      const response = await fetch(`${getApiBaseUrl()}/stripe/config`);
      if (!response.ok) {
        throw new Error('Stripe configuration is unavailable');
      }

      const data = await response.json();
      if (!data.publishable_key) {
        throw new Error('Stripe publishable key is missing');
      }

      return data.publishable_key as string;
    })().catch((error) => {
      publishableKeyPromise = null;
      throw error;
    });
  }

  return publishableKeyPromise;
}

export function getStripeClient(): Promise<Stripe | null> {
  if (!stripePromise) {
    stripePromise = fetchPublishableKey()
      .then((publishableKey) => loadStripe(publishableKey))
      .catch((error) => {
        stripePromise = null;
        throw error;
      });
  }

  return stripePromise;
}

export async function preloadStripeClient(): Promise<void> {
  await getStripeClient();
}

export interface ResolvedSetupIntent {
  id: string;
  paymentMethodId: string;
  customerId?: string;
}

export async function retrieveSucceededSetupIntent(
  setupIntentClientSecret: string
): Promise<ResolvedSetupIntent> {
  const stripe = await getStripeClient();
  if (!stripe) {
    throw new Error('Unable to load Stripe right now.');
  }

  const { setupIntent, error } = await stripe.retrieveSetupIntent(setupIntentClientSecret);

  if (error || !setupIntent) {
    throw new Error(error?.message || 'Unable to verify this payment setup.');
  }

  if (setupIntent.status !== 'succeeded') {
    throw new Error('Payment setup is not complete yet.');
  }

  if (typeof setupIntent.payment_method !== 'string') {
    throw new Error('Payment setup did not produce a reusable payment method.');
  }

  return {
    id: setupIntent.id,
    paymentMethodId: setupIntent.payment_method,
    customerId: typeof setupIntent.customer === 'string' ? setupIntent.customer : undefined,
  };
}
