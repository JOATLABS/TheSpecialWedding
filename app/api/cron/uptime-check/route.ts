/**
 * Vercel Cron - Backend Uptime Monitor
 *
 * FREE Vercel Cron (runs every 5 minutes on Pro plan, or configure as needed)
 * Monitors backend API health and sends alerts if down
 *
 * Schedule: every 5 minutes (cron pattern minute-step-of-five; see vercel.json)
 * Configured in: vercel.json
 */

import { NextResponse } from 'next/server';

export async function GET(request: Request) {
  try {
    const API_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://api.thespecialwedding.com';

    // Check backend health
    const healthResponse = await fetch(`${API_URL}/health`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      },
      // 10 second timeout
      signal: AbortSignal.timeout(10000)
    });

    const isHealthy = healthResponse.ok;
    const responseTime = healthResponse.headers.get('X-Response-Time') || 'unknown';

    if (!isHealthy) {
      // Backend is down or unhealthy
      console.error(`❌ Backend health check failed: ${healthResponse.status}`);

      // Send alert email via Resend
      await sendDowntimeAlert({
        status: healthResponse.status,
        statusText: healthResponse.statusText,
        timestamp: new Date().toISOString()
      });

      return NextResponse.json({
        status: 'unhealthy',
        backend_status: healthResponse.status,
        checked_at: new Date().toISOString(),
        alert_sent: true
      }, { status: 200 });
    }

    // Backend is healthy
    console.log(`✓ Backend healthy - Response time: ${responseTime}ms`);

    return NextResponse.json({
      status: 'healthy',
      backend_status: 200,
      response_time: responseTime,
      checked_at: new Date().toISOString()
    }, { status: 200 });

  } catch (error: any) {
    console.error('❌ Health check error:', error.message);

    // Send critical alert
    await sendDowntimeAlert({
      error: error.message,
      timestamp: new Date().toISOString()
    });

    return NextResponse.json({
      status: 'error',
      error: error.message,
      checked_at: new Date().toISOString(),
      alert_sent: true
    }, { status: 200 });
  }
}

/**
 * Send downtime alert via Resend
 */
async function sendDowntimeAlert(errorInfo: any) {
  try {
    // Use Resend API (you already pay for this!)
    const RESEND_API_KEY = process.env.RESEND_API_KEY;
    const ALERT_EMAIL = process.env.ROOT_ADMIN_EMAIL || 'admin@example.com';

    if (!RESEND_API_KEY) {
      console.error('RESEND_API_KEY not set, cannot send alert');
      return;
    }

    await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${RESEND_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        from: 'alerts@thespecialwedding.com',
        to: [ALERT_EMAIL],
        subject: '🚨 BACKEND DOWN - Immediate Action Required',
        html: `
          <!DOCTYPE html>
          <html>
          <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
          </head>
          <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">

            <div style="background-color: #DC2626; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
              <h1 style="margin: 0; font-size: 24px;">🚨 BACKEND DOWN</h1>
              <p style="margin: 10px 0 0 0; font-size: 14px;">
                Your backend API is not responding
              </p>
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
                <p style="margin: 5px 0 0 0;">Checks run every 5 minutes via Vercel Cron (FREE).</p>
              </div>

            </div>

          </body>
          </html>
        `
      })
    });

    console.log('✓ Downtime alert email sent');

  } catch (emailError) {
    console.error('Failed to send downtime alert:', emailError);
  }
}

// Verify cron request (Vercel-specific header)
export const runtime = 'edge';
export const dynamic = 'force-dynamic';
