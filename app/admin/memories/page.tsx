'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';
import { formatDate } from '@/utils/dateFormat';
import { getWeddingEventLabel } from '@/utils/weddingEvents';
import PageHeader from '../components/PageHeader';
import GuestMemoriesSummaryCard from '@/components/guest-memories/GuestMemoriesSummaryCard';
import {
  CalendarDays,
  CheckCircle2,
  Copy,
  Download,
  ExternalLink,
  Images,
  Info,
  Link2,
  Loader2,
  QrCode,
  RefreshCcw,
  RotateCw,
  XCircle,
} from 'lucide-react';
import {
  NOT_SURE_EVENT_VALUE,
  fetchPlannerMemoriesQrBlob,
  fetchPlannerMemoriesSettings,
  fetchPlannerMemoriesSignPdfBlob,
  rotatePlannerMemoriesLink,
  updatePlannerMemoriesSettings,
  type GuestMemoriesSettings,
} from '@/services/guestMemoriesApi';

interface WeddingOption {
  id?: string;
  _id?: string;
  couple_names: string;
  slug: string;
  date?: string;
}

function formatDateLabel(value?: string | null): string {
  if (!value) return 'Not set';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Not set';
  return date.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1_000);
}

export default function AdminGuestMemoriesPage() {
  const { token } = useAdmin();
  const [weddings, setWeddings] = useState<WeddingOption[]>([]);
  const [selectedWedding, setSelectedWedding] = useState('');
  const [settings, setSettings] = useState<GuestMemoriesSettings | null>(null);
  const [loadingWeddings, setLoadingWeddings] = useState(true);
  const [loadingSettings, setLoadingSettings] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [qrUrl, setQrUrl] = useState<string | null>(null);
  const [closeDate, setCloseDate] = useState('');

  useEffect(() => {
    return () => {
      if (qrUrl) {
        URL.revokeObjectURL(qrUrl);
      }
    };
  }, [qrUrl]);

  const selectedWeddingData = useMemo(
    () => weddings.find((wedding) => (wedding.id || wedding._id) === selectedWedding) || null,
    [selectedWedding, weddings],
  );

  const loadWeddings = useCallback(async () => {
    if (!token) return;

    setLoadingWeddings(true);
    try {
      const response = await fetch(`${getApiBaseUrl()}/admin/planner/weddings?page=1&limit=200`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        cache: 'no-store',
      });

      if (!response.ok) {
        throw new Error('Could not load planner weddings.');
      }

      const payload = await response.json();
      const nextWeddings = Array.isArray(payload) ? payload : payload.weddings || [];
      setWeddings(nextWeddings);
      setSelectedWedding((current) => current || nextWeddings[0]?.id || nextWeddings[0]?._id || '');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not load planner weddings.';
      toast.error(message);
    } finally {
      setLoadingWeddings(false);
    }
  }, [token]);

  const loadSettings = useCallback(async (showLoader = false) => {
    if (!token || !selectedWedding) {
      setSettings(null);
      return;
    }

    if (showLoader) {
      setLoadingSettings(true);
    } else {
      setRefreshing(true);
    }

    try {
      const nextSettings = await fetchPlannerMemoriesSettings(token, selectedWedding);
      setSettings(nextSettings);
      if (nextSettings.upload_closes_at) {
        const date = new Date(nextSettings.upload_closes_at);
        if (!Number.isNaN(date.getTime())) {
          setCloseDate(date.toISOString().slice(0, 10));
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not load guest memories.';
      toast.error(message);
    } finally {
      setLoadingSettings(false);
      setRefreshing(false);
    }
  }, [selectedWedding, token]);

  useEffect(() => {
    void loadWeddings();
  }, [loadWeddings]);

  useEffect(() => {
    setQrUrl((current) => {
      if (current) {
        URL.revokeObjectURL(current);
      }
      return null;
    });
    void loadSettings(true);
  }, [loadSettings]);

  const handleCopyLink = async () => {
    if (!settings?.upload_url) return;
    try {
      await navigator.clipboard.writeText(settings.upload_url);
      toast.success('Guest upload link copied.');
    } catch {
      toast.error('Could not copy the link on this device.');
    }
  };

  const handleGenerateQr = async () => {
    if (!token || !selectedWedding) return;

    try {
      const blob = await fetchPlannerMemoriesQrBlob(token, selectedWedding);
      if (qrUrl) {
        URL.revokeObjectURL(qrUrl);
      }
      setQrUrl(URL.createObjectURL(blob));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not generate the QR code.';
      toast.error(message);
    }
  };

  const handleDownloadSign = async () => {
    if (!token || !selectedWedding || !settings) return;

    try {
      const blob = await fetchPlannerMemoriesSignPdfBlob(token, selectedWedding);
      triggerBlobDownload(blob, `${settings.wedding.slug || 'wedding'}-guest-memories-sign.pdf`);
      toast.success('Printable sign downloaded.');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not download the sign PDF.';
      toast.error(message);
    }
  };

  const handleRotateLink = async () => {
    if (!token || !selectedWedding) return;
    if (!window.confirm('Rotate the guest upload link? Existing QR signs and shared links will stop working immediately.')) {
      return;
    }

    setSaving(true);
    try {
      const nextSettings = await rotatePlannerMemoriesLink(token, selectedWedding);
      setSettings(nextSettings);
      toast.success('Guest upload link rotated.');
      await loadSettings(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not rotate the guest upload link.';
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  const handleToggleOpen = async () => {
    if (!token || !selectedWedding || !settings) return;

    setSaving(true);
    try {
      const nextSettings = await updatePlannerMemoriesSettings(token, selectedWedding, {
        enabled: !settings.enabled,
      });
      setSettings(nextSettings);
      toast.success(nextSettings.enabled ? 'Guest uploads reopened.' : 'Guest uploads closed.');
      await loadSettings(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not update guest upload availability.';
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveCloseDate = async () => {
    if (!token || !selectedWedding) return;
    if (!closeDate) {
      toast.error('Choose a closing date first.');
      return;
    }

    setSaving(true);
    try {
      const nextSettings = await updatePlannerMemoriesSettings(token, selectedWedding, {
        upload_closes_at: new Date(`${closeDate}T23:59:59`).toISOString(),
      });
      setSettings(nextSettings);
      toast.success('Upload close date updated.');
      await loadSettings(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not update the close date.';
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  if (loadingWeddings) {
    return (
      <div className="space-y-4">
        <PageHeader title="Guest Memories" description="Planner-managed QR and sign distribution for guest uploads." />
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-indigo-500" />
          <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">Loading planner weddings...</p>
        </div>
      </div>
    );
  }

  if (!weddings.length) {
    return (
      <div className="space-y-6">
        <PageHeader title="Guest Memories" description="Planner-managed QR and sign distribution for guest uploads." />
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center text-sm text-slate-500 shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
          Add or assign a wedding first. Guest memories operations appear here once a planner wedding is available.
        </div>
      </div>
    );
  }

  const summary = settings;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Guest Memories"
        description="Run guest photo and video collection from the planner dashboard while the couple keeps private review control."
      >
        <button
          type="button"
          onClick={() => void loadSettings(false)}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
        >
          {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
          Refresh
        </button>
      </PageHeader>

      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <div className="grid gap-4 lg:grid-cols-[1.2fr,0.8fr]">
          <label className="block">
            <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">Wedding</span>
            <select
              value={selectedWedding}
              onChange={(event) => setSelectedWedding(event.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:focus:ring-indigo-500/10"
            >
              {weddings.map((wedding) => {
                const weddingId = wedding.id || wedding._id || '';
                return (
                  <option key={weddingId} value={weddingId}>
                    {wedding.couple_names}
                  </option>
                );
              })}
            </select>
          </label>

          <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-300">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">Wedding profile</p>
            <p className="mt-2 text-base font-semibold text-slate-900 dark:text-white">
              {selectedWeddingData?.couple_names || settings?.wedding.couple_names || 'Selected wedding'}
            </p>
            <p className="mt-1 text-xs">
              {selectedWeddingData?.date
                ? `Date: ${formatDate(selectedWeddingData.date, { month: 'long', day: 'numeric', year: 'numeric' })}`
                : 'Date not set'}
              {settings?.wedding.slug ? ` • /${settings.wedding.slug}` : ''}
            </p>
          </div>
        </div>
      </div>

      {loadingSettings ? (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-indigo-500" />
          <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">Loading guest memories operations...</p>
        </div>
      ) : settings ? (
        <>
          {!settings.storage_ready && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/30 dark:bg-red-950/30 dark:text-red-200">
              {settings.storage_issue ||
                'Guest media storage is not configured or is currently inaccessible. Restore the dedicated guest memories bucket and signer before opening uploads to guests.'}
            </div>
          )}

          <div className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-800 dark:border-indigo-900/40 dark:bg-indigo-950/30 dark:text-indigo-200">
            <div className="flex items-start gap-3">
              <Info className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                Planners own the rollout here: link distribution, QR signage, close dates, and rotations. Couples still own private review, keep/reject decisions, and downloads inside their portal.
              </p>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-4">
            <GuestMemoriesSummaryCard icon={Images} title="Pending review" value={String(summary?.pending_count ?? 0)} subtitle="Uploads waiting in the couple portal" accent="indigo" />
            <GuestMemoriesSummaryCard icon={CheckCircle2} title="Kept" value={String(summary?.kept_count ?? 0)} subtitle="Memories the couple has already saved" accent="emerald" />
            <GuestMemoriesSummaryCard icon={XCircle} title="Rejected" value={String(summary?.rejected_count ?? 0)} subtitle="Uploads removed from the main library" accent="rose" />
            <GuestMemoriesSummaryCard
              icon={CalendarDays}
              title="Upload window"
              value={summary?.link_status === 'open' ? 'Open' : 'Closed'}
              subtitle={`Closes ${formatDateLabel(summary?.upload_closes_at)}`}
              accent={summary?.link_status === 'open' ? 'amber' : 'slate'}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Distribution toolkit</h2>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    Share one operational link across signage, welcome tables, programs, and post-event follow-up messages.
                  </p>
                </div>
                <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
                  settings.enabled
                    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
                    : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                }`}>
                  {settings.enabled ? 'Open' : 'Closed'}
                </span>
              </div>

              <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/60">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
                  <Link2 className="h-3.5 w-3.5" />
                  Active link
                </div>
                <p className="mt-3 break-all text-sm text-slate-700 dark:text-slate-200">{settings.upload_url}</p>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <button
                  type="button"
                  onClick={handleCopyLink}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700"
                >
                  <Copy className="h-4 w-4" /> Copy link
                </button>
                <button
                  type="button"
                  onClick={handleGenerateQr}
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  <QrCode className="h-4 w-4" /> Generate QR
                </button>
                <button
                  type="button"
                  onClick={handleDownloadSign}
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  <Download className="h-4 w-4" /> Printable sign PDF
                </button>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-[1fr_auto]">
                <label className="block">
                  <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">Uploads close on</span>
                  <input
                    type="date"
                    value={closeDate}
                    onChange={(event) => setCloseDate(event.target.value)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:focus:ring-indigo-500/10"
                  />
                </label>
                <button
                  type="button"
                  onClick={handleSaveCloseDate}
                  disabled={saving}
                  className="mt-[1.7rem] inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100"
                >
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarDays className="h-4 w-4" />}
                  Save date
                </button>
              </div>
            </div>

            <div className="space-y-6">
              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Operational controls</h2>
                    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                      Close or reopen access during the event, and rotate the link if a printed QR sign needs to be reissued.
                    </p>
                  </div>
                  <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
                    settings.stream_configured
                      ? 'bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300'
                      : 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
                  }`}>
                    {settings.stream_configured ? 'Stream ready' : 'R2 only'}
                  </span>
                </div>

                <div className="mt-5 space-y-3">
                  <button
                    type="button"
                    onClick={handleToggleOpen}
                    disabled={saving}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                  >
                    {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
                    {settings.enabled ? 'Close uploads now' : 'Reopen uploads'}
                  </button>
                  <button
                    type="button"
                    onClick={handleRotateLink}
                    disabled={saving}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                  >
                    {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCw className="h-4 w-4" />}
                    Rotate link and QR
                  </button>
                  <a
                    href={settings.upload_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                  >
                    <ExternalLink className="h-4 w-4" /> Preview guest upload page
                  </a>
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Event coverage</h2>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  Guests can tag uploads to any configured event, or choose “Not sure” when they cannot place the moment.
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {settings.event_options.map((option) => (
                    <span
                      key={option.value}
                      className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:bg-slate-900 dark:text-slate-200"
                    >
                      {option.value === NOT_SURE_EVENT_VALUE
                        ? option.label
                        : getWeddingEventLabel(option.value, option.label !== option.value ? option.label : undefined)}
                    </span>
                  ))}
                </div>
                <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-300">
                  <p>
                    Processing videos: <span className="font-semibold text-slate-900 dark:text-white">{settings.processing_videos}</span>
                  </p>
                  <p className="mt-1">
                    The couple portal handles the private moderation queue and final downloads.
                  </p>
                </div>
              </div>

              {qrUrl && (
                <div className="rounded-xl border border-slate-200 bg-white p-5 text-center shadow-sm dark:border-slate-700 dark:bg-slate-800">
                  <img src={qrUrl} alt="Guest memories QR code" className="mx-auto rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900" />
                  <button
                    type="button"
                    onClick={async () => {
                      if (!token || !selectedWedding || !settings) return;
                      try {
                        const blob = await fetchPlannerMemoriesQrBlob(token, selectedWedding);
                        triggerBlobDownload(blob, `${settings.wedding.slug || 'wedding'}-guest-memories-qr.png`);
                      } catch (error) {
                        const message = error instanceof Error ? error.message : 'Could not download the QR code.';
                        toast.error(message);
                      }
                    }}
                    className="mt-4 inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                  >
                    <Download className="h-4 w-4" /> Download QR
                  </button>
                </div>
              )}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
