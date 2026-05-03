/**
 * Cloudflare Worker - Daily Database Backup
 *
 * FREE Cloudflare Workers Cron Trigger
 * Runs daily at 2:00 AM UTC to backup MongoDB to R2 storage
 *
 * Setup Instructions:
 * 1. Go to Cloudflare Dashboard → Workers & Pages
 * 2. Create new Worker
 * 3. Paste this code
 * 4. Add environment variables (via GitHub secrets):
 *    - NEXT_PUBLIC_API_BASE_URL: (backend API URL)
 *    - BACKUP_SECRET: (your backup secret from .env)
 *    - RESEND_API_KEY: (your Resend API key for alerts)
 *    - ALERT_EMAIL: (admin email for alerts)
 * 5. Add trigger: Cron Trigger → Schedule: 0 2 * * * (daily at 2 AM UTC)
 * 6. Deploy
 *
 * Cost: $0/month (FREE tier: 100,000 requests/day, unlimited workers)
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
		console.log('Starting daily backup cron job...');

		try {
			// Trigger backup endpoint on your VPS (longer timeout for backups).
			//
			// The backup router (app/api/admin_backup.py) declares
			// `prefix="/backup"`, but is mounted under `/admin/` in
			// app/main.py:882 along with every other admin router. The full
			// production path is therefore `/admin/backup/trigger`. Hitting
			// the un-prefixed `/backup/trigger` returns 404 and was the
			// reason every cron run errored out.
			// 15 minute timeout aligns with the server-side BACKUP_MAX_SECONDS
			// ceiling in app/api/admin_backup.py. A real mongodump of any
			// non-trivial database easily exceeds the previous 60 s window.
			const response = await fetchWithTimeout(`${env.NEXT_PUBLIC_API_BASE_URL}/admin/backup/trigger`, {
				method: 'POST',
				headers: {
					'Authorization': `Bearer ${env.BACKUP_SECRET}`,
					'Content-Type': 'application/json'
				}
			}, 900000);

			if (!response.ok) {
				const errorText = await response.text();
				throw new Error(`Backup failed: ${response.status} - ${errorText}`);
			}

			const result = await response.json();

			console.log('Backup completed successfully', result);

			// Send success notification via Resend
			if (env.RESEND_API_KEY && env.ALERT_EMAIL && env.ROOT_ADMIN_EMAIL) {
				ctx.waitUntil(sendSuccessEmail(env, result));
			}

			return new Response('Backup completed successfully', { status: 200 });

		} catch (error) {
			console.error('Backup failed:', error);

			// Send failure alert
			if (env.RESEND_API_KEY && env.ALERT_EMAIL && env.ROOT_ADMIN_EMAIL) {
				ctx.waitUntil(sendFailureEmail(env, error.message));
			}

			// Re-throw to mark cron execution as failed
			throw error;
		}
	}
};

export default worker;

/**
 * Send success notification email via Resend
 */
async function sendSuccessEmail(env, backupInfo) {
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
				subject: 'Daily Backup Completed Successfully',
				html: `
					<h2>Database Backup Successful</h2>
					<p>Your daily database backup has completed successfully.</p>
					<ul>
						<li><strong>Time:</strong> ${new Date().toISOString()}</li>
						<li><strong>Size:</strong> ${backupInfo.file_size_mb || 'N/A'} MB</li>
						<li><strong>Location:</strong> ${backupInfo.storage_location || 'N/A'}</li>
					</ul>
					<p>No action required.</p>
				`
			})
		});
		console.log('Success email sent');
	} catch (emailError) {
		console.error('Failed to send success email:', emailError);
	}
}

/**
 * Send failure notification email via Resend
 */
async function sendFailureEmail(env, errorMessage) {
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
				subject: 'Daily Backup FAILED',
				html: `
					<h2 style="color: red;">Database Backup Failed</h2>
					<p>Your daily database backup has failed.</p>
					<p><strong>Error:</strong> ${errorMessage}</p>
					<p><strong>Time:</strong> ${new Date().toISOString()}</p>
					<p>Please check your backup system immediately.</p>
					<a href="https://thespecialwedding.io/admin/platform/metrics"
					   style="display: inline-block; background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600;">
						View Dashboard
					</a>
				`
			})
		});
		console.log('Failure alert email sent');
	} catch (emailError) {
		console.error('Failed to send failure email:', emailError);
	}
}
