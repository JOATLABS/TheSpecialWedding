/**
 * Boot-time probe that fails fast when the frontend container cannot reach
 * the backend over the SSR-side API base URL.
 *
 * Background. Server components like `app/[slug]/layout.tsx` call
 * `getServerApiBaseUrl()` at request time. When that URL points somewhere the
 * frontend container can't reach (e.g. an internal Docker hostname whose DNS
 * record was lost), every public wedding page silently 500s with an opaque
 * Next.js `__next_error__` shell. The deploy completes green, traffic moves
 * over, the breakage only shows up when a smoke or end-to-end probe finally
 * hits a public slug.
 *
 * This probe is invoked from `instrumentation.ts` at server startup, before
 * Next.js accepts any traffic. If the probe fails, we exit non-zero so the
 * container crashes, Coolify (or whatever orchestrator) marks the deploy
 * unhealthy, and the failure surfaces at deploy time instead of at request
 * time.
 *
 * Retry budget is intentionally tight: 5 attempts spaced 3 seconds apart. The
 * goal is to absorb genuine container-start ordering jitter, not to wait for
 * an actually-broken backend to come back. Anything beyond ~15 seconds is a
 * misconfiguration we want to fail loudly.
 */
import { getServerApiBaseUrl } from './env';

const PROBE_PATH = '/health/livez';
const PROBE_ATTEMPTS = 5;
const PROBE_DELAY_MS = 3000;
const PROBE_REQUEST_TIMEOUT_MS = 5000;

const PROBE_TAG = '[SSR-boot-probe]';

/**
 * Sleep helper that does not import any test-only utilities.
 *
 * Kept inline so this module has no transitive dependencies beyond `env.ts`
 * and the built-in fetch — fewer ways for the probe itself to fail to start.
 */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Hit `${INTERNAL_API_BASE_URL or fallback}/health/livez` with a short retry.
 *
 * Returns on first 2xx. Throws on persistent failure with a message that
 * names the resolved API base and the last underlying error — that string is
 * the load-bearing diagnostic when this fires.
 */
async function probeBackendReachable(apiBase: string): Promise<void> {
  const url = `${apiBase}${PROBE_PATH}`;
  let lastError = 'unknown';

  for (let attempt = 1; attempt <= PROBE_ATTEMPTS; attempt++) {
    try {
      const response = await fetch(url, {
        signal: AbortSignal.timeout(PROBE_REQUEST_TIMEOUT_MS),
        cache: 'no-store',
      });
      if (response.ok) {
        console.log(`${PROBE_TAG} backend reachable at ${url} (attempt ${attempt})`);
        return;
      }
      lastError = `HTTP ${response.status}`;
    } catch (err) {
      lastError = err instanceof Error ? err.message : String(err);
    }

    console.warn(`${PROBE_TAG} attempt ${attempt}/${PROBE_ATTEMPTS} failed: ${lastError}`);

    if (attempt < PROBE_ATTEMPTS) {
      await delay(PROBE_DELAY_MS);
    }
  }

  throw new Error(
    `Backend unreachable from frontend container at ${url} after ${PROBE_ATTEMPTS} attempts. ` +
      `Last error: ${lastError}. ` +
      `Check INTERNAL_API_BASE_URL or NEXT_PUBLIC_API_BASE_URL on the frontend container — ` +
      `getServerApiBaseUrl() currently resolves to ${apiBase}.`,
  );
}

/**
 * Top-level probe entry point. Resolves the SSR API base, runs the probe,
 * and on persistent failure logs a single high-signal line and exits the
 * process with code 1.
 *
 * Intentionally never throws upward — instrumentation.register() failures in
 * Next.js are best-effort and the process can otherwise continue serving
 * broken traffic. We exit explicitly so the container restart loop catches
 * us.
 */
export async function runSsrBootProbe(): Promise<void> {
  let apiBase: string;
  try {
    apiBase = getServerApiBaseUrl();
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`${PROBE_TAG} cannot resolve API base URL: ${message}`);
    process.exit(1);
  }

  try {
    await probeBackendReachable(apiBase);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`${PROBE_TAG} ${message}`);
    process.exit(1);
  }
}
