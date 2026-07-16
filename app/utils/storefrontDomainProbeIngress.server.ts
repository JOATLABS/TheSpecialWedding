import { createHmac } from 'node:crypto';

const PROBE_INGRESS_VERSION = '1';
const PROBE_BACKEND_PATH = '/api/storefront/domain-verification-probe';

export const STOREFRONT_DOMAIN_PROBE_INGRESS_HEADER =
  'x-tsw-storefront-ingress-proof';

function ingressPayload(hostname: string, challenge: string): string {
  return [
    `v${PROBE_INGRESS_VERSION}`,
    'GET',
    PROBE_BACKEND_PATH,
    hostname,
    challenge,
  ].join('\n');
}

export function buildStorefrontProbeIngressProof(
  hostname: string,
  challenge: string,
  ingressSecret: string,
): string {
  if (Buffer.byteLength(ingressSecret, 'utf8') < 32) {
    throw new Error('A strong storefront probe ingress secret is required');
  }
  const proof = createHmac('sha256', ingressSecret)
    .update(ingressPayload(hostname, challenge), 'utf8')
    .digest('hex');
  return `v${PROBE_INGRESS_VERSION}.${proof}`;
}
