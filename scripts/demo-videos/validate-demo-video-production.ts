import fs from 'node:fs';
import path from 'node:path';

import { DEMO_VIDEO_PLAYLIST } from '../../app/data/demoVideos';
import {
  DEMO_VIDEO_PRODUCTION_REQUIREMENTS,
  getDemoVideoExportTarget,
  getDemoVideoProductionRequirementById,
} from '../../app/data/demoVideoProduction';
import { parseCliArgs, resolveFromRepo } from './cli';
import { validateManualDemoVideo } from './validate-manual-demo-video';

type ValidationIssue = {
  demoId: string;
  message: string;
};

function publicAssetExists(assetPath: string): boolean {
  const withoutLeadingSlash = assetPath.replace(/^\//, '');
  return fileExistsAndIsNonempty(resolveFromRepo('public', withoutLeadingSlash));
}

function staticAssetExists(assetPath: string): boolean {
  return fileExistsAndIsNonempty(resolveFromRepo('public', assetPath));
}

function fileExistsAndIsNonempty(filePath: string): boolean {
  return fs.existsSync(filePath) && fs.statSync(filePath).isFile() && fs.statSync(filePath).size > 0;
}

function validateRequirementInventory(demoIds: readonly string[], requireAssets: boolean): ValidationIssue[] {
  const issues: ValidationIssue[] = [];

  for (const demoId of demoIds) {
    const demo = DEMO_VIDEO_PLAYLIST.find((item) => item.id === demoId);
    const requirement = getDemoVideoProductionRequirementById(demoId);

    if (!demo) {
      issues.push({ demoId, message: 'Demo id does not exist in DEMO_VIDEO_PLAYLIST.' });
      continue;
    }

    if (!requirement) {
      issues.push({ demoId, message: 'Production requirement is missing.' });
      continue;
    }

    if (requirement.captureSurfaces.length === 0) {
      issues.push({ demoId, message: 'At least one capture surface is required.' });
    }

    if (requirement.sideEffectGuards.length === 0) {
      issues.push({ demoId, message: 'At least one side-effect/session guard is required.' });
    }

    for (const format of ['web-16x9', 'social-9x16'] as const) {
      const target = getDemoVideoExportTarget(requirement, format);
      if (!target) {
        issues.push({ demoId, message: `Missing ${format} export target.` });
      }
    }

    if (!requireAssets) continue;

    try {
      validateManualDemoVideo(resolveFromRepo(requirement.captureReceiptPath));
    } catch (error: unknown) {
      issues.push({
        demoId,
        message: `Manual capture receipt/raw recording failed validation: ${error instanceof Error ? error.message : String(error)}`,
      });
    }

    if (!fileExistsAndIsNonempty(resolveFromRepo(requirement.rawRecordingPath))) {
      issues.push({ demoId, message: `Missing raw recording at ${requirement.rawRecordingPath}.` });
    }

    if (fs.existsSync(resolveFromRepo('public', requirement.renderInputPath))) {
      issues.push({
        demoId,
        message: `Temporary Remotion input remains at public/${requirement.renderInputPath}; raw footage must stay outside public/.`,
      });
    }

    if (!staticAssetExists(requirement.captionPath)) {
      issues.push({ demoId, message: `Missing captions at public/${requirement.captionPath}.` });
    }

    if (!staticAssetExists(requirement.transcriptPath)) {
      issues.push({ demoId, message: `Missing transcript at public/${requirement.transcriptPath}.` });
    }

    for (const target of requirement.exportTargets) {
      if (!publicAssetExists(target.assetPath)) {
        issues.push({ demoId, message: `Missing rendered video at ${target.assetPath}.` });
      }

      if (!publicAssetExists(target.thumbnailPath)) {
        issues.push({ demoId, message: `Missing thumbnail at ${target.thumbnailPath}.` });
      }
    }
  }

  return issues;
}

function summarize(demoIds: readonly string[], requireAssets: boolean): void {
  for (const demoId of demoIds) {
    const requirement = getDemoVideoProductionRequirementById(demoId);
    if (!requirement) continue;

    const params = requirement.routeParameters.length ? requirement.routeParameters.join(', ') : 'none';
    const targets = requirement.exportTargets.map((target) => `${target.format}:${path.basename(target.assetPath)}`).join(', ');

    console.log(
      `${demoId}: surfaces=${requirement.captureSurfaces.join(', ')} params=${params} targets=${targets}`,
    );
  }

  console.log(
    `Checked ${demoIds.length} demo video${demoIds.length === 1 ? '' : 's'} (${requireAssets ? 'requirements + assets' : 'requirements only'}).`,
  );
}

function main(): void {
  const args = parseCliArgs(process.argv.slice(2));
  const demoFilter = args.values.get('demo');
  const requireAssets = args.flags.has('require-assets');
  const demoIds = demoFilter ? [demoFilter] : DEMO_VIDEO_PRODUCTION_REQUIREMENTS.map((item) => item.demoId);
  const issues = validateRequirementInventory(demoIds, requireAssets);

  summarize(demoIds, requireAssets);

  if (issues.length > 0) {
    console.error('\nDemo video production validation failed:');
    for (const issue of issues) {
      console.error(`- ${issue.demoId}: ${issue.message}`);
    }
    process.exitCode = 1;
    return;
  }

  console.log('Demo video production validation passed.');
}

main();
