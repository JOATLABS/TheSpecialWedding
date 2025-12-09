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
 * 4. Add environment variables:
 *    - API_URL: https://api.thespecialwedding.com
 *    - BACKUP_SECRET: (your backup secret from .env)
 * 5. Add trigger: Cron Trigger → Schedule: 0 2 * * * (daily at 2 AM UTC)
 * 6. Deploy
 *
 * Cost: $0/month (FREE tier: 100,000 requests/day, unlimited workers)
 */

export default {
	async scheduled(event, env, ctx) {
		console.log('Starting daily backup cron job...');

		try {
			// Trigger backup endpoint on your VPS
			const response = await fetch(`${env.API_URL}/backup/trigger`, {
				method: 'POST',
				headers: {
					'Authorization': `Bearer ${env.BACKUP_SECRET}`,
					'Content-Type': 'application/json'
				}
			});

			if (!response.ok) {
				const errorText = await response.text();
				throw new Error(`Backup failed: ${response.status} - ${errorText}`);
			}

			const result = await response.json();

			console.log('✓ Backup completed successfully', result);

			// Optional: Send success notification to yourself via email
			// Using Cloudflare Email Workers (FREE)
			if (env.ALERT_EMAIL) {
				await sendSuccessEmail(env.ALERT_EMAIL, result);
			}

			return new Response('Backup completed successfully', { status: 200 });

		} catch (error) {
			console.error('✗ Backup failed:', error);

			// Send failure alert
			if (env.ALERT_EMAIL) {
				await sendFailureEmail(env.ALERT_EMAIL, error.message);
			}

			// Re-throw to mark cron execution as failed
			throw error;
		}
	}
};

/**
 * Send success notification email (optional)
 */
async function sendSuccessEmail(to, backupInfo) {
	// Using MailChannels (FREE for Cloudflare Workers)
	await fetch('https://api.mailchannels.net/tx/v1/send', {
		method: 'POST',
		headers: {
			'content-type': 'application/json',
		},
		body: JSON.stringify({
			personalizations: [{
				to: [{ email: to }],
			}],
			from: {
				email: 'backups@thespecialwedding.com',
				name: 'Backup System',
			},
			subject: '✓ Daily Backup Completed Successfully',
			content: [{
				type: 'text/html',
				value: `
					<h2>✓ Database Backup Successful</h2>
					<p>Your daily database backup has completed successfully.</p>
					<ul>
						<li><strong>Time:</strong> ${new Date().toISOString()}</li>
						<li><strong>Size:</strong> ${backupInfo.file_size_mb} MB</li>
						<li><strong>Location:</strong> ${backupInfo.storage_location}</li>
					</ul>
					<p>No action required.</p>
				`
			}],
		}),
	});
}

/**
 * Send failure notification email
 */
async function sendFailureEmail(to, errorMessage) {
	await fetch('https://api.mailchannels.net/tx/v1/send', {
		method: 'POST',
		headers: {
			'content-type': 'application/json',
		},
		body: JSON.stringify({
			personalizations: [{
				to: [{ email: to }],
			}],
			from: {
				email: 'backups@thespecialwedding.com',
				name: 'Backup System',
			},
			subject: '⚠️ Daily Backup FAILED',
			content: [{
				type: 'text/html',
				value: `
					<h2 style="color: red;">⚠️ Database Backup Failed</h2>
					<p>Your daily database backup has failed.</p>
					<p><strong>Error:</strong> ${errorMessage}</p>
					<p><strong>Time:</strong> ${new Date().toISOString()}</p>
					<p>Please check your backup system immediately.</p>
					<a href="https://admin.thespecialwedding.com/admin/platform/metrics">View Dashboard</a>
				`
			}],
		}),
	});
}
