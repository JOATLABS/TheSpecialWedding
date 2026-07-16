import { NextResponse } from 'next/server';

import { getServerApiBaseUrl } from '@/utils/env';
import {
  buildStorefrontProbeIngressProof,
  STOREFRONT_DOMAIN_PROBE_INGRESS_HEADER,
} from '@/utils/storefrontDomainProbeIngress.server';
import {
  STOREFRONT_DOMAIN_PROBE_HEADER,
  STOREFRONT_DOMAIN_PROBE_HOST_HEADER,
  STOREFRONT_DOMAIN_PROBE_PATTERN,
} from '@/utils/storefrontDomainVerification';
import { resolveCustomStorefrontHost } from '@/utils/storefrontHost';

export const dynamic = 'force-dynamic';
export const fetchCache = 'force-no-store';
export const runtime = 'nodejs';

const MAX_RESPONSE_BYTES = 8 * 1024;

function notFound(): NextResponse {
  return new NextResponse('Not Found', {
    status: 404,
    headers: {
      'Cache-Control': 'no-store, max-age=0',
      'X-Content-Type-Options': 'nosniff',
    },
  });
}

async function readBoundedBody(response: Response): Promise<Uint8Array | null> {
  const declaredLength = Number(response.headers.get('content-length'));
  if (Number.isFinite(declaredLength) && declaredLength > MAX_RESPONSE_BYTES) {
    return null;
  }
  if (!response.body) {
    return new Uint8Array();
  }

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > MAX_RESPONSE_BYTES) {
        await reader.cancel();
        return null;
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  const body = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

export async function GET(request: Request): Promise<Response> {
  const requestUrl = new URL(request.url);
  if (requestUrl.search) {
    return notFound();
  }

  const authority = resolveCustomStorefrontHost(request.headers.get('host'), {
    platformDomains: process.env.STOREFRONT_PLATFORM_DOMAINS,
    frontendUrl: process.env.FRONTEND_URL,
    apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL,
    cnameTarget: process.env.STOREFRONT_CNAME_TARGET,
  });
  const challenge = request.headers.get(STOREFRONT_DOMAIN_PROBE_HEADER) ?? '';
  if (authority.kind !== 'custom' || !STOREFRONT_DOMAIN_PROBE_PATTERN.test(challenge)) {
    return notFound();
  }

  const ingressSecret = process.env.STOREFRONT_PROBE_INGRESS_SECRET ?? '';
  let ingressProof: string;
  try {
    ingressProof = buildStorefrontProbeIngressProof(
      authority.hostname,
      challenge,
      ingressSecret,
    );
  } catch {
    return notFound();
  }

  try {
    const apiBase = getServerApiBaseUrl().replace(/\/+$/, '');
    const upstream = await fetch(
      `${apiBase}/api/storefront/domain-verification-probe`,
      {
        method: 'GET',
        cache: 'no-store',
        redirect: 'manual',
        headers: {
          Accept: 'application/json',
          [STOREFRONT_DOMAIN_PROBE_HEADER]: challenge,
          [STOREFRONT_DOMAIN_PROBE_HOST_HEADER]: authority.hostname,
          [STOREFRONT_DOMAIN_PROBE_INGRESS_HEADER]: ingressProof,
        },
        signal: AbortSignal.timeout(5_000),
      },
    );
    const body = await readBoundedBody(upstream);
    if (body === null) {
      return notFound();
    }
    return new Response(body, {
      status: upstream.status,
      headers: {
        'Cache-Control': 'no-store, max-age=0',
        'Content-Type': upstream.headers.get('content-type') ?? 'application/json',
        'X-Content-Type-Options': 'nosniff',
      },
    });
  } catch {
    return notFound();
  }
}
