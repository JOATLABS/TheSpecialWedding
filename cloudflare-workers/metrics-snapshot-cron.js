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
 *    - Optional: DEPLOYMENT_ENV (production, staging, development)
 *    - Optional: ANALYTICS_INDEX (sampling key for Analytics Engine)
 * 5. Bind Workers Analytics Engine dataset:
 *    - Binding name: WEDDING_ANALYTICAL
 *    - Dataset name: special_wedding
 * 6. Add trigger: Cron Trigger → Schedule: 0 * * * * (every hour)
 * 7. Deploy
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

                        if (env.WEDDING_ANALYTICAL && result.metrics) {
                                console.log('→ Writing metrics to Workers Analytics Engine dataset');
                                writeMetricsToAnalyticsEngine(env.WEDDING_ANALYTICAL, result.metrics, {
                                        environment: env.DEPLOYMENT_ENV || inferEnvironment(env.API_URL),
                                        index: env.ANALYTICS_INDEX || 'special-wedding',
                                });
                        } else {
                                console.log('ℹ️ Analytics Engine binding missing or metrics payload unavailable; skipping dataset write');
                        }

                        return new Response('Snapshot saved successfully', { status: 200 });

		} catch (error) {
			console.error('✗ Metrics snapshot failed:', error);
			throw error;
		}
	}
};

function writeMetricsToAnalyticsEngine(dataset, metrics, context) {
        const environment = context.environment || 'production';
        const index = context.index || 'special-wedding';

        const writeMetric = (category, name, value, dimension = 'overall') => {
                const numericValue = typeof value === 'number' ? value : Number(value);

                if (!Number.isFinite(numericValue)) {
                        return;
                }

                try {
                        dataset.writeDataPoint({
                                blobs: [category, name, dimension, environment],
                                doubles: [numericValue],
                                indexes: [index],
                        });
                } catch (error) {
                        console.error('Failed to write metric to Analytics Engine', { category, name, dimension, error });
                }
        };

        const health = metrics.health || {};
        if (health.database) {
                const statusValue = health.database === 'healthy' ? 1 : 0;
                writeMetric('health', 'database_status', statusValue, health.database);
        }
        writeMetric('health', 'db_latency_ms', health.db_latency_ms);
        writeMetric('health', 'disk_usage_percent', health.disk_usage_percent);
        writeMetric('health', 'disk_free_gb', health.disk_free_gb);
        writeMetric('health', 'memory_usage_percent', health.memory_usage_percent);
        writeMetric('health', 'memory_available_gb', health.memory_available_gb);
        writeMetric('health', 'cpu_usage_percent', health.cpu_usage_percent);

        const errors = metrics.errors || {};
        writeMetric('errors', 'total_24h', errors.total_24h);
        writeMetric('errors', 'critical_24h', errors.critical_24h);
        writeMetric('errors', 'unacknowledged', errors.unacknowledged);
        writeMetric('errors', 'error_rate_per_hour', errors.error_rate_per_hour);

        const business = metrics.business || {};
        Object.entries(business).forEach(([name, value]) => {
                writeMetric('business', name, value);
        });

        const performance = metrics.performance || {};
        const slowEndpoints = performance.slow_endpoints || [];
        slowEndpoints.forEach((endpoint, indexPosition) => {
                const endpointName = endpoint.endpoint || `unknown-${indexPosition}`;
                writeMetric('performance', 'avg_response_seconds', endpoint.avg_response_time, endpointName);
                writeMetric('performance', 'max_response_seconds', endpoint.max_response_time, endpointName);
                writeMetric('performance', 'request_count', endpoint.request_count, endpointName);
        });
}

function inferEnvironment(apiUrl) {
        if (!apiUrl) {
                return 'production';
        }

        const lowerUrl = apiUrl.toLowerCase();
        if (lowerUrl.includes('staging')) {
                return 'staging';
        }
        if (lowerUrl.includes('dev') || lowerUrl.includes('localhost')) {
                return 'development';
        }

        return 'production';
}
