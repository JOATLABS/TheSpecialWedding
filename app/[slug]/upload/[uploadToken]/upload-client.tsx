'use client';

import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  Camera,
  CheckCircle2,
  HelpCircle,
  ImagePlus,
  Loader2,
  RefreshCcw,
  UploadCloud,
  User,
  Video,
  X,
} from 'lucide-react';

import { BrandLockup } from '@/components/brand/BrandLockup';
import {
  NOT_SURE_EVENT_VALUE,
  createPublicGuestMemoriesUploadPlan,
  fetchPublicGuestMemoriesContext,
  finalizePublicGuestMemoriesUpload,
  type GuestMemoriesEventOption,
  type PublicGuestMemoriesContext,
} from '@/services/guestMemoriesApi';
import { getWeddingEventLabel } from '@/utils/weddingEvents';

type UploadStep = 0 | 1 | 2;
type UploadFileStatus = 'ready' | 'uploading' | 'uploaded' | 'finalizing' | 'saved' | 'failed';

interface SelectedUploadFile {
  id: string;
  file: File;
  previewUrl: string;
  eventType: string;
  mediaType: 'image' | 'video';
  status: UploadFileStatus;
  assetId?: string;
  error?: string;
}

const STEP_ITEMS = [
  { id: 0 as UploadStep, label: 'Your name', icon: User },
  { id: 1 as UploadStep, label: 'Event', icon: CalendarDays },
  { id: 2 as UploadStep, label: 'Upload', icon: UploadCloud },
];

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatDateLabel(value?: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

function eventLabel(option: GuestMemoriesEventOption): string {
  if (option.value === NOT_SURE_EVENT_VALUE) {
    return option.label;
  }
  return getWeddingEventLabel(option.value, option.label !== option.value ? option.label : undefined);
}

function buildPreviewType(file: File): 'image' | 'video' {
  return file.type.startsWith('video/') ? 'video' : 'image';
}

function fileStatusLabel(status: UploadFileStatus): string {
  switch (status) {
    case 'uploading':
      return 'Uploading';
    case 'uploaded':
      return 'Uploaded';
    case 'finalizing':
      return 'Finalizing';
    case 'saved':
      return 'Saved';
    case 'failed':
      return 'Needs retry';
    default:
      return 'Ready';
  }
}

function fileStatusClassName(status: UploadFileStatus): string {
  switch (status) {
    case 'failed':
      return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300';
    case 'uploading':
    case 'finalizing':
      return 'border-wedding-gold/50 bg-wedding-gold/15 text-wedding-navy dark:text-wedding-gold';
    case 'uploaded':
    case 'saved':
      return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300';
    default:
      return 'border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300';
  }
}

async function uploadFileToPresignedUrl(file: File, uploadUrl: string): Promise<void> {
  const response = await fetch(uploadUrl, {
    method: 'PUT',
    headers: {
      'Content-Type': file.type,
    },
    body: file,
  });

  if (!response.ok) {
    throw new Error(`Upload failed with status ${response.status}`);
  }
}

export default function GuestMemoriesUploadClient({
  slug,
  uploadToken,
}: {
  slug: string;
  uploadToken: string;
}) {
  const [context, setContext] = useState<PublicGuestMemoriesContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [step, setStep] = useState<UploadStep>(0);
  const [guestName, setGuestName] = useState('');
  const [batchEventType, setBatchEventType] = useState<string>(NOT_SURE_EVENT_VALUE);
  const [selectedFiles, setSelectedFiles] = useState<SelectedUploadFile[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [uploadingLabel, setUploadingLabel] = useState<string>('');
  const [successCount, setSuccessCount] = useState<number>(0);
  const [lastSavedCount, setLastSavedCount] = useState<number>(0);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const selectedFilesRef = useRef<SelectedUploadFile[]>([]);

  const uploadCloseLabel = formatDateLabel(context?.guest_media.upload_closes_at);
  const totalSelectedBytes = selectedFiles.reduce((sum, item) => sum + item.file.size, 0);
  const failedFileCount = selectedFiles.filter((item) => item.status === 'failed').length;
  const activeUploadCount = selectedFiles.length;

  useEffect(() => {
    let cancelled = false;

    async function loadContext() {
      try {
        setLoading(true);
        setLoadError(null);
        const payload = await fetchPublicGuestMemoriesContext(slug, uploadToken);
        if (cancelled) return;
        setContext(payload);
        if (payload.events.length > 0) {
          setBatchEventType(payload.events[0].value);
        }
      } catch (error) {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : 'Could not open this upload link.';
        setLoadError(message);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadContext();

    return () => {
      cancelled = true;
    };
  }, [slug, uploadToken]);

  useEffect(() => {
    selectedFilesRef.current = selectedFiles;
  }, [selectedFiles]);

  useEffect(() => {
    return () => {
      selectedFilesRef.current.forEach((item) => URL.revokeObjectURL(item.previewUrl));
    };
  }, []);

  const eventOptions = context?.events ?? [];

  const updateFileState = (fileId: string, patch: Partial<SelectedUploadFile>) => {
    setSelectedFiles((current) =>
      current.map((item) => (item.id === fileId ? { ...item, ...patch } : item)),
    );
  };

  const validateFileBeforeAdd = (file: File): string | null => {
    if (!context) return 'Upload settings are still loading.';
    if (!context.limits.accepted_types.includes(file.type)) {
      return `${file.name} is not a supported image or video type.`;
    }
    const isVideo = file.type.startsWith('video/');
    const maxAllowed = isVideo ? context.limits.max_video_size_bytes : context.limits.max_image_size_bytes;
    if (file.size > maxAllowed) {
      return `${file.name} exceeds the ${formatBytes(maxAllowed)} limit.`;
    }
    return null;
  };

  const handleFileSelection = (event: React.ChangeEvent<HTMLInputElement>) => {
    const incomingFiles = Array.from(event.target.files || []);
    if (!context || incomingFiles.length === 0) return;

    const combinedCount = selectedFiles.length + incomingFiles.length;
    if (combinedCount > context.limits.max_files_per_batch) {
      toast.error(`You can upload up to ${context.limits.max_files_per_batch} files at a time.`);
      event.target.value = '';
      return;
    }

    const newSelections: SelectedUploadFile[] = [];
    for (const file of incomingFiles) {
      const validationError = validateFileBeforeAdd(file);
      if (validationError) {
        toast.error(validationError);
        continue;
      }

      newSelections.push({
        id: `${file.name}-${file.lastModified}-${Math.random().toString(36).slice(2, 8)}`,
        file,
        previewUrl: URL.createObjectURL(file),
        eventType: batchEventType,
        mediaType: buildPreviewType(file),
        status: 'ready',
      });
    }

    const updatedFiles = [...selectedFiles, ...newSelections];
    const updatedTotal = updatedFiles.reduce((sum, item) => sum + item.file.size, 0);
    if (updatedTotal > context.limits.max_batch_size_bytes) {
      newSelections.forEach((item) => URL.revokeObjectURL(item.previewUrl));
      toast.error(`This batch exceeds the ${formatBytes(context.limits.max_batch_size_bytes)} total upload limit.`);
      event.target.value = '';
      return;
    }

    setSelectedFiles(updatedFiles);
    setLastSavedCount(0);
    event.target.value = '';
  };

  const removeFile = (fileId: string) => {
    if (submitting) return;
    setSelectedFiles((current) => {
      const removed = current.find((item) => item.id === fileId);
      if (removed) {
        URL.revokeObjectURL(removed.previewUrl);
      }
      return current.filter((item) => item.id !== fileId);
    });
  };

  const openFilePicker = () => {
    if (submitting) return;
    const picker = fileInputRef.current as (HTMLInputElement & { showPicker?: () => void }) | null;
    if (!picker) return;

    try {
      if (typeof picker.showPicker === 'function') {
        picker.showPicker();
        return;
      }
    } catch {
      // Fall back to click() for browsers that reject showPicker on hidden inputs.
    }

    picker.click();
  };

  const resetUploads = () => {
    selectedFiles.forEach((item) => URL.revokeObjectURL(item.previewUrl));
    setSelectedFiles([]);
    setSuccessCount(0);
    setLastSavedCount(0);
    setUploadingLabel('');
    setStep(2);
  };

  const handleSubmit = async () => {
    if (!context || selectedFiles.length === 0) {
      toast.error('Select at least one photo or video first.');
      return;
    }
    if (!guestName.trim()) {
      toast.error('Please enter your name before uploading.');
      setStep(0);
      return;
    }

    const uploadCandidates = selectedFiles.filter((item) => item.status !== 'saved');
    if (uploadCandidates.length === 0) {
      toast.success('Everything selected has already been saved.');
      return;
    }

    setSubmitting(true);
    setUploadingLabel('Preparing uploads...');
    setSuccessCount(0);
    setLastSavedCount(0);
    setSelectedFiles((current) =>
      current.map((item) =>
        uploadCandidates.some((candidate) => candidate.id === item.id)
          ? { ...item, status: 'ready', assetId: undefined, error: undefined }
          : item,
      ),
    );

    try {
      const plan = await createPublicGuestMemoriesUploadPlan(slug, uploadToken, {
        uploader_name: guestName.trim(),
        batch_event_type: batchEventType,
        files: uploadCandidates.map((item) => ({
          filename: item.file.name,
          content_type: item.file.type,
          size_bytes: item.file.size,
          event_type: item.eventType,
        })),
      });

      const successfulUploads: Array<{ assetId: string; fileId: string }> = [];

      for (let index = 0; index < plan.assets.length; index += 1) {
        const assetPlan = plan.assets[index];
        const localFile = uploadCandidates[index];
        if (!localFile) continue;

        setUploadingLabel(`Uploading ${index + 1} of ${plan.assets.length}...`);
        updateFileState(localFile.id, {
          status: 'uploading',
          assetId: assetPlan.asset_id,
          error: undefined,
        });

        try {
          await uploadFileToPresignedUrl(localFile.file, assetPlan.upload_url);
          updateFileState(localFile.id, { status: 'uploaded' });
          successfulUploads.push({ assetId: assetPlan.asset_id, fileId: localFile.id });
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Upload failed';
          updateFileState(localFile.id, { status: 'failed', error: message });
          toast.error(`${localFile.file.name}: ${message}`);
        }
      }

      if (successfulUploads.length === 0) {
        throw new Error('None of the selected files uploaded successfully.');
      }

      setUploadingLabel('Finalizing your upload...');
      setSelectedFiles((current) =>
        current.map((item) =>
          successfulUploads.some((upload) => upload.fileId === item.id)
            ? { ...item, status: 'finalizing' }
            : item,
        ),
      );

      const finalized = await finalizePublicGuestMemoriesUpload(slug, uploadToken, {
        upload_batch_id: plan.upload_batch_id,
        asset_ids: successfulUploads.map((upload) => upload.assetId),
      });

      const failedFinalizeReasons = new Map(
        finalized.failed_assets.map((asset) => [asset.asset_id, asset.reason]),
      );
      const savedUploads = successfulUploads.filter((upload) => !failedFinalizeReasons.has(upload.assetId));
      const savedFileIds = new Set(savedUploads.map((upload) => upload.fileId));

      if (savedUploads.length > 0) {
        setSelectedFiles((current) => {
          const savedItems = current.filter((item) => savedFileIds.has(item.id));
          savedItems.forEach((item) => URL.revokeObjectURL(item.previewUrl));
          return current
            .filter((item) => !savedFileIds.has(item.id))
            .map((item) => {
              const failedReason = item.assetId ? failedFinalizeReasons.get(item.assetId) : undefined;
              return failedReason ? { ...item, status: 'failed', error: failedReason } : item;
            });
        });
      } else {
        setSelectedFiles((current) =>
          current.map((item) => {
            const failedReason = item.assetId ? failedFinalizeReasons.get(item.assetId) : undefined;
            return failedReason ? { ...item, status: 'failed', error: failedReason } : item;
          }),
        );
      }

      setLastSavedCount(savedUploads.length);
      setUploadingLabel('');

      const failedCount = uploadCandidates.length - savedUploads.length;
      if (failedCount > 0) {
        toast.warning(`${savedUploads.length} file(s) were saved, but ${failedCount} need another try.`);
        return;
      }

      setSuccessCount(finalized.uploaded_count);
      toast.success(`Saved ${finalized.uploaded_count} memory${finalized.uploaded_count === 1 ? '' : 'ies'} for the couple.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not finish the upload.';
      setUploadingLabel('');
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const Shell = ({ children }: { children: ReactNode }) => (
    <div className="min-h-screen bg-light-bg text-light-text transition-colors duration-300 dark:bg-dark-bg dark:text-dark-text">
      <div className="mx-auto flex min-h-screen w-full max-w-5xl flex-col px-4 py-4 sm:px-6 sm:py-6 lg:px-8">
        <header className="flex items-center justify-between border-b border-slate-200/70 pb-4 dark:border-slate-800">
          <Link href={`/${slug}`} aria-label="Back to wedding page" className="min-w-0">
            <span className="block dark:hidden">
              <BrandLockup variant="mark" surface="light" size="sm" />
            </span>
            <span className="hidden dark:block">
              <BrandLockup variant="mark" surface="dark" size="sm" />
            </span>
          </Link>
          <Link
            href={`/${slug}#rsvp`}
            className="inline-flex items-center gap-2 rounded-lg border border-wedding-rose/25 bg-white/70 px-3 py-2 text-sm font-medium text-wedding-navy transition hover:border-wedding-rose/50 hover:bg-wedding-blush/60 dark:border-wedding-rose/30 dark:bg-slate-900/70 dark:text-slate-100 dark:hover:bg-slate-800"
          >
            <HelpCircle className="h-4 w-4 text-wedding-rose" />
            Need help?
          </Link>
        </header>
        {children}
      </div>
    </div>
  );

  if (loading) {
    return (
      <Shell>
        <main className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-md rounded-xl border border-wedding-rose/20 bg-white/85 px-6 py-8 text-center shadow-lg backdrop-blur dark:border-white/10 dark:bg-slate-900/75">
            <Loader2 className="mx-auto h-9 w-9 animate-spin text-wedding-rose" />
            <p className="mt-4 text-sm font-medium text-slate-600 dark:text-slate-300">Opening your wedding upload link...</p>
          </div>
        </main>
      </Shell>
    );
  }

  if (loadError || !context) {
    return (
      <Shell>
        <main className="flex flex-1 items-center justify-center py-10">
          <section className="w-full max-w-xl rounded-xl border border-wedding-rose/20 bg-white/85 p-6 shadow-lg backdrop-blur dark:border-white/10 dark:bg-slate-900/75 sm:p-8">
            <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-wedding-rose/15 text-wedding-rose">
              <AlertCircle className="h-6 w-6" />
            </div>
            <h1 className="mt-5 text-3xl font-heading font-semibold text-wedding-navy dark:text-white">This memories link isn&apos;t available right now.</h1>
            <p className="mt-4 text-sm leading-7 text-slate-600 dark:text-slate-300">
              {loadError || 'The upload link may have expired, been rotated, or uploads may be closed for this wedding.'}
            </p>
            <div className="mt-7 grid gap-3 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => window.location.reload()}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-wedding-rose px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-wedding-blush disabled:opacity-60"
              >
                <RefreshCcw className="h-4 w-4" /> Try again
              </button>
              <Link
                href={`/${slug}`}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-wedding-rose/50 hover:bg-wedding-blush/50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                Back to wedding page
              </Link>
            </div>
          </section>
        </main>
      </Shell>
    );
  }

  if (successCount > 0 && selectedFiles.length === 0) {
    return (
      <Shell>
        <main className="flex flex-1 items-center justify-center py-10">
          <section className="w-full max-w-xl rounded-xl border border-wedding-rose/20 bg-white/85 p-6 shadow-lg backdrop-blur dark:border-white/10 dark:bg-slate-900/75 sm:p-8">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-300">
              <CheckCircle2 className="h-7 w-7" />
            </div>
            <h1 className="mt-5 text-3xl font-heading font-semibold text-wedding-navy dark:text-white">Thank you for sharing the moment.</h1>
            <p className="mt-4 text-sm leading-7 text-slate-600 dark:text-slate-300">
              {context.wedding.couple_names} received {successCount} new {successCount === 1 ? 'memory' : 'memories'} from you.
              Videos may take a little time to finish processing before the couple can play them back.
            </p>
            <div className="mt-7 grid gap-3 sm:grid-cols-2">
              <button
                type="button"
                onClick={resetUploads}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-wedding-rose px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-wedding-blush"
              >
                <ImagePlus className="h-4 w-4" /> Upload more
              </button>
              <Link
                href={`/${slug}`}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-wedding-rose/50 hover:bg-wedding-blush/50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                Done
              </Link>
            </div>
          </section>
        </main>
      </Shell>
    );
  }

  return (
    <Shell>
      <main className="grid flex-1 gap-6 py-6 lg:grid-cols-[minmax(0,1fr),320px] lg:py-8">
        <section className="rounded-xl border border-slate-200/80 bg-white/85 shadow-lg shadow-slate-900/5 backdrop-blur dark:border-slate-800 dark:bg-slate-900/75">
          <div className="border-b border-slate-200/80 px-5 py-5 dark:border-slate-800 sm:px-7">
            <Link
              href={`/${slug}`}
              className="mb-5 inline-flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-wedding-navy dark:text-slate-400 dark:hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" />
              Wedding page
            </Link>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-wedding-rose">Guest memories</p>
                <h1 className="mt-2 text-3xl font-heading font-semibold text-wedding-navy dark:text-white sm:text-4xl">
                  {context.wedding.couple_names}
                </h1>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600 dark:text-slate-300">
                  Add your photos and videos from the celebration. The couple receives every memory privately in their portal.
                </p>
              </div>
              <div className="rounded-lg border border-wedding-gold/40 bg-wedding-gold/10 px-4 py-3 text-left sm:text-right">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-wedding-navy/70 dark:text-wedding-gold">Upload window</p>
                <p className="mt-1 text-sm font-semibold text-wedding-navy dark:text-white">{uploadCloseLabel || 'Available now'}</p>
              </div>
            </div>

            <div className="mt-6 grid gap-2 sm:grid-cols-3">
              {STEP_ITEMS.map(({ id, label, icon: Icon }) => {
                const isActive = step === id;
                const isComplete = step > id;
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setStep(id)}
                    className={`flex items-center gap-3 rounded-lg border px-3 py-3 text-left transition ${
                      isActive
                        ? 'border-wedding-rose/50 bg-wedding-blush/70 text-wedding-navy'
                        : isComplete
                          ? 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300'
                          : 'border-slate-200 bg-white text-slate-600 hover:border-wedding-rose/30 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
                    }`}
                  >
                    <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${isActive ? 'bg-wedding-rose text-slate-950' : 'bg-slate-100 dark:bg-slate-900'}`}>
                      {isComplete ? <CheckCircle2 className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
                    </span>
                    <span>
                      <span className="block text-[11px] font-semibold uppercase tracking-[0.16em] opacity-70">Step {id + 1}</span>
                      <span className="block text-sm font-semibold">{label}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="px-5 py-6 sm:px-7">
            {lastSavedCount > 0 && activeUploadCount > 0 ? (
              <div className="mb-5 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300">
                {lastSavedCount} file{lastSavedCount === 1 ? '' : 's'} saved. Retry the remaining file{activeUploadCount === 1 ? '' : 's'} below.
              </div>
            ) : null}

            {step === 0 && (
              <div className="space-y-5">
                <div>
                  <h2 className="text-xl font-heading font-semibold text-wedding-navy dark:text-white">Who should the couple thank?</h2>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Your name helps them recognize who captured each memory.</p>
                </div>
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-wedding-navy dark:text-slate-200">Your display name</span>
                  <input
                    type="text"
                    value={guestName}
                    onInput={(event) => setGuestName(event.currentTarget.value)}
                    placeholder="e.g. Maya, Tunde, Auntie Bisi"
                    className="w-full rounded-lg border border-wedding-rose/20 bg-white px-4 py-3 text-base text-slate-900 shadow-inner outline-none transition focus:border-wedding-rose focus:ring-2 focus:ring-wedding-rose/40 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                  />
                </label>
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  disabled={!guestName.trim()}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-wedding-rose px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-wedding-blush disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto sm:min-w-40"
                >
                  Continue <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            )}

            {step === 1 && (
              <div className="space-y-5">
                <div>
                  <h2 className="text-xl font-heading font-semibold text-wedding-navy dark:text-white">What part of the celebration did you capture?</h2>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Choose a default event now. You can still adjust each file after selecting media.</p>
                </div>
                <div className="grid gap-3">
                  {eventOptions.map((option) => {
                    const selected = batchEventType === option.value;
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => setBatchEventType(option.value)}
                        className={`w-full rounded-lg border px-4 py-4 text-left transition ${
                          selected
                            ? 'border-wedding-rose/60 bg-wedding-blush/70 shadow-sm'
                            : 'border-slate-200 bg-white hover:border-wedding-rose/30 dark:border-slate-700 dark:bg-slate-800'
                        }`}
                      >
                        <span className="flex items-start justify-between gap-4">
                          <span>
                            <span className="block text-sm font-semibold text-wedding-navy dark:text-white">{eventLabel(option)}</span>
                            {option.date ? (
                              <span className="mt-1 block text-xs text-slate-500 dark:text-slate-400">{formatDateLabel(option.date)}</span>
                            ) : null}
                          </span>
                          <span
                            className={`mt-0.5 flex h-5 w-5 items-center justify-center rounded-full border ${
                              selected ? 'border-wedding-rose bg-wedding-rose' : 'border-slate-300 dark:border-slate-600'
                            }`}
                            aria-hidden="true"
                          >
                            {selected ? <span className="h-2 w-2 rounded-full bg-white" /> : null}
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <button
                    type="button"
                    onClick={() => setStep(0)}
                    className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-wedding-rose/40 hover:bg-wedding-blush/40 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    onClick={() => setStep(2)}
                    className="inline-flex items-center justify-center gap-2 rounded-lg bg-wedding-rose px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-wedding-blush"
                  >
                    Add media <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h2 className="text-xl font-heading font-semibold text-wedding-navy dark:text-white">Upload your photos and videos</h2>
                    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                      JPEG, PNG, WebP, MP4, and QuickTime files are supported.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setStep(1)}
                    className="inline-flex items-center justify-center rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:border-wedding-rose/40 hover:bg-wedding-blush/40 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                  >
                    Change event
                  </button>
                </div>

                <button
                  type="button"
                  onClick={openFilePicker}
                  disabled={submitting}
                  className="flex w-full cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-wedding-rose/50 bg-wedding-blush/50 px-6 py-9 text-center transition hover:border-wedding-rose hover:bg-wedding-blush disabled:cursor-not-allowed disabled:opacity-70 dark:bg-slate-800/70"
                >
                  <span className="flex h-12 w-12 items-center justify-center rounded-lg bg-white text-wedding-rose shadow-sm dark:bg-slate-900">
                    <Camera className="h-6 w-6" />
                  </span>
                  <span className="mt-4 text-base font-semibold text-wedding-navy dark:text-white">Tap to add photos or videos</span>
                  <span className="mt-2 max-w-md text-sm leading-6 text-slate-600 dark:text-slate-300">
                    Use your camera, gallery, or files app. Guests can upload up to {context.limits.max_files_per_batch} items per batch.
                  </span>
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={context.limits.accepted_types.join(',')}
                  multiple
                  className="sr-only"
                  onChange={handleFileSelection}
                  tabIndex={-1}
                  aria-hidden="true"
                />

                <div className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-300 sm:grid-cols-3">
                  <div>
                    <p className="font-semibold text-wedding-navy dark:text-white">{selectedFiles.length} selected</p>
                    <p className="mt-1 text-xs">Up to {context.limits.max_files_per_batch} files</p>
                  </div>
                  <div>
                    <p className="font-semibold text-wedding-navy dark:text-white">{formatBytes(totalSelectedBytes)}</p>
                    <p className="mt-1 text-xs">Total batch size</p>
                  </div>
                  <div>
                    <p className="font-semibold text-wedding-navy dark:text-white">
                      {eventLabel(eventOptions.find((option) => option.value === batchEventType) || { value: NOT_SURE_EVENT_VALUE, label: 'Not sure' })}
                    </p>
                    <p className="mt-1 text-xs">Default event tag</p>
                  </div>
                </div>

                {selectedFiles.length > 0 ? (
                  <div className="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
                    {selectedFiles.map((item, index) => (
                      <div
                        key={item.id}
                        className={`grid gap-4 p-4 sm:grid-cols-[132px,1fr] ${index > 0 ? 'border-t border-slate-200 dark:border-slate-700' : ''}`}
                      >
                        <div className="overflow-hidden rounded-lg bg-slate-100 dark:bg-slate-800">
                          {item.mediaType === 'image' ? (
                            <img
                              src={item.previewUrl}
                              alt={item.file.name}
                              className="h-32 w-full object-cover"
                            />
                          ) : (
                            <video
                              src={item.previewUrl}
                              className="h-32 w-full object-cover"
                              muted
                              playsInline
                              controls
                            />
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-start justify-between gap-4">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-semibold text-wedding-navy dark:text-white">{item.file.name}</p>
                              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                                <span className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                                  {item.mediaType === 'image' ? <ImagePlus className="h-3.5 w-3.5" /> : <Video className="h-3.5 w-3.5" />}
                                  {item.mediaType === 'image' ? 'Photo' : 'Video'}
                                </span>
                                <span>{formatBytes(item.file.size)}</span>
                                <span className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 font-medium ${fileStatusClassName(item.status)}`}>
                                  {item.status === 'uploading' || item.status === 'finalizing' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                                  {item.status === 'failed' ? <AlertCircle className="h-3.5 w-3.5" /> : null}
                                  {fileStatusLabel(item.status)}
                                </span>
                              </div>
                            </div>
                            <button
                              type="button"
                              onClick={() => removeFile(item.id)}
                              disabled={submitting}
                              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition hover:border-wedding-rose/40 hover:bg-wedding-blush/40 hover:text-wedding-navy disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800"
                              aria-label={`Remove ${item.file.name}`}
                            >
                              <X className="h-4 w-4" />
                            </button>
                          </div>

                          {item.error ? (
                            <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300">
                              {item.error}
                            </p>
                          ) : null}

                          <label className="mt-4 block">
                            <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">Captured during</span>
                            <select
                              value={item.eventType}
                              disabled={submitting}
                              onChange={(event) => {
                                const nextEventType = event.target.value;
                                setSelectedFiles((current) =>
                                  current.map((currentItem) =>
                                    currentItem.id === item.id
                                      ? { ...currentItem, eventType: nextEventType, error: undefined, status: currentItem.status === 'failed' ? 'ready' : currentItem.status }
                                      : currentItem,
                                  ),
                                );
                              }}
                              className="w-full rounded-lg border border-wedding-rose/20 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-wedding-rose focus:ring-2 focus:ring-wedding-rose/40 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                            >
                              {eventOptions.map((option) => (
                                <option key={option.value} value={option.value}>
                                  {eventLabel(option)}
                                </option>
                              ))}
                            </select>
                          </label>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-slate-200 px-6 py-10 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
                    Add at least one photo or video to continue.
                  </div>
                )}

                <div className="space-y-3">
                  {uploadingLabel ? (
                    <div className="flex items-center gap-2 rounded-lg bg-wedding-navy px-4 py-3 text-sm font-medium text-white">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      {uploadingLabel}
                    </div>
                  ) : null}
                  <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={submitting || selectedFiles.length === 0}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-wedding-rose px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-wedding-blush disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : failedFileCount > 0 ? <RefreshCcw className="h-4 w-4" /> : <UploadCloud className="h-4 w-4" />}
                    {failedFileCount > 0 ? 'Retry failed upload(s)' : 'Share with the couple'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setStep(1)}
                    disabled={submitting}
                    className="w-full rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-wedding-rose/40 hover:bg-wedding-blush/40 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                  >
                    Back
                  </button>
                </div>
              </div>
            )}
          </div>
        </section>

        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          <section className="rounded-xl border border-slate-200/80 bg-white/80 p-5 shadow-sm backdrop-blur dark:border-slate-800 dark:bg-slate-900/75">
            <h2 className="text-lg font-heading font-semibold text-wedding-navy dark:text-white">Day-of upload limits</h2>
            <dl className="mt-4 space-y-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-slate-500 dark:text-slate-400">Photos</dt>
                <dd className="font-semibold text-slate-800 dark:text-slate-100">{formatBytes(context.limits.max_image_size_bytes)}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-slate-500 dark:text-slate-400">Videos</dt>
                <dd className="font-semibold text-slate-800 dark:text-slate-100">{formatBytes(context.limits.max_video_size_bytes)}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-slate-500 dark:text-slate-400">Batch</dt>
                <dd className="font-semibold text-slate-800 dark:text-slate-100">{formatBytes(context.limits.max_batch_size_bytes)}</dd>
              </div>
            </dl>
          </section>

          <section className="rounded-xl border border-wedding-rose/20 bg-wedding-blush/60 p-5 dark:border-wedding-rose/30 dark:bg-slate-900/75">
            <h2 className="text-lg font-heading font-semibold text-wedding-navy dark:text-white">Need help?</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">
              If the upload link is not working on your phone, use the wedding help option and the planner can respond.
            </p>
            <Link
              href={`/${slug}#rsvp`}
              className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-wedding-rose/30 bg-white px-4 py-3 text-sm font-semibold text-wedding-navy transition hover:bg-wedding-blush dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
            >
              <HelpCircle className="h-4 w-4 text-wedding-rose" />
              Open wedding help
            </Link>
          </section>
        </aside>
      </main>
    </Shell>
  );
}
