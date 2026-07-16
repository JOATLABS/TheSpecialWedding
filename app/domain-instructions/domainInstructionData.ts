import { getServerApiBaseUrl } from '@/utils/env';

const PUBLIC_INSTRUCTION_TOKEN = /^[A-Za-z0-9_-]{43,128}$/;
const DNS_RECORD_TYPES = new Set(['NS', 'A', 'AAAA', 'CNAME', 'CAA', 'TXT']);
const PROXY_MODES = new Set(['dns_only', 'proxied', 'provider_default']);

type JsonObject = Record<string, unknown>;

export type DomainInstructionProvider = {
  name: string | null;
  zone: string | null;
  controlPanelUrl: string | null;
};

export type DomainInstructionRecord = {
  type: 'NS' | 'A' | 'AAAA' | 'CNAME' | 'CAA' | 'TXT';
  fqdn: string;
  relativeHost: string | null;
  values: string[];
  ttl: number | null;
  purpose: string | null;
  proxy: 'dns_only' | 'proxied' | 'provider_default' | null;
};

export type DomainInstruction = {
  hostname: string;
  provider: DomainInstructionProvider;
  records: DomainInstructionRecord[];
  note: string | null;
  expiresAt: string;
};

export type DomainInstructionLoadResult =
  | { status: 'ready'; instruction: DomainInstruction }
  | { status: 'expired_or_revoked' }
  | { status: 'temporarily_unavailable' };

export type DomainInstructionLoadOptions = {
  apiBaseUrl?: string;
  fetchImpl?: typeof fetch;
  now?: () => Date;
  timeoutMs?: number;
};

function asObject(value: unknown): JsonObject | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as JsonObject)
    : null;
}

function boundedText(value: unknown, maxLength: number): string | null {
  if (typeof value !== 'string') return null;
  const normalized = value.trim();
  if (!normalized || normalized.length > maxLength) return null;
  return normalized;
}

function boundedExactText(value: unknown, maxLength: number): string | null {
  if (typeof value !== 'string' || !value.trim() || value.length > maxLength) return null;
  return value;
}

function safeControlPanelUrl(value: unknown): string | null {
  const raw = boundedText(value, 2048);
  if (!raw) return null;

  try {
    const parsed = new URL(raw);
    const isIpLiteral =
      /^\d{1,3}(?:\.\d{1,3}){3}$/.test(parsed.hostname) ||
      parsed.hostname.includes(':');
    if (
      parsed.protocol !== 'https:' ||
      parsed.username ||
      parsed.password ||
      isIpLiteral ||
      parsed.hostname === 'localhost' ||
      parsed.hostname.endsWith('.local')
    ) {
      return null;
    }
    return parsed.toString();
  } catch {
    return null;
  }
}

function normalizeApiBaseUrl(value: string): string | null {
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return null;
    return parsed.toString().replace(/\/+$/, '');
  } catch {
    return null;
  }
}

function mapProvider(payload: JsonObject): DomainInstructionProvider {
  const provider = asObject(payload.provider);
  if (!provider) {
    return { name: null, zone: null, controlPanelUrl: null };
  }

  return {
    name: boundedText(provider.name, 120),
    zone: boundedText(provider.zone, 253),
    controlPanelUrl: safeControlPanelUrl(provider.control_panel_url),
  };
}

function mapRecord(value: unknown): DomainInstructionRecord | null {
  const record = asObject(value);
  if (!record) return null;

  const type = boundedText(record.type, 10)?.toUpperCase();
  const fqdn = boundedText(record.name, 253);
  if (!type || !DNS_RECORD_TYPES.has(type) || !fqdn) return null;

  const singularValue = boundedExactText(record.value, 4096);
  const pluralValues = Array.isArray(record.values)
    ? record.values
        .map((item) => boundedExactText(item, 4096))
        .filter((item): item is string => Boolean(item))
        .slice(0, 20)
    : [];
  const values = singularValue ? [singularValue] : pluralValues;
  if (values.length === 0) return null;
  const ttl = Number.isInteger(record.ttl) && Number(record.ttl) > 0
    ? Math.min(Number(record.ttl), 2_147_483_647)
    : null;
  const proxy = boundedText(record.proxy, 32);

  return {
    type: type as DomainInstructionRecord['type'],
    fqdn,
    relativeHost: boundedText(record.relative_host, 253),
    values,
    ttl,
    purpose: boundedText(record.purpose, 120),
    proxy: proxy && PROXY_MODES.has(proxy)
      ? (proxy as DomainInstructionRecord['proxy'])
      : null,
  };
}

function mapInstruction(payload: unknown, now: Date): DomainInstructionLoadResult {
  const body = asObject(payload);
  if (!body) return { status: 'temporarily_unavailable' };

  const hostname = boundedText(body.hostname, 253);
  const expiresAt = boundedText(body.expires_at, 64);
  const expiry = expiresAt ? new Date(expiresAt) : null;
  if (!hostname || !expiry || Number.isNaN(expiry.getTime())) {
    return { status: 'temporarily_unavailable' };
  }
  if (expiry.getTime() <= now.getTime()) {
    return { status: 'expired_or_revoked' };
  }

  if (!Array.isArray(body.records) || body.records.length === 0) {
    return { status: 'temporarily_unavailable' };
  }
  const mappedRecords = body.records.map(mapRecord);
  if (mappedRecords.some((record) => record === null)) {
    // Never show a partial DNS snapshot: omitting one malformed required record
    // can leave the customer with an unsafe, impossible-to-verify setup.
    return { status: 'temporarily_unavailable' };
  }
  const records = mappedRecords as DomainInstructionRecord[];

  return {
    status: 'ready',
    instruction: {
      hostname,
      provider: mapProvider(body),
      records,
      note: boundedText(body.note, 1000),
      expiresAt: expiry.toISOString(),
    },
  };
}

/**
 * Load the revocable read-only DNS snapshot without exposing provider errors to
 * the browser. This is intentionally a server-side read; the secret token is
 * never placed in client-side API requests or persisted browser storage.
 */
export async function loadDomainInstructions(
  token: string,
  options: DomainInstructionLoadOptions = {},
): Promise<DomainInstructionLoadResult> {
  if (!PUBLIC_INSTRUCTION_TOKEN.test(token)) {
    return { status: 'expired_or_revoked' };
  }

  let apiBaseUrl: string | null;
  try {
    apiBaseUrl = normalizeApiBaseUrl(options.apiBaseUrl ?? getServerApiBaseUrl());
  } catch {
    return { status: 'temporarily_unavailable' };
  }
  if (!apiBaseUrl) return { status: 'temporarily_unavailable' };

  try {
    const response = await (options.fetchImpl ?? fetch)(
      `${apiBaseUrl}/api/storefront/domain-instructions/${encodeURIComponent(token)}`,
      {
        method: 'GET',
        cache: 'no-store',
        headers: { Accept: 'application/json' },
        signal: AbortSignal.timeout(options.timeoutMs ?? 8_000),
      },
    );

    if (response.status === 404 || response.status === 410) {
      return { status: 'expired_or_revoked' };
    }
    if (!response.ok) return { status: 'temporarily_unavailable' };

    return mapInstruction(await response.json(), (options.now ?? (() => new Date()))());
  } catch {
    return { status: 'temporarily_unavailable' };
  }
}
