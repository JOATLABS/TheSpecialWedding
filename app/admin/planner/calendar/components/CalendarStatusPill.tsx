'use client';

// Header pill + connections popover. Replaces the inline Calendar
// Connections card that previously occupied ~400 px at the top of
// /admin/planner/calendar.
//
// Design intent (per docs/plans/planner_calendar_redesign_mockup.md View 1):
//   * Pill in the page header is the only persistent affordance —
//     calendar connections are NOT a primary surface, they're a
//     setup-time concern.
//   * Click → popover anchored under the pill. Popover contains the
//     four provider-connect buttons (Google, Office 365, iCloud, EWS)
//     and a per-account collapsible list of connected rows. Each row
//     reuses the existing per-calendar Settings modal we already
//     shipped via ``CalendarConnect`` (no new settings UI).
//   * Status semantics:
//       healthy  → emerald dot, "N active · Webhooks OK"
//       warning  → amber dot, "Webhook issues" (last_error on any row)
//       empty    → muted dot, "No calendar connected"
//   * Brand application: wedding-rose for the primary "+ Connect"
//     button and the rose-tinted hover state on rows; slate for the
//     neutral card chrome so it sits visually in the page header
//     instead of competing with the calendar grid.

import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  beginCalendarConnect,
  CalendarConnection,
  type CalendarProviderId,
} from '@/services/calendarApi';
import { useAdmin } from '@/contexts/AdminContext';

interface ProviderOption {
  id: CalendarProviderId;
  label: string;
  avatar: string;
}

const PROVIDERS: ProviderOption[] = [
  { id: 'google', label: 'Google', avatar: 'G' },
  { id: 'office365', label: 'Microsoft 365', avatar: 'M' },
  { id: 'icloud', label: 'iCloud', avatar: 'iC' },
  { id: 'ews', label: 'Exchange', avatar: 'EX' },
];

type StatusTone = 'healthy' | 'warning' | 'empty' | 'connecting';

interface CalendarStatusPillProps {
  connections: CalendarConnection[];
  /** Click on a per-row "Settings" — caller opens its existing
   *  per-calendar Settings modal. */
  onOpenSettings: (connection: CalendarConnection) => void;
  onCheckHealth: (connection: CalendarConnection) => void;
  onDisconnect: (connection: CalendarConnection) => void;
  /** Optional — true while any disconnect/check-health is in flight,
   *  so the popover can dim its action buttons. */
  busy?: boolean;
}

function deriveStatus(connections: CalendarConnection[]): {
  tone: StatusTone;
  label: string;
} {
  if (connections.length === 0) {
    return { tone: 'empty', label: 'No calendar connected' };
  }
  const active = connections.filter(
    (c) => (c.connection_status || '').toLowerCase() === 'active'
  );
  const hasError = connections.some((c) => Boolean(c.last_error));
  const providerLabel = active.length > 0 ? capitalize(active[0].provider) : 'Calendar';
  if (hasError) {
    return {
      tone: 'warning',
      label: `${providerLabel} · ${active.length} active · webhook issues`,
    };
  }
  return {
    tone: 'healthy',
    label: `${providerLabel} · ${active.length} active · webhooks OK`,
  };
}

function capitalize(s: string | null | undefined): string {
  if (!s) return 'Calendar';
  const lower = String(s).toLowerCase();
  if (lower === 'google') return 'Google';
  if (lower === 'office365' || lower === 'microsoft') return 'Microsoft 365';
  if (lower === 'icloud') return 'iCloud';
  if (lower === 'ews' || lower === 'exchange') return 'Exchange';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function statusToneClasses(tone: StatusTone): {
  dot: string;
  pill: string;
  text: string;
} {
  switch (tone) {
    case 'healthy':
      return {
        dot: 'bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,0.18)]',
        pill: 'bg-emerald-500/8 border-emerald-500/30 hover:bg-emerald-500/12',
        text: 'text-emerald-800 dark:text-emerald-200',
      };
    case 'warning':
      return {
        dot: 'bg-amber-500 shadow-[0_0_0_3px_rgba(245,158,11,0.18)]',
        pill: 'bg-amber-500/10 border-amber-500/30 hover:bg-amber-500/15',
        text: 'text-amber-800 dark:text-amber-200',
      };
    case 'connecting':
      return {
        dot: 'bg-wedding-rose shadow-[0_0_0_3px_rgba(212,165,165,0.25)]',
        pill: 'bg-wedding-rose/10 border-wedding-rose/30 hover:bg-wedding-rose/15',
        // wedding-rose #D4A5A5 fails WCAG 1.4.3 as text on light surfaces
        // (2.24:1). primary-700 #804040 passes (~8.6:1).
        text: 'text-primary-700 dark:text-rose-200',
      };
    case 'empty':
    default:
      return {
        dot: 'bg-slate-400 dark:bg-slate-500',
        pill: 'bg-slate-100 border-slate-300 hover:bg-slate-200 dark:bg-slate-800 dark:border-slate-700 dark:hover:bg-slate-700/70',
        text: 'text-slate-700 dark:text-slate-200',
      };
  }
}

export default function CalendarStatusPill({
  connections,
  onOpenSettings,
  onCheckHealth,
  onDisconnect,
  busy = false,
}: CalendarStatusPillProps) {
  const { token } = useAdmin();
  const [open, setOpen] = useState(false);
  const [connectInFlight, setConnectInFlight] = useState<CalendarProviderId | null>(
    null
  );
  const [connectError, setConnectError] = useState<string | null>(null);
  const [expandedAccounts, setExpandedAccounts] = useState<Set<string>>(
    new Set()
  );
  const popoverRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Click-outside / Escape-to-close.
  useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        popoverRef.current &&
        !popoverRef.current.contains(target) &&
        triggerRef.current &&
        !triggerRef.current.contains(target)
      ) {
        setOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    window.addEventListener('mousedown', onClick);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('mousedown', onClick);
      window.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const status = useMemo(() => deriveStatus(connections), [connections]);
  const tone = connectInFlight ? 'connecting' : status.tone;
  const toneClasses = statusToneClasses(tone);

  // Group connections by Aurinko account email so the popover shows
  // one card per account with per-calendar rows nested below.
  const accounts = useMemo(() => {
    const groups = new Map<string, CalendarConnection[]>();
    for (const conn of connections) {
      const key =
        conn.provider_account_email || conn.user_email || conn.id || 'unknown';
      const list = groups.get(key) || [];
      list.push(conn);
      groups.set(key, list);
    }
    return Array.from(groups.entries()).map(([accountEmail, rows]) => ({
      accountEmail,
      provider: rows[0]?.provider || 'unknown',
      rows: rows.sort((a, b) => {
        if (a.is_default_write_target) return -1;
        if (b.is_default_write_target) return 1;
        if (a.is_primary) return -1;
        if (b.is_primary) return 1;
        return (a.calendar_name || '').localeCompare(b.calendar_name || '');
      }),
    }));
  }, [connections]);

  const toggleAccount = (email: string) => {
    setExpandedAccounts((prev) => {
      const next = new Set(prev);
      if (next.has(email)) next.delete(email);
      else next.add(email);
      return next;
    });
  };

  const handleConnect = async (provider: CalendarProviderId) => {
    if (!token || connectInFlight) return;
    setConnectInFlight(provider);
    setConnectError(null);
    try {
      const { auth_url } = await beginCalendarConnect(token, provider);
      window.location.href = auth_url;
    } catch (err) {
      setConnectError(
        err instanceof Error ? err.message : 'Failed to start calendar connect.'
      );
      setConnectInFlight(null);
    }
  };

  const label = connectInFlight
    ? `Connecting ${PROVIDERS.find((p) => p.id === connectInFlight)?.label ?? ''}…`
    : status.label;

  return (
    <div className="relative inline-flex">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className={`inline-flex items-center gap-2.5 rounded-full border px-3.5 py-1.5 text-[12.5px] font-medium transition ${toneClasses.pill} ${toneClasses.text}`}
      >
        <span className={`inline-block h-2 w-2 rounded-full ${toneClasses.dot}`} />
        <span>{label}</span>
        <span className="text-slate-400 dark:text-slate-500" aria-hidden>
          {open ? '▴' : '▾'}
        </span>
      </button>

      {open && (
        <div
          ref={popoverRef}
          role="dialog"
          aria-label="Calendar connections"
          className="absolute right-0 top-full z-40 mt-2 w-[480px] max-w-[calc(100vw-2rem)] origin-top-right animate-fade-in rounded-2xl border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-900"
        >
          <div className="border-b border-slate-200 px-5 py-4 dark:border-slate-700">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-primary-700 dark:text-rose-200">
              Connect a calendar
            </p>
            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
              We'll ask which calendars to sync after authorization.
            </p>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {PROVIDERS.map((provider) => {
                const isLoading = connectInFlight === provider.id;
                return (
                  <button
                    key={provider.id}
                    type="button"
                    onClick={() => handleConnect(provider.id)}
                    disabled={Boolean(connectInFlight)}
                    className="group inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-2.5 py-2 text-xs font-medium text-slate-800 transition hover:border-wedding-rose hover:bg-wedding-rose/5 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700/60"
                  >
                    {isLoading ? (
                      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-300 border-t-wedding-rose" />
                    ) : (
                      <span
                        aria-hidden
                        className="flex h-5 w-5 items-center justify-center rounded bg-slate-100 text-[10px] font-semibold text-slate-700 dark:bg-slate-700 dark:text-slate-200"
                      >
                        {provider.avatar}
                      </span>
                    )}
                    <span>{provider.label}</span>
                  </button>
                );
              })}
            </div>
            {connectError && (
              <p className="mt-2 rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-[11.5px] text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
                {connectError}
              </p>
            )}
          </div>

          <div className="max-h-[400px] overflow-y-auto px-5 py-4">
            {accounts.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center dark:border-slate-700 dark:bg-slate-800/40">
                <p className="text-sm font-medium text-slate-800 dark:text-slate-200">
                  No calendars connected yet
                </p>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Pick a provider above to get started.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">
                  Connected accounts
                </p>
                {accounts.map(({ accountEmail, provider, rows }) => {
                  const expanded = expandedAccounts.has(accountEmail);
                  const active = rows.filter(
                    (r) => (r.connection_status || '').toLowerCase() === 'active'
                  ).length;
                  const hasError = rows.some((r) => Boolean(r.last_error));
                  return (
                    <div
                      key={accountEmail}
                      className="rounded-xl border border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/50"
                    >
                      <button
                        type="button"
                        onClick={() => toggleAccount(accountEmail)}
                        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-wedding-rose/15 text-[11px] font-semibold text-primary-700 dark:text-rose-200">
                            {capitalize(provider).slice(0, 1)}
                          </span>
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
                              {accountEmail}
                            </p>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400">
                              {capitalize(provider)} · {active} active · {rows.length} calendar{rows.length === 1 ? '' : 's'}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {hasError ? (
                            <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10.5px] font-medium text-amber-800 dark:text-amber-200">
                              <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                              Issue
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2 py-0.5 text-[10.5px] font-medium text-emerald-800 dark:text-emerald-200">
                              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                              Healthy
                            </span>
                          )}
                          <span className="text-slate-500 dark:text-slate-400" aria-hidden>
                            {expanded ? '▾' : '▸'}
                          </span>
                        </div>
                      </button>

                      {expanded && (
                        <div className="space-y-2 border-t border-slate-200 bg-white px-4 py-3 dark:border-slate-700 dark:bg-slate-800">
                          {rows.map((conn) => (
                            <div
                              key={conn.id}
                              className="rounded-lg border border-slate-200 px-3 py-2.5 transition hover:border-wedding-rose/40 hover:bg-wedding-rose/5 dark:border-slate-700 dark:hover:bg-slate-700/30"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <div className="min-w-0">
                                  <div className="flex flex-wrap items-center gap-1.5">
                                    <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">
                                      {conn.calendar_name || conn.calendar_id || 'Unnamed calendar'}
                                    </p>
                                    {conn.is_default_write_target && (
                                      <span className="rounded-full bg-slate-900 px-1.5 py-0.5 text-[9.5px] font-medium text-white dark:bg-slate-100 dark:text-slate-900">
                                        Default
                                      </span>
                                    )}
                                    {conn.is_primary && (
                                      <span className="rounded-full bg-wedding-rose/15 px-1.5 py-0.5 text-[9.5px] font-medium text-primary-700 dark:text-rose-200">
                                        Primary
                                      </span>
                                    )}
                                    {!conn.is_writable && (
                                      <span className="rounded-full bg-slate-200 px-1.5 py-0.5 text-[9.5px] font-medium text-slate-700 dark:bg-slate-700 dark:text-slate-200">
                                        Read-only
                                      </span>
                                    )}
                                  </div>
                                  {conn.last_error && (
                                    <p className="mt-1 text-[10.5px] text-amber-700 dark:text-amber-300">
                                      {conn.last_error}
                                    </p>
                                  )}
                                </div>
                                <div className="flex flex-shrink-0 items-center gap-1">
                                  <button
                                    type="button"
                                    onClick={() => onOpenSettings(conn)}
                                    disabled={busy}
                                    className="rounded-md border border-slate-300 px-2 py-1 text-[11px] font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700/60"
                                  >
                                    Settings
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => onCheckHealth(conn)}
                                    disabled={busy}
                                    className="rounded-md border border-slate-300 px-2 py-1 text-[11px] font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700/60"
                                  >
                                    Check
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => onDisconnect(conn)}
                                    disabled={busy}
                                    className="rounded-md border border-rose-300 px-2 py-1 text-[11px] font-medium text-rose-700 transition hover:bg-rose-50 disabled:opacity-50 dark:border-rose-500/40 dark:text-rose-200 dark:hover:bg-rose-500/10"
                                  >
                                    Disconnect
                                  </button>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
