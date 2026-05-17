/**
 * Diagnostic endpoint that surfaces whether the frontend container can reach
 * the backend over the SSR-side API base URL.
 *
 * Used by the deploy smoke harness (scripts/deploy/verify_environment.py) to
 * produce a readable error when a misconfigured INTERNAL_API_BASE_URL would
 * otherwise show up only as `public route HTTP 500` from the slug page. The
 * deploy smoke runs can opt into the resolved `api_base` and upstream
 * diagnostics with SSR_HEALTHCHECK_TOKEN. Untokened production callers get
 * only a redacted status so the route does not leak internal topology.
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
const HEALTHCHECK_TOKEN_HEADER = 'x-ssr-health-token';

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

function isDetailedDiagnosticAllowed(request: Request): boolean {
  const environment = (
    process.env.ENVIRONMENT ||
    process.env.NODE_ENV ||
    'development'
  ).toLowerCase();
  if (environment !== 'production') {
    return true;
  }

  const configuredToken = process.env.SSR_HEALTHCHECK_TOKEN;
  if (!configuredToken) {
    return false;
  }

  return request.headers.get(HEALTHCHECK_TOKEN_HEADER) === configuredToken;
}

function successPayload(apiBase: string, includeDetails: boolean): SuccessPayload {
  return includeDetails
    ? { status: 'ok', api_base: apiBase }
    : { status: 'ok', api_base: 'redacted' };
}

function failurePayload(
  payload: FailurePayload,
  includeDetails: boolean,
): FailurePayload {
  if (includeDetails) {
    return payload;
  }
  return { status: 'fail', stage: payload.stage };
}

export async function GET(
  request: Request,
): Promise<NextResponse<SuccessPayload | FailurePayload>> {
  const includeDetails = isDetailedDiagnosticAllowed(request);
  let apiBase: string;
  try {
    apiBase = getServerApiBaseUrl();
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json<FailurePayload>(
      failurePayload(
        {
          status: 'fail',
          stage: 'resolve_api_base',
          error: message,
        },
        includeDetails,
      ),
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
        failurePayload(
          {
            status: 'fail',
            stage: 'backend_response',
            api_base: apiBase,
            backend_status: response.status,
          },
          includeDetails,
        ),
        { status: 503 },
      );
    }

    return NextResponse.json<SuccessPayload>(successPayload(apiBase, includeDetails));
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json<FailurePayload>(
      failurePayload(
        {
          status: 'fail',
          stage: 'fetch_failed',
          api_base: apiBase,
          error: message,
        },
        includeDetails,
      ),
      { status: 503 },
    );
  }
}
