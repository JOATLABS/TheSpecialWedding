'use client';

import React from 'react';
import type { RSVPConfig } from '@/types/wedding';

interface RSVPHelpBlockProps {
  rsvpConfig?: Partial<RSVPConfig>;
  onRequestHelp?: () => void;
}

export function RSVPHelpBlock({ rsvpConfig, onRequestHelp }: RSVPHelpBlockProps) {
  const helpText =
    rsvpConfig?.help_text ||
    'Check your phone for your personal invitation link. If you need help, use the Get Help button and our planner will text you.';
  const hidePhoneNumbers = rsvpConfig?.hide_phone_numbers ?? true;
  const buttonLabel = rsvpConfig?.help_button_label?.trim() || 'Get Help';
  const phoneNumbers = rsvpConfig?.phone_numbers?.filter((phone) => phone.trim()) || [];
  const shouldShowPhoneNumbers = !hidePhoneNumbers && phoneNumbers.length > 0;

  return (
    <div className="space-y-4 text-center">
      <p className="text-gray-600 dark:text-gray-300">{helpText}</p>

      {!shouldShowPhoneNumbers ? (
        onRequestHelp ? (
          <button
            type="button"
            onClick={onRequestHelp}
            className="inline-flex flex-col items-center justify-center text-white px-6 py-3 rounded-lg theme-bg-accent hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-wedding-rose transition"
          >
            <span className="font-semibold">Need help?</span>
            <span className="text-sm">{buttonLabel}</span>
          </button>
        ) : (
          <span className="inline-flex flex-col items-center justify-center text-white px-6 py-3 rounded-lg theme-bg-accent">
            <span className="font-semibold">Need help?</span>
            <span className="text-sm">{buttonLabel}</span>
          </span>
        )
      ) : (
        <div className="inline-flex text-white px-6 py-3 rounded-lg theme-bg-accent">
          <div>
            <p className="font-semibold">Need help?</p>
            <p className="text-sm">
              Call us at {phoneNumbers.join(' or ')}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
