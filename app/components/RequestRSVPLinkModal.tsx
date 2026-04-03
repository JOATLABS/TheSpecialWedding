'use client';

import { Fragment, useState } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { XMarkIcon, EnvelopeIcon, PhoneIcon, CheckCircleIcon } from '@heroicons/react/24/outline';
import { getApiBaseUrl } from '@/utils/env';

interface RequestRSVPLinkModalProps {
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

export default function RequestRSVPLinkModal({
  isOpen,
  onClose,
  slug,
  coupleName,
  themeConfig
}: RequestRSVPLinkModalProps) {
  const apiBaseUrl = getApiBaseUrl();
  const [contact, setContact] = useState('');
  const [contactType, setContactType] = useState<'phone' | 'email'>('phone');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const primaryColor = themeConfig?.primary_color || '#1e3a5f';
  const secondaryColor = themeConfig?.secondary_color || '#d4af37';
  const accentColor = themeConfig?.accent_color || '#c8847e';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    // Basic validation
    if (!contact.trim()) {
      setError('Please enter your phone number or email.');
      setLoading(false);
      return;
    }

    // Phone validation
    if (contactType === 'phone') {
      const phoneDigits = contact.replace(/\D/g, '');
      if (phoneDigits.length < 10) {
        setError('Please enter a valid phone number.');
        setLoading(false);
        return;
      }
    }

    // Email validation
    if (contactType === 'email') {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(contact)) {
        setError('Please enter a valid email address.');
        setLoading(false);
        return;
      }
    }

    try {
      const response = await fetch(`${apiBaseUrl}/guests/request-rsvp-link`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          slug,
          contact: contact.trim(),
          contact_type: contactType,
        }),
      });

      if (response.ok) {
        setSubmitted(true);
      } else {
        setError('Something went wrong. Please try again.');
      }
    } catch {
      setError('Network error. Please check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  // Auto-detect contact type based on input
  const handleContactChange = (value: string) => {
    setContact(value);
    setError('');

    // Auto-detect type
    if (value.includes('@')) {
      setContactType('email');
    } else if (/^\+?\d/.test(value)) {
      setContactType('phone');
    }
  };

  // Reset state when modal closes
  const handleClose = () => {
    setContact('');
    setContactType('phone');
    setError('');
    setSubmitted(false);
    onClose();
  };

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={handleClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-3xl bg-gradient-to-b from-white to-gray-50 dark:from-slate-800 dark:to-slate-900 p-8 text-left align-middle shadow-2xl transition-all border border-gray-100 dark:border-slate-700">
                {/* Decorative top border */}
                <div
                  className="absolute top-0 left-0 right-0 h-1 rounded-t-3xl"
                  style={{ background: `linear-gradient(90deg, ${primaryColor}, ${secondaryColor}, ${accentColor})` }}
                />

                <Dialog.Title as="div" className="flex justify-between items-center mb-6">
                  <div>
                    <h3
                      className="text-2xl font-light tracking-wide"
                      style={{ color: primaryColor }}
                    >
                      {submitted ? 'Link Sent' : 'Request Your Invitation'}
                    </h3>
                    <div
                      className="w-12 h-0.5 mt-2"
                      style={{ backgroundColor: secondaryColor }}
                    />
                  </div>
                  <button
                    onClick={handleClose}
                    className="rounded-full p-2 hover:bg-gray-100 dark:hover:bg-slate-700 transition-all duration-200"
                  >
                    <XMarkIcon className="h-5 w-5 text-gray-400" />
                  </button>
                </Dialog.Title>

                {submitted ? (
                  // Success state - Luxury design
                  <div className="text-center py-8">
                    <div
                      className="w-20 h-20 mx-auto mb-6 rounded-full flex items-center justify-center"
                      style={{ backgroundColor: `${accentColor}15` }}
                    >
                      <CheckCircleIcon className="h-10 w-10" style={{ color: accentColor }} />
                    </div>
                    <p className="text-gray-700 dark:text-gray-200 mb-3 font-light text-lg">
                      If you are on the guest list, your personal RSVP link will arrive shortly.
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-8 font-light">
                      {contactType === 'phone'
                        ? 'Please check your text messages.'
                        : 'Please check your email inbox and spam folder.'}
                    </p>
                    <button
                      type="button"
                      onClick={handleClose}
                      className="px-8 py-3 rounded-full text-sm font-medium text-white transition-all duration-300 hover:shadow-lg hover:scale-105"
                      style={{ backgroundColor: primaryColor }}
                    >
                      Close
                    </button>
                  </div>
                ) : (
                  // Form state - Luxury design
                  <form onSubmit={handleSubmit}>
                    <p className="text-gray-600 dark:text-gray-300 mb-6 font-light leading-relaxed">
                      Enter your phone number or email address to receive your personal RSVP link for {coupleName}&apos;s celebration.
                    </p>

                    {/* Contact type toggle - Elegant pill design */}
                    <div className="flex mb-6 bg-gray-100 dark:bg-slate-700/50 rounded-full p-1.5">
                      <button
                        type="button"
                        onClick={() => setContactType('phone')}
                        className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-full text-sm font-medium transition-all duration-300 ${
                          contactType === 'phone'
                            ? 'bg-white dark:bg-slate-600 shadow-md text-gray-900 dark:text-white'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                        }`}
                      >
                        <PhoneIcon className="h-4 w-4" />
                        Phone
                      </button>
                      <button
                        type="button"
                        onClick={() => setContactType('email')}
                        className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-full text-sm font-medium transition-all duration-300 ${
                          contactType === 'email'
                            ? 'bg-white dark:bg-slate-600 shadow-md text-gray-900 dark:text-white'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                        }`}
                      >
                        <EnvelopeIcon className="h-4 w-4" />
                        Email
                      </button>
                    </div>

                    {/* Contact input - Elegant styling */}
                    <div className="mb-6">
                      <label htmlFor="contact" className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wider">
                        {contactType === 'phone' ? 'Phone Number' : 'Email Address'}
                      </label>
                      <input
                        type={contactType === 'phone' ? 'tel' : 'email'}
                        id="contact"
                        value={contact}
                        onChange={(e) => handleContactChange(e.target.value)}
                        placeholder={contactType === 'phone' ? '(555) 123-4567' : 'your@email.com'}
                        className="w-full px-5 py-4 rounded-xl border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-700/50 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-2 transition-all duration-200"
                        style={{
                          boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.05)'
                        }}
                        disabled={loading}
                      />
                    </div>

                    {/* Error message - Subtle styling */}
                    {error && (
                      <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-800/50 rounded-xl">
                        <p className="text-sm text-red-600 dark:text-red-400 font-light">{error}</p>
                      </div>
                    )}

                    {/* Submit button - Luxury gradient */}
                    <button
                      type="submit"
                      disabled={loading || !contact.trim()}
                      className="w-full py-4 rounded-xl text-sm font-medium text-white transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]"
                      style={{
                        background: `linear-gradient(135deg, ${primaryColor} 0%, ${accentColor} 100%)`,
                      }}
                    >
                      {loading ? (
                        <span className="flex items-center justify-center gap-2">
                          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                            <circle
                              className="opacity-25"
                              cx="12"
                              cy="12"
                              r="10"
                              stroke="currentColor"
                              strokeWidth="4"
                              fill="none"
                            />
                            <path
                              className="opacity-75"
                              fill="currentColor"
                              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                            />
                          </svg>
                          Sending...
                        </span>
                      ) : (
                        'Send My RSVP Link'
                      )}
                    </button>

                    {/* Help text - Refined */}
                    <p className="mt-6 text-xs text-gray-400 dark:text-gray-500 text-center font-light leading-relaxed">
                      Please use the same phone number or email you provided when you were added to the guest list.
                    </p>
                  </form>
                )}
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
