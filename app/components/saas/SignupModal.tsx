'use client';

import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { ThemeConfig } from '@/types/wedding';
import { getApiBaseUrl } from '@/utils/env';
import { umamiTrack } from '@/utils/umami';

interface SubscriptionPlan {
  _id: string;
  name: string;
  description: string;
  price_monthly: number;
  price_yearly: number;
  billing_model?: string;
  is_metered?: boolean;
  max_weddings: number;
  max_guests_per_wedding: number;
  trial_days?: number;
  features_list?: string[];
  features: Record<string, boolean> | string[];
  is_featured: boolean;
  is_active?: boolean;
  display_order?: number;
}

// IMPORTANT: keep in sync with scripts/seed_subscription_plans.py and the
// fallback in app/page.tsx. This list is only used until the /public/
// subscription-plans fetch resolves; once that lands, the modal renders
// from the live Mongo data.
const FALLBACK_PLANS: SubscriptionPlan[] = [
  {
    _id: 'plan_solo',
    name: 'Solo',
    description: 'Try us with your first client. One wedding, on us.',
    price_monthly: 0,
    price_yearly: 0,
    billing_model: 'flat_rate',
    is_metered: false,
    trial_days: 0,
    max_weddings: 1,
    max_guests_per_wedding: 50,
    features_list: [
      '1 wedding to try us out',
      'Up to 50 guests',
      'Guest list & RSVP system',
      'Branded wedding website',
      'Basic timeline builder',
      '1GB storage',
    ],
    features: {},
    is_featured: false,
    display_order: 0,
  },
  {
    _id: 'plan_boutique',
    name: 'Boutique',
    description: 'For independent planners running their solo practice. Unlimited weddings, no caps.',
    price_monthly: 49,
    price_yearly: 490,
    billing_model: 'flat_rate',
    is_metered: false,
    trial_days: 30,
    max_weddings: -1,
    max_guests_per_wedding: -1,
    features_list: [
      'Unlimited weddings',
      'Unlimited guests',
      'AI-powered timeline & vendor matching',
      'Vendor management',
      'Seating orchestration',
      'QR check-in & live counts',
      'Automated reminders',
      '300 AI credits/month',
      '25GB storage',
    ],
    features: {},
    is_featured: false,
    display_order: 1,
  },
  {
    _id: 'plan_signature',
    name: 'Signature',
    description: 'For agencies running a team of planners. Everything in Boutique, plus team seats and agency-grade reporting.',
    price_monthly: 149,
    price_yearly: 1490,
    billing_model: 'flat_rate',
    is_metered: false,
    trial_days: 30,
    max_weddings: -1,
    max_guests_per_wedding: -1,
    features_list: [
      'Unlimited weddings',
      'Unlimited guests',
      'Everything in Boutique',
      'Team collaboration (5 staff seats)',
      'Vendor-collaboration workspaces',
      'Cross-wedding analytics',
      'Custom domain',
      '1,500 AI credits/month',
      '100GB storage',
      'Priority support',
    ],
    features: {},
    is_featured: true,
    display_order: 2,
  },
  {
    _id: 'plan_enterprise',
    name: 'Enterprise',
    description: 'For franchises and white-label partners. Your brand, our platform, dedicated success.',
    price_monthly: 399,
    price_yearly: 3990,
    billing_model: 'flat_rate',
    is_metered: false,
    trial_days: 30,
    max_weddings: -1,
    max_guests_per_wedding: -1,
    features_list: [
      'Unlimited weddings',
      'Unlimited guests',
      'Everything in Signature',
      'White-label branding',
      'API access + webhooks',
      '20 staff seats',
      '5,000 AI credits/month',
      '500GB storage',
      'Dedicated success manager',
    ],
    features: {},
    is_featured: false,
    display_order: 3,
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

function getBillingUnitLabel(plan: SubscriptionPlan | null | undefined, interval: 'monthly' | 'yearly') {
  const isMetered = plan?.is_metered || plan?.billing_model === 'metered';
  if (isMetered) {
    return interval === 'yearly' ? 'active wedding / year' : 'active wedding / month';
  }
  return interval === 'yearly' ? 'year' : 'month';
}

function getCompactBillingUnit(plan: SubscriptionPlan | null | undefined) {
  return plan?.is_metered || plan?.billing_model === 'metered' ? 'active wedding/mo' : 'mo';
}

export const SignupModal: React.FC<SignupModalProps> = ({ isOpen, onClose, selectedPlanId }) => {
  const apiBaseUrl = getApiBaseUrl();
  const [plans, setPlans] = useState<SubscriptionPlan[]>(FALLBACK_PLANS);
  // Default to the featured plan (Signature) so the modal opens on the
  // recommended option when no specific plan was clicked. Falls back to
  // the first plan if no featured one is found.
  const [selectedPlan, setSelectedPlan] = useState<SubscriptionPlan | null>(
    FALLBACK_PLANS.find((p) => p.is_featured) ?? FALLBACK_PLANS[0]
  );
  const [billingInterval, setBillingInterval] = useState<'monthly' | 'yearly'>('monthly');
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(true);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    watch,
    reset,
    trigger,
    setValue,
  } = useForm<FormValues>();

  // Chrome autofill workaround: when transitioning to step 2, Chrome may
  // inject the password into Company / Phone DOM inputs (without triggering
  // React onChange).  We clear them at the DOM level and sync react-hook-form.
  useEffect(() => {
    if (step === 2) {
      const timer = setTimeout(() => {
        const form = document.querySelector('form[autocomplete="off"]');
        if (!form) return;
        const companyInput = form.querySelector<HTMLInputElement>('input[name="companyName"]');
        const phoneInput = form.querySelector<HTMLInputElement>('input[name="phone"]');
        if (companyInput && companyInput.value && !companyInput.value.includes(' ')) {
          // Heuristic: passwords don't contain spaces; company names usually do
          // but more importantly, if the value matches the password, clear it
          companyInput.value = '';
          setValue('companyName', '');
        }
        if (phoneInput && phoneInput.value && !/^[\d\s()+\-.,]*$/.test(phoneInput.value)) {
          // If phone value contains non-phone chars, it's autofill junk
          phoneInput.value = '';
          setValue('phone', '');
        }
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [step, setValue]);

  // Lock body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  // Umami: top-of-funnel signal — modal opened (separate from pricing CTA
  // click since the modal can be opened from other surfaces too).
  useEffect(() => {
    if (isOpen) {
      umamiTrack('signup_modal_opened', {
        selected_plan_id: selectedPlanId,
      });
    }
  }, [isOpen, selectedPlanId]);

  useEffect(() => {
    const fetchPlans = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/public/subscription-plans`);
        if (response.ok) {
          const data = await response.json();
          const activePlans = data
            .filter((p: SubscriptionPlan) => p && p.is_active !== false)
            .sort((a: SubscriptionPlan, b: SubscriptionPlan) =>
              (a.display_order ?? a.price_monthly ?? 0) - (b.display_order ?? b.price_monthly ?? 0)
            );
          if (activePlans.length > 0) {
            setPlans(activePlans);
            const initialPlan = selectedPlanId
              ? activePlans.find((p: SubscriptionPlan) => p._id === selectedPlanId || p.name.toLowerCase() === selectedPlanId.toLowerCase())
              : activePlans.find((p: SubscriptionPlan) => p.is_featured) || activePlans[1] || activePlans[0];
            setSelectedPlan(initialPlan);
          }
        }
      } catch (error) {
        console.error('Failed to fetch plans:', error);
      } finally {
        setLoading(false);
      }
    };

    if (isOpen) {
      fetchPlans();
      reset();
      setStep(1);
    }
  }, [apiBaseUrl, isOpen, selectedPlanId, reset]);

  if (!isOpen) return null;

  const displayPrice = selectedPlan
    ? (billingInterval === 'yearly' ? selectedPlan.price_yearly : selectedPlan.price_monthly)
    : 0;

  const handleNext = async () => {
    const fieldsToValidate: (keyof FormValues)[] = step === 1
      ? ['email', 'password', 'confirmPassword']
      : ['firstName', 'lastName', 'companyName', 'phone', 'acceptTerms'];

    const isValid = await trigger(fieldsToValidate);
    if (isValid) {
      if (step === 1) {
        // Umami: intent signal — visitor cleared the email/password gate.
        umamiTrack('signup_step_advanced', {
          from_step: 1,
          plan_id: selectedPlan?._id,
        });
        setStep(2);
      }
    }
  };

  const onSubmit = handleSubmit(async (data) => {
    if (data.password !== data.confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    try {
      const registerResponse = await fetch(`${apiBaseUrl}/public/register`, {
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
        const error = await registerResponse.json().catch(() => ({}));
        const message = typeof error?.detail === 'string' ? error.detail : 'Registration failed';
        toast.error(message);
        return;
      }

      const registerData = await registerResponse.json();
      toast.success('Account created! Redirecting to checkout...');

      // Umami: primary conversion — account successfully created. Do not
      // include PII (email, name); the plan id and billing interval are the
      // signal we actually want in the funnel report.
      umamiTrack('signup_registered', {
        plan_id: selectedPlan?._id,
        plan_name: selectedPlan?.name,
        billing_interval: billingInterval,
      });

      const checkoutResponse = await fetch(`${apiBaseUrl}/stripe/public/create-checkout-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: registerData?.user_id,
          email: data.email,
          plan_id: selectedPlan?._id,
          billing_interval: billingInterval,
          success_url: `${window.location.origin}/admin/login?payment=success`,
          cancel_url: `${window.location.origin}/?payment=cancelled`,
        })
      });

      if (checkoutResponse.ok) {
        const { checkout_session } = await checkoutResponse.json();
        if (checkout_session?.url) {
          // Umami: secondary conversion — visitor is being handed to Stripe.
          // Fires before the redirect so it lands in Umami even if the
          // browser tears down the page mid-flight.
          umamiTrack('signup_checkout_redirect', {
            plan_id: selectedPlan?._id,
            billing_interval: billingInterval,
          });
          window.location.href = checkout_session.url;
          return;
        }
      }
      toast.warning('Account created! Check your email for payment link.');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Signup failed');
    }
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/80 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-[360px] sm:max-w-md lg:max-w-4xl bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl shadow-2xl border border-slate-700/50 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute right-3 top-3 z-10 rounded-full bg-slate-700/50 p-2 text-slate-400 hover:text-white hover:bg-slate-600/50 transition-all"
          aria-label="Close"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <div className="lg:grid lg:grid-cols-[280px_1fr]">
          {/* Left sidebar - desktop only */}
          <div className="hidden lg:flex flex-col justify-between bg-gradient-to-b from-indigo-600 to-purple-700 p-6 text-white">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-indigo-200 mb-1">Selected Plan</div>
              <div className="text-2xl font-bold mb-4">{selectedPlan?.name}</div>

              <div className="flex gap-1 mb-4">
                {['monthly', 'yearly'].map((interval) => (
                  <button
                    key={interval}
                    type="button"
                    onClick={() => setBillingInterval(interval as 'monthly' | 'yearly')}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium transition ${
                      billingInterval === interval
                        ? 'bg-white text-indigo-600'
                        : 'bg-white/20 text-white hover:bg-white/30'
                    }`}
                  >
                    {interval === 'monthly' ? 'Monthly' : 'Yearly'}
                    {interval === 'yearly' && <span className="ml-1 text-emerald-300">save 2 mo</span>}
                  </button>
                ))}
              </div>

              <div className="bg-white/10 rounded-xl p-4 mb-4">
                <div className="text-3xl font-bold">${displayPrice}</div>
                <div className="text-sm text-indigo-200">per {getBillingUnitLabel(selectedPlan, billingInterval)}</div>
                {selectedPlan?.trial_days ? (
                  <div className="mt-1 text-xs font-medium text-emerald-200">
                    {selectedPlan.trial_days}-day free trial · no card required
                  </div>
                ) : null}
              </div>

              <div className="space-y-2">
                {(Array.isArray(selectedPlan?.features_list) ? selectedPlan.features_list : []).slice(0, 4).map((feature, idx) => (
                  <div key={idx} className="flex items-center gap-2 text-sm text-indigo-100">
                    <svg className="h-4 w-4 text-emerald-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    <span>{feature}</span>
                  </div>
                ))}
              </div>
            </div>

            <select
              value={selectedPlan?._id || ''}
              onChange={(e) => setSelectedPlan(plans.find(p => p._id === e.target.value) || null)}
              className="w-full mt-4 px-3 py-2 rounded-lg bg-white/10 border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-white/30"
            >
              {plans.map(plan => (
                <option key={plan._id} value={plan._id} className="text-slate-900">{plan.name} - ${plan.price_monthly}/{getCompactBillingUnit(plan)}</option>
              ))}
            </select>
          </div>

          {/* Form area */}
          <div className="p-5 sm:p-6">
            {/* Mobile: Plan selector bar */}
            <div className="lg:hidden flex items-center justify-between gap-3 mb-5 p-3 rounded-xl bg-slate-700/50 border border-slate-600/50">
              <select
                value={selectedPlan?._id || ''}
                onChange={(e) => setSelectedPlan(plans.find(p => p._id === e.target.value) || null)}
                className="flex-1 px-3 py-2 rounded-lg bg-slate-600 border-0 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {plans.map(plan => (
                  <option key={plan._id} value={plan._id}>{plan.name}</option>
                ))}
              </select>
              <div className="flex rounded-lg overflow-hidden border border-slate-600">
                {['monthly', 'yearly'].map((interval) => (
                  <button
                    key={interval}
                    type="button"
                    onClick={() => setBillingInterval(interval as 'monthly' | 'yearly')}
                    className={`px-3 py-2 text-xs font-medium transition ${
                      billingInterval === interval
                        ? 'bg-indigo-600 text-white'
                        : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                    }`}
                  >
                    {interval === 'monthly' ? 'Mo' : 'Yr'}
                  </button>
                ))}
              </div>
              <div className="text-right">
                <div className="text-lg font-bold text-white">${displayPrice}</div>
                <div className="text-[10px] text-slate-400">
                  /{selectedPlan?.is_metered || selectedPlan?.billing_model === 'metered'
                    ? billingInterval === 'yearly' ? 'active wedding/yr' : 'active wedding/mo'
                    : billingInterval === 'yearly' ? 'yr' : 'mo'}
                </div>
              </div>
            </div>

            {/* Step indicator */}
            <div className="flex items-center gap-2 mb-5">
              {[1, 2].map((s) => (
                <div key={s} className="flex items-center">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                    step >= s ? 'bg-indigo-600 text-white' : 'bg-slate-700 text-slate-400'
                  }`}>
                    {step > s ? '✓' : s}
                  </div>
                  {s < 2 && <div className={`w-8 h-0.5 mx-1 ${step > 1 ? 'bg-indigo-600' : 'bg-slate-700'}`} />}
                </div>
              ))}
              <span className="text-xs text-slate-400 ml-2">
                {step === 1 ? 'Account' : 'Details'}
              </span>
            </div>

            <form onSubmit={onSubmit} autoComplete="off" className="space-y-4">
              {/* Hidden honeypot fields to absorb Chrome autofill and prevent
                  password leaking into company/phone fields on step 2. */}
              <div aria-hidden="true" className="absolute" style={{ width: 0, height: 0, overflow: 'hidden', opacity: 0 }}>
                <input type="text" name="fake_username" tabIndex={-1} autoComplete="username" />
                <input type="password" name="fake_password" tabIndex={-1} autoComplete="current-password" />
              </div>
              {/* Step 1 fields — hidden (not unmounted) on step 2 so react-hook-form retains values */}
              <div className={step === 1 ? '' : 'hidden'}>
                  <div>
                    <h2 className="text-xl font-bold text-white mb-1">Create your account</h2>
                    <p className="text-sm text-slate-400">Enter your email and create a password</p>
                  </div>

                  <div className="mt-4">
                    <label className="block text-sm font-medium text-slate-300 mb-1">Email</label>
                    <input
                      type="email"
                      autoComplete="email"
                      {...register('email', { required: 'Email is required' })}
                      className="w-full px-4 py-3 rounded-lg bg-slate-700/50 border border-slate-600 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      placeholder="you@company.com"
                    />
                    {errors.email && <p className="mt-1 text-xs text-red-400">{errors.email.message}</p>}
                  </div>

                  <div className="mt-4">
                    <label className="block text-sm font-medium text-slate-300 mb-1">Password</label>
                    <input
                      type="password"
                      autoComplete="new-password"
                      {...register('password', {
                        required: 'Password is required',
                        minLength: { value: 8, message: 'Min 8 characters' },
                        pattern: {
                          value: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-[\]{}|;:,.<>?]).{8,}$/,
                          message: 'Include upper, lower, number & special char'
                        }
                      })}
                      className="w-full px-4 py-3 rounded-lg bg-slate-700/50 border border-slate-600 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      placeholder="••••••••"
                    />
                    {errors.password && <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>}
                  </div>

                  <div className="mt-4">
                    <label className="block text-sm font-medium text-slate-300 mb-1">Confirm Password</label>
                    <input
                      type="password"
                      autoComplete="new-password"
                      {...register('confirmPassword', {
                        required: 'Please confirm password',
                        validate: (value) => value === watch('password') || 'Passwords must match'
                      })}
                      className="w-full px-4 py-3 rounded-lg bg-slate-700/50 border border-slate-600 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      placeholder="••••••••"
                    />
                    {errors.confirmPassword && <p className="mt-1 text-xs text-red-400">{errors.confirmPassword.message}</p>}
                  </div>

                  <button
                    type="button"
                    onClick={handleNext}
                    className="w-full mt-4 py-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition-all"
                  >
                    Continue
                  </button>
              </div>
              {step === 2 && (
                <>
                  <div className="flex items-center gap-2 mb-2">
                    <button
                      type="button"
                      onClick={() => setStep(1)}
                      className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                      </svg>
                    </button>
                    <div>
                      <h2 className="text-xl font-bold text-white">Your details</h2>
                      <p className="text-sm text-slate-400">Almost there! Just a few more details.</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">First name</label>
                      <input
                        autoComplete="given-name"
                        {...register('firstName', { required: 'Required' })}
                        className="w-full px-3 py-2.5 rounded-lg bg-slate-700/50 border border-slate-600 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
                        placeholder="Jane"
                      />
                      {errors.firstName && <p className="mt-1 text-xs text-red-400">{errors.firstName.message}</p>}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">Last name</label>
                      <input
                        autoComplete="family-name"
                        {...register('lastName', { required: 'Required' })}
                        className="w-full px-3 py-2.5 rounded-lg bg-slate-700/50 border border-slate-600 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
                        placeholder="Smith"
                      />
                      {errors.lastName && <p className="mt-1 text-xs text-red-400">{errors.lastName.message}</p>}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Company name</label>
                    <input
                      autoComplete="one-time-code"
                      {...register('companyName', { required: 'Required' })}
                      className="w-full px-3 py-2.5 rounded-lg bg-slate-700/50 border border-slate-600 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
                      placeholder="Your Planning Co."
                    />
                    {errors.companyName && <p className="mt-1 text-xs text-red-400">{errors.companyName.message}</p>}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">Phone</label>
                    <input
                      type="tel"
                      autoComplete="one-time-code"
                      {...register('phone', { required: 'Required' })}
                      className="w-full px-3 py-2.5 rounded-lg bg-slate-700/50 border border-slate-600 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
                      placeholder="(555) 123-4567"
                    />
                    {errors.phone && <p className="mt-1 text-xs text-red-400">{errors.phone.message}</p>}
                  </div>

                  <label className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      {...register('acceptTerms', { required: 'You must accept the terms' })}
                      className="mt-0.5 rounded border-slate-600 bg-slate-700 text-indigo-600 focus:ring-indigo-500"
                    />
                    <span className="text-xs text-slate-400">
                      I agree to the <a href="#" className="text-indigo-400 hover:underline">Terms</a> and <a href="#" className="text-indigo-400 hover:underline">Privacy Policy</a>
                    </span>
                  </label>
                  {errors.acceptTerms && <p className="text-xs text-red-400">{errors.acceptTerms.message as string}</p>}

                  <button
                    type="submit"
                    disabled={isSubmitting || loading}
                    className="w-full py-3 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold transition-all disabled:opacity-50"
                  >
                    {isSubmitting ? 'Creating account...' : 'Continue to payment →'}
                  </button>

                  <p className="text-center text-xs text-slate-500">
                    Secure checkout powered by Stripe
                  </p>
                </>
              )}
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignupModal;
