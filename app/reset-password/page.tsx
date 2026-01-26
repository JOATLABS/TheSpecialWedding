'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import React, { FormEvent, Suspense, useCallback, useEffect, useState } from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { GlassCard } from '@/components/ui/GlassCard';
import { Button } from '@/components/ui/Button';

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

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gradient-to-br from-[#f8f5f2] via-[#f2ecff] to-[#eef6ff] flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-wedding-rose mx-auto mb-4"></div>
          <p className="text-wedding-navy/70">Loading...</p>
        </div>
      </div>
    }>
      <ResetPasswordContent />
    </Suspense>
  );
}

function ResetPasswordContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get('token');

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
        if (!isActive) return;
        setTokenValid(true);
        setMaskedEmail(result.email);
        setError('');
      } catch (err) {
        if (!isActive) return;
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

    runValidation();

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
        // Redirect to login after 3 seconds
        setTimeout(() => {
          router.push('/admin/login?message=Password reset successful! Please log in with your new password.');
        }, 3000);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to reset password');
      }
    } catch (err) {
      setError('Failed to reset password. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#f8f5f2] via-[#f2ecff] to-[#eef6ff] flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-wedding-rose mx-auto mb-4"></div>
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
                  href="/admin/login"
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
                href="/admin/login"
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
      <div
        aria-hidden="true"
        className="pointer-events-none absolute bottom-[-6rem] left-[-6rem] h-[22rem] w-[22rem] rounded-full bg-wedding-navy/10 blur-3xl"
      />

      <div className="relative mx-auto flex min-h-screen w-full max-w-lg items-center px-4 py-12">
        <GlassCard depth="near" blur="xl" className="w-full px-6 py-8 sm:px-10">
          <div className="text-center mb-8">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-wedding-rose/10">
              <svg className="h-7 w-7 text-wedding-rose" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <h1 className="text-2xl font-semibold text-wedding-navy">Create New Password</h1>
            <p className="mt-2 text-sm text-wedding-navy/70">
              for <strong>{maskedEmail}</strong>
            </p>
          </div>

          <form className="space-y-5" onSubmit={handleSubmit} noValidate>
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium text-wedding-navy">
                New Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => handlePasswordChange(e.target.value)}
                  required
                  className="w-full rounded-xl border border-white/40 bg-white/60 px-4 py-3 pr-12 text-base text-wedding-navy shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/50"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute inset-y-0 right-0 flex items-center rounded-r-xl px-4 text-sm font-medium text-wedding-navy/80 hover:text-wedding-rose"
                  aria-pressed={showPassword}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>

              {/* Password Requirements Checklist */}
              <div className="mt-3 space-y-1.5">
                <p className="text-xs font-medium text-wedding-navy/60 mb-2">Password requirements:</p>
                <PasswordRequirement met={passwordValidation.minLength} text="At least 8 characters" />
                <PasswordRequirement met={passwordValidation.hasUppercase} text="One uppercase letter (A-Z)" />
                <PasswordRequirement met={passwordValidation.hasLowercase} text="One lowercase letter (a-z)" />
                <PasswordRequirement met={passwordValidation.hasNumber} text="One number (0-9)" />
                <PasswordRequirement met={passwordValidation.hasSpecial} text="One special character (!@#$%^&*)" />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="confirmPassword" className="text-sm font-medium text-wedding-navy">
                Confirm New Password
              </label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className="w-full rounded-xl border border-white/40 bg-white/60 px-4 py-3 text-base text-wedding-navy shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/50"
              />
            </div>

            {error && (
              <p role="alert" className="rounded-lg border border-wedding-rose/40 bg-wedding-rose/10 px-3 py-2 text-sm text-wedding-rose">
                {error}
              </p>
            )}

            <Button
              type="submit"
              disabled={!isPasswordValid(passwordValidation) || submitting}
              className="w-full justify-center rounded-xl py-3 text-base shadow-lg transition disabled:cursor-not-allowed disabled:opacity-60"
              aria-busy={submitting}
            >
              {submitting ? 'Resetting password...' : 'Reset Password'}
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

function PasswordRequirement({ met, text }: { met: boolean; text: string }) {
  return (
    <div className={`flex items-center gap-2 text-xs ${met ? 'text-green-600' : 'text-wedding-navy/40'}`}>
      {met ? (
        <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10" strokeWidth={2} />
        </svg>
      )}
      <span>{text}</span>
    </div>
  );
}
