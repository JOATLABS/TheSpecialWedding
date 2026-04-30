/**
 * Diagnostic endpoint that surfaces whether the frontend container can reach
 * the backend over the SSR-side API base URL.
 *
 * Used by the deploy smoke harness (scripts/deploy/verify_environment.py) to
 * produce a readable error when a misconfigured INTERNAL_API_BASE_URL would
 * otherwise show up only as `public route HTTP 500` from the slug page. The
 * payload includes the resolved `api_base` and either the upstream HTTP
 * status or the underlying fetch error message — enough to diagnose the
 * regression class we hit (DNS bad address, connection refused, TLS, 5xx)
 * without parsing `__next_error__` HTML.
 *
 * This is NOT a public health endpoint; it is named `/api/health-ssr` to
 * avoid colliding with the marketing root. Treat it as deploy-time
 * diagnostics. The route is `force-dynamic` so the cache layer never serves
 * a stale "ok" after the underlying config has drifted.
 */
import { NextResponse } from 'next/server';

import { getServerApiBaseUrl } from '@/utils/env';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const PROBE_PATH = '/health/livez';
const PROBE_REQUEST_TIMEOUT_MS = 5000;

type FailStage = 'resolve_api_base' | 'fetch_failed' | 'backend_response';

interface SuccessPayload {
  status: 'ok';
  api_base: string;
}

interface FailurePayload {
  status: 'fail';
  stage: FailStage;
  api_base?: string;
  error?: string;
  backend_status?: number;
}

export async function GET(): Promise<NextResponse<SuccessPayload | FailurePayload>> {
  let apiBase: string;
  try {
    apiBase = getServerApiBaseUrl();
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json<FailurePayload>(
      {
        status: 'fail',
        stage: 'resolve_api_base',
        error: message,
      },
      { status: 503 },
    );
  }

  const url = `${apiBase}${PROBE_PATH}`;
  try {
    const response = await fetch(url, {
      cache: 'no-store',
      signal: AbortSignal.timeout(PROBE_REQUEST_TIMEOUT_MS),
    });

    if (!response.ok) {
      return NextResponse.json<FailurePayload>(
        {
          status: 'fail',
          stage: 'backend_response',
          api_base: apiBase,
          backend_status: response.status,
        },
        { status: 503 },
      );
    }

    return NextResponse.json<SuccessPayload>({
      status: 'ok',
      api_base: apiBase,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json<FailurePayload>(
      {
        status: 'fail',
        stage: 'fetch_failed',
        api_base: apiBase,
        error: message,
      },
      { status: 503 },
    );
  }
}
