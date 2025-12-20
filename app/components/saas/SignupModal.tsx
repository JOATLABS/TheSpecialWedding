'use client';

import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { ThemeConfig } from '@/types/wedding';

interface SubscriptionPlan {
  _id: string;
  name: string;
  description: string;
  price_monthly: number;
  price_yearly: number;
  max_weddings: number;
  max_guests_per_wedding: number;
  features_list?: string[];
  features: string[];
  is_featured: boolean;
}

// Fallback plans if API fails (matching database structure)
const FALLBACK_PLANS: SubscriptionPlan[] = [
  {
    _id: 'plan_boutique',
    name: 'Boutique',
    description: 'For new planners onboarding their first weddings',
    price_monthly: 29,
    price_yearly: 348,
    max_weddings: 3,
    max_guests_per_wedding: 150,
    features: ['Guest & RSVP manager', 'Email invitations', 'Wedding website', 'Timeline builder'],
    is_featured: false
  },
  {
    _id: 'plan_signature',
    name: 'Signature',
    description: 'Most popular plan with automation',
    price_monthly: 59,
    price_yearly: 708,
    max_weddings: 10,
    max_guests_per_wedding: 350,
    features: ['Seating orchestration', 'QR check-in & live counts', 'Automated reminders', 'Vendor collaboration'],
    is_featured: true
  }
];

interface SignupModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedPlanId?: string;
  theme: ThemeConfig;
}

type FormValues = {
  firstName: string;
  lastName: string;
  companyName: string;
  email: string;
  phone: string;
  password: string;
  confirmPassword: string;
  acceptTerms: boolean;
};

export const SignupModal: React.FC<SignupModalProps> = ({ isOpen, onClose, selectedPlanId, theme }) => {
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<SubscriptionPlan | null>(null);
  const [billingInterval, setBillingInterval] = useState<'monthly' | 'yearly'>('monthly');
  const [loading, setLoading] = useState(true);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
    watch,
    reset
  } = useForm<FormValues>();

  // Fetch plans from API
  useEffect(() => {
    const fetchPlans = async () => {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/public/subscription-plans`);
        if (response.ok) {
          const data = await response.json();
          const activePlans = data.filter((p: SubscriptionPlan) => p).sort((a: SubscriptionPlan, b: SubscriptionPlan) =>
            (a.price_monthly || 0) - (b.price_monthly || 0)
          );
          setPlans(activePlans.length > 0 ? activePlans : FALLBACK_PLANS);

          // Set initially selected plan
          const plansToUse = activePlans.length > 0 ? activePlans : FALLBACK_PLANS;
          const initialPlan = selectedPlanId
            ? plansToUse.find((p: SubscriptionPlan) => p._id === selectedPlanId || p.name.toLowerCase() === selectedPlanId.toLowerCase())
            : plansToUse.find((p: SubscriptionPlan) => p.is_featured) || plansToUse[1] || plansToUse[0];
          setSelectedPlan(initialPlan);
        } else {
          // API call failed, use fallback
          setPlans(FALLBACK_PLANS);
          const initialPlan = selectedPlanId
            ? FALLBACK_PLANS.find((p: SubscriptionPlan) => p._id === selectedPlanId || p.name.toLowerCase() === selectedPlanId.toLowerCase())
            : FALLBACK_PLANS.find((p: SubscriptionPlan) => p.is_featured) || FALLBACK_PLANS[1] || FALLBACK_PLANS[0];
          setSelectedPlan(initialPlan || null);
        }
      } catch (error) {
        console.error('Failed to fetch plans:', error);
        // Use fallback on error
        setPlans(FALLBACK_PLANS);
        const initialPlan = selectedPlanId
          ? FALLBACK_PLANS.find((p: SubscriptionPlan) => p._id === selectedPlanId || p.name.toLowerCase() === selectedPlanId.toLowerCase())
          : FALLBACK_PLANS.find((p: SubscriptionPlan) => p.is_featured) || FALLBACK_PLANS[1] || FALLBACK_PLANS[0];
        setSelectedPlan(initialPlan || null);
      } finally {
        setLoading(false);
      }
    };

    if (isOpen) {
      fetchPlans();
      reset();
    }
  }, [isOpen, selectedPlanId, reset]);

  if (!isOpen) return null;

  const displayPrice = selectedPlan
    ? (billingInterval === 'yearly' ? selectedPlan.price_yearly : selectedPlan.price_monthly)
    : 0;

  const onSubmit = handleSubmit(async (data) => {
    if (data.password !== data.confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    try {
      // Step 1: Register user
      const registerResponse = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/public/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: data.email,
          password: data.password,
          first_name: data.firstName,
          last_name: data.lastName,
          company_name: data.companyName,
          phone: data.phone,
          selected_plan_id: selectedPlan?._id,
          role: 'wedding_planner'
        })
      });

      if (!registerResponse.ok) {
        let message = 'Registration failed';
        try {
          const error = await registerResponse.json();
          if (error?.detail) {
            if (Array.isArray(error.detail)) {
              message = error.detail.map((d: any) => d.msg || d.detail || d.loc?.join('.') || 'Validation error').join('; ');
            } else if (typeof error.detail === 'string') {
              message = error.detail;
            }
          }
        } catch {
          // ignore parse issues
        }
        toast.error(message);
        return;
      }

      const registerData = await registerResponse.json();
      const userId = registerData?.user_id;

      toast.success('Account created! Redirecting to secure checkout...');

      // Step 2: Create Stripe Checkout (no login until webhook activation)
      const checkoutResponse = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/stripe/public/create-checkout-session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          user_id: userId,
          email: data.email,
          plan_id: selectedPlan?._id,
          billing_interval: billingInterval,
          success_url: `${window.location.origin}/admin/login?payment=success`,
          cancel_url: `${window.location.origin}/?payment=cancelled`,
          trial_days: 0
        })
      });

      if (!checkoutResponse.ok) {
        let message = 'Account created! Please continue from the payment link we emailed you.';
        try {
          const error = await checkoutResponse.json();
          if (error?.detail) {
            message = typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail);
          }
        } catch {
          // ignore
        }
        toast.warning(message);
        return;
      }

      const { checkout_session } = await checkoutResponse.json();
      if (checkout_session?.url) {
        window.location.href = checkout_session.url;
      } else {
        toast.error('Could not start payment checkout. Please try again from your email link.');
      }

    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Signup failed');
    }
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-md"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-6xl rounded-3xl border border-white/20 bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute right-6 top-6 z-10 rounded-full bg-slate-100 p-2 text-slate-600 transition-all hover:bg-slate-200"
          aria-label="Close"
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <div className="grid lg:grid-cols-[380px_1fr]">
          {/* Left: Plan Selection */}
          <div className="border-r border-slate-200 bg-slate-50 p-8">
            <div className="space-y-6">
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Selected Plan</h3>
                <h2 className="mt-2 text-2xl font-bold text-slate-900">{selectedPlan?.name || 'Loading...'}</h2>
              </div>

              {/* Billing Toggle */}
              <div className="inline-flex rounded-full bg-white p-1 shadow-sm">
                <button
                  type="button"
                  onClick={() => setBillingInterval('monthly')}
                  className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                    billingInterval === 'monthly' ? 'bg-slate-900 text-white' : 'text-slate-600'
                  }`}
                >
                  Monthly
                </button>
                <button
                  type="button"
                  onClick={() => setBillingInterval('yearly')}
                  className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                    billingInterval === 'yearly' ? 'bg-slate-900 text-white' : 'text-slate-600'
                  }`}
                >
                  Yearly <span className="text-xs text-emerald-600">-15%</span>
                </button>
              </div>

              {/* Price */}
              <div className="rounded-xl bg-white p-5 shadow-sm">
                <div className="text-3xl font-bold text-slate-900">${displayPrice}</div>
                <div className="text-sm text-slate-600">{billingInterval === 'yearly' ? 'per year' : 'per month'}</div>
              </div>

              {/* Features */}
              {selectedPlan?.features_list && (
                <div className="space-y-2">
                  {selectedPlan.features_list.slice(0, 4).map((feature, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-sm">
                      <svg className="mt-0.5 h-5 w-5 text-emerald-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                      <span className="text-slate-700">{feature}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Change Plan */}
              <select
                value={selectedPlan?._id || ''}
                onChange={(e) => setSelectedPlan(plans.find(p => p._id === e.target.value) || null)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900"
              >
                {plans.map(plan => (
                  <option key={plan._id} value={plan._id}>{plan.name} - ${plan.price_monthly}/mo</option>
                ))}
              </select>

              <div className="rounded-xl bg-blue-50 p-4">
                <p className="text-sm font-semibold text-blue-900">Secure Payment</p>
                <p className="text-xs text-blue-700">Powered by Stripe</p>
              </div>
            </div>
          </div>

          {/* Right: Form */}
          <div className="max-h-[85vh] overflow-y-auto p-8 lg:p-10">
            <form onSubmit={onSubmit} className="space-y-5">
              <div>
                <h2 className="text-2xl font-bold text-slate-900">Create your account</h2>
                <p className="mt-1 text-slate-600">Complete your subscription signup</p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-slate-700">First name</label>
                  <input
                    {...register('firstName', { required: 'Required' })}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-1 focus:ring-slate-900"
                  />
                  {errors.firstName && <p className="mt-1 text-xs text-red-600">{errors.firstName.message}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700">Last name</label>
                  <input
                    {...register('lastName', { required: 'Required' })}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-1 focus:ring-slate-900"
                  />
                  {errors.lastName && <p className="mt-1 text-xs text-red-600">{errors.lastName.message}</p>}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700">Company name</label>
                <input
                  {...register('companyName', { required: 'Required' })}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-1 focus:ring-slate-900"
                />
                {errors.companyName && <p className="mt-1 text-xs text-red-600">{errors.companyName.message}</p>}
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-slate-700">Email</label>
                  <input
                    type="email"
                    {...register('email', { required: 'Required' })}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-1 focus:ring-slate-900"
                  />
                  {errors.email && <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700">Phone</label>
                  <input
                    type="tel"
                    {...register('phone', { required: 'Required' })}
                    placeholder="405-708-1076"
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-1 focus:ring-slate-900"
                  />
                  {errors.phone && <p className="mt-1 text-xs text-red-600">{errors.phone.message}</p>}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-slate-700">Password</label>
                  <input
                    type="password"
                    {...register('password', {
                      required: 'Required',
                      minLength: { value: 8, message: 'Minimum 8 characters' },
                      pattern: {
                        value: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-[\]{}|;:,.<>?]).{8,}$/,
                        message: 'Must include upper, lower, number, and special character'
                      }
                    })}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-1 focus:ring-slate-900"
                  />
                  {errors.password && <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700">Confirm password</label>
                  <input
                    type="password"
                    {...register('confirmPassword', {
                      required: 'Required',
                      validate: (value) => value === watch('password') || 'Passwords must match'
                    })}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-1 focus:ring-slate-900"
                  />
                  {errors.confirmPassword && <p className="mt-1 text-xs text-red-600">{errors.confirmPassword.message}</p>}
                </div>
              </div>

              <label className="flex items-start gap-2 text-sm">
                <input type="checkbox" {...register('acceptTerms', { required: 'Please accept the terms to continue' })} className="mt-1" />
                <span className="text-slate-600">I agree to the Terms and Privacy Policy</span>
              </label>
              {errors.acceptTerms && <p className="text-xs text-red-600">{errors.acceptTerms.message as string}</p>}

              <button
                type="submit"
                disabled={isSubmitting || loading}
                className="w-full rounded-xl bg-slate-900 px-6 py-3 font-semibold text-white transition hover:bg-slate-800 disabled:opacity-50"
              >
                {isSubmitting ? 'Creating account...' : 'Continue to payment →'}
              </button>

              <p className="text-center text-xs text-slate-500">
                You'll be redirected to Stripe's secure checkout
              </p>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignupModal;
