'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { getApiBaseUrl } from '@/utils/env';
import { Building2, ArrowLeft, CheckCircle2, Loader2 } from 'lucide-react';

const API_BASE = getApiBaseUrl();

// Vendor categories matching the existing VendorCategory enum
const VENDOR_CATEGORIES = [
  'photographer',
  'videographer',
  'florist',
  'caterer',
  'baker',
  'dj',
  'band',
  'wedding_planner',
  'decorator',
  'venue',
  'transportation',
  'officiant',
  'hair_stylist',
  'makeup_artist',
  'jeweler',
  'stationer',
  'rental',
  'photo_booth',
  'lighting',
  'other',
];

function formatCategory(cat: string) {
  return cat
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function VendorSignupPage() {
  const router = useRouter();
  const [step, setStep] = useState<'form' | 'success'>('form');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Form fields
  const [email, setEmail] = useState('');
  const [businessName, setBusinessName] = useState('');
  const [category, setCategory] = useState('');
  const [location, setLocation] = useState('');
  const [phone, setPhone] = useState('');
  const [website, setWebsite] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email.trim() || !businessName.trim()) {
      setError('Email and business name are required.');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/vendors/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          business_name: businessName.trim(),
          category,
          location: location.trim(),
          phone: phone.trim(),
          website: website.trim(),
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || 'Signup failed. Please try again.');
      }

      setStep('success');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ─── Success Screen ──────────────────────────────────────────
  if (step === 'success') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
        <div className="w-full max-w-md text-center">
          <div className="bg-slate-800/80 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-10 shadow-2xl">
            <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-emerald-500/20 flex items-center justify-center">
              <CheckCircle2 className="w-8 h-8 text-emerald-400" />
            </div>
            <h1 className="text-2xl font-bold text-white mb-3">Application Received!</h1>
            <p className="text-slate-300 text-sm leading-relaxed mb-6">
              Thank you for signing up. Our team will review your application
              and you&apos;ll receive an email with your temporary password once
              approved. This usually takes 1–2 business days.
            </p>
            <div className="bg-slate-700/50 rounded-lg p-4 text-left mb-6">
              <p className="text-xs text-slate-400 mb-2">What happens next?</p>
              <ol className="text-sm text-slate-300 space-y-1.5 list-decimal list-inside">
                <li>We review your application</li>
                <li>You receive a temporary password via email</li>
                <li>Sign in and change your password</li>
                <li>Complete your business profile</li>
                <li>Create your first advertising campaign</li>
              </ol>
            </div>
            <Link
              href="/portal/ads"
              className="inline-block w-full text-center py-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition-colors"
            >
              Go to Vendor Portal Login
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ─── Signup Form ─────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="text-center mb-8">
          <Link
            href="/vendors"
            className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition mb-6"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Vendor Directory
          </Link>
          <div className="w-14 h-14 mx-auto mb-4 rounded-xl bg-indigo-600/20 flex items-center justify-center">
            <Building2 className="w-7 h-7 text-indigo-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">Vendor Registration</h1>
          <p className="text-slate-400 text-sm mt-2">
            Join The Special Wedding and advertise your services to wedding planners.
          </p>
        </div>

        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="bg-slate-800/80 backdrop-blur-sm rounded-2xl border border-slate-700/50 p-8 shadow-2xl space-y-5"
        >
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          {/* Email */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">
              Email Address <span className="text-red-400">*</span>
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@yourbusiness.com"
              required
              className="w-full px-4 py-3 rounded-lg bg-slate-700/50 border border-slate-600 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
            />
          </div>

          {/* Business Name */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">
              Business Name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={businessName}
              onChange={(e) => setBusinessName(e.target.value)}
              placeholder="Your Business Name"
              required
              className="w-full px-4 py-3 rounded-lg bg-slate-700/50 border border-slate-600 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
            />
          </div>

          {/* Category */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">
              Service Category
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-4 py-3 rounded-lg bg-slate-700/50 border border-slate-600 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
            >
              <option value="">Select a category...</option>
              {VENDOR_CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {formatCategory(cat)}
                </option>
              ))}
            </select>
          </div>

          {/* Location */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">
              Location / Service Area
            </label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. New York, NY"
              className="w-full px-4 py-3 rounded-lg bg-slate-700/50 border border-slate-600 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
            />
          </div>

          {/* Phone + Website (side by side) */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">
                Phone
              </label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+1-555-0123"
                className="w-full px-4 py-3 rounded-lg bg-slate-700/50 border border-slate-600 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">
                Website
              </label>
              <input
                type="url"
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                placeholder="https://..."
                className="w-full px-4 py-3 rounded-lg bg-slate-700/50 border border-slate-600 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
              />
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm transition-colors flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Submitting...
              </>
            ) : (
              'Submit Application'
            )}
          </button>

          <p className="text-xs text-slate-500 text-center">
            Already have an account?{' '}
            <Link href="/portal/ads" className="text-indigo-400 hover:text-indigo-300">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
