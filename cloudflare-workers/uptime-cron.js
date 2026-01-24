/**
 * Cloudflare Worker - Backend Uptime Monitor
 *
 * Monitors backend API health and sends alerts via Resend if down.
 * Uses KV to debounce alerts (max 1 alert per hour) and track recovery.
 *
 * Cron Schedule: Every 5 minutes (*/5 * * * *)
 *
 * Setup Instructions:
 * 1. Go to Cloudflare Dashboard → Workers & Pages
 * 2. Create new Worker named "uptime-cron"
 * 3. Paste this code
 * 4. Add environment variables (via GitHub secrets):
 *    - NEXT_PUBLIC_API_BASE_URL: (backend API URL)
 *    - RESEND_API_KEY: (your Resend API key)
 *    - ALERT_EMAIL: (from email for alerts)
 *    - ROOT_ADMIN_EMAIL: (to email for alerts)
 * 5. Create KV namespace: wrangler kv:namespace create "uptime-state"
 * 6. Add KV binding in wrangler.toml (UPTIME_KV)
 * 7. Add triggers: Cron Trigger with schedule */5 * * * *
 * 8. Deploy
 *
 * Cost: $0/month (FREE tier)
 */

// Alert debounce interval (1 hour in milliseconds)
const ALERT_DEBOUNCE_MS = 60 * 60 * 1000;

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

export default {
  async scheduled(event, env, ctx) {
    console.log('Uptime check triggered');

    try {
      const result = await checkHealth(env);
      const wasDown = await getDowntimeState(env);

      if (!result.healthy) {
        // Service is down
        const shouldAlert = await shouldSendAlert(env);
        if (shouldAlert) {
          ctx.waitUntil(sendDowntimeAlert(env, result));
          ctx.waitUntil(recordAlertSent(env));
        } else {
          console.log('Alert debounced - already sent within the last hour');
        }
        // Mark service as down
        ctx.waitUntil(setDowntimeState(env, true));
      } else if (wasDown) {
        // Service recovered - send recovery notification
        console.log('Service recovered from downtime');
        ctx.waitUntil(sendRecoveryAlert(env, result));
        ctx.waitUntil(setDowntimeState(env, false));
        ctx.waitUntil(clearAlertTimestamp(env));
      }

      console.log('Uptime check completed:', result);
      return result;

    } catch (error) {
      console.error('Uptime check failed:', error);
      const shouldAlert = await shouldSendAlert(env);
      if (shouldAlert) {
        ctx.waitUntil(sendDowntimeAlert(env, {
          healthy: false,
          error: error.message,
          timestamp: new Date().toISOString()
        }));
        ctx.waitUntil(recordAlertSent(env));
      }
      ctx.waitUntil(setDowntimeState(env, true));
      throw error;
    }
  },

  // HTTP handler for manual triggers and status checks
  async fetch(request, env) {
    const url = new URL(request.url);

    try {
      if (url.pathname === '/status') {
        // Return current downtime state
        const isDown = await getDowntimeState(env);
        const lastAlert = await env.UPTIME_KV?.get('last_downtime_alert');
        return new Response(JSON.stringify({
          service_down: isDown,
          last_alert: lastAlert ? new Date(parseInt(lastAlert)).toISOString() : null
        }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        });
      }

      const result = await checkHealth(env);
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
 * Check backend health
 */
async function checkHealth(env) {
  const startTime = Date.now();

  try {
    const response = await fetchWithTimeout(`${env.NEXT_PUBLIC_API_BASE_URL}/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    }, 15000); // 15 second timeout

    const responseTime = Date.now() - startTime;
    const isHealthy = response.ok;

    if (!isHealthy) {
      console.error(`Backend health check failed: ${response.status}`);
    } else {
      console.log(`Backend healthy - Response time: ${responseTime}ms`);
    }

    return {
      healthy: isHealthy,
      status: response.status,
      statusText: response.statusText,
      responseTime,
      timestamp: new Date().toISOString()
    };

  } catch (error) {
    const responseTime = Date.now() - startTime;
    console.error('Health check error:', error.message);

    return {
      healthy: false,
      error: error.message,
      responseTime,
      timestamp: new Date().toISOString()
    };
  }
}

/**
 * KV Helper: Check if we should send an alert (debounce logic)
 */
async function shouldSendAlert(env) {
  if (!env.UPTIME_KV) {
    console.warn('UPTIME_KV not configured, skipping debounce');
    return true;
  }

  try {
    const lastAlert = await env.UPTIME_KV.get('last_downtime_alert');
    if (!lastAlert) return true;

    const timeSinceLastAlert = Date.now() - parseInt(lastAlert);
    return timeSinceLastAlert >= ALERT_DEBOUNCE_MS;
  } catch (error) {
    console.error('Error checking alert debounce:', error);
    return true; // Send alert if KV check fails
  }
}

/**
 * KV Helper: Record that an alert was sent
 */
async function recordAlertSent(env) {
  if (!env.UPTIME_KV) return;

  try {
    await env.UPTIME_KV.put('last_downtime_alert', Date.now().toString());
  } catch (error) {
    console.error('Error recording alert timestamp:', error);
  }
}

/**
 * KV Helper: Clear alert timestamp (on recovery)
 */
async function clearAlertTimestamp(env) {
  if (!env.UPTIME_KV) return;

  try {
    await env.UPTIME_KV.delete('last_downtime_alert');
  } catch (error) {
    console.error('Error clearing alert timestamp:', error);
  }
}

/**
 * KV Helper: Get downtime state
 */
async function getDowntimeState(env) {
  if (!env.UPTIME_KV) return false;

  try {
    const state = await env.UPTIME_KV.get('is_down');
    return state === 'true';
  } catch (error) {
    console.error('Error getting downtime state:', error);
    return false;
  }
}

/**
 * KV Helper: Set downtime state
 */
async function setDowntimeState(env, isDown) {
  if (!env.UPTIME_KV) return;

  try {
    await env.UPTIME_KV.put('is_down', isDown.toString());
  } catch (error) {
    console.error('Error setting downtime state:', error);
  }
}

/**
 * Send downtime alert via Resend
 */
async function sendDowntimeAlert(env, errorInfo) {
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
        subject: 'BACKEND DOWN - Immediate Action Required',
        html: `
          <!DOCTYPE html>
          <html>
          <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #DC2626; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
              <h1 style="margin: 0; font-size: 24px;">BACKEND DOWN</h1>
              <p style="margin: 10px 0 0 0; font-size: 14px;">Your backend API is not responding</p>
            </div>
            <div style="background-color: #f9fafb; padding: 20px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
              <div style="background-color: white; padding: 15px; border-radius: 6px; margin-bottom: 15px;">
                <h2 style="margin: 0 0 10px 0; font-size: 18px; color: #1f2937;">Incident Details</h2>
                <table style="width: 100%; border-collapse: collapse;">
                  <tr>
                    <td style="padding: 8px 0; color: #6b7280; width: 120px;">Time:</td>
                    <td style="padding: 8px 0;">${errorInfo.timestamp}</td>
                  </tr>
                  ${errorInfo.status ? `
                  <tr>
                    <td style="padding: 8px 0; color: #6b7280;">Status Code:</td>
                    <td style="padding: 8px 0; color: #DC2626; font-weight: 600;">${errorInfo.status}</td>
                  </tr>
                  ` : ''}
                  ${errorInfo.error ? `
                  <tr>
                    <td style="padding: 8px 0; color: #6b7280;">Error:</td>
                    <td style="padding: 8px 0; color: #DC2626;">${errorInfo.error}</td>
                  </tr>
                  ` : ''}
                  ${errorInfo.responseTime ? `
                  <tr>
                    <td style="padding: 8px 0; color: #6b7280;">Response Time:</td>
                    <td style="padding: 8px 0;">${errorInfo.responseTime}ms</td>
                  </tr>
                  ` : ''}
                </table>
              </div>
              <div style="background-color: #FEF2F2; border: 1px solid #FCA5A5; padding: 15px; border-radius: 6px; margin-bottom: 15px;">
                <h3 style="margin: 0 0 10px 0; font-size: 16px; color: #DC2626;">Immediate Actions Required</h3>
                <ol style="margin: 0; padding-left: 20px;">
                  <li>SSH into your VPS: <code>ssh user@your-vps-ip</code></li>
                  <li>Check Docker containers: <code>docker-compose ps</code></li>
                  <li>View logs: <code>docker-compose logs api --tail=100</code></li>
                  <li>Restart if needed: <code>docker-compose restart api</code></li>
                </ol>
              </div>
              <div style="text-align: center; margin-top: 20px;">
                <a href="https://admin.thespecialwedding.com/admin/platform/metrics"
                   style="display: inline-block; background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600;">
                  View Dashboard
                </a>
              </div>
              <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center; color: #6b7280; font-size: 12px;">
                <p style="margin: 0;">This is an automated alert from your uptime monitoring system.</p>
                <p style="margin: 5px 0 0 0;">Alerts are debounced to max 1 per hour. Checks run every 5 minutes.</p>
              </div>
            </div>
          </body>
          </html>
        `
      })
    });

    console.log('Downtime alert email sent');

  } catch (emailError) {
    console.error('Failed to send downtime alert:', emailError);
  }
}

/**
 * Send recovery alert via Resend
 */
async function sendRecoveryAlert(env, healthInfo) {
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
        subject: 'BACKEND RECOVERED - Service is back online',
        html: `
          <!DOCTYPE html>
          <html>
          <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #059669; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
              <h1 style="margin: 0; font-size: 24px;">BACKEND RECOVERED</h1>
              <p style="margin: 10px 0 0 0; font-size: 14px;">Your backend API is back online</p>
            </div>
            <div style="background-color: #f9fafb; padding: 20px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
              <div style="background-color: white; padding: 15px; border-radius: 6px; margin-bottom: 15px;">
                <h2 style="margin: 0 0 10px 0; font-size: 18px; color: #1f2937;">Recovery Details</h2>
                <table style="width: 100%; border-collapse: collapse;">
                  <tr>
                    <td style="padding: 8px 0; color: #6b7280; width: 120px;">Recovery Time:</td>
                    <td style="padding: 8px 0;">${healthInfo.timestamp}</td>
                  </tr>
                  <tr>
                    <td style="padding: 8px 0; color: #6b7280;">Status:</td>
                    <td style="padding: 8px 0; color: #059669; font-weight: 600;">${healthInfo.status} ${healthInfo.statusText}</td>
                  </tr>
                  <tr>
                    <td style="padding: 8px 0; color: #6b7280;">Response Time:</td>
                    <td style="padding: 8px 0;">${healthInfo.responseTime}ms</td>
                  </tr>
                </table>
              </div>
              <div style="background-color: #ECFDF5; border: 1px solid #6EE7B7; padding: 15px; border-radius: 6px; margin-bottom: 15px;">
                <p style="margin: 0; color: #065F46;">The service has recovered and is responding normally. No action is required.</p>
              </div>
              <div style="text-align: center; margin-top: 20px;">
                <a href="https://admin.thespecialwedding.com/admin/platform/metrics"
                   style="display: inline-block; background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600;">
                  View Dashboard
                </a>
              </div>
            </div>
          </body>
          </html>
        `
      })
    });

    console.log('Recovery alert email sent');

  } catch (emailError) {
    console.error('Failed to send recovery alert:', emailError);
  }
}
