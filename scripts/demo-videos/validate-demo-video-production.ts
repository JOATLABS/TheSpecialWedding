import fs from 'node:fs';
import path from 'node:path';

import { DEMO_VIDEO_PRODUCTION_CATALOG } from '../../app/data/demoVideos';
import {
  DEMO_VIDEO_PRODUCTION_REQUIREMENTS,
  getDemoVideoExportTarget,
  getDemoVideoProductionRequirementById,
} from '../../app/data/demoVideoProduction';
import { parseCliArgs, resolveFromRepo } from './cli';
import {
  assertRenderedDurationMatchesManualCapture,
  validateDemoVideoPlaybackApproval,
} from './validate-demo-video-playback-approval';
import { validateManualDemoVideo } from './validate-manual-demo-video';
import { findUnexpectedPublicRenderInputs } from './render-input-safety';

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

  if (requireAssets) {
    for (const artifactPath of findUnexpectedPublicRenderInputs(resolveFromRepo())) {
      issues.push({
        demoId: 'public-render-staging',
        message: `Temporary Remotion input remains under public/: ${artifactPath}.`,
      });
    }
  }

  for (const demoId of demoIds) {
    const demo = DEMO_VIDEO_PRODUCTION_CATALOG.find((item) => item.id === demoId);
    const requirement = getDemoVideoProductionRequirementById(demoId);

    if (!demo) {
      issues.push({ demoId, message: 'Demo id does not exist in DEMO_VIDEO_PRODUCTION_CATALOG.' });
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

    const expectedFormat = requirement.productionChannel === 'social'
      ? 'social-9x16'
      : 'web-16x9';
    const forbiddenFormat = requirement.productionChannel === 'social'
      ? 'web-16x9'
      : 'social-9x16';

    if (!getDemoVideoExportTarget(requirement, expectedFormat)) {
      issues.push({ demoId, message: `Missing ${expectedFormat} export target.` });
    }

    if (getDemoVideoExportTarget(requirement, forbiddenFormat)) {
      issues.push({
        demoId,
        message: `${requirement.productionChannel} production cannot define a ${forbiddenFormat} export target.`,
      });
    }

    if (requirement.exportTargets.length !== 1) {
      issues.push({ demoId, message: 'Exactly one channel-native export target is required.' });
    }

    if (!requireAssets) continue;

    let manualValidation: ReturnType<typeof validateManualDemoVideo> | undefined;
    try {
      manualValidation = validateManualDemoVideo(resolveFromRepo(requirement.captureReceiptPath));
    } catch (error: unknown) {
      issues.push({
        demoId,
        message: `Manual capture receipt/raw recording failed validation: ${error instanceof Error ? error.message : String(error)}`,
      });
    }

    if (
      manualValidation
      && demo.status === 'published'
      && demo.appBuildCommit !== manualValidation.appBuildCommit
    ) {
      issues.push({
        demoId,
        message: 'Publication approval appBuildCommit does not match the validated manual recording.',
      });
    }

    if (!fileExistsAndIsNonempty(resolveFromRepo(requirement.rawRecordingPath))) {
      issues.push({ demoId, message: `Missing raw recording at ${requirement.rawRecordingPath}.` });
    }

    if (!fileExistsAndIsNonempty(resolveFromRepo(requirement.narrationPath))) {
      issues.push({ demoId, message: `Missing narration at ${requirement.narrationPath}.` });
    }

    if (fs.existsSync(resolveFromRepo('public', requirement.renderInputPath))) {
      issues.push({
        demoId,
        message: `Temporary Remotion input remains at public/${requirement.renderInputPath}; raw footage must stay outside public/.`,
      });
    }


    if (fs.existsSync(resolveFromRepo('public', requirement.renderNarrationInputPath))) {
      issues.push({
        demoId,
        message: `Temporary Remotion narration input remains at public/${requirement.renderNarrationInputPath}; narration source must stay outside public/.`,
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

    let playbackValidation: ReturnType<typeof validateDemoVideoPlaybackApproval> | undefined;
    try {
      playbackValidation = validateDemoVideoPlaybackApproval(demoId);
    } catch (error: unknown) {
      issues.push({
        demoId,
        message: `Human playback approval failed validation: ${error instanceof Error ? error.message : String(error)}`,
      });
    }


    if (manualValidation && playbackValidation) {
      try {
        assertRenderedDurationMatchesManualCapture(
          manualValidation.durationSeconds,
          playbackValidation.durationSeconds,
        );
      } catch (error: unknown) {
        issues.push({
          demoId,
          message: error instanceof Error ? error.message : String(error),
        });
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
  const publishedOnly = args.flags.has('published');
  const requireAssets = args.flags.has('require-assets') || publishedOnly;
  const publishedDemoIds = DEMO_VIDEO_PRODUCTION_CATALOG
    .filter((demo) => demo.status === 'published')
    .map((demo) => demo.id);
  const demoIds = demoFilter
    ? [demoFilter]
    : publishedOnly
      ? publishedDemoIds
      : DEMO_VIDEO_PRODUCTION_REQUIREMENTS.map((item) => item.demoId);
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
