'use client';

import { ImagePlus, Loader2, Trash2 } from 'lucide-react';
import type { DragEvent } from 'react';
import { useState } from 'react';

interface StorefrontImagePickerProps {
  id: string;
  label: string;
  hint: string;
  imageUrl: string | null;
  hasImage?: boolean;
  uploading: boolean;
  onFileSelect: (file: File) => void | Promise<void>;
  onRemove: () => void;
  compact?: boolean;
}

export function StorefrontImagePicker({
  id,
  label,
  hint,
  imageUrl,
  hasImage = Boolean(imageUrl),
  uploading,
  onFileSelect,
  onRemove,
  compact = false,
}: StorefrontImagePickerProps) {
  const [dragActive, setDragActive] = useState(false);
  const hintId = `${id}-hint`;

  const selectFirstFile = (files: FileList | null) => {
    const file = files?.[0];
    if (file) {
      void onFileSelect(file);
    }
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(false);
    if (!uploading) {
      selectFirstFile(event.dataTransfer.files);
    }
  };

  return (
    <div className="space-y-2">
      <div>
        <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">
          {label}
        </p>
        <p id={hintId} className="text-[11px] text-slate-500 dark:text-slate-400">
          {hint}
        </p>
      </div>

      {imageUrl || hasImage ? (
        <div
          className={`relative overflow-hidden rounded-xl border border-slate-200 bg-slate-100 shadow-sm dark:border-slate-700 dark:bg-slate-800 ${
            compact ? 'h-32' : 'h-44'
          }`}
        >
          {/* Dynamic planner uploads are served from a runtime-configured CDN. */}
          {imageUrl ? (
            <img src={imageUrl} alt={`${label} preview`} className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full items-center justify-center px-12 text-center text-xs text-slate-500">
              The saved image is attached, but its preview is temporarily unavailable.
            </div>
          )}
          <button
            type="button"
            onClick={onRemove}
            disabled={uploading}
            className="absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-full bg-slate-950/80 px-3 py-1.5 text-xs font-medium text-white shadow-sm backdrop-blur transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
            Remove
          </button>
        </div>
      ) : (
        <div
          onDragEnter={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          className={`relative rounded-xl border-2 border-dashed transition ${
            dragActive
              ? 'border-primary-500 bg-primary-50 dark:bg-primary-950/30'
              : 'border-slate-300 bg-slate-50 hover:border-primary-400 dark:border-slate-700 dark:bg-slate-900/40'
          } ${compact ? 'p-4' : 'p-6'}`}
        >
          <input
            id={id}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            aria-label={label}
            aria-describedby={hintId}
            disabled={uploading}
            className="peer sr-only"
            onChange={(event) => {
              selectFirstFile(event.currentTarget.files);
              event.currentTarget.value = '';
            }}
          />
          <label
            htmlFor={id}
            className="flex cursor-pointer flex-col items-center justify-center rounded-lg text-center outline-none peer-focus-visible:ring-2 peer-focus-visible:ring-primary-500 peer-focus-visible:ring-offset-2 dark:peer-focus-visible:ring-offset-slate-900"
          >
            {uploading ? (
              <Loader2
                className="mb-2 h-6 w-6 animate-spin text-primary-600"
                aria-hidden="true"
              />
            ) : (
              <ImagePlus className="mb-2 h-6 w-6 text-slate-400" aria-hidden="true" />
            )}
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">
              {uploading ? 'Uploading image…' : 'Choose an image or drop it here'}
            </span>
            <span className="mt-1 text-[10px] text-slate-500">
              JPEG, PNG, or WebP · 5 MB maximum
            </span>
          </label>
        </div>
      )}
    </div>
  );
}
