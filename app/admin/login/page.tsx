'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { GlassCard } from '@/components/ui/GlassCard';
import { useAdmin } from '@/contexts/AdminContext';
import { BrandLockup } from '@/components/brand/BrandLockup';
import { PortalSwitch } from '@/components/auth/PortalSwitch';

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function AdminLoginPage() {
  const { login } = useAdmin();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [querySuccessMessage, setQuerySuccessMessage] = useState<string | null>(null);
  const [dismissedQuerySuccess, setDismissedQuerySuccess] = useState(false);
  // PR1 Step 4: mid-session cutoff redirects (e.g. blocked team member bounced
  // back to /admin/login?error=<reason>) surface via this banner. Kept separate
  // from the form-submit `error` state so a user can still see *why* they were
  // kicked out while typing a fresh login attempt. No auto-dismiss — the
  // subscription-block copy needs to stay readable until the user ack's it or
  // submits again.
  const [queryErrorMessage, setQueryErrorMessage] = useState<string | null>(null);
  const [dismissedQueryError, setDismissedQueryError] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const message = params.get('message');
    const paymentState = params.get('payment');
    const derivedMessage = message
      ?? (paymentState === 'success'
        ? 'Payment received. Check your inbox and verify your email before signing in.'
        : null);

    setQuerySuccessMessage(derivedMessage);
    setDismissedQuerySuccess(false);

    const errorParam = params.get('error');
    setQueryErrorMessage(errorParam && errorParam.trim().length > 0 ? errorParam : null);
    setDismissedQueryError(false);
  }, []);

  useEffect(() => {
    if (!querySuccessMessage) return;
    const timer = setTimeout(() => setDismissedQuerySuccess(true), 10000);
    return () => clearTimeout(timer);
  }, [querySuccessMessage]);

  const disableSubmit = useMemo(() => {
    if (!emailPattern.test(email)) {
      return true;
    }
    return password.length === 0 || submitting;
  }, [email, password.length, submitting]);

  const visibleSuccessMessage = !dismissedQuerySuccess ? querySuccessMessage : null;
  const visibleQueryErrorMessage = !dismissedQueryError ? queryErrorMessage : null;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (disableSubmit) {
      setError('Please enter your email and password to sign in.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      await login(email.trim(), password, rememberMe);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative min-h-dvh overflow-x-hidden bg-gradient-to-br from-[#f8f5f2] via-[#f2ecff] to-[#eef6ff]">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 right-0 h-96 w-96 rounded-full bg-wedding-rose/20 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute bottom-[-6rem] left-[-6rem] h-[22rem] w-[22rem] rounded-full bg-wedding-navy/10 blur-3xl"
      />

      <div className="relative mx-auto flex min-h-dvh w-full max-w-3xl flex-col items-center justify-center gap-5 px-4 pb-16 pt-4 sm:gap-6 sm:px-6 sm:pb-12 sm:pt-8 lg:py-8">
        <header className="relative z-10 flex w-full justify-center px-2">
          <span className="sm:hidden">
            <BrandLockup
              variant="full"
              surface="light"
              size="lg"
              className="drop-shadow-[0_16px_36px_rgba(29,53,87,0.16)]"
            />
          </span>
          <span className="hidden sm:block">
            <BrandLockup
              variant="full"
              surface="light"
              size="xl"
              className="drop-shadow-[0_18px_42px_rgba(29,53,87,0.18)]"
            />
          </span>
        </header>
        <div className="relative isolate w-full overflow-hidden rounded-[2rem] border border-white/40 bg-white/25 p-3 shadow-2xl backdrop-blur-2xl sm:rounded-[3rem] sm:p-6">
          <div aria-hidden="true" className="pointer-events-none absolute inset-0">
            <div className="absolute -left-16 top-12 h-32 w-32 rounded-full bg-white/50 blur-3xl" />
            <div className="absolute -right-20 bottom-10 h-28 w-40 rounded-full bg-wedding-rose/20 blur-3xl" />
          </div>
          <div className="relative">
            <section>
              <GlassCard depth="near" blur="xl" className="px-5 py-6 sm:px-8 sm:py-7 xl:px-10">
                <PortalSwitch active="planner" />

                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase text-wedding-navy/70 sm:text-sm">Planner portal</p>
                    <h1 className="mt-2 text-[1.6rem] font-semibold text-wedding-navy sm:text-[1.8rem]">Welcome back</h1>
                    <p className="mt-2 text-[0.9rem] text-wedding-navy/70">
                      Sign in to manage your weddings, guests, and everything in between.
                    </p>
                  </div>
                  <div className="hidden shrink-0 rounded-full bg-white/50 p-4 text-wedding-rose backdrop-blur sm:block">
                    <svg aria-hidden="true" className="h-8 w-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path
                        d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-3.53 0-8 1.79-8 5.33V21h16v-1.67C20 15.79 15.53 14 12 14z"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </div>
                </div>

                <div className="mt-6 space-y-5">
                  <form className="space-y-4" onSubmit={handleSubmit} noValidate>
                    <div className="space-y-2">
                      <label htmlFor="email" className="text-sm font-medium text-wedding-navy">
                        Work email
                      </label>
                      <input
                        id="email"
                        type="email"
                        inputMode="email"
                        autoComplete="email"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                        required
                        aria-invalid={error !== null && !emailPattern.test(email)}
                        aria-describedby="email-guidance"
                        className="w-full rounded-xl border border-white/40 bg-white/60 px-4 py-3 text-base text-wedding-navy shadow-inner placeholder:text-wedding-navy/40 focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/50"
                      />
                      <p id="email-guidance" className="text-xs text-wedding-navy/60">
                        The email you used when creating your account.
                      </p>
                    </div>

                    <div className="space-y-2">
                      <label htmlFor="password" className="text-sm font-medium text-wedding-navy">
                        Password
                      </label>
                      <div className="relative">
                        <input
                          id="password"
                          type={showPassword ? 'text' : 'password'}
                          autoComplete="current-password"
                          value={password}
                          onChange={(event) => setPassword(event.target.value)}
                          required
                          aria-invalid={error !== null && password.length === 0}
                          className="w-full rounded-xl border border-white/40 bg-white/60 px-4 py-3 pr-12 text-base text-wedding-navy shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/50"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword((previous) => !previous)}
                          className="absolute inset-y-0 right-0 flex items-center rounded-r-xl px-4 text-sm font-medium text-wedding-navy/80 hover:text-wedding-rose focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wedding-rose/60"
                          aria-pressed={showPassword}
                        >
                          {showPassword ? 'Hide' : 'Show'}
                        </button>
                      </div>
                    </div>

                    <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
                      <label className="flex items-center gap-2 text-sm text-wedding-navy">
                        <input
                          type="checkbox"
                          checked={rememberMe}
                          onChange={(event) => setRememberMe(event.target.checked)}
                          className="h-4 w-4 rounded border-wedding-navy/20 text-wedding-rose focus:ring-wedding-rose/60"
                        />
                        <span>Keep me signed in on this device</span>
                      </label>
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                        <Link
                          href="/forgot-password"
                          className="text-sm font-medium text-wedding-rose transition hover:text-wedding-gold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wedding-rose/60"
                        >
                          Forgot password?
                        </Link>
                        <Link
                          href="/"
                          className="text-sm font-medium text-wedding-navy/60 transition hover:text-wedding-navy focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wedding-rose/60"
                        >
                          Back to homepage
                        </Link>
                      </div>
                    </div>

                    {visibleSuccessMessage && (
                      <div role="status" className="rounded-lg border border-emerald-400/40 bg-emerald-50 px-4 py-3 flex items-start gap-3">
                        <svg className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <div className="flex-1">
                          <p className="text-sm font-medium text-emerald-800">{visibleSuccessMessage}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => setDismissedQuerySuccess(true)}
                          className="text-emerald-600 hover:text-emerald-800"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    )}

                    {visibleQueryErrorMessage && (
                      <div role="alert" className="rounded-lg border border-wedding-rose/40 bg-wedding-rose/10 px-4 py-3 flex items-start gap-3">
                        <svg className="w-5 h-5 text-wedding-rose flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                        <div className="flex-1">
                          <p className="text-sm font-medium text-wedding-rose">{visibleQueryErrorMessage}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => setDismissedQueryError(true)}
                          className="text-wedding-rose/80 hover:text-wedding-rose"
                          aria-label="Dismiss"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    )}

                    {error && (
                      <p role="alert" className="rounded-lg border border-wedding-rose/40 bg-wedding-rose/10 px-3 py-2 text-sm text-wedding-rose">
                        {error}
                      </p>
                    )}

                    <Button
                      type="submit"
                      disabled={disableSubmit}
                      className="w-full justify-center rounded-xl py-3 text-base shadow-lg transition disabled:cursor-not-allowed disabled:opacity-60"
                      aria-busy={submitting}
                    >
                      {submitting ? 'Signing you in…' : 'Sign in'}
                    </Button>
                  </form>

                  <div className="mt-5 border-t border-white/30 pt-4 text-center">
                    <p className="mx-auto max-w-md text-xs leading-5 text-wedding-navy/55 sm:text-sm">
                      Your full dashboard is ready at a venue walkthrough or from your desk.
                    </p>
                  </div>
                </div>
              </GlassCard>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
