/** Exact public contract used for signed custom-host origin attestation. */
export const STOREFRONT_DOMAIN_PROBE_PATH =
  '/.well-known/tsw-storefront-verification';
export const STOREFRONT_DOMAIN_PROBE_HEADER = 'x-tsw-storefront-probe';
export const STOREFRONT_DOMAIN_PROBE_HOST_HEADER = 'x-tsw-storefront-host';
export const STOREFRONT_DOMAIN_PROBE_PATTERN =
  /^v1\.[A-Za-z0-9_-]{16,128}\.[0-9a-f]{64}$/;

