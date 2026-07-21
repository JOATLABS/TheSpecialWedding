import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  buildDemoVideoTranscript,
  getDemoVideoById,
  getDemoVideoProductionRequirementById,
  resolveDemoVideoRenderTarget,
  type DemoVideoExportFormat,
} from '../../app/data/demoVideoProduction';
import type { NarrationWindow } from '../../remotion/musicDucking';
import type { DemoVideoRemotionProps } from '../../remotion/types';
import { buildWebVttForDemo } from './captions';
import { getNumberValue, getRequiredValue, parseCliArgs, resolveFromRepo } from './cli';
import { validateManualDemoVideo } from './validate-manual-demo-video';

const MUSIC_BED_STATIC_PATH = 'demo-videos/music/afrobeat-elevator-bed.m4a';

/**
 * Ducking follows the synthesized speech recorded in the narration provenance
 * manifest. A human-recorded master has no manifest, so the bed plays at a
 * constant low level in that case (no windows).
 */
function readNarrationWindows(narrationPath: string): NarrationWindow[] {
  const manifestFile = resolveFromRepo(narrationPath.replace(/\.m4a$/, '.narration.json'));
  if (!fs.existsSync(manifestFile)) return [];

  try {
    const parsed: unknown = JSON.parse(fs.readFileSync(manifestFile, 'utf8'));
    const segments = (parsed as { segments?: unknown }).segments;
    if (!Array.isArray(segments)) return [];

    return segments.flatMap((segment) => {
      const start = (segment as { placedStartSeconds?: unknown }).placedStartSeconds;
      const end = (segment as { placedEndSeconds?: unknown }).placedEndSeconds;
      if (typeof start !== 'number' || typeof end !== 'number' || end <= start) return [];
      return [{ startSeconds: start, endSeconds: end }];
    });
  } catch {
    return [];
  }
}

function runRemotion(args: readonly string[]): void {
  const result = spawnSync('npx', ['remotion', ...args], {
    cwd: resolveFromRepo(),
    encoding: 'utf8',
    env: process.env,
  });

  if (result.error) throw result.error;
  if (result.status !== 0) {
    if (result.stdout) console.error(result.stdout);
    if (result.stderr) console.error(result.stderr);
    throw new Error(`Remotion command failed: remotion ${args.join(' ')}`);
  }
}

function assertFileExists(filePath: string, label: string): void {
  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    throw new Error(`${label} does not exist: ${filePath}`);
  }
  if (fs.statSync(filePath).size === 0) {
    throw new Error(`${label} is empty: ${filePath}`);
  }
}

function assertRenderedAudioStream(filePath: string): void {
  const result = spawnSync(
    'ffprobe',
    [
      '-v',
      'error',
      '-select_streams',
      'a:0',
      '-show_entries',
      'stream=codec_type',
      '-of',
      'default=noprint_wrappers=1:nokey=1',
      filePath,
    ],
    { encoding: 'utf8', maxBuffer: 1024 * 1024 },
  );

  if (result.error || result.status !== 0 || result.stdout.trim() !== 'audio') {
    throw new Error('Rendered walkthrough does not contain an audio stream.');
  }
}

function writeJson(filePath: string, value: unknown): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`);
}

export function withTemporaryRenderInput<T>(
  rawRecordingFile: string,
  stagedRecordingFile: string,
  render: () => T,
): T {
  fs.mkdirSync(path.dirname(stagedRecordingFile), { recursive: true });
  fs.rmSync(stagedRecordingFile, { force: true });

  try {
    fs.copyFileSync(rawRecordingFile, stagedRecordingFile);
    return render();
  } finally {
    fs.rmSync(stagedRecordingFile, { force: true });
  }
}

function main(): void {
  const args = parseCliArgs(process.argv.slice(2));
  const demoId = getRequiredValue(args, 'demo');
  const requestedFormat = args.values.get('format') as DemoVideoExportFormat | undefined;
  const demo = getDemoVideoById(demoId);
  const requirement = getDemoVideoProductionRequirementById(demoId);

  if (!demo || !requirement) {
    throw new Error(`Unknown demo "${demoId}".`);
  }
  if (args.values.has('raw') || args.values.has('duration-seconds')) {
    throw new Error('Manual demo renders do not accept --raw or --duration-seconds overrides.');
  }

  const target = resolveDemoVideoRenderTarget(requirement, requestedFormat);
  const format = target.format;

  const receiptPath = args.values.get('receipt')
    ? path.resolve(args.values.get('receipt')!)
    : resolveFromRepo(requirement.captureReceiptPath);
  // Published demos tolerate in-flight regenerated demo artifacts (a narration
  // or render refresh touches several tracked outputs before one publication
  // commit); everything outside those generated paths must still be clean.
  const validation = validateManualDemoVideo(receiptPath, {
    allowStagedPublicationChanges: demo.status === 'published',
  });
  if (validation.demoId !== demoId) {
    throw new Error(`Receipt ${receiptPath} belongs to ${validation.demoId}, not ${demoId}.`);
  }

  const durationSeconds = validation.durationSeconds;
  const timeoutMs = getNumberValue(args, 'timeout-ms', 120000);
  const durationFrames = Math.max(30, Math.ceil(durationSeconds * target.fps));
  const thumbnailFrame = Math.min(
    durationFrames - 1,
    Math.floor(getNumberValue(args, 'thumbnail-frame', Math.max(90, Math.floor(durationFrames * 0.6)))),
  );

  const rawRecordingFile = resolveFromRepo(requirement.rawRecordingPath);
  const narrationFile = resolveFromRepo(requirement.narrationPath);
  const stagedRecordingFile = resolveFromRepo('public', requirement.renderInputPath);
  const stagedNarrationFile = resolveFromRepo('public', requirement.renderNarrationInputPath);
  assertFileExists(rawRecordingFile, 'Validated manual recording');
  assertFileExists(narrationFile, 'Approved narration');

  const webVtt = buildWebVttForDemo(demo, durationSeconds);
  const captionFile = resolveFromRepo('public', requirement.captionPath);
  const transcriptFile = resolveFromRepo('public', requirement.transcriptPath);
  const outputFile = resolveFromRepo('public', target.assetPath.replace(/^\//, ''));
  const thumbnailFile = resolveFromRepo('public', target.thumbnailPath.replace(/^\//, ''));
  const propsFile = resolveFromRepo('output', 'demo-videos', 'props', `${demoId}-${format}.json`);

  const musicFile = resolveFromRepo('public', MUSIC_BED_STATIC_PATH);
  const useMusic = !args.flags.has('no-music') && fs.existsSync(musicFile);

  const props: DemoVideoRemotionProps = {
    demoId,
    title: demo.title,
    audience: demo.audience,
    rawVideoPath: requirement.renderInputPath,
    narrationPath: requirement.renderNarrationInputPath,
    ...(useMusic
      ? {
          musicPath: MUSIC_BED_STATIC_PATH,
          narrationWindows: readNarrationWindows(requirement.narrationPath),
        }
      : {}),
    format,
    durationSeconds,
    phaseOnePillar: demo.phaseOnePillar,
    socialOutcome: demo.socialOutcome,
  };

  fs.mkdirSync(path.dirname(captionFile), { recursive: true });
  fs.writeFileSync(captionFile, webVtt);
  fs.mkdirSync(path.dirname(transcriptFile), { recursive: true });
  fs.writeFileSync(transcriptFile, buildDemoVideoTranscript(demo));
  writeJson(propsFile, props);
  fs.mkdirSync(path.dirname(outputFile), { recursive: true });
  fs.mkdirSync(path.dirname(thumbnailFile), { recursive: true });
  fs.rmSync(outputFile, { force: true });
  fs.rmSync(thumbnailFile, { force: true });

  withTemporaryRenderInput(rawRecordingFile, stagedRecordingFile, () => {
    withTemporaryRenderInput(narrationFile, stagedNarrationFile, () => {
      console.log(
        `Rendering ${demoId} ${format} from validated ${validation.artifactPath} (${durationSeconds.toFixed(2)}s)`,
      );
      runRemotion([
        'render',
        'remotion/index.ts',
        target.compositionId,
        outputFile,
        `--props=${propsFile}`,
        `--timeout=${timeoutMs}`,
      ]);
      runRemotion([
        'still',
        'remotion/index.ts',
        target.compositionId,
        thumbnailFile,
        `--props=${propsFile}`,
        `--frame=${thumbnailFrame}`,
        `--timeout=${timeoutMs}`,
      ]);
    });
  });

  assertFileExists(outputFile, 'Rendered MP4');
  assertRenderedAudioStream(outputFile);
  assertFileExists(thumbnailFile, 'Rendered thumbnail');
  assertFileExists(captionFile, 'WebVTT captions');
  assertFileExists(transcriptFile, 'Transcript');

  console.log(`Rendered video: ${target.assetPath}`);
  console.log(`Rendered thumbnail: ${target.thumbnailPath}`);
  console.log(`Captions: /${requirement.captionPath}`);
  console.log(`Transcript: /${requirement.transcriptPath}`);
}

const isMainModule = process.argv[1]
  ? path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url))
  : false;

if (isMainModule) {
  try {
    main();
  } catch (error: unknown) {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  }
}
