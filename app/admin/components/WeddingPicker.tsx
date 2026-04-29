'use client';

/**
 * Shared wedding picker.
 *
 * Lifts the inline pill-style dropdown that lives in
 * `CommunicationsInboxView.tsx` into a reusable component so every
 * page (Seating, Budget, Reminders, etc.) gets the same compact UX.
 *
 * Pattern:
 *   - small Heart-icon pill button with a truncated label and chevron
 *   - portal opens beneath, max-h with scroll, "All Weddings" row optional
 *   - click outside closes
 *
 * Each consumer maps its own wedding shape to `{id, label}` so this
 * component doesn't need to know about partner names, slugs, dates,
 * etc. The label is a single render-friendly string.
 */

import { useEffect, useRef, useState } from 'react';
import { ChevronDown, Heart } from 'lucide-react';

export interface WeddingPickerOption {
  id: string;
  label: string;
}

export interface WeddingPickerProps {
  /** All weddings the planner can switch between. */
  options: WeddingPickerOption[];
  /** Currently selected wedding id. Use the `allValue` constant when "All" is selected. */
  value: string;
  /** Called when the planner picks a wedding (or the "All" entry, if enabled). */
  onChange: (id: string) => void;
  /** When true, prepends an "All Weddings" entry whose value is `allValue`. */
  allowAll?: boolean;
  /** Value used for the "All Weddings" entry when `allowAll` is true. Defaults to `'all'`. */
  allValue?: string;
  /** Label shown when nothing is selected (or `value === ''`). */
  placeholder?: string;
  /** Optional override for the "All Weddings" label. */
  allLabel?: string;
  /** Disable the trigger entirely. */
  disabled?: boolean;
  /** Additional class names on the trigger button (e.g. for layout positioning). */
  className?: string;
}

export default function WeddingPicker({
  options,
  value,
  onChange,
  allowAll = false,
  allValue = 'all',
  placeholder = 'Choose a wedding…',
  allLabel = 'All Weddings',
  disabled = false,
  className = '',
}: WeddingPickerProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Close on outside click. Necessary because we render an absolute portal
  // that doesn't take focus by default.
  useEffect(() => {
    if (!open) return;
    const handler = (event: MouseEvent) => {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const selectedLabel = (() => {
    if (allowAll && value === allValue) return allLabel;
    const found = options.find((o) => o.id === value);
    return found?.label ?? placeholder;
  })();

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <button
        type="button"
        onClick={() => !disabled && setOpen((prev) => !prev)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm bg-white text-gray-700 hover:bg-gray-100 dark:bg-slate-800 dark:text-gray-300 dark:hover:bg-slate-700 transition border border-gray-200 dark:border-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <Heart size={14} />
        <span className="max-w-[180px] truncate">{selectedLabel}</span>
        <ChevronDown
          size={14}
          className={`transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div
          role="listbox"
          className="absolute right-0 top-full mt-1 min-w-[16rem] max-w-[24rem] bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-gray-200 dark:border-slate-700 z-50 max-h-64 overflow-y-auto"
        >
          {allowAll && (
            <button
              type="button"
              role="option"
              aria-selected={value === allValue}
              onClick={() => {
                onChange(allValue);
                setOpen(false);
              }}
              className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-slate-700 transition ${
                value === allValue
                  ? 'bg-rose-50 dark:bg-rose-900/10 text-rose-600 dark:text-rose-400 font-medium'
                  : 'text-gray-700 dark:text-gray-300'
              }`}
            >
              {allLabel}
            </button>
          )}
          {options.length === 0 ? (
            <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
              No weddings yet
            </div>
          ) : (
            options.map((option) => (
              <button
                key={option.id}
                type="button"
                role="option"
                aria-selected={value === option.id}
                onClick={() => {
                  onChange(option.id);
                  setOpen(false);
                }}
                className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-slate-700 transition ${
                  value === option.id
                    ? 'bg-rose-50 dark:bg-rose-900/10 text-rose-600 dark:text-rose-400 font-medium'
                    : 'text-gray-700 dark:text-gray-300'
                }`}
              >
                {option.label}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
