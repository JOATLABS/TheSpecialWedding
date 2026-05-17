'use client';

// Post-OAuth picker modal.
//
// Rendered inside ``app/admin/planner/calendar/callback/page.tsx`` after
// ``completeCalendarCallback`` returns a response with
// ``needs_selection === true``. Visual treatment matches
// ``docs/plans/planner_calendar_redesign_preview.html`` (View 2).
//
// Submission posts to ``POST /admin/planner/calendar/connections/select``
// via ``selectCalendars``. Empty submission ("Skip for now") still posts —
// the backend deletes the draft and returns a zero-rows success. We always
// want the draft cleaned up; the TTL fallback is for crash paths only.

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import type {
  CalendarSelectionPick,
  ContactBookSelectionPick,
  ProviderCallbackCalendar,
  ProviderCallbackContactBook,
  ProviderCallbackTasklist,
  TaskListSelectionPick,
} from '@/services/calendarApi';
import { getCalendarPickerResume } from '@/services/calendarApi';
import { useAdmin } from '@/contexts/AdminContext';
import { useFocusTrap } from '@/hooks/useFocusTrap';

interface CalendarPickerModalProps {
  draftId: string;
  accountEmail?: string | null;
  accountName?: string | null;
  provider?: string | null;
  calendars: ProviderCallbackCalendar[];
  tasklists?: ProviderCallbackTasklist[];
  contactBooks?: ProviderCallbackContactBook[];
  submitting: boolean;
  errorMessage?: string | null;
  onSubmit: (
    picks: CalendarSelectionPick[],
    taskPicks?: TaskListSelectionPick[],
    contactPicks?: ContactBookSelectionPick[]
  ) => void;
  onSkip: () => void;
}

function providerLabel(provider?: string | null): string {
  if (!provider) return 'Calendar';
  const lower = provider.toLowerCase();
  if (lower === 'google') return 'Google';
  if (lower === 'office365' || lower === 'microsoft') return 'Microsoft 365';
  if (lower === 'icloud') return 'iCloud';
  if (lower === 'ews' || lower === 'exchange') return 'Exchange';
  return provider;
}

type PickerTab = 'calendars' | 'tasks' | 'contacts';

export default function CalendarPickerModal({
  draftId,
  accountEmail,
  accountName,
  provider,
  calendars,
  tasklists = [],
  contactBooks = [],
  submitting,
  errorMessage,
  onSubmit,
  onSkip,
}: CalendarPickerModalProps) {
  // Pick state: a Set of aurinko_calendar_id for checked calendars,
  // plus a single id for the planner's explicit default-write override.
  // Initial state pre-checks every writable calendar; read-only feeds
  // are disabled (Aurinko refuses /subscriptions for them anyway).
  const writableIds = useMemo(
    () =>
      calendars.filter((c) => c.is_writable).map((c) => c.aurinko_calendar_id),
    [calendars]
  );
  const suggestedDefault = useMemo(
    () =>
      calendars.find((c) => c.suggested_default_write)?.aurinko_calendar_id ||
      writableIds[0] ||
      null,
    [calendars, writableIds]
  );

  const [checked, setChecked] = useState<Set<string>>(
    () => new Set(writableIds)
  );
  const [defaultWriteId, setDefaultWriteId] = useState<string | null>(
    suggestedDefault
  );
  const [visibility, setVisibility] = useState<
    Record<string, 'details' | 'busy_only'>
  >(() => {
    const init: Record<string, 'details' | 'busy_only'> = {};
    for (const c of calendars) init[c.aurinko_calendar_id] = 'busy_only';
    return init;
  });
  const [selectedTasklistId, setSelectedTasklistId] = useState<string | null>(
    () => tasklists.find((entry) => entry.suggested_default)?.aurinko_tasklist_id || null
  );
  const [selectedContactBookId, setSelectedContactBookId] = useState<string | null>(
    () =>
      contactBooks.find((entry) => entry.suggested_default)?.aurinko_contact_book_id ||
      null
  );
  const [activeTab, setActiveTab] = useState<PickerTab>('calendars');

  // Close on Escape (Skip path) + body scroll lock while open.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !submitting) {
        onSkip();
      }
    };
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onSkip, submitting]);

  // WAI-ARIA Dialog Modal pattern — trap Tab inside the dialog,
  // restore focus to the trigger on unmount. See useFocusTrap.
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef, true);

  // Stale-draft detection. If another tab finishes an OAuth round
  // and creates a NEW draft for the same (user, account), our draft
  // gets replaced by the unique-index upsert and our draft_token is
  // no longer valid server-side. Submitting the picker would 404. We
  // poll /picker-resume every 30 s and on tab-focus; if the active
  // draft id no longer matches ours, surface a clear message instead
  // of letting the planner submit into a void.
  const { token } = useAdmin();
  const [staleNotice, setStaleNotice] = useState(false);
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    const check = async () => {
      try {
        const resume = await getCalendarPickerResume(token);
        if (cancelled || submitting) return;
        // A live draft exists for this user and it isn't ours — our
        // tab is the older one. The reverse case (no draft + we have
        // a draft_id) means our draft was committed elsewhere; treat
        // it the same way.
        if (
          resume.needs_selection &&
          resume.draft_id &&
          resume.draft_id !== draftId
        ) {
          setStaleNotice(true);
        } else if (!resume.needs_selection) {
          setStaleNotice(true);
        }
      } catch {
        // Network blip — silently swallow; the next tick will retry.
      }
    };
    const interval = window.setInterval(check, 30_000);
    const onFocus = () => void check();
    window.addEventListener('focus', onFocus);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
      window.removeEventListener('focus', onFocus);
    };
  }, [token, draftId, submitting]);

  const toggle = (id: string, writable: boolean) => {
    if (!writable || submitting) return;
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
        // If we just unchecked the current default-write target, pick a
        // new one from whatever's still checked.
        if (defaultWriteId === id) {
          const fallback = Array.from(next).find((cid) =>
            writableIds.includes(cid)
          );
          setDefaultWriteId(fallback ?? null);
        }
      } else {
        next.add(id);
        if (!defaultWriteId) setDefaultWriteId(id);
      }
      return next;
    });
  };

  const handleSubmit = () => {
    const picks: CalendarSelectionPick[] = Array.from(checked).map((cid) => ({
      aurinko_calendar_id: cid,
      is_default_write_target: cid === defaultWriteId,
      details_visibility: visibility[cid] ?? 'busy_only',
    }));
    onSubmit(
      picks,
      selectedTasklistId ? [{ aurinko_tasklist_id: selectedTasklistId }] : [],
      selectedContactBookId
        ? [{ aurinko_contact_book_id: selectedContactBookId }]
        : []
    );
  };

  // Bulk-action helpers. "Select all writable" sets the checked set
  // to every writable calendar (read-only feeds stay disabled regardless).
  // "Clear all" empties the set without dropping the default-write id —
  // the planner can re-check rows and the previously-default stays
  // remembered if they re-include it. The two appear as small text
  // buttons above the list because accounts with many calendars (15+
  // is common on Google) get tedious to tick one-by-one.
  const allWritablePicked =
    writableIds.length > 0 &&
    writableIds.every((id) => checked.has(id));
  const selectAllWritable = () => {
    if (submitting) return;
    setChecked(new Set(writableIds));
    if (!defaultWriteId && writableIds.length > 0) {
      setDefaultWriteId(suggestedDefault ?? writableIds[0]);
    }
  };
  const clearAll = () => {
    if (submitting) return;
    setChecked(new Set());
  };

  if (typeof document === 'undefined') return null;

  const pickedCount = checked.size;
  const submitLabel = submitting
    ? 'Connecting…'
    : pickedCount === 0
      ? 'Skip and continue'
      : `Connect ${pickedCount} calendar${pickedCount === 1 ? '' : 's'}`;

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center"
      role="presentation"
      onClick={() => {
        if (!submitting) onSkip();
      }}
    >
      <div className="absolute inset-0 bg-slate-950/55 backdrop-blur-sm dark:bg-black/65" />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="calendar-picker-title"
        className="relative z-[10000] mx-4 max-h-[88vh] w-full max-w-[600px] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700/60 dark:bg-slate-900"
        onClick={(event) => event.stopPropagation()}
      >
        {/* Header */}
        <div className="border-b border-slate-200 px-6 pt-6 pb-4 dark:border-slate-700/60">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-primary-700 dark:text-rose-200">
                Almost there
              </p>
              <h2
                id="calendar-picker-title"
                className="mt-1 font-serif text-2xl text-slate-900 dark:text-slate-100"
              >
                Pick the calendars to sync
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">
                We'll only sync events from the ones you check. You can
                change this later from the calendar settings.
              </p>
            </div>
            <button
              type="button"
              onClick={() => !submitting && onSkip()}
              disabled={submitting}
              aria-label="Close picker"
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-500 transition-colors hover:bg-slate-200 hover:text-slate-700 disabled:opacity-50 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700"
            >
              <X size={16} />
            </button>
          </div>
          {accountEmail && (
            <div className="mt-3 inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600 dark:bg-slate-800/70 dark:text-slate-300">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-rose-100 text-[10px] font-semibold text-rose-700 dark:bg-rose-500/20 dark:text-rose-200">
                {(provider || '?').slice(0, 1).toUpperCase()}
              </span>
              {accountEmail} · {providerLabel(provider)}
            </div>
          )}
          {accountName && accountName !== accountEmail && (
            <p className="mt-1 text-[11px] text-slate-400">{accountName}</p>
          )}
        </div>

        <div
          role="tablist"
          aria-label="Sync resource picker"
          className="flex border-b border-slate-200 bg-slate-50/80 px-6 pt-3 dark:border-slate-700/60 dark:bg-slate-900/60"
        >
          {[
            { id: 'calendars' as const, label: 'Calendars', count: calendars.length },
            { id: 'tasks' as const, label: 'Tasks', count: tasklists.length },
            { id: 'contacts' as const, label: 'Contacts', count: contactBooks.length },
          ].map((tab) => {
            const selected = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={selected}
                aria-controls={`calendar-picker-${tab.id}`}
                onClick={() => setActiveTab(tab.id)}
                className={`relative -mb-px flex min-h-10 items-center gap-2 border-b-2 px-3 text-sm font-medium transition ${
                  selected
                    ? 'border-rose-500 text-slate-950 dark:text-slate-100'
                    : 'border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
                }`}
              >
                <span>{tab.label}</span>
                <span className="rounded-full bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                  {tab.count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Bulk-action bar — surfaces "Select all writable" / "Clear"
            so accounts with many calendars don't require one click per
            row. Read-only iCal feeds are excluded from "all writable"
            and stay unchecked regardless. */}
        {activeTab === 'calendars' && writableIds.length > 1 && (
          <div className="flex items-center justify-between border-b border-slate-200 px-6 py-2 text-[11.5px] text-slate-500 dark:border-slate-700/60 dark:text-slate-400">
            <span>
              {pickedCount} of {writableIds.length} writable selected
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={selectAllWritable}
                disabled={submitting || allWritablePicked}
                className="rounded-md px-2 py-1 font-medium text-primary-700 transition hover:bg-rose-50 disabled:opacity-50 dark:text-rose-200 dark:hover:bg-rose-500/10"
              >
                Select all writable
              </button>
              <button
                type="button"
                onClick={clearAll}
                disabled={submitting || pickedCount === 0}
                className="rounded-md px-2 py-1 font-medium text-slate-500 transition hover:bg-slate-100 disabled:opacity-50 dark:text-slate-400 dark:hover:bg-slate-700/40"
              >
                Clear
              </button>
            </div>
          </div>
        )}

        {/* List */}
        <div className="max-h-[460px] space-y-3 overflow-y-auto px-6 py-5">
          <div
            id="calendar-picker-calendars"
            role="tabpanel"
            hidden={activeTab !== 'calendars'}
          >
            {calendars.length === 0 && (
              <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-800/40">
                No calendars found on this account.
              </p>
            )}
            <div className="space-y-3">
              {calendars.map((cal) => {
                const id = cal.aurinko_calendar_id;
                const isChecked = checked.has(id);
                const disabled = !cal.is_writable;
                return (
                  <label
                    key={id}
                    // Cursor utility is mutually exclusive — emit one or
                    // the other instead of both (Tailwind utilities don't
                    // cascade-override reliably and ``cursor-pointer``
                    // appearing first in the className would lose to a
                    // later utility only by source-order accident).
                    className={`block rounded-xl border p-4 transition ${
                      disabled
                        ? 'cursor-not-allowed border-slate-200 bg-slate-50/60 opacity-60 dark:border-slate-700/40 dark:bg-slate-800/40'
                        : isChecked
                          ? 'cursor-pointer border-rose-300 bg-rose-50/60 dark:border-rose-500/40 dark:bg-rose-500/10'
                          : 'cursor-pointer border-slate-200 bg-white hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800/60 dark:hover:border-slate-600'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        checked={isChecked}
                        disabled={disabled || submitting}
                        onChange={() => toggle(id, cal.is_writable)}
                        className="mt-0.5 h-4 w-4 rounded border-slate-300 text-rose-500 focus:ring-rose-400 dark:border-slate-600 dark:bg-slate-700"
                      />
                      <div className="flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                            {cal.name || id}
                          </p>
                          {cal.is_primary && (
                            <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-medium text-rose-700 dark:bg-rose-500/20 dark:text-rose-200">
                              Primary
                            </span>
                          )}
                          {isChecked && id === defaultWriteId && (
                            <span className="rounded-full bg-slate-900 px-2 py-0.5 text-[10px] font-medium text-white dark:bg-slate-100 dark:text-slate-900">
                              Default write
                            </span>
                          )}
                          {!cal.is_writable && (
                            <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-medium text-slate-700 dark:bg-slate-700 dark:text-slate-300">
                              Read-only
                            </span>
                          )}
                        </div>
                        <p className="mt-0.5 text-[11.5px] text-slate-500 dark:text-slate-400">
                          {cal.access_role
                            ? `${cal.access_role} access`
                            : cal.is_writable
                              ? 'writable'
                              : 'subscribed feed · cannot sync events back'}
                        </p>

                        {isChecked && cal.is_writable && (
                          <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
                            <div>
                              <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-slate-500">
                                Visibility
                              </p>
                              <label className="flex items-center gap-1.5 text-slate-700 dark:text-slate-200">
                                <input
                                  type="radio"
                                  name={`vis-${id}`}
                                  value="busy_only"
                                  checked={visibility[id] !== 'details'}
                                  onChange={() =>
                                    setVisibility((prev) => ({
                                      ...prev,
                                      [id]: 'busy_only',
                                    }))
                                  }
                                  className="h-3 w-3 border-slate-300 text-rose-500"
                                />
                                Busy/free only
                              </label>
                              <label className="mt-1 flex items-center gap-1.5 text-slate-700 dark:text-slate-200">
                                <input
                                  type="radio"
                                  name={`vis-${id}`}
                                  value="details"
                                  checked={visibility[id] === 'details'}
                                  onChange={() =>
                                    setVisibility((prev) => ({
                                      ...prev,
                                      [id]: 'details',
                                    }))
                                  }
                                  className="h-3 w-3 border-slate-300 text-rose-500"
                                />
                                Full details
                              </label>
                            </div>
                            {id !== defaultWriteId && (
                              <div>
                                <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-slate-500">
                                  Default write target
                                </p>
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.preventDefault();
                                    setDefaultWriteId(id);
                                  }}
                                  className="rounded-md border border-slate-300 px-2.5 py-1 text-[11.5px] font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700/60"
                                >
                                  Use this calendar
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </label>
                );
              })}
            </div>
          </div>

          <div
            id="calendar-picker-tasks"
            role="tabpanel"
            hidden={activeTab !== 'tasks'}
          >
            {tasklists.length === 0 ? (
              <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-800/40">
                No task lists found on this account.
              </p>
            ) : (
              <label className="block text-xs text-slate-700 dark:text-slate-200">
                <span className="mb-2 block font-semibold uppercase tracking-[0.14em] text-slate-400 dark:text-slate-500">
                  Task list
                </span>
                <select
                  value={selectedTasklistId || ''}
                  onChange={(event) =>
                    setSelectedTasklistId(event.target.value || null)
                  }
                  disabled={submitting}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                >
                  <option value="">Do not sync tasks</option>
                  {tasklists.map((tasklist) => (
                    <option
                      key={tasklist.aurinko_tasklist_id}
                      value={tasklist.aurinko_tasklist_id}
                    >
                      {tasklist.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>

          <div
            id="calendar-picker-contacts"
            role="tabpanel"
            hidden={activeTab !== 'contacts'}
          >
            {contactBooks.length === 0 ? (
              <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-800/40">
                No contact books found on this account.
              </p>
            ) : (
              <label className="block text-xs text-slate-700 dark:text-slate-200">
                <span className="mb-2 block font-semibold uppercase tracking-[0.14em] text-slate-400 dark:text-slate-500">
                  Contact book
                </span>
                <select
                  value={selectedContactBookId || ''}
                  onChange={(event) =>
                    setSelectedContactBookId(event.target.value || null)
                  }
                  disabled={submitting}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                >
                  <option value="">Do not sync contacts</option>
                  {contactBooks.map((book) => (
                    <option
                      key={book.aurinko_contact_book_id}
                      value={book.aurinko_contact_book_id}
                    >
                      {book.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        </div>

        {staleNotice && (
          <div className="mx-6 mb-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
            Another tab started a new calendar setup, so this picker is no
            longer connected to a live session. Switch to the other tab to
            finish, or close this one.
          </div>
        )}

        {errorMessage && (
          <div className="mx-6 mb-3 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
            {errorMessage}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 border-t border-slate-200 bg-slate-50/60 px-6 py-4 dark:border-slate-700/60 dark:bg-slate-900/60">
          <button
            type="button"
            onClick={() => !submitting && onSkip()}
            disabled={submitting}
            className="text-sm text-slate-500 hover:text-slate-800 disabled:opacity-50 dark:text-slate-400 dark:hover:text-slate-200"
          >
            Skip for now
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || staleNotice}
            // Visual weight follows pick state — when 0 picks selected
            // the button reads "Skip and continue" which is semantically
            // SECONDARY, so it gets a neutral outline instead of the
            // primary rose fill (Material 3 + Apple HIG: lower-priority
            // actions shouldn't compete with the primary CTA).
            // ``bg-rose-600`` over ``bg-rose-500`` for white-text
            // contrast (WCAG 1.4.3 — rose-500 + white = 4.34:1 fails;
            // rose-600 + white = 5.04:1 passes).
            className={
              pickedCount === 0
                ? 'rounded-full border border-slate-300 bg-white px-5 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-60 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700/70'
                : 'rounded-full bg-rose-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-rose-700 disabled:opacity-60 dark:bg-rose-300 dark:text-slate-900 dark:hover:bg-rose-200'
            }
          >
            {submitLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

// ``draftId`` is forwarded by the parent component; it isn't referenced
// inside this modal because submission posts via the parent's onSubmit
// handler which already closes over the draft id. We keep it in the
// props signature to document the contract and make TS reader-eyes
// understand the modal is single-draft-scoped.
