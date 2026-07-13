import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, it } from 'node:test';

const ROOT = process.cwd();

function source(relativePath: string): string {
  return readFileSync(path.join(ROOT, relativePath), 'utf8');
}

describe('demo capture execution', () => {
  it('executes typed product scenarios rather than synthetic cursor waypoints', () => {
    const scenarioPath = path.join(ROOT, 'scripts/demo-videos/capture-scenarios.ts');
    assert.equal(existsSync(scenarioPath), true, 'typed capture scenarios are missing');

    const recorder = source('scripts/demo-videos/record-demo-video.ts');
    assert.match(recorder, /executeDemoCaptureScenario/);
    assert.doesNotMatch(recorder, /moveLikeHuman|waypoints/);
    assert.doesNotMatch(recorder, /mouse\.wheel/);
  });

  it('gates every capture checkpoint on stable UI and a post-action assertion', () => {
    const readinessPath = path.join(ROOT, 'scripts/demo-videos/wait-for-capture-ready.ts');
    assert.equal(existsSync(readinessPath), true, 'stable capture readiness barrier is missing');

    const scenarios = source('scripts/demo-videos/capture-scenarios.ts');
    assert.match(scenarios, /assert-visible/);
    assert.match(scenarios, /checkpoint/);
    assert.match(scenarios, /click|fill|drag|press/);
  });

  it('validates manually captured product images without driving a browser or generating screenshots', () => {
    const capturePath = path.join(ROOT, 'scripts/demo-videos/capture-product-images.ts');
    assert.equal(existsSync(capturePath), false, 'scripted product-image capture must stay removed');

    const validatorPath = path.join(ROOT, 'scripts/demo-videos/validate-manual-product-images.ts');
    assert.equal(existsSync(validatorPath), true, 'manual product-image validator is missing');

    const validator = source('scripts/demo-videos/validate-manual-product-images.ts');
    assert.match(validator, /MARKETING_CAPTURE_MANIFEST/);
    assert.match(validator, /manual-in-app-browser/);
    assert.match(validator, /entry\.status !== 'approved'/);
    assert.match(validator, /PNG/);
    assert.match(validator, /checksum/);
    assert.doesNotMatch(validator, /playwright|puppeteer|chromium/i);
    assert.doesNotMatch(
      validator,
      /\.goto\s*\(|\.screenshot\s*\(|page\.(?:locator|evaluate)|browser\.(?:newContext|close)/i,
    );

    const packageJson = source('package.json');
    assert.match(
      packageJson,
      /"demo:validate-images": "tsx scripts\/demo-videos\/validate-manual-product-images\.ts"/,
    );
  });
});
