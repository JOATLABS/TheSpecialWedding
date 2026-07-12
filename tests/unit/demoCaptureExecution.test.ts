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

  it('captures every marketed surface with named output targets and safety scanning', () => {
    const capturePath = path.join(ROOT, 'scripts/demo-videos/capture-product-images.ts');
    assert.equal(existsSync(capturePath), true, 'product-image capture runner is missing');

    const capture = source('scripts/demo-videos/capture-product-images.ts');
    for (const featureId of [
      'dashboard',
      'real-time',
      'couple-portal',
      'wedding-website',
      'configuration',
      'gallery',
      'guests',
      'seating',
      'guest-memories',
      'communications',
      'contracts',
      'payments',
      'budget',
      'vendors',
      'knowledge-base',
      'forms',
      'team',
    ]) {
      assert.match(capture, new RegExp(`['\"]${featureId}['\"]`));
    }
    assert.match(capture, /scanCaptureArtifact/);
    assert.match(capture, /capture-receipt/);
  });
});

