'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import PageHeader from '@/components/ui/PageHeader';
import {
  CalendarDays,
  CheckCircle2,
  Copy,
  Download,
  Filter,
  Image as ImageIcon,
  Images,
  Link2,
  Loader2,
  PlayCircle,
  QrCode,
  RefreshCcw,
  RotateCw,
  Search,
  Video,
  XCircle,
} from 'lucide-react';
import {
  NOT_SURE_EVENT_VALUE,
  createCoupleMemoriesExport,
  fetchCoupleMemories,
  fetchCoupleMemoriesExport,
  fetchCoupleMemoriesQrBlob,
  fetchCoupleMemoriesSettings,
  fetchCoupleMemoryDownload,
  reviewCoupleMemory,
  rotateCoupleMemoriesLink,
  updateCoupleMemoriesSettings,
  type CoupleMemoriesExportJob,
  type CoupleMemoriesListResponse,
  type CoupleMemoryAsset,
  type GuestMemoriesSettings,
  type GuestMemoriesSummary,
} from '@/services/guestMemoriesApi';
import { getWeddingEventLabel } from '@/utils/weddingEvents';
import GuestMemoriesSummaryCard from '@/components/guest-memories/GuestMemoriesSummaryCard';

type ReviewFilter = 'all' | 'pending' | 'kept' | 'rejected';
type MediaFilter = 'all' | 'image' | 'video';

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

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

interface CoupleMemoriesSectionProps {
  archived: boolean;
  initialSummary?: GuestMemoriesSummary | null;
  onUpdated: () => void;
}

export default function CoupleMemoriesSection({
  archived,
  initialSummary,
  onUpdated,
}: CoupleMemoriesSectionProps) {
  const [settings, setSettings] = useState<GuestMemoriesSettings | null>(null);
  const [listData, setListData] = useState<CoupleMemoriesListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>('pending');
  const [mediaFilter, setMediaFilter] = useState<MediaFilter>('all');
  const [eventFilter, setEventFilter] = useState('all');
  const [uploaderInput, setUploaderInput] = useState('');
  const [uploaderQuery, setUploaderQuery] = useState('');
  const [page, setPage] = useState(1);
  const [savingSettings, setSavingSettings] = useState(false);
  const [closeDate, setCloseDate] = useState('');
  const [qrUrl, setQrUrl] = useState<string | null>(null);
  const [activeVideo, setActiveVideo] = useState<CoupleMemoryAsset | null>(null);
  const [workingAssetId, setWorkingAssetId] = useState<string | null>(null);
  const [exportJob, setExportJob] = useState<CoupleMemoriesExportJob | null>(null);
  const [exporting, setExporting] = useState(false);
  const hasLoadedMemoriesRef = useRef(false);

  useEffect(() => {
    return () => {
      if (qrUrl) {
        URL.revokeObjectURL(qrUrl);
      }
    };
  }, [qrUrl]);

  useEffect(() => {
    if (!exportJob || exportJob.status === 'completed' || exportJob.status === 'failed') {
      return undefined;
    }

    const interval = window.setInterval(async () => {
      try {
        const latest = await fetchCoupleMemoriesExport(exportJob.id);
        setExportJob(latest);
      } catch {
        // Keep polling until explicit failure.
      }
    }, 4000);

    return () => window.clearInterval(interval);
  }, [exportJob]);

  useEffect(() => {
    if (settings?.upload_closes_at) {
      const date = new Date(settings.upload_closes_at);
      if (!Number.isNaN(date.getTime())) {
        setCloseDate(date.toISOString().slice(0, 10));
      }
    }
  }, [settings?.upload_closes_at]);

  const summary = listData?.summary || settings || initialSummary;

  const loadMemories = useCallback(async (showLoader = false) => {
    if (showLoader) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }

    try {
      const nextList = await fetchCoupleMemories({
        reviewStatus: reviewFilter,
        mediaType: mediaFilter,
        eventType: eventFilter,
        uploaderQuery: uploaderQuery || undefined,
        page,
      });
      setListData(nextList);
      onUpdated();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not refresh memories.';
      toast.error(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [eventFilter, mediaFilter, onUpdated, page, reviewFilter, uploaderQuery]);

  const refreshData = useCallback(async (showLoader = false) => {
    if (showLoader) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }

    try {
      const [nextSettings, nextList] = await Promise.all([
        fetchCoupleMemoriesSettings(),
        fetchCoupleMemories({
          reviewStatus: reviewFilter,
          mediaType: mediaFilter,
          eventType: eventFilter,
          uploaderQuery: uploaderQuery || undefined,
          page,
        }),
      ]);
      setSettings(nextSettings);
      setListData(nextList);
      hasLoadedMemoriesRef.current = true;
      onUpdated();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not load guest memories.';
      toast.error(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [eventFilter, mediaFilter, onUpdated, page, reviewFilter, uploaderQuery]);

  const initializeData = useCallback(async () => {
    setLoading(true);
    try {
      const [nextSettings, nextList] = await Promise.all([
        fetchCoupleMemoriesSettings(),
        fetchCoupleMemories({
          reviewStatus: 'pending',
          mediaType: 'all',
          eventType: 'all',
          page: 1,
        }),
      ]);
      setSettings(nextSettings);
      setListData(nextList);
      hasLoadedMemoriesRef.current = true;
      onUpdated();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not load guest memories.';
      toast.error(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [onUpdated]);

  useEffect(() => {
    void initializeData();
  }, [initializeData]);

  useEffect(() => {
    if (hasLoadedMemoriesRef.current) {
      void loadMemories(false);
    }
  }, [loadMemories]);

  const handleSearchSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextQuery = uploaderInput.trim();
    if (page === 1 && nextQuery === uploaderQuery) {
      await loadMemories(false);
      return;
    }

    setPage(1);
    setUploaderQuery(nextQuery);
  };

  const handleCopyLink = async () => {
    if (!settings?.upload_url) return;
    try {
      await navigator.clipboard.writeText(settings.upload_url);
      toast.success('Guest upload link copied.');
    } catch {
      toast.error('Could not copy the link on this device.');
    }
  };

  const handleRotateLink = async () => {
    if (!window.confirm('Rotate the guest upload link? Old QR codes will stop working immediately.')) {
      return;
    }
    setSavingSettings(true);
    try {
      const nextSettings = await rotateCoupleMemoriesLink();
      setSettings(nextSettings);
      toast.success('Guest upload link rotated.');
      await loadMemories(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not rotate the guest upload link.';
      toast.error(message);
    } finally {
      setSavingSettings(false);
    }
  };

  const handleToggleOpen = async () => {
    if (!settings) return;
    setSavingSettings(true);
    try {
      const nextSettings = await updateCoupleMemoriesSettings({
        enabled: !settings.enabled,
      });
      setSettings(nextSettings);
      toast.success(nextSettings.enabled ? 'Guest uploads reopened.' : 'Guest uploads closed.');
      await loadMemories(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not update guest upload availability.';
      toast.error(message);
    } finally {
      setSavingSettings(false);
    }
  };

  const handleSaveCloseDate = async () => {
    if (!closeDate) {
      toast.error('Choose a closing date first.');
      return;
    }

    setSavingSettings(true);
    try {
      const nextSettings = await updateCoupleMemoriesSettings({
        upload_closes_at: new Date(`${closeDate}T23:59:59`).toISOString(),
      });
      setSettings(nextSettings);
      toast.success('Upload close date updated.');
      await loadMemories(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not update the close date.';
      toast.error(message);
    } finally {
      setSavingSettings(false);
    }
  };

  const handleGenerateQr = async () => {
    try {
      const blob = await fetchCoupleMemoriesQrBlob();
      if (qrUrl) {
        URL.revokeObjectURL(qrUrl);
      }
      const nextUrl = URL.createObjectURL(blob);
      setQrUrl(nextUrl);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not generate the QR code.';
      toast.error(message);
    }
  };

  const handleReview = async (assetId: string, reviewStatus: 'pending' | 'kept' | 'rejected') => {
    setWorkingAssetId(assetId);
    try {
      await reviewCoupleMemory(assetId, reviewStatus);
      toast.success(`Marked as ${reviewStatus}.`);
      await loadMemories(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not update the memory review status.';
      toast.error(message);
    } finally {
      setWorkingAssetId(null);
    }
  };

  const handleDownload = async (assetId: string) => {
    setWorkingAssetId(assetId);
    try {
      const payload = await fetchCoupleMemoryDownload(assetId);
      window.open(payload.download_url, '_blank', 'noopener,noreferrer');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not prepare the download.';
      toast.error(message);
    } finally {
      setWorkingAssetId(null);
    }
  };

  const handleCreateExport = async () => {
    setExporting(true);
    try {
      const payload = await createCoupleMemoriesExport({ review_status: 'kept' });
      const latest = await fetchCoupleMemoriesExport(payload.export_id);
      setExportJob(latest);
      toast.success('Export started. We’ll keep checking until it is ready.');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not start the export.';
      toast.error(message);
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <PageHeader title="Memories" description="Private guest-uploaded photos and videos for your wedding." />
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-indigo-500" />
          <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">Loading your guest memories...</p>
        </div>
      </div>
    );
  }

  const eventOptions = settings?.event_options ?? [];

  return (
    <div className="space-y-6">
      <PageHeader title="Memories" description="Review guest uploads, keep the best moments, and share a QR code at the event.">
        <button
          type="button"
          onClick={() => void refreshData(false)}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
        >
          {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
          Refresh
        </button>
      </PageHeader>

      {archived && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200">
          Your wedding is archived, but guest memories remain available here for review and downloads.
        </div>
      )}

      {!settings?.storage_ready && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/30 dark:bg-red-950/30 dark:text-red-200">
          {settings?.storage_issue ||
            'Guest media storage is not configured or is currently inaccessible. Restore the guest memories bucket and signer before opening uploads to guests.'}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-4">
        <GuestMemoriesSummaryCard icon={Images} title="Pending review" value={String(summary?.pending_count ?? 0)} subtitle="New uploads waiting for a decision" accent="indigo" />
        <GuestMemoriesSummaryCard icon={CheckCircle2} title="Kept" value={String(summary?.kept_count ?? 0)} subtitle="Saved to the couple library" accent="emerald" />
        <GuestMemoriesSummaryCard icon={XCircle} title="Rejected" value={String(summary?.rejected_count ?? 0)} subtitle="Hidden from the main library" accent="rose" />
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
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Guest upload link</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Share this link or QR sign so guests can send you photos and videos during the event.
              </p>
            </div>
            <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
              settings?.enabled ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300' : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
            }`}>
              {settings?.enabled ? 'Open' : 'Closed'}
            </span>
          </div>

          <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/60">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
              <Link2 className="h-3.5 w-3.5" />
              Active link
            </div>
            <p className="mt-3 break-all text-sm text-slate-700 dark:text-slate-200">{settings?.upload_url}</p>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
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
              onClick={handleToggleOpen}
              disabled={savingSettings}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              {savingSettings ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
              {settings?.enabled ? 'Close uploads' : 'Reopen uploads'}
            </button>
            <button
              type="button"
              onClick={handleRotateLink}
              disabled={savingSettings}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              {savingSettings ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCw className="h-4 w-4" />}
              Rotate link
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
              disabled={savingSettings}
              className="mt-[1.7rem] inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100"
            >
              {savingSettings ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarDays className="h-4 w-4" />}
              Save date
            </button>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Export and playback</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Videos are processed for smoother playback. Export builds a ZIP of your kept memories.
              </p>
            </div>
            <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
              settings?.stream_configured ? 'bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
            }`}>
              {settings?.stream_configured ? 'Stream ready' : 'R2 only'}
            </span>
          </div>

          <div className="mt-5 space-y-4">
            <button
              type="button"
              onClick={handleCreateExport}
              disabled={exporting || !summary?.kept_count}
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              Export kept memories
            </button>

            {exportJob && (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm dark:border-slate-700 dark:bg-slate-900/60">
                <p className="font-semibold text-slate-900 dark:text-white">Latest export</p>
                <p className="mt-1 text-slate-500 dark:text-slate-400">
                  Status: <span className="font-medium text-slate-900 dark:text-white">{exportJob.status}</span>
                  {' · '}
                  {exportJob.asset_count} asset{exportJob.asset_count === 1 ? '' : 's'}
                </p>
                {exportJob.status === 'completed' && exportJob.download_url && (
                  <button
                    type="button"
                    onClick={() => window.open(exportJob.download_url, '_blank', 'noopener,noreferrer')}
                    className="mt-3 inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                  >
                    <Download className="h-4 w-4" /> Download ZIP
                  </button>
                )}
                {exportJob.status === 'failed' && exportJob.error && (
                  <p className="mt-3 text-sm text-red-600 dark:text-red-300">{exportJob.error}</p>
                )}
              </div>
            )}

            {qrUrl && (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-center dark:border-slate-700 dark:bg-slate-900/60">
                <img src={qrUrl} alt="Guest memories QR code" className="mx-auto rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800" />
                <button
                  type="button"
                  onClick={() => {
                    const anchor = document.createElement('a');
                    anchor.href = qrUrl;
                    anchor.download = 'guest-memories-qr.png';
                    anchor.click();
                  }}
                  className="mt-4 inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                >
                  <Download className="h-4 w-4" /> Download QR
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Review queue</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Filter by status, media type, event, or guest name. Keep the best uploads and reject the rest.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-600 dark:bg-slate-900 dark:text-slate-300">
            <Filter className="h-3.5 w-3.5" />
            {listData?.total ?? 0} total
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          {(['pending', 'kept', 'rejected', 'all'] as ReviewFilter[]).map((filter) => (
            <button
              key={filter}
              type="button"
              onClick={() => { setPage(1); setReviewFilter(filter); }}
              className={`rounded-full px-3 py-2 text-sm font-semibold transition ${
                reviewFilter === filter
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-700'
              }`}
            >
              {filter === 'all' ? 'All' : filter[0].toUpperCase() + filter.slice(1)}
            </button>
          ))}
        </div>

        <div className="mt-5 grid gap-3 lg:grid-cols-[0.8fr,0.7fr,0.8fr,1.2fr]">
          <label className="block">
            <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">Media type</span>
            <select
              value={mediaFilter}
              onChange={(event) => { setPage(1); setMediaFilter(event.target.value as MediaFilter); }}
              className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:focus:ring-indigo-500/10"
            >
              <option value="all">All media</option>
              <option value="image">Photos</option>
              <option value="video">Videos</option>
            </select>
          </label>

          <label className="block">
            <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">Event</span>
            <select
              value={eventFilter}
              onChange={(event) => { setPage(1); setEventFilter(event.target.value); }}
              className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:focus:ring-indigo-500/10"
            >
              <option value="all">All events</option>
              {eventOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.value === NOT_SURE_EVENT_VALUE
                    ? option.label
                    : getWeddingEventLabel(option.value, option.label !== option.value ? option.label : undefined)}
                </option>
              ))}
            </select>
          </label>

          <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-300">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">Processing</p>
            <p className="mt-2 text-lg font-semibold text-slate-900 dark:text-white">{summary?.processing_videos ?? 0}</p>
            <p className="mt-1 text-xs">Videos still preparing for playback</p>
          </div>

          <form onSubmit={(event) => void handleSearchSubmit(event)} className="block">
            <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">Guest name</span>
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={uploaderInput}
                  onChange={(event) => setUploaderInput(event.target.value)}
                  placeholder="Search uploader"
                  className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-10 pr-4 text-sm text-slate-900 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-100 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:focus:ring-indigo-500/10"
                />
              </div>
              <button
                type="submit"
                className="rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100"
              >
                Go
              </button>
            </div>
          </form>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {listData?.items.length ? (
          listData.items.map((asset) => (
            <MemoryCard
              key={asset.id}
              asset={asset}
              eventOptions={eventOptions}
              working={workingAssetId === asset.id}
              onKeep={() => void handleReview(asset.id, 'kept')}
              onReject={() => void handleReview(asset.id, 'rejected')}
              onReset={() => void handleReview(asset.id, 'pending')}
              onDownload={() => void handleDownload(asset.id)}
              onOpenVideo={() => setActiveVideo(asset)}
            />
          ))
        ) : (
          <div className="col-span-full rounded-xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center text-sm text-slate-500 shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
            No memories matched the current filters yet.
          </div>
        )}
      </div>

      {listData && listData.pages > 1 && (
        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Page {listData.page} of {listData.pages}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              disabled={listData.page <= 1}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-700"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => setPage((current) => Math.min(listData.pages, current + 1))}
              disabled={listData.page >= listData.pages}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-700"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {activeVideo?.player_url && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 px-4 py-8">
          <div className="w-full max-w-5xl rounded-2xl bg-white p-4 shadow-2xl dark:bg-slate-900">
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">{activeVideo.original_filename}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">{activeVideo.uploader_name}</p>
              </div>
              <button
                type="button"
                onClick={() => setActiveVideo(null)}
                className="rounded-full border border-slate-200 p-2 text-slate-500 transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-700 dark:border-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>
            <div className="aspect-video overflow-hidden rounded-xl bg-slate-950">
              <iframe
                src={activeVideo.player_url}
                title={activeVideo.original_filename}
                allow="accelerometer; gyroscope; autoplay; encrypted-media; picture-in-picture;"
                allowFullScreen
                className="h-full w-full border-0"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MemoryCard({
  asset,
  eventOptions,
  working,
  onKeep,
  onReject,
  onReset,
  onDownload,
  onOpenVideo,
}: {
  asset: CoupleMemoryAsset;
  eventOptions: GuestMemoriesSettings['event_options'];
  working: boolean;
  onKeep: () => void;
  onReject: () => void;
  onReset: () => void;
  onDownload: () => void;
  onOpenVideo: () => void;
}) {
  const eventOption = eventOptions.find((option) => option.value === asset.event_type);
  const eventName = asset.event_type === NOT_SURE_EVENT_VALUE
    ? 'Not sure'
    : getWeddingEventLabel(asset.event_type, eventOption && eventOption.label !== asset.event_type ? eventOption.label : undefined);

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className="relative">
        {asset.media_type === 'image' && asset.preview_url ? (
          <img src={asset.preview_url} alt={asset.original_filename} className="h-56 w-full object-cover" />
        ) : (
          <button
            type="button"
            onClick={onOpenVideo}
            disabled={!asset.player_url}
            className="group flex h-56 w-full items-center justify-center bg-slate-950 text-white disabled:cursor-not-allowed"
          >
            {asset.thumbnail_url ? (
              <img src={asset.thumbnail_url} alt={asset.original_filename} className="absolute inset-0 h-full w-full object-cover opacity-70" />
            ) : null}
            <div className="relative flex flex-col items-center gap-2">
              <PlayCircle className="h-12 w-12 transition group-hover:scale-105" />
              <span className="text-sm font-semibold">
                {asset.stream_status === 'ready'
                  ? 'Play video'
                  : asset.stream_status === 'queued' || asset.stream_status === 'ingesting' || asset.stream_status === 'processing'
                    ? 'Processing video'
                    : 'Video upload'}
              </span>
            </div>
          </button>
        )}

        <div className="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full bg-slate-950/70 px-2.5 py-1 text-xs font-semibold text-white">
          {asset.media_type === 'image' ? <ImageIcon className="h-3.5 w-3.5" /> : <Video className="h-3.5 w-3.5" />}
          {asset.media_type === 'image' ? 'Photo' : 'Video'}
        </div>
      </div>

      <div className="space-y-4 p-4">
        <div>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-white">{asset.original_filename}</p>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                {asset.uploader_name} • {formatBytes(asset.size_bytes)}
              </p>
            </div>
            <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold ${
              asset.review_status === 'kept'
                ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
                : asset.review_status === 'rejected'
                  ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300'
                  : 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
            }`}>
              {asset.review_status}
            </span>
          </div>
          <p className="mt-2 text-xs font-medium uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">Event</p>
          <p className="mt-1 text-sm text-slate-700 dark:text-slate-200">{eventName}</p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onKeep}
            disabled={working}
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:opacity-60"
          >
            {working ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            Keep
          </button>
          <button
            type="button"
            onClick={onReject}
            disabled={working}
            className="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-rose-700 disabled:opacity-60"
          >
            {working ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
            Reject
          </button>
          <button
            type="button"
            onClick={onReset}
            disabled={working}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-700"
          >
            Pending
          </button>
          <button
            type="button"
            onClick={onDownload}
            disabled={working}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-700"
          >
            <Download className="h-4 w-4" /> Download
          </button>
        </div>

        <p className="text-xs text-slate-500 dark:text-slate-400">
          Uploaded {formatDateLabel(asset.uploaded_at)}
          {asset.media_type === 'video' && ['queued', 'ingesting', 'processing'].includes(asset.stream_status || '')
            ? ' • Stream processing in progress'
            : ''}
        </p>
      </div>
    </div>
  );
}
