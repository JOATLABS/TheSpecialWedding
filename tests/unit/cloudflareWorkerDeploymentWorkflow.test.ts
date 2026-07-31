import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

test('cloudflare worker deploy workflow retries transient wrangler api failures', () => {
  const source = readFileSync('.github/workflows/deploy-workers.yml', 'utf8');

  assert.match(source, /name: Install Wrangler retry wrapper/);
  assert.match(source, /max_attempts="\$\{WRANGLER_RETRY_ATTEMPTS:-3\}"/);
  assert.match(source, /stdout_file="\$\(mktemp\)"/);
  assert.match(source, /sleep "\$\{delay_seconds\}"/);
  assert.match(source, /echo "Wrangler command failed with \$\{status\}; retrying \$\{attempt\}\/\$\{max_attempts\} after \$\{delay_seconds\}s\." >&2/);
  assert.match(source, /wrangler-retry kv namespace list/);
  assert.match(source, /wrangler-retry deploy --config cloudflare-workers\/autopilot\.wrangler\.toml/);
  assert.match(source, /wrangler-retry deploy --config cloudflare-workers\/scheduler\.wrangler\.toml/);
  assert.match(source, /printf '%s' "\$ROOT_ADMIN_EMAIL" \| wrangler-retry secret put ROOT_ADMIN_EMAIL/);
});
