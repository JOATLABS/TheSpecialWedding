/**
 * Container liveness endpoint for the frontend runtime.
 *
 * The Dockerfile HEALTHCHECK probes this route from inside the container
 * (`http://localhost:3000/api/health`). It must stay host-agnostic and
 * dependency-free:
 *
 * - `proxy.ts` fails closed (404) for any Host that is not a recognized
 *   platform domain, and its matcher excludes `api/` routes. Probing `/`
 *   with Host `localhost` therefore marks a perfectly healthy container
 *   unhealthy and Traefik drops it from rotation ("no available server",
 *   production incident 2026-07-31).
 * - It must NOT probe the backend: liveness of this container must not
 *   cascade a backend outage into a frontend restart loop. Backend
 *   reachability diagnostics live in `/api/health-ssr`.
 */
import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export function GET() {
  return NextResponse.json({ status: 'ok' });
}
