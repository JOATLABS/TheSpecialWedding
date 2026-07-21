import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { resolveFromRepo } from './cli';

/**
 * Deterministic Afrobeat-flavored elevator bed for the demo videos.
 *
 * The track is synthesized from code (no samples, no third-party audio), so
 * the repo owns the license outright and the exact same bytes can be
 * regenerated from this script. The musical goal is an unobtrusive groove:
 * laid-back Afrobeats drum pattern, log-drum bassline, muted guitar plucks,
 * and a warm pad, mastered quiet so narration always sits on top.
 */

const SAMPLE_RATE = 44100;
const BPM = 102;
const BARS = 8;
const STEPS_PER_BAR = 16;
const SECONDS_PER_STEP = 60 / BPM / 4;
const LOOP_SECONDS = BARS * STEPS_PER_BAR * SECONDS_PER_STEP;
const SWING = 0.012;

const OUTPUT_RELATIVE_PATH = 'public/demo-videos/music/afrobeat-elevator-bed.m4a';
const MANIFEST_RELATIVE_PATH = 'public/demo-videos/music/afrobeat-elevator-bed.json';

// A pentatonic minor palette keeps every overlap consonant.
const NOTE = {
  A1: 55.0,
  C2: 65.41,
  D2: 73.42,
  E2: 82.41,
  G2: 98.0,
  A2: 110.0,
  C3: 130.81,
  D3: 146.83,
  E3: 164.81,
  G3: 196.0,
  A3: 220.0,
  C4: 261.63,
  D4: 293.66,
  E4: 329.63,
  G4: 392.0,
  A4: 440.0,
} as const;

function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

type Stereo = { left: Float64Array; right: Float64Array };

function createBuffer(seconds: number): Stereo {
  const length = Math.round(seconds * SAMPLE_RATE);
  return { left: new Float64Array(length), right: new Float64Array(length) };
}

/** Adds a rendered voice into the loop buffer, wrapping tails around the loop
 * boundary so the bed loops seamlessly. */
function mixIn(target: Stereo, samples: Float64Array, startSeconds: number, pan: number, gain: number): void {
  const start = Math.round(startSeconds * SAMPLE_RATE);
  const leftGain = gain * Math.SQRT1_2 * (1 - pan);
  const rightGain = gain * Math.SQRT1_2 * (1 + pan);
  const length = target.left.length;
  for (let i = 0; i < samples.length; i += 1) {
    const at = (start + i) % length;
    target.left[at] += samples[i] * leftGain;
    target.right[at] += samples[i] * rightGain;
  }
}

function envelope(i: number, total: number, attack: number, release: number): number {
  const t = i / SAMPLE_RATE;
  const remaining = (total - i) / SAMPLE_RATE;
  const a = attack > 0 ? Math.min(1, t / attack) : 1;
  const r = release > 0 ? Math.min(1, remaining / release) : 1;
  return a * r;
}

function kick(): Float64Array {
  const duration = 0.28;
  const out = new Float64Array(Math.round(duration * SAMPLE_RATE));
  for (let i = 0; i < out.length; i += 1) {
    const t = i / SAMPLE_RATE;
    const freq = 42 + 78 * Math.exp(-t * 26);
    const body = Math.sin(2 * Math.PI * freq * t) * Math.exp(-t * 13);
    out[i] = Math.tanh(body * 1.8) * envelope(i, out.length, 0.001, 0.05);
  }
  return out;
}

function rim(random: () => number): Float64Array {
  const duration = 0.06;
  const out = new Float64Array(Math.round(duration * SAMPLE_RATE));
  for (let i = 0; i < out.length; i += 1) {
    const t = i / SAMPLE_RATE;
    const click = Math.sin(2 * Math.PI * 1720 * t) + 0.5 * Math.sin(2 * Math.PI * 2450 * t);
    out[i] = (click * 0.7 + (random() * 2 - 1) * 0.3) * Math.exp(-t * 90);
  }
  return out;
}

function shaker(random: () => number, accent: boolean): Float64Array {
  const duration = accent ? 0.09 : 0.055;
  const out = new Float64Array(Math.round(duration * SAMPLE_RATE));
  let highpassState = 0;
  for (let i = 0; i < out.length; i += 1) {
    const white = random() * 2 - 1;
    highpassState = 0.86 * highpassState + white - (out[i - 1] ?? 0) * 0;
    const hissy = white - highpassState * 0.55;
    out[i] = hissy * envelope(i, out.length, 0.004, 0.03) * (accent ? 1 : 0.62);
  }
  return out;
}

/** The rounded, gliding bass hit that anchors the Afrobeats/Amapiano feel. */
function logDrum(frequency: number, durationSeconds: number): Float64Array {
  const out = new Float64Array(Math.round(durationSeconds * SAMPLE_RATE));
  for (let i = 0; i < out.length; i += 1) {
    const t = i / SAMPLE_RATE;
    const glide = frequency * (1 + 0.5 * Math.exp(-t * 30));
    const body = Math.sin(2 * Math.PI * glide * t) + 0.18 * Math.sin(2 * Math.PI * glide * 2 * t);
    out[i] = Math.tanh(body * 1.5) * envelope(i, out.length, 0.004, 0.1) * Math.exp(-t * 3.2);
  }
  return out;
}

/** Karplus–Strong pluck through a soft lowpass: a muted rhythm-guitar chirp. */
function pluck(frequency: number, durationSeconds: number, random: () => number): Float64Array {
  const out = new Float64Array(Math.round(durationSeconds * SAMPLE_RATE));
  const period = Math.max(2, Math.round(SAMPLE_RATE / frequency));
  const delay = new Float64Array(period);
  for (let i = 0; i < period; i += 1) delay[i] = random() * 2 - 1;
  let index = 0;
  let lowpass = 0;
  for (let i = 0; i < out.length; i += 1) {
    const next = (index + 1) % period;
    delay[index] = (delay[index] + delay[next]) * 0.4985;
    lowpass = lowpass * 0.35 + delay[index] * 0.65;
    out[i] = lowpass * envelope(i, out.length, 0.002, 0.05);
    index = next;
  }
  return out;
}

function pad(frequencies: readonly number[], durationSeconds: number): Float64Array {
  const out = new Float64Array(Math.round(durationSeconds * SAMPLE_RATE));
  for (let i = 0; i < out.length; i += 1) {
    const t = i / SAMPLE_RATE;
    let sample = 0;
    for (const frequency of frequencies) {
      sample += Math.sin(2 * Math.PI * frequency * t + 0.6 * Math.sin(2 * Math.PI * 0.13 * t));
      sample += 0.5 * Math.sin(2 * Math.PI * frequency * 1.005 * t);
    }
    const breathe = 0.75 + 0.25 * Math.sin(2 * Math.PI * t / durationSeconds);
    out[i] = (sample / (frequencies.length * 1.5)) * envelope(i, out.length, 1.2, 1.6) * breathe;
  }
  return out;
}

function stepTime(bar: number, step: number): number {
  const swing = step % 2 === 1 ? SWING : 0;
  return bar * STEPS_PER_BAR * SECONDS_PER_STEP + step * SECONDS_PER_STEP + swing;
}

function renderLoop(): Stereo {
  const random = mulberry32(0x5eed_a11);
  const loop = createBuffer(LOOP_SECONDS);

  const kickSample = kick();
  const kickSteps = [0, 6, 10];
  const rimSteps = [4, 12];
  const ghostRimSteps = [7, 15];

  // Two-bar log-drum bass phrase, answered in the second half of the loop.
  const bassPhraseA: ReadonlyArray<readonly [number, number]> = [
    [0, NOTE.A1], [3, NOTE.A2], [6, NOTE.G2], [10, NOTE.E2], [14, NOTE.C2],
    [16, NOTE.A1], [22, NOTE.D2], [26, NOTE.E2], [30, NOTE.G2],
  ];
  const bassPhraseB: ReadonlyArray<readonly [number, number]> = [
    [0, NOTE.A1], [3, NOTE.A2], [6, NOTE.G2], [10, NOTE.E2], [14, NOTE.D2],
    [16, NOTE.C2], [22, NOTE.E2], [26, NOTE.D2], [29, NOTE.C2], [30, NOTE.A1],
  ];

  // Sparse muted-guitar answers on the offbeats.
  const guitarPhrase: ReadonlyArray<readonly [number, number]> = [
    [2, NOTE.E3], [5, NOTE.G3], [13, NOTE.A3],
    [18, NOTE.C4], [21, NOTE.A3], [29, NOTE.G3],
    [34, NOTE.E3], [37, NOTE.G3], [45, NOTE.D4],
    [50, NOTE.C4], [53, NOTE.E4], [61, NOTE.A3],
  ];

  for (let bar = 0; bar < BARS; bar += 1) {
    for (const step of kickSteps) {
      mixIn(loop, kickSample, stepTime(bar, step), 0, 0.8);
    }
    if (bar % 2 === 1) {
      mixIn(loop, kickSample, stepTime(bar, 14), 0, 0.55);
    }
    for (const step of rimSteps) {
      mixIn(loop, rim(random), stepTime(bar, step), 0.22, 0.5);
    }
    for (const step of ghostRimSteps) {
      if (random() < 0.6) mixIn(loop, rim(random), stepTime(bar, step), -0.18, 0.2);
    }
    for (let step = 0; step < STEPS_PER_BAR; step += 2) {
      const accent = step % 4 === 2;
      mixIn(loop, shaker(random, accent), stepTime(bar, step), -0.3, 0.3 + random() * 0.05);
    }
  }

  for (let half = 0; half < 2; half += 1) {
    const phrase = half === 0 ? bassPhraseA : bassPhraseB;
    for (let repeat = 0; repeat < 2; repeat += 1) {
      const barOffset = half * 4 + repeat * 2;
      for (const [step, frequency] of phrase) {
        mixIn(loop, logDrum(frequency, 0.42), stepTime(barOffset, step), 0, 0.85);
      }
    }
  }

  for (let half = 0; half < 2; half += 1) {
    for (const [step, frequency] of guitarPhrase) {
      mixIn(loop, pluck(frequency, 0.5, random), stepTime(half * 4, step), 0.35, 0.4);
    }
  }

  const padBarSeconds = 4 * STEPS_PER_BAR * SECONDS_PER_STEP;
  mixIn(loop, pad([NOTE.A2, NOTE.C3, NOTE.E3, NOTE.G3], padBarSeconds), 0, -0.1, 0.16);
  mixIn(loop, pad([NOTE.G2, NOTE.C3, NOTE.D3, NOTE.A3], padBarSeconds), padBarSeconds, 0.1, 0.16);

  return loop;
}

function writeWav(filePath: string, loop: Stereo): void {
  const frames = loop.left.length;
  const dataBytes = frames * 2 * 2;
  const buffer = Buffer.alloc(44 + dataBytes);
  buffer.write('RIFF', 0);
  buffer.writeUInt32LE(36 + dataBytes, 4);
  buffer.write('WAVE', 8);
  buffer.write('fmt ', 12);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(2, 22);
  buffer.writeUInt32LE(SAMPLE_RATE, 24);
  buffer.writeUInt32LE(SAMPLE_RATE * 4, 28);
  buffer.writeUInt16LE(4, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write('data', 36);
  buffer.writeUInt32LE(dataBytes, 40);
  for (let i = 0; i < frames; i += 1) {
    const left = Math.max(-1, Math.min(1, loop.left[i]));
    const right = Math.max(-1, Math.min(1, loop.right[i]));
    buffer.writeInt16LE(Math.round(left * 32767), 44 + i * 4);
    buffer.writeInt16LE(Math.round(right * 32767), 44 + i * 4 + 2);
  }
  fs.writeFileSync(filePath, buffer);
}

export function generateMusicBed(repoRootOverride?: string): { outputPath: string; loopSeconds: number } {
  const resolve = (relative: string) =>
    repoRootOverride ? path.resolve(repoRootOverride, relative) : resolveFromRepo(relative);
  const loop = renderLoop();

  const outputFile = resolve(OUTPUT_RELATIVE_PATH);
  fs.mkdirSync(path.dirname(outputFile), { recursive: true });
  const wavFile = `${outputFile}.tmp.wav`;
  writeWav(wavFile, loop);

  try {
    // Gentle glue and a quiet master target: the bed should always need the
    // composition to lift it, never fight the narration.
    const result = spawnSync(
      'ffmpeg',
      [
        '-y',
        '-v',
        'error',
        '-i',
        wavFile,
        '-af',
        'highpass=f=34,lowpass=f=11000,loudnorm=I=-20:TP=-2.0:LRA=7',
        '-ar',
        String(SAMPLE_RATE),
        '-c:a',
        'aac',
        '-b:a',
        '160k',
        outputFile,
      ],
      { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 },
    );
    if (result.error || result.status !== 0) {
      throw new Error(`ffmpeg failed to master the music bed: ${result.error?.message ?? result.stderr}`);
    }
  } finally {
    fs.rmSync(wavFile, { force: true });
  }

  const manifest = {
    schemaVersion: 1,
    generator: 'scripts/demo-videos/generate-music-bed.ts',
    style: 'afrobeat-elevator',
    bpm: BPM,
    bars: BARS,
    loopSeconds: Number(LOOP_SECONDS.toFixed(3)),
    sampleRate: SAMPLE_RATE,
    masteredLoudnessLufs: -20,
    license: 'Synthesized from code in this repository; no third-party audio.',
    outputSha256: createHash('sha256').update(fs.readFileSync(outputFile)).digest('hex'),
  };
  fs.writeFileSync(resolve(MANIFEST_RELATIVE_PATH), `${JSON.stringify(manifest, null, 2)}\n`);

  return { outputPath: outputFile, loopSeconds: LOOP_SECONDS };
}

const isMainModule = process.argv[1]
  ? path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url))
  : false;

if (isMainModule) {
  try {
    const { outputPath, loopSeconds } = generateMusicBed();
    console.log(`Wrote ${outputPath} (${loopSeconds.toFixed(2)}s seamless loop).`);
  } catch (error: unknown) {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  }
}
