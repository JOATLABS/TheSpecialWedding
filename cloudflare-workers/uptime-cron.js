/**
 * Cloudflare Worker - Backend Uptime Monitor
 *
 * Monitors backend API health and sends alerts via Resend if down.
 *
 * Cron Schedule: Every 5 minutes (*/5 * * * *)
 *
 * Setup Instructions:
 * 1. Go to Cloudflare Dashboard → Workers & Pages
 * 2. Create new Worker named "uptime-cron"
 * 3. Paste this code
 * 4. Add environment variables:
 *    - API_URL: https://api.thespecialwedding.com
 *    - RESEND_API_KEY: (your Resend API key)
 *    - ALERT_EMAIL: (admin email for alerts)
 * 5. Add triggers: Cron Trigger with schedule */5 * * * *
 * 6. Deploy
 *
 * Cost: $0/month (FREE tier)
 */

export default {
  async scheduled(event, env, ctx) {
    console.log('Uptime check triggered');

    try {
      const result = await checkHealth(env);

      if (!result.healthy) {
        ctx.waitUntil(sendDowntimeAlert(env, result));
      }

      console.log('Uptime check completed:', result);
      return result;

    } catch (error) {
      console.error('Uptime check failed:', error);
      ctx.waitUntil(sendDowntimeAlert(env, {
        healthy: false,
        error: error.message,
        timestamp: new Date().toISOString()
      }));
      throw error;
    }
  },

  // HTTP handler for manual triggers
  async fetch(request, env) {
    try {
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
    const response = await fetch(`${env.API_URL}/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

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
 * Send downtime alert via Resend
 */
async function sendDowntimeAlert(env, errorInfo) {
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
        subject: '🚨 BACKEND DOWN - Immediate Action Required',
        html: `
          <!DOCTYPE html>
          <html>
          <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #DC2626; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
              <h1 style="margin: 0; font-size: 24px;">🚨 BACKEND DOWN</h1>
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
                <h3 style="margin: 0 0 10px 0; font-size: 16px; color: #DC2626;">⚠️ Immediate Actions Required</h3>
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
                  View Dashboard →
                </a>
              </div>
              <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center; color: #6b7280; font-size: 12px;">
                <p style="margin: 0;">This is an automated alert from your uptime monitoring system.</p>
                <p style="margin: 5px 0 0 0;">Checks run every 5 minutes via Cloudflare Workers (FREE).</p>
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
