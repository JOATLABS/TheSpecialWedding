'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import { GlassCard } from '../components/ui/GlassCard';
import { getApiBaseUrl } from '@/utils/env';

interface InvitationDetails {
  email: string;
  role: string;
  company_name?: string;
  expires_at: string;
}

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

export default function SetupAccountPageClient({ initialToken }: { initialToken: string | null }) {
  const router = useRouter();
  const token = initialToken;

  const [invitationDetails, setInvitationDetails] = useState<InvitationDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    password: '',
    confirmPassword: '',
  });
  const [passwordValidation, setPasswordValidation] = useState<PasswordValidation>({
    minLength: false,
    hasUppercase: false,
    hasLowercase: false,
    hasNumber: false,
    hasSpecial: false,
  });

  const handlePasswordChange = (password: string) => {
    setFormData((previous) => ({ ...previous, password }));
    setPasswordValidation(validatePassword(password));
  };

  const validateToken = useCallback(async (invitationToken: string) => {
    const baseUrl = getApiBaseUrl();
    const response = await fetch(`${baseUrl}/setup/validate-token/${invitationToken}`);

    if (!response.ok) {
      throw new Error('Invalid or expired invitation link');
    }

    return (await response.json()) as InvitationDetails;
  }, []);

  useEffect(() => {
    if (!token) {
      setInvitationDetails(null);
      setError('Invalid invitation link');
      setLoading(false);
      return;
    }

    let isActive = true;

    const runValidation = async () => {
      setLoading(true);
      try {
        const details = await validateToken(token);
        if (!isActive) {
          return;
        }
        setInvitationDetails(details);
        setError('');
      } catch (err) {
        if (!isActive) {
          return;
        }
        setInvitationDetails(null);
        if (err instanceof Error && err.message === 'Invalid or expired invitation link') {
          setError(err.message);
        } else {
          setError('Failed to validate invitation link');
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

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!formData.firstName.trim()) {
      setError('First name is required');
      return;
    }
    if (!formData.lastName.trim()) {
      setError('Last name is required');
      return;
    }

    if (!isPasswordValid(passwordValidation)) {
      setError('Password must meet all requirements listed below');
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/setup/complete`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          token,
          password: formData.password,
          confirm_password: formData.confirmPassword,
          first_name: formData.firstName.trim(),
          last_name: formData.lastName.trim(),
        }),
      });

      if (response.ok) {
        router.push('/admin/login?message=Account setup completed! Please log in with your credentials.');
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to complete account setup');
      }
    } catch {
      setError('Failed to complete account setup');
    } finally {
      setIsSubmitting(false);
    }
  };

  const getRoleDisplayName = (role: string) => {
    switch (role) {
      case 'wedding_planner':
        return 'Wedding Planner';
      case 'vendor':
        return 'Vendor';
      default:
        return role.replace('_', ' ').replace(/\b\w/g, (value) => value.toUpperCase());
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-emerald-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4" />
          <p className="text-gray-600">Validating invitation...</p>
        </div>
      </div>
    );
  }

  if (error && !invitationDetails) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-emerald-50 flex items-center justify-center">
        <GlassCard depth="mid" className="max-w-md mx-auto p-8 text-center">
          <div className="text-red-500 mb-4">
            <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.464 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Invalid Invitation</h1>
          <p className="text-gray-600 mb-6">{error}</p>
          <button
            onClick={() => router.push('/admin/login')}
            className="bg-indigo-600 text-white px-6 py-2 rounded-lg hover:bg-indigo-700 transition-colors"
          >
            Go to Login
          </button>
        </GlassCard>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-emerald-50 flex items-center justify-center p-4">
      <GlassCard depth="mid" className="max-w-md mx-auto p-8">
        <div className="text-center mb-8">
          <div className="text-indigo-600 mb-4">
            <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Complete Your Account Setup</h1>
          <p className="text-gray-600">Welcome to Special Wedding Platform!</p>
        </div>

        {invitationDetails && (
          <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4 mb-6">
            <h3 className="font-semibold text-indigo-900 mb-2">Account Details</h3>
            <div className="space-y-1 text-sm">
              <p><span className="font-medium">Email:</span> {invitationDetails.email}</p>
              <p><span className="font-medium">Role:</span> {getRoleDisplayName(invitationDetails.role)}</p>
              {invitationDetails.company_name && (
                <p><span className="font-medium">Company:</span> {invitationDetails.company_name}</p>
              )}
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="firstName" className="block text-sm font-medium text-gray-700 mb-2">
                First Name
              </label>
              <input
                type="text"
                id="firstName"
                value={formData.firstName}
                onChange={(event) => setFormData({ ...formData, firstName: event.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="Enter your first name"
                required
              />
            </div>
            <div>
              <label htmlFor="lastName" className="block text-sm font-medium text-gray-700 mb-2">
                Last Name
              </label>
              <input
                type="text"
                id="lastName"
                value={formData.lastName}
                onChange={(event) => setFormData({ ...formData, lastName: event.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="Enter your last name"
                required
              />
            </div>
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
              Password
            </label>
            <input
              type="password"
              id="password"
              value={formData.password}
              onChange={(event) => handlePasswordChange(event.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              placeholder="Enter your password"
              required
            />
            <div className="mt-3 space-y-1.5">
              <p className="text-xs font-medium text-gray-600 mb-2">Password requirements:</p>
              <PasswordRequirement met={passwordValidation.minLength} text="At least 8 characters" />
              <PasswordRequirement met={passwordValidation.hasUppercase} text="One uppercase letter (A-Z)" />
              <PasswordRequirement met={passwordValidation.hasLowercase} text="One lowercase letter (a-z)" />
              <PasswordRequirement met={passwordValidation.hasNumber} text="One number (0-9)" />
              <PasswordRequirement met={passwordValidation.hasSpecial} text="One special character (!@#$%^&*)" />
            </div>
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-2">
              Confirm Password
            </label>
            <input
              type="password"
              id="confirmPassword"
              value={formData.confirmPassword}
              onChange={(event) => setFormData({ ...formData, confirmPassword: event.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              placeholder="Confirm your password"
              required
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-indigo-600 text-white py-3 px-4 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
          >
            {isSubmitting ? 'Setting up account...' : 'Complete Setup'}
          </button>
        </form>

        <div className="mt-6 pt-6 border-t border-gray-200 text-center">
          <p className="text-sm text-gray-500">
            Already have an account?{' '}
            <button
              onClick={() => router.push('/admin/login')}
              className="text-indigo-600 hover:text-indigo-700 font-medium"
            >
              Sign in here
            </button>
          </p>
        </div>
      </GlassCard>
    </div>
  );
}

function PasswordRequirement({ met, text }: { met: boolean; text: string }) {
  return (
    <div className={`flex items-center gap-2 text-xs ${met ? 'text-green-600' : 'text-gray-400'}`}>
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
