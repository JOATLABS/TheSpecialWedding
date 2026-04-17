'use client';

import React, { useRef, useState } from 'react';
import { Image as ImageIcon, Loader2, RefreshCw, Upload, X } from 'lucide-react';

import {
  uploadVendorMediaAsset,
  type VendorMediaAssetKind,
} from '@/services/campaignAdvertisingApi';

import { useVendorAuth } from './VendorAuthContext';
import {
  vendorGhostButtonClass,
  vendorInsetClass,
  vendorPrimaryButtonClass,
  vendorSecondaryButtonClass,
} from './styles';

const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;

interface VendorMediaUploaderProps {
  inputId: string;
  assetKind: VendorMediaAssetKind;
  label: string;
  value: string | null;
  onChange: (url: string | null) => void;
  previewAlt: string;
  helperText?: string;
  emptyTitle: string;
  emptyDescription: string;
  disabled?: boolean;
}

function formatMaxImageSize(bytes: number) {
  return `${Math.round(bytes / (1024 * 1024))} MB`;
}

export function VendorMediaUploader({
  inputId,
  assetKind,
  label,
  value,
  onChange,
  previewAlt,
  helperText,
  emptyTitle,
  emptyDescription,
  disabled = false,
}: VendorMediaUploaderProps) {
  const { token } = useVendorAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragActive, setIsDragActive] = useState(false);
  const [error, setError] = useState('');

  const canUpload = Boolean(token) && !disabled;

  const openPicker = () => {
    if (!canUpload) return;
    inputRef.current?.click();
  };

  const validateFile = (file: File) => {
    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      throw new Error('Only JPEG, PNG, and WebP images are allowed.');
    }
    if (file.size > MAX_IMAGE_SIZE_BYTES) {
      throw new Error(`Image must be under ${formatMaxImageSize(MAX_IMAGE_SIZE_BYTES)}.`);
    }
  };

  const handleFile = async (file: File | null | undefined) => {
    if (!file || !token) {
      return;
    }

    try {
      validateFile(file);
      setIsUploading(true);
      setError('');
      const uploaded = await uploadVendorMediaAsset(token, file, assetKind, value);
      onChange(uploaded.cdn_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.');
    } finally {
      setIsUploading(false);
      setIsDragActive(false);
      if (inputRef.current) {
        inputRef.current.value = '';
      }
    }
  };

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <label htmlFor={inputId} className="block text-sm font-medium text-slate-700 dark:text-slate-200">
          {label}
        </label>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {helperText ?? `JPEG, PNG, or WebP up to ${formatMaxImageSize(MAX_IMAGE_SIZE_BYTES)}.`}
        </p>
      </div>

      <div
        className={`${vendorInsetClass} overflow-hidden border-2 border-dashed transition-colors ${
          isDragActive
            ? 'border-primary-500/70 bg-primary-50/70 dark:bg-primary-900/20'
            : 'border-slate-200/80 dark:border-slate-700/80'
        } ${disabled ? 'opacity-60' : ''}`}
        onDragOver={(event) => {
          if (!canUpload) return;
          event.preventDefault();
          setIsDragActive(true);
        }}
        onDragLeave={(event) => {
          if (!canUpload) return;
          event.preventDefault();
          setIsDragActive(false);
        }}
        onDrop={(event) => {
          if (!canUpload) return;
          event.preventDefault();
          void handleFile(event.dataTransfer.files?.[0]);
        }}
      >
        {value ? (
          <div className="space-y-4 p-4">
            <div className="overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-sm dark:border-slate-700/80 dark:bg-slate-900/70">
              <img src={value} alt={previewAlt} className="h-48 w-full object-cover" />
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={openPicker}
                disabled={!canUpload || isUploading}
                className={vendorPrimaryButtonClass}
              >
                {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                {isUploading ? 'Uploading…' : 'Replace Image'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setError('');
                  onChange(null);
                }}
                disabled={disabled || isUploading}
                className={vendorSecondaryButtonClass}
              >
                <X className="h-4 w-4" />
                Remove
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={openPicker}
            disabled={!canUpload || isUploading}
            className="flex w-full flex-col items-center justify-center gap-3 px-6 py-10 text-center"
          >
            {isUploading ? (
              <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
            ) : (
              <div className="rounded-full bg-white/80 p-3 text-primary-500 shadow-sm dark:bg-slate-900/80">
                {isDragActive ? <Upload className="h-6 w-6" /> : <ImageIcon className="h-6 w-6" />}
              </div>
            )}
            <div className="space-y-1">
              <p className="text-sm font-medium text-slate-900 dark:text-white">{emptyTitle}</p>
              <p className="max-w-md text-sm text-slate-500 dark:text-slate-400">{emptyDescription}</p>
            </div>
            <span className={vendorGhostButtonClass}>
              <Upload className="h-4 w-4" />
              {isUploading ? 'Uploading…' : 'Choose Image'}
            </span>
          </button>
        )}

        <input
          id={inputId}
          ref={inputRef}
          type="file"
          accept={ALLOWED_IMAGE_TYPES.join(',')}
          className="hidden"
          aria-label={label}
          onChange={(event) => {
            void handleFile(event.target.files?.[0]);
          }}
        />
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
          {error}
        </div>
      ) : null}
    </div>
  );
}
