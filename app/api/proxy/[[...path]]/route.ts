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

function jsonError(message: string, status: number): NextResponse<{ error: string; detail: string }> {
  return NextResponse.json(
    {
      error: status >= 500 ? 'API proxy error' : 'API proxy request rejected',
      detail: message,
    },
    { status },
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
  const storefrontHost = resolveCustomStorefrontHost(
    request.headers.get('host'),
    {
      platformDomains: process.env.STOREFRONT_PLATFORM_DOMAINS,
      frontendUrl: process.env.FRONTEND_URL,
      apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL,
      cnameTarget: process.env.STOREFRONT_CNAME_TARGET,
    },
  );
  if (!storefrontHost) {
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
    requestedIdentifier === storefrontHost &&
    pathSegments[3] === 'inquiries'
  );
}

async function proxyRequest(request: Request, context: ProxyContext): Promise<Response> {
  const requestUrl = new URL(request.url);
  const params = await context.params;
  const pathSegments = params.path ?? [];
  if (!isAllowedCustomStorefrontRequest(request, pathSegments)) {
    return jsonError('Not Found', 404);
  }
  let apiBase: string;

  try {
    apiBase = getProxyBackendBaseUrl(requestUrl.origin);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return jsonError(message, 503);
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

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers: buildResponseHeaders(upstreamResponse.headers),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return jsonError(`Failed to reach backend API at ${targetUrl}: ${message}`, 502);
  }
}

export const GET = proxyRequest;
export const HEAD = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
export const OPTIONS = proxyRequest;
