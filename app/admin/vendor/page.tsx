'use client';

import { useEffect, useMemo, useState } from 'react';
import type { ReactElement } from 'react';
import { useRouter } from 'next/navigation';

import { useAdmin } from '@/contexts/AdminContext';
import {
  VendorDashboardResponse,
  fetchVendorDashboard,
  updateVendorTaskStatus,
} from '@/services/vendorDashboardApi';
import { formatDate as formatUtcDate, isSameLocalCalendarDate } from '@/utils/dateFormat';

const STATUS_OPTIONS: Array<{ value: VendorDashboardResponse['tasks'][number]['status']; label: string }> = [
  { value: 'pending', label: 'Pending' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
];

const STATUS_STYLES: Record<VendorDashboardResponse['tasks'][number]['status'], string> = {
  pending: 'bg-yellow-200/60 text-yellow-900 border border-yellow-300/60',
  in_progress: 'bg-blue-200/50 text-blue-900 border border-blue-300/60',
  completed: 'bg-emerald-200/50 text-emerald-900 border border-emerald-300/60',
};

const pageShellClass =
  'min-h-screen bg-gradient-to-br from-slate-50 via-white to-rose-50 py-12 text-slate-900 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 dark:text-white';

const glassPanelClass =
  'rounded-3xl border border-slate-200/80 bg-white/85 shadow-sm backdrop-blur-2xl dark:border-white/10 dark:bg-white/10';

const glassSoftPanelClass =
  'rounded-2xl border border-slate-200/80 bg-white/70 shadow-sm backdrop-blur-xl dark:border-white/15 dark:bg-white/15 dark:shadow-inner';

const pillClass =
  'rounded-full border border-slate-200 bg-white/80 px-3 py-1 text-xs font-medium text-slate-600 dark:border-white/10 dark:bg-white/10 dark:text-slate-200/80';

function formatDisplayDate(value?: string | null): string {
  if (!value) return '—';
  const formatted = formatUtcDate(value, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return formatted || '—';
}

export default function VendorDashboardPage(): ReactElement {
  const router = useRouter();
  const { token, userProfile, fetchUserProfile } = useAdmin();

  const [dashboard, setDashboard] = useState<VendorDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingTaskId, setUpdatingTaskId] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      router.push('/admin/login');
      return;
    }

    if (!userProfile) {
      fetchUserProfile();
      return;
    }

    if (!(userProfile.is_vendor || userProfile.is_root_admin || userProfile.is_wedding_planner)) {
      router.push('/admin');
      return;
    }

    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await fetchVendorDashboard(token);
        setDashboard(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load vendor dashboard');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [fetchUserProfile, router, token, userProfile]);

  const pendingTasks = useMemo(
    () => dashboard?.tasks.filter((task) => task.status !== 'completed') ?? [],
    [dashboard],
  );

  const completedTasksToday = useMemo(
    () =>
      dashboard?.tasks.filter((task) => {
        if (task.status !== 'completed' || !task.updated_at) {
          return false;
        }
        return isSameLocalCalendarDate(task.updated_at, new Date());
      }).length ?? 0,
    [dashboard],
  );

  const handleStatusChange = async (
    taskId: string,
    status: VendorDashboardResponse['tasks'][number]['status'],
  ) => {
    if (!token) return;

    try {
      setUpdatingTaskId(taskId);
      const updated = await updateVendorTaskStatus(token, taskId, status);
      setDashboard((current) => {
        if (!current) return current;
        return {
          ...current,
          tasks: current.tasks.map((task) => (task.id === taskId ? { ...task, ...updated } : task)),
          stats: {
            ...current.stats,
            completed_tasks:
              status === 'completed'
                ? current.stats.completed_tasks + (current.tasks.find((task) => task.id === taskId)?.status === 'completed' ? 0 : 1)
                : current.stats.completed_tasks -
                  (current.tasks.find((task) => task.id === taskId)?.status === 'completed' ? 1 : 0),
            open_tasks:
              status === 'completed'
                ? Math.max(current.stats.open_tasks - 1, 0)
                : current.stats.open_tasks + (current.tasks.find((task) => task.id === taskId)?.status === 'completed' ? 1 : 0),
          },
        };
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update task status');
    } finally {
      setUpdatingTaskId(null);
    }
  };

  if (loading) {
    return (
      <div className={`${pageShellClass} flex items-center justify-center`}>
        <div className="rounded-3xl border border-slate-200 bg-white px-10 py-8 text-lg text-slate-900 shadow-xl backdrop-blur-xl dark:border-white/10 dark:bg-white/10 dark:text-white">
          Loading your workspace…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`${pageShellClass} flex items-center justify-center`}>
        <div className="max-w-md space-y-4 rounded-3xl border border-red-300/40 bg-red-50/80 px-8 py-6 text-red-900 shadow-xl backdrop-blur-lg">
          <h1 className="text-xl font-semibold">We couldn’t open your workspace</h1>
          <p className="text-sm leading-relaxed text-red-700 dark:text-red-300/90">{error}</p>
          <button
            onClick={() => {
              if (!token) return;
              setLoading(true);
              fetchVendorDashboard(token)
                .then(setDashboard)
                .catch((err) => setError(err instanceof Error ? err.message : 'Failed to reload dashboard'))
                .finally(() => setLoading(false));
            }}
            className="rounded-xl bg-red-500 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-red-500/30 transition hover:bg-red-400"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div className={`${pageShellClass} flex items-center justify-center`}>
        No vendor data available.
      </div>
    );
  }

  const showcaseName = userProfile?.user_data?.company_name || userProfile?.email || 'Your team';

  return (
    <div className={pageShellClass}>
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-6">
        <header className="grid gap-6 lg:grid-cols-[1.35fr,1fr]">
          <section className={`${glassPanelClass} relative overflow-hidden p-8 dark:shadow-[0_40px_60px_-40px_rgba(15,23,42,0.8)]`}>
            <div className="pointer-events-none absolute -left-10 -top-10 h-48 w-48 rounded-full bg-rose-300/35 blur-3xl dark:bg-rose-400/30" />
            <div className="pointer-events-none absolute bottom-0 right-0 h-56 w-56 rounded-full bg-sky-200/40 blur-3xl dark:bg-sky-400/20" />

            <div className="relative flex flex-col gap-6">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-200/70">Vendor workspace</p>
                <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 dark:text-white md:text-4xl">
                  Welcome back, {showcaseName}
                </h1>
                <p className="mt-3 max-w-xl text-sm text-slate-600 dark:text-slate-200/80">
                  Track planner requests, keep your deliverables on schedule, and handoff forms without leaving this split-glass workspace.
                </p>
              </div>

              <dl className="grid gap-4 sm:grid-cols-3">
                <div className={`${glassSoftPanelClass} p-4 text-sm`}>
                  <dt className="text-slate-500 dark:text-slate-200/70">Open tasks</dt>
                  <dd className="mt-2 text-3xl font-semibold text-slate-900 dark:text-white">{dashboard.stats.open_tasks}</dd>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-200/60">{pendingTasks.length} in motion today</p>
                </div>
                <div className={`${glassSoftPanelClass} p-4 text-sm`}>
                  <dt className="text-slate-500 dark:text-slate-200/70">Completed today</dt>
                  <dd className="mt-2 text-3xl font-semibold text-slate-900 dark:text-white">{completedTasksToday}</dd>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-200/60">Keep the momentum going</p>
                </div>
                <div className={`${glassSoftPanelClass} p-4 text-sm`}>
                  <dt className="text-slate-500 dark:text-slate-200/70">Assigned weddings</dt>
                  <dd className="mt-2 text-3xl font-semibold text-slate-900 dark:text-white">{dashboard.weddings.length}</dd>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-200/60">Across {dashboard.profile.services.length || 1} service focus{dashboard.profile.services.length === 1 ? '' : 'es'}</p>
                </div>
              </dl>
            </div>
          </section>

          <aside className={`${glassPanelClass} flex h-full flex-col justify-between gap-4 p-6 dark:shadow-[0_40px_60px_-40px_rgba(59,130,246,0.5)]`}>
            <div>
              <h2 className="text-base font-semibold text-slate-900 dark:text-white">Planner pulse</h2>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-200/70">
                {dashboard.stats.pending_forms === 0
                  ? 'Everything shared with planners is up to date.'
                  : `You have ${dashboard.stats.pending_forms} form${dashboard.stats.pending_forms === 1 ? '' : 's'} awaiting completion.`}
              </p>
            </div>

            <div className="grid gap-3 text-sm text-slate-700 dark:text-slate-200/80">
              <div className={`${glassSoftPanelClass} flex items-center justify-between px-4 py-3`}>
                <span>Automation ready</span>
                <span className="text-base font-semibold text-slate-900 dark:text-white">{dashboard.stats.completed_forms}</span>
              </div>
              <div className={`${glassSoftPanelClass} flex items-center justify-between px-4 py-3`}>
                <span>Live services</span>
                <span className="text-base font-semibold text-slate-900 dark:text-white">{dashboard.profile.services.length}</span>
              </div>
              <div className={`${glassSoftPanelClass} flex items-center justify-between px-4 py-3`}>
                <span>Open items</span>
                <span className="text-base font-semibold text-slate-900 dark:text-white">{dashboard.stats.open_tasks}</span>
              </div>
            </div>
          </aside>
        </header>

        <main className="grid gap-6 lg:grid-cols-[2fr,1fr]">
          <section className={`${glassPanelClass} p-6 dark:shadow-[0_30px_50px_-40px_rgba(14,165,233,0.6)]`}>
            <div className="flex items-center justify-between gap-4 pb-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Action queue</h2>
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-200/70">Prioritised by due date across every wedding you support.</p>
              </div>
              <div className={pillClass}>
                {pendingTasks.length} open items
              </div>
            </div>

            <div className="divide-y divide-slate-200/70 dark:divide-white/5">
              {dashboard.tasks.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-10 text-center text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-200/70">
                  All of your planner requests are complete. We’ll surface new items here when they’re assigned.
                </div>
              ) : (
                dashboard.tasks.map((task) => (
                  <article key={task.id} className="flex flex-col gap-3 py-4 md:flex-row md:items-start md:justify-between">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-3">
                        <h3 className="text-base font-semibold text-slate-900 dark:text-white">{task.task}</h3>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${STATUS_STYLES[task.status]}`}>
                          {task.status.replace('_', ' ')}
                        </span>
                      </div>
                      <p className="text-sm text-slate-600 dark:text-slate-200/70">{task.category || 'General'}</p>
                      <div className="flex flex-wrap gap-3 text-xs text-slate-500 dark:text-slate-200/60">
                        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 dark:border-white/10 dark:bg-white/5">{task.wedding_name || 'Wedding'}</span>
                        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 dark:border-white/10 dark:bg-white/5">
                          Due {task.due_date ? formatDisplayDate(task.due_date) : 'soon'}
                        </span>
                        {task.notes && <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 dark:border-white/10 dark:bg-white/5">Note available</span>}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <label className="sr-only" htmlFor={`status-${task.id}`}>
                        Update status for {task.task}
                      </label>
                      <select
                        id={`status-${task.id}`}
                        disabled={updatingTaskId === task.id}
                        value={task.status}
                        onChange={(event) => handleStatusChange(task.id, event.target.value as typeof task.status)}
                        className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm text-slate-900 shadow-sm transition focus:border-wedding-rose/60 focus:outline-none focus:ring-2 focus:ring-wedding-rose/20 disabled:opacity-60 dark:border-white/15 dark:bg-white/15 dark:text-white dark:shadow-inner dark:focus:border-white/40 dark:focus:ring-white/40"
                      >
                        {STATUS_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value} className="text-slate-900">
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </article>
                ))
              )}
            </div>
          </section>

          <aside className={`${glassPanelClass} flex h-full flex-col gap-4 p-6 dark:shadow-[0_30px_50px_-40px_rgba(236,72,153,0.6)]`}>
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Planner forms</h2>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-200/70">Complete these before your next sync to keep planners unblocked.</p>
            </div>

            <div className="space-y-3 overflow-y-auto pr-1 text-sm">
              {dashboard.forms.pending.length === 0 && dashboard.forms.completed.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-200/70">
                  No planner questionnaires to complete right now.
                </div>
              ) : (
                <ul className="space-y-3">
                  {dashboard.forms.pending.map((form) => (
                    <li key={form.id} className={`${glassSoftPanelClass} p-4`}>
                      <p className="text-sm font-semibold text-slate-900 dark:text-white">{form.form_name}</p>
                      <p className="mt-1 text-xs text-slate-500 dark:text-slate-200/70">{form.wedding_name}</p>
                      <p className="mt-1 text-xs text-slate-500 dark:text-slate-200/60">Sent {formatDisplayDate(form.sent_at)}</p>
                      {form.access_token && (
                        <a
                          href={`/vendor-form/${form.id}?token=${form.access_token}`}
                          className="mt-3 inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-900 transition hover:border-slate-400 hover:bg-slate-50 dark:border-white/15 dark:bg-white/15 dark:text-white dark:hover:border-white/40 dark:hover:bg-white/25"
                        >
                          Open form
                        </a>
                      )}
                    </li>
                  ))}

                  {dashboard.forms.completed.length > 0 && (
                    <li className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-200/70">
                      <p className="font-semibold text-slate-900 dark:text-white">Completed</p>
                      <ul className="mt-2 space-y-2">
                        {dashboard.forms.completed.map((form) => (
                          <li key={form.id} className="flex items-center justify-between gap-2">
                            <span>{form.form_name}</span>
                            <span className="rounded-full border border-emerald-300/40 bg-emerald-200/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-100">
                              Submitted {formatDisplayDate(form.submitted_at)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </li>
                  )}
                </ul>
              )}
            </div>
          </aside>
        </main>

        <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {dashboard.weddings.map((wedding) => (
            <div
              key={wedding.id}
              className={`${glassPanelClass} flex flex-col gap-3 p-5 dark:shadow-[0_20px_40px_-40px_rgba(96,165,250,0.8)]`}
            >
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-base font-semibold text-slate-900 dark:text-white">{wedding.name}</h3>
                <span className={pillClass}>
                  {wedding.status.replace('_', ' ')}
                </span>
              </div>
              <p className="text-sm text-slate-600 dark:text-slate-200/70">{wedding.location || 'Location pending'}</p>
              <p className="text-xs text-slate-500 dark:text-slate-200/60">Event date {formatDisplayDate(wedding.date)}</p>
              <div className="flex items-center gap-3 text-xs text-slate-600 dark:text-slate-200/70">
                <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 dark:border-white/10 dark:bg-white/10">
                  {wedding.tasks_completed}/{wedding.tasks_total} tasks complete
                </span>
              </div>
            </div>
          ))}

          {dashboard.weddings.length === 0 && (
            <div className="rounded-3xl border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-200/70">
              You’re not assigned to any weddings yet. Invitations from planners will appear here the moment they’re sent.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
