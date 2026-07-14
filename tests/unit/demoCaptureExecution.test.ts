import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { describe, it } from 'node:test';

import {
  HERO_DEMO_VIDEO,
  type DemoCaptureCheckpoint,
  type DemoVideo,
} from '../../app/data/demoVideos';
import { withTemporaryRenderInput } from '../../scripts/demo-videos/render-demo-video';
import { validateManualCaptureCheckpoints } from '../../scripts/demo-videos/validate-manual-demo-video';

const ROOT = process.cwd();

function source(relativePath: string): string {
  return readFileSync(path.join(ROOT, relativePath), 'utf8');
}

function withFrameProof(checkpoints: readonly DemoCaptureCheckpoint[]) {
  return checkpoints.map((checkpoint, index) => ({
    ...checkpoint,
    atSeconds: 5 + index * 10,
    frameSha256: 'a'.repeat(64),
  }));
}

describe('demo capture execution', () => {
  it('does not keep a scripted browser-recording path in the repository', () => {
    for (const relativePath of [
      'scripts/demo-videos/record-demo-video.ts',
      'scripts/demo-videos/capture-all-demo-videos.ts',
      'scripts/demo-videos/capture-scenarios.ts',
      'scripts/demo-videos/wait-for-capture-ready.ts',
    ]) {
      assert.equal(existsSync(path.join(ROOT, relativePath)), false, `${relativePath} must stay removed`);
    }

    const packageJson = JSON.parse(source('package.json')) as { scripts?: Record<string, string> };
    assert.equal(packageJson.scripts?.['demo:record'], undefined);
    assert.equal(packageJson.scripts?.['demo:capture-all'], undefined);
  });

  it('validates a manually driven visible-browser recording without driving a browser', () => {
    const validatorPath = path.join(ROOT, 'scripts/demo-videos/validate-manual-demo-video.ts');
    assert.equal(existsSync(validatorPath), true, 'manual demo-video validator is missing');

    const validator = source('scripts/demo-videos/validate-manual-demo-video.ts');
    assert.match(validator, /manual-visible-browser/);
    assert.match(validator, /scriptedBrowserCaptureWasUsed/);
    assert.match(validator, /ffprobe/);
    assert.match(validator, /ffmpeg/);
    assert.match(validator, /image2pipe/);
    assert.match(validator, /frameSha256/);
    assert.match(validator, /atSeconds/);
    assert.match(validator, /runtimeBuildIdentity/);
    assert.match(validator, /meta\[name="tsw-app-build-commit"\]/);
    assert.match(validator, /isolated local capture server/);
    assert.match(validator, /cat-file/);
    assert.match(validator, /merge-base/);
    assert.match(validator, /--is-ancestor/);
    assert.match(validator, /recording commit must be an ancestor of current HEAD/);
    assert.doesNotMatch(validator, /does not match current HEAD/);
    assert.match(validator, /--untracked-files=all/);
    assert.doesNotMatch(validator, /--untracked-files=no/);
    assert.match(validator, /requires a clean worktree/);
    assert.match(validator, /artifactSha256/);
    assert.match(validator, /capture bounds must preserve the entire product window/);
    assert.doesNotMatch(validator, /playwright|puppeteer|chromium/i);
    assert.doesNotMatch(
      validator,
      /\.goto\s*\(|\.screenshot\s*\(|page\.(?:locator|evaluate)|browser\.(?:newContext|close)/i,
    );

    const packageJson = source('package.json');
    assert.match(
      packageJson,
      /"demo:validate-manual-video": "tsx scripts\/demo-videos\/validate-manual-demo-video\.ts"/,
    );

    const renderer = source('scripts/demo-videos/render-demo-video.ts');
    assert.match(renderer, /validateManualDemoVideo\(receiptPath\)/);
    assert.match(renderer, /Manual demo renders do not accept --raw or --duration-seconds overrides/);
    assert.match(renderer, /requirement\.narrationPath/);
    assert.match(renderer, /requirement\.renderNarrationInputPath/);
    assert.match(renderer, /ffprobe/);
    assert.match(renderer, /Rendered walkthrough does not contain an audio stream/);
    assert.match(renderer, /buildWebVttForDemo/);
    assert.match(renderer, /requirement\.captionPath/);
    assert.doesNotMatch(renderer, /writeJson\(captionFile/);

    const productionValidator = source('scripts/demo-videos/validate-demo-video-production.ts');
    assert.match(productionValidator, /raw footage must stay outside public/);
    assert.match(productionValidator, /Missing narration/);
    assert.match(productionValidator, /Temporary Remotion narration input remains/);
    assert.match(productionValidator, /validateDemoVideoPlaybackApproval\(demoId\)/);

    const layout = source('app/layout.tsx');
    assert.match(layout, /<meta name="tsw-app-build-commit" content=\{appBuildCommit\} \/>/);
    const nextConfig = source('next.config.js');
    assert.match(nextConfig, /git', \['rev-parse', 'HEAD'\]/);
    assert.match(nextConfig, /NEXT_PUBLIC_APP_BUILD_COMMIT:\s*appBuildCommit/);
  });

  it('requires the ordered hero journey instead of accepting duplicate placeholder checkpoints', () => {
    const approvedCheckpoints = HERO_DEMO_VIDEO.captureCheckpoints;
    assert.ok(approvedCheckpoints);
    const receiptCheckpoints = withFrameProof(approvedCheckpoints);
    assert.doesNotThrow(() => validateManualCaptureCheckpoints(receiptCheckpoints, HERO_DEMO_VIDEO));

    assert.throws(
      () => validateManualCaptureCheckpoints(
        Array.from({ length: approvedCheckpoints.length }, (_, index) => ({
          label: `Placeholder ${index + 1}`,
          route: '/admin/planner',
          action: 'Open a page.',
          visibleResult: 'A page is visible.',
          atSeconds: 5 + index * 10,
          frameSha256: 'a'.repeat(64),
        })),
        HERO_DEMO_VIDEO,
      ),
      /missing the ordered checkpoint Planner command center/,
    );

    assert.throws(
      () => validateManualCaptureCheckpoints(
        receiptCheckpoints.map((checkpoint) => ({ ...checkpoint, label: `Other ${checkpoint.label}` })),
        HERO_DEMO_VIDEO,
      ),
      /missing the ordered checkpoint Planner command center/,
    );

    assert.throws(
      () => validateManualCaptureCheckpoints([
        ...receiptCheckpoints.slice(0, 1),
        {
          ...receiptCheckpoints[1],
          route: '/admin/weddings/[id]',
        },
        ...receiptCheckpoints.slice(2),
      ], HERO_DEMO_VIDEO),
      /must be a resolved application pathname/,
    );

    const seatingIndex = receiptCheckpoints.findIndex((checkpoint) => checkpoint.label === 'Seating plan');
    assert.ok(seatingIndex >= 0);
    assert.throws(
      () => validateManualCaptureCheckpoints(
        receiptCheckpoints.map((checkpoint, index) => index === seatingIndex
          ? { ...checkpoint, route: `${checkpoint.route}&view=compact` }
          : checkpoint),
        HERO_DEMO_VIDEO,
      ),
      /not part of .* route plan/,
    );
    assert.throws(
      () => validateManualCaptureCheckpoints(
        receiptCheckpoints.map((checkpoint, index) => index === seatingIndex
          ? { ...checkpoint, route: '/admin/seating?weddingId=wedding_marketing_capture_sofia_daniel' }
          : checkpoint),
        HERO_DEMO_VIDEO,
      ),
      /not part of .* route plan/,
    );
    assert.throws(
      () => validateManualCaptureCheckpoints(
        receiptCheckpoints.map((checkpoint, index) => index === 2
          ? { ...checkpoint, atSeconds: receiptCheckpoints[index - 1].atSeconds }
          : checkpoint),
        HERO_DEMO_VIDEO,
      ),
      /atSeconds values must be strictly increasing/,
    );
    assert.throws(
      () => validateManualCaptureCheckpoints(
        receiptCheckpoints.map((checkpoint, index) => index === 2
          ? { ...checkpoint, frameSha256: 'not-a-frame-hash' }
          : checkpoint),
        HERO_DEMO_VIDEO,
      ),
      /frameSha256 must be a full SHA-256 checksum/,
    );
  });

  it('rejects Phase 1 demos that do not define at least three exact checkpoints', () => {
    const phaseOneDemo: DemoVideo = {
      ...HERO_DEMO_VIDEO,
      id: 'phase-one-contract-test',
      priority: 'phase-one',
      routePlan: ['/admin/planner'],
      captureCheckpoints: undefined,
    };
    const genericCheckpoint = withFrameProof([
      {
        label: 'Generic page',
        route: '/admin/planner',
        action: 'Inspect the page.',
        visibleResult: 'The page is visible.',
      },
    ]);

    assert.throws(
      () => validateManualCaptureCheckpoints(genericCheckpoint, phaseOneDemo),
      /phase-one-contract-test must define at least 3 exact capture checkpoints/,
    );

    assert.throws(
      () => validateManualCaptureCheckpoints(genericCheckpoint, {
        ...phaseOneDemo,
        captureCheckpoints: [
          {
            label: 'Only one exact checkpoint',
            route: '/admin/planner',
            action: 'Inspect the planner dashboard.',
            visibleResult: 'The planner dashboard is visible.',
          },
        ],
      }),
      /phase-one-contract-test must define at least 3 exact capture checkpoints/,
    );

    const placeholderContract = Array.from({ length: 3 }, (_, index) => ({
      label: `Placeholder ${index + 1}`,
      route: '/admin/planner',
      action: 'Open a page.',
      visibleResult: 'A page is visible.',
    }));
    assert.throws(
      () => validateManualCaptureCheckpoints(
        withFrameProof(placeholderContract),
        { ...phaseOneDemo, captureCheckpoints: placeholderContract },
      ),
      /must define a meaningful label, action, and visible result/,
    );
  });

  it('removes the ignored Remotion input even when rendering throws', () => {
    const temporaryDirectory = mkdtempSync(path.join(os.tmpdir(), 'demo-video-render-input-'));
    const rawRecording = path.join(temporaryDirectory, 'raw.mp4');
    const stagedRecording = path.join(temporaryDirectory, 'public', '.render-input', 'raw.mp4');
    writeFileSync(rawRecording, 'manually recorded pixels');

    try {
      assert.throws(
        () => withTemporaryRenderInput(rawRecording, stagedRecording, () => {
          assert.equal(readFileSync(stagedRecording, 'utf8'), 'manually recorded pixels');
          throw new Error('render failed');
        }),
        /render failed/,
      );
      assert.equal(existsSync(stagedRecording), false);
    } finally {
      rmSync(temporaryDirectory, { recursive: true, force: true });
    }
  });

  it('validates manually captured product images without driving a browser or generating screenshots', () => {
    const capturePath = path.join(ROOT, 'scripts/demo-videos/capture-product-images.ts');
    assert.equal(existsSync(capturePath), false, 'scripted product-image capture must stay removed');

    const validatorPath = path.join(ROOT, 'scripts/demo-videos/validate-manual-product-images.ts');
    assert.equal(existsSync(validatorPath), true, 'manual product-image validator is missing');

    const validator = source('scripts/demo-videos/validate-manual-product-images.ts');
    assert.match(validator, /MARKETING_CAPTURE_MANIFEST/);
    assert.match(validator, /manual-visible-browser/);
    assert.match(validator, /pageZoomPercent/);
    assert.match(validator, /devicePixelRatio/);
    assert.match(validator, /Capture screenshot/);
    assert.match(validator, /scriptedBrowserCaptureWasUsed/);
    assert.match(validator, /entry\.status !== 'approved'/);
    assert.match(validator, /runtimeBuildIdentity/);
    assert.match(validator, /MARKETING_CAPTURE_BUILD_IDENTITY_SELECTOR/);
    assert.match(validator, /merge-base/);
    assert.match(validator, /--is-ancestor/);
    assert.match(validator, /capture build must be an ancestor of current HEAD/);
    assert.match(validator, /--verify-git-ancestry/);
    assert.match(validator, /validatePublishedProductImages/);
    assert.match(validator, /--published/);
    assert.match(validator, /PNG/);
    assert.match(validator, /checksum/);
    assert.doesNotMatch(validator, /playwright|puppeteer|chromium/i);
    assert.doesNotMatch(
      validator,
      /\.goto\s*\(|\.screenshot\s*\(|page\.(?:locator|evaluate)|browser\.(?:newContext|close)/i,
    );

    const pureContractStart = validator.indexOf('export function assertManualFullWindowContract');
    const pureContractEnd = validator.indexOf(
      '\nexport function validateApprovedProductImage',
      pureContractStart,
    );
    assert.ok(pureContractStart >= 0 && pureContractEnd > pureContractStart);
    const pureContract = validator.slice(pureContractStart, pureContractEnd);
    assert.doesNotMatch(pureContract, /execFileSync|assertCaptureBuildAncestry/);

    const packageJson = source('package.json');
    assert.match(
      packageJson,
      /"demo:validate-images": "tsx scripts\/demo-videos\/validate-manual-product-images\.ts --verify-git-ancestry"/,
    );
    assert.match(
      packageJson,
      /"demo:validate-published-images": "tsx scripts\/demo-videos\/validate-manual-product-images\.ts --published"/,
    );
    assert.match(
      packageJson,
      /"demo:validate-published-ancestry": "tsx scripts\/demo-videos\/validate-manual-product-images\.ts --published --verify-git-ancestry"/,
    );
    assert.match(
      packageJson,
      /"build": "node scripts\/ensure-deps\.mjs && npm run demo:validate-published-images && next build --webpack"/,
    );
    const packageConfig = JSON.parse(packageJson) as { scripts: Record<string, string> };
    assert.doesNotMatch(packageConfig.scripts.build, /git|ancestry|--verify-git-ancestry/);

    const ci = source('.github/workflows/ci.yml');
    assert.match(
      ci,
      /frontend-lint:[\s\S]*?actions\/checkout@v7\s+with:\s+fetch-depth: 0[\s\S]*?npm run demo:validate-published-ancestry[\s\S]*?npm run build/,
    );

    const runbook = source('docs/marketing/demo-video-production-runbook.md');
    assert.match(runbook, /NODE_ENV=production npm run build/);
    assert.match(runbook, /TESTBED_GOOGLE_MAPS_API_KEY=""/);
    assert.match(runbook, /browser zoom.*100%/i);
    assert.match(runbook, /Responsive.*1440(?:×|x)900.*DPR 1/i);
    assert.match(runbook, /Capture screenshot/);
    assert.match(runbook, /not [`*]*Capture full size screenshot/i);
    assert.match(runbook, /original 1440(?:×|x)900 PNG/i);
    assert.match(runbook, /no crop, resize, stitching, scripted navigation, or scripted screenshot/i);
  });
});
