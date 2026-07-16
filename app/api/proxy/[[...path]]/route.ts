import { randomUUID } from 'node:crypto';

import { NextResponse } from 'next/server';

import { getProxyBackendBaseUrl } from '@/utils/env';
import { resolveCustomStorefrontHost } from '@/utils/storefrontHost';

export const dynamic = 'force-dynamic';
export const fetchCache = 'force-no-store';
export const runtime = 'nodejs';

type ProxyContext = {
  params: Promise<{ path?: string[] }>;
};

type ProxyFetchInit = RequestInit & {
  duplex?: 'half';
};

const REQUEST_HEADERS_TO_STRIP = new Set([
  'connection',
  'content-length',
  'host',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
  'x-forwarded-for',
  'x-forwarded-host',
  'x-forwarded-port',
  'x-forwarded-proto',
  'x-real-ip',
]);

const RESPONSE_HEADERS_TO_STRIP = new Set([
  'connection',
  'content-encoding',
  'content-length',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
]);

type ProxyErrorEnvelope = {
  error: {
    code: string;
    message: string;
    customer_action: string;
    retryable: boolean;
    support_id: string;
    field_errors: Record<string, string>;
  };
};

function createSupportId(): string {
  return `proxy_${randomUUID().replaceAll('-', '').slice(0, 16)}`;
}

function jsonError(
  {
    code,
    message,
    customerAction,
    retryable,
    supportId = createSupportId(),
  }: {
    code: string;
    message: string;
    customerAction: string;
    retryable: boolean;
    supportId?: string;
  },
  status: number,
): NextResponse<ProxyErrorEnvelope> {
  return NextResponse.json(
    {
      error: {
        code,
        message,
        customer_action: customerAction,
        retryable,
        support_id: supportId,
        field_errors: {},
      },
    },
    { status },
  );
}

function internalProxyError(
  code: 'proxy_configuration_unavailable' | 'proxy_backend_unreachable',
  status: 502 | 503,
  request: Request,
  error: unknown,
): NextResponse<ProxyErrorEnvelope> {
  const supportId = createSupportId();
  const requestUrl = new URL(request.url);
  const errorName = error instanceof Error ? error.name : typeof error;

  // Diagnostics stay in server logs, bound to an opaque support ID. Never put
  // backend origins, request URLs, exception messages, provider payloads, or
  // secrets in either the browser response or the log event.
  console.error(`[api-proxy:${supportId}] ${code}`, {
    method: request.method,
    pathname: requestUrl.pathname,
    errorName,
  });

  return jsonError(
    {
      code,
      message: 'This service is temporarily unavailable.',
      customerAction:
        'Try again in a moment. If the problem continues, contact support with the support ID.',
      retryable: true,
      supportId,
    },
    status,
  );
}

function buildTargetUrl(apiBase: string, requestUrl: URL, pathSegments: string[]): string {
  const target = new URL(apiBase);
  const basePath = target.pathname.replace(/^\/+|\/+$/g, '');
  const proxyPath = pathSegments.map((segment) => encodeURIComponent(segment)).join('/');
  const joinedPath = [basePath, proxyPath].filter(Boolean).join('/');

  target.pathname = `/${joinedPath}`;
  target.search = requestUrl.search;
  return target.toString();
}

function buildForwardHeaders(request: Request): Headers {
  const headers = new Headers();

  request.headers.forEach((value, key) => {
    if (!REQUEST_HEADERS_TO_STRIP.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  const requestUrl = new URL(request.url);
  headers.set('x-forwarded-host', request.headers.get('host') ?? requestUrl.host);
  headers.set('x-forwarded-proto', requestUrl.protocol.replace(':', ''));

  return headers;
}

function buildResponseHeaders(upstreamHeaders: Headers): Headers {
  const headers = new Headers();
  const setCookies = upstreamHeaders.getSetCookie?.() ?? [];

  upstreamHeaders.forEach((value, key) => {
    const normalizedKey = key.toLowerCase();
    if (normalizedKey !== 'set-cookie' && !RESPONSE_HEADERS_TO_STRIP.has(normalizedKey)) {
      headers.set(key, value);
    }
  });

  for (const cookie of setCookies) {
    headers.append('set-cookie', cookie);
  }

  return headers;
}

function addForwardBody(request: Request, init: ProxyFetchInit): void {
  if (request.method === 'GET' || request.method === 'HEAD' || !request.body) {
    return;
  }

  init.body = request.body;
  init.duplex = 'half';
}

function isAllowedCustomStorefrontRequest(
  request: Request,
  pathSegments: string[],
): boolean {
  const requestUrl = new URL(request.url);
  const storefrontAuthority = resolveCustomStorefrontHost(
    request.headers.get('host'),
    {
      platformDomains: process.env.STOREFRONT_PLATFORM_DOMAINS,
      frontendUrl: process.env.FRONTEND_URL,
      apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL,
      cnameTarget: process.env.STOREFRONT_CNAME_TARGET,
    },
  );
  if (storefrontAuthority.kind === 'invalid') {
    return false;
  }
  if (storefrontAuthority.kind === 'platform') {
    return true;
  }

  let requestedIdentifier: string;
  try {
    requestedIdentifier = decodeURIComponent(pathSegments[2] ?? '');
  } catch {
    return false;
  }
  return (
    request.method === 'POST' &&
    requestUrl.search === '' &&
    pathSegments.length === 4 &&
    pathSegments[0] === 'api' &&
    pathSegments[1] === 'storefront' &&
    requestedIdentifier === storefrontAuthority.hostname &&
    pathSegments[3] === 'inquiries'
  );
}

async function proxyRequest(request: Request, context: ProxyContext): Promise<Response> {
  const requestUrl = new URL(request.url);
  const params = await context.params;
  const pathSegments = params.path ?? [];
  if (!isAllowedCustomStorefrontRequest(request, pathSegments)) {
    return jsonError(
      {
        code: 'proxy_route_not_found',
        message: 'The requested route was not found.',
        customerAction: 'Check the link and try again.',
        retryable: false,
      },
      404,
    );
  }
  let apiBase: string;

  try {
    apiBase = getProxyBackendBaseUrl(requestUrl.origin);
  } catch (err) {
    return internalProxyError('proxy_configuration_unavailable', 503, request, err);
  }

  const targetUrl = buildTargetUrl(apiBase, requestUrl, pathSegments);

  try {
    const init: ProxyFetchInit = {
      method: request.method,
      headers: buildForwardHeaders(request),
      cache: 'no-store',
      redirect: 'manual',
    };
    addForwardBody(request, init);

    const upstreamResponse = await fetch(targetUrl, init);

    // A 204/205/304 response is bodyless by definition. Passing Fetch's empty
    // ReadableStream through to Next can make Chromium abort the response even
    // though the upstream mutation succeeded, which leaves browser diagnostics
    // reporting a false network failure. Normalize those statuses to a null
    // body at the proxy boundary.
    const responseBody = [204, 205, 304].includes(upstreamResponse.status)
      ? null
      : upstreamResponse.body;

    return new Response(responseBody, {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers: buildResponseHeaders(upstreamResponse.headers),
    });
  } catch (err) {
    return internalProxyError('proxy_backend_unreachable', 502, request, err);
  }
}

export const GET = proxyRequest;
export const HEAD = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
export const OPTIONS = proxyRequest;
