/**
 * Cloudflare Worker - Hourly Metrics Snapshot
 *
 * FREE Cloudflare Workers Cron Trigger
 * Runs every hour to save platform metrics for historical trending
 *
 * Setup Instructions:
 * 1. Go to Cloudflare Dashboard → Workers & Pages
 * 2. Create new Worker
 * 3. Paste this code
 * 4. Add environment variables:
 *    - API_URL: https://api.thespecialwedding.com
 *    - ADMIN_TOKEN: (JWT token for ROOT_ADMIN - get from login)
 * 5. Add trigger: Cron Trigger → Schedule: 0 * * * * (every hour)
 * 6. Deploy
 *
 * Cost: $0/month (FREE tier)
 */

export default {
	async scheduled(event, env, ctx) {
		console.log('Saving metrics snapshot...');

		try {
			// Save metrics snapshot
			const response = await fetch(`${env.API_URL}/admin/platform/metrics/snapshot`, {
				method: 'POST',
				headers: {
					'Authorization': `Bearer ${env.ADMIN_TOKEN}`,
					'Content-Type': 'application/json'
				}
			});

			if (!response.ok) {
				const errorText = await response.text();
				throw new Error(`Metrics snapshot failed: ${response.status} - ${errorText}`);
			}

			const result = await response.json();

			console.log('✓ Metrics snapshot saved', result);

			return new Response('Snapshot saved successfully', { status: 200 });

		} catch (error) {
			console.error('✗ Metrics snapshot failed:', error);
			throw error;
		}
	}
};
