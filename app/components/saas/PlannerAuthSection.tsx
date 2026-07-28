'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';

import { SocialAuthButtons } from '../auth/SocialAuthButtons';
import { ThemeConfig } from '@/types/wedding';
import { clearAdminAuthStorage, persistAdminAuthToken } from '@/utils/adminAuthStorage';
import { resolveApiUrl } from './apiClient';

export interface SubscriptionPlan {
  _id: string;
  name: string;
  description: string;
  price_monthly: number;
  // 2026-07-28 pricing: yearly billing is not sold; live plan docs carry
  // price_yearly: null. Optional for legacy plan documents only.
  price_yearly?: number | null;
  billing_model?: string;
  is_metered?: boolean;
  trial_days?: number;
  is_featured: boolean;
  is_active: boolean;
  display_order?: number;
}

type PlanSelection = { id: string; name?: string };

type AuthMode = 'signup' | 'login';

type PlannerAuthSectionProps = {
  mode?: AuthMode;
  defaultMode?: AuthMode;
  onModeChange?: (mode: AuthMode) => void;
  theme: ThemeConfig;
  plans?: SubscriptionPlan[];
  plansLoading?: boolean;
  plansError?: string;
  plansNotice?: string;
  selectedPlan?: PlanSelection | null;
  onSelectPlan?: (plan: PlanSelection) => void;
  onSignupSuccess?: () => void;
  className?: string;
  layout?: 'panel' | 'modal';
};

type SignupFormValues = {
  firstName: string;
  lastName: string;
  companyName: string;
  email: string;
  password: string;
  confirmPassword: string;
  acceptTerms: boolean;
};

type LoginFormValues = {
  email: string;
  password: string;
  rememberMe: boolean;
};

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function getErrorMessage(response: Response, fallback: string) {
  return response
    .clone()
    .json()
    .then((body) => {
      if (body && typeof body === 'object') {
        if (typeof body.detail === 'string') {
          return body.detail;
        }
        if (Array.isArray(body.detail) && body.detail.length > 0) {
          const first = body.detail[0];
          if (first && typeof first === 'object' && 'msg' in first && typeof first.msg === 'string') {
            return first.msg as string;
          }
        }
      }
      return fallback;
    })
    .catch(() => fallback);
}

function PlanToggle({
  plans,
  selectedPlan,
  onSelectPlan,
  isLoading,
  error,
  notice,
}: {
  plans?: SubscriptionPlan[];
  selectedPlan?: PlanSelection | null;
  onSelectPlan?: (plan: PlanSelection) => void;
  isLoading?: boolean;
  error?: string;
  notice?: string;
}) {
  const [cycle, setCycle] = useState<'monthly' | 'yearly'>('monthly');

  useEffect(() => {
    if (!plans || plans.length === 0 || selectedPlan) {
      return;
    }
    const featured = plans.find((plan) => plan.is_featured) ?? plans[0];
    onSelectPlan?.({ id: featured._id, name: featured.name });
  }, [plans, onSelectPlan, selectedPlan]);

  const formatPrice = (plan: SubscriptionPlan) => {
    if (plan.price_monthly === 0) {
      return 'Free';
    }
    const value = cycle === 'monthly' ? plan.price_monthly : plan.price_yearly || plan.price_monthly * 12;
    const isMetered = plan.is_metered || plan.billing_model === 'metered';
    if (isMetered) {
      return `$${value}${cycle === 'monthly' ? '/active wedding/mo' : '/active wedding/yr'}`;
    }
    return `$${value}${cycle === 'monthly' ? '/mo' : '/yr'}`;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center rounded-2xl border border-slate-200 bg-white/80 px-4 py-6 text-sm text-slate-600">
        Loading pricing…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
    );
  }

  if (!plans || plans.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between rounded-full bg-white/80 p-1 text-xs font-medium text-slate-600 shadow-inner">
        <button
          type="button"
          onClick={() => setCycle('monthly')}
          className={`flex-1 rounded-full px-3 py-1.5 transition ${cycle === 'monthly' ? 'bg-slate-900 text-white shadow' : 'hover:text-slate-900'}`}
          aria-pressed={cycle === 'monthly'}
        >
          Monthly
        </button>
        <button
          type="button"
          onClick={() => setCycle('yearly')}
          className={`flex-1 rounded-full px-3 py-1.5 transition ${cycle === 'yearly' ? 'bg-slate-900 text-white shadow' : 'hover:text-slate-900'}`}
          aria-pressed={cycle === 'yearly'}
        >
          Yearly
        </button>
      </div>

      <div className="space-y-3">
        {plans.map((plan) => {
          if (!plan.is_active) {
            return null;
          }
          const isSelected = selectedPlan?.id === plan._id;
          return (
            <button
              key={plan._id}
              type="button"
              onClick={() => onSelectPlan?.({ id: plan._id, name: plan.name })}
              className={`w-full rounded-2xl border px-4 py-3 text-left transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900 ${
                isSelected
                  ? 'border-slate-900 bg-slate-900 text-white shadow-lg'
                  : 'border-slate-200/70 bg-white/85 text-slate-800 hover:border-slate-300 hover:bg-white'
              }`}
              aria-pressed={isSelected}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <p className="text-sm font-semibold">
                    {plan.name}
                    {plan.is_featured ? ' · Most popular' : ''}
                  </p>
                  <p className={`text-xs ${isSelected ? 'text-white/80' : 'text-slate-600'}`}>{plan.description}</p>
                  {plan.trial_days ? (
                    <p className={`text-[11px] font-medium uppercase tracking-[0.18em] ${isSelected ? 'text-emerald-100' : 'text-emerald-700'}`}>
                      {plan.trial_days}-day free trial · no card required
                    </p>
                  ) : null}
                </div>
                <span className={`text-sm font-semibold ${isSelected ? 'text-white' : 'text-slate-900'}`}>{formatPrice(plan)}</span>
              </div>
            </button>
          );
        })}
      </div>

      {notice && (
        <p className="rounded-2xl border border-slate-200/70 bg-slate-50/90 px-4 py-3 text-xs text-slate-600">{notice}</p>
      )}

      {cycle === 'yearly' && (
        <p className="text-xs text-slate-500">Yearly pricing highlights total annual investment so you can plan budgets with clarity.</p>
      )}
    </div>
  );
}

export function PlannerAuthSection({
  mode,
  defaultMode = 'signup',
  onModeChange,
  theme,
  plans,
  plansLoading,
  plansError,
  plansNotice,
  selectedPlan,
  onSelectPlan,
  onSignupSuccess,
  className = '',
  layout = 'panel',
}: PlannerAuthSectionProps) {
  const [internalMode, setInternalMode] = useState<AuthMode>(defaultMode);
  const resolvedMode = mode ?? internalMode;

  const [internalPlan, setInternalPlan] = useState<PlanSelection | null>(selectedPlan ?? null);
  const activePlan = selectedPlan ?? internalPlan;

  const handleModeChange = (next: AuthMode) => {
    onModeChange?.(next);
    if (mode === undefined) {
      setInternalMode(next);
    }
  };

  const handlePlanSelect = (plan: PlanSelection) => {
    onSelectPlan?.(plan);
    if (!selectedPlan) {
      setInternalPlan(plan);
    }
    handleModeChange('signup');
  };

  const signupForm = useForm<SignupFormValues>({
    mode: 'onBlur',
    defaultValues: {
      firstName: '',
      lastName: '',
      companyName: '',
      email: '',
      password: '',
      confirmPassword: '',
      acceptTerms: false,
    },
  });
  const loginForm = useForm<LoginFormValues>({
    mode: 'onBlur',
    defaultValues: { email: '', password: '', rememberMe: true },
  });

  const [signupComplete, setSignupComplete] = useState(false);

  const containerClass = useMemo(
    () =>
      [
        'relative rounded-2xl sm:rounded-[2.5rem] border border-white/60 bg-white/90 text-left text-slate-900 shadow-[0_30px_100px_-45px_rgba(15,23,42,0.35)] backdrop-blur-2xl',
        layout === 'modal' ? 'p-6 sm:p-8' : 'p-6 sm:p-8 lg:p-10',
        className,
      ]
        .filter(Boolean)
        .join(' '),
    [className, layout]
  );

  const renderSignupForm = () => {
    if (signupComplete) {
      return (
        <div className="space-y-5 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
            <svg aria-hidden="true" className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div className="space-y-2">
            <h3 className="text-lg font-semibold text-slate-900">Check your inbox</h3>
            <p className="text-sm text-slate-600">
              We&apos;ve emailed a verification link so you can activate your planner workspace before signing in.
            </p>
          </div>
          <div className="space-y-3">
            <button
              type="button"
              className="w-full rounded-xl px-4 py-2 text-sm font-semibold text-white shadow-md transition hover:opacity-95"
              style={{ backgroundColor: theme.primary_color }}
              onClick={() => {
                if (typeof window !== 'undefined') {
                  window.location.href = '/admin/login';
                }
              }}
            >
              Go to planner login
            </button>
            <button
              type="button"
              className="w-full rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              onClick={() => setSignupComplete(false)}
            >
              Back to registration
            </button>
          </div>
        </div>
      );
    }

    const {
      register,
      handleSubmit,
      formState: { errors, isSubmitting },
      setError,
      getValues,
      reset,
    } = signupForm;

    const onSubmit = handleSubmit(async (values) => {
      if (values.password !== values.confirmPassword) {
        setError('confirmPassword', { type: 'validate', message: 'Passwords must match' });
        return;
      }

      let endpoint: string;
      try {
        endpoint = resolveApiUrl('/public/register');
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Registration is unavailable right now. Please try again later.';
        setError('root', { message });
        return;
      }

      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            email: values.email.trim(),
            password: values.password,
            first_name: values.firstName.trim(),
            last_name: values.lastName.trim(),
            company_name: values.companyName.trim(),
            selected_plan_id: activePlan?.id,
            role: 'wedding_planner',
          }),
        });

        if (!response.ok) {
          const message = await getErrorMessage(response, 'Registration failed. Please review your details and try again.');
          setError('root', { message });
          return;
        }

        setSignupComplete(true);
        reset();
        onSignupSuccess?.();
        toast.success('Registration email sent. Check your inbox to verify your workspace.');
      } catch (error) {
        const message =
          error instanceof Error && error.message.includes('NEXT_PUBLIC_API_BASE_URL')
            ? 'Registration is unavailable because the platform URL is not configured. Please contact support.'
            : error instanceof Error && error.message
              ? `Registration failed: ${error.message}`
              : 'Registration failed. Please try again.';
        setError('root', { message });
      }
    });

    return (
      <form className="space-y-5" onSubmit={onSubmit} noValidate>
        <div className="space-y-2">
          <SocialAuthButtons flow="signup" redirectPath="/setup-account" />
          <p className="text-xs text-slate-500">
            We&apos;ll redirect you to verify Google or Apple before returning to finish onboarding.
          </p>
        </div>

        <div className="flex items-center gap-3 text-[0.7rem] font-medium uppercase tracking-[0.32em] text-slate-400">
          <div className="h-px flex-1 bg-gradient-to-r from-transparent via-slate-300/70 to-transparent" aria-hidden="true" />
          <span>Or email</span>
          <div className="h-px flex-1 bg-gradient-to-r from-transparent via-slate-300/70 to-transparent" aria-hidden="true" />
        </div>

        {errors.root && <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{errors.root.message}</p>}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="signup-first-name" className="text-sm font-medium text-slate-800">
              First name
            </label>
            <input
              id="signup-first-name"
              type="text"
              autoComplete="given-name"
              {...register('firstName', { required: 'First name is required' })}
              className={`w-full rounded-xl border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-slate-900/10 ${
                errors.firstName ? 'border-red-300' : 'border-slate-200'
              }`}
            />
            {errors.firstName && <p className="text-xs text-red-600">{errors.firstName.message}</p>}
          </div>
          <div className="space-y-1.5">
            <label htmlFor="signup-last-name" className="text-sm font-medium text-slate-800">
              Last name
            </label>
            <input
              id="signup-last-name"
              type="text"
              autoComplete="family-name"
              {...register('lastName', { required: 'Last name is required' })}
              className={`w-full rounded-xl border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-slate-900/10 ${
                errors.lastName ? 'border-red-300' : 'border-slate-200'
              }`}
            />
            {errors.lastName && <p className="text-xs text-red-600">{errors.lastName.message}</p>}
          </div>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="signup-company" className="text-sm font-medium text-slate-800">
            Planning business or team name
          </label>
          <input
            id="signup-company"
            type="text"
            autoComplete="organization"
            {...register('companyName', { required: 'Company name helps us prepare the workspace' })}
            className={`w-full rounded-xl border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-slate-900/10 ${
              errors.companyName ? 'border-red-300' : 'border-slate-200'
            }`}
          />
          {errors.companyName ? (
            <p className="text-xs text-red-600">{errors.companyName.message}</p>
          ) : (
            <p className="text-xs text-slate-500">This creates the workspace used by the person or team managing weddings.</p>
          )}
        </div>

        <div className="space-y-1.5">
          <label htmlFor="signup-email" className="text-sm font-medium text-slate-800">
            Work email
          </label>
          <input
            id="signup-email"
            type="email"
            autoComplete="email"
            {...register('email', {
              required: 'Work email is required',
              validate: (value) => emailPattern.test(value) || 'Enter a valid email address',
            })}
            className={`w-full rounded-xl border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-slate-900/10 ${
              errors.email ? 'border-red-300' : 'border-slate-200'
            }`}
          />
          {errors.email ? (
            <p className="text-xs text-red-600">{errors.email.message}</p>
          ) : (
            <p className="text-xs text-slate-500">Use the email your couples already recognise for a seamless launch.</p>
          )}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label htmlFor="signup-password" className="text-sm font-medium text-slate-800">
              Password
            </label>
            <input
              id="signup-password"
              type="password"
              autoComplete="new-password"
              {...register('password', {
                required: 'Password is required',
                minLength: { value: 8, message: 'Password must be at least 8 characters' },
              })}
              className={`w-full rounded-xl border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-slate-900/10 ${
                errors.password ? 'border-red-300' : 'border-slate-200'
              }`}
            />
            {errors.password ? (
              <p className="text-xs text-red-600">{errors.password.message}</p>
            ) : (
              <p className="text-xs text-slate-500">Use at least 8 characters with a mix of letters and numbers.</p>
            )}
          </div>
          <div className="space-y-1.5">
            <label htmlFor="signup-confirm" className="text-sm font-medium text-slate-800">
              Confirm password
            </label>
            <input
              id="signup-confirm"
              type="password"
              autoComplete="new-password"
              {...register('confirmPassword', {
                required: 'Confirm your password',
                validate: (value) => value === getValues('password') || 'Passwords must match',
              })}
              className={`w-full rounded-xl border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-slate-900/10 ${
                errors.confirmPassword ? 'border-red-300' : 'border-slate-200'
              }`}
            />
            {errors.confirmPassword && <p className="text-xs text-red-600">{errors.confirmPassword.message}</p>}
          </div>
        </div>

        <label className="flex items-start gap-3 text-sm text-slate-600">
          <input
            type="checkbox"
            className="mt-1 rounded border-slate-300 text-slate-900 focus:ring-slate-900/40"
            {...register('acceptTerms', {
              validate: (value) => value || 'Please accept the terms and privacy policy to continue',
            })}
          />
          <span>
            I agree to the{' '}
            <Link href="/docs/compliance/privacy-policy" className="font-medium text-slate-900 underline decoration-slate-300 underline-offset-4 hover:decoration-slate-500">
              Privacy Policy
            </Link>{' '}
            and{' '}
            <Link href="/docs/compliance/terms-of-service" className="font-medium text-slate-900 underline decoration-slate-300 underline-offset-4 hover:decoration-slate-500">
              Terms of Service
            </Link>
            .
          </span>
        </label>
        {errors.acceptTerms && <p className="text-xs text-red-600">{errors.acceptTerms.message}</p>}

        <button
          type="submit"
          className="w-full rounded-xl px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
          style={{ backgroundColor: theme.primary_color }}
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Creating workspace…' : 'Launch your workspace'}
        </button>
      </form>
    );
  };

  const renderLoginForm = () => {
    const {
      register,
      handleSubmit,
      formState: { errors, isSubmitting },
      setError,
    } = loginForm;

    const onSubmit = handleSubmit(async (values) => {
      let endpoint: string;
      try {
        endpoint = resolveApiUrl('/admin/token');
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Login is unavailable right now. Please try again later.';
        setError('root', { message });
        return;
      }

      try {
        clearAdminAuthStorage();
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: values.email.trim(), password: values.password }),
          credentials: 'include',
        });

        if (!response.ok) {
          const message = await getErrorMessage(response, 'We could not sign you in. Double-check your credentials.');
          setError('root', { message });
          return;
        }

        const payload = await response.json();
        if (!payload?.access_token) {
          setError('root', { message: 'Unexpected response from the server. Please try again.' });
          return;
        }

        persistAdminAuthToken(payload.access_token, values.rememberMe);
        toast.success('Login successful');
        // Send planners directly to their dashboard. Previously this hard-redirected
        // to `/admin` (root-admin Platform Health page), which relied on an
        // in-page useEffect to bounce planners to `/admin/planner` — producing
        // a brief content flash and contributing to a pushState loop. The
        // AdminRouteGuard still handles expired/blocked planners by bouncing
        // them to `/admin/planner/billing`.
        window.location.href = '/admin/planner';
      } catch (error) {
        const message =
          error instanceof Error && error.message.includes('NEXT_PUBLIC_API_BASE_URL')
            ? 'Login is unavailable because the platform URL is not configured. Please contact support.'
            : 'We could not sign you in. Please try again.';
        setError('root', { message });
      }
    });

    return (
      <form className="space-y-5" onSubmit={onSubmit} noValidate>
        <div>
          <SocialAuthButtons flow="login" redirectPath="/admin/planner" />
          <p className="mt-3 text-xs text-slate-500">
            Use Google Workspace or Apple ID for instant access with enforced multi-factor security.
          </p>
        </div>

        <div className="flex items-center gap-3 text-[0.7rem] font-medium uppercase tracking-[0.32em] text-slate-400">
          <div className="h-px flex-1 bg-gradient-to-r from-transparent via-slate-300/70 to-transparent" aria-hidden="true" />
          <span>Or email</span>
          <div className="h-px flex-1 bg-gradient-to-r from-transparent via-slate-300/70 to-transparent" aria-hidden="true" />
        </div>

        {errors.root && <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{errors.root.message}</p>}

        <div className="space-y-1.5">
          <label htmlFor="login-email" className="text-sm font-medium text-slate-800">
            Work email
          </label>
          <input
            id="login-email"
            type="email"
            autoComplete="email"
            {...register('email', {
              required: 'Email is required',
              validate: (value) => emailPattern.test(value) || 'Enter a valid email address',
            })}
            className={`w-full rounded-xl border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-slate-900/10 ${
              errors.email ? 'border-red-300' : 'border-slate-200'
            }`}
          />
          {errors.email && <p className="text-xs text-red-600">{errors.email.message}</p>}
        </div>

        <div className="space-y-1.5">
          <label htmlFor="login-password" className="text-sm font-medium text-slate-800">
            Password
          </label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            {...register('password', { required: 'Password is required' })}
            className={`w-full rounded-xl border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-slate-900/10 ${
              errors.password ? 'border-red-300' : 'border-slate-200'
            }`}
          />
          {errors.password && <p className="text-xs text-red-600">{errors.password.message}</p>}
        </div>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" className="rounded border-slate-300 text-slate-900 focus:ring-slate-900/40" {...register('rememberMe')} />
            Remember this device
          </label>
          <Link href="/forgot-password" className="text-sm font-medium text-slate-800 underline decoration-slate-300 underline-offset-4 hover:decoration-slate-500">
            Forgot password?
          </Link>
        </div>

        <button
          type="submit"
          className="w-full rounded-xl px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:opacity-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
          style={{ backgroundColor: theme.primary_color }}
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Checking credentials…' : 'Log in securely'}
        </button>

        <p className="text-xs text-slate-500">
          Need access for your team?{' '}
          <button
            type="button"
            onClick={() => handleModeChange('signup')}
            className="font-semibold text-slate-900 underline decoration-slate-300 underline-offset-4 hover:decoration-slate-500"
          >
            Start a new workspace
          </button>
          .
        </p>
      </form>
    );
  };

  return (
    <section className={containerClass}>
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 rounded-[2.5rem] bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.65),transparent_55%),radial-gradient(circle_at_bottom_left,rgba(180,209,255,0.4),transparent_60%)]"
      />
      <div className="relative flex flex-col gap-6">
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-[0.32em] text-slate-500">Planner access</p>
          <h2 className="text-2xl font-semibold text-slate-900 sm:text-[1.65rem]">
            {resolvedMode === 'signup' ? 'Launch your planner workspace' : 'Welcome back, planner'}
          </h2>
          <p className="text-sm text-slate-600">
            Manage client weddings, couples, guests, vendors, and your team from one operating system built for planners.
          </p>
        </div>

        <div className="inline-flex rounded-full bg-white/80 p-1 text-sm font-medium shadow-inner">
          <button
            type="button"
            onClick={() => handleModeChange('signup')}
            className={`flex-1 rounded-full px-4 py-2 transition ${resolvedMode === 'signup' ? 'bg-slate-900 text-white shadow' : 'text-slate-600 hover:text-slate-900'}`}
            aria-pressed={resolvedMode === 'signup'}
          >
            Sign up
          </button>
          <button
            type="button"
            onClick={() => handleModeChange('login')}
            className={`flex-1 rounded-full px-4 py-2 transition ${resolvedMode === 'login' ? 'bg-slate-900 text-white shadow' : 'text-slate-600 hover:text-slate-900'}`}
            aria-pressed={resolvedMode === 'login'}
          >
            Log in
          </button>
        </div>

        {resolvedMode === 'signup' && (
          <div className="space-y-5">
            <PlanToggle
              plans={plans}
              selectedPlan={activePlan}
              onSelectPlan={handlePlanSelect}
              isLoading={plansLoading}
              error={plansError}
              notice={plansNotice}
            />
            <div className="rounded-2xl border border-slate-200/70 bg-white/85 p-4 text-sm text-slate-700 shadow-sm">
              <p className="font-semibold text-slate-900">Selected plan</p>
              <p className="mt-1 text-slate-600">
                {activePlan?.name ?? 'Choose the plan that fits your studio. You can adjust this during onboarding.'}
              </p>
            </div>
          </div>
        )}

        {resolvedMode === 'signup' ? renderSignupForm() : renderLoginForm()}
      </div>
    </section>
  );
}

export default PlannerAuthSection;
