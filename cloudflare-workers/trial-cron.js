/**
 * Cloudflare Worker - Trial Management Cron Jobs
 *
 * FREE Cloudflare Workers Cron Trigger
 * Handles automated trial expiration and warning emails
 *
 * Cron Schedules:
 * - run-maintenance: Daily at 8:00 AM UTC (0 8 * * *)
 *   Sends warning emails and expires trials
 *
 * Setup Instructions:
 * 1. Go to Cloudflare Dashboard -> Workers & Pages
 * 2. Create new Worker named "trial-cron"
 * 3. Paste this code
 * 4. Add environment variables:
 *    - API_URL: https://api.thespecialwedding.io
 *    - CRON_SECRET: (same secret used by autopilot-cron)
 *    - RESEND_API_KEY: (your Resend API key for alerts)
 *    - ALERT_EMAIL: (admin email for alerts)
 * 5. Add triggers: Cron Trigger with schedule 0 8 * * *
 * 6. Deploy
 *
 * Cost: $0/month (FREE tier)
 */

export default {
  async scheduled(event, env, ctx) {
    const cronTime = event.cron;
    console.log(`Trial cron triggered: ${cronTime}`);

    let jobName = 'trial-maintenance';

    try {
      const result = await runTrialMaintenance(env);

      console.log('Trial cron completed:', result);

      // Send success notification if configured
      if (result.status === 'success') {
        ctx.waitUntil(sendSuccessNotification(env, result));
      } else {
        ctx.waitUntil(sendFailureAlert(env, jobName, result.error || 'Unknown error'));
      }

      return new Response(JSON.stringify(result), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });

    } catch (error) {
      console.error('Trial cron failed:', error);

      // Send failure alert
      ctx.waitUntil(sendFailureAlert(env, jobName, error.message));

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
        case '/run-maintenance':
          result = await runTrialMaintenance(env);
          break;
        case '/send-warnings':
          result = await sendTrialWarnings(env);
          break;
        case '/check-expired':
          result = await checkExpiredTrials(env);
          break;
        case '/health':
          result = { status: 'ok', timestamp: new Date().toISOString() };
          break;
        default:
          return new Response('Not Found. Available: /run-maintenance, /send-warnings, /check-expired, /health', { status: 404 });
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

/**
 * Run complete trial maintenance (warnings + expiration)
 */
async function runTrialMaintenance(env) {
  console.log('Running trial maintenance...');

  const response = await fetch(`${env.NEXT_PUBLIC_API_BASE_URL}/cron/trials/run-maintenance`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.CRON_SECRET}`,
      'Content-Type': 'application/json'
    }
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Trial maintenance failed: ${response.status} - ${errorText}`);
  }

  const result = await response.json();
  console.log('Trial maintenance result:', result);

  return {
    job: 'trial-maintenance',
    ...result
  };
}

/**
 * Send trial warning emails only
 */
async function sendTrialWarnings(env) {
  console.log('Sending trial warnings...');

  const response = await fetch(`${env.NEXT_PUBLIC_API_BASE_URL}/cron/trials/send-warnings`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.CRON_SECRET}`,
      'Content-Type': 'application/json'
    }
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Send trial warnings failed: ${response.status} - ${errorText}`);
  }

  const result = await response.json();
  console.log('Trial warnings result:', result);

  return {
    job: 'send-warnings',
    ...result
  };
}

/**
 * Check and expire trials only
 */
async function checkExpiredTrials(env) {
  console.log('Checking expired trials...');

  const response = await fetch(`${env.NEXT_PUBLIC_API_BASE_URL}/cron/trials/check-expired`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.CRON_SECRET}`,
      'Content-Type': 'application/json'
    }
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Check expired trials failed: ${response.status} - ${errorText}`);
  }

  const result = await response.json();
  console.log('Expired trials result:', result);

  return {
    job: 'check-expired',
    ...result
  };
}

/**
 * Send failure alert via Resend
 */
async function sendFailureAlert(env, jobName, errorMessage) {
  if (!env.RESEND_API_KEY || !env.ALERT_EMAIL) {
    console.error('RESEND_API_KEY or ALERT_EMAIL not set, cannot send alert');
    return;
  }

  try {
    await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.RESEND_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        from: 'alerts@thespecialwedding.com',
        to: [env.ALERT_EMAIL],
        subject: `Trial Cron Job Failed: ${jobName}`,
        html: `
          <!DOCTYPE html>
          <html>
          <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #DC2626; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
              <h1 style="margin: 0; font-size: 24px;">Trial Cron Job Failed</h1>
              <p style="margin: 10px 0 0 0; font-size: 14px;">The scheduled trial maintenance job encountered an error</p>
            </div>
            <div style="background-color: #f9fafb; padding: 20px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
              <div style="background-color: white; padding: 15px; border-radius: 6px; margin-bottom: 15px;">
                <h2 style="margin: 0 0 10px 0; font-size: 18px; color: #1f2937;">Error Details</h2>
                <table style="width: 100%; border-collapse: collapse;">
                  <tr>
                    <td style="padding: 8px 0; color: #6b7280; width: 100px;">Job:</td>
                    <td style="padding: 8px 0; font-weight: 600;">${jobName}</td>
                  </tr>
                  <tr>
                    <td style="padding: 8px 0; color: #6b7280;">Time:</td>
                    <td style="padding: 8px 0;">${new Date().toISOString()}</td>
                  </tr>
                  <tr>
                    <td style="padding: 8px 0; color: #6b7280;">Error:</td>
                    <td style="padding: 8px 0; color: #DC2626;">${errorMessage}</td>
                  </tr>
                </table>
              </div>
              <div style="background-color: #FEF2F2; border: 1px solid #FCA5A5; padding: 15px; border-radius: 6px; margin-bottom: 15px;">
                <h3 style="margin: 0 0 10px 0; font-size: 16px; color: #DC2626;">Impact</h3>
                <ul style="margin: 0; padding-left: 20px;">
                  <li>Trial expiration emails may not have been sent</li>
                  <li>Trial warning emails may not have been sent</li>
                  <li>Users with expired trials may still have access</li>
                </ul>
              </div>
              <div style="text-align: center; margin-top: 20px;">
                <a href="https://thespecialwedding.io/admin/users"
                   style="display: inline-block; background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600;">
                  View Users Dashboard
                </a>
              </div>
              <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center; color: #6b7280; font-size: 12px;">
                <p style="margin: 0;">This is an automated alert from your trial management system.</p>
                <p style="margin: 5px 0 0 0;">Runs daily at 8:00 AM UTC via Cloudflare Workers (FREE).</p>
              </div>
            </div>
          </body>
          </html>
        `
      })
    });

    console.log('Failure alert email sent');

  } catch (emailError) {
    console.error('Failed to send failure alert:', emailError);
  }
}

/**
 * Send success notification (optional - only if significant actions taken)
 */
async function sendSuccessNotification(env, result) {
  // Only send notification if trials were actually expired or warnings sent
  const warningsCount = result.warning_results?.warnings_sent || 0;
  const expiredCount = result.expiration_results?.expired_trials || 0;

  if (warningsCount === 0 && expiredCount === 0) {
    console.log('No trial actions taken, skipping success notification');
    return;
  }

  if (!env.RESEND_API_KEY || !env.ALERT_EMAIL) {
    return;
  }

  try {
    await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.RESEND_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        from: 'alerts@thespecialwedding.com',
        to: [env.ALERT_EMAIL],
        subject: `Trial Maintenance Complete: ${warningsCount} warnings, ${expiredCount} expired`,
        html: `
          <!DOCTYPE html>
          <html>
          <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #059669; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
              <h1 style="margin: 0; font-size: 24px;">Trial Maintenance Complete</h1>
              <p style="margin: 10px 0 0 0; font-size: 14px;">${new Date().toISOString()}</p>
            </div>
            <div style="background-color: #f9fafb; padding: 20px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
              <div style="background-color: white; padding: 15px; border-radius: 6px;">
                <h2 style="margin: 0 0 15px 0; font-size: 18px; color: #1f2937;">Summary</h2>
                <div style="display: flex; gap: 20px;">
                  <div style="flex: 1; text-align: center; padding: 15px; background: #FEF3C7; border-radius: 8px;">
                    <div style="font-size: 32px; font-weight: bold; color: #D97706;">${warningsCount}</div>
                    <div style="color: #92400E; font-size: 14px;">Warnings Sent</div>
                  </div>
                  <div style="flex: 1; text-align: center; padding: 15px; background: #FEE2E2; border-radius: 8px;">
                    <div style="font-size: 32px; font-weight: bold; color: #DC2626;">${expiredCount}</div>
                    <div style="color: #991B1B; font-size: 14px;">Trials Expired</div>
                  </div>
                </div>
              </div>
              <div style="text-align: center; margin-top: 20px;">
                <a href="https://thespecialwedding.io/admin/users"
                   style="display: inline-block; background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600;">
                  View Users Dashboard
                </a>
              </div>
            </div>
          </body>
          </html>
        `
      })
    });

    console.log('Success notification sent');

  } catch (emailError) {
    console.error('Failed to send success notification:', emailError);
  }
}
