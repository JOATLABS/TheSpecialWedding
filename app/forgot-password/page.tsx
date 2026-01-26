'use client';

import Link from 'next/link';
import { FormEvent, useState } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { GlassCard } from '@/components/ui/GlassCard';
import { Button } from '@/components/ui/Button';

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isValidEmail = emailPattern.test(email);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!isValidEmail) {
      setError('Please enter a valid email address.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/forgot-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email: email.trim() }),
      });

      if (response.ok) {
        setSubmitted(true);
      } else {
        // Even on error, show success for security (don't reveal if email exists)
        setSubmitted(true);
      }
    } catch (err) {
      // Show success anyway for security
      setSubmitted(true);
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
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

        <div className="relative mx-auto flex min-h-screen w-full max-w-lg items-center px-4 py-12">
          <GlassCard depth="near" blur="xl" className="w-full px-6 py-8 sm:px-10">
            <div className="text-center">
              <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100">
                <svg className="h-8 w-8 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <h1 className="text-2xl font-semibold text-wedding-navy">Check Your Email</h1>
              <p className="mt-4 text-wedding-navy/70">
                If an account exists for <strong className="text-wedding-navy">{email}</strong>, we&apos;ve sent a password reset link.
              </p>
              <p className="mt-2 text-sm text-wedding-navy/60">
                The link will expire in 1 hour.
              </p>

              <div className="mt-8 space-y-4">
                <p className="text-sm text-wedding-navy/60">
                  Didn&apos;t receive the email? Check your spam folder or{' '}
                  <button
                    onClick={() => {
                      setSubmitted(false);
                      setEmail('');
                    }}
                    className="font-medium text-wedding-rose hover:text-wedding-gold"
                  >
                    try again
                  </button>
                </p>

                <Link
                  href="/admin/login"
                  className="inline-block text-sm font-medium text-wedding-rose transition hover:text-wedding-gold"
                >
                  Back to login
                </Link>
              </div>
            </div>
          </GlassCard>
        </div>
      </div>
    );
  }

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

      <div className="relative mx-auto flex min-h-screen w-full max-w-lg items-center px-4 py-12">
        <GlassCard depth="near" blur="xl" className="w-full px-6 py-8 sm:px-10">
          <div className="text-center mb-8">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-wedding-rose/10">
              <svg className="h-7 w-7 text-wedding-rose" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
              </svg>
            </div>
            <h1 className="text-2xl font-semibold text-wedding-navy">Forgot your password?</h1>
            <p className="mt-2 text-sm text-wedding-navy/70">
              No worries! Enter your email and we&apos;ll send you a reset link.
            </p>
          </div>

          <form className="space-y-5" onSubmit={handleSubmit} noValidate>
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium text-wedding-navy">
                Email address
              </label>
              <input
                id="email"
                type="email"
                inputMode="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                className="w-full rounded-xl border border-white/40 bg-white/60 px-4 py-3 text-base text-wedding-navy shadow-inner placeholder:text-wedding-navy/40 focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/50"
              />
            </div>

            {error && (
              <p role="alert" className="rounded-lg border border-wedding-rose/40 bg-wedding-rose/10 px-3 py-2 text-sm text-wedding-rose">
                {error}
              </p>
            )}

            <Button
              type="submit"
              disabled={!isValidEmail || submitting}
              className="w-full justify-center rounded-xl py-3 text-base shadow-lg transition disabled:cursor-not-allowed disabled:opacity-60"
              aria-busy={submitting}
            >
              {submitting ? 'Sending reset link...' : 'Send reset link'}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <Link
              href="/admin/login"
              className="text-sm font-medium text-wedding-rose transition hover:text-wedding-gold"
            >
              Back to login
            </Link>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
