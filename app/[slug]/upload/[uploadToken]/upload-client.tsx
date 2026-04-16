'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import {
  ArrowRight,
  CalendarDays,
  Camera,
  CheckCircle2,
  Heart,
  ImagePlus,
  Loader2,
  RefreshCcw,
  UploadCloud,
  User,
  Video,
  X,
} from 'lucide-react';

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

interface SelectedUploadFile {
  id: string;
  file: File;
  previewUrl: string;
  eventType: string;
  mediaType: 'image' | 'video';
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
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const uploadCloseLabel = formatDateLabel(context?.guest_media.upload_closes_at);
  const totalSelectedBytes = selectedFiles.reduce((sum, item) => sum + item.file.size, 0);

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
    return () => {
      selectedFiles.forEach((item) => URL.revokeObjectURL(item.previewUrl));
    };
  }, [selectedFiles]);

  const eventOptions = context?.events ?? [];

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
    event.target.value = '';
  };

  const removeFile = (fileId: string) => {
    setSelectedFiles((current) => {
      const nextFiles = current.filter((item) => item.id !== fileId);
      const removed = current.find((item) => item.id === fileId);
      if (removed) {
        URL.revokeObjectURL(removed.previewUrl);
      }
      return nextFiles;
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

    setSubmitting(true);
    setUploadingLabel('Preparing uploads...');

    try {
      const plan = await createPublicGuestMemoriesUploadPlan(slug, uploadToken, {
        uploader_name: guestName.trim(),
        batch_event_type: batchEventType,
        files: selectedFiles.map((item) => ({
          filename: item.file.name,
          content_type: item.file.type,
          size_bytes: item.file.size,
          event_type: item.eventType,
        })),
      });

      const successfulAssetIds: string[] = [];

      for (let index = 0; index < plan.assets.length; index += 1) {
        const assetPlan = plan.assets[index];
        const localFile = selectedFiles[index];
        if (!localFile) continue;

        setUploadingLabel(`Uploading ${index + 1} of ${plan.assets.length}...`);
        try {
          await uploadFileToPresignedUrl(localFile.file, assetPlan.upload_url);
          successfulAssetIds.push(assetPlan.asset_id);
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Upload failed';
          toast.error(`${localFile.file.name}: ${message}`);
        }
      }

      if (successfulAssetIds.length === 0) {
        throw new Error('None of the selected files uploaded successfully.');
      }

      setUploadingLabel('Finalizing your upload...');
      const finalized = await finalizePublicGuestMemoriesUpload(slug, uploadToken, {
        upload_batch_id: plan.upload_batch_id,
        asset_ids: successfulAssetIds,
      });

      setSuccessCount(finalized.uploaded_count);
      selectedFiles.forEach((item) => URL.revokeObjectURL(item.previewUrl));
      setSelectedFiles([]);
      setUploadingLabel('');

      if (finalized.failed_count > 0) {
        toast.warning(`${finalized.uploaded_count} file(s) were saved, but ${finalized.failed_count} need another try.`);
      } else {
        toast.success(`Saved ${finalized.uploaded_count} memory${finalized.uploaded_count === 1 ? '' : 'ies'} for the couple.`);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not finish the upload.';
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(244,114,182,0.18),_transparent_40%),linear-gradient(180deg,_#fff8fb,_#fff)] flex items-center justify-center px-6">
        <div className="rounded-3xl border border-rose-100 bg-white/90 px-8 py-10 shadow-[0_24px_80px_rgba(188,24,93,0.12)] backdrop-blur">
          <Loader2 className="mx-auto h-10 w-10 animate-spin text-rose-500" />
          <p className="mt-4 text-sm font-medium text-slate-600">Opening your wedding upload link...</p>
        </div>
      </div>
    );
  }

  if (loadError || !context) {
    return (
      <div className="min-h-screen bg-slate-950 text-white px-6 py-16">
        <div className="mx-auto max-w-xl rounded-[2rem] border border-white/10 bg-white/5 p-8 shadow-2xl">
          <p className="inline-flex items-center rounded-full border border-rose-400/30 bg-rose-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-rose-200">
            Upload unavailable
          </p>
          <h1 className="mt-6 text-3xl font-semibold">This memories link isn&apos;t available right now.</h1>
          <p className="mt-4 text-sm leading-7 text-slate-300">
            {loadError || 'The upload link may have expired, been rotated, or uploads may be closed for this wedding.'}
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-medium text-slate-900 transition hover:bg-rose-50"
            >
              <RefreshCcw className="h-4 w-4" /> Try again
            </button>
            <Link
              href={`/${slug}`}
              className="inline-flex items-center gap-2 rounded-full border border-white/15 px-4 py-2 text-sm font-medium text-white transition hover:border-white/30 hover:bg-white/5"
            >
              Back to wedding page
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (successCount > 0) {
    return (
      <div className="min-h-screen bg-[linear-gradient(180deg,_#fffafc,_#fff3f7)] px-6 py-10">
        <div className="mx-auto max-w-lg rounded-[2rem] border border-rose-100 bg-white p-8 shadow-[0_28px_90px_rgba(225,29,72,0.12)]">
          <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-600">
            <CheckCircle2 className="h-7 w-7" />
          </div>
          <p className="mt-6 text-xs font-semibold uppercase tracking-[0.24em] text-rose-500">Upload complete</p>
          <h1 className="mt-3 text-3xl font-semibold text-slate-900">Thank you for sharing the moment.</h1>
          <p className="mt-4 text-sm leading-7 text-slate-600">
            {context.wedding.couple_names} received {successCount} new {successCount === 1 ? 'memory' : 'memories'} from you.
            Videos may take a little time to finish processing before the couple can play them back.
          </p>
          <div className="mt-8 space-y-3">
            <button
              type="button"
              onClick={resetUploads}
              className="flex w-full items-center justify-center gap-2 rounded-2xl bg-rose-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-rose-700"
            >
              <ImagePlus className="h-4 w-4" /> Upload more
            </button>
            <Link
              href={`/${slug}`}
              className="flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
            >
              Done
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_right,_rgba(244,114,182,0.16),_transparent_34%),radial-gradient(circle_at_bottom_left,_rgba(251,191,36,0.14),_transparent_32%),linear-gradient(180deg,_#fff8fb,_#fff)] px-4 py-5 sm:px-6 sm:py-8">
      <div className="mx-auto max-w-2xl">
        <div className="overflow-hidden rounded-[2rem] border border-white/80 bg-white/90 shadow-[0_30px_100px_rgba(188,24,93,0.12)] backdrop-blur">
          <div className="border-b border-rose-100/80 bg-[linear-gradient(135deg,_rgba(255,255,255,0.96),_rgba(255,244,248,0.9))] px-6 py-7 sm:px-8">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="inline-flex items-center gap-2 rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-rose-500">
                  <Heart className="h-3.5 w-3.5" /> Share your memories
                </p>
                <h1 className="mt-4 text-3xl font-semibold text-slate-900 sm:text-4xl">{context.wedding.couple_names}</h1>
                <p className="mt-3 max-w-xl text-sm leading-7 text-slate-600">
                  Snap the best parts of the day, upload them here, and the couple will get them privately in their portal.
                </p>
              </div>
              <div className="hidden rounded-[1.5rem] bg-rose-50 px-4 py-3 text-right sm:block">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-rose-500">Window closes</p>
                <p className="mt-1 text-sm font-medium text-slate-900">{uploadCloseLabel || 'Soon'}</p>
              </div>
            </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              {STEP_ITEMS.map(({ id, label, icon: Icon }) => {
                const isActive = step === id;
                const isComplete = step > id;
                return (
                  <div
                    key={id}
                    className={`rounded-2xl border px-4 py-3 transition ${
                      isActive
                        ? 'border-rose-200 bg-rose-50'
                        : isComplete
                          ? 'border-emerald-200 bg-emerald-50'
                          : 'border-slate-200 bg-slate-50'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`flex h-10 w-10 items-center justify-center rounded-2xl ${
                          isActive
                            ? 'bg-rose-600 text-white'
                            : isComplete
                              ? 'bg-emerald-500 text-white'
                              : 'bg-white text-slate-500'
                        }`}
                      >
                        {isComplete ? <CheckCircle2 className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Step {id + 1}</p>
                        <p className="text-sm font-medium text-slate-900">{label}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-5 block rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-900 sm:hidden">
              <span className="font-semibold">Upload window:</span> {uploadCloseLabel || 'Available now'}
            </div>
          </div>

          <div className="px-6 py-7 sm:px-8">
            {step === 0 && (
              <div className="space-y-5">
                <div>
                  <p className="text-sm font-semibold text-slate-900">Who are you?</p>
                  <p className="mt-1 text-sm text-slate-500">Your name helps the couple know who captured each memory.</p>
                </div>
                <label className="block">
                  <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Your display name</span>
                  <input
                    type="text"
                    value={guestName}
                    onChange={(event) => setGuestName(event.target.value)}
                    placeholder="e.g. Maya, Tunde, Auntie Bisi"
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-base text-slate-900 shadow-sm outline-none transition focus:border-rose-300 focus:ring-4 focus:ring-rose-100"
                  />
                </label>
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  disabled={!guestName.trim()}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Continue <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            )}

            {step === 1 && (
              <div className="space-y-5">
                <div>
                  <p className="text-sm font-semibold text-slate-900">What part of the celebration did you capture?</p>
                  <p className="mt-1 text-sm text-slate-500">
                    Pick one default event now. You can change individual photos and videos later.
                  </p>
                </div>
                <div className="space-y-3">
                  {eventOptions.map((option) => {
                    const selected = batchEventType === option.value;
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => setBatchEventType(option.value)}
                        className={`w-full rounded-2xl border px-4 py-4 text-left transition ${
                          selected
                            ? 'border-rose-300 bg-rose-50 shadow-sm'
                            : 'border-slate-200 bg-white hover:border-slate-300'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <p className="text-sm font-semibold text-slate-900">{eventLabel(option)}</p>
                            {option.date && (
                              <p className="mt-1 text-xs text-slate-500">{formatDateLabel(option.date)}</p>
                            )}
                          </div>
                          <div
                            className={`mt-0.5 h-5 w-5 rounded-full border-2 ${
                              selected ? 'border-rose-500 bg-rose-500' : 'border-slate-300'
                            }`}
                          />
                        </div>
                      </button>
                    );
                  })}
                </div>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => setStep(0)}
                    className="flex-1 rounded-2xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    onClick={() => setStep(2)}
                    className="flex flex-1 items-center justify-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
                  >
                    Add media <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">Upload your photos and videos</p>
                    <p className="mt-1 text-sm text-slate-500">
                      JPEG, PNG, WebP, MP4, and QuickTime files are supported. You can tag each file separately if needed.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setStep(1)}
                    className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-slate-300 hover:bg-slate-50"
                  >
                    Change event
                  </button>
                </div>

                <button
                  type="button"
                  onClick={openFilePicker}
                  disabled={submitting}
                  className="flex w-full cursor-pointer flex-col items-center justify-center rounded-[1.75rem] border border-dashed border-rose-300 bg-rose-50/70 px-6 py-10 text-center transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-rose-600 shadow-sm">
                    <Camera className="h-6 w-6" />
                  </div>
                  <p className="mt-4 text-base font-semibold text-slate-900">Tap to add photos or videos</p>
                  <p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">
                    Your phone can use the camera, your gallery, or your files app. Guests can upload up to {context.limits.max_files_per_batch} items per batch.
                  </p>
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

                <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600 sm:grid-cols-3">
                  <div>
                    <p className="font-semibold text-slate-900">{selectedFiles.length} selected</p>
                    <p className="mt-1 text-xs">Up to {context.limits.max_files_per_batch} files</p>
                  </div>
                  <div>
                    <p className="font-semibold text-slate-900">{formatBytes(totalSelectedBytes)}</p>
                    <p className="mt-1 text-xs">Total batch size</p>
                  </div>
                  <div>
                    <p className="font-semibold text-slate-900">
                      {eventLabel(eventOptions.find((option) => option.value === batchEventType) || { value: NOT_SURE_EVENT_VALUE, label: 'Not sure' })}
                    </p>
                    <p className="mt-1 text-xs">Default event tag</p>
                  </div>
                </div>

                {selectedFiles.length > 0 ? (
                  <div className="space-y-4">
                    {selectedFiles.map((item) => (
                      <div
                        key={item.id}
                        className="overflow-hidden rounded-[1.5rem] border border-slate-200 bg-white shadow-sm"
                      >
                        <div className="grid gap-4 p-4 sm:grid-cols-[140px,1fr]">
                          <div className="overflow-hidden rounded-2xl bg-slate-100">
                            {item.mediaType === 'image' ? (
                              <img
                                src={item.previewUrl}
                                alt={item.file.name}
                                className="h-36 w-full object-cover"
                              />
                            ) : (
                              <video
                                src={item.previewUrl}
                                className="h-36 w-full object-cover"
                                muted
                                playsInline
                                controls
                              />
                            )}
                          </div>
                          <div>
                            <div className="flex items-start justify-between gap-4">
                              <div>
                                <p className="text-sm font-semibold text-slate-900">{item.file.name}</p>
                                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                                  <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-700">
                                    {item.mediaType === 'image' ? <ImagePlus className="h-3.5 w-3.5" /> : <Video className="h-3.5 w-3.5" />}
                                    {item.mediaType === 'image' ? 'Photo' : 'Video'}
                                  </span>
                                  <span>{formatBytes(item.file.size)}</span>
                                </div>
                              </div>
                              <button
                                type="button"
                                onClick={() => removeFile(item.id)}
                                className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 text-slate-500 transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-700"
                                aria-label={`Remove ${item.file.name}`}
                              >
                                <X className="h-4 w-4" />
                              </button>
                            </div>

                            <label className="mt-4 block">
                              <span className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Captured during</span>
                              <select
                                value={item.eventType}
                                onChange={(event) => {
                                  const nextEventType = event.target.value;
                                  setSelectedFiles((current) =>
                                    current.map((currentItem) =>
                                      currentItem.id === item.id
                                        ? { ...currentItem, eventType: nextEventType }
                                        : currentItem,
                                    ),
                                  );
                                }}
                                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-rose-300 focus:ring-4 focus:ring-rose-100"
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
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-[1.75rem] border border-dashed border-slate-200 px-6 py-10 text-center text-sm text-slate-500">
                    Add at least one photo or video to continue.
                  </div>
                )}

                <div className="space-y-3">
                  {uploadingLabel && (
                    <div className="flex items-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-medium text-white">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      {uploadingLabel}
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={submitting || selectedFiles.length === 0}
                    className="flex w-full items-center justify-center gap-2 rounded-2xl bg-rose-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                    Share with the couple
                  </button>
                  <button
                    type="button"
                    onClick={() => setStep(1)}
                    className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
                  >
                    Back
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
