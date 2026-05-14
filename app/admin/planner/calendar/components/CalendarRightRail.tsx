'use client';

// Tabbed right rail: Upcoming / Availability / Legend.
//
// Replaces the three stacked sections that used to sit in the right
// column of /admin/planner/calendar. One tab visible at a time keeps
// the column compact (~360 px wide × ~520 px tall) instead of
// growing unbounded with every new piece of context.
//
// When the day-slide-over is open, the parent should hide this rail
// — the slide-over takes the same visual slot and represents a
// drilldown into a specific day.
//
// Design tokens:
//   * font-heading (Playfair Display) on the tab body's small section
//     title to maintain editorial hierarchy with the page heading.
//   * wedding-rose underline on the active tab.
//   * wedding-sage chips on the legend's "internal meeting" swatch.

import React, { useState } from 'react';
import type {
  AvailabilityWindow,
  SharedCalendarEvent,
} from '@/services/calendarApi';

type TabKey = 'upcoming' | 'availability' | 'legend';

interface CalendarRightRailProps {
  /** Pre-filtered upcoming items the parent computed (e.g. next 7
   *  days). Sorted ascending by start_date. */
  upcoming: SharedCalendarEvent[];
  /** Availability windows from /planner/calendar/availability. */
  availabilityWindows: AvailabilityWindow[];
  /** Staff option labels, indexed for the availability tab caption. */
  availabilityLabel?: string;
  onRefreshUpcoming?: () => void;
  onRefreshAvailability?: () => void;
}

function formatRangeDay(iso: string): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export default function CalendarRightRail({
  upcoming,
  availabilityWindows,
  availabilityLabel,
  onRefreshUpcoming,
  onRefreshAvailability,
}: CalendarRightRailProps) {
  const [activeTab, setActiveTab] = useState<TabKey>('upcoming');

  const tabs: { key: TabKey; label: string; count?: number }[] = [
    { key: 'upcoming', label: 'Upcoming', count: upcoming.length },
    {
      key: 'availability',
      label: 'Availability',
      count: availabilityWindows.length,
    },
    { key: 'legend', label: 'Legend' },
  ];

  return (
    <aside
      role="region"
      aria-label="Calendar side rail"
      className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800"
    >
      {/* Tab bar */}
      <nav
        role="tablist"
        aria-label="Side rail view"
        className="flex border-b border-slate-200 px-1 dark:border-slate-700"
      >
        {tabs.map((tab) => {
          const active = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              role="tab"
              aria-selected={active}
              onClick={() => setActiveTab(tab.key)}
              className={`flex-1 border-b-2 px-2 py-2.5 text-[12px] font-medium transition ${
                active
                  ? 'border-wedding-rose text-wedding-rose'
                  : 'border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
              }`}
            >
              {tab.label}
              {typeof tab.count === 'number' && (
                <span className="ml-1 text-[10.5px] text-slate-400 dark:text-slate-500">
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Tab body */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'upcoming' && (
          <UpcomingTab events={upcoming} onRefresh={onRefreshUpcoming} />
        )}
        {activeTab === 'availability' && (
          <AvailabilityTab
            windows={availabilityWindows}
            label={availabilityLabel}
            onRefresh={onRefreshAvailability}
          />
        )}
        {activeTab === 'legend' && <LegendTab />}
      </div>
    </aside>
  );
}

function UpcomingTab({
  events,
  onRefresh,
}: {
  events: SharedCalendarEvent[];
  onRefresh?: () => void;
}) {
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <p className="font-heading text-sm text-slate-900 dark:text-slate-100">
          Next up
        </p>
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            className="rounded-md border border-slate-300 px-2 py-0.5 text-[10.5px] font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700/60"
          >
            Refresh
          </button>
        )}
      </div>
      {events.length === 0 ? (
        <p className="font-elegant italic text-[12.5px] text-slate-500 dark:text-slate-400">
          No upcoming items in the current filtered view.
        </p>
      ) : (
        <ul className="space-y-2">
          {events.map((event) => (
            <li
              key={event.id}
              className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800/40"
            >
              <p className="truncate text-[13px] font-medium text-slate-900 dark:text-slate-100">
                {event.title || 'Untitled'}
              </p>
              <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
                {formatRangeDay(event.start_date || '')}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AvailabilityTab({
  windows,
  label,
  onRefresh,
}: {
  windows: AvailabilityWindow[];
  label?: string;
  onRefresh?: () => void;
}) {
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <p className="font-heading text-sm text-slate-900 dark:text-slate-100">
          Open windows
        </p>
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            className="rounded-md border border-slate-300 px-2 py-0.5 text-[10.5px] font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700/60"
          >
            Refresh
          </button>
        )}
      </div>
      {label && (
        <p className="mb-2 font-elegant italic text-[11px] text-slate-500 dark:text-slate-400">
          {label}
        </p>
      )}
      {windows.length === 0 ? (
        <p className="font-elegant italic text-[12.5px] text-slate-500 dark:text-slate-400">
          No open windows found for the selected staff in this range.
        </p>
      ) : (
        <ul className="space-y-2">
          {windows.slice(0, 8).map((w, idx) => (
            <li
              key={`${w.start}-${idx}`}
              className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 dark:border-emerald-900/40 dark:bg-emerald-950/30"
            >
              <p className="text-[10.5px] font-semibold uppercase tracking-[0.18em] text-emerald-700 dark:text-emerald-200">
                Available window
              </p>
              <p className="mt-0.5 text-[12.5px] font-medium text-slate-900 dark:text-slate-100">
                {formatRangeDay(w.start)}
              </p>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                until {formatRangeDay(w.end)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function LegendTab() {
  return (
    <div>
      <p className="font-heading text-sm text-slate-900 dark:text-slate-100">
        Legend
      </p>
      <ul className="mt-3 space-y-2 text-[12.5px]">
        <li className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
          <span className="h-2 w-2 rounded-full bg-wedding-sage" />
          Internal task
        </li>
        <li className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
          <span className="h-2 w-2 rounded-full bg-wedding-rose" />
          Internal meeting
        </li>
        <li className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
          <span className="h-2 w-2 rounded-full bg-slate-400" />
          External event (connected calendar)
        </li>
      </ul>
      <p className="mt-4 font-elegant italic text-[11.5px] leading-relaxed text-slate-500 dark:text-slate-400">
        External calendars show busy/free only unless the connection enables
        full details. Couples receive email plus ICS for meetings; they do
        not connect calendars in v1.
      </p>
    </div>
  );
}
