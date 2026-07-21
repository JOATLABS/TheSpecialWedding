import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { DEMO_VIDEO_PRODUCTION_CATALOG, type DemoVideo } from '../../app/data/demoVideos';
import {
  getDemoVideoById,
  getDemoVideoProductionRequirementById,
  type DemoVideoProductionRequirement,
} from '../../app/data/demoVideoProduction';
import { parseCliArgs, resolveFromRepo, type CliArgs } from './cli';
import {
  placeNarrationSegments,
  planNarrationSegments,
  type PlacedNarrationSegment,
} from './narration-timeline';

// ElevenLabs defaults. Every identifier can be overridden by flag or env so a
// provider-side rename is a configuration change, not a code change.
// - Voice: the founder's cloned narration voice ("Emmanuel Akinwale" in the
//   account's VoiceLab). Override with ELEVENLABS_VOICE_ID or --voice-id;
//   the premade US-female fallback is Rachel, 21m00Tcm4TlvDq8ikWAM.
// - Model: eleven_multilingual_v2 is the stable high-quality tier.
// - Output: mp3_44100_128 is the highest MP3 rate available on the Starter
//   plan; mp3_44100_192 requires Creator or above.
const DEFAULT_VOICE_ID = 'My4OXDyai4TWzZlKmUyw';
const DEFAULT_MODEL_ID = 'eleven_multilingual_v2';
const DEFAULT_OUTPUT_FORMAT = 'mp3_44100_128';
const ELEVENLABS_API_BASE_URL = 'https://api.elevenlabs.io';
const REQUEST_TIMEOUT_MS = 120_000;
const MAX_SYNTHESIS_ATTEMPTS = 4;

// The master matches the runbook's narration normalization contract exactly:
// gentle band-pass around the voice, broadcast loudness, 44.1 kHz AAC at 192k.
const MASTER_AUDIO_FILTER = 'highpass=f=80,lowpass=f=16000,loudnorm=I=-16:TP=-1.5:LRA=11,apad';
const MASTER_SAMPLE_RATE = 44100;
const MASTER_BITRATE = '192k';

export type NarrationVoiceSettings = {
  stability: number;
  similarity_boost: number;
  style: number;
  use_speaker_boost: boolean;
  speed?: number;
};

export type NarrationManifestSegment = {
  index: number;
  text: string;
  textSha256: string;
  characterCount: number;
  scheduledStartSeconds: number;
  scheduledEndSeconds: number;
  placedStartSeconds: number;
  audioDurationSeconds: number;
  placedEndSeconds: number;
};

export type NarrationManifest = {
  schemaVersion: 1;
  demoId: string;
  generatedAt: string;
  generator: 'scripts/demo-videos/generate-narration.ts';
  provider: 'elevenlabs';
  modelId: string;
  voiceId: string;
  outputFormat: string;
  voiceSettings: NarrationVoiceSettings;
  durationSource: 'capture-receipt' | 'authored';
  videoDurationSeconds: number;
  segments: NarrationManifestSegment[];
  totalCharacterCount: number;
  inputsSha256: string;
  masterPath: string;
  masterSha256: string;
  masterDurationSeconds: number;
};

type NarrationConfig = {
  apiKey: string | undefined;
  voiceId: string;
  modelId: string;
  outputFormat: string;
  voiceSettings: NarrationVoiceSettings;
  dryRun: boolean;
  force: boolean;
};

function sha256(value: string | Buffer): string {
  return createHash('sha256').update(value).digest('hex');
}

function narrationManifestPath(requirement: DemoVideoProductionRequirement): string {
  return resolveFromRepo(requirement.narrationPath.replace(/\.m4a$/, '.narration.json'));
}

function readJsonFile(filePath: string): Record<string, unknown> | undefined {
  if (!fs.existsSync(filePath)) return undefined;
  try {
    const parsed: unknown = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    return undefined;
  }
  return undefined;
}

/**
 * Prefer the validated manual take's real duration so voice and captions track
 * the footage. Full receipt validation happens at render time; here we only
 * need its duration, and a missing receipt (a not-yet-captured demo such as a
 * new storefront walkthrough) falls back to the authored duration so narration
 * can be produced before the raw take exists.
 */
function resolveVideoDuration(
  demo: DemoVideo,
  requirement: DemoVideoProductionRequirement,
): { durationSeconds: number; durationSource: NarrationManifest['durationSource'] } {
  const receipt = readJsonFile(resolveFromRepo(requirement.captureReceiptPath));
  const source = receipt?.source;
  if (source && typeof source === 'object' && !Array.isArray(source)) {
    const durationSeconds = (source as Record<string, unknown>).durationSeconds;
    if (typeof durationSeconds === 'number' && Number.isFinite(durationSeconds) && durationSeconds > 0) {
      return { durationSeconds, durationSource: 'capture-receipt' };
    }
  }

  return { durationSeconds: demo.durationSeconds, durationSource: 'authored' };
}

export function probeAudioDurationSeconds(filePath: string): number {
  const result = spawnSync(
    'ffprobe',
    [
      '-v',
      'error',
      '-show_entries',
      'format=duration',
      '-of',
      'default=noprint_wrappers=1:nokey=1',
      filePath,
    ],
    { encoding: 'utf8', maxBuffer: 1024 * 1024 },
  );

  if (result.error) {
    throw new Error(`ffprobe could not inspect ${filePath}: ${result.error.message}`);
  }
  const duration = Number.parseFloat(result.stdout.trim());
  if (result.status !== 0 || !Number.isFinite(duration) || duration <= 0) {
    throw new Error(`ffprobe returned an invalid duration for ${filePath}.`);
  }

  return duration;
}

async function synthesizeSegment(
  config: NarrationConfig,
  text: string,
  previousText: string | undefined,
  nextText: string | undefined,
): Promise<Buffer> {
  const url = `${ELEVENLABS_API_BASE_URL}/v1/text-to-speech/${config.voiceId}`
    + `?output_format=${encodeURIComponent(config.outputFormat)}`;
  const body = JSON.stringify({
    text,
    model_id: config.modelId,
    // Request-stitching context keeps prosody continuous across separately
    // synthesized lines instead of every segment restarting cold.
    ...(previousText ? { previous_text: previousText } : {}),
    ...(nextText ? { next_text: nextText } : {}),
    voice_settings: config.voiceSettings,
  });

  let lastError: Error | undefined;
  for (let attempt = 1; attempt <= MAX_SYNTHESIS_ATTEMPTS; attempt += 1) {
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'xi-api-key': config.apiKey ?? '',
          'content-type': 'application/json',
          accept: 'audio/mpeg',
        },
        body,
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });

      if (response.ok) {
        return Buffer.from(await response.arrayBuffer());
      }

      const detail = (await response.text()).slice(0, 500);
      if (response.status === 401 || response.status === 403) {
        throw new Error(
          `ElevenLabs rejected the API key (${response.status}). Check ELEVEN_LABS_API_KEY `
            + `and that the requested output format/model is available on the account tier. ${detail}`,
        );
      }
      if (response.status === 422 || response.status === 400) {
        throw new Error(`ElevenLabs rejected the request (${response.status}): ${detail}`);
      }

      lastError = new Error(`ElevenLabs request failed (${response.status}): ${detail}`);
    } catch (error: unknown) {
      if (error instanceof Error && /rejected the/.test(error.message)) throw error;
      lastError = error instanceof Error ? error : new Error(String(error));
    }

    if (attempt < MAX_SYNTHESIS_ATTEMPTS) {
      const backoffMs = 2 ** attempt * 1000;
      await new Promise((resolve) => setTimeout(resolve, backoffMs));
    }
  }

  throw lastError ?? new Error('ElevenLabs synthesis failed.');
}

/**
 * Mix the per-line clips at their placed offsets, then master with the
 * runbook's normalization chain and pad with silence to the exact video
 * duration, matching the shape of the previous hand-produced masters.
 */
export function assembleMaster(
  segmentFiles: readonly string[],
  placements: readonly PlacedNarrationSegment[],
  videoDurationSeconds: number,
  masterFile: string,
): void {
  const inputs = segmentFiles.flatMap((file) => ['-i', file]);
  const delayed = placements.map((placement, index) => {
    const delayMs = Math.max(0, Math.round(placement.placedStartSeconds * 1000));
    return `[${index}:a]adelay=${delayMs}:all=1[s${index}]`;
  });
  const mix = placements.length === 1
    ? `[s0]${MASTER_AUDIO_FILTER}[master]`
    : `${placements.map((_, index) => `[s${index}]`).join('')}`
      + `amix=inputs=${placements.length}:duration=longest:normalize=0,${MASTER_AUDIO_FILTER}[master]`;
  const filterGraph = [...delayed, mix].join(';');

  fs.mkdirSync(path.dirname(masterFile), { recursive: true });
  const result = spawnSync(
    'ffmpeg',
    [
      '-y',
      '-v',
      'error',
      ...inputs,
      '-filter_complex',
      filterGraph,
      '-map',
      '[master]',
      '-t',
      videoDurationSeconds.toFixed(3),
      '-ar',
      String(MASTER_SAMPLE_RATE),
      '-ac',
      '1',
      '-c:a',
      'aac',
      '-b:a',
      MASTER_BITRATE,
      masterFile,
    ],
    { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 },
  );

  if (result.error) {
    throw new Error(`ffmpeg could not assemble the narration master: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`ffmpeg failed to assemble the narration master: ${result.stderr}`);
  }
}

function computeInputsSha256(
  demo: DemoVideo,
  config: NarrationConfig,
  videoDurationSeconds: number,
): string {
  return sha256(
    JSON.stringify({
      demoId: demo.id,
      videoDurationSeconds,
      segments: demo.script.map((step) => [step.timestamp, step.voiceover]),
      voiceId: config.voiceId,
      modelId: config.modelId,
      outputFormat: config.outputFormat,
      voiceSettings: config.voiceSettings,
    }),
  );
}

function isManifestCurrent(
  manifestFile: string,
  masterFile: string,
  inputsSha256: string,
): boolean {
  const manifest = readJsonFile(manifestFile);
  if (!manifest || manifest.inputsSha256 !== inputsSha256) return false;
  if (!fs.existsSync(masterFile)) return false;

  return sha256(fs.readFileSync(masterFile)) === manifest.masterSha256;
}

async function generateNarrationForDemo(
  demo: DemoVideo,
  requirement: DemoVideoProductionRequirement,
  config: NarrationConfig,
): Promise<'generated' | 'skipped' | 'planned'> {
  const { durationSeconds, durationSource } = resolveVideoDuration(demo, requirement);
  const plans = planNarrationSegments(demo, durationSeconds);
  if (plans.length === 0) {
    throw new Error(`Demo "${demo.id}" has no voiceover script steps.`);
  }

  const totalCharacterCount = plans.reduce((total, plan) => total + plan.text.length, 0);
  const masterFile = resolveFromRepo(requirement.narrationPath);
  const manifestFile = narrationManifestPath(requirement);
  const inputsSha256 = computeInputsSha256(demo, config, durationSeconds);

  console.log(
    `\n${demo.id}: ${plans.length} lines, ${totalCharacterCount} characters, `
      + `${durationSeconds.toFixed(2)}s video (${durationSource} duration)`,
  );

  if (config.dryRun) {
    for (const plan of plans) {
      console.log(
        `  [${plan.scheduledStartSeconds.toFixed(2)}s-${plan.scheduledEndSeconds.toFixed(2)}s] `
          + `${plan.text.length} chars: ${plan.text}`,
      );
    }
    return 'planned';
  }

  if (!config.force && isManifestCurrent(manifestFile, masterFile, inputsSha256)) {
    console.log('  Narration master is current (script, voice, and settings unchanged); skipping.');
    return 'skipped';
  }

  if (!config.apiKey) {
    throw new Error(
      'Missing ElevenLabs API key. Set ELEVEN_LABS_API_KEY (or ELEVENLABS_API_KEY), or use --dry-run.',
    );
  }

  const segmentsDirectory = resolveFromRepo('output', 'demo-videos', 'narration', '.segments', demo.id);
  fs.rmSync(segmentsDirectory, { recursive: true, force: true });
  fs.mkdirSync(segmentsDirectory, { recursive: true });

  try {
    const segmentFiles: string[] = [];
    const audioDurations: number[] = [];
    for (const plan of plans) {
      console.log(`  Synthesizing line ${plan.index + 1}/${plans.length}…`);
      const audio = await synthesizeSegment(
        config,
        plan.text,
        plans[plan.index - 1]?.text,
        plans[plan.index + 1]?.text,
      );
      const segmentFile = path.join(segmentsDirectory, `${String(plan.index).padStart(2, '0')}.mp3`);
      fs.writeFileSync(segmentFile, audio);
      segmentFiles.push(segmentFile);
      audioDurations.push(probeAudioDurationSeconds(segmentFile));
    }

    const placements = placeNarrationSegments(plans, audioDurations, durationSeconds);
    assembleMaster(segmentFiles, placements, durationSeconds, masterFile);

    const masterDurationSeconds = probeAudioDurationSeconds(masterFile);
    const manifest: NarrationManifest = {
      schemaVersion: 1,
      demoId: demo.id,
      generatedAt: new Date().toISOString(),
      generator: 'scripts/demo-videos/generate-narration.ts',
      provider: 'elevenlabs',
      modelId: config.modelId,
      voiceId: config.voiceId,
      outputFormat: config.outputFormat,
      voiceSettings: config.voiceSettings,
      durationSource,
      videoDurationSeconds: durationSeconds,
      segments: placements.map((placement) => ({
        index: placement.index,
        text: placement.text,
        textSha256: sha256(placement.text),
        characterCount: placement.text.length,
        scheduledStartSeconds: placement.scheduledStartSeconds,
        scheduledEndSeconds: placement.scheduledEndSeconds,
        placedStartSeconds: placement.placedStartSeconds,
        audioDurationSeconds: placement.audioDurationSeconds,
        placedEndSeconds: placement.placedEndSeconds,
      })),
      totalCharacterCount,
      inputsSha256,
      masterPath: requirement.narrationPath,
      masterSha256: sha256(fs.readFileSync(masterFile)),
      masterDurationSeconds,
    };
    fs.writeFileSync(manifestFile, `${JSON.stringify(manifest, null, 2)}\n`);

    console.log(
      `  Wrote ${requirement.narrationPath} (${masterDurationSeconds.toFixed(2)}s master, `
        + `voice ${config.voiceId}, model ${config.modelId}).`,
    );
    return 'generated';
  } finally {
    fs.rmSync(segmentsDirectory, { recursive: true, force: true });
  }
}

function parseOptionalNumber(args: CliArgs, key: string, fallback: number): number {
  const value = args.values.get(key);
  if (value === undefined) return fallback;

  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(`--${key} must be a number.`);
  }
  return parsed;
}

function resolveTargetDemos(args: CliArgs): DemoVideo[] {
  const requested = args.repeatedValues.get('demo') ?? [];
  if (args.flags.has('all-published')) {
    if (requested.length > 0) {
      throw new Error('Use either --all-published or repeated --demo values, not both.');
    }
    return DEMO_VIDEO_PRODUCTION_CATALOG.filter((demo) => demo.status === 'published');
  }

  if (requested.length === 0) {
    throw new Error(
      'Pass --demo <id> (repeatable), --all-published, or --list-published. '
        + 'Run with --list-published to see regenerable demo ids.',
    );
  }

  return requested.map((demoId) => {
    const demo = getDemoVideoById(demoId);
    if (!demo) {
      throw new Error(`Unknown demo "${demoId}".`);
    }
    return demo;
  });
}

async function main(): Promise<void> {
  const args = parseCliArgs(process.argv.slice(2));

  if (args.flags.has('list-published')) {
    for (const demo of DEMO_VIDEO_PRODUCTION_CATALOG) {
      if (demo.status === 'published') console.log(demo.id);
    }
    return;
  }

  const speed = args.values.has('speed')
    ? parseOptionalNumber(args, 'speed', 1)
    : process.env.ELEVENLABS_SPEED
      ? Number(process.env.ELEVENLABS_SPEED)
      : undefined;
  if (speed !== undefined && (!Number.isFinite(speed) || speed < 0.7 || speed > 1.2)) {
    throw new Error('--speed must be between 0.7 and 1.2.');
  }

  const config: NarrationConfig = {
    apiKey: process.env.ELEVEN_LABS_API_KEY || process.env.ELEVENLABS_API_KEY,
    voiceId: args.values.get('voice-id') || process.env.ELEVENLABS_VOICE_ID || DEFAULT_VOICE_ID,
    modelId: args.values.get('model') || process.env.ELEVENLABS_MODEL_ID || DEFAULT_MODEL_ID,
    outputFormat:
      args.values.get('output-format') || process.env.ELEVENLABS_OUTPUT_FORMAT || DEFAULT_OUTPUT_FORMAT,
    voiceSettings: {
      stability: parseOptionalNumber(args, 'stability', 0.5),
      similarity_boost: parseOptionalNumber(args, 'similarity-boost', 0.75),
      style: parseOptionalNumber(args, 'style', 0),
      use_speaker_boost: true,
      ...(speed !== undefined ? { speed } : {}),
    },
    dryRun: args.flags.has('dry-run'),
    force: args.flags.has('force'),
  };

  const demos = resolveTargetDemos(args);
  console.log(
    `Narration voice ${config.voiceId}, model ${config.modelId}, format ${config.outputFormat}`
      + `${config.dryRun ? ' (dry run)' : ''}.`,
  );

  const counts = { generated: 0, skipped: 0, planned: 0 };
  for (const demo of demos) {
    const requirement = getDemoVideoProductionRequirementById(demo.id);
    if (!requirement) {
      throw new Error(`Demo "${demo.id}" has no production requirement.`);
    }
    counts[await generateNarrationForDemo(demo, requirement, config)] += 1;
  }

  console.log(
    `\nDone: ${counts.generated} generated, ${counts.skipped} already current`
      + `${config.dryRun ? `, ${counts.planned} planned (dry run)` : ''}.`,
  );
  if (counts.generated > 0) {
    console.log(
      'Next: re-render each regenerated demo with `npm run demo:render -- --demo <id>`, watch the '
        + 'exports, then refresh the human playback approvals with `npm run demo:approve-playback`.',
    );
  }
}

const isMainModule = process.argv[1]
  ? path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url))
  : false;

if (isMainModule) {
  main().catch((error: unknown) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  });
}
