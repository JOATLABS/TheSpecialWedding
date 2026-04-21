/**
 * Cloudflare Worker - Backend Scheduler Cron
 *
 * Replaces `.github/workflows/calendar-scheduler.yml` and covers five backend
 * scheduler endpoints, three of which are currently not being triggered by
 * anything in the repo.
 *
 * Authentication: HMAC-SHA256 signing matching app/api/scheduler_jobs.py::_verify_hmac.
 *
 *   Payload:     "<unix_seconds>.<METHOD>.<path>"   (query string NOT included)
 *   Algorithm:   HMAC-SHA256, hex digest
 *   Headers:
 *     X-Scheduler-Timestamp: <unix seconds as decimal string>
 *     X-Scheduler-Signature: sha256=<hex digest>
 *   Skew window: ±300 seconds (enforced by backend)
 *
 * Cron triggers (all UTC):
 *   *\/5  * * * *    — calendar-invite-jobs + task-reminders (fan-out)
 *   *\/15 * * * *    — calendar-maintenance (sync retries + drift checks)
 *   0 4  * * *       — cleanup-reminders (DB hygiene, off-peak)
 *   0 9  * * *       — planner-onboarding-emails (drip sequence)
 *
 * Required secrets (set via deploy-workers.yml):
 *   NEXT_PUBLIC_API_BASE_URL   — backend base URL, no trailing slash
 *   SCHEDULER_HMAC_SECRET      — shared HMAC secret, mirrors backend env var
 *   RESEND_API_KEY             — for failure alerts
 *   ALERT_EMAIL                — Resend `from` address
 *   ROOT_ADMIN_EMAIL           — alert recipient
 *
 * Cost: $0/month on Cloudflare Workers free tier.
 */

// ─── HMAC helper ────────────────────────────────────────────────────────────
async function hmacSha256Hex(secret, payload) {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const sigBuf = await crypto.subtle.sign('HMAC', key, encoder.encode(payload));
  return [...new Uint8Array(sigBuf)]
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

// ─── Fetch with timeout ─────────────────────────────────────────────────────
async function fetchWithTimeout(url, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

// ─── Call a scheduler endpoint with HMAC signing ────────────────────────────
// `path` must start with '/'; `queryString` must be '' or 'key=value&...'
async function callScheduler(env, { method = 'POST', path, queryString = '' }) {
  if (!path.startsWith('/')) {
    throw new Error(`Scheduler path must start with '/', got: ${path}`);
  }
  if (!env.NEXT_PUBLIC_API_BASE_URL) {
    throw new Error('NEXT_PUBLIC_API_BASE_URL is not set');
  }
  if (!env.SCHEDULER_HMAC_SECRET) {
    throw new Error('SCHEDULER_HMAC_SECRET is not set');
  }

  const timestamp = String(Math.floor(Date.now() / 1000));
  // Backend signs `timestamp.METHOD.path` — query string is deliberately excluded.
  const payload = `${timestamp}.${method.toUpperCase()}.${path}`;
  const digest = await hmacSha256Hex(env.SCHEDULER_HMAC_SECRET, payload);

  const base = env.NEXT_PUBLIC_API_BASE_URL.replace(/\/$/, '');
  const url = `${base}${path}${queryString ? `?${queryString}` : ''}`;

  const response = await fetchWithTimeout(
    url,
    {
      method: method.toUpperCase(),
      headers: {
        'Accept': 'application/json',
        'User-Agent': 'wedding-scheduler-cron/1.0',
        'X-Scheduler-Timestamp': timestamp,
        'X-Scheduler-Signature': `sha256=${digest}`,
      },
    },
    20000
  );

  const bodyText = await response.text();
  if (!response.ok) {
    throw new Error(
      `Scheduler call ${method} ${path} failed: HTTP ${response.status} — ${bodyText.slice(0, 500)}`
    );
  }

  // Responses are JSON; fall back to raw text if parsing fails.
  try {
    return { path, status: response.status, body: JSON.parse(bodyText) };
  } catch (_parseErr) {
    return { path, status: response.status, body: bodyText };
  }
}

// ─── Individual job wrappers ────────────────────────────────────────────────
async function runCalendarInviteJobs(env) {
  return callScheduler(env, {
    path: '/scheduler/calendar-invite-jobs',
    queryString: 'limit=25',
  });
}

async function runCalendarMaintenance(env) {
  return callScheduler(env, {
    path: '/scheduler/calendar-maintenance',
    queryString: 'retry_limit=50&drift_limit=50',
  });
}

async function runTaskReminders(env) {
  return callScheduler(env, {
    path: '/scheduler/task-reminders',
  });
}

async function runCleanupReminders(env) {
  return callScheduler(env, {
    path: '/scheduler/cleanup-reminders',
    queryString: 'days_old=7',
  });
}

async function runPlannerOnboardingEmails(env) {
  return callScheduler(env, {
    path: '/scheduler/planner-onboarding-emails',
  });
}

// ─── Fan-out helper: run multiple jobs, collect per-job results ─────────────
async function runFanOut(jobs) {
  // Run in parallel; one failing job shouldn't cancel the others.
  const entries = await Promise.all(
    jobs.map(async ([name, fn]) => {
      try {
        return [name, { ok: true, ...(await fn()) }];
      } catch (error) {
        return [name, { ok: false, error: error.message }];
      }
    })
  );
  const results = Object.fromEntries(entries);
  const failed = entries.filter(([, r]) => !r.ok).map(([n]) => n);
  return { results, failed };
}

// ─── Cron dispatch ──────────────────────────────────────────────────────────
const worker = {
  async scheduled(event, env, ctx) {
    const cron = event.cron;
    console.log(`Scheduler cron triggered: ${cron}`);

    let tickName = 'unknown';
    try {
      let outcome;

      if (cron === '*/5 * * * *') {
        tickName = 'every-5min';
        // Two independent backend queues, run in parallel so one slow call
        // doesn't starve the other.
        outcome = await runFanOut([
          ['calendar-invite-jobs', () => runCalendarInviteJobs(env)],
          ['task-reminders', () => runTaskReminders(env)],
        ]);
      } else if (cron === '*/15 * * * *') {
        tickName = 'every-15min';
        outcome = await runFanOut([
          ['calendar-maintenance', () => runCalendarMaintenance(env)],
        ]);
      } else if (cron === '0 4 * * *') {
        tickName = 'daily-cleanup';
        outcome = await runFanOut([
          ['cleanup-reminders', () => runCleanupReminders(env)],
        ]);
      } else if (cron === '0 9 * * *') {
        tickName = 'daily-onboarding';
        outcome = await runFanOut([
          ['planner-onboarding-emails', () => runPlannerOnboardingEmails(env)],
        ]);
      } else {
        tickName = 'unknown-schedule';
        throw new Error(`Unrecognized cron schedule: ${cron}`);
      }

      console.log(`Scheduler tick ${tickName} completed:`, JSON.stringify(outcome));

      // If any job failed, surface it as an alert without killing the tick —
      // successful jobs already completed and we don't want CF to retry them.
      if (outcome.failed && outcome.failed.length > 0) {
        ctx.waitUntil(
          sendFailureEmail(
            env,
            `${tickName} (partial: ${outcome.failed.join(', ')})`,
            JSON.stringify(outcome.results, null, 2)
          )
        );
      }
    } catch (error) {
      console.error(`Scheduler tick ${tickName} hard-failed:`, error);
      ctx.waitUntil(sendFailureEmail(env, tickName, error.message));
      throw error; // Triggers Cloudflare's built-in retry for the whole tick.
    }
  },

  // ─── Manual HTTP trigger (for debugging, staging dry-runs, incident use) ──
  async fetch(request, env) {
    const url = new URL(request.url);

    // Gate with a bearer that's NOT the HMAC secret — reuse CRON_SECRET from
    // the existing workers so staff can curl this the same way they curl
    // autopilot-cron.
    const authHeader = request.headers.get('Authorization');
    if (!env.CRON_SECRET || !authHeader || authHeader !== `Bearer ${env.CRON_SECRET}`) {
      return new Response('Unauthorized', { status: 401 });
    }

    try {
      let result;
      switch (url.pathname) {
        case '/run/calendar-invite-jobs':
          result = await runCalendarInviteJobs(env);
          break;
        case '/run/calendar-maintenance':
          result = await runCalendarMaintenance(env);
          break;
        case '/run/task-reminders':
          result = await runTaskReminders(env);
          break;
        case '/run/cleanup-reminders':
          result = await runCleanupReminders(env);
          break;
        case '/run/planner-onboarding-emails':
          result = await runPlannerOnboardingEmails(env);
          break;
        case '/run/all':
          result = await runFanOut([
            ['calendar-invite-jobs', () => runCalendarInviteJobs(env)],
            ['calendar-maintenance', () => runCalendarMaintenance(env)],
            ['task-reminders', () => runTaskReminders(env)],
            ['cleanup-reminders', () => runCleanupReminders(env)],
            ['planner-onboarding-emails', () => runPlannerOnboardingEmails(env)],
          ]);
          break;
        default:
          return new Response(
            JSON.stringify({
              available_paths: [
                '/run/calendar-invite-jobs',
                '/run/calendar-maintenance',
                '/run/task-reminders',
                '/run/cleanup-reminders',
                '/run/planner-onboarding-emails',
                '/run/all',
              ],
            }),
            { status: 404, headers: { 'Content-Type': 'application/json' } }
          );
      }
      return new Response(JSON.stringify(result, null, 2), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  },
};

export default worker;

// ─── Alerting ───────────────────────────────────────────────────────────────
async function sendFailureEmail(env, tickName, errorDetail) {
  if (!env.RESEND_API_KEY || !env.ALERT_EMAIL || !env.ROOT_ADMIN_EMAIL) {
    console.error('Resend config missing; cannot send failure alert');
    return;
  }
  try {
    await fetchWithTimeout('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.RESEND_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: env.ALERT_EMAIL,
        to: [env.ROOT_ADMIN_EMAIL],
        subject: `Scheduler cron failed: ${tickName}`,
        html: `
          <h2 style="color:#ef4444;">Scheduler cron failure</h2>
          <p><strong>Tick:</strong> ${tickName}</p>
          <p><strong>Time:</strong> ${new Date().toISOString()}</p>
          <pre style="background:#f5f5f5;padding:12px;border-radius:6px;white-space:pre-wrap;word-break:break-word;">${escapeHtml(
            errorDetail
          )}</pre>
        `,
      }),
    });
  } catch (emailErr) {
    console.error('Failed to send failure alert:', emailErr);
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
