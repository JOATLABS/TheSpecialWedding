export const MAX_STOREFRONT_IMAGE_BYTES = 5 * 1024 * 1024;

export const STOREFRONT_IMAGE_TYPES = [
  'image/jpeg',
  'image/png',
  'image/webp',
] as const;

export type StorefrontImageType = (typeof STOREFRONT_IMAGE_TYPES)[number];
export type StorefrontImageSlot = 'hero' | 'about';

export type StorefrontApiTransport = <T = unknown>(
  path: string,
  method?: string,
  body?: unknown,
) => Promise<T | undefined>;

export interface StorefrontAccess {
  plan_id: string | null;
  storefront_enabled: boolean;
  custom_domain_enabled: boolean;
  can_manage_existing_domain: boolean;
}

export interface StorefrontSettings {
  slug: string;
  title: string | null;
  description: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  hero_asset_id: string | null;
  about_asset_id: string | null;
  theme_color: string;
  packages_enabled: boolean;
  reviews_enabled: boolean;
  is_published: boolean;
  published_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  revision: number;
  slug_editable: boolean;
  slug_persisted: boolean;
}

export interface StorefrontSettingsUpdate {
  slug?: string;
  title?: string | null;
  description?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  hero_asset_id?: string | null;
  about_asset_id?: string | null;
  theme_color?: string;
  packages_enabled?: boolean;
  reviews_enabled?: boolean;
  is_published?: boolean;
}

export type StorefrontSettingsField = keyof StorefrontSettingsUpdate;

export function buildStorefrontSettingsPatch(
  candidate: StorefrontSettingsUpdate,
  dirtyFields: ReadonlySet<StorefrontSettingsField>,
): StorefrontSettingsUpdate {
  return Object.fromEntries(
    [...dirtyFields]
      .filter((field) => Object.prototype.hasOwnProperty.call(candidate, field))
      .map((field) => [field, candidate[field]]),
  ) as StorefrontSettingsUpdate;
}

export type StorefrontPublicSettings = PublicStorefrontSettings;
export type StorefrontPlanner = PublicStorefrontPlanner;
export type StorefrontPackageService = PublicStorefrontPackageService;
export type StorefrontPackage = PublicStorefrontPackage;
export type StorefrontReview = PublicStorefrontReview;
export type StorefrontPreviewData = PublicStorefrontData;

export interface StorefrontOwnershipVerification {
  type: string | null;
  name: string | null;
  value: string | null;
}

export interface StorefrontOwnershipVerificationHttp {
  http_url: string | null;
  http_body: string | null;
}

export interface StorefrontSslValidationRecord {
  status: string | null;
  txt_name: string | null;
  txt_value: string | null;
  cname_name: string | null;
  cname_target: string | null;
}

export interface StorefrontDomain {
  hostname: string;
  status: string;
  provider_status: string;
  ssl_status: string;
  ownership_verification: StorefrontOwnershipVerification | null;
  ownership_verification_http: StorefrontOwnershipVerificationHttp | null;
  ssl_validation_records: StorefrontSslValidationRecord[];
  cname_target: string | null;
  deletion_status: string | null;
  last_error: string | null;
}

export type StorefrontDomainIntent = 'new' | 'migration';

export interface StorefrontDomainProviderIdentity {
  id: string | null;
  name: string;
  nameservers: string[];
  zone: string | null;
  controlPanelUrl: string | null;
}

export interface StorefrontDomainDnsRecord {
  type: string;
  relativeHost: string;
  fqdn: string;
  value: string | null;
  ttl: number | null;
  purpose: string;
  proxy: string | null;
  observedValues: string[];
  matches: boolean | null;
}

export interface StorefrontDomainConflict {
  code: string;
  recordType: string | null;
  values: string[];
  message: string | null;
}

export interface StorefrontDomainPreflight {
  hostname: string;
  hostType: string;
  intent: StorefrontDomainIntent;
  recommendedFlow: string;
  dnsProvider: StorefrontDomainProviderIdentity;
  registrar: string | null;
  platformProvider: string | null;
  domainConnectSupported: boolean;
  domainConnectProvider: string | null;
  expectedRecords: StorefrontDomainDnsRecord[];
  observedRecords: StorefrontDomainDnsRecord[];
  conflicts: StorefrontDomainConflict[];
  selfServiceAllowed: boolean;
  customerAction: string | null;
}

export interface StorefrontDomainErrorDetail {
  code: string;
  message: string;
  customerAction: string | null;
  retryable: boolean;
  supportId: string | null;
  field: string | null;
  provider: string | null;
}

export interface StorefrontDomainJourney {
  attemptId: string | null;
  revision: number | null;
  hostname: string;
  intent: StorefrontDomainIntent;
  applicationStatus: string;
  action: string;
  ownershipStatus: string;
  routingDnsStatus: string;
  providerHostnameStatus: string;
  sslStatus: string;
  httpsStatus: string;
  dnsProvider: StorefrontDomainProviderIdentity;
  registrar: string | null;
  platformProvider: string | null;
  domainConnectSupported: boolean;
  domainConnectProvider: string | null;
  expectedRecords: StorefrontDomainDnsRecord[];
  observedRecords: StorefrontDomainDnsRecord[];
  conflicts: StorefrontDomainConflict[];
  conflictCode: string | null;
  cleanupRecords: StorefrontDomainDnsRecord[];
  lastCheckedAt: string | null;
  nextCheckAt: string | null;
  claimExpiresAt: string | null;
  lastError: StorefrontDomainErrorDetail | null;
}

export interface StorefrontDomainConnectAuthorization {
  attemptId: string;
  authorizationUrl: string;
}

export interface StorefrontDomainInstructionRequest {
  attemptId: string;
  email: string;
  note?: string;
}

export type StorefrontDomainInstructionState =
  | 'active'
  | 'delivery_pending'
  | 'delivery_failed';

export interface StorefrontDomainInstructionResponse {
  status: 'sent';
  linkId: string;
  state: StorefrontDomainInstructionState;
  createdAt: string;
  expiresAt: string;
  recipientHint: string;
}

export interface StorefrontDomainInstructionLinkSummary {
  linkId: string;
  state: StorefrontDomainInstructionState;
  createdAt: string;
  expiresAt: string;
  recipientHint: string;
}

export interface StorefrontDomainInstructionRevokeResponse {
  status: 'revoked';
}

type UnknownRecord = Record<string, unknown>;

function asRecord(value: unknown): UnknownRecord | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as UnknownRecord)
    : null;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map(asString).filter((entry): entry is string => Boolean(entry))
    : [];
}

function asNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return null;
}

function asBoolean(value: unknown, fallback = false): boolean {
  return typeof value === 'boolean' ? value : fallback;
}

const STOREFRONT_DOMAIN_INSTRUCTION_STATES = new Set<StorefrontDomainInstructionState>([
  'active',
  'delivery_pending',
  'delivery_failed',
]);

function asStorefrontDomainInstructionState(
  value: unknown,
): StorefrontDomainInstructionState | null {
  const state = asString(value);
  return state && STOREFRONT_DOMAIN_INSTRUCTION_STATES.has(
    state as StorefrontDomainInstructionState,
  )
    ? (state as StorefrontDomainInstructionState)
    : null;
}

function humanizeIdentifier(value: string | null, fallback: string): string {
  if (!value) return fallback;
  return value
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function safeHttpsUrl(value: unknown): string | null {
  const candidate = asString(value);
  if (!candidate) return null;
  try {
    const parsed = new URL(candidate);
    return parsed.protocol === 'https:' ? parsed.toString() : null;
  } catch {
    return null;
  }
}

function relativeDnsHost(fqdn: string, zone: string | null): string {
  if (!zone) return fqdn;
  if (fqdn === zone) return '@';
  const suffix = `.${zone}`;
  return fqdn.endsWith(suffix) ? fqdn.slice(0, -suffix.length) : fqdn;
}

function mapProviderIdentity(rawValue: unknown): StorefrontDomainProviderIdentity {
  const raw = asRecord(rawValue) ?? {};
  const id = asString(raw.provider) ?? asString(raw.id);
  const name =
    asString(raw.provider_name) ??
    asString(raw.name) ??
    humanizeIdentifier(id, 'DNS provider not detected');
  return {
    id,
    name,
    nameservers: asStringArray(raw.nameservers),
    zone: asString(raw.zone),
    controlPanelUrl: safeHttpsUrl(
      raw.control_panel_url ?? raw.url_control_panel ?? raw.dns_control_panel_url,
    ),
  };
}

function rawRecordValues(raw: UnknownRecord): string[] {
  const list = asStringArray(raw.values ?? raw.observed_values);
  if (list.length) return list;
  const single = asString(raw.observed_value);
  return single ? [single] : [];
}

function mapDnsRecords(
  rawValue: unknown,
  provider: StorefrontDomainProviderIdentity,
  observedValue?: unknown,
): StorefrontDomainDnsRecord[] {
  const observed = Array.isArray(observedValue)
    ? observedValue.map(asRecord).filter((entry): entry is UnknownRecord => Boolean(entry))
    : [];
  if (!Array.isArray(rawValue)) return [];
  return rawValue
    .map(asRecord)
    .filter((entry): entry is UnknownRecord => Boolean(entry))
    .map((raw) => {
      const type = (asString(raw.type) ?? 'DNS').toUpperCase();
      const fqdn = asString(raw.fqdn) ?? asString(raw.name) ?? asString(raw.host) ?? '';
      const value = asString(raw.value) ?? asString(raw.target);
      const matchingObserved = observed.filter((candidate) => {
        const candidateType = (asString(candidate.type) ?? '').toUpperCase();
        const candidateName =
          asString(candidate.fqdn) ?? asString(candidate.name) ?? asString(candidate.host);
        return candidateType === type && candidateName === fqdn;
      });
      const observedValues = matchingObserved.flatMap(rawRecordValues);
      const explicitMatch = raw.matches ?? raw.verified;
      return {
        type,
        relativeHost:
          asString(raw.relative_host) ?? relativeDnsHost(fqdn, provider.zone),
        fqdn,
        value,
        ttl: asNumber(raw.ttl),
        purpose: asString(raw.purpose) ?? 'dns_setup',
        proxy:
          asString(raw.proxy) ??
          (typeof raw.proxied === 'boolean' ? (raw.proxied ? 'proxied' : 'dns_only') : null),
        observedValues,
        matches:
          typeof explicitMatch === 'boolean'
            ? explicitMatch
            : observedValues.length > 0 && value
              ? observedValues.includes(value)
              : null,
      };
    })
    .filter((record) => Boolean(record.fqdn));
}

function mapObservedRecords(
  rawValue: unknown,
  provider: StorefrontDomainProviderIdentity,
): StorefrontDomainDnsRecord[] {
  if (!Array.isArray(rawValue)) return [];
  return rawValue
    .map(asRecord)
    .filter((entry): entry is UnknownRecord => Boolean(entry))
    .flatMap((raw) => {
      const type = (asString(raw.type) ?? 'DNS').toUpperCase();
      const fqdn = asString(raw.fqdn) ?? asString(raw.name) ?? '';
      const values = rawRecordValues(raw);
      return values.length
        ? values.map((value) => ({
            type,
            relativeHost: relativeDnsHost(fqdn, provider.zone),
            fqdn,
            value,
            ttl: asNumber(raw.ttl),
            purpose: 'observed_dns',
            proxy: null,
            observedValues: values,
            matches: null,
          }))
        : [];
    });
}

function mapConflicts(rawValue: unknown): StorefrontDomainConflict[] {
  if (!Array.isArray(rawValue)) return [];
  return rawValue
    .map(asRecord)
    .filter((entry): entry is UnknownRecord => Boolean(entry))
    .map((raw) => ({
      code: asString(raw.code) ?? 'dns_conflict',
      recordType: asString(raw.record_type) ?? asString(raw.type),
      values: asStringArray(raw.values),
      message: asString(raw.message),
    }));
}

function mapStructuredError(value: unknown): StorefrontDomainErrorDetail | null {
  const raw = asRecord(value);
  if (!raw) {
    const message = asString(value);
    return message
      ? {
          code: 'storefront_domain_error',
          message,
          customerAction: null,
          retryable: false,
          supportId: null,
          field: null,
          provider: null,
        }
      : null;
  }
  const provider = asRecord(raw.provider);
  return {
    code: asString(raw.code) ?? asString(raw.error) ?? 'storefront_domain_error',
    message: asString(raw.message) ?? 'The custom-domain operation could not be completed.',
    customerAction: asString(raw.customer_action),
    retryable: asBoolean(raw.retryable),
    supportId: asString(raw.support_id),
    field: asString(raw.field),
    provider: asString(raw.provider) ?? asString(provider?.name) ?? asString(provider?.kind),
  };
}

function synthesizeLegacyExpectedRecords(raw: UnknownRecord): unknown[] {
  const records: UnknownRecord[] = [];
  const ownership = asRecord(raw.ownership_verification);
  const ownershipName = asString(ownership?.name);
  const ownershipValue = asString(ownership?.value);
  if (ownershipName && ownershipValue) {
    records.push({
      type: asString(ownership?.type) ?? 'TXT',
      name: ownershipName,
      value: ownershipValue,
      purpose: 'provider_ownership',
    });
  }
  const hostname = asString(raw.hostname);
  const cname = asString(raw.cname_target);
  if (hostname && cname) {
    records.push({
      type: 'CNAME',
      name: hostname,
      value: cname,
      purpose: 'storefront_routing',
    });
  }
  return records;
}

function mapDomainPreflight(rawValue: unknown): StorefrontDomainPreflight {
  const raw = asRecord(rawValue);
  const hostname = asString(raw?.hostname);
  if (!raw || !hostname) {
    throw new Error('Storefront domain preflight returned an unreadable response');
  }
  const provider = mapProviderIdentity(raw.authoritative_dns ?? raw.dns_provider);
  const observedRecords = mapObservedRecords(raw.observed_records, provider);
  return {
    hostname,
    hostType: asString(raw.host_type) ?? 'subdomain',
    intent: asString(raw.intent) === 'migration' ? 'migration' : 'new',
    recommendedFlow: asString(raw.recommended_flow) ?? 'manual',
    dnsProvider: provider,
    registrar:
      asString(raw.registrar) ?? asString(asRecord(raw.registrar)?.name),
    platformProvider: asString(raw.platform_provider),
    domainConnectSupported: asBoolean(
      raw.domain_connect_supported ?? asRecord(raw.domain_connect)?.supported,
    ),
    domainConnectProvider:
      asString(raw.domain_connect_provider) ?? asString(asRecord(raw.domain_connect)?.provider),
    expectedRecords: mapDnsRecords(raw.expected_records, provider, raw.observed_records),
    observedRecords,
    conflicts: mapConflicts(raw.conflicts),
    selfServiceAllowed: asBoolean(raw.self_service_allowed) ?? true,
    customerAction: asString(raw.customer_action),
  };
}

function mapDomainJourney(rawValue: unknown): StorefrontDomainJourney {
  const raw = asRecord(rawValue);
  const hostname = asString(raw?.hostname);
  if (!raw || !hostname) {
    throw new Error('Storefront custom-domain status returned an unreadable response');
  }
  const provider = mapProviderIdentity(raw.authoritative_dns ?? raw.dns_provider);
  const observedRecords = mapObservedRecords(raw.observed_records, provider);
  const expectedSource = Array.isArray(raw.expected_records)
    ? raw.expected_records
    : synthesizeLegacyExpectedRecords(raw);
  const cleanupSource = Array.isArray(raw.cleanup_records) ? raw.cleanup_records : [];
  return {
    attemptId: asString(raw.attempt_id) ?? asString(raw.provisioning_attempt_id),
    revision: asNumber(raw.revision),
    hostname,
    intent: asString(raw.intent) === 'migration' ? 'migration' : 'new',
    applicationStatus:
      asString(raw.application_status) ?? asString(raw.status) ?? 'dns_setup_pending',
    action: asString(raw.action) ?? 'check_again',
    ownershipStatus: asString(raw.ownership_status) ?? 'pending',
    routingDnsStatus: asString(raw.routing_dns_status) ?? 'pending',
    providerHostnameStatus:
      asString(raw.provider_hostname_status) ?? asString(raw.provider_status) ?? 'not_started',
    sslStatus: asString(raw.ssl_status) ?? 'not_started',
    httpsStatus: asString(raw.https_status) ?? 'not_started',
    dnsProvider: provider,
    registrar: asString(raw.registrar) ?? asString(asRecord(raw.registrar)?.name),
    platformProvider: asString(raw.platform_provider),
    domainConnectSupported: asBoolean(
      raw.domain_connect_supported ?? asRecord(raw.domain_connect)?.supported,
    ),
    domainConnectProvider:
      asString(raw.domain_connect_provider) ?? asString(asRecord(raw.domain_connect)?.provider),
    expectedRecords: mapDnsRecords(expectedSource, provider, raw.observed_records),
    observedRecords,
    conflicts: mapConflicts(raw.conflicts),
    conflictCode: asString(raw.conflict_code),
    cleanupRecords: mapDnsRecords(cleanupSource, provider),
    lastCheckedAt: asString(raw.last_checked_at),
    nextCheckAt: asString(raw.next_check_at),
    claimExpiresAt: asString(raw.claim_expires_at) ?? asString(raw.expires_at),
    lastError: mapStructuredError(raw.last_error),
  };
}

export class StorefrontCustomerError extends Error {
  readonly code: string;
  readonly customerAction: string | null;
  readonly retryable: boolean;
  readonly supportId: string | null;
  readonly field: string | null;
  readonly provider: string | null;

  constructor(detail: StorefrontDomainErrorDetail) {
    super(detail.message);
    this.name = 'StorefrontCustomerError';
    this.code = detail.code;
    this.customerAction = detail.customerAction;
    this.retryable = detail.retryable;
    this.supportId = detail.supportId;
    this.field = detail.field;
    this.provider = detail.provider;
  }
}

function parseErrorPayload(value: string): unknown {
  try {
    const parsed = JSON.parse(value) as unknown;
    const envelope = asRecord(parsed);
    if (envelope && 'error' in envelope) return envelope.error;
    return envelope && 'detail' in envelope ? envelope.detail : parsed;
  } catch {
    return value;
  }
}

function isCustomerSafeLegacyMessage(value: string | null): value is string {
  if (!value) return false;
  const trimmed = value.trim();
  return (
    trimmed.length > 0 &&
    trimmed.length <= 500 &&
    !/^[{[<]/.test(trimmed) &&
    !/\b(?:Traceback|stack trace|Exception at)\b/i.test(trimmed) &&
    !/\n\s*at\s+\S+/.test(trimmed)
  );
}

const SAFE_LEGACY_STOREFRONT_MESSAGES = new Set([
  'The custom domain is not configured.',
  'The current custom-domain attempt could not be found.',
  'The DNS ownership challenge has expired.',
  'Storefront image storage is temporarily unavailable',
]);

function knownCustomerSafeLegacyMessage(value: string | null): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  return SAFE_LEGACY_STOREFRONT_MESSAGES.has(trimmed) ? trimmed : null;
}

function sanitizeStorefrontCustomerError(
  detail: StorefrontDomainErrorDetail,
  fallbackMessage: string,
): StorefrontCustomerError {
  const supportId =
    detail.supportId && /^[a-z0-9_-]{1,128}$/i.test(detail.supportId)
      ? detail.supportId
      : null;
  return new StorefrontCustomerError({
    ...detail,
    message: isCustomerSafeLegacyMessage(detail.message)
      ? detail.message.trim()
      : fallbackMessage,
    customerAction: isCustomerSafeLegacyMessage(detail.customerAction)
      ? detail.customerAction.trim()
      : null,
    supportId,
  });
}

export function normalizeStorefrontError(
  caught: unknown,
  fallbackMessage = 'The storefront operation could not be completed.',
): StorefrontCustomerError {
  if (caught instanceof StorefrontCustomerError) {
    return sanitizeStorefrontCustomerError(
      {
        code: caught.code,
        message: caught.message,
        customerAction: caught.customerAction,
        retryable: caught.retryable,
        supportId: caught.supportId,
        field: caught.field,
        provider: caught.provider,
      },
      fallbackMessage,
    );
  }
  const rawMessage = caught instanceof Error ? caught.message : asString(caught);
  const parsed = rawMessage ? parseErrorPayload(rawMessage) : null;
  const parsedMessage = asString(parsed);
  const structured = mapStructuredError(parsed);
  const configurationFailure =
    parsedMessage?.toLowerCase().includes('cname target is not configured') ||
    structured?.code === 'custom_domain_configuration_unavailable' ||
    structured?.code === 'custom_domain_provider_configuration';
  if (configurationFailure) {
    return new StorefrontCustomerError({
      code: 'custom_domain_configuration_unavailable',
      message: 'Custom domains are temporarily unavailable.',
      customerAction:
        'Keep using your platform storefront URL. The Special Wedding support team has been notified.',
      retryable: true,
      supportId: structured?.supportId ?? null,
      field: null,
      provider: null,
    });
  }
  if (structured && asRecord(parsed)) {
    return sanitizeStorefrontCustomerError(structured, fallbackMessage);
  }
  const legacyMessage = knownCustomerSafeLegacyMessage(parsedMessage);
  return new StorefrontCustomerError({
    code: 'storefront_domain_error',
    message: legacyMessage ?? fallbackMessage,
    customerAction: 'Try again. If the problem continues, contact support.',
    retryable: true,
    supportId: null,
    field: null,
    provider: null,
  });
}

export interface StorefrontUploadReservation {
  asset_id: string;
  upload_url: string;
  cdn_url: string;
  key: string;
  max_size_bytes: number;
}

export interface StorefrontAsset {
  asset_id: string;
  slot: StorefrontImageSlot;
  state: string;
  key: string;
  cdn_url: string;
  content_type: StorefrontImageType;
  size_bytes: number;
}

export interface StorefrontAssetDeleteResponse {
  status: string;
  asset_id: string;
}

function requireResponse<T>(value: T | undefined, operation: string): T {
  if (value === undefined) {
    throw new Error(`Storefront ${operation} returned an empty response`);
  }
  return value;
}

export async function getStorefrontAccess(
  transport: StorefrontApiTransport,
): Promise<StorefrontAccess> {
  return requireResponse(
    await transport<StorefrontAccess>('/admin/storefront/access', 'GET'),
    'access request',
  );
}

export async function getStorefrontSettings(
  transport: StorefrontApiTransport,
): Promise<StorefrontSettings | null> {
  const response = requireResponse(
    await transport<{ settings: StorefrontSettings | null }>(
      '/admin/storefront/settings',
      'GET',
    ),
    'settings request',
  );
  return response.settings;
}

export async function saveStorefrontSettings(
  settings: StorefrontSettingsUpdate,
  transport: StorefrontApiTransport,
): Promise<StorefrontSettings> {
  const response = requireResponse(
    await transport<{ status: string; settings: StorefrontSettings }>(
      '/admin/storefront/settings',
      'POST',
      settings,
    ),
    'settings save',
  );
  return response.settings;
}

export function getStorefrontPreviewUrl(slug: string): string {
  return `/storefront/${encodeURIComponent(slug)}?preview=1`;
}

export async function getStorefrontPreviewData(
  slug: string,
  transport: StorefrontApiTransport,
): Promise<StorefrontPreviewData> {
  return requireResponse(
    await transport<StorefrontPreviewData>(
      `/admin/storefront/preview/${encodeURIComponent(slug)}`,
      'GET',
    ),
    'preview request',
  );
}

export async function getStorefrontPreviewSeed(
  transport: StorefrontApiTransport,
): Promise<StorefrontPreviewData> {
  return requireResponse(
    await transport<StorefrontPreviewData>('/admin/storefront/preview-data', 'GET'),
    'preview data request',
  );
}

export async function connectCustomDomain(
  domain: string,
  transport: StorefrontApiTransport,
): Promise<StorefrontDomain> {
  return requireResponse(
    await transport<StorefrontDomain>(
      '/admin/storefront/custom-domain',
      'POST',
      { domain },
    ),
    'custom-domain connect',
  );
}

export async function refreshCustomDomain(
  transport: StorefrontApiTransport,
): Promise<StorefrontDomain | null> {
  const response = await transport<StorefrontDomain | null>(
    '/admin/storefront/custom-domain/status',
    'GET',
  );
  if (response === undefined) {
    throw new Error('Storefront custom-domain refresh returned an empty response');
  }
  return response;
}

export async function removeCustomDomain(
  transport: StorefrontApiTransport,
): Promise<void> {
  await transport('/admin/storefront/custom-domain', 'DELETE');
}

export async function preflightCustomDomain(
  domain: string,
  intent: StorefrontDomainIntent,
  transport: StorefrontApiTransport,
): Promise<StorefrontDomainPreflight> {
  const response = requireResponse(
    await transport<unknown>('/admin/storefront/custom-domain/preflight', 'POST', {
      domain,
      intent,
    }),
    'custom-domain preflight',
  );
  return mapDomainPreflight(response);
}

export async function claimCustomDomain(
  domain: string,
  intent: StorefrontDomainIntent,
  transport: StorefrontApiTransport,
): Promise<StorefrontDomainJourney> {
  const response = requireResponse(
    await transport<unknown>('/admin/storefront/custom-domain/claim', 'POST', {
      domain,
      intent,
    }),
    'custom-domain claim',
  );
  return mapDomainJourney(response);
}

export async function verifyCustomDomain(
  transport: StorefrontApiTransport,
  attemptId?: string | null,
): Promise<StorefrontDomainJourney> {
  return mapDomainJourney(
    requireResponse(
      await transport<unknown>(
        '/admin/storefront/custom-domain/verify',
        'POST',
        attemptId ? { attempt_id: attemptId } : undefined,
      ),
      'custom-domain verification',
    ),
  );
}

export async function getCustomDomainStatus(
  transport: StorefrontApiTransport,
  attemptId?: string | null,
): Promise<StorefrontDomainJourney | null> {
  const statusPath = attemptId
    ? `/admin/storefront/custom-domain/status?attempt_id=${encodeURIComponent(attemptId)}`
    : '/admin/storefront/custom-domain/status';
  const response = await transport<unknown>(statusPath, 'GET');
  if (response === undefined) {
    throw new Error('Storefront custom-domain status returned an empty response');
  }
  return response === null ? null : mapDomainJourney(response);
}

export async function observeCustomDomain(
  attemptId: string,
  transport: StorefrontApiTransport,
): Promise<StorefrontDomainJourney | null> {
  const response = await transport<unknown>(
    '/admin/storefront/custom-domain/observe',
    'POST',
    { attempt_id: attemptId },
  );
  if (response === undefined) {
    throw new Error('Storefront custom-domain observation returned an empty response');
  }
  return response === null ? null : mapDomainJourney(response);
}

export async function startCustomDomainConnect(
  attemptId: string,
  transport: StorefrontApiTransport,
): Promise<StorefrontDomainConnectAuthorization> {
  const raw = asRecord(
    requireResponse(
      await transport<unknown>(
        '/admin/storefront/custom-domain/domain-connect/authorize',
        'POST',
        { attempt_id: attemptId },
      ),
      'Domain Connect authorization',
    ),
  );
  const authorizationUrl = safeHttpsUrl(raw?.authorization_url);
  const returnedAttempt = asString(raw?.attempt_id);
  if (!authorizationUrl || !returnedAttempt) {
    throw new Error('Domain Connect returned an unreadable authorization response');
  }
  return { authorizationUrl, attemptId: returnedAttempt };
}

export async function completeCustomDomainConnect(
  attemptId: string,
  transport: StorefrontApiTransport,
): Promise<StorefrontDomainJourney> {
  return mapDomainJourney(
    requireResponse(
      await transport<unknown>(
        '/admin/storefront/custom-domain/domain-connect/complete',
        'POST',
        { attempt_id: attemptId },
      ),
      'Domain Connect completion',
    ),
  );
}

export async function retryCustomDomainVerification(
  attemptId: string,
  transport: StorefrontApiTransport,
): Promise<StorefrontDomainJourney> {
  return mapDomainJourney(
    requireResponse(
      await transport<unknown>('/admin/storefront/custom-domain/retry', 'POST', {
        attempt_id: attemptId,
      }),
      'custom-domain retry',
    ),
  );
}

export async function sendCustomDomainInstructions(
  request: StorefrontDomainInstructionRequest,
  transport: StorefrontApiTransport,
): Promise<StorefrontDomainInstructionResponse> {
  const raw = asRecord(
    requireResponse(
      await transport<unknown>('/admin/storefront/custom-domain/instructions', 'POST', {
        attempt_id: request.attemptId,
        email: request.email,
        ...(request.note?.trim() ? { note: request.note.trim() } : {}),
      }),
      'custom-domain instructions',
    ),
  );
  const linkId = asString(raw?.link_id);
  const status = asString(raw?.status);
  const state = asStorefrontDomainInstructionState(raw?.state);
  const createdAt = asString(raw?.created_at);
  const expiresAt = asString(raw?.expires_at);
  const recipientHint = asString(raw?.recipient_hint);
  if (
    status !== 'sent' ||
    !linkId ||
    !state ||
    !createdAt ||
    !expiresAt ||
    !recipientHint
  ) {
    throw new Error('Custom-domain instructions returned an unreadable receipt');
  }
  return {
    status,
    linkId,
    state,
    createdAt,
    expiresAt,
    recipientHint,
  };
}

export async function getCustomDomainInstructionLinks(
  attemptId: string,
  transport: StorefrontApiTransport,
): Promise<StorefrontDomainInstructionLinkSummary[]> {
  const raw = asRecord(
    requireResponse(
      await transport<unknown>(
        `/admin/storefront/custom-domain/instructions?attempt_id=${encodeURIComponent(attemptId)}`,
        'GET',
      ),
      'custom-domain instruction links',
    ),
  );
  if (!raw || !Array.isArray(raw.links)) {
    throw new Error('Custom-domain instruction links returned an unreadable response');
  }
  return raw.links.slice(0, 20).map((value) => {
    const item = asRecord(value);
    const linkId = asString(item?.link_id);
    const state = asStorefrontDomainInstructionState(item?.state);
    const createdAt = asString(item?.created_at);
    const expiresAt = asString(item?.expires_at);
    const recipientHint = asString(item?.recipient_hint);
    if (!linkId || !state || !createdAt || !expiresAt || !recipientHint) {
      throw new Error('Custom-domain instruction links returned an unreadable receipt');
    }
    return { linkId, state, createdAt, expiresAt, recipientHint };
  });
}

export async function revokeCustomDomainInstructions(
  linkId: string,
  transport: StorefrontApiTransport,
): Promise<StorefrontDomainInstructionRevokeResponse> {
  const raw = asRecord(
    requireResponse(
      await transport<unknown>(
        `/admin/storefront/custom-domain/instructions/${encodeURIComponent(linkId)}`,
        'DELETE',
      ),
      'custom-domain instruction revocation',
    ),
  );
  if (asString(raw?.status) !== 'revoked') {
    throw new Error('Custom-domain instruction revocation returned an unreadable receipt');
  }
  return { status: 'revoked' };
}

export async function deleteStorefrontUpload(
  assetId: string,
  transport: StorefrontApiTransport,
): Promise<StorefrontAssetDeleteResponse> {
  return requireResponse(
    await transport<StorefrontAssetDeleteResponse>(
      `/admin/storefront/upload?asset_id=${encodeURIComponent(assetId)}`,
      'DELETE',
    ),
    'upload cleanup',
  );
}

function validateStorefrontImage(file: File): asserts file is File & {
  type: StorefrontImageType;
} {
  if (!(STOREFRONT_IMAGE_TYPES as readonly string[]).includes(file.type)) {
    throw new Error('Choose a JPEG, PNG, or WebP image');
  }
  if (file.size <= 0) {
    throw new Error('Choose a non-empty image');
  }
  if (file.size > MAX_STOREFRONT_IMAGE_BYTES) {
    throw new Error('Storefront images must be 5 MB or smaller');
  }
}

async function bestEffortCleanup(
  assetId: string,
  transport: StorefrontApiTransport,
): Promise<void> {
  try {
    await deleteStorefrontUpload(assetId, transport);
  } catch {
    // The durable backend reservation lifecycle also expires abandoned rows.
    // Preserve the original upload/finalize error for the caller.
  }
}

export async function uploadStorefrontImage(
  file: File,
  slot: StorefrontImageSlot,
  transport: StorefrontApiTransport,
  fetchImpl: typeof fetch = fetch,
  lifecycle: { isActive: () => boolean } = { isActive: () => true },
): Promise<StorefrontAsset> {
  validateStorefrontImage(file);

  const query = new URLSearchParams({
    filename: file.name,
    slot,
    content_type: file.type,
    size_bytes: String(file.size),
  });
  const reservation = requireResponse(
    await transport<StorefrontUploadReservation>(
      `/admin/storefront/upload-url?${query.toString()}`,
      'GET',
    ),
    'upload reservation',
  );

  try {
    if (!lifecycle.isActive()) {
      throw new Error('Storefront upload lifecycle closed before direct upload');
    }
    const uploadResponse = await fetchImpl(reservation.upload_url, {
      method: 'PUT',
      headers: { 'Content-Type': file.type },
      body: file,
    });
    if (!uploadResponse.ok) {
      const detail = (await uploadResponse.text()).trim();
      throw new Error(detail || 'Storefront image upload failed');
    }
    if (!lifecycle.isActive()) {
      throw new Error('Storefront upload lifecycle closed before finalize');
    }

    const asset = requireResponse(
      await transport<StorefrontAsset>(
        '/admin/storefront/upload-complete',
        'POST',
        { asset_id: reservation.asset_id },
      ),
      'upload finalize',
    );
    if (!lifecycle.isActive()) {
      throw new Error('Storefront upload lifecycle closed after finalize');
    }
    return asset;
  } catch (error) {
    await bestEffortCleanup(reservation.asset_id, transport);
    throw error;
  }
}
import type {
  PublicStorefrontData,
  PublicStorefrontPackage,
  PublicStorefrontPackageService,
  PublicStorefrontPlanner,
  PublicStorefrontReview,
  PublicStorefrontSettings,
} from '@/storefront/storefrontTypes';

export type {
  PublicStorefrontData,
  PublicStorefrontPackage,
  PublicStorefrontPackageService,
  PublicStorefrontPlanner,
  PublicStorefrontReview,
  PublicStorefrontSettings,
} from '@/storefront/storefrontTypes';
