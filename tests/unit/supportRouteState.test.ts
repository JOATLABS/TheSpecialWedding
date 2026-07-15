import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';


async function loadRouteState() {
  const routeState = await import('../../app/admin/support/supportRouteState').catch(() => null);
  assert.ok(routeState, 'support route-state parser is missing');
  return routeState;
}


test('report-issue query hydrates the planner support ticket form', async () => {
  const routeState = await loadRouteState();
  const params = new URLSearchParams({
    action: 'create',
    subject: 'Delivery failed',
    description: 'SMS provider rejected the message.',
    category: 'technical',
    priority: 'high',
  });

  assert.deepEqual(routeState.getSupportCreatePrefill(params, false), {
    subject: 'Delivery failed',
    description: 'SMS provider rejected the message.',
    category: 'technical',
    priority: 'high',
  });
  assert.equal(routeState.getSupportCreatePrefill(params, true), null);
});


test('support form query falls back safely for unsupported values', async () => {
  const routeState = await loadRouteState();
  const params = new URLSearchParams({
    action: 'create',
    category: 'not-real',
    priority: 'catastrophic',
  });

  assert.deepEqual(routeState.getSupportCreatePrefill(params, false), {
    subject: '',
    description: '',
    category: 'general',
    priority: 'medium',
  });
  assert.equal(
    routeState.getSupportCreatePrefill(new URLSearchParams({ action: 'view' }), false),
    null,
  );
});


test('legacy inbox redirect preserves deep-link query parameters', () => {
  const source = readFileSync('app/admin/inbox/page.tsx', 'utf8');
  assert.match(source, /searchParams/);
  assert.match(source, /URLSearchParams/);
  assert.match(source, /\/admin\/communications\/inbox\?\$\{queryString\}/);
});


test('support page consumes create-prefill state and keeps root links wedding-free', () => {
  const source = readFileSync('app/admin/support/page.tsx', 'utf8');

  assert.match(source, /getSupportCreatePrefill/);
  assert.match(source, /if \(ticket\.wedding_id && !isRootAdmin\)/);
});
