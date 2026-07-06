import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

import { DEMO_VIDEO_PLAYLIST, type DemoVideo } from '../../app/data/demoVideos';
import { getDemoVideoProductionRequirementById } from '../../app/data/demoVideoProduction';
import { parseCliArgs, resolveFromRepo } from './cli';
import { assertPublicSafeStorageState } from './public-safe-storage';

type CaptureFixtures = {
  primaryWeddingId: string;
  primarySlug: string;
  guestMemoriesUploadToken: string;
  formId: string;
  coupleFormId: string;
  vendorProfileId: string;
  vendorContractId: string;
  vendorContractToken: string;
  vendorPortalToken: string;
};

type ReceiptEntry = {
  demoId: string;
  recordStatus: number | null;
  render16x9Status: number | null;
  render9x16Status: number | null;
};

function readFixtures(filePath: string): CaptureFixtures {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Capture fixtures file does not exist: ${filePath}. Run npm run demo:seed first.`);
  }
  return JSON.parse(fs.readFileSync(filePath, 'utf8')) as CaptureFixtures;
}

function routeParamsForDemo(demoId: string, fixtures: CaptureFixtures): Record<string, string> {
  const common = {
    id: fixtures.primaryWeddingId,
    weddingId: fixtures.primaryWeddingId,
    slug: fixtures.primarySlug,
    uploadToken: fixtures.guestMemoriesUploadToken,
    token: fixtures.vendorPortalToken,
    formId: fixtures.coupleFormId,
  };

  if (demoId === 'forms-canvas-demo') {
    return { ...common, id: fixtures.formId, formId: fixtures.coupleFormId };
  }

  if (demoId === 'contract-sign-pay-demo') {
    return {
      ...common,
      id: fixtures.vendorContractId,
      token: fixtures.vendorContractToken,
      vendorProfileId: fixtures.vendorProfileId,
    };
  }

  return common;
}

function run(command: string, args: readonly string[]): number | null {
  console.log(`\n$ ${command} ${args.join(' ')}`);
  const result = spawnSync(command, args, {
    cwd: resolveFromRepo(),
    stdio: 'inherit',
    env: process.env,
  });

  if (result.error) {
    console.error(result.error.message);
    return null;
  }

  return result.status;
}

function targetFilesExist(demo: DemoVideo): boolean {
  const requirement = getDemoVideoProductionRequirementById(demo.id);
  if (!requirement) return false;

  const files = [
    requirement.rawRecordingPath,
    requirement.captionPath,
    requirement.transcriptPath,
    ...requirement.exportTargets.flatMap((target) => [
      target.assetPath.replace(/^\//, ''),
      target.thumbnailPath.replace(/^\//, ''),
    ]),
  ];

  return files.every((filePath) => fs.existsSync(resolveFromRepo('public', filePath)));
}

function main(): void {
  const args = parseCliArgs(process.argv.slice(2));
  const baseUrl = args.values.get('base-url') ?? 'http://localhost:3100';
  const storageState = args.values.get('storage-state') ?? resolveFromRepo('output', 'demo-videos', 'state', 'demo-public-safe.json');
  const fixturesPath = args.values.get('fixtures') ?? resolveFromRepo('output', 'demo-videos', 'capture-fixtures.json');
  const receiptPath = args.values.get('receipt') ?? resolveFromRepo('output', 'demo-videos', 'capture-receipt.json');
  const demoFilters = args.repeatedValues.get('demo');
  const skipExisting = args.flags.has('skip-existing');
  const fixtures = readFixtures(fixturesPath);
  if (!args.flags.has('allow-personal-state')) {
    assertPublicSafeStorageState(storageState);
  }
  const demos = demoFilters?.length
    ? DEMO_VIDEO_PLAYLIST.filter((demo) => demoFilters.includes(demo.id))
    : [...DEMO_VIDEO_PLAYLIST];

  if (demos.length === 0) {
    throw new Error(`No demos matched filters: ${demoFilters?.join(', ')}`);
  }

  const receipts: ReceiptEntry[] = [];
  for (const demo of demos) {
    if (skipExisting && targetFilesExist(demo)) {
      console.log(`Skipping ${demo.id}; all target files already exist.`);
      receipts.push({
        demoId: demo.id,
        recordStatus: 0,
        render16x9Status: 0,
        render9x16Status: 0,
      });
      continue;
    }

    const routeParams = routeParamsForDemo(demo.id, fixtures);
    const routeArgs = Object.entries(routeParams).flatMap(([key, value]) => ['--route-param', `${key}=${value}`]);
    const recordStatus = run('npx', [
      'tsx',
      'scripts/demo-videos/record-demo-video.ts',
      '--demo',
      demo.id,
      '--base-url',
      baseUrl,
      '--storage-state',
      storageState,
      '--route-plan',
      '--allow-side-effect-fixtures',
      ...routeArgs,
    ]);

    let render16x9Status: number | null = null;
    let render9x16Status: number | null = null;
    if (recordStatus === 0) {
      render16x9Status = run('npx', [
        'tsx',
        'scripts/demo-videos/render-demo-video.ts',
        '--demo',
        demo.id,
        '--format',
        'web-16x9',
      ]);
      render9x16Status = run('npx', [
        'tsx',
        'scripts/demo-videos/render-demo-video.ts',
        '--demo',
        demo.id,
        '--format',
        'social-9x16',
      ]);
    }

    receipts.push({
      demoId: demo.id,
      recordStatus,
      render16x9Status,
      render9x16Status,
    });
  }

  fs.mkdirSync(path.dirname(receiptPath), { recursive: true });
  fs.writeFileSync(receiptPath, `${JSON.stringify({ generatedAt: new Date().toISOString(), receipts }, null, 2)}\n`);

  const failed = receipts.filter(
    (entry) => entry.recordStatus !== 0 || entry.render16x9Status !== 0 || entry.render9x16Status !== 0,
  );
  if (failed.length > 0) {
    console.error(`\n${failed.length} demo capture(s) failed. Receipt: ${receiptPath}`);
    process.exitCode = 1;
    return;
  }

  console.log(`\nAll demo captures completed. Receipt: ${receiptPath}`);
}

main();
