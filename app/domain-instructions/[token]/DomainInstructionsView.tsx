'use client';

import { useState } from 'react';
import {
  Check,
  Clipboard,
  Clock3,
  Copy,
  ExternalLink,
  Globe2,
  Info,
  LockKeyhole,
  ShieldCheck,
} from 'lucide-react';

import type {
  DomainInstruction,
  DomainInstructionRecord,
} from '../domainInstructionData';

const PURPOSE_LABELS: Record<string, string> = {
  application_ownership: 'Ownership verification',
  storefront_routing: 'Storefront routing',
  remove_application_ownership: 'Remove ownership verification',
  remove_storefront_routing: 'Remove storefront routing',
};

function purposeLabel(purpose: string | null): string {
  if (!purpose) return 'DNS configuration';
  return PURPOSE_LABELS[purpose] ?? 'DNS configuration';
}

function proxyLabel(proxy: DomainInstructionRecord['proxy']): string | null {
  if (proxy === 'dns_only') return 'DNS only / not proxied';
  if (proxy === 'proxied') return 'Proxied';
  if (proxy === 'provider_default') return 'Use provider default';
  return null;
}

function recordSupportsProxy(record: DomainInstructionRecord): boolean {
  return record.type === 'A' || record.type === 'AAAA' || record.type === 'CNAME';
}

function formatExpiry(expiresAt: string): string {
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'UTC',
    timeZoneName: 'short',
  }).format(new Date(expiresAt));
}

function recordCopyText(record: DomainInstructionRecord): string {
  return [
    `Purpose: ${purposeLabel(record.purpose)}`,
    `Type: ${record.type}`,
    `Host / name: ${record.relativeHost ?? 'Not provided — use the full hostname'}`,
    `Full hostname: ${record.fqdn}`,
    `Value: ${record.values.length > 0 ? record.values.join(', ') : 'Not provided'}`,
    `TTL: ${record.ttl ? `${record.ttl} seconds` : 'Not provided'}`,
    `Proxy: ${recordSupportsProxy(record) ? (proxyLabel(record.proxy) ?? 'Not provided') : 'Not applicable'}`,
  ].join('\n');
}

function CopyButton({
  label,
  value,
  onCopy,
}: {
  label: string;
  value: string;
  onCopy: (value: string, successMessage: string) => Promise<void>;
}) {
  return (
    <button
      type="button"
      onClick={() => void onCopy(value, `${label} copied`)}
      className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-wedding-rose hover:bg-wedding-blush/60 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wedding-navy focus-visible:ring-offset-2 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:hover:border-wedding-rose dark:hover:bg-slate-700"
      aria-label={`Copy ${label.toLowerCase()}`}
    >
      <Copy className="h-4 w-4" aria-hidden="true" />
      <span className="hidden sm:inline">Copy</span>
    </button>
  );
}

function DataField({
  label,
  children,
  className = '',
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`min-w-0 border-t border-slate-200 py-4 dark:border-slate-700 ${className}`}>
      <dt className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
        {label}
      </dt>
      <dd className="mt-2 min-w-0 text-sm font-medium leading-6 text-slate-900 dark:text-slate-100">
        {children}
      </dd>
    </div>
  );
}

function UnavailableValue({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-normal text-amber-800 dark:text-amber-200">
      {children}
    </span>
  );
}

function RecordSection({
  record,
  index,
  onCopy,
}: {
  record: DomainInstructionRecord;
  index: number;
  onCopy: (value: string, successMessage: string) => Promise<void>;
}) {
  const proxy = recordSupportsProxy(record)
    ? proxyLabel(record.proxy)
    : 'Not applicable for this record type';

  return (
    <section
      aria-labelledby={`dns-record-${index}`}
      className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900"
    >
      <header className="flex flex-col gap-4 border-b border-slate-200 bg-slate-50/80 px-5 py-5 dark:border-slate-700 dark:bg-slate-800/70 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-wedding-navy px-3 py-1 text-xs font-bold tracking-wide text-white">
              {record.type}
            </span>
            <span className="text-sm font-semibold text-wedding-navy dark:text-wedding-sage">
              Record {index + 1}
            </span>
          </div>
          <h2
            id={`dns-record-${index}`}
            className="mt-3 text-xl font-semibold tracking-tight text-slate-950 dark:text-white"
          >
            {purposeLabel(record.purpose)}
          </h2>
        </div>
        <button
          type="button"
          onClick={() => void onCopy(recordCopyText(record), `Record ${index + 1} copied`)}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-wedding-navy px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-[#142a47] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wedding-navy focus-visible:ring-offset-2 dark:bg-wedding-rose dark:text-slate-950 dark:hover:bg-[#e0b8b8]"
          aria-label={`Copy DNS record ${index + 1}`}
        >
          <Clipboard className="h-4 w-4" aria-hidden="true" />
          Copy record
        </button>
      </header>

      <dl className="grid px-5 sm:grid-cols-2 sm:gap-x-8 sm:px-6">
        <DataField label="Host / name" className="sm:col-span-2">
          {record.relativeHost ? (
            <code className="break-all rounded bg-slate-100 px-2 py-1 font-mono text-[0.82rem] text-slate-950 dark:bg-slate-800 dark:text-slate-50">
              {record.relativeHost}
            </code>
          ) : (
            <UnavailableValue>
              Not included — use the full hostname below.
            </UnavailableValue>
          )}
        </DataField>

        <DataField label="Full hostname" className="sm:col-span-2">
          <div className="flex min-w-0 items-start gap-3">
            <code className="min-w-0 flex-1 break-all rounded bg-slate-100 px-2 py-1 font-mono text-[0.82rem] text-slate-950 dark:bg-slate-800 dark:text-slate-50">
              {record.fqdn}
            </code>
            <CopyButton label="Full hostname" value={record.fqdn} onCopy={onCopy} />
          </div>
        </DataField>

        <DataField label="Value / target" className="sm:col-span-2">
          {record.values.length > 0 ? (
            <div className="space-y-3">
              {record.values.map((value) => (
                <div key={value} className="flex min-w-0 items-start gap-3">
                  <code className="min-w-0 flex-1 break-all rounded bg-slate-100 px-2 py-1 font-mono text-[0.82rem] text-slate-950 dark:bg-slate-800 dark:text-slate-50">
                    {value}
                  </code>
                  <CopyButton label="Record value" value={value} onCopy={onCopy} />
                </div>
              ))}
            </div>
          ) : (
            <UnavailableValue>
              Not included — ask the planner for a refreshed link.
            </UnavailableValue>
          )}
        </DataField>

        <DataField label="TTL">
          {record.ttl ? (
            `${record.ttl} seconds`
          ) : (
            <UnavailableValue>Not provided</UnavailableValue>
          )}
        </DataField>
        <DataField label="Proxy setting">
          {proxy ?? (
            <UnavailableValue>
              Not provided — do not change proxy mode without guidance.
            </UnavailableValue>
          )}
        </DataField>
      </dl>
    </section>
  );
}

export function DomainInstructionsView({ instruction }: { instruction: DomainInstruction }) {
  const [copyStatus, setCopyStatus] = useState('');
  const hasIncompleteProviderDetails =
    !instruction.provider.name ||
    !instruction.provider.zone ||
    instruction.records.some(
      (record) =>
        !record.relativeHost ||
        (recordSupportsProxy(record) && !record.proxy),
    );

  async function copyValue(value: string, successMessage: string) {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(value);
      setCopyStatus(`${successMessage}.`);
    } catch {
      setCopyStatus('Copy failed. Select the text and copy it manually.');
    }
  }

  const allRecords = instruction.records
    .map((record, index) => `Record ${index + 1}\n${recordCopyText(record)}`)
    .join('\n\n');

  return (
    <main className="min-h-screen overflow-x-hidden bg-[#f6f3f1] text-slate-950 dark:bg-slate-950 dark:text-slate-50">
      <div className="border-b border-slate-200 bg-wedding-navy text-white dark:border-slate-700">
        <div className="mx-auto flex max-w-4xl flex-col gap-4 px-4 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <a
            href="/"
            className="inline-flex w-fit items-center rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-wedding-navy"
            aria-label="The Special Wedding homepage"
          >
            {/* This is a bundled first-party asset; no customer data leaves the page. */}
            <img src="/logo-mark.svg" alt="The Special Wedding" className="h-12 w-auto" />
          </a>
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-white/30 bg-white/10 px-3 py-2 text-sm font-semibold text-white">
            <LockKeyhole className="h-4 w-4" aria-hidden="true" />
            Secure read-only link
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6 sm:py-14">
        <header className="max-w-3xl">
          <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-[#925f65] dark:text-wedding-rose">
            <ShieldCheck className="h-5 w-5" aria-hidden="true" />
            Storefront domain setup
          </p>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-wedding-navy dark:text-white sm:text-4xl">
            Add these DNS records
          </h1>
          <p className="mt-4 text-base leading-7 text-slate-700 dark:text-slate-300 sm:text-lg">
            These instructions connect <strong className="text-slate-950 dark:text-white">{instruction.hostname}</strong> to a planner&apos;s storefront. Sign in to the DNS provider directly; The Special Wedding never receives the provider password.
          </p>
        </header>

        <section
          aria-labelledby="provider-heading"
          className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900 sm:p-6"
        >
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-600 dark:text-slate-300">
                <Globe2 className="h-5 w-5 text-wedding-navy dark:text-wedding-sage" aria-hidden="true" />
                DNS provider
              </div>
              <h2 id="provider-heading" className="mt-2 text-2xl font-semibold text-slate-950 dark:text-white">
                {instruction.provider.name ?? 'Provider details unavailable'}
              </h2>
              <p className="mt-1 break-all text-sm text-slate-600 dark:text-slate-300">
                DNS zone:{' '}
                {instruction.provider.zone ?? 'Not included in this secure link'}
              </p>
            </div>
            {instruction.provider.controlPanelUrl ? (
              <a
                href={instruction.provider.controlPanelUrl}
                target="_blank"
                rel="noopener noreferrer"
                referrerPolicy="no-referrer"
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-wedding-navy px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-[#142a47] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wedding-navy focus-visible:ring-offset-2 dark:bg-wedding-rose dark:text-slate-950 dark:hover:bg-[#e0b8b8]"
              >
                Open DNS settings
                <ExternalLink className="h-4 w-4" aria-hidden="true" />
              </a>
            ) : (
              <p className="max-w-xs text-sm leading-6 text-amber-800 dark:text-amber-200">
                The DNS control-panel link is not available. Open the provider in a separate browser tab.
              </p>
            )}
          </div>

          <div className="mt-5 flex flex-col gap-3 border-t border-slate-200 pt-5 text-sm text-slate-700 dark:border-slate-700 dark:text-slate-300 sm:flex-row sm:items-center sm:justify-between">
            <span className="inline-flex items-center gap-2">
              <Clock3 className="h-4 w-4" aria-hidden="true" />
              Link expires {formatExpiry(instruction.expiresAt)}
            </span>
            <span className="inline-flex items-center gap-2">
              <LockKeyhole className="h-4 w-4" aria-hidden="true" />
              No publish or account access
            </span>
          </div>
        </section>

        {instruction.note ? (
          <aside className="mt-5 rounded-xl border border-[#d8b9bd] bg-[#fff8f7] p-4 text-sm leading-6 text-slate-800 dark:border-[#7a4b50] dark:bg-[#2b171a] dark:text-slate-100">
            <p className="font-semibold text-slate-950 dark:text-white">Note from the planner</p>
            <p className="mt-1 whitespace-pre-wrap break-words">{instruction.note}</p>
          </aside>
        ) : null}

        {hasIncompleteProviderDetails ? (
          <aside className="mt-5 flex gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm leading-6 text-amber-950 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100">
            <Info className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-semibold">Some provider-specific details are unavailable.</p>
              <p className="mt-1">
                Use the exact full hostnames and values shown here. Do not guess a relative host or proxy mode; ask the planner for a refreshed link if a required field is missing.
              </p>
            </div>
          </aside>
        ) : null}

        <div className="mt-8 flex flex-col gap-4 border-b border-slate-300 pb-5 dark:border-slate-700 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-wedding-navy dark:text-white">DNS records</h2>
            <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">
              Add every record exactly as shown. Existing website records should not be overwritten unless the planner explicitly confirms a migration cutover.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void copyValue(allRecords, 'All DNS records copied')}
            className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-lg border border-wedding-navy bg-white px-4 py-2 text-sm font-semibold text-wedding-navy shadow-sm transition hover:bg-wedding-navy hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wedding-navy focus-visible:ring-offset-2 dark:border-wedding-rose dark:bg-slate-900 dark:text-wedding-rose dark:hover:bg-wedding-rose dark:hover:text-slate-950"
            aria-label="Copy all DNS records"
          >
            <Copy className="h-4 w-4" aria-hidden="true" />
            Copy all records
          </button>
        </div>

        <div className="mt-6 space-y-5">
          {instruction.records.map((record, index) => (
            <RecordSection
              key={`${record.type}-${record.fqdn}-${index}`}
              record={record}
              index={index}
              onCopy={copyValue}
            />
          ))}
        </div>

        <p
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className={`sticky bottom-4 mx-auto mt-6 w-fit max-w-full rounded-full px-4 py-3 text-center text-sm font-semibold shadow-lg transition ${
            copyStatus
              ? 'bg-wedding-navy text-white dark:bg-wedding-rose dark:text-slate-950'
              : 'sr-only'
          }`}
        >
          {copyStatus}
        </p>

        <footer className="mt-10 border-t border-slate-300 pt-6 text-sm leading-6 text-slate-600 dark:border-slate-700 dark:text-slate-300">
          <p className="inline-flex items-start gap-2">
            <Check className="mt-1 h-4 w-4 shrink-0 text-emerald-700 dark:text-emerald-300" aria-hidden="true" />
            This link only displays DNS instructions. It cannot publish, activate, transfer, or disconnect a storefront.
          </p>
        </footer>
      </div>
    </main>
  );
}
