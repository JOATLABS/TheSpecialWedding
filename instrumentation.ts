/**
 * Next.js instrumentation hook.
 *
 * Runs once per server process at startup, before any request is served.
 * Used here to fail-fast if the frontend container cannot reach the backend
 * over its configured SSR API base URL — preventing the silent 500 cascade
 * we hit when INTERNAL_API_BASE_URL pointed at a Docker hostname that no
 * longer resolved on the frontend's network.
 *
 * Skips:
 * - Edge runtime (only the Node.js runtime renders the slug layout that
 *   exercises getServerApiBaseUrl()).
 * - The production build phase (no live backend during build).
 * - SKIP_SSR_BOOT_PROBE=1 (local dev escape hatch when running against a
 *   stopped backend on purpose).
 */
export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME !== 'nodejs') {
    return;
  }
  if (process.env.NEXT_PHASE === 'phase-production-build') {
    return;
  }
  if (process.env.SKIP_SSR_BOOT_PROBE === '1') {
    return;
  }

  // Dynamic import so the probe and its env.ts dependency are not pulled into
  // build-time evaluation. Importing eagerly would force getServerApiBaseUrl
  // to be resolved during `next build`, which has no API to talk to.
  const { runSsrBootProbe } = await import('./app/utils/ssrBootProbe');
  await runSsrBootProbe();
}
