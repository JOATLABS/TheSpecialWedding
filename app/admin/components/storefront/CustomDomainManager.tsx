'use client';

import {
  AlertCircle,
  Check,
  Copy,
  Globe2,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { useAdmin } from '@/contexts/AdminContext';
import {
  connectCustomDomain,
  refreshCustomDomain,
  removeCustomDomain,
  type StorefrontDomain,
  type StorefrontOwnershipVerificationHttp,
} from '@/services/storefrontApi';

function DomainValue({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
      <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{label}</p>
      <div className="mt-1 flex items-center gap-2">
        <code className="min-w-0 flex-1 break-all text-xs text-slate-800 dark:text-slate-200">
          {value}
        </code>
        <button
          type="button"
          onClick={() => void copy()}
          className="rounded-md p-1.5 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-slate-800 dark:hover:text-white"
          aria-label={`Copy ${label}`}
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" />
          ) : (
            <Copy className="h-3.5 w-3.5" aria-hidden="true" />
          )}
        </button>
      </div>
    </div>
  );
}

function statusTone(status: string) {
  if (status === 'active') {
    return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300';
  }
  if (status === 'failed' || status === 'error' || status === 'deletion_failed') {
    return 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300';
  }
  return 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300';
}

export function StorefrontHttpVerification({
  verification,
}: {
  verification: StorefrontOwnershipVerificationHttp | null;
}) {
  if (!verification) {
    return null;
  }
  return (
    <>
      {verification.http_url ? (
        <DomainValue label="HTTP verification URL" value={verification.http_url} />
      ) : null}
      {verification.http_body ? (
        <DomainValue label="HTTP verification body" value={verification.http_body} />
      ) : null}
    </>
  );
}

export function CustomDomainManager() {
  const { apiRequest } = useAdmin();
  const [domainInput, setDomainInput] = useState('');
  const [domain, setDomain] = useState<StorefrontDomain | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadDomain = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDomain(await refreshCustomDomain(apiRequest));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load the custom domain');
    } finally {
      setLoading(false);
    }
  }, [apiRequest]);

  useEffect(() => {
    void loadDomain();
  }, [loadDomain]);

  const handleConnect = async () => {
    const hostname = domainInput.trim();
    if (!hostname) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const connected = await connectCustomDomain(hostname, apiRequest);
      setDomain(connected);
      setDomainInput('');
      setMessage('Domain connection started. Add the provider records below, then verify.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to connect the domain');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRefresh = async () => {
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      const refreshed = await refreshCustomDomain(apiRequest);
      setDomain(refreshed);
      setMessage(
        refreshed?.status === 'active'
          ? 'The custom domain is active and secured.'
          : 'Verification refreshed. DNS and SSL activation can take time.',
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to verify the domain');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemove = async () => {
    if (!window.confirm('Remove this custom domain? Your platform storefront URL will keep working.')) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setMessage(null);
    try {
      await removeCustomDomain(apiRequest);
      setDomain(null);
      setMessage('Custom domain removed. Your platform storefront URL is unchanged.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to remove the domain');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section aria-labelledby="custom-domain-heading" className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Globe2 className="h-5 w-5 text-slate-500" aria-hidden="true" />
            <h3
              id="custom-domain-heading"
              className="text-sm font-semibold text-slate-900 dark:text-white"
            >
              Custom domain
            </h3>
          </div>
          <p className="mt-1 text-[11px] leading-5 text-slate-500 dark:text-slate-400">
            Domain changes apply immediately and are separate from saved design settings.
            Your platform URL remains available throughout setup.
          </p>
        </div>
        {domain ? (
          <span
            className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase ${statusTone(
              domain.status,
            )}`}
          >
            {domain.status}
          </span>
        ) : null}
      </div>

      {loading ? (
        <div className="flex items-center gap-2 rounded-xl bg-slate-50 p-4 text-xs text-slate-500 dark:bg-slate-900/50">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Checking custom-domain status…
        </div>
      ) : domain ? (
        <div className="space-y-4 rounded-xl border border-slate-200 bg-slate-50/70 p-4 dark:border-slate-700 dark:bg-slate-900/40">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs text-slate-500">Connected hostname</p>
              <p className="font-semibold text-slate-900 dark:text-white">{domain.hostname}</p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => void handleRefresh()}
                disabled={submitting}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
              >
                {submitting ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                ) : (
                  <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                )}
                Verify now
              </button>
              <button
                type="button"
                onClick={() => void handleRemove()}
                disabled={submitting}
                className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-2 text-xs font-semibold text-red-700 transition hover:bg-red-50 disabled:opacity-50 dark:border-red-900 dark:bg-slate-800 dark:text-red-300"
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                Remove
              </button>
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <div className="rounded-lg bg-white p-3 dark:bg-slate-900">
              <p className="text-[10px] font-bold uppercase text-slate-500">Provider</p>
              <p className="mt-1 text-xs font-semibold">{domain.provider_status}</p>
            </div>
            <div className="rounded-lg bg-white p-3 dark:bg-slate-900">
              <p className="text-[10px] font-bold uppercase text-slate-500">SSL</p>
              <p className="mt-1 text-xs font-semibold">{domain.ssl_status}</p>
            </div>
          </div>

          {domain.status !== 'active' ? (
            <div className="space-y-3 rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
              <div className="flex items-center gap-2 text-xs font-semibold text-amber-900 dark:text-amber-200">
                <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                Add the exact DNS values supplied by the provider
              </div>
              {domain.cname_target ? (
                <DomainValue label="CNAME target" value={domain.cname_target} />
              ) : null}
              {domain.ownership_verification?.name ? (
                <DomainValue
                  label={`${domain.ownership_verification.type || 'TXT'} name`}
                  value={domain.ownership_verification.name}
                />
              ) : null}
              {domain.ownership_verification?.value ? (
                <DomainValue
                  label={`${domain.ownership_verification.type || 'TXT'} value`}
                  value={domain.ownership_verification.value}
                />
              ) : null}
              <StorefrontHttpVerification verification={domain.ownership_verification_http} />
              {domain.ssl_validation_records.flatMap((record, index) => {
                const values: Array<{ label: string; value: string }> = [];
                if (record.txt_name) {
                  values.push({ label: `SSL TXT ${index + 1} name`, value: record.txt_name });
                }
                if (record.txt_value) {
                  values.push({ label: `SSL TXT ${index + 1} value`, value: record.txt_value });
                }
                if (record.cname_name) {
                  values.push({ label: `SSL CNAME ${index + 1} name`, value: record.cname_name });
                }
                if (record.cname_target) {
                  values.push({ label: `SSL CNAME ${index + 1} target`, value: record.cname_target });
                }
                return values.map((value) => (
                  <DomainValue key={value.label} label={value.label} value={value.value} />
                ));
              })}
            </div>
          ) : (
            <p className="flex items-center gap-2 text-xs font-medium text-emerald-700 dark:text-emerald-300">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              Domain and SSL are active.
            </p>
          )}

          {domain.last_error ? (
            <p className="flex items-start gap-2 text-xs text-red-700 dark:text-red-300">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              {domain.last_error}
            </p>
          ) : null}
        </div>
      ) : (
        <div className="space-y-3">
          <label htmlFor="storefront-custom-domain" className="text-xs font-medium text-slate-700 dark:text-slate-300">
            Domain name
          </label>
          <div className="flex overflow-hidden rounded-lg border border-slate-300 bg-white focus-within:ring-2 focus-within:ring-primary-500 dark:border-slate-700 dark:bg-slate-900">
            <input
              id="storefront-custom-domain"
              type="text"
              inputMode="url"
              autoCapitalize="none"
              autoCorrect="off"
              value={domainInput}
              onChange={(event) => setDomainInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  void handleConnect();
                }
              }}
              placeholder="weddings.example.com"
              disabled={submitting}
              className="min-w-0 flex-1 bg-transparent px-3 py-2.5 text-sm outline-none"
            />
            <button
              type="button"
              onClick={() => void handleConnect()}
              disabled={submitting || !domainInput.trim()}
              className="inline-flex items-center gap-2 border-l border-slate-200 bg-slate-100 px-4 text-xs font-semibold text-slate-800 transition hover:bg-slate-200 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
            >
              {submitting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              ) : null}
              Connect
            </button>
          </div>
        </div>
      )}

      {error ? (
        <p role="alert" className="flex items-start gap-2 text-xs text-red-600 dark:text-red-300">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {error}
        </p>
      ) : null}
      {message ? (
        <p role="status" className="text-xs text-emerald-700 dark:text-emerald-300">
          {message}
        </p>
      ) : null}
    </section>
  );
}
