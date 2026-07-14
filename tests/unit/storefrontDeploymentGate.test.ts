import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

const apiSource = readFileSync('app/api/storefront.py', 'utf8');
const planSource = readFileSync(
  'docs/superpowers/plans/2026-07-12-storefront-production-hardening.md',
  'utf8'
);

describe('intermediate storefront deployment gate', () => {
  it('blocks deployment while secure external lifecycle routes are absent', () => {
    const requiredLifecyclePaths = [
      '/storefront/upload-url',
      '/storefront/upload-complete',
      '/storefront/custom-domain',
      '/storefront/custom-domain/status',
    ];
    const missingPaths = requiredLifecyclePaths.filter(
      (path) => !apiSource.includes(path)
    );

    if (missingPaths.length > 0) {
      assert.match(
        planSource,
        /Storefront branch deployment gate: BLOCKED/,
        `branch must stay deployment-blocked while routes are absent: ${missingPaths.join(', ')}`
      );
    }
  });
});
