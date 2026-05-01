import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

function readRepoFile(relativePath: string): string {
  return readFileSync(new URL(`../../${relativePath}`, import.meta.url), 'utf8');
}

test('legacy email verification page calls the verify-email backend route', () => {
  const source = readRepoFile('app/verify-email/[token]/page.tsx');

  assert.match(source, /\/verify-email\/\$\{token\}/);
});

test('email-change verification page exists and calls the verify-email-change backend route', () => {
  const source = readRepoFile('app/verify-email-change/[token]/page.tsx');

  assert.match(source, /\/verify-email-change\/\$\{token\}/);
});
