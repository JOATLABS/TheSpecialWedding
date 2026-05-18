'use client';

import React, { useEffect, useState } from 'react';

import { ThemeConfig } from '@/types/wedding';
import { resolveApiUrl } from './apiClient';

interface ContactSalesModalProps {
  isOpen: boolean;
  onClose: () => void;
  theme: ThemeConfig;
}

interface ContactFormState {
  name: string;
  email: string;
  company: string;
  phone: string;
  message: string;
}

const INITIAL_FORM: ContactFormState = {
  name: '',
  email: '',
  company: '',
  phone: '',
  message: '',
};

export const ContactSalesModal: React.FC<ContactSalesModalProps> = ({ isOpen, onClose, theme }) => {
  const [formState, setFormState] = useState<ContactFormState>(INITIAL_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (isOpen) {
      setError('');
      setSuccess('');
      setFormState(INITIAL_FORM);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  const handleChange = (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = event.target;
    setFormState((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setSubmitting(true);
    setError('');
    setSuccess('');

    try {
      const endpoint = resolveApiUrl('/saas/contact');
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: formState.name.trim(),
          email: formState.email.trim(),
          company: formState.company.trim() || undefined,
          phone: formState.phone.trim() || undefined,
          message: formState.message.trim(),
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || 'We could not submit your request. Please try again.');
      }

      setSuccess('Thanks! Our team will reach out shortly.');
      setFormState(INITIAL_FORM);
    } catch (submissionError) {
      const message =
        submissionError instanceof Error ? submissionError.message : 'We could not submit your request. Please try again.';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 px-4 py-6 backdrop-blur-sm">
      <div className="relative w-full max-w-lg">
        <div
          className="absolute inset-0 -z-10 rounded-[2.8rem] bg-gradient-to-br from-white/80 via-white/60 to-white/30 shadow-[0_45px_140px_-60px_rgba(15,23,42,0.7)]"
          style={{ border: `1px solid ${theme.primary_color}1a` }}
        />
        <div className="relative overflow-hidden rounded-[2.8rem] border border-white/40 bg-white/80 p-6 shadow-2xl backdrop-blur-2xl sm:p-8">
          <button
            type="button"
            onClick={onClose}
            className="absolute right-4 top-4 rounded-full bg-black/5 p-2 text-slate-500 transition hover:bg-black/10 hover:text-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700"
            aria-label="Close contact sales dialog"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>

          <div className="mb-6 space-y-3 text-left">
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">Talk to sales</p>
            <h2 className="text-2xl font-semibold text-slate-900 sm:text-3xl">Let&apos;s plan growth together</h2>
            <p className="text-sm text-slate-600">
              Share a few details and we&apos;ll craft a tailored walkthrough, note any onboarding help you need, and keep you
              updated via email.
            </p>
          </div>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
                Full name
                <input
                  type="text"
                  name="name"
                  value={formState.name}
                  onChange={handleChange}
                  required
                  autoFocus
                  className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-2 text-sm text-slate-900 shadow-sm transition focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
                  placeholder="Alex Planner"
                />
              </label>
              <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
                Work email
                <input
                  type="email"
                  name="email"
                  value={formState.email}
                  onChange={handleChange}
                  required
                  className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-2 text-sm text-slate-900 shadow-sm transition focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
                  placeholder="you@studio.com"
                />
              </label>
              <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
                Studio or company
                <input
                  type="text"
                  name="company"
                  value={formState.company}
                  onChange={handleChange}
                  className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-2 text-sm text-slate-900 shadow-sm transition focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
                  placeholder="Special Moments Co."
                />
              </label>
              <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
                Phone (optional)
                <input
                  type="tel"
                  name="phone"
                  value={formState.phone}
                  onChange={handleChange}
                  className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-2 text-sm text-slate-900 shadow-sm transition focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
                  placeholder="+1 (555) 123-4567"
                />
              </label>
            </div>

            <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
              How can we help?
              <textarea
                name="message"
                value={formState.message}
                onChange={handleChange}
                required
                rows={4}
                className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-3 text-sm text-slate-900 shadow-sm transition focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
                placeholder="Share a bit about your planning workflows, your client volume, or the automations you need."
              />
            </label>

            {error && (
              <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            {success && (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                {success}
              </div>
            )}

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs text-slate-500">
                We&apos;ll respond within one business day. You&apos;ll receive a confirmation email and a notification inside the
                admin portal.
              </p>
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center justify-center rounded-full px-6 py-2 text-sm font-semibold text-white shadow-lg transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
                style={{ backgroundColor: submitting ? `${theme.primary_color}cc` : theme.primary_color }}
              >
                {submitting ? 'Sending…' : 'Send message'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ContactSalesModal;
