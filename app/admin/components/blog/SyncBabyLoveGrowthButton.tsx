'use client';

/**
 * Admin button that triggers a BabyLoveGrowth sync run and reports
 * the outcome via sonner toast. Lives in the BlogManager header.
 *
 * Lifecycle:
 *   idle  → POST /admin/blog/sync-babylovegrowth
 *   POST returns 200 + {status: "accepted"}
 *   we poll GET /admin/blog/sync-babylovegrowth/status
 *   until the singleton doc shows a terminal status:
 *     - "succeeded" / "partial" / "failed" → terminal, surface counts
 *     - "skipped" returned from POST means it was gated off before
 *       the lock was acquired (sync_disabled, no_api_key, lock_held)
 *       — the singleton doc is unchanged so we surface the reason
 *       straight from the POST response
 *
 * Polling caps at MAX_POLLS (45s @ 1.5s interval) to avoid hammering
 * the status endpoint if a sync takes longer than expected. If we
 * time out, the toast says so — the run continues server-side, the
 * admin can refresh later.
 */

import { useCallback, useRef, useState } from 'react';
import { Cloud, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAdmin } from '@/contexts/AdminContext';

const POLL_INTERVAL_MS = 1500;
const MAX_POLLS = 30; // 30 × 1.5s = 45 s ceiling

type PostResult =
  | { status: 'accepted'; message: string }
  | { status: 'skipped'; reason: string };

type SyncRunDoc = {
  status: 'idle' | 'running' | 'succeeded' | 'partial' | 'failed';
  new_count: number;
  skipped_count: number;
  image_failed_count: number;
  error_count: number;
  ended_at?: string | null;
};

type BackfillResultEntry = {
  blg_id: number;
  slug?: string;
  title?: string;
  status: 'ok' | 'error' | 'skipped';
  stage?: 'fetch_article' | 'upload_from_url';
  reason?: string;
  error?: string;
  cdn_url?: string;
  hero_image_url?: string;
};

type BackfillResult =
  | { status: 'skipped'; reason: string; results: BackfillResultEntry[] }
  | { status: 'idle'; reason: string; results: BackfillResultEntry[] }
  | {
      status: 'completed';
      total_targets: number;
      succeeded: number;
      failed: number;
      results: BackfillResultEntry[];
    };

interface SyncBabyLoveGrowthButtonProps {
  /** Called after a successful run so the parent can refresh its
   *  article list. Not invoked on "skipped" outcomes since the
   *  article list didn't change. */
  onSyncComplete?: () => void;
}

export default function SyncBabyLoveGrowthButton({
  onSyncComplete,
}: SyncBabyLoveGrowthButtonProps = {}) {
  const { apiRequest } = useAdmin();
  const [busy, setBusy] = useState(false);
  // Used to cancel a stale poll if the user clicks Sync again while one is in flight.
  const cancelTokenRef = useRef<{ cancelled: boolean }>({ cancelled: false });

  const runBackfill = useCallback(async () => {
    const t = toast.loading('Backfilling missing hero images on R2…');
    try {
      const result = (await apiRequest(
        '/admin/blog/sync-babylovegrowth/backfill-images',
        'POST'
      )) as BackfillResult;

      toast.dismiss(t);

      if (result.status === 'skipped' || result.status === 'idle') {
        // Idle = no articles needed backfill (silent). Skipped = no
        // API key etc. (informative).
        if (result.status === 'skipped') {
          toast.info('Backfill skipped', { description: result.reason });
        }
        return;
      }

      const failures = result.results.filter(
        (r): r is BackfillResultEntry & { status: 'error' } =>
          r.status === 'error'
      );
      const desc = `${result.succeeded} restored · ${result.failed} still failing`;

      if (result.failed === 0 && result.succeeded > 0) {
        toast.success('Hero images backfilled on R2', { description: desc });
      } else if (result.succeeded > 0) {
        toast.warning('Backfill partial', {
          description: `${desc} — see DevTools console for per-article errors`,
        });
      } else {
        toast.error('All image backfills failed', {
          description:
            failures[0]?.error ||
            'Check the FastAPI logs for BlogUploadFromUrlError details',
        });
      }

      // Always log the full per-article breakdown so the operator can
      // grab exact URLs + error strings out of DevTools when needed.
      console.info('[BLG backfill]', result);
    } catch (e) {
      toast.dismiss(t);
      const message = e instanceof Error ? e.message : String(e);
      toast.error('Backfill request failed', { description: message });
    }
  }, [apiRequest]);

  const pollUntilDone = useCallback(
    async (token: { cancelled: boolean }): Promise<SyncRunDoc | 'timeout'> => {
      for (let i = 0; i < MAX_POLLS; i++) {
        if (token.cancelled) return 'timeout';
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
        try {
          const doc = (await apiRequest(
            '/admin/blog/sync-babylovegrowth/status'
          )) as SyncRunDoc;
          // Empty state from get_last_run_status() reads as status="idle"
          // with new_count=0 — that's the seed shape. If we triggered a run
          // and the doc is back to idle, the background task hit one of the
          // pre-lock guards (sync_disabled / no_api_key) and the POST
          // response handler will have already toasted with the reason.
          // Either way, idle is terminal.
          if (doc.status !== 'running') return doc;
        } catch (e) {
          // Network blip — keep polling. If permission failed (admin
          // logged out mid-poll) the underlying apiRequest will toast.
          console.warn('Sync status poll error (continuing):', e);
        }
      }
      return 'timeout';
    },
    [apiRequest]
  );

  const handleClick = useCallback(async () => {
    if (busy) return;

    // Cancel any prior in-flight poll loop and start a fresh token.
    cancelTokenRef.current.cancelled = true;
    const token = { cancelled: false };
    cancelTokenRef.current = token;

    setBusy(true);
    const startToast = toast.loading('Starting BabyLoveGrowth sync…');

    try {
      const post = (await apiRequest(
        '/admin/blog/sync-babylovegrowth',
        'POST'
      )) as PostResult;

      if (post.status === 'skipped') {
        // Background task short-circuited before doing any work.
        // No need to poll — the singleton state doc is unchanged.
        toast.dismiss(startToast);
        toast.warning('Sync skipped', {
          description: prettifySkipReason(post.reason),
        });
        return;
      }

      toast.dismiss(startToast);
      const pollingToast = toast.loading('Sync running — polling status…');

      const result = await pollUntilDone(token);
      toast.dismiss(pollingToast);

      if (result === 'timeout') {
        toast.warning('Sync still running', {
          description: `No terminal state after ${
            (POLL_INTERVAL_MS * MAX_POLLS) / 1000
          }s. Refresh later to see the result.`,
        });
        return;
      }

      // Idle with all-zero counters = gated off before lock acquisition.
      // The POST handler already handled this above; this only happens
      // if the doc was reset between POST and first poll. Treat it as
      // a no-op.
      const ranWork =
        result.new_count > 0 ||
        result.skipped_count > 0 ||
        result.error_count > 0;
      if (result.status === 'idle' && !ranWork) {
        toast.info('Sync did not run', {
          description: 'Background task exited before acquiring the lock.',
        });
        return;
      }

      const description =
        `${result.new_count} new · ${result.skipped_count} skipped · ${result.image_failed_count} image failures · ${result.error_count} errors`;

      if (result.status === 'succeeded') {
        toast.success('Sync complete', { description });
      } else if (result.status === 'partial') {
        toast.warning('Sync finished with errors', { description });
      } else {
        // "failed" — > 20% error rate, see per-run threshold in mockup.
        toast.error('Sync failed', { description });
      }

      // Always run backfill after a non-failed sync. The backfill
      // endpoint scopes to articles with og_image=None, so it's a
      // no-op when there's nothing to do — but it catches three
      // important cases that the previous narrower condition missed:
      //   1. The sync just ran cleanly but there's a backlog of
      //      articles that failed on prior runs (e.g. R2 credentials
      //      were broken last time, now fixed)
      //   2. Hero image fetch failed this run (image_failed_count > 0)
      //   3. New articles synced without hero (new_count > 0 with
      //      null og_image — rare but possible if BLG omits the hero)
      // Running unconditionally is cheap when there's no backlog.
      if (result.status !== 'failed') {
        await runBackfill();
      }

      if (result.status === 'succeeded' || result.status === 'partial') {
        onSyncComplete?.();
      }
    } catch (e) {
      toast.dismiss(startToast);
      const message = e instanceof Error ? e.message : String(e);
      toast.error('Could not trigger sync', { description: message });
    } finally {
      setBusy(false);
    }
  }, [apiRequest, busy, onSyncComplete, pollUntilDone, runBackfill]);

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:shadow-none dark:hover:bg-white/10 dark:hover:text-white"
      aria-busy={busy}
      title="Pull new AI-generated articles from BabyLoveGrowth"
    >
      {busy ? (
        <Loader2 className="w-4 h-4 animate-spin" />
      ) : (
        <Cloud className="w-4 h-4" />
      )}
      {busy ? 'Syncing…' : 'Sync from BLG'}
    </button>
  );
}

function prettifySkipReason(reason: string): string {
  switch (reason) {
    case 'sync_disabled':
      return 'BABYLOVEGROWTH_SYNC_ENABLED is false in env. Flip it to true and restart the backend.';
    case 'no_api_key':
      return 'BABYLOVEGROWTH_API_KEY is unset. Add it to .env and restart the backend.';
    case 'lock_held':
      return 'Another sync is already in flight. Wait for it to finish and try again.';
    default:
      return reason;
  }
}
