"use client";

import {
  AlertCircle,
  Check,
  CheckCircle2,
  ClipboardCopy,
  Clock3,
  ExternalLink,
  Globe2,
  Loader2,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Trash2,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAdmin } from "@/contexts/AdminContext";
import {
  claimCustomDomain,
  completeCustomDomainConnect,
  getCustomDomainStatus,
  getCustomDomainInstructionLinks,
  normalizeStorefrontError,
  observeCustomDomain,
  preflightCustomDomain,
  removeCustomDomain,
  revokeCustomDomainInstructions,
  retryCustomDomainVerification,
  sendCustomDomainInstructions,
  startCustomDomainConnect,
  StorefrontCustomerError,
  verifyCustomDomain,
  type StorefrontApiTransport,
  type StorefrontDomainDnsRecord,
  type StorefrontDomainIntent,
  type StorefrontDomainInstructionLinkSummary,
  type StorefrontDomainJourney,
  type StorefrontDomainPreflight,
  type StorefrontDomainSetupMethod,
  type StorefrontOwnershipVerificationHttp,
} from "@/services/storefrontApi";

const PASSING_STATUSES = new Set([
  "active",
  "complete",
  "completed",
  "passed",
  "ready",
  "verified",
]);
const ACTION_REQUIRED_STATUSES = new Set([
  "action_required",
  "blocked",
  "conflict",
  "error",
  "expired",
  "failed",
  "operator_review",
  "validation_timed_out",
]);
const EXPECTED_DNS_WAITING_ERROR_CODES = new Set([
  "dns_ownership_not_verified",
  "ownership_record_missing",
]);

function isExpectedDnsWaitingError(journey: StorefrontDomainJourney): boolean {
  return Boolean(
    journey.applicationStatus === "dns_setup_pending" &&
    journey.lastError &&
    EXPECTED_DNS_WAITING_ERROR_CODES.has(journey.lastError.code),
  );
}

// The leased reconciliation worker sweeps every 30 seconds. Keep the modal
// attached long enough to observe one full sweep without turning Check again
// into a provider retry or making the customer click twice.
const OBSERVATION_POLL_DELAYS_MS = [
  250, 750, 1500, 3000, 5000, 8000, 12000, 15000,
];

function observationSignature(journey: StorefrontDomainJourney | null): string {
  if (!journey) return "none";
  return JSON.stringify({
    revision: journey.revision,
    applicationStatus: journey.applicationStatus,
    action: journey.action,
    ownershipStatus: journey.ownershipStatus,
    routingDnsStatus: journey.routingDnsStatus,
    providerHostnameStatus: journey.providerHostnameStatus,
    sslStatus: journey.sslStatus,
    httpsStatus: journey.httpsStatus,
    expectedRecords: journey.expectedRecords.map((record) => ({
      type: record.type,
      fqdn: record.fqdn,
      observedValues: record.observedValues,
      matches: record.matches,
    })),
    observedRecords: journey.observedRecords,
    lastCheckedAt: journey.lastCheckedAt,
    lastError: journey.lastError,
  });
}

const controlClass =
  "min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-[16px] text-slate-900 outline-none placeholder:text-slate-500 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/30 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500 dark:border-slate-600 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-400 dark:disabled:bg-slate-900";
const secondaryButtonClass =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-base font-semibold text-slate-800 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 disabled:cursor-not-allowed disabled:border-slate-300 disabled:bg-slate-200 disabled:text-slate-700 disabled:hover:bg-slate-200 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800 dark:disabled:border-slate-600 dark:disabled:bg-slate-800 dark:disabled:text-slate-200 dark:disabled:hover:bg-slate-800";
const primaryButtonClass =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-primary-800 px-4 text-base font-semibold text-white transition hover:bg-primary-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-700 disabled:hover:bg-slate-200 dark:disabled:bg-slate-800 dark:disabled:text-slate-200 dark:disabled:hover:bg-slate-800 dark:focus-visible:ring-offset-slate-950";

function humanize(value: string): string {
  return value
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function isPassing(status: string): boolean {
  return PASSING_STATUSES.has(status.toLowerCase());
}

function normalizeCustomerWebAddress(value: string): string {
  const candidate = value.trim();
  if (!candidate.includes("://")) return candidate;
  try {
    const parsed = new URL(candidate);
    if (
      !["http:", "https:"].includes(parsed.protocol) ||
      parsed.username ||
      parsed.password ||
      parsed.port
    ) {
      return candidate;
    }
    return parsed.hostname;
  } catch {
    return candidate;
  }
}

function formatCheckedAt(value: string | null): string {
  if (!value) return "Not checked yet";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function DomainValue({
  label,
  value,
  onCopy,
}: {
  label: string;
  value: string;
  onCopy?: (label: string, value: string) => void;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-950">
      <p className="text-base font-semibold text-slate-700 dark:text-slate-300">
        {label}
      </p>
      <div className="mt-1 flex items-start gap-2">
        <code className="min-w-0 flex-1 break-all text-[16px] text-slate-900 dark:text-slate-100">
          {value}
        </code>
        {onCopy ? (
          <button
            type="button"
            onClick={() => onCopy(label, value)}
            className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-slate-600 transition hover:bg-slate-100 hover:text-slate-950 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white"
            aria-label={`Copy ${label}`}
          >
            <ClipboardCopy className="h-4 w-4" aria-hidden="true" />
          </button>
        ) : null}
      </div>
    </div>
  );
}

/** Kept for provider responses that use HTTP ownership proof instead of DNS. */
export function StorefrontHttpVerification({
  verification,
}: {
  verification: StorefrontOwnershipVerificationHttp | null;
}) {
  if (!verification) return null;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {verification.http_url ? (
        <DomainValue
          label="HTTP verification URL"
          value={verification.http_url}
        />
      ) : null}
      {verification.http_body ? (
        <DomainValue
          label="HTTP verification body"
          value={verification.http_body}
        />
      ) : null}
    </div>
  );
}

function ProviderSummary({
  preflight,
}: {
  preflight: StorefrontDomainPreflight;
}) {
  const hasConflicts = preflight.conflicts.length > 0;
  const providerNeedsConfirmation =
    !preflight.dnsProvider.id ||
    preflight.dnsProvider.id === "unknown" ||
    preflight.dnsProvider.id === "google_or_squarespace_dns";
  return (
    <div className="space-y-4" aria-live="polite">
      <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-sky-950 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-100">
        <p className="text-base font-semibold">
          {providerNeedsConfirmation
            ? "Confirm where DNS is managed"
            : `${preflight.dnsProvider.name} detected`}
        </p>
        <p className="mt-1 text-base leading-6">
          {providerNeedsConfirmation
            ? `The nameservers match ${preflight.dnsProvider.name}, but they do not identify one customer dashboard with certainty. Check the domain's nameserver or DNS settings before adding records.`
            : "We found the DNS service that controls this hostname. It may be different from the company where the domain was purchased."}
        </p>
      </div>

      <details className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-950">
        <summary className="cursor-pointer text-base font-semibold text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 dark:text-slate-100">
          View provider details
        </summary>
        <dl className="mt-4 grid gap-3 sm:grid-cols-3">
          {[
            ["Domain provider", preflight.dnsProvider.name],
            ["Domain seller", preflight.registrar ?? "Not detected"],
            [
              "Storefront service",
              preflight.platformProvider ?? "The Special Wedding",
            ],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-base font-medium text-slate-600 dark:text-slate-300">
                {label}
              </dt>
              <dd className="mt-1 text-[16px] font-semibold text-slate-950 dark:text-slate-100">
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </details>

      {preflight.recommendedFlow === "assisted_migration" ? (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
          <p className="text-base font-semibold">
            Assisted migration recommended
          </p>
          <p className="mt-1 text-base leading-6">
            This hostname appears to serve an existing site. Keep the current
            records in place until the replacement is ready so customer traffic
            is not interrupted.
          </p>
          {preflight.customerAction ? (
            <p className="mt-3 text-base font-semibold leading-6">
              {preflight.customerAction}
            </p>
          ) : null}
          {hasConflicts ? (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-base">
              {preflight.conflicts.map((conflict) => (
                <li key={`${conflict.code}-${conflict.recordType ?? "record"}`}>
                  {conflict.message ??
                    `${humanize(conflict.code)}: ${conflict.values.join(", ")}`}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      {!preflight.selfServiceAllowed &&
      preflight.recommendedFlow !== "assisted_migration" ? (
        <div className="rounded-xl border border-slate-300 bg-slate-50 p-4 text-slate-950 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100">
          <p className="text-base font-semibold">
            Custom-domain onboarding is limited
          </p>
          <p className="mt-1 text-base leading-6">
            {preflight.customerAction ??
              "Keep using the platform storefront URL while the production pilot is restricted."}
          </p>
        </div>
      ) : null}
    </div>
  );
}

function DnsRecordCard({
  record,
  onCopy,
}: {
  record: StorefrontDomainDnsRecord;
  onCopy: (label: string, value: string) => void;
}) {
  return (
    <article className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-base font-semibold">{humanize(record.purpose)}</p>
          <p className="text-base text-slate-600 dark:text-slate-300">
            {record.type} record
          </p>
        </div>
        {record.matches === true ? (
          <span className="rounded-full bg-emerald-100 px-3 py-1 text-base font-semibold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
            Matches
          </span>
        ) : null}
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <DomainValue
          label="Host in DNS provider"
          value={record.relativeHost}
          onCopy={onCopy}
        />
        <DomainValue
          label="Full hostname"
          value={record.fqdn}
          onCopy={onCopy}
        />
        {record.value ? (
          <div className="lg:col-span-2">
            <DomainValue label="Value" value={record.value} onCopy={onCopy} />
          </div>
        ) : null}
      </div>
      <dl className="grid grid-cols-2 gap-3 text-base sm:grid-cols-4">
        <div>
          <dt className="text-slate-600 dark:text-slate-400">TTL</dt>
          <dd className="mt-1 text-[16px] font-medium">
            {record.ttl ?? "Automatic"}
          </dd>
        </div>
        <div>
          <dt className="text-slate-600 dark:text-slate-400">Proxy</dt>
          <dd className="mt-1 text-[16px] font-medium">
            {record.proxy === "dns_only"
              ? "DNS only"
              : record.proxy
                ? humanize(record.proxy)
                : "Not applicable"}
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="text-slate-600 dark:text-slate-400">Observed now</dt>
          <dd className="mt-1 break-all text-[16px] font-medium">
            {record.observedValues.length
              ? record.observedValues.join(", ")
              : "Not detected"}
          </dd>
        </div>
      </dl>
    </article>
  );
}

function VerificationProgress({
  journey,
}: {
  journey: StorefrontDomainJourney;
}) {
  const ownershipRecord = journey.expectedRecords.find(
    (record) => record.purpose === "application_ownership",
  );
  const routingRecord = journey.expectedRecords.find(
    (record) => record.purpose === "storefront_routing",
  );
  const migrationPrevalidation =
    journey.intent === "migration" &&
    journey.applicationStatus === "migration_prevalidation";
  const migrationCutoverReady =
    journey.intent === "migration" &&
    journey.applicationStatus === "cutover_ready";
  const checks = [
    {
      label: "Ownership",
      status: journey.ownershipStatus,
      expected: ownershipRecord?.value
        ? `${ownershipRecord.type} ${ownershipRecord.fqdn} = ${ownershipRecord.value}`
        : "A current ownership proof for this exact hostname",
      observed: ownershipRecord?.observedValues.length
        ? ownershipRecord.observedValues.join(", ")
        : "Not detected",
    },
    {
      label: "DNS routing",
      status: journey.routingDnsStatus,
      expected: routingRecord?.value
        ? `${routingRecord.type} ${routingRecord.fqdn} → ${routingRecord.value}`
        : migrationPrevalidation
          ? "Withheld until ownership and provider prevalidation are complete"
          : migrationCutoverReady
            ? "Keep the current route until the storefront CNAME is available"
            : "The storefront CNAME target",
      observed: routingRecord?.observedValues.length
        ? routingRecord.observedValues.join(", ")
        : migrationPrevalidation || migrationCutoverReady
          ? "Current website routing remains unchanged"
          : "Not detected",
    },
    {
      label: "Provider hostname",
      status: journey.providerHostnameStatus,
      expected: "Cloudflare custom hostname: Active",
      observed: humanize(journey.providerHostnameStatus),
    },
    {
      label: "SSL certificate",
      status: journey.sslStatus,
      expected: "TLS certificate: Active",
      observed: humanize(journey.sslStatus),
    },
    {
      label: "Secure storefront",
      status: journey.httpsStatus,
      expected: `Signed HTTPS response from ${journey.hostname}`,
      observed: humanize(journey.httpsStatus),
    },
  ] as const;

  return (
    <section aria-labelledby="domain-progress-heading" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h4
            id="domain-progress-heading"
            className="text-[16px] font-semibold text-slate-950 dark:text-slate-100"
          >
            Connection progress
          </h4>
          <p className="mt-1 text-base text-slate-600 dark:text-slate-300">
            Each check is independent. DNS may pass before SSL is ready.
          </p>
        </div>
        <div className="text-right text-base text-slate-600 dark:text-slate-300">
          <p>Last check: {formatCheckedAt(journey.lastCheckedAt)}</p>
          <p>Next automatic check: {formatCheckedAt(journey.nextCheckAt)}</p>
        </div>
      </div>
      {migrationPrevalidation ? (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
          <p className="text-base font-semibold">
            Storefront routing is withheld during prevalidation
          </p>
          <p className="mt-1 text-base leading-6">
            Keep the current website route unchanged. We will show the
            storefront CNAME only after ownership and provider prevalidation
            make the final cutover ready.
          </p>
        </div>
      ) : null}
      {migrationCutoverReady ? (
        <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-sky-950 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-100">
          <p className="text-base font-semibold">
            Storefront routing is ready for cutover
          </p>
          <p className="mt-1 text-base leading-6">
            The storefront routing record is now shown separately from provider
            certificate records. Change the current route only when you are
            ready to send customer traffic to the storefront.
          </p>
        </div>
      ) : null}
      <ol className="grid gap-3">
        {checks.map(({ label, status, expected, observed }) => {
          const passed = isPassing(status);
          const failed = ACTION_REQUIRED_STATUSES.has(status.toLowerCase());
          const Icon = passed ? CheckCircle2 : failed ? XCircle : Clock3;
          const tone = passed
            ? "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-100"
            : failed
              ? "border-red-300 bg-red-50 text-red-900 dark:border-red-800 dark:bg-red-950/40 dark:text-red-100"
              : "border-amber-300 bg-amber-50 text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100";
          return (
            <li key={label} className={`rounded-xl border p-3 ${tone}`}>
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                  <p className="text-base font-semibold">{label}</p>
                </div>
                <span className="rounded-full border border-current/30 px-2.5 py-1 text-base font-semibold">
                  {passed ? "Passed" : failed ? "Action required" : "Waiting"}
                </span>
              </div>
              <dl className="mt-3 grid gap-2 text-base sm:grid-cols-2">
                <div>
                  <dt className="font-semibold">Expected</dt>
                  <dd className="mt-1 break-all">{expected}</dd>
                </div>
                <div>
                  <dt className="font-semibold">Observed</dt>
                  <dd className="mt-1 break-all">{observed}</dd>
                </div>
              </dl>
              <p className="mt-2 text-base font-medium">
                Provider state: {humanize(status)}
              </p>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function FriendlyConnectionProgress({
  journey,
}: {
  journey: StorefrontDomainJourney;
}) {
  const providerConnected = journey.domainConnectAuthorized;
  const dnsReady = [journey.ownershipStatus, journey.routingDnsStatus].every(
    isPassing,
  );
  const secured =
    [
      journey.providerHostnameStatus,
      journey.sslStatus,
      journey.httpsStatus,
    ].every(isPassing) && dnsReady;
  const ready =
    journey.applicationStatus === "active" && providerConnected && secured;
  const steps = [
    {
      label: `${journey.domainConnectProvider ?? journey.dnsProvider.name} connected`,
      description: providerConnected
        ? "Your domain provider approved the requested connection."
        : "Waiting for approval from your domain provider.",
      complete: providerConnected,
    },
    {
      label: "Securing your web address",
      description: secured
        ? "Your secure storefront connection is ready."
        : "We are preparing a secure connection. This often takes a few minutes.",
      complete: secured,
    },
    {
      label: "Ready",
      description: ready
        ? `Visitors can use ${journey.hostname}.`
        : "We will mark the address ready only after every safety check passes.",
      complete: ready,
    },
  ];

  return (
    <section
      aria-labelledby="friendly-domain-progress-heading"
      className="space-y-4"
    >
      <div>
        <h4
          id="friendly-domain-progress-heading"
          className="text-[16px] font-semibold text-slate-950 dark:text-slate-100"
        >
          {ready
            ? "Your custom web address is ready"
            : "Connecting your custom web address"}
        </h4>
        <p className="mt-1 text-base leading-6 text-slate-600 dark:text-slate-300">
          You can close this window and return later. We will keep checking
          automatically.
        </p>
      </div>
      <ol className="space-y-3">
        {steps.map((step) => (
          <li
            key={step.label}
            className={`flex items-start gap-3 rounded-xl border p-4 ${
              step.complete
                ? "border-emerald-300 bg-emerald-50 text-emerald-950 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-100"
                : "border-slate-200 bg-white text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
            }`}
          >
            {step.complete ? (
              <CheckCircle2
                className="mt-0.5 h-5 w-5 shrink-0"
                aria-hidden="true"
              />
            ) : (
              <Clock3
                className="mt-0.5 h-5 w-5 shrink-0 text-amber-600 dark:text-amber-300"
                aria-hidden="true"
              />
            )}
            <div>
              <p className="text-base font-semibold">{step.label}</p>
              <p className="mt-1 text-base leading-6">{step.description}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function JourneyNotice({ journey }: { journey: StorefrontDomainJourney }) {
  if (journey.conflictCode === "hostname_reserved") {
    const proofReceived =
      journey.applicationStatus === "operator_review" ||
      journey.action === "operator_review";
    return (
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
        <p className="text-base font-semibold">
          {proofReceived
            ? "Ownership proof received — review required"
            : "This hostname is already reserved"}
        </p>
        <p className="mt-1 text-base leading-6">
          {proofReceived
            ? "We verified the fresh TXT proof and paused for a safe operator review. The hostname was not reassigned and no provider routing was changed."
            : "Add the fresh TXT record shown below to prove control. We do not reveal who currently uses the hostname, and proof never transfers it automatically."}
        </p>
      </div>
    );
  }
  if (
    journey.applicationStatus === "operator_review" ||
    journey.action === "operator_review"
  ) {
    const assistedCloudflareMigration =
      journey.lastError?.code ===
      "cloudflare_o2o_migration_requires_assistance";
    return (
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
        <p className="text-base font-semibold">
          {assistedCloudflareMigration
            ? "Ownership verified — assisted cutover required"
            : "Operator review required"}
        </p>
        <p className="mt-1 text-base leading-6">
          {assistedCloudflareMigration
            ? "The current Cloudflare routing remains unchanged. We paused before provider provisioning so an operator can coordinate a safe cutover without interrupting the existing site."
            : "We paused automation because the provider result could not be confirmed safely."}
        </p>
        {assistedCloudflareMigration ? (
          <a
            href={`/admin/support?${new URLSearchParams({
              action: "create",
              category: "technical",
              priority: "high",
              subject: `Assisted storefront cutover for ${journey.hostname}`,
              description: `Ownership is verified for ${journey.hostname}. Please coordinate the Cloudflare-to-Cloudflare storefront cutover. I have not changed the current DNS routing.${journey.lastError?.supportId ? ` Support ID: ${journey.lastError.supportId}` : ""}`,
            }).toString()}`}
            className={`${secondaryButtonClass} mt-3`}
          >
            Request assisted cutover
          </a>
        ) : null}
      </div>
    );
  }
  if (
    journey.applicationStatus === "authorization_cancelled" ||
    journey.action === "authorization_cancelled"
  ) {
    return (
      <div className="rounded-xl border border-slate-300 bg-slate-50 p-4 text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100">
        <p className="text-base font-semibold">Automatic setup was cancelled</p>
        <p className="mt-1 text-base">
          Nothing was changed. Resume automatic setup or use the manual records
          below.
        </p>
      </div>
    );
  }
  return null;
}

function CustomerErrorNotice({ error }: { error: StorefrontCustomerError }) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-red-300 bg-red-50 p-4 text-red-950 dark:border-red-800 dark:bg-red-950/40 dark:text-red-100"
    >
      <div className="flex items-start gap-2">
        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
        <div>
          <p className="text-base font-semibold">{error.message}</p>
          {error.customerAction ? (
            <p className="mt-1 text-base leading-6">{error.customerAction}</p>
          ) : null}
          {error.supportId ? (
            <p className="mt-2 text-base font-medium">
              Support ID: {error.supportId}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export interface CustomDomainPanelProps {
  transport: StorefrontApiTransport;
  canActivate: boolean;
  canManageExisting?: boolean;
  platformUrl: string;
  isPublished: boolean;
  attemptId?: string | null;
  onProviderAuthorize?: (url: string) => void;
  onResumeHandled?: () => void;
}

export function CustomDomainPanel({
  transport,
  canActivate,
  canManageExisting = false,
  platformUrl,
  isPublished,
  attemptId = null,
  onProviderAuthorize,
  onResumeHandled,
}: CustomDomainPanelProps) {
  const [domainInput, setDomainInput] = useState("");
  const [intent, setIntent] = useState<StorefrontDomainIntent>("new");
  const [preflight, setPreflight] = useState<StorefrontDomainPreflight | null>(
    null,
  );
  const [journey, setJourney] = useState<StorefrontDomainJourney | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusLoadState, setStatusLoadState] = useState<
    "loading" | "ready" | "error"
  >("loading");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<StorefrontCustomerError | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [instructionEmail, setInstructionEmail] = useState("");
  const [instructionNote, setInstructionNote] = useState("");
  const [instructionError, setInstructionError] = useState<string | null>(null);
  const [instructionReceipts, setInstructionReceipts] = useState<
    Array<StorefrontDomainInstructionLinkSummary & { revoked: boolean }>
  >([]);
  const [instructionLinksLoadState, setInstructionLinksLoadState] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [disconnectOpen, setDisconnectOpen] = useState(false);
  const [disconnectedRecords, setDisconnectedRecords] = useState<
    StorefrontDomainDnsRecord[]
  >([]);
  const [cancelledConflict, setCancelledConflict] = useState(false);
  const [cancelledSetup, setCancelledSetup] = useState(false);
  const [automaticSupportState, setAutomaticSupportState] = useState<
    "idle" | "checking" | "supported" | "unavailable"
  >("idle");
  const resumedAttemptRef = useRef<string | null>(null);
  const disconnectTriggerRef = useRef<HTMLButtonElement | null>(null);
  const keepDomainRef = useRef<HTMLButtonElement | null>(null);
  const confirmDisconnectRef = useRef<HTMLButtonElement | null>(null);
  const errorNoticeRef = useRef<HTMLDivElement | null>(null);
  const instructionAttemptRef = useRef<string | null>(null);
  const observationPollRef = useRef(0);
  const observationPollTimerRef = useRef<number | null>(null);
  const observationPollResolveRef = useRef<(() => void) | null>(null);
  const automaticSupportCheckRef = useRef(0);
  const errorFocusTimerRef = useRef<number | null>(null);

  const setCaughtError = useCallback((caught: unknown, fallback: string) => {
    setError(normalizeStorefrontError(caught, fallback));
  }, []);

  const cancelObservationPoll = useCallback(() => {
    const resolvePendingPoll = observationPollResolveRef.current;
    if (observationPollTimerRef.current !== null) {
      window.clearTimeout(observationPollTimerRef.current);
      observationPollTimerRef.current = null;
    }
    observationPollResolveRef.current = null;
    resolvePendingPoll?.();
  }, []);

  const waitForObservationPoll = useCallback(
    (delayMs: number) =>
      new Promise<void>((resolve) => {
        observationPollResolveRef.current = resolve;
        observationPollTimerRef.current = window.setTimeout(() => {
          observationPollTimerRef.current = null;
          observationPollResolveRef.current = null;
          resolve();
        }, delayMs);
      }),
    [],
  );

  const loadStatus = useCallback(async () => {
    setLoading(true);
    setStatusLoadState("loading");
    setJourney(null);
    setDisconnectedRecords([]);
    setCancelledConflict(false);
    setCancelledSetup(false);
    setError(null);
    try {
      setJourney(await getCustomDomainStatus(transport));
      setStatusLoadState("ready");
    } catch (caught) {
      setStatusLoadState("error");
      setCaughtError(
        caught,
        "We could not load the current custom-domain status.",
      );
    } finally {
      setLoading(false);
    }
  }, [setCaughtError, transport]);

  const completeResumedAuthorization = useCallback(
    async (force = false) => {
      if (!attemptId || (!force && resumedAttemptRef.current === attemptId))
        return;
      resumedAttemptRef.current = attemptId;
      setLoading(true);
      setStatusLoadState("loading");
      setDisconnectedRecords([]);
      setCancelledConflict(false);
      setCancelledSetup(false);
      setError(null);
      try {
        await completeCustomDomainConnect(attemptId, transport);
        setJourney(await getCustomDomainStatus(transport, attemptId));
        setStatusLoadState("ready");
        setAnnouncement(
          "Automatic DNS authorization completed. Connection status refreshed.",
        );
        onResumeHandled?.();
      } catch (caught) {
        const completionError = normalizeStorefrontError(
          caught,
          "We could not finish the automatic DNS authorization.",
        );
        if (completionError.code === "domain_connect_flow_consumed") {
          try {
            setJourney(await getCustomDomainStatus(transport, attemptId));
            setStatusLoadState("ready");
            setAnnouncement(
              "This one-time authorization was already completed. Connection status refreshed.",
            );
            onResumeHandled?.();
            return;
          } catch (refreshError) {
            resumedAttemptRef.current = null;
            setStatusLoadState("error");
            setCaughtError(
              refreshError,
              "The authorization was already completed, but its current status could not be loaded.",
            );
            return;
          }
        }
        resumedAttemptRef.current = null;
        setStatusLoadState("error");
        setError(completionError);
      } finally {
        setLoading(false);
      }
    },
    [attemptId, onResumeHandled, setCaughtError, transport],
  );

  useEffect(() => {
    if (!canActivate && !canManageExisting) {
      setJourney(null);
      setStatusLoadState("ready");
      setLoading(false);
      return;
    }
    if (attemptId) {
      void completeResumedAuthorization();
      return;
    }
    void loadStatus();
  }, [
    attemptId,
    canActivate,
    canManageExisting,
    completeResumedAuthorization,
    loadStatus,
  ]);

  useEffect(() => {
    if (disconnectOpen) keepDomainRef.current?.focus();
  }, [disconnectOpen]);

  useEffect(
    () => () => {
      observationPollRef.current += 1;
      cancelObservationPoll();
      if (errorFocusTimerRef.current !== null) {
        window.clearTimeout(errorFocusTimerRef.current);
        errorFocusTimerRef.current = null;
      }
    },
    [cancelObservationPoll],
  );

  const loadInstructionLinks = useCallback(
    async (currentAttemptId: string) => {
      instructionAttemptRef.current = currentAttemptId;
      setInstructionLinksLoadState("loading");
      try {
        const links = await getCustomDomainInstructionLinks(
          currentAttemptId,
          transport,
        );
        if (instructionAttemptRef.current !== currentAttemptId) return;
        setInstructionReceipts(
          links.map((link) => ({ ...link, revoked: false })),
        );
        setInstructionLinksLoadState("ready");
      } catch {
        if (instructionAttemptRef.current !== currentAttemptId) return;
        setInstructionReceipts([]);
        setInstructionLinksLoadState("error");
      }
    },
    [transport],
  );

  useEffect(() => {
    const currentAttemptId = journey?.attemptId;
    if (
      !currentAttemptId ||
      journey?.applicationStatus === "disconnected" ||
      Boolean(journey?.conflictCode)
    ) {
      instructionAttemptRef.current = null;
      setInstructionReceipts([]);
      setInstructionLinksLoadState("idle");
      return;
    }
    void loadInstructionLinks(currentAttemptId);
  }, [
    journey?.applicationStatus,
    journey?.attemptId,
    journey?.conflictCode,
    loadInstructionLinks,
  ]);

  const closeDisconnectConfirmation = () => {
    setDisconnectOpen(false);
    window.setTimeout(() => disconnectTriggerRef.current?.focus(), 0);
  };

  const copyValue = useCallback(async (label: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setAnnouncement(`Copied ${label}.`);
    } catch {
      setAnnouncement(
        `Could not copy ${label}. Select and copy the value manually.`,
      );
    }
  }, []);

  const copyAllRecords = async () => {
    if (!journey) return;
    const text = journey.expectedRecords
      .map((record) =>
        [
          `Purpose: ${humanize(record.purpose)}`,
          `Type: ${record.type}`,
          `Host in DNS provider: ${record.relativeHost}`,
          `Full hostname: ${record.fqdn}`,
          `Value: ${record.value ?? ""}`,
          `TTL: ${record.ttl ?? "Automatic"}`,
          `Proxy: ${record.proxy === "dns_only" ? "DNS only" : record.proxy ? humanize(record.proxy) : "Not applicable"}`,
        ].join("\n"),
      )
      .join("\n\n");
    try {
      await navigator.clipboard.writeText(text);
      setAnnouncement("Copied all DNS records.");
    } catch {
      setAnnouncement(
        "Could not copy all DNS records. Copy each value manually.",
      );
    }
  };

  const handlePreflight = async () => {
    const hostname = normalizeCustomerWebAddress(domainInput);
    if (!hostname) return;
    setDomainInput(hostname);
    setSubmitting(true);
    setError(null);
    setPreflight(null);
    try {
      setPreflight(await preflightCustomDomain(hostname, intent, transport));
    } catch (caught) {
      setCaughtError(caught, "We could not check this domain.");
    } finally {
      setSubmitting(false);
    }
  };

  const claim = async (
    method: StorefrontDomainSetupMethod,
  ): Promise<StorefrontDomainJourney | null> => {
    if (!preflight) return null;
    const claimed = await claimCustomDomain(
      preflight.hostname,
      intent,
      method,
      transport,
    );
    setJourney(claimed);
    setPreflight(null);
    return claimed;
  };

  const handleManualSetup = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await claim("manual");
    } catch (caught) {
      setCaughtError(caught, "We could not start manual domain setup.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleAutomaticSetup = async () => {
    if (!preflight?.domainConnectSupported) return;
    setSubmitting(true);
    setError(null);
    try {
      const claimed = await claim("automatic");
      if (!claimed?.attemptId) {
        throw new Error(
          "Automatic setup could not create a resumable attempt.",
        );
      }
      setAnnouncement(
        "Automatic setup is ready. Review the exact DNS changes before continuing.",
      );
    } catch (caught) {
      setCaughtError(
        caught,
        "We could not prepare the DNS provider authorization.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleAutomaticAuthorization = async () => {
    if (!journey?.attemptId) return;
    setSubmitting(true);
    setError(null);
    try {
      const authorization = await startCustomDomainConnect(
        journey.attemptId,
        transport,
      );
      if (onProviderAuthorize) {
        onProviderAuthorize(authorization.authorizationUrl);
      } else {
        window.location.assign(authorization.authorizationUrl);
      }
    } catch (caught) {
      setCaughtError(
        caught,
        "We could not open the DNS provider authorization.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleSwitchToManualSetup = async () => {
    if (!journey) return;
    setSubmitting(true);
    setError(null);
    try {
      setJourney(
        await claimCustomDomain(
          journey.hostname,
          journey.intent,
          "manual",
          transport,
        ),
      );
      setAnnouncement("Manual setup selected. Add the records shown below.");
    } catch (caught) {
      setCaughtError(caught, "We could not switch to manual domain setup.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleVerify = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const verifiedJourney = await verifyCustomDomain(
        transport,
        journey?.attemptId,
      );
      setJourney(verifiedJourney);
      if (
        verifiedJourney?.lastError &&
        isExpectedDnsWaitingError(verifiedJourney)
      ) {
        setError(new StorefrontCustomerError(verifiedJourney.lastError));
      }
    } catch (caught) {
      setCaughtError(caught, "We could not verify the DNS records.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetry = async () => {
    if (!journey?.attemptId) return;
    setSubmitting(true);
    setError(null);
    try {
      setJourney(
        await retryCustomDomainVerification(journey.attemptId, transport),
      );
    } catch (caught) {
      setCaughtError(caught, "We could not retry domain verification.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleObserve = async () => {
    if (!journey?.attemptId) return;
    const currentAttemptId = journey.attemptId;
    const pollRevision = observationPollRef.current + 1;
    observationPollRef.current = pollRevision;
    setSubmitting(true);
    setError(null);
    try {
      const observed = await observeCustomDomain(currentAttemptId, transport);
      if (observed) setJourney(observed);
      const scheduledSignature = observationSignature(observed ?? journey);
      setAnnouncement(
        "Checking authoritative DNS, certificate, and HTTPS status. This can take up to about a minute.",
      );

      for (const delayMs of OBSERVATION_POLL_DELAYS_MS) {
        await waitForObservationPoll(delayMs);
        if (observationPollRef.current !== pollRevision) return;
        const refreshed = await getCustomDomainStatus(
          transport,
          currentAttemptId,
        );
        if (observationPollRef.current !== pollRevision) return;
        if (!refreshed) continue;
        setJourney(refreshed);
        if (observationSignature(refreshed) !== scheduledSignature) {
          setAnnouncement("DNS and connection status refreshed.");
          return;
        }
      }

      setAnnouncement(
        "The status check is still running. Keep this window open or use Check again later.",
      );
    } catch (caught) {
      const observationError = normalizeStorefrontError(
        caught,
        "We could not check the latest domain status.",
      );
      if (observationError.code === "domain_attempt_not_found") {
        try {
          const currentJourney = await getCustomDomainStatus(transport);
          if (currentJourney?.applicationStatus === "disconnected") {
            setJourney(currentJourney);
            setAnnouncement("Domain cleanup completed.");
            return;
          }
        } catch {
          // Preserve the original actionable status error below.
        }
      }
      setError(observationError);
    } finally {
      if (observationPollRef.current === pollRevision) setSubmitting(false);
    }
  };

  const handleSendInstructions = async () => {
    if (!journey?.attemptId) return;
    const email = instructionEmail.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setInstructionError(
        "Enter a valid email address for the person managing DNS.",
      );
      return;
    }
    setSubmitting(true);
    setInstructionError(null);
    setError(null);
    try {
      const receipt = await sendCustomDomainInstructions(
        {
          attemptId: journey.attemptId,
          email,
          ...(instructionNote.trim() ? { note: instructionNote.trim() } : {}),
        },
        transport,
      );
      setInstructionReceipts((current) => [
        { ...receipt, revoked: false },
        ...current.filter((item) => item.linkId !== receipt.linkId),
      ]);
      setInstructionLinksLoadState("ready");
      setAnnouncement(`DNS instructions sent to ${email}.`);
    } catch (caught) {
      setCaughtError(caught, "We could not send the DNS instructions.");
      void loadInstructionLinks(journey.attemptId);
    } finally {
      setSubmitting(false);
    }
  };

  const handleRevokeInstructions = async (
    instructionReceipt: StorefrontDomainInstructionLinkSummary & {
      revoked: boolean;
    },
  ) => {
    if (instructionReceipt.revoked) return;
    setSubmitting(true);
    setInstructionError(null);
    setError(null);
    try {
      await revokeCustomDomainInstructions(
        instructionReceipt.linkId,
        transport,
      );
      setInstructionReceipts((current) =>
        current.map((item) =>
          item.linkId === instructionReceipt.linkId
            ? { ...item, revoked: true }
            : item,
        ),
      );
      setAnnouncement("The DNS instruction link was revoked.");
    } catch (caught) {
      setCaughtError(caught, "We could not revoke the DNS instruction link.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDisconnect = async () => {
    if (!journey) return;
    setSubmitting(true);
    setError(null);
    try {
      const cleanup = journey.cleanupRecords.length
        ? journey.cleanupRecords
        : journey.expectedRecords;
      const wasConflictClaim = journey.conflictCode === "hostname_reserved";
      const wasActiveDomain = active;
      await removeCustomDomain(transport);
      setDisconnectedRecords(cleanup);
      setCancelledConflict(wasConflictClaim);
      setCancelledSetup(!wasConflictClaim && !wasActiveDomain);
      setJourney(null);
      setPreflight(null);
      setDisconnectOpen(false);
      setAnnouncement(
        wasConflictClaim
          ? "Ownership review cancelled."
          : wasActiveDomain
            ? "Custom domain disconnected."
            : "Custom-domain setup cancelled.",
      );
    } catch (caught) {
      setDisconnectOpen(false);
      setCaughtError(caught, "We could not disconnect the custom domain.");
      // Disconnect intent is monotonic on the backend. Until the current
      // lifecycle state can be re-read, fail closed instead of continuing to
      // present a public instruction link as active.
      instructionAttemptRef.current = null;
      setInstructionReceipts([]);
      setInstructionLinksLoadState("error");
      try {
        const latestJourney = await getCustomDomainStatus(transport);
        setJourney(latestJourney);
        if (latestJourney?.attemptId) {
          await loadInstructionLinks(latestJourney.attemptId);
        }
      } catch {
        // Preserve the actionable disconnect error. The explicit retry affordance
        // remains available for both status and instruction-link observation.
      }
      errorFocusTimerRef.current = window.setTimeout(() => {
        errorFocusTimerRef.current = null;
        errorNoticeRef.current?.focus();
      }, 0);
    } finally {
      setSubmitting(false);
    }
  };

  const active = useMemo(
    () =>
      Boolean(journey) &&
      journey?.applicationStatus === "active" &&
      [
        journey.ownershipStatus,
        journey.routingDnsStatus,
        journey.providerHostnameStatus,
        journey.sslStatus,
        journey.httpsStatus,
      ].every(isPassing),
    [journey],
  );
  const automaticConsentCandidate = Boolean(
    canActivate &&
    journey?.attemptId &&
    journey.intent === "new" &&
    journey.setupMethod === "automatic" &&
    !journey.domainConnectAuthorized &&
    journey.domainConnectSupported &&
    [
      "claim_pending",
      "dns_setup_pending",
      "authorization_cancelled",
      "action_required",
    ].includes(journey.applicationStatus),
  );
  useEffect(() => {
    const checkId = ++automaticSupportCheckRef.current;
    if (!automaticConsentCandidate || !journey) {
      setAutomaticSupportState("idle");
      return;
    }

    setAutomaticSupportState("checking");
    void preflightCustomDomain(journey.hostname, journey.intent, transport)
      .then((currentPreflight) => {
        if (automaticSupportCheckRef.current !== checkId) return;
        const exactAutomaticSetupAvailable = Boolean(
          currentPreflight.intent === "new" &&
          currentPreflight.selfServiceAllowed &&
          currentPreflight.domainConnectSupported &&
          currentPreflight.recommendedFlow === "automatic",
        );
        setAutomaticSupportState(
          exactAutomaticSetupAvailable ? "supported" : "unavailable",
        );
      })
      .catch(() => {
        if (automaticSupportCheckRef.current !== checkId) return;
        // A provider-discovery failure must never leave a stale authorization
        // promise on screen. Manual setup remains the safe customer path.
        setAutomaticSupportState("unavailable");
      });

    return () => {
      if (automaticSupportCheckRef.current === checkId) {
        automaticSupportCheckRef.current += 1;
      }
    };
  }, [
    automaticConsentCandidate,
    journey?.hostname,
    journey?.intent,
    journey,
    transport,
  ]);
  const canAuthorizeAutomatically = Boolean(
    automaticConsentCandidate && automaticSupportState === "supported",
  );
  const automaticJourney = Boolean(
    journey &&
    journey.intent === "new" &&
    journey.domainConnectSupported &&
    journey.setupMethod === "automatic",
  );
  const automaticConsentPending = Boolean(
    automaticJourney &&
    !journey?.domainConnectAuthorized &&
    canAuthorizeAutomatically,
  );
  const automaticSupportChecking = Boolean(
    automaticConsentCandidate &&
    (automaticSupportState === "idle" ||
      automaticSupportState === "checking"),
  );
  const automaticSupportUnavailable = Boolean(
    automaticConsentCandidate && automaticSupportState === "unavailable",
  );
  const canRetryProviderVerification = Boolean(
    canActivate &&
    !journey?.conflictCode &&
    journey?.lastError?.retryable &&
    journey.attemptId &&
    !["not_started", "not_created", "pending"].includes(
      journey.providerHostnameStatus.toLowerCase(),
    ),
  );
  const operatorReview = Boolean(
    journey &&
    (journey.applicationStatus === "operator_review" ||
      journey.action === "operator_review"),
  );
  const assistedCloudflareMigration = Boolean(
    operatorReview &&
    journey?.lastError?.code === "cloudflare_o2o_migration_requires_assistance",
  );
  const persistedDisconnectedJourney =
    journey?.applicationStatus === "disconnected" ? journey : null;
  const cleanupRecords = disconnectedRecords.length
    ? disconnectedRecords
    : persistedDisconnectedJourney?.cleanupRecords.length
      ? persistedDisconnectedJourney.cleanupRecords
      : (persistedDisconnectedJourney?.expectedRecords ?? []);
  const showDisconnectedReceipt = Boolean(
    !loading &&
    statusLoadState === "ready" &&
    (persistedDisconnectedJourney ||
      (!journey && disconnectedRecords.length > 0)),
  );
  const disconnectedConflict = Boolean(
    cancelledConflict ||
    persistedDisconnectedJourney?.removalKind ===
      "ownership_review_cancelled" ||
    persistedDisconnectedJourney?.conflictCode === "hostname_reserved",
  );
  const disconnectedSetup = Boolean(
    cancelledSetup ||
    persistedDisconnectedJourney?.removalKind === "setup_cancelled",
  );

  const startAnotherDomainSetup = () => {
    setJourney(null);
    setDisconnectedRecords([]);
    setCancelledConflict(false);
    setCancelledSetup(false);
    setDomainInput("");
    setIntent("new");
    setPreflight(null);
    setError(null);
    setDisconnectOpen(false);
    setAnnouncement("Ready to set up another custom domain.");
  };

  return (
    <section
      aria-labelledby="custom-domain-heading"
      className="space-y-5 text-slate-900 dark:text-slate-100"
    >
      <div>
        <div className="flex items-center gap-2">
          <Globe2
            className="h-5 w-5 text-slate-600 dark:text-slate-300"
            aria-hidden="true"
          />
          <h3 id="custom-domain-heading" className="text-lg font-semibold">
            Custom domain
          </h3>
        </div>
        <p className="mt-2 max-w-3xl text-base leading-6 text-slate-600 dark:text-slate-300">
          Use a domain you control while keeping your permanent platform
          storefront as a fallback. Domain operations apply immediately and
          never change saved design settings.
        </p>
        <a
          href={platformUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-lg text-base font-semibold text-primary-700 underline-offset-4 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 dark:text-primary-300"
        >
          Platform storefront{" "}
          <ExternalLink className="h-4 w-4" aria-hidden="true" />
        </a>
      </div>

      <p
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {announcement}
      </p>

      {attemptId && journey && !persistedDisconnectedJourney ? (
        <p className="rounded-lg border border-sky-200 bg-sky-50 p-3 text-base text-sky-950 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-100">
          We resumed your domain setup. You can continue from where you left
          off.
        </p>
      ) : null}

      {loading ? (
        <div className="flex min-h-24 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-slate-50 p-4 text-base text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
          <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
          Checking custom-domain status…
        </div>
      ) : null}

      {!loading && statusLoadState === "error" && !attemptId ? (
        <button
          type="button"
          onClick={() => void loadStatus()}
          className={secondaryButtonClass}
        >
          Retry loading domain status
        </button>
      ) : null}

      {showDisconnectedReceipt ? (
        <div className="space-y-4 rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
          <div>
            <p className="text-base font-semibold">
              {disconnectedConflict
                ? "Ownership review cancelled"
                : disconnectedSetup
                  ? "Setup cancelled"
                  : "Connection removed from The Special Wedding"}
            </p>
            <p className="mt-1 text-base leading-6">
              Your platform URL and publication setting did not change.{" "}
              {cleanupRecords.length
                ? disconnectedSetup
                  ? "If you added these DNS records, you can remove them from your DNS provider."
                  : "Delete these DNS records at your DNS provider when you are ready to finish cleanup."
                : "There are no DNS records to clean up."}
            </p>
          </div>
          <div className="space-y-3">
            {cleanupRecords.map((record) => (
              <DnsRecordCard
                key={`${record.type}-${record.fqdn}-${record.value ?? ""}`}
                record={record}
                onCopy={copyValue}
              />
            ))}
          </div>
          {canActivate ? (
            <button
              type="button"
              onClick={startAnotherDomainSetup}
              className={secondaryButtonClass}
            >
              Set up another domain
            </button>
          ) : null}
        </div>
      ) : null}

      {!loading &&
      statusLoadState === "ready" &&
      !journey &&
      disconnectedRecords.length === 0 &&
      !canActivate ? (
        <div className="rounded-xl border border-violet-300 bg-violet-50 p-5 text-violet-950 dark:border-violet-800 dark:bg-violet-950/40 dark:text-violet-100">
          <p className="text-[16px] font-semibold">
            Upgrade to add a custom domain
          </p>
          <p className="mt-2 text-base leading-6">
            Design, publish, and preview your storefront on the platform URL
            now. Custom-domain activation is available on eligible plans.
          </p>
          <a
            href="/admin/planner/billing"
            className="mt-4 inline-flex min-h-11 items-center rounded-lg bg-primary-800 px-4 text-base font-semibold text-white transition hover:bg-primary-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
          >
            Compare plans
          </a>
        </div>
      ) : null}

      {!loading &&
      statusLoadState === "ready" &&
      !journey &&
      disconnectedRecords.length === 0 &&
      canActivate &&
      !attemptId ? (
        <div className="space-y-5 rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/50 sm:p-5">
          <div>
            <label
              htmlFor="storefront-custom-domain"
              className="text-base font-semibold"
            >
              Custom web address
            </label>
            <p
              id="storefront-domain-help"
              className="mt-1 text-base leading-6 text-slate-600 dark:text-slate-300"
            >
              Use an address such as weddings.yourbusiness.com. Your existing
              platform storefront stays available.
            </p>
            <input
              id="storefront-custom-domain"
              aria-describedby="storefront-domain-help"
              type="text"
              inputMode="url"
              autoCapitalize="none"
              autoCorrect="off"
              value={domainInput}
              onChange={(event) => {
                setDomainInput(event.target.value);
                setPreflight(null);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void handlePreflight();
                }
              }}
              placeholder="events.example.com"
              disabled={submitting}
              className={`mt-2 w-full ${controlClass}`}
            />
          </div>

          <fieldset className="space-y-3">
            <legend className="text-base font-semibold">
              Is this web address already in use?
            </legend>
            <label className="flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border border-slate-300 bg-white p-3 text-base dark:border-slate-600 dark:bg-slate-950">
              <input
                type="radio"
                name="storefront-domain-intent"
                value="new"
                checked={intent === "new"}
                onChange={() => {
                  setIntent("new");
                  setPreflight(null);
                }}
                className="mt-1 h-4 w-4"
              />
              <span>
                <span className="block font-semibold">No, it is new</span>
                <span className="text-slate-600 dark:text-slate-300">
                  Nothing important currently uses this address.
                </span>
              </span>
            </label>
            <label className="flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border border-slate-300 bg-white p-3 text-base dark:border-slate-600 dark:bg-slate-950">
              <input
                type="radio"
                name="storefront-domain-intent"
                value="migration"
                checked={intent === "migration"}
                onChange={() => {
                  setIntent("migration");
                  setPreflight(null);
                }}
                className="mt-1 h-4 w-4"
              />
              <span>
                <span className="block font-semibold">
                  Yes, it is already in use
                </span>
                <span className="text-slate-600 dark:text-slate-300">
                  Help me move it without unexpectedly interrupting visitors.
                </span>
              </span>
            </label>
          </fieldset>

          <button
            type="button"
            onClick={() => void handlePreflight()}
            disabled={submitting || !domainInput.trim()}
            className={primaryButtonClass}
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            )}
            Check domain
          </button>

          {preflight ? (
            <div className="space-y-4 border-t border-slate-200 pt-5 dark:border-slate-700">
              <ProviderSummary preflight={preflight} />
              {preflight.selfServiceAllowed &&
              preflight.domainConnectSupported === true ? (
                <div className="space-y-3 rounded-xl border border-violet-300 bg-violet-50 p-4 text-violet-950 dark:border-violet-800 dark:bg-violet-950/40 dark:text-violet-100">
                  <div>
                    <p className="text-[16px] font-semibold">
                      {preflight.domainConnectProvider ??
                        preflight.dnsProvider.name}{" "}
                      can connect this address for you
                    </p>
                    <p className="mt-1 text-base leading-6">
                      You will sign in securely at{" "}
                      {preflight.domainConnectProvider ??
                        preflight.dnsProvider.name}{" "}
                      and approve the connection there. We never see your
                      provider password.
                    </p>
                  </div>
                  <div className="flex flex-col gap-3 sm:flex-row">
                    <button
                      type="button"
                      onClick={() => void handleAutomaticSetup()}
                      disabled={submitting}
                      className={primaryButtonClass}
                    >
                      Continue with{" "}
                      {preflight.domainConnectProvider ??
                        preflight.dnsProvider.name}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleManualSetup()}
                      disabled={submitting}
                      className={secondaryButtonClass}
                    >
                      Set up manually instead
                    </button>
                  </div>
                </div>
              ) : preflight.selfServiceAllowed ? (
                <button
                  type="button"
                  onClick={() => void handleManualSetup()}
                  disabled={submitting}
                  className={secondaryButtonClass}
                >
                  Set up manually
                </button>
              ) : preflight.recommendedFlow === "assisted_migration" ? (
                <button
                  type="button"
                  onClick={() => void handleManualSetup()}
                  disabled={submitting}
                  className={secondaryButtonClass}
                >
                  Start assisted migration
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {journey && !persistedDisconnectedJourney ? (
        <div className="space-y-5">
          {!canActivate && !active ? (
            <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
              <p className="text-base font-semibold">
                Setup actions are unavailable on this plan
              </p>
              <p className="mt-1 text-base leading-6">
                You can review status, check current DNS, or disconnect this
                domain. Upgrade before continuing provisioning or verification.
              </p>
            </div>
          ) : null}
          {active ? (
            <div className="rounded-xl border border-emerald-300 bg-emerald-50 p-5 text-emerald-950 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-100">
              <p className="text-[16px] font-semibold">Custom domain is live</p>
              <a
                href={`https://${journey.hostname}`}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex min-h-11 items-center gap-2 text-base font-semibold text-emerald-900 underline underline-offset-4 dark:text-emerald-100"
              >
                https://{journey.hostname}{" "}
                <ExternalLink className="h-4 w-4" aria-hidden="true" />
              </a>
              {!isPublished ? (
                <p className="mt-3 text-base font-medium">
                  Your storefront is not published. Visitors will not see it
                  until you publish.
                </p>
              ) : null}
            </div>
          ) : automaticSupportChecking ? (
            <section
              aria-live="polite"
              className="flex items-start gap-3 rounded-xl border border-sky-200 bg-sky-50 p-5 text-sky-950 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-100"
            >
              <Loader2
                className="mt-0.5 h-5 w-5 shrink-0 animate-spin"
                aria-hidden="true"
              />
              <div>
                <h4 className="text-[16px] font-semibold">
                  Checking automatic setup
                </h4>
                <p className="mt-1 text-base leading-6">
                  We’re confirming that your DNS provider can safely connect
                  this exact web address.
                </p>
              </div>
            </section>
          ) : automaticSupportUnavailable ? (
            <section
              aria-labelledby="automatic-domain-unavailable-heading"
              className="space-y-4 rounded-xl border border-amber-300 bg-amber-50 p-5 text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100"
            >
              <div>
                <h4
                  id="automatic-domain-unavailable-heading"
                  className="text-[16px] font-semibold"
                >
                  Automatic setup is not available right now
                </h4>
                <p className="mt-1 text-base leading-6">
                  Your saved setup is still here. Use the guided manual steps
                  to connect this address without sharing your DNS password.
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handleSwitchToManualSetup()}
                disabled={submitting}
                className={secondaryButtonClass}
              >
                Use manual setup
              </button>
            </section>
          ) : automaticConsentPending ? (
            <section
              aria-labelledby="automatic-domain-consent-heading"
              className="space-y-4 rounded-xl border border-violet-300 bg-violet-50 p-5 text-violet-950 dark:border-violet-800 dark:bg-violet-950/40 dark:text-violet-100"
            >
              <div>
                <h4
                  id="automatic-domain-consent-heading"
                  className="text-[16px] font-semibold"
                >
                  {journey.domainConnectProvider ?? journey.dnsProvider.name}{" "}
                  will connect your address
                </h4>
                <p className="mt-1 text-base leading-6">
                  Sign in securely at{" "}
                  {journey.domainConnectProvider ?? journey.dnsProvider.name}{" "}
                  and approve these two changes. We never see your provider
                  password.
                </p>
              </div>
              <ul className="space-y-2 text-base">
                <li className="flex items-start gap-2">
                  <Check
                    className="mt-0.5 h-5 w-5 shrink-0"
                    aria-hidden="true"
                  />
                  <span>Verify that you control this web address.</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check
                    className="mt-0.5 h-5 w-5 shrink-0"
                    aria-hidden="true"
                  />
                  <span>Connect it to your planner storefront.</span>
                </li>
              </ul>
              <details className="rounded-lg border border-violet-300/80 bg-white/70 p-3 dark:border-violet-700 dark:bg-slate-950/50">
                <summary className="cursor-pointer text-base font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500">
                  View exact DNS changes
                </summary>
                <div className="mt-3 space-y-3">
                  {journey.expectedRecords.map((record) => (
                    <DnsRecordCard
                      key={`${record.type}-${record.fqdn}-${record.value ?? ""}`}
                      record={record}
                      onCopy={copyValue}
                    />
                  ))}
                </div>
              </details>
              <div className="flex flex-col gap-3 sm:flex-row">
                <button
                  type="button"
                  onClick={() => void handleAutomaticAuthorization()}
                  disabled={submitting}
                  className={primaryButtonClass}
                >
                  {submitting ? (
                    <Loader2
                      className="h-4 w-4 animate-spin"
                      aria-hidden="true"
                    />
                  ) : (
                    <ExternalLink className="h-4 w-4" aria-hidden="true" />
                  )}
                  Sign in to{" "}
                  {journey.domainConnectProvider ?? journey.dnsProvider.name}
                </button>
                <button
                  type="button"
                  onClick={() => void handleSwitchToManualSetup()}
                  disabled={submitting}
                  className={secondaryButtonClass}
                >
                  Use manual setup
                </button>
              </div>
            </section>
          ) : operatorReview ? null : automaticJourney ? (
            <FriendlyConnectionProgress journey={journey} />
          ) : (
            <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-sky-950 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-100">
              <p className="text-[16px] font-semibold">Add these records</p>
              <p className="mt-1 text-base leading-6">
                Open {journey.dnsProvider.name}, add every record exactly as
                shown, then return here.
              </p>
            </div>
          )}

          {!isPublished && !active ? (
            <p className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-base text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
              Your storefront is not published. Domain setup can continue
              without changing publication.
            </p>
          ) : null}

          <JourneyNotice journey={journey} />

          {journey.lastError && isExpectedDnsWaitingError(journey) && !error ? (
            <div
              role="status"
              className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100"
            >
              <p className="text-base font-semibold">
                {journey.lastError.message}
              </p>
              {journey.lastError.customerAction ? (
                <p className="mt-1 text-base leading-6">
                  {journey.lastError.customerAction}
                </p>
              ) : null}
            </div>
          ) : null}

          {journey.lastError &&
          !assistedCloudflareMigration &&
          !error &&
          !isExpectedDnsWaitingError(journey) ? (
            <CustomerErrorNotice
              error={normalizeStorefrontError(
                new StorefrontCustomerError(journey.lastError),
                "Domain verification needs attention.",
              )}
            />
          ) : null}

          {!active && !automaticJourney && journey.expectedRecords.length ? (
            <section
              aria-labelledby="dns-records-heading"
              className="space-y-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h4
                    id="dns-records-heading"
                    className="text-[16px] font-semibold"
                  >
                    DNS records
                  </h4>
                  <p className="mt-1 text-base text-slate-600 dark:text-slate-300">
                    Expected values are compared with what public DNS currently
                    returns.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {journey.dnsProvider.controlPanelUrl ? (
                    <a
                      href={journey.dnsProvider.controlPanelUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={secondaryButtonClass}
                    >
                      Open {journey.dnsProvider.name}{" "}
                      <ExternalLink className="h-4 w-4" aria-hidden="true" />
                    </a>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => void copyAllRecords()}
                    className={secondaryButtonClass}
                  >
                    <ClipboardCopy className="h-4 w-4" aria-hidden="true" />{" "}
                    Copy all records
                  </button>
                </div>
              </div>
              <div className="space-y-3">
                {journey.expectedRecords.map((record) => (
                  <DnsRecordCard
                    key={`${record.type}-${record.fqdn}-${record.value ?? ""}`}
                    record={record}
                    onCopy={copyValue}
                  />
                ))}
              </div>
            </section>
          ) : null}

          {canActivate &&
          !active &&
          !automaticJourney &&
          !operatorReview &&
          !journey.conflictCode &&
          journey.expectedRecords.length > 0 &&
          journey.attemptId ? (
            <form
              aria-labelledby="send-domain-instructions-heading"
              className="space-y-4 rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900/60"
              onSubmit={(event) => {
                event.preventDefault();
                void handleSendInstructions();
              }}
              noValidate
            >
              <div>
                <h4
                  id="send-domain-instructions-heading"
                  className="text-[16px] font-semibold"
                >
                  Send instructions to your DNS contact
                </h4>
                <p className="mt-1 text-base leading-6 text-slate-600 dark:text-slate-300">
                  Email the exact records to the person or agency that manages
                  this domain.
                </p>
              </div>
              <div>
                <label
                  htmlFor="storefront-domain-instruction-email"
                  className="text-base font-semibold"
                >
                  Email DNS instructions
                </label>
                <input
                  id="storefront-domain-instruction-email"
                  type="email"
                  autoComplete="email"
                  value={instructionEmail}
                  onChange={(event) => {
                    setInstructionEmail(event.target.value);
                    setInstructionError(null);
                  }}
                  placeholder="dns-contact@example.com"
                  aria-invalid={Boolean(instructionError)}
                  aria-describedby={
                    instructionError
                      ? "domain-instruction-email-error"
                      : undefined
                  }
                  className={`mt-2 w-full ${controlClass}`}
                />
              </div>
              <div>
                <label
                  htmlFor="storefront-domain-instruction-note"
                  className="text-base font-semibold"
                >
                  Optional note
                </label>
                <textarea
                  id="storefront-domain-instruction-note"
                  rows={3}
                  maxLength={500}
                  value={instructionNote}
                  onChange={(event) => setInstructionNote(event.target.value)}
                  placeholder="Add context for your DNS contact."
                  className={`mt-2 w-full py-3 ${controlClass}`}
                />
              </div>
              {instructionError ? (
                <p
                  id="domain-instruction-email-error"
                  role="alert"
                  className="text-base font-medium text-red-700 dark:text-red-300"
                >
                  {instructionError}
                </p>
              ) : null}
              <button
                type="submit"
                disabled={submitting}
                className={secondaryButtonClass}
              >
                Send instructions
              </button>
            </form>
          ) : null}

          {journey.attemptId &&
          (instructionLinksLoadState !== "ready" ||
            instructionReceipts.length > 0) ? (
            <section
              aria-labelledby="active-domain-instruction-links-heading"
              className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-950"
            >
              <div>
                <h4
                  id="active-domain-instruction-links-heading"
                  className="text-[16px] font-semibold"
                >
                  Active DNS instruction links
                </h4>
                <p className="mt-1 text-base leading-6 text-slate-600 dark:text-slate-300">
                  These read-only links remain revocable after a reload. The
                  Special Wedding does not store the full recipient address for
                  these links. We keep the masked hint shown here and a one-way
                  digest for delivery limits; Resend receives the address to
                  deliver the email.
                </p>
              </div>
              {instructionLinksLoadState === "loading" ? (
                <p
                  role="status"
                  className="text-base text-slate-600 dark:text-slate-300"
                >
                  Loading active instruction links…
                </p>
              ) : null}
              {instructionLinksLoadState === "error" ? (
                <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
                  <p className="text-base font-semibold">
                    Active instruction links could not be loaded.
                  </p>
                  <button
                    type="button"
                    onClick={() =>
                      void loadInstructionLinks(journey.attemptId as string)
                    }
                    className={`${secondaryButtonClass} mt-3`}
                  >
                    <RefreshCw className="h-4 w-4" aria-hidden="true" />
                    Retry loading links
                  </button>
                </div>
              ) : null}
              {instructionReceipts.map((instructionReceipt) => {
                const deliveryFailed =
                  instructionReceipt.state === "delivery_failed";
                const deliveryPending =
                  instructionReceipt.state === "delivery_pending";
                return (
                  <div
                    key={instructionReceipt.linkId}
                    className={`rounded-xl border p-4 ${
                      instructionReceipt.revoked
                        ? "border-slate-300 bg-slate-100 text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                        : deliveryFailed || deliveryPending
                          ? "border-amber-300 bg-amber-50 text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100"
                          : "border-emerald-300 bg-emerald-50 text-emerald-950 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-100"
                    }`}
                    aria-live="polite"
                  >
                    <p className="text-base font-semibold">
                      {instructionReceipt.revoked
                        ? "Instruction link revoked"
                        : deliveryFailed
                          ? "Email delivery not confirmed"
                          : deliveryPending
                            ? "Email delivery in progress"
                            : "Secure instructions sent"}
                    </p>
                    <p className="mt-1 text-base leading-6">
                      {instructionReceipt.revoked
                        ? `The link for ${instructionReceipt.recipientHint} can no longer be opened.`
                        : deliveryFailed
                          ? `The read-only link for ${instructionReceipt.recipientHint} is active, but email delivery was not confirmed. Retry with the same address to reuse this link, or revoke it below.`
                          : deliveryPending
                            ? `The read-only link for ${instructionReceipt.recipientHint} is active while delivery finishes. Reload before trying again.`
                            : `A read-only link for ${instructionReceipt.recipientHint} was created ${formatCheckedAt(instructionReceipt.createdAt)} and expires ${formatCheckedAt(instructionReceipt.expiresAt)}. It cannot publish, activate, transfer, disconnect, or change DNS.`}
                    </p>
                    {!instructionReceipt.revoked ? (
                      <button
                        type="button"
                        onClick={() =>
                          void handleRevokeInstructions(instructionReceipt)
                        }
                        disabled={submitting}
                        className={`${secondaryButtonClass} mt-3`}
                        aria-label={`Revoke instruction link for ${instructionReceipt.recipientHint}`}
                      >
                        <RotateCcw className="h-4 w-4" aria-hidden="true" />
                        Revoke instruction link
                      </button>
                    ) : null}
                  </div>
                );
              })}
            </section>
          ) : null}

          {automaticJourney && !automaticConsentPending ? (
            <details className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-950">
              <summary className="cursor-pointer text-base font-semibold text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 dark:text-slate-100">
                View technical details
              </summary>
              <div className="mt-4 space-y-4">
                <VerificationProgress journey={journey} />
                {journey.expectedRecords.length ? (
                  <div className="space-y-3">
                    {journey.expectedRecords.map((record) => (
                      <DnsRecordCard
                        key={`${record.type}-${record.fqdn}-${record.value ?? ""}`}
                        record={record}
                        onCopy={copyValue}
                      />
                    ))}
                  </div>
                ) : null}
              </div>
            </details>
          ) : !automaticJourney ? (
            <VerificationProgress journey={journey} />
          ) : null}

          <div className="flex flex-wrap gap-3">
            {canActivate && !active && !operatorReview && !automaticJourney ? (
              <button
                type="button"
                onClick={() => void handleVerify()}
                disabled={submitting}
                className={primaryButtonClass}
              >
                {submitting ? (
                  <Loader2
                    className="h-4 w-4 animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <Check className="h-4 w-4" aria-hidden="true" />
                )}
                {journey.conflictCode === "hostname_reserved"
                  ? "I've added the ownership record"
                  : "I've added these records"}
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => void handleObserve()}
              disabled={submitting}
              className={secondaryButtonClass}
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" /> Check again
            </button>
            {canRetryProviderVerification ? (
              <button
                type="button"
                onClick={() => void handleRetry()}
                disabled={submitting}
                className={secondaryButtonClass}
              >
                Retry verification
              </button>
            ) : null}
            {!disconnectOpen ? (
              <button
                ref={disconnectTriggerRef}
                type="button"
                onClick={() => setDisconnectOpen(true)}
                disabled={submitting}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-red-300 bg-white px-4 text-base font-semibold text-red-700 hover:bg-red-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 disabled:cursor-not-allowed disabled:border-slate-300 disabled:bg-slate-200 disabled:text-slate-700 disabled:hover:bg-slate-200 dark:border-red-800 dark:bg-slate-950 dark:text-red-300 dark:hover:bg-red-950/40 dark:disabled:border-slate-600 dark:disabled:bg-slate-800 dark:disabled:text-slate-200 dark:disabled:hover:bg-slate-800"
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
                {journey.conflictCode === "hostname_reserved"
                  ? "Cancel ownership review"
                  : active
                    ? "Disconnect domain"
                    : "Cancel setup"}
              </button>
            ) : null}
          </div>

          {disconnectOpen ? (
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="disconnect-domain-title"
              data-storefront-nested-dialog="true"
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  event.stopPropagation();
                  closeDisconnectConfirmation();
                }
                if (event.key === "Tab") {
                  if (
                    event.shiftKey &&
                    document.activeElement === keepDomainRef.current
                  ) {
                    event.preventDefault();
                    confirmDisconnectRef.current?.focus();
                  } else if (
                    !event.shiftKey &&
                    document.activeElement === confirmDisconnectRef.current
                  ) {
                    event.preventDefault();
                    keepDomainRef.current?.focus();
                  }
                }
              }}
              className="fixed inset-0 z-[10000] flex items-center justify-center bg-slate-950/75 p-4"
            >
              <div className="w-full max-w-lg rounded-xl border border-red-300 bg-white p-5 text-slate-900 shadow-2xl dark:border-red-800 dark:bg-slate-950 dark:text-slate-100">
                <h4
                  id="disconnect-domain-title"
                  className="text-[16px] font-semibold text-slate-950 dark:text-slate-100"
                >
                  {journey.conflictCode === "hostname_reserved"
                    ? `Cancel ownership review for ${journey.hostname}?`
                    : active
                      ? `Disconnect ${journey.hostname}?`
                      : `Cancel setup for ${journey.hostname}?`}
                </h4>
                <p className="mt-2 text-base leading-6 text-slate-700 dark:text-slate-300">
                  {journey.conflictCode === "hostname_reserved"
                    ? "This cancels only your ownership review. It does not reassign or change the currently reserved hostname. Your platform URL and storefront publication setting will not change."
                    : active
                      ? "The custom hostname will stop routing through The Special Wedding. Your platform URL will not change, and your storefront publication setting will not change."
                      : "This cancels the current connection setup and removes any provider mapping already created. Your platform URL and storefront publication setting will not change. DNS records already added may still need to be removed manually."}
                </p>
                <div className="mt-4 flex flex-wrap justify-end gap-3">
                  <button
                    ref={keepDomainRef}
                    type="button"
                    onClick={closeDisconnectConfirmation}
                    disabled={submitting}
                    className={secondaryButtonClass}
                  >
                    {active ? "Keep domain" : "Continue setup"}
                  </button>
                  <button
                    ref={confirmDisconnectRef}
                    type="button"
                    onClick={() => void handleDisconnect()}
                    disabled={submitting}
                    className="inline-flex min-h-11 items-center justify-center rounded-lg bg-red-700 px-4 text-base font-semibold text-white hover:bg-red-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-700 disabled:hover:bg-slate-200 dark:disabled:bg-slate-800 dark:disabled:text-slate-200 dark:disabled:hover:bg-slate-800"
                  >
                    {journey.conflictCode === "hostname_reserved"
                      ? "Cancel ownership review"
                      : active
                        ? "Disconnect domain"
                        : "Cancel setup"}
                  </button>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {error ? (
        <div
          ref={errorNoticeRef}
          tabIndex={-1}
          className="focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
        >
          <CustomerErrorNotice error={error} />
        </div>
      ) : null}
      {error && attemptId && (canActivate || canManageExisting) ? (
        <button
          type="button"
          onClick={() => void completeResumedAuthorization(true)}
          disabled={loading || submitting}
          className={secondaryButtonClass}
        >
          Retry automatic setup
        </button>
      ) : null}
    </section>
  );
}

/** Convenience wrapper for the admin surface; tests and the modal use the injected panel. */
export function CustomDomainManager({
  canActivate = true,
  canManageExisting = false,
  platformUrl = "/storefront/your-storefront-slug",
  isPublished = false,
  attemptId = null,
}: Omit<CustomDomainPanelProps, "transport"> & { transport?: never }) {
  const { apiRequest } = useAdmin();
  return (
    <CustomDomainPanel
      transport={apiRequest}
      canActivate={canActivate}
      canManageExisting={canManageExisting}
      platformUrl={platformUrl}
      isPublished={isPublished}
      attemptId={attemptId}
    />
  );
}
