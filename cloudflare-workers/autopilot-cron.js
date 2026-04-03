/**
 * Cloudflare Worker - Autopilot Payment Cron Jobs
 *
 * FREE Cloudflare Workers Cron Trigger
 * Handles automated payment processing for Wedding Finance Autopilot
 *
 * Cron Schedules:
 * - process-due-payments: Daily at 9:00 AM UTC (0 9 * * *)
 * - send-payment-reminders: Daily at 10:00 AM UTC (0 10 * * *)
 * - retry-failed-payments: Every 6 hours (0 *\/6 * * *)
 *
 * Setup Instructions:
 * 1. Go to Cloudflare Dashboard → Workers & Pages
 * 2. Create new Worker named "autopilot-cron"
 * 3. Paste this code
 * 4. Add environment variables (via GitHub secrets):
 *    - NEXT_PUBLIC_API_BASE_URL: (backend API URL)
 *    - CRON_SECRET: (secret token for cron authentication)
 *    - RESEND_API_KEY: (your Resend API key for alerts)
 *    - ALERT_EMAIL: (admin email for alerts)
 * 5. Add triggers: Cron Triggers with schedules above
 * 6. Deploy
 *
 * Cost: $0/month (FREE tier)
 */

/**
 * Fetch with timeout to prevent hanging requests
 */
async function fetchWithTimeout(url, options = {}, timeoutMs = 10000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

const worker = {
  async scheduled(event, env, ctx) {
    const cronTime = event.cron;
    console.log(`Autopilot cron triggered: ${cronTime}`);

    let jobName = 'unknown';

    try {
      // Determine which job to run based on cron schedule
      let jobResult;

      if (cronTime === '0 9 * * *') {
        jobName = 'process-due-payments';
        jobResult = await processDuePayments(env);
      } else if (cronTime === '0 10 * * *') {
        jobName = 'send-payment-reminders';
        jobResult = await sendPaymentReminders(env);
      } else if (cronTime === '0 */6 * * *') {
        jobName = 'retry-failed-payments';
        jobResult = await retryFailedPayments(env);
      } else {
        jobName = 'run-all-jobs';
        console.log('Unknown cron schedule, running all jobs');
        jobResult = await runAllJobs(env);
      }

      console.log('Autopilot cron completed:', jobResult);

      // Send success email if configured
      ctx.waitUntil(sendSuccessEmail(env, { jobs: { [jobName]: jobResult }, timestamp: new Date().toISOString() }));

      return new Response(JSON.stringify(jobResult), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });

    } catch (error) {
      console.error('Autopilot cron failed:', error);

      // Send failure alert email
      ctx.waitUntil(sendFailureEmail(env, jobName, error.message));

      throw error;
    }
  },

  // HTTP handler for manual triggers
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Verify authorization for manual triggers
    const authHeader = request.headers.get('Authorization');
    if (!authHeader || authHeader !== `Bearer ${env.CRON_SECRET}`) {
      return new Response('Unauthorized', { status: 401 });
    }

    try {
      let result;

      switch (path) {
        case '/process-due-payments':
          result = await processDuePayments(env);
          break;
        case '/send-payment-reminders':
          result = await sendPaymentReminders(env);
          break;
        case '/retry-failed-payments':
          result = await retryFailedPayments(env);
          break;
        case '/run-all':
          result = await runAllJobs(env);
          break;
        default:
          return new Response('Not Found', { status: 404 });
      }

      return new Response(JSON.stringify(result), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });

    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  }
};

export default worker;

/**
 * Process all scheduled payments that are due
 */
async function processDuePayments(env) {
  console.log('Processing due payments...');

  const response = await fetchWithTimeout(`${env.NEXT_PUBLIC_API_BASE_URL}/admin/autopilot/process-due-payments`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.CRON_SECRET}`,
      'Content-Type': 'application/json'
    }
  }, 30000);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Process due payments failed: ${response.status} - ${errorText}`);
  }

  const result = await response.json();
  console.log('Process due payments result:', result);

  return {
    job: 'process-due-payments',
    ...result
  };
}

/**
 * Send reminders for payments due in 3 days
 */
async function sendPaymentReminders(env) {
  console.log('Sending payment reminders...');

  const response = await fetchWithTimeout(`${env.NEXT_PUBLIC_API_BASE_URL}/admin/autopilot/send-payment-reminders?days_ahead=3`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.CRON_SECRET}`,
      'Content-Type': 'application/json'
    }
  }, 30000);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Send payment reminders failed: ${response.status} - ${errorText}`);
  }

  const result = await response.json();
  console.log('Send payment reminders result:', result);

  return {
    job: 'send-payment-reminders',
    ...result
  };
}

/**
 * Retry failed payments with exponential backoff
 */
async function retryFailedPayments(env) {
  console.log('Retrying failed payments...');

  const response = await fetchWithTimeout(`${env.NEXT_PUBLIC_API_BASE_URL}/admin/autopilot/retry-failed-payments`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.CRON_SECRET}`,
      'Content-Type': 'application/json'
    }
  }, 30000);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Retry failed payments failed: ${response.status} - ${errorText}`);
  }

  const result = await response.json();
  console.log('Retry failed payments result:', result);

  return {
    job: 'retry-failed-payments',
    ...result
  };
}

/**
 * Run all autopilot jobs (for manual triggers or fallback)
 */
async function runAllJobs(env) {
  const results = {
    timestamp: new Date().toISOString(),
    jobs: {}
  };

  try {
    results.jobs.processDuePayments = await processDuePayments(env);
  } catch (error) {
    results.jobs.processDuePayments = { error: error.message };
  }

  try {
    results.jobs.sendPaymentReminders = await sendPaymentReminders(env);
  } catch (error) {
    results.jobs.sendPaymentReminders = { error: error.message };
  }

  try {
    results.jobs.retryFailedPayments = await retryFailedPayments(env);
  } catch (error) {
    results.jobs.retryFailedPayments = { error: error.message };
  }

  return results;
}

/**
 * Send failure notification email via Resend API
 */
async function sendFailureEmail(env, jobName, errorMessage) {
  if (!env.RESEND_API_KEY || !env.ALERT_EMAIL || !env.ROOT_ADMIN_EMAIL) {
    console.error('RESEND_API_KEY, ALERT_EMAIL, or ROOT_ADMIN_EMAIL not set, cannot send alert');
    return;
  }

  try {
    await fetchWithTimeout('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.RESEND_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        from: env.ALERT_EMAIL,
        to: [env.ROOT_ADMIN_EMAIL],
        subject: `Autopilot Job Failed: ${jobName}`,
        html: `
          <h2 style="color: #ef4444;">Autopilot Job Failed</h2>
          <p><strong>Job:</strong> ${jobName}</p>
          <p><strong>Error:</strong> ${errorMessage}</p>
          <p><strong>Time:</strong> ${new Date().toISOString()}</p>
          <p>Please check the payment system immediately.</p>
          <a href="https://thespecialwedding.io/admin/contracts"
             style="display: inline-block; background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; margin-top: 10px;">
            View Dashboard
          </a>
        `
      })
    });
    console.log('Failure alert email sent');
  } catch (emailError) {
    console.error('Failed to send alert email:', emailError);
  }
}

/**
 * Send success summary email (optional - only if SEND_SUCCESS_EMAILS is set)
 */
async function sendSuccessEmail(env, results) {
  if (!env.RESEND_API_KEY || !env.ALERT_EMAIL || !env.ROOT_ADMIN_EMAIL || !env.SEND_SUCCESS_EMAILS) return;

  try {
    const summary = Object.entries(results.jobs || {})
      .map(([job, result]) => `<li><strong>${job}:</strong> ${result.error ? 'Failed: ' + result.error : 'Success'}</li>`)
      .join('');

    await fetchWithTimeout('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.RESEND_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        from: env.ALERT_EMAIL,
        to: [env.ROOT_ADMIN_EMAIL],
        subject: 'Autopilot Jobs Completed',
        html: `
          <h2 style="color: #22c55e;">Autopilot Jobs Completed</h2>
          <p><strong>Time:</strong> ${results.timestamp}</p>
          <ul>${summary}</ul>
        `
      })
    });
  } catch (emailError) {
    console.error('Failed to send success email:', emailError);
  }
}
