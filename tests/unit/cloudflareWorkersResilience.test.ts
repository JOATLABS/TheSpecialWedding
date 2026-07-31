import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

test('scheduler cron retries transient edge and origin fetch failures before alerting', () => {
  const source = readFileSync('cloudflare-workers/scheduler-cron.js', 'utf8');

  assert.match(source, /const SCHEDULER_FETCH_ATTEMPTS = 3;/);
  assert.match(source, /RETRYABLE_SCHEDULER_STATUS_CODES = new Set\(\[[^\]]*520[^\]]*522[^\]]*524[^\]]*\]\)/s);
  assert.match(source, /for \(let attempt = 1; attempt <= SCHEDULER_FETCH_ATTEMPTS; attempt \+= 1\)/);
  assert.match(source, /isRetryableSchedulerStatus\(response\.status\)/);
  assert.match(source, /failed after \$\{SCHEDULER_FETCH_ATTEMPTS\} attempts/);
});

test('uptime cron suppresses one-off health blips before sending downtime alerts', () => {
  const source = readFileSync('cloudflare-workers/uptime-cron.js', 'utf8');

  assert.match(source, /const HEALTH_FETCH_ATTEMPTS = 3;/);
  assert.match(source, /const CONSECUTIVE_FAILURES_BEFORE_ALERT = 2;/);
  assert.match(source, /const HEALTH_CONSECUTIVE_FAILURES_KEY = 'consecutive_health_failures';/);
  assert.match(source, /RETRYABLE_HEALTH_STATUS_CODES = new Set\(\[[^\]]*520[^\]]*522[^\]]*524[^\]]*\]\)/s);
  assert.match(source, /const alertableFailure = consecutiveFailures >= CONSECUTIVE_FAILURES_BEFORE_ALERT;/);
  assert.match(source, /suppressing transient alert/);
  assert.match(source, /clearConsecutiveFailures\(env\)/);
});
