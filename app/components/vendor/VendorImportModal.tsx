'use client';

import { useState, useCallback, useRef } from 'react';
import type { ReactElement } from 'react';
import {
  importVendors,
  VendorImportItem,
  VendorImportResponse,
} from '@/services/vendorManagementApi';

// ─── Styles matching the admin glass-panel design system ─────────────────────

const overlayClass =
  'fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm';

const modalClass =
  'relative w-full max-w-[560px] max-h-[90vh] overflow-hidden rounded-3xl border border-slate-200/80 bg-white/[.97] shadow-xl backdrop-blur-2xl dark:border-white/10 dark:bg-slate-900/95';

const glassSoftClass =
  'rounded-2xl border border-slate-200/80 bg-white/70 p-4 dark:border-white/15 dark:bg-white/15';

// ─── Types ───────────────────────────────────────────────────────────────────

interface VendorImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  token: string;
  onImportComplete?: (result: VendorImportResponse) => void;
}

type ImportStage = 'upload' | 'preview' | 'importing' | 'done';

interface ParsedData {
  vendors: VendorImportItem[];
  fileName: string;
  fileSize: number;
  /** Vendors grouped by whether they're likely new or updates (client-side guess) */
  newCount: number;
  updateCount: number;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const VALID_CATEGORIES = new Set([
  'photographer', 'videographer', 'florist', 'caterer', 'venue', 'dj', 'mc',
  'band', 'officiant', 'planner', 'decorator', 'cake', 'hair_makeup',
  'transportation', 'stationery', 'rentals', 'lighting', 'photo_booth',
  'jewelry', 'attire', 'other',
]);

function validateVendors(data: unknown): VendorImportItem[] {
  if (!Array.isArray(data)) {
    throw new Error('JSON must be an array of vendor objects');
  }
  if (data.length === 0) {
    throw new Error('JSON array is empty — no vendors to import');
  }
  if (data.length > 500) {
    throw new Error(`Too many vendors (${data.length}). Maximum is 500 per import.`);
  }

  const vendors: VendorImportItem[] = [];
  for (let i = 0; i < data.length; i++) {
    const item = data[i];
    if (!item.business_name || typeof item.business_name !== 'string') {
      throw new Error(`Vendor at index ${i} is missing a valid business_name`);
    }
    if (!item.service_category || !VALID_CATEGORIES.has(item.service_category)) {
      throw new Error(
        `Vendor "${item.business_name}" has invalid category: "${item.service_category}"`
      );
    }
    vendors.push(item as VendorImportItem);
  }

  return vendors;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const categoryLabel = (cat: string) =>
  cat.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

// ─── Component ───────────────────────────────────────────────────────────────

export default function VendorImportModal({
  isOpen,
  onClose,
  token,
  onImportComplete,
}: VendorImportModalProps): ReactElement | null {
  const [stage, setStage] = useState<ImportStage>('upload');
  const [parsed, setParsed] = useState<ParsedData | null>(null);
  const [result, setResult] = useState<VendorImportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const reset = useCallback(() => {
    setStage('upload');
    setParsed(null);
    setResult(null);
    setError(null);
    setIsDragging(false);
    // Reset file input so re-uploading the same file triggers onChange
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  const handleClose = useCallback(() => {
    reset();
    onClose();
  }, [reset, onClose]);

  // ── File parsing ──

  const parseFile = useCallback((file: File) => {
    setError(null);

    if (!file.name.endsWith('.json')) {
      setError('Only .json files are accepted');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const raw = JSON.parse(e.target?.result as string);
        const vendors = validateVendors(raw);

        // Rough guess: items with google_place_id and scraped_at are updates
        // (the actual server-side diff is authoritative)
        const updateCount = vendors.filter(
          (v) => v.google_place_id && (v as any).scraped_at
        ).length;

        setParsed({
          vendors,
          fileName: file.name,
          fileSize: file.size,
          newCount: vendors.length - updateCount,
          updateCount,
        });
        setStage('preview');
      } catch (err: any) {
        setError(err.message || 'Failed to parse JSON file');
      }
    };
    reader.onerror = () => setError('Failed to read file');
    reader.readAsText(file);
  }, []);

  // ── Drag & drop ──

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) parseFile(file);
    },
    [parseFile]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) parseFile(file);
    },
    [parseFile]
  );

  // ── Import ──

  const handleImport = useCallback(async () => {
    if (!parsed) return;
    setStage('importing');
    setError(null);

    try {
      const res = await importVendors(token, parsed.vendors);
      setResult(res);
      setStage('done');
      onImportComplete?.(res);
    } catch (err: any) {
      setError(err.message || 'Import failed');
      setStage('preview'); // Go back to preview so they can retry
    }
  }, [parsed, token, onImportComplete]);

  // Close on Escape
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    },
    [handleClose]
  );

  if (!isOpen) return null;

  return (
    <div className={overlayClass} onClick={handleClose} onKeyDown={handleKeyDown} tabIndex={-1}>
      <div className={modalClass} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200/60 px-6 py-5 dark:border-white/10">
          <div>
            <h2 className="text-lg font-bold text-slate-800 dark:text-white">Import Vendors</h2>
            <p className="mt-0.5 text-xs text-slate-400">
              Upload JSON from the vendor scraper CLI
            </p>
          </div>
          <button
            onClick={handleClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 dark:hover:bg-white/10"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-5 max-h-[60vh] overflow-y-auto">
          {/* Error banner */}
          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
              {error}
            </div>
          )}

          {/* ── Upload stage ── */}
          {stage === 'upload' && (
            <div
              className={`cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition-colors ${
                isDragging
                  ? 'border-rose-400 bg-rose-50/50'
                  : 'border-slate-300 hover:border-rose-300 hover:bg-rose-50/30'
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-rose-100">
                <svg className="h-6 w-6 text-rose-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </div>
              <p className="text-sm font-medium text-slate-600 dark:text-slate-300">
                Drop your JSON file here
              </p>
              <p className="mt-1 text-xs text-slate-400">or click to browse</p>
              <p className="mt-3 font-mono text-[11px] text-slate-300">
                .service-manager/exports/vendors-*.json
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                className="hidden"
                onChange={handleFileSelect}
              />
            </div>
          )}

          {/* ── Preview stage ── */}
          {(stage === 'preview' || stage === 'importing') && parsed && (
            <div className={glassSoftClass}>
              {/* File info */}
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <svg className="h-4 w-4 text-emerald-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
                    <path d="M22 4L12 14.01l-3-3" />
                  </svg>
                  <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                    {parsed.fileName}
                  </span>
                </div>
                <span className="text-xs text-slate-400">{formatFileSize(parsed.fileSize)}</span>
              </div>

              {/* Summary stats */}
              <div className="mb-4 grid grid-cols-3 gap-3">
                <div className="rounded-xl border border-emerald-200/60 bg-emerald-50 p-2.5 text-center dark:border-emerald-800 dark:bg-emerald-900/20">
                  <p className="text-lg font-bold text-emerald-700 dark:text-emerald-400">
                    {parsed.vendors.length}
                  </p>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-500">
                    Total
                  </p>
                </div>
                <div className="rounded-xl border border-blue-200/60 bg-blue-50 p-2.5 text-center dark:border-blue-800 dark:bg-blue-900/20">
                  <p className="text-lg font-bold text-blue-700 dark:text-blue-400">
                    {new Set(parsed.vendors.map((v) => v.service_category)).size}
                  </p>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-blue-500">
                    Categories
                  </p>
                </div>
                <div className="rounded-xl border border-amber-200/60 bg-amber-50 p-2.5 text-center dark:border-amber-800 dark:bg-amber-900/20">
                  <p className="text-lg font-bold text-amber-700 dark:text-amber-400">
                    {new Set(parsed.vendors.map((v) => v.city).filter(Boolean)).size}
                  </p>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-amber-500">
                    Cities
                  </p>
                </div>
              </div>

              {/* Scrollable preview list */}
              <div className="max-h-[200px] space-y-1.5 overflow-y-auto text-xs">
                {parsed.vendors.slice(0, 20).map((v, i) => (
                  <div
                    key={`${v.google_place_id || v.business_name}-${i}`}
                    className="flex items-center gap-2 rounded-lg bg-white/80 px-2 py-1.5 dark:bg-white/5"
                  >
                    <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
                    <span className="flex-1 truncate font-medium text-slate-700 dark:text-slate-200">
                      {v.business_name}
                    </span>
                    <span className="shrink-0 text-slate-400">
                      {categoryLabel(v.service_category)}
                    </span>
                    <span className="shrink-0 text-slate-300">{v.city || '—'}</span>
                  </div>
                ))}
                {parsed.vendors.length > 20 && (
                  <div className="py-2 text-center text-slate-400">
                    + {parsed.vendors.length - 20} more vendors...
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── Done stage ── */}
          {stage === 'done' && result && (
            <div className={glassSoftClass}>
              <div className="mb-4 flex items-center gap-2">
                <svg className="h-5 w-5 text-emerald-500" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
                  <path d="M22 4L12 14.01l-3-3" />
                </svg>
                <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                  Import Complete
                </span>
              </div>
              <div className="grid grid-cols-4 gap-3">
                <div className="rounded-xl border border-emerald-200/60 bg-emerald-50 p-2.5 text-center">
                  <p className="text-lg font-bold text-emerald-700">{result.inserted}</p>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-500">
                    Inserted
                  </p>
                </div>
                <div className="rounded-xl border border-blue-200/60 bg-blue-50 p-2.5 text-center">
                  <p className="text-lg font-bold text-blue-700">{result.updated}</p>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-blue-500">
                    Updated
                  </p>
                </div>
                <div className="rounded-xl border border-amber-200/60 bg-amber-50 p-2.5 text-center">
                  <p className="text-lg font-bold text-amber-700">{result.skipped}</p>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-amber-500">
                    Skipped
                  </p>
                </div>
                <div className="rounded-xl border border-red-200/60 bg-red-50 p-2.5 text-center">
                  <p className="text-lg font-bold text-red-700">{result.errors}</p>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-red-500">
                    Errors
                  </p>
                </div>
              </div>
              {result.error_details.length > 0 && (
                <div className="mt-3 max-h-[120px] overflow-y-auto rounded-lg bg-red-50/50 p-3 text-xs text-red-600">
                  {result.error_details.map((err, i) => (
                    <div key={i} className="mb-1">
                      <span className="font-medium">{err.business_name}:</span> {err.error}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-slate-200/60 bg-slate-50/50 px-6 py-4 dark:border-white/10 dark:bg-white/5">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 16v-4M12 8h.01" />
            </svg>
            ROOT_ADMIN only
          </div>
          <div className="flex gap-3">
            {stage === 'done' ? (
              <button
                onClick={handleClose}
                className="rounded-xl bg-rose-500 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-rose-500/20 transition-colors hover:bg-rose-600"
              >
                Done
              </button>
            ) : (
              <>
                <button
                  onClick={stage === 'preview' ? reset : handleClose}
                  className="rounded-xl px-4 py-2 text-sm font-medium text-slate-500 transition-colors hover:bg-slate-100 dark:hover:bg-white/10"
                >
                  {stage === 'preview' ? 'Back' : 'Cancel'}
                </button>
                {stage === 'preview' && parsed && (
                  <button
                    onClick={handleImport}
                    className="flex items-center gap-2 rounded-xl bg-rose-500 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-rose-500/20 transition-colors hover:bg-rose-600"
                  >
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
                      <path d="M22 4L12 14.01l-3-3" />
                    </svg>
                    Import {parsed.vendors.length} Vendors
                  </button>
                )}
                {stage === 'importing' && (
                  <button
                    disabled
                    className="flex items-center gap-2 rounded-xl bg-rose-400 px-5 py-2 text-sm font-semibold text-white opacity-70"
                  >
                    <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Importing...
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
