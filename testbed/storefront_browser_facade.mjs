#!/usr/bin/env node

/**
 * Loopback-only HTTP facade for visible storefront review in user-selected Chrome.
 *
 * The isolated production Next server remains private HTTP and the deterministic
 * FastAPI/provider harness remains run-scoped HTTPS. Browsers do not need to trust
 * the ephemeral test CA: provider consent and callback paths are forwarded over a
 * CA-verified loopback HTTPS connection, while every product route goes to Next.
 * This is testbed transport only and never represents external-provider proof.
 */

import fs from 'node:fs';
import http from 'node:http';
import https from 'node:https';

function required(name) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const host = required('STOREFRONT_BROWSER_FACADE_HOST');
const port = Number(required('STOREFRONT_BROWSER_FACADE_PORT'));
const backend = new URL(required('STOREFRONT_BROWSER_FACADE_BACKEND'));
const frontend = new URL(required('STOREFRONT_BROWSER_FACADE_FRONTEND'));
const httpsFrontend = new URL(
  required('STOREFRONT_BROWSER_FACADE_HTTPS_FRONTEND'),
);
const ca = fs.readFileSync(required('STOREFRONT_BROWSER_FACADE_CA'));
const loopback = new Set(['127.0.0.1', 'localhost', '::1']);

if (
  !Number.isInteger(port) ||
  port < 1 ||
  port > 65535 ||
  !loopback.has(host) ||
  !loopback.has(backend.hostname) ||
  !loopback.has(frontend.hostname) ||
  !loopback.has(httpsFrontend.hostname) ||
  backend.protocol !== 'https:' ||
  frontend.protocol !== 'http:' ||
  httpsFrontend.protocol !== 'https:'
) {
  throw new Error('The visible storefront facade requires bounded loopback origins');
}

const browserOrigin = `http://${host}:${port}`;
const backendPaths = [
  '/__testbed/storefront-provider',
  '/admin/storefront/custom-domain/domain-connect/callback',
];

function rewriteLocation(value) {
  if (!value) return value;
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    return value;
  }
  if (parsed.origin === backend.origin || parsed.origin === httpsFrontend.origin) {
    return `${browserOrigin}${parsed.pathname}${parsed.search}${parsed.hash}`;
  }
  return value;
}

function proxy(request, response) {
  const requestUrl = new URL(request.url ?? '/', browserOrigin);
  const useBackend = backendPaths.some((prefix) =>
    requestUrl.pathname.startsWith(prefix),
  );
  const upstream = useBackend ? backend : frontend;
  const transport = useBackend ? https : http;
  const headers = {
    ...request.headers,
    connection: 'close',
    host: upstream.host,
    'x-forwarded-host': request.headers.host ?? `${host}:${port}`,
    'x-forwarded-proto': 'http',
  };
  delete headers['proxy-connection'];

  const upstreamRequest = transport.request(
    {
      protocol: upstream.protocol,
      hostname: upstream.hostname,
      port: upstream.port,
      method: request.method,
      path: request.url,
      headers,
      ...(useBackend ? { ca, rejectUnauthorized: true } : {}),
    },
    (upstreamResponse) => {
      const responseHeaders = { ...upstreamResponse.headers };
      if (typeof responseHeaders.location === 'string') {
        responseHeaders.location = rewriteLocation(responseHeaders.location);
      }
      response.writeHead(
        upstreamResponse.statusCode ?? 502,
        upstreamResponse.statusMessage,
        responseHeaders,
      );
      upstreamResponse.pipe(response);
    },
  );
  upstreamRequest.setTimeout(30_000, () => {
    upstreamRequest.destroy(new Error('Visible storefront upstream timed out'));
  });
  upstreamRequest.on('error', () => {
    if (!response.headersSent) {
      response.writeHead(502, { 'content-type': 'text/plain; charset=utf-8' });
    }
    response.end('Visible storefront upstream unavailable');
  });
  request.pipe(upstreamRequest);
}

const server = http.createServer(proxy);
server.requestTimeout = 35_000;
server.headersTimeout = 40_000;
server.listen(port, host);

const shutdown = () => server.close(() => process.exit(0));
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
