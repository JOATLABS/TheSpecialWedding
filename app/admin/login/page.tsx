'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { GlassCard } from '@/components/ui/GlassCard';
import { useAdmin } from '@/contexts/AdminContext';

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const showcaseHighlights = [
  {
    label: 'Every detail, one place',
    description: 'RSVPs, guest lists, seating charts, and reminders — all managed from a single dashboard so nothing slips through.',
  },
  {
    label: 'Keep couples in the loop',
    description: 'Send updates, share timelines, and track vendor progress without switching between apps or spreadsheets.',
  },
];

const showcaseStats = [
  { value: 'Real-time', caption: 'Guest RSVPs and responses update instantly' },
  { value: 'Any device', caption: 'Manage weddings from your desk or on-site' },
];

function WelcomeShowcase() {
  return (
    <div className="relative w-full max-w-xl overflow-hidden rounded-[2.5rem] border border-white/45 bg-gradient-to-br from-white/65 via-white/30 to-white/10 p-6 shadow-[0_40px_120px_-40px_rgba(29,53,87,0.35)] backdrop-blur-2xl sm:p-8">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.65),transparent_55%),radial-gradient(circle_at_bottom_left,rgba(212,165,165,0.45),transparent_60%)]"
      />
      <div className="relative z-10 flex flex-col gap-6 text-wedding-navy">
        <header className="space-y-2">
          <p className="text-[0.6rem] font-semibold uppercase tracking-[0.3em] text-wedding-navy/65">Your planning hub</p>
          <h2 className="text-[1.15rem] font-semibold leading-tight sm:text-[1.3rem]">Beautiful weddings start with effortless planning</h2>
          <p className="text-[0.78rem] text-wedding-navy/70 sm:text-sm">
            Everything you need to coordinate, communicate, and create unforgettable celebrations — all in one place.
          </p>
        </header>

        <dl className="grid gap-3">
          {showcaseHighlights.map((highlight) => (
            <div
              key={highlight.label}
              className="relative overflow-hidden rounded-[1.8rem] border border-white/50 bg-white/60 p-4 shadow-lg backdrop-blur"
            >
              <div className="pointer-events-none absolute -right-6 -top-6 h-16 w-16 rounded-full bg-wedding-rose/20 blur-xl" aria-hidden="true" />
              <div className="pointer-events-none absolute -bottom-10 left-3 h-20 w-20 rounded-full bg-wedding-sage/20 blur-2xl" aria-hidden="true" />
              <div className="relative z-10 space-y-1.5">
                <dt className="text-[0.65rem] font-semibold uppercase tracking-[0.28em] text-wedding-navy/60">{highlight.label}</dt>
                <dd className="text-[0.8rem] leading-relaxed text-wedding-navy/75">{highlight.description}</dd>
              </div>
            </div>
          ))}
        </dl>

        <div className="grid grid-cols-2 gap-3">
          {showcaseStats.map((stat) => (
            <div
              key={stat.caption}
              className="rounded-[1.6rem] border border-white/45 bg-white/55 px-4 py-3 text-center shadow-inner backdrop-blur"
            >
              <div className="text-lg font-semibold text-wedding-navy">{stat.value}</div>
              <p className="mt-1 text-[0.7rem] text-wedding-navy/65">{stat.caption}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

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
    <div className="relative min-h-screen overflow-hidden bg-gradient-to-br from-[#f8f5f2] via-[#f2ecff] to-[#eef6ff]">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 right-0 h-96 w-96 rounded-full bg-wedding-rose/20 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute bottom-[-6rem] left-[-6rem] h-[22rem] w-[22rem] rounded-full bg-wedding-navy/10 blur-3xl"
      />

      <div className="relative mx-auto flex min-h-screen w-full max-w-[1600px] items-center px-4 py-12 sm:px-6 lg:px-12">
        <div className="relative isolate w-full overflow-hidden rounded-[3rem] border border-white/40 bg-white/25 p-6 shadow-2xl backdrop-blur-2xl sm:p-8">
          <div aria-hidden="true" className="pointer-events-none absolute inset-0">
            <div className="absolute -left-16 top-12 h-32 w-32 rounded-full bg-white/50 blur-3xl" />
            <div className="absolute -right-20 bottom-10 h-28 w-40 rounded-full bg-wedding-rose/20 blur-3xl" />
            <div className="absolute inset-y-12 left-1/2 hidden w-px -translate-x-1/2 bg-gradient-to-b from-white/5 via-white/50 to-white/5 opacity-70 blur-sm md:block" />
          </div>
          <div className="relative grid items-stretch gap-10 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-12 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
            <section className="order-2 flex justify-center md:order-2 md:pl-6 lg:pl-10">
              <div className="w-full">
                <WelcomeShowcase />
              </div>
            </section>

            <section className="order-1 md:order-1 md:pr-6 lg:pr-10">
              <GlassCard depth="near" blur="xl" className="h-full px-6 py-7 sm:px-8 xl:px-10">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-[0.3em] text-wedding-navy/70 sm:text-sm">Planner portal</p>
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
                </div>

                <div className="mt-6 rounded-2xl border border-white/30 bg-white/40 px-5 py-4 text-sm text-wedding-navy/70 shadow-inner">
                  <h2 className="text-xs font-semibold uppercase tracking-[0.25em] text-wedding-navy/60 sm:text-sm">Plan from anywhere</h2>
                  <p className="mt-1.5 text-xs sm:text-sm">
                    Whether you're at a venue walkthrough or at your desk, your full dashboard is always a tap away on any device.
                  </p>
                </div>
              </GlassCard>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
