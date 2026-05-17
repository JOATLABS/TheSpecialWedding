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

import React, { useEffect, useRef, useState } from 'react';
import type {
  AvailabilityWindow,
  SharedCalendarEvent,
} from '@/services/calendarApi';

type TabKey = 'upcoming' | 'availability' | 'legend';

export interface StaffOption {
  id: string;
  label: string;
}

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
  /** Optional — staff selector inside the Availability tab. When all
   *  three are present, a "Select staff" popover is mounted next to
   *  the Refresh button. */
  staffOptions?: StaffOption[];
  selectedStaffIds?: string[];
  onToggleStaff?: (staffId: string) => void;
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
  staffOptions,
  selectedStaffIds,
  onToggleStaff,
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
      {/* Tab bar — WAI-ARIA APG Tabs Pattern compliant (tablist +
          tab + tabpanel triple, aria-controls/labelledby linkage,
          roving tabindex, arrow-key navigation with wrap, Home/End). */}
      <nav
        role="tablist"
        aria-label="Side rail view"
        className="flex border-b border-slate-200 px-1 dark:border-slate-700"
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
          const el = document.getElementById(`rail-tab-${tabs[next].key}`);
          el?.focus();
        }}
      >
        {tabs.map((tab) => {
          const active = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              id={`rail-tab-${tab.key}`}
              role="tab"
              type="button"
              aria-selected={active}
              aria-controls={`rail-tabpanel-${tab.key}`}
              tabIndex={active ? 0 : -1}
              onClick={() => setActiveTab(tab.key)}
              className={`flex-1 border-b-2 px-2 py-2.5 text-[12px] font-medium transition ${
                active
                  ? 'border-wedding-rose text-primary-700 dark:text-rose-200'
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
      <div
        role="tabpanel"
        id={`rail-tabpanel-${activeTab}`}
        aria-labelledby={`rail-tab-${activeTab}`}
        tabIndex={0}
        className="flex-1 overflow-y-auto p-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-wedding-rose/60"
      >
        {activeTab === 'upcoming' && (
          <UpcomingTab events={upcoming} onRefresh={onRefreshUpcoming} />
        )}
        {activeTab === 'availability' && (
          <AvailabilityTab
            windows={availabilityWindows}
            label={availabilityLabel}
            onRefresh={onRefreshAvailability}
            staffOptions={staffOptions}
            selectedStaffIds={selectedStaffIds}
            onToggleStaff={onToggleStaff}
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
  staffOptions,
  selectedStaffIds,
  onToggleStaff,
}: {
  windows: AvailabilityWindow[];
  label?: string;
  onRefresh?: () => void;
  staffOptions?: StaffOption[];
  selectedStaffIds?: string[];
  onToggleStaff?: (staffId: string) => void;
}) {
  // Local popover for the staff selector. Anchored under the
  // "Select staff" button; closes on outside click + Escape. We keep
  // this STATE-LOCAL (not lifted to the parent) because nothing
  // outside the Availability tab cares whether the popover is open.
  const [staffOpen, setStaffOpen] = useState(false);
  const staffPopoverRef = useRef<HTMLDivElement>(null);
  const staffTriggerRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!staffOpen) return;
    const onClick = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        staffPopoverRef.current &&
        !staffPopoverRef.current.contains(target) &&
        staffTriggerRef.current &&
        !staffTriggerRef.current.contains(target)
      ) {
        setStaffOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setStaffOpen(false);
    };
    window.addEventListener('mousedown', onClick);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('mousedown', onClick);
      window.removeEventListener('keydown', onKey);
    };
  }, [staffOpen]);

  const showStaffPicker =
    Boolean(staffOptions && staffOptions.length > 0 && onToggleStaff);
  const selectedCount = (selectedStaffIds || []).length;

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="font-heading text-sm text-slate-900 dark:text-slate-100">
          Open windows
        </p>
        <div className="relative flex items-center gap-1.5">
          {showStaffPicker && (
            <>
              <button
                ref={staffTriggerRef}
                type="button"
                onClick={() => setStaffOpen((v) => !v)}
                aria-expanded={staffOpen}
                aria-haspopup="dialog"
                className="rounded-md border border-slate-300 px-2 py-0.5 text-[10.5px] font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700/60"
              >
                Staff{selectedCount > 0 ? ` · ${selectedCount}` : ''}
                <span className="ml-1 text-slate-400">{staffOpen ? '▴' : '▾'}</span>
              </button>
              {staffOpen && (
                <div
                  ref={staffPopoverRef}
                  role="dialog"
                  aria-label="Select staff for availability"
                  className="absolute right-0 top-full z-30 mt-1.5 w-[230px] rounded-xl border border-slate-200 bg-white p-2 shadow-lg animate-fade-in dark:border-slate-700 dark:bg-slate-800"
                >
                  <p className="px-2 pt-1 pb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-slate-500">
                    Show availability for
                  </p>
                  <ul className="max-h-[220px] overflow-y-auto">
                    {staffOptions!.map((staff) => {
                      const checked = (selectedStaffIds || []).includes(staff.id);
                      return (
                        <li key={staff.id}>
                          <label className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-[12.5px] text-slate-700 transition hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-700/40">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => onToggleStaff?.(staff.id)}
                              className="h-3.5 w-3.5 rounded border-slate-300 text-wedding-rose focus:ring-wedding-rose/40 dark:border-slate-600 dark:bg-slate-700"
                            />
                            <span className="truncate">{staff.label}</span>
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </>
          )}
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
