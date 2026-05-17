'use client';

import Link from 'next/link';
import React, { FormEvent, useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import { Button } from '@/components/ui/Button';
import { GlassCard } from '@/components/ui/GlassCard';
import { PUBLIC_LOGIN_PATH } from '@/seo/crawlPolicy';
import { getApiBaseUrl } from '@/utils/env';

interface PasswordValidation {
  minLength: boolean;
  hasUppercase: boolean;
  hasLowercase: boolean;
  hasNumber: boolean;
  hasSpecial: boolean;
}

const validatePassword = (password: string): PasswordValidation => ({
  minLength: password.length >= 8,
  hasUppercase: /[A-Z]/.test(password),
  hasLowercase: /[a-z]/.test(password),
  hasNumber: /\d/.test(password),
  hasSpecial: /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]/.test(password),
});

const isPasswordValid = (validation: PasswordValidation): boolean =>
  validation.minLength &&
  validation.hasUppercase &&
  validation.hasLowercase &&
  validation.hasNumber &&
  validation.hasSpecial;

export default function ResetPasswordPageClient({ initialToken }: { initialToken: string | null }) {
  const router = useRouter();
  const token = initialToken;

  const [loading, setLoading] = useState(true);
  const [tokenValid, setTokenValid] = useState(false);
  const [maskedEmail, setMaskedEmail] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [passwordValidation, setPasswordValidation] = useState<PasswordValidation>({
    minLength: false,
    hasUppercase: false,
    hasLowercase: false,
    hasNumber: false,
    hasSpecial: false,
  });

  const handlePasswordChange = (newPassword: string) => {
    setPassword(newPassword);
    setPasswordValidation(validatePassword(newPassword));
  };

  const validateToken = useCallback(async (resetToken: string) => {
    const baseUrl = getApiBaseUrl();
    const response = await fetch(`${baseUrl}/reset-password/validate/${resetToken}`);

    if (!response.ok) {
      throw new Error('Invalid or expired reset link');
    }

    return await response.json();
  }, []);

  useEffect(() => {
    if (!token) {
      setError('Invalid reset link');
      setLoading(false);
      return;
    }

    let isActive = true;

    const runValidation = async () => {
      setLoading(true);
      try {
        const result = await validateToken(token);
        if (!isActive) {
          return;
        }
        setTokenValid(true);
        setMaskedEmail(result.email);
        setError('');
      } catch (err) {
        if (!isActive) {
          return;
        }
        setTokenValid(false);
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('Invalid or expired reset link');
        }
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    };

    void runValidation();

    return () => {
      isActive = false;
    };
  }, [token, validateToken]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!isPasswordValid(passwordValidation)) {
      setError('Password must meet all requirements');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setSubmitting(true);
    setError('');

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/reset-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          token,
          password,
          confirm_password: confirmPassword,
        }),
      });

      if (response.ok) {
        setSuccess(true);
        setTimeout(() => {
          router.push('/admin/login?message=Password reset successful! Please log in with your new password.');
        }, 3000);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to reset password');
      }
    } catch {
      setError('Failed to reset password. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#f8f5f2] via-[#f2ecff] to-[#eef6ff] flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-wedding-rose mx-auto mb-4" />
          <p className="text-wedding-navy/70">Validating reset link...</p>
        </div>
      </div>
    );
  }

  if (!tokenValid) {
    return (
      <div className="relative min-h-screen overflow-hidden bg-gradient-to-br from-[#f8f5f2] via-[#f2ecff] to-[#eef6ff]">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-40 right-0 h-96 w-96 rounded-full bg-wedding-rose/20 blur-3xl"
        />
        <div className="relative mx-auto flex min-h-screen w-full max-w-lg items-center px-4 py-12">
          <GlassCard depth="near" blur="xl" className="w-full px-6 py-8 sm:px-10 text-center">
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
              <svg className="h-8 w-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.464 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <h1 className="text-2xl font-semibold text-wedding-navy">Invalid Reset Link</h1>
            <p className="mt-4 text-wedding-navy/70">{error}</p>
            <p className="mt-2 text-sm text-wedding-navy/60">
              Password reset links expire after 1 hour.
            </p>

            <div className="mt-8 space-y-3">
              <Link
                href="/forgot-password"
                className="inline-block rounded-xl bg-wedding-rose px-6 py-3 text-white font-medium hover:bg-wedding-rose/90 transition"
              >
                Request New Reset Link
              </Link>
              <div>
                <Link
                  href={PUBLIC_LOGIN_PATH}
                  className="text-sm font-medium text-wedding-rose hover:text-wedding-gold"
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

  if (success) {
    return (
      <div className="relative min-h-screen overflow-hidden bg-gradient-to-br from-[#f8f5f2] via-[#f2ecff] to-[#eef6ff]">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-40 right-0 h-96 w-96 rounded-full bg-wedding-rose/20 blur-3xl"
        />
        <div className="relative mx-auto flex min-h-screen w-full max-w-lg items-center px-4 py-12">
          <GlassCard depth="near" blur="xl" className="w-full px-6 py-8 sm:px-10 text-center">
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100">
              <svg className="h-8 w-8 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="text-2xl font-semibold text-wedding-navy">Password Reset Successful!</h1>
            <p className="mt-4 text-wedding-navy/70">
              Your password has been changed successfully.
            </p>
            <p className="mt-2 text-sm text-wedding-navy/60">
              Redirecting you to the login page...
            </p>

            <div className="mt-8">
              <Link
                href={PUBLIC_LOGIN_PATH}
                className="inline-block rounded-xl bg-wedding-rose px-6 py-3 text-white font-medium hover:bg-wedding-rose/90 transition"
              >
                Go to Login
              </Link>
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
      <div className="relative mx-auto flex min-h-screen w-full max-w-lg items-center px-4 py-12">
        <GlassCard depth="near" blur="xl" className="w-full px-6 py-8 sm:px-10">
          <div className="text-center">
            <h1 className="text-3xl font-semibold text-wedding-navy">Set a new password</h1>
            {maskedEmail && (
              <p className="mt-3 text-sm text-wedding-navy/70">
                Resetting password for <span className="font-medium text-wedding-navy">{maskedEmail}</span>
              </p>
            )}
          </div>

          <form onSubmit={handleSubmit} className="mt-8 space-y-5">
            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium text-wedding-navy">New password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(event) => handlePasswordChange(event.target.value)}
                  className="w-full rounded-xl border border-wedding-gold/20 bg-white/85 px-4 py-3 pr-12 text-wedding-navy focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/20"
                  placeholder="Create a strong password"
                  autoComplete="new-password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((previous) => !previous)}
                  className="absolute inset-y-0 right-0 flex items-center px-4 text-wedding-navy/50 hover:text-wedding-navy"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            <div className="rounded-xl border border-wedding-gold/15 bg-white/70 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-wedding-navy/60">
                Password requirements
              </p>
              <ul className="mt-3 space-y-2 text-sm text-wedding-navy/70">
                <li className={passwordValidation.minLength ? 'text-emerald-700' : undefined}>At least 8 characters</li>
                <li className={passwordValidation.hasUppercase ? 'text-emerald-700' : undefined}>One uppercase letter</li>
                <li className={passwordValidation.hasLowercase ? 'text-emerald-700' : undefined}>One lowercase letter</li>
                <li className={passwordValidation.hasNumber ? 'text-emerald-700' : undefined}>One number</li>
                <li className={passwordValidation.hasSpecial ? 'text-emerald-700' : undefined}>One special character</li>
              </ul>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-wedding-navy">Confirm password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                className="w-full rounded-xl border border-wedding-gold/20 bg-white/85 px-4 py-3 text-wedding-navy focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/20"
                placeholder="Re-enter your new password"
                autoComplete="new-password"
                required
              />
              {confirmPassword && password !== confirmPassword && (
                <p className="text-sm text-red-600">Passwords do not match.</p>
              )}
            </div>

            <Button type="submit" disabled={submitting} className="w-full justify-center">
              {submitting ? 'Resetting password...' : 'Reset password'}
            </Button>
          </form>
        </GlassCard>
      </div>
    </div>
  );
}
