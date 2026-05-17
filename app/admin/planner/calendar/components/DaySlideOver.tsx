'use client';

// Right-side slide-over showing a single day's tasks / meetings /
// external events. Replaces the previous "stack everything in the
// right rail" pattern with a TABBED panel so the planner sees one
// category at a time and the slide-over fits in ~380px instead of
// growing unbounded.
//
// Tabs (left → right):
//   Timeline  — chronological mix of all items for the day
//   Tasks     — internal planner_tasks only
//   Meetings  — internal meetings only
//   External  — events imported from connected provider calendars
//
// Counts are shown inline on each tab label so the planner can decide
// where to look without clicking. Empty tabs are still selectable so
// the absence of items is explicit, not hidden.
//
// Design tokens:
//   * Header serif (font-heading = Playfair Display) for the date.
//   * Italic caption (font-elegant) for the subtitle counts.
//   * wedding-rose accent on the active tab underline + quick-action
//     "+ Task" button (primary intent).
//   * wedding-sage accent on "+ Meeting" (secondary intent).
//   * neutral slate for "+ Block".

import React, { useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import type { SharedCalendarEvent } from '@/services/calendarApi';
import { useFocusTrap } from '@/hooks/useFocusTrap';

type TabKey = 'timeline' | 'tasks' | 'meetings' | 'external';

interface DaySlideOverProps {
  /** ISO date string for the selected day (date-only, no time). */
  selectedDateIso: string;
  /** All shared events visible in the parent's current month/filter
   *  scope. The slide-over filters internally to the selected day. */
  events: SharedCalendarEvent[];
  onClose: () => void;
  onCreateTask: (dateIso: string) => void;
  onCreateMeeting: (dateIso: string) => void;
  onCreateBlock?: (dateIso: string) => void;
  onSelectEvent?: (event: SharedCalendarEvent) => void;
}

function formatHeaderDate(iso: string): { weekday: string; rest: string } {
  const d = new Date(`${iso}T00:00:00`);
  const weekday = d.toLocaleDateString(undefined, { weekday: 'long' });
  const rest = d.toLocaleDateString(undefined, {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
  return { weekday, rest };
}

function formatTime(value: string | null | undefined): string {
  if (!value) return '';
  try {
    return new Date(value).toLocaleTimeString(undefined, {
      hour: 'numeric',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

// P3#8 — date-string slice was timezone-naive. ECMA-262 §21.4.1.18
// states that ISO strings with explicit offsets parse to absolute
// instants; the literal first 10 chars represent the date IN THE
// OFFSET, not the viewer's local calendar day. We now resolve each
// event's start/end to the viewer's local calendar day via
// Intl.DateTimeFormat and compare against the selected day's ISO.
function eventLocalDayIso(value: string): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  // ``en-CA`` locale renders as YYYY-MM-DD, matching our dayIso shape
  // and avoiding manual zero-padding gymnastics.
  return new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(parsed);
}

function isOnDay(event: SharedCalendarEvent, dayIso: string): boolean {
  const start = event.start_date ? eventLocalDayIso(event.start_date) : null;
  if (start && start === dayIso) return true;
  // An event that starts before and ends after the selected day (a
  // multi-day block) should still surface on the selected day.
  const end = event.end_date ? eventLocalDayIso(event.end_date) : null;
  if (end && end === dayIso) return true;
  if (start && end && start <= dayIso && dayIso <= end) return true;
  return false;
}

// Per app/services/calendarApi.ts, source_type is one of
// 'internal_task' | 'internal_meeting' | 'external_google' | string.
// The backend has since started emitting bare 'external' (Aurinko
// migration) plus 'external_provider' as a separate hint; we cover
// both with a prefix check.
function isTask(event: SharedCalendarEvent): boolean {
  return event.source_type === 'internal_task';
}
function isMeeting(event: SharedCalendarEvent): boolean {
  return event.source_type === 'internal_meeting';
}
function isExternal(event: SharedCalendarEvent): boolean {
  return String(event.source_type || '').startsWith('external');
}

export default function DaySlideOver({
  selectedDateIso,
  events,
  onClose,
  onCreateTask,
  onCreateMeeting,
  onCreateBlock,
  onSelectEvent,
}: DaySlideOverProps) {
  const [activeTab, setActiveTab] = useState<TabKey>('timeline');

  const dayEvents = useMemo(
    () => events.filter((e) => isOnDay(e, selectedDateIso)),
    [events, selectedDateIso]
  );
  const tasks = useMemo(() => dayEvents.filter(isTask), [dayEvents]);
  const meetings = useMemo(() => dayEvents.filter(isMeeting), [dayEvents]);
  const externals = useMemo(() => dayEvents.filter(isExternal), [dayEvents]);

  // Esc closes; body scroll locked while open.
  React.useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  // WAI-ARIA Dialog pattern: trap Tab inside the slide-over, restore
  // focus to the triggering calendar cell on close.
  const dialogRef = useRef<HTMLElement>(null);
  useFocusTrap(dialogRef, true);

  if (typeof document === 'undefined') return null;

  const { weekday, rest } = formatHeaderDate(selectedDateIso);

  const tabs: { key: TabKey; label: string; count: number }[] = [
    { key: 'timeline', label: 'Timeline', count: dayEvents.length },
    { key: 'tasks', label: 'Tasks', count: tasks.length },
    { key: 'meetings', label: 'Meetings', count: meetings.length },
    { key: 'external', label: 'External', count: externals.length },
  ];

  const visibleEvents =
    activeTab === 'timeline'
      ? sortChronologically(dayEvents)
      : activeTab === 'tasks'
        ? tasks
        : activeTab === 'meetings'
          ? meetings
          : externals;

  return createPortal(
    <div className="fixed inset-0 z-[80]" role="dialog" aria-modal="true">
      {/* Backdrop: blocks clicks on the calendar grid behind. */}
      <div
        className="absolute inset-0 bg-slate-950/35 backdrop-blur-[2px] dark:bg-black/55"
        onClick={onClose}
        aria-hidden
      />
      <aside
        ref={dialogRef}
        className="absolute right-0 top-0 flex h-full w-full max-w-[420px] flex-col bg-white shadow-2xl animate-slide-up dark:bg-slate-900"
      >
        {/* Header */}
        <header className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 pt-5 pb-4 dark:border-slate-700">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-primary-700 dark:text-rose-200">
              Selected day
            </p>
            <h2 className="font-heading text-2xl text-slate-900 dark:text-slate-100">
              {weekday}
            </h2>
            <p className="font-elegant italic text-sm text-slate-500 dark:text-slate-400">
              {rest}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close day panel"
            className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-500 transition hover:bg-slate-200 hover:text-slate-700 dark:bg-slate-800 dark:text-slate-400 dark:hover:bg-slate-700"
          >
            <X size={16} />
          </button>
        </header>

        {/* Quick-create */}
        <div className="grid grid-cols-3 gap-2 border-b border-slate-200 px-5 py-3 dark:border-slate-700">
          <button
            type="button"
            onClick={() => onCreateTask(selectedDateIso)}
            className="rounded-lg bg-wedding-rose/15 px-2 py-1.5 text-xs font-semibold text-primary-700 ring-1 ring-wedding-rose/30 transition hover:bg-wedding-rose/25 dark:text-rose-200"
          >
            + Task
          </button>
          <button
            type="button"
            onClick={() => onCreateMeeting(selectedDateIso)}
            className="rounded-lg bg-wedding-sage/15 px-2 py-1.5 text-xs font-semibold text-secondary-700 ring-1 ring-wedding-sage/40 transition hover:bg-wedding-sage/25 dark:text-secondary-200"
          >
            + Meeting
          </button>
          <button
            type="button"
            onClick={() => onCreateBlock?.(selectedDateIso)}
            disabled={!onCreateBlock}
            className="rounded-lg bg-slate-100 px-2 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700 dark:hover:bg-slate-700/70"
          >
            + Block
          </button>
        </div>

        {/* Tabs — implements WAI-ARIA APG Tabs Pattern:
            * tablist + tab + tabpanel triple
            * aria-controls + aria-labelledby linkage
            * roving tabindex (only the active tab is reachable via Tab)
            * arrow-key navigation between tabs with wrap, Home/End */}
        <nav
          role="tablist"
          aria-label="Day view"
          className="flex border-b border-slate-200 px-2 dark:border-slate-700"
          onKeyDown={(event) => {
            const idx = tabs.findIndex((t) => t.key === activeTab);
            if (idx < 0) return;
            let next = idx;
            if (event.key === 'ArrowRight') next = (idx + 1) % tabs.length;
            else if (event.key === 'ArrowLeft') next = (idx - 1 + tabs.length) % tabs.length;
            else if (event.key === 'Home') next = 0;
            else if (event.key === 'End') next = tabs.length - 1;
            else return;
            event.preventDefault();
            setActiveTab(tabs[next].key);
            // Move focus to the newly-active tab so keyboard users see
            // the focus ring track the selection (automatic activation
            // per the APG recommendation for unrelated content panels).
            const el = document.getElementById(`day-tab-${tabs[next].key}`);
            el?.focus();
          }}
        >
          {tabs.map((tab) => {
            const active = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                id={`day-tab-${tab.key}`}
                role="tab"
                type="button"
                aria-selected={active}
                aria-controls={`day-tabpanel-${tab.key}`}
                tabIndex={active ? 0 : -1}
                onClick={() => setActiveTab(tab.key)}
                className={`flex-1 border-b-2 px-2 py-2.5 text-xs font-medium transition ${
                  active
                    ? 'border-wedding-rose text-primary-700 dark:text-rose-200'
                    : 'border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
                }`}
              >
                {tab.label}{' '}
                <span className="ml-1 text-[10.5px] text-slate-400 dark:text-slate-500">
                  {tab.count}
                </span>
              </button>
            );
          })}
        </nav>

        {/* Tab content */}
        <div
          role="tabpanel"
          id={`day-tabpanel-${activeTab}`}
          aria-labelledby={`day-tab-${activeTab}`}
          tabIndex={0}
          className="flex-1 overflow-y-auto px-5 py-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-wedding-rose/60"
        >
          {visibleEvents.length === 0 ? (
            <EmptyState tab={activeTab} />
          ) : (
            <ul className="space-y-2.5">
              {visibleEvents.map((event) => (
                <li key={event.id || `${event.title}-${event.start_date}`}>
                  <EventRow event={event} onClick={onSelectEvent} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </div>,
    document.body
  );
}

function sortChronologically(events: SharedCalendarEvent[]): SharedCalendarEvent[] {
  return [...events].sort((a, b) => {
    const ta = a.start_date ? new Date(a.start_date).getTime() : 0;
    const tb = b.start_date ? new Date(b.start_date).getTime() : 0;
    return ta - tb;
  });
}

interface EventRowProps {
  event: SharedCalendarEvent;
  onClick?: (event: SharedCalendarEvent) => void;
}

function EventRow({ event, onClick }: EventRowProps) {
  const time = formatTime(event.start_date);
  const accent = isTask(event)
    ? 'border-wedding-sage/40 bg-wedding-sage/10'
    : isMeeting(event)
      ? 'border-wedding-rose/30 bg-wedding-rose/8'
      : 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/40';

  const Wrapper: React.ElementType = onClick ? 'button' : 'div';
  const wrapperProps = onClick
    ? {
        type: 'button' as const,
        onClick: () => onClick(event),
        className: `block w-full rounded-xl border px-3 py-2.5 text-left transition hover:border-wedding-rose/50 ${accent}`,
      }
    : {
        className: `block rounded-xl border px-3 py-2.5 ${accent}`,
      };

  return (
    <Wrapper {...wrapperProps}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">
            {event.title || 'Untitled'}
          </p>
          {(event.owner_planner_email || event.wedding_id) && (
            <p className="mt-0.5 truncate text-[11.5px] text-slate-500 dark:text-slate-400">
              {event.wedding_id ? `Wedding · ${event.wedding_id}` : event.owner_planner_email}
            </p>
          )}
        </div>
        {time && (
          <span className="flex-shrink-0 rounded-full bg-white/70 px-2 py-0.5 text-[10.5px] font-medium text-slate-700 ring-1 ring-slate-200 dark:bg-slate-900/60 dark:text-slate-200 dark:ring-slate-700">
            {time}
          </span>
        )}
      </div>
    </Wrapper>
  );
}

function EmptyState({ tab }: { tab: TabKey }) {
  const copy =
    tab === 'tasks'
      ? 'No tasks for this day.'
      : tab === 'meetings'
        ? 'No meetings scheduled.'
        : tab === 'external'
          ? 'Nothing on your connected calendars today.'
          : 'No items for this day. Use the quick-create buttons above.';
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center dark:border-slate-700 dark:bg-slate-800/40">
      <p className="font-elegant italic text-sm text-slate-500 dark:text-slate-400">
        {copy}
      </p>
    </div>
  );
}
