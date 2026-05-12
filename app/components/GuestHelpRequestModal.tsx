'use client';

import { FormEvent, useState } from 'react';
import { CheckCircleIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { getApiBaseUrl } from '@/utils/env';

interface GuestHelpRequestModalProps {
  isOpen: boolean;
  onClose: () => void;
  slug: string;
  coupleName: string;
  themeConfig?: {
    primary_color?: string;
    secondary_color?: string;
    accent_color?: string;
  };
}

export default function GuestHelpRequestModal({
  isOpen,
  onClose,
  slug,
  coupleName,
  themeConfig,
}: GuestHelpRequestModalProps) {
  const apiBaseUrl = getApiBaseUrl();
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [relationship, setRelationship] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const primaryColor = themeConfig?.primary_color || '#1e3a5f';
  const secondaryColor = themeConfig?.secondary_color || '#d4af37';
  const accentColor = themeConfig?.accent_color || '#c8847e';

  if (!isOpen) {
    return null;
  }

  const resetAndClose = () => {
    setFullName('');
    setPhone('');
    setRelationship('');
    setError('');
    setSubmitted(false);
    onClose();
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');

    if (fullName.trim().length < 2) {
      setError('Please enter your full name.');
      return;
    }

    const digits = phone.replace(/\D/g, '');
    if (digits.length < 10) {
      setError('Please enter a valid phone number.');
      return;
    }

    if (relationship.trim().length < 2) {
      setError('Please enter your relationship to the couple.');
      return;
    }

    try {
      setLoading(true);
      const response = await fetch(`${apiBaseUrl}/guests/help-request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          slug,
          full_name: fullName.trim(),
          phone: phone.trim(),
          relationship_to_couple: relationship.trim(),
        }),
      });

      if (!response.ok) {
        setError('We could not send your help request. Please try again.');
        return;
      }

      setSubmitted(true);
    } catch {
      setError('Network error. Please check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" role="dialog" aria-modal="true" aria-labelledby="guest-help-title">
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={resetAndClose} />
      <div className="relative flex min-h-full items-center justify-center p-4 text-center">
        <div className="relative w-full max-w-md transform overflow-hidden rounded-3xl bg-gradient-to-b from-white to-gray-50 dark:from-slate-800 dark:to-slate-900 p-8 text-left align-middle shadow-2xl transition-all border border-gray-100 dark:border-slate-700">
          <div
            className="absolute top-0 left-0 right-0 h-1 rounded-t-3xl"
            style={{ background: `linear-gradient(90deg, ${primaryColor}, ${secondaryColor}, ${accentColor})` }}
          />

          <div className="flex justify-between items-center mb-6">
            <div>
              <h3 id="guest-help-title" className="text-2xl font-light tracking-wide" style={{ color: primaryColor }}>
                {submitted ? 'Text Sent' : 'Get Help'}
              </h3>
              <div className="w-12 h-0.5 mt-2" style={{ backgroundColor: secondaryColor }} />
            </div>
            <button
              type="button"
              onClick={resetAndClose}
              className="rounded-full p-2 hover:bg-gray-100 dark:hover:bg-slate-700 transition-all duration-200"
            >
              <XMarkIcon className="h-5 w-5 text-gray-400" />
            </button>
          </div>

          {submitted ? (
            <div className="text-center py-8">
              <div
                className="w-20 h-20 mx-auto mb-6 rounded-full flex items-center justify-center"
                style={{ backgroundColor: `${accentColor}15` }}
              >
                <CheckCircleIcon className="h-10 w-10" style={{ color: accentColor }} />
              </div>
              <p className="text-gray-700 dark:text-gray-200 mb-3 font-light text-lg">
                Please check your text messages.
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-8 font-light">
                Reply to the text with your question for {coupleName}&apos;s planner.
              </p>
              <button
                type="button"
                onClick={resetAndClose}
                className="px-8 py-3 rounded-full text-sm font-medium text-white transition-all duration-300 hover:shadow-lg hover:scale-105"
                style={{ backgroundColor: primaryColor }}
              >
                Close
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <p className="text-gray-600 dark:text-gray-300 mb-6 font-light leading-relaxed">
                Tell us who you are so the wedding planner can help from the message inbox.
              </p>

              <div className="space-y-5">
                <div>
                  <label htmlFor="guest-help-full-name" className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wider">
                    Full Name
                  </label>
                  <input
                    id="guest-help-full-name"
                    value={fullName}
                    onChange={(event) => setFullName(event.target.value)}
                    className="w-full px-5 py-4 rounded-xl border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700/50 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-2 transition-all duration-200"
                    disabled={loading}
                  />
                </div>

                <div>
                  <label htmlFor="guest-help-phone" className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wider">
                    Phone Number
                  </label>
                  <input
                    id="guest-help-phone"
                    type="tel"
                    value={phone}
                    onChange={(event) => setPhone(event.target.value)}
                    placeholder="(555) 123-4567"
                    className="w-full px-5 py-4 rounded-xl border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700/50 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-2 transition-all duration-200"
                    disabled={loading}
                  />
                </div>

                <div>
                  <label htmlFor="guest-help-relationship" className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wider">
                    Relationship to the Couple
                  </label>
                  <input
                    id="guest-help-relationship"
                    value={relationship}
                    onChange={(event) => setRelationship(event.target.value)}
                    placeholder="Friend, cousin, coworker..."
                    className="w-full px-5 py-4 rounded-xl border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700/50 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-2 transition-all duration-200"
                    disabled={loading}
                  />
                </div>
              </div>

              {error && (
                <div className="mt-5 p-4 bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-800/50 rounded-xl">
                  <p className="text-sm text-red-600 dark:text-red-400 font-light">{error}</p>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="mt-6 w-full py-4 rounded-xl text-sm font-medium text-white transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]"
                style={{ background: `linear-gradient(135deg, ${primaryColor} 0%, ${accentColor} 100%)` }}
              >
                {loading ? 'Sending...' : 'Text Me'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
