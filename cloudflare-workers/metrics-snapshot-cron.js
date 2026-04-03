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
 * 4. Add environment variables (via GitHub secrets):
 *    - NEXT_PUBLIC_API_BASE_URL: (backend API URL)
 *    - ADMIN_TOKEN: (JWT token for ROOT_ADMIN - get from login)
 *    - Optional: DEPLOYMENT_ENV (production, staging, development)
 *    - Optional: ANALYTICS_INDEX (sampling key for Analytics Engine)
 * 5. Bind Workers Analytics Engine dataset (Wrangler automatically provisions
 *    the dataset on first write per Cloudflare docs):
 *    - Binding name: WEDDING_ANALYTICAL
 *    - Dataset name: special_wedding
 *    - If you prefer an explicit setup run:
 *        wrangler analyticsengine create special_wedding
 *    - Docs: https://developers.cloudflare.com/analytics/analytics-engine/get-started/
 * 6. Add trigger: Cron Trigger → Schedule: 0 * * * * (every hour)
 * 7. Deploy
 *
 * Cost: $0/month (FREE tier)
 */

const worker = {
  async scheduled(event, env, ctx) {
    console.log('Saving metrics snapshot...');

    try {
      const response = await fetch(`${env.NEXT_PUBLIC_API_BASE_URL}/admin/platform/metrics/snapshot`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${env.ADMIN_TOKEN}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Metrics snapshot failed: ${response.status} - ${errorText}`);
      }

      let result;
      try {
        result = await response.json();
      } catch (parseError) {
        throw new Error(`Failed to parse metrics snapshot response: ${parseError.message}`);
      }

      console.log('✓ Metrics snapshot saved', result);

      if (env.WEDDING_ANALYTICAL && result.metrics) {
        console.log('→ Writing metrics to Workers Analytics Engine dataset');
        const analyticsPromise = writeMetricsToAnalyticsEngine(
          env.WEDDING_ANALYTICAL,
          result.metrics,
          {
            environment: env.DEPLOYMENT_ENV || inferEnvironment(env.NEXT_PUBLIC_API_BASE_URL),
            index: env.ANALYTICS_INDEX || 'special-wedding',
          }
        );

        ctx.waitUntil(
          analyticsPromise.catch((error) => {
            console.error('Analytics Engine write failed', error);
          })
        );
      } else {
        console.log('ℹ️ Analytics Engine binding missing or metrics payload unavailable; skipping dataset write');
      }

      return new Response('Snapshot saved successfully', { status: 200 });
    } catch (error) {
      console.error('✗ Metrics snapshot failed:', error);
      throw error;
    }
  },
};

export default worker;

async function writeMetricsToAnalyticsEngine(dataset, metrics, context) {
  if (!dataset || typeof dataset.writeDataPoint !== 'function') {
    console.warn('Analytics Engine dataset binding is unavailable or invalid');
    return;
  }

  if (!metrics || typeof metrics !== 'object') {
    console.warn('Metrics payload missing or invalid; skipping Analytics Engine write');
    return;
  }

  const environment = context.environment || 'production';
  const index = context.index || 'special-wedding';
  const writes = [];

  const enqueueMetric = (category, name, value, dimension = 'overall') => {
    const numericValue = typeof value === 'number' ? value : Number(value);

    if (!Number.isFinite(numericValue)) {
      return;
    }

    writes.push(
      dataset
        .writeDataPoint({
          blobs: [category, name, dimension, environment],
          doubles: [numericValue],
          indexes: [index],
        })
        .catch((error) => {
          console.error('Failed to write metric to Analytics Engine', {
            category,
            name,
            dimension,
            error,
          });
        })
    );
  };

  const health = metrics.health || {};
  const databaseHealth = health.database || {};
  const cpuHealth = health.cpu || {};
  const memoryHealth = health.memory || {};
  const diskHealth = health.disk || {};

  if (databaseHealth.status) {
    const statusValue = databaseHealth.status === 'healthy' ? 1 : 0;
    enqueueMetric('health', 'database_status', statusValue, databaseHealth.status);
  }
  enqueueMetric('health', 'db_latency_ms', databaseHealth.latency_ms);
  enqueueMetric('health', 'cpu_usage_percent', cpuHealth.percent);
  if (cpuHealth.cores) {
    enqueueMetric('health', 'cpu_cores', cpuHealth.cores);
  }
  enqueueMetric('health', 'memory_usage_percent', memoryHealth.percent_used);
  enqueueMetric('health', 'memory_available_gb', memoryHealth.available_gb);
  enqueueMetric('health', 'memory_used_gb', memoryHealth.used_gb);
  enqueueMetric('health', 'disk_usage_percent', diskHealth.percent_used);
  enqueueMetric('health', 'disk_free_gb', diskHealth.free_gb);
  enqueueMetric('health', 'disk_used_gb', diskHealth.used_gb);

  const errors = metrics.errors || {};
  enqueueMetric('errors', 'total_24h', errors.total_24h);
  enqueueMetric('errors', 'critical_24h', errors.critical_24h);
  enqueueMetric('errors', 'unacknowledged', errors.unacknowledged);
  enqueueMetric('errors', 'error_rate_per_hour', errors.error_rate_per_hour);

  const business = metrics.business || {};
  Object.entries(business).forEach(([name, value]) => {
    enqueueMetric('business', name, value);
  });

  const performance = metrics.performance || {};
  const slowEndpoints = performance.slow_endpoints || [];
  slowEndpoints.forEach((endpoint, indexPosition) => {
    const endpointName = endpoint.endpoint || `unknown-${indexPosition}`;
    enqueueMetric('performance', 'avg_response_seconds', endpoint.avg_response_time, endpointName);
    enqueueMetric('performance', 'max_response_seconds', endpoint.max_response_time, endpointName);
    enqueueMetric('performance', 'request_count', endpoint.request_count, endpointName);
  });

  await Promise.all(writes);
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
