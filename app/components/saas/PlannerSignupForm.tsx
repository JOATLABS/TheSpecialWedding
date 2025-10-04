'use client';

import React, { useState } from 'react';
import Link from 'next/link';

import { SocialAuthButtons } from '../auth/SocialAuthButtons';
import { ThemeConfig } from '@/types/wedding';

interface PlannerSignupFormProps {
  theme: ThemeConfig;
  selectedPlanId?: string;
  selectedPlanLabel?: string;
  onRegistered?: () => void;
  onDismiss?: () => void;
  variant?: 'panel' | 'modal';
}

type SignupFormData = {
  email: string;
  password: string;
  confirmPassword: string;
  companyName: string;
  firstName: string;
  lastName: string;
  acceptTerms: boolean;
};

export function PlannerSignupForm({
  theme,
  selectedPlanId,
  selectedPlanLabel,
  onRegistered,
  onDismiss,
  variant = 'panel',
}: PlannerSignupFormProps) {
  const [formData, setFormData] = useState<SignupFormData>({
    email: '',
    password: '',
    confirmPassword: '',
    companyName: '',
    firstName: '',
    lastName: '',
    acceptTerms: false,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState<'idle' | 'success'>('idle');

  const spacingClass = variant === 'panel' ? 'space-y-4' : 'space-y-6';

  const handleInputChange = (field: keyof SignupFormData, value: string | boolean) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setError('');
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }

    if (!formData.acceptTerms) {
      setError('Please accept the terms and conditions');
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/public/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: formData.email,
          password: formData.password,
          first_name: formData.firstName,
          last_name: formData.lastName,
          company_name: formData.companyName,
          selected_plan_id: selectedPlanId,
          role: 'wedding_planner',
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        setError(errorData.detail || 'Registration failed');
        return;
      }

      setStatus('success');
      onRegistered?.();
    } catch (submitError) {
      setError('Registration failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (status === 'success') {
    return (
      <div className="space-y-4 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
          <svg aria-hidden="true" className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <div className="space-y-2">
          <h3 className="text-lg font-semibold text-gray-900">Check your inbox</h3>
          <p className="text-sm text-gray-600">
            We&apos;ve emailed a verification link so you can activate your planner workspace before signing in.
          </p>
        </div>
        <div className="space-y-3">
          <button
            type="button"
            className="w-full rounded-lg px-4 py-2 text-sm font-semibold text-white shadow-md transition hover:opacity-95"
            style={{ backgroundColor: theme.primary_color }}
            onClick={() => {
              if (typeof window !== 'undefined') {
                window.location.href = '/admin/login';
              }
            }}
          >
            Go to planner login
          </button>
          {onDismiss && (
            <button
              type="button"
              className="w-full rounded-lg border border-gray-200 px-4 py-2 text-sm font-semibold text-gray-700 transition hover:bg-gray-50"
              onClick={onDismiss}
            >
              Continue exploring
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={`text-left ${spacingClass}`}>
      <div className="space-y-3" aria-label="Social registration options">
        <SocialAuthButtons flow="signup" redirectPath="/setup-account" />
        <p className="text-xs text-gray-500">
          We&apos;ll redirect you to verify Google or Apple before returning to finish onboarding.
        </p>
        <div className="flex items-center gap-3">
          <div className="h-px flex-1 bg-gray-200" aria-hidden="true" />
          <span className="text-xs uppercase tracking-[0.3em] text-gray-400">or continue with email</span>
          <div className="h-px flex-1 bg-gray-200" aria-hidden="true" />
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1">
            <label htmlFor="signup-first-name" className="text-sm font-medium text-gray-700">
              First name
            </label>
            <input
              id="signup-first-name"
              type="text"
              value={formData.firstName}
              onChange={(event) => handleInputChange('firstName', event.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm shadow-sm focus:border-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-200"
              required
              autoComplete="given-name"
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="signup-last-name" className="text-sm font-medium text-gray-700">
              Last name
            </label>
            <input
              id="signup-last-name"
              type="text"
              value={formData.lastName}
              onChange={(event) => handleInputChange('lastName', event.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm shadow-sm focus:border-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-200"
              required
              autoComplete="family-name"
            />
          </div>
        </div>

        <div className="space-y-1">
          <label htmlFor="signup-company" className="text-sm font-medium text-gray-700">
            Company name
          </label>
          <input
            id="signup-company"
            type="text"
            value={formData.companyName}
            onChange={(event) => handleInputChange('companyName', event.target.value)}
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm shadow-sm focus:border-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-200"
            required
            autoComplete="organization"
          />
        </div>

        <div className="space-y-1">
          <label htmlFor="signup-email" className="text-sm font-medium text-gray-700">
            Work email
          </label>
          <input
            id="signup-email"
            type="email"
            value={formData.email}
            onChange={(event) => handleInputChange('email', event.target.value)}
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm shadow-sm focus:border-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-200"
            required
            autoComplete="email"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1">
            <label htmlFor="signup-password" className="text-sm font-medium text-gray-700">
              Password
            </label>
            <input
              id="signup-password"
              type="password"
              value={formData.password}
              onChange={(event) => handleInputChange('password', event.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm shadow-sm focus:border-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-200"
              required
              autoComplete="new-password"
              minLength={8}
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="signup-confirm" className="text-sm font-medium text-gray-700">
              Confirm password
            </label>
            <input
              id="signup-confirm"
              type="password"
              value={formData.confirmPassword}
              onChange={(event) => handleInputChange('confirmPassword', event.target.value)}
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm shadow-sm focus:border-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-200"
              required
              autoComplete="new-password"
              minLength={8}
            />
          </div>
        </div>

        <div className="flex items-start gap-3 rounded-lg bg-gray-50 px-3 py-2">
          <input
            id="signup-terms"
            type="checkbox"
            checked={formData.acceptTerms}
            onChange={(event) => handleInputChange('acceptTerms', event.target.checked)}
            className="mt-1 h-4 w-4 rounded border-gray-300 text-gray-700 focus:ring-2 focus:ring-gray-300"
            required
          />
          <label htmlFor="signup-terms" className="text-xs text-gray-600">
            I agree to the Special Wedding <Link href="/legal/terms" className="underline">Terms</Link> and{' '}
            <Link href="/legal/privacy" className="underline">Privacy Policy</Link>.
          </label>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded-lg px-4 py-2 text-sm font-semibold text-white shadow-md transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60"
          style={{ backgroundColor: theme.primary_color }}
        >
          {isSubmitting ? 'Creating account…' : 'Create my planner workspace'}
        </button>

        {selectedPlanId && (
          <p className="text-xs text-gray-500">
            Selected plan: <span className="font-medium">{selectedPlanLabel ?? selectedPlanId}</span>
          </p>
        )}
      </form>
    </div>
  );
}

export default PlannerSignupForm;
