'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { getApiBaseUrl } from '@/utils/env';
import { ArrowLeft, ArrowRight, CheckCircle2, Loader2, ShieldCheck } from 'lucide-react';

import { VendorAuthShell, VendorAuthShowcase } from '../components/VendorAuthShell';
import {
  vendorGhostButtonClass,
  vendorInputClass,
  vendorInsetClass,
  vendorPrimaryButtonClass,
  vendorSecondaryButtonClass,
} from '../components/styles';

const API_BASE = getApiBaseUrl();

const vendorSignupHighlights = [
  {
    label: 'Apply once, build inside the platform',
    description: 'Join the same ad workspace used for campaign creative, billing, vendor leads, and profile management.',
  },
  {
    label: 'No pasted media setup',
    description: 'Once approved, your logo and creative assets live in one shared media flow instead of scattered URLs and manual copy-paste.',
  },
];

const vendorSignupStats = [
  { value: '1-2 days', caption: 'Typical review window before approval email' },
  { value: 'Shared', caption: 'Visual system and media workflow with the rest of the platform' },
];

const successHighlights = [
  {
    label: 'Review comes first',
    description: 'Your application is queued for manual approval so vendor listings and ad access stay curated.',
  },
  {
    label: 'Then you enter the workspace',
    description: 'After approval, you receive a temporary password and move straight into the vendor portal used for campaigns and profile setup.',
  },
];

const successStats = [
  { value: 'Queued', caption: 'Application is now waiting on review' },
  { value: 'Next', caption: 'Approval email includes your temporary password' },
];

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
  const [step, setStep] = useState<'form' | 'success'>('form');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

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
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Signup failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (step === 'success') {
    return (
      <VendorAuthShell
        showcase={(
          <VendorAuthShowcase
            eyebrow="Vendor application"
            title="You are in review. The workspace unlocks after approval."
            description="Your details are now with the team. Once approved, you will receive a temporary password and land in the same vendor workspace used for campaign creative, logo management, and billing."
            highlights={successHighlights}
            stats={successStats}
          />
        )}
      >
        <div className="flex h-full flex-col justify-center">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-wedding-rose/70">Application received</p>
              <h2 className="mt-2 text-[1.75rem] font-semibold leading-tight text-wedding-navy dark:text-white">
                Thank you for applying
              </h2>
              <p className="mt-2 text-[0.95rem] leading-relaxed text-wedding-navy/70 dark:text-slate-300">
                We will review your business details and email a temporary password once the account is approved. Most applications are handled within 1-2 business days.
              </p>
            </div>
            <div className="hidden rounded-full bg-white/55 p-4 text-wedding-sage shadow-sm backdrop-blur sm:block dark:bg-slate-800/65">
              <CheckCircle2 className="h-8 w-8" />
            </div>
          </div>

          <div className={`${vendorInsetClass} mt-8 space-y-4 p-5`}>
            <div className="flex items-center gap-2 text-sm font-medium text-wedding-navy dark:text-slate-200">
              <ShieldCheck className="h-4 w-4 text-wedding-sage" />
              What happens next
            </div>
            <ol className="space-y-2 text-sm leading-relaxed text-wedding-navy/75 dark:text-slate-300">
              <li>1. We review your application details and category fit.</li>
              <li>2. You receive a temporary password by email after approval.</li>
              <li>3. You sign in, change that password once, and complete your profile.</li>
              <li>4. You can then launch campaigns and manage creative from the vendor portal.</li>
            </ol>
          </div>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link href="/portal/ads" className={`${vendorPrimaryButtonClass} w-full sm:flex-1`}>
              Go to Vendor Portal Login
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link href="/vendors" className={`${vendorSecondaryButtonClass} w-full sm:w-auto`}>
              Back to vendor directory
            </Link>
          </div>
        </div>
      </VendorAuthShell>
    );
  }

  return (
    <VendorAuthShell
      showcase={(
        <VendorAuthShowcase
          eyebrow="Vendor registration"
          title="Apply once, then manage campaigns inside the same polished workspace."
          description="Register your business with The Special Wedding and move into the vendor ads portal after approval, using the same design language and media workflow as the rest of the platform."
          highlights={vendorSignupHighlights}
          stats={vendorSignupStats}
        />
      )}
    >
      <div className="flex h-full flex-col justify-center">
        <div className="flex items-start justify-between gap-4">
          <div>
            <Link
              href="/vendors"
              className={`${vendorGhostButtonClass} -ml-4 mb-4 w-fit px-4 py-2 text-wedding-navy/70 dark:text-slate-300`}
            >
              <ArrowLeft className="h-4 w-4" />
              Back to vendor directory
            </Link>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-wedding-rose/70">Vendor portal</p>
            <h2 className="mt-2 text-[1.75rem] font-semibold leading-tight text-wedding-navy dark:text-white">
              Register your business
            </h2>
            <p className="mt-2 text-[0.95rem] leading-relaxed text-wedding-navy/70 dark:text-slate-300">
              Join The Special Wedding and advertise your services to planners without managing a separate off-brand account flow.
            </p>
          </div>
          <div className="hidden rounded-full bg-white/55 p-4 text-wedding-rose shadow-sm backdrop-blur sm:block dark:bg-slate-800/65">
            <ShieldCheck className="h-8 w-8" />
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-8 space-y-5" noValidate>
          {error ? (
            <div className="rounded-2xl border border-red-200/70 bg-red-50/80 px-4 py-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
              {error}
            </div>
          ) : null}

          <div className={`${vendorInsetClass} space-y-5 p-5`}>
            <div className="space-y-2">
              <label htmlFor="vendor-signup-email" className="text-sm font-medium text-wedding-navy dark:text-slate-200">
                Email address <span className="text-red-500">*</span>
              </label>
              <input
                id="vendor-signup-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@yourbusiness.com"
                required
                autoComplete="email"
                className={vendorInputClass}
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="vendor-signup-business-name" className="text-sm font-medium text-wedding-navy dark:text-slate-200">
                Business name <span className="text-red-500">*</span>
              </label>
              <input
                id="vendor-signup-business-name"
                type="text"
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                placeholder="Your Business Name"
                required
                autoComplete="organization"
                className={vendorInputClass}
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="vendor-signup-category" className="text-sm font-medium text-wedding-navy dark:text-slate-200">
                Service category
              </label>
              <select
                id="vendor-signup-category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className={vendorInputClass}
              >
                <option value="">Select a category...</option>
                {VENDOR_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {formatCategory(cat)}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <label htmlFor="vendor-signup-location" className="text-sm font-medium text-wedding-navy dark:text-slate-200">
                Location / service area
              </label>
              <input
                id="vendor-signup-location"
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. New York, NY"
                autoComplete="address-level2"
                className={vendorInputClass}
              />
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <div className="space-y-2">
                <label htmlFor="vendor-signup-phone" className="text-sm font-medium text-wedding-navy dark:text-slate-200">
                  Phone
                </label>
                <input
                  id="vendor-signup-phone"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+1-555-0123"
                  autoComplete="tel"
                  className={vendorInputClass}
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="vendor-signup-website" className="text-sm font-medium text-wedding-navy dark:text-slate-200">
                  Website
                </label>
                <input
                  id="vendor-signup-website"
                  type="url"
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                  placeholder="https://..."
                  autoComplete="url"
                  className={vendorInputClass}
                />
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              type="submit"
              disabled={loading}
              className={`${vendorPrimaryButtonClass} w-full sm:flex-1`}
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  Submit Application
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>

            <Link href="/portal/ads" className={`${vendorSecondaryButtonClass} w-full sm:w-auto`}>
              Sign in instead
            </Link>
          </div>
        </form>
      </div>
    </VendorAuthShell>
  );
}
