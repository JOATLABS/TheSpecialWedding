#!/usr/bin/env node

/**
 * Run-scoped TLS edge for the production `next start` storefront testbed.
 *
 * Next's production server owns rendering and routing on a private loopback
 * HTTP port. This tiny edge only terminates the ephemeral testbed certificate
 * and preserves the original Host header so custom-host authority is exercised
 * exactly as it is at the production edge.
 */

import fs from 'node:fs';
import http from 'node:http';
import https from 'node:https';

function required(name) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const host = required('STOREFRONT_HTTPS_PROXY_HOST');
const port = Number(required('STOREFRONT_HTTPS_PROXY_PORT'));
const upstream = new URL(required('STOREFRONT_HTTPS_PROXY_UPSTREAM'));
const certificatePath = required('STOREFRONT_HTTPS_PROXY_CERT');
const privateKeyPath = required('STOREFRONT_HTTPS_PROXY_KEY');

if (
  !Number.isInteger(port) ||
  port < 1 ||
  port > 65535 ||
  upstream.protocol !== 'http:' ||
  !['127.0.0.1', 'localhost', '::1'].includes(upstream.hostname) ||
  !['127.0.0.1', 'localhost', '::1'].includes(host)
) {
  throw new Error('The storefront TLS edge requires bounded loopback endpoints');
}

const server = https.createServer(
  {
    cert: fs.readFileSync(certificatePath),
    key: fs.readFileSync(privateKeyPath),
  },
  (request, response) => {
    const headers = { ...request.headers, connection: 'close' };
    delete headers['proxy-connection'];
    const upstreamRequest = http.request(
      {
        protocol: upstream.protocol,
        hostname: upstream.hostname,
        port: upstream.port,
        method: request.method,
        path: request.url,
        headers,
      },
      (upstreamResponse) => {
        response.writeHead(
          upstreamResponse.statusCode ?? 502,
          upstreamResponse.statusMessage,
          upstreamResponse.headers,
        );
        upstreamResponse.pipe(response);
      },
    );
    upstreamRequest.setTimeout(30_000, () => {
      upstreamRequest.destroy(new Error('Next upstream timed out'));
    });
    upstreamRequest.on('error', () => {
      if (!response.headersSent) {
        response.writeHead(502, { 'content-type': 'text/plain; charset=utf-8' });
      }
      response.end('Next upstream unavailable');
    });
    request.pipe(upstreamRequest);
  },
);

server.requestTimeout = 35_000;
server.headersTimeout = 40_000;
server.listen(port, host);

const shutdown = () => server.close(() => process.exit(0));
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
