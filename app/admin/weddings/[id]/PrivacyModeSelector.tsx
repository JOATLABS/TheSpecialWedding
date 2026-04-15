'use client';

import clsx from 'clsx';

import type { PrivacyMode } from './privacySettings';
import { PRIVACY_MODE_OPTIONS } from './privacySettings';

interface PrivacyModeSelectorProps {
  value: PrivacyMode;
  onChange: (mode: PrivacyMode) => void;
}

export function PrivacyModeSelector({
  value,
  onChange,
}: PrivacyModeSelectorProps) {
  return (
    <div
      role="radiogroup"
      aria-label="Privacy Mode"
      className="grid gap-3 sm:grid-cols-3"
    >
      {PRIVACY_MODE_OPTIONS.map((option) => {
        const selected = option.value === value;

        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option.value)}
            className={clsx(
              'rounded-xl border px-4 py-3 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-wedding-gold/40',
              selected
                ? 'border-wedding-gold bg-wedding-gold/10 text-wedding-navy dark:border-wedding-gold/70 dark:bg-wedding-gold/10 dark:text-white'
                : 'border-gray-200 bg-white text-gray-700 hover:border-wedding-gold/50 hover:bg-wedding-gold/5 dark:border-gray-700 dark:bg-slate-800 dark:text-gray-200 dark:hover:border-wedding-gold/50 dark:hover:bg-wedding-gold/10',
            )}
          >
            <span className="block text-sm font-semibold">{option.label}</span>
            <span className="mt-1 block text-xs leading-5 opacity-80">
              {option.description}
            </span>
          </button>
        );
      })}
    </div>
  );
}
