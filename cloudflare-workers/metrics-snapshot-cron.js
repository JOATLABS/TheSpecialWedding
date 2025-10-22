const SNAPSHOT_ENDPOINT = "metrics/snapshot";

function resolveSnapshotUrl(baseUrl) {
  const url = new URL(baseUrl);
  if (!url.pathname.endsWith("/")) {
    url.pathname = `${url.pathname}/`;
  }

  return new URL(SNAPSHOT_ENDPOINT, url);
}

async function fetchSnapshot(env) {
  const snapshotUrl = resolveSnapshotUrl(env.API_BASE_URL);
  const response = await fetch(snapshotUrl, {
    headers: {
      "Authorization": `Bearer ${env.API_TOKEN}`,
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch metrics snapshot: ${response.status}`);
  }

  return response.json();
}

function normalizeMetricValue(rawValue) {
  if (rawValue === null || rawValue === undefined) {
    return null;
  }

  if (typeof rawValue === "number") {
    return Number.isFinite(rawValue) ? rawValue : null;
  }

  const coerced = Number(rawValue);
  return Number.isFinite(coerced) ? coerced : null;
}

function* buildDataPoints(snapshot, timestamp) {
  if (!snapshot || typeof snapshot !== "object") {
    return;
  }

  const metrics = snapshot.metrics ?? snapshot;
  if (!metrics || typeof metrics !== "object") {
    return;
  }

  for (const [metricName, value] of Object.entries(metrics)) {
    const numericValue = normalizeMetricValue(value);
    if (numericValue === null) {
      continue;
    }

    yield {
      indexes: [timestamp],
      blobs: [metricName],
      doubles: [numericValue],
    };
  }
}

async function writeDataPoints(env, dataPoints) {
  for (const point of dataPoints) {
    await env.WEDDING_ANALYTICAL.writeDataPoint(point);
  }
}

async function handleScheduled(event, env) {
  const snapshot = await fetchSnapshot(env);
  const timestamp = Math.floor(event.scheduledTime ?? Date.now());
  await writeDataPoints(env, buildDataPoints(snapshot, timestamp));
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(handleScheduled(event, env));
  },

  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    const event = { scheduledTime: Date.now() };
    try {
      await handleScheduled(event, env);
      return new Response("ok");
    } catch (error) {
      return new Response(error instanceof Error ? error.message : String(error), {
        status: 500,
      });
    }
  },
};
