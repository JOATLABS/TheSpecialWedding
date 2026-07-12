import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { afterEach, describe, it } from 'node:test';

import { findPublicDemoStorageStateViolations } from '../../scripts/demo-videos/public-safe-storage';

const temporaryFiles: string[] = [];

function writeState(contents: string): string {
  const filePath = path.join(os.tmpdir(), `tsw-public-state-${process.pid}-${temporaryFiles.length}.json`);
  fs.writeFileSync(filePath, contents);
  temporaryFiles.push(filePath);
  return filePath;
}

afterEach(() => {
  while (temporaryFiles.length > 0) {
    fs.rmSync(temporaryFiles.pop()!, { force: true });
  }
});

describe('public marketing capture safety', () => {
  it('rejects local, fixture, error, PII, and token-shaped capture state', () => {
    const unsafe = writeState(JSON.stringify({
      origin: 'http://127.0.0.1:3100',
      label: 'DEMO PREVIEW ONLY - Development fixture sandbox',
      error: 'AI service authentication failed',
      email: 'someone@gmail.com',
      phone: '(555) 014-1188',
      authorization: 'Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature',
      contract: 'CON-DEMO-VIDEO-001',
    }));

    const violations = findPublicDemoStorageStateViolations(unsafe);
    assert.ok(violations.length >= 7, `expected broad safety findings, received ${violations.join(', ')}`);
  });

  it('allows the approved fictional product language', () => {
    const safe = writeState(JSON.stringify({
      studio: 'Marigold & Co. Weddings',
      wedding: 'Sofia & Daniel',
      product: 'The Special Wedding',
      outcome: 'One connected planner workspace',
    }));

    assert.deepEqual(findPublicDemoStorageStateViolations(safe), []);
  });
});
