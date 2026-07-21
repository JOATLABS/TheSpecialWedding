import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { describe, it } from 'node:test';

import {
  MUSIC_BED_BASE_VOLUME,
  MUSIC_BED_DUCKED_VOLUME,
  MUSIC_DUCK_LEAD_SECONDS,
  MUSIC_DUCK_RAMP_SECONDS,
  musicVolumeAtSeconds,
} from '../../remotion/musicDucking';
import { generateMusicBed } from '../../scripts/demo-videos/generate-music-bed';

const WINDOWS = [
  { startSeconds: 10, endSeconds: 16 },
  { startSeconds: 30, endSeconds: 33 },
];

describe('music bed ducking', () => {
  it('plays at the base level away from narration and ducks during it', () => {
    assert.equal(musicVolumeAtSeconds(2, WINDOWS), MUSIC_BED_BASE_VOLUME);
    assert.equal(musicVolumeAtSeconds(13, WINDOWS), MUSIC_BED_DUCKED_VOLUME);
    assert.equal(musicVolumeAtSeconds(31, WINDOWS), MUSIC_BED_DUCKED_VOLUME);
    assert.equal(musicVolumeAtSeconds(50, WINDOWS), MUSIC_BED_BASE_VOLUME);
  });

  it('is fully ducked slightly before a line starts, not just at onset', () => {
    assert.equal(
      musicVolumeAtSeconds(10 - MUSIC_DUCK_LEAD_SECONDS, WINDOWS),
      MUSIC_BED_DUCKED_VOLUME,
    );
  });

  it('ramps monotonically into and out of a window', () => {
    const approachStart = 10 - MUSIC_DUCK_LEAD_SECONDS - MUSIC_DUCK_RAMP_SECONDS;
    let previous = musicVolumeAtSeconds(approachStart, WINDOWS);
    assert.ok(Math.abs(previous - MUSIC_BED_BASE_VOLUME) < 1e-6);
    for (let step = 1; step <= 10; step += 1) {
      const value = musicVolumeAtSeconds(
        approachStart + (MUSIC_DUCK_RAMP_SECONDS * step) / 10,
        WINDOWS,
      );
      assert.ok(value <= previous + 1e-9, 'volume must not rise while approaching a line');
      previous = value;
    }
    assert.ok(Math.abs(previous - MUSIC_BED_DUCKED_VOLUME) < 1e-6);

    const releaseStart = 16 + MUSIC_DUCK_LEAD_SECONDS;
    previous = musicVolumeAtSeconds(releaseStart, WINDOWS);
    for (let step = 1; step <= 10; step += 1) {
      const value = musicVolumeAtSeconds(
        releaseStart + (MUSIC_DUCK_RAMP_SECONDS * step) / 10,
        WINDOWS,
      );
      assert.ok(value >= previous - 1e-9, 'volume must not dip while releasing after a line');
      previous = value;
    }
    assert.ok(Math.abs(previous - MUSIC_BED_BASE_VOLUME) < 1e-6);
  });

  it('stays at the base level with no narration windows', () => {
    assert.equal(musicVolumeAtSeconds(12, []), MUSIC_BED_BASE_VOLUME);
  });

  it('ignores malformed windows instead of muting the bed', () => {
    assert.equal(
      musicVolumeAtSeconds(5, [{ startSeconds: 9, endSeconds: 4 }]),
      MUSIC_BED_BASE_VOLUME,
    );
  });
});

describe('music bed generator', () => {
  it('renders a seamless continuous loop with the documented shape', () => {
    const workDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'music-bed-'));
    try {
      const { outputPath, loopSeconds } = generateMusicBed(workDirectory);
      assert.ok(fs.existsSync(outputPath));
      assert.ok(loopSeconds > 15 && loopSeconds < 25, `unexpected loop length ${loopSeconds}`);

      const probe = spawnSync(
        'ffprobe',
        [
          '-v',
          'error',
          '-show_entries',
          'stream=sample_rate,channels:format=duration',
          '-of',
          'default=noprint_wrappers=1',
          outputPath,
        ],
        { encoding: 'utf8' },
      );
      assert.equal(probe.status, 0, probe.stderr);
      assert.match(probe.stdout, /sample_rate=44100/);
      assert.match(probe.stdout, /channels=2/);

      const silences = spawnSync(
        'ffmpeg',
        ['-hide_banner', '-i', outputPath, '-af', 'silencedetect=noise=-45dB:d=0.8', '-f', 'null', '-'],
        { encoding: 'utf8' },
      );
      assert.doesNotMatch(
        `${silences.stderr}`,
        /silence_start/,
        'the bed must be a continuous groove with no dead air',
      );

      const manifestFile = path.join(
        workDirectory,
        'public/demo-videos/music/afrobeat-elevator-bed.json',
      );
      const manifest = JSON.parse(fs.readFileSync(manifestFile, 'utf8')) as {
        style: string;
        license: string;
      };
      assert.equal(manifest.style, 'afrobeat-elevator');
      assert.match(manifest.license, /no third-party audio/i);
    } finally {
      fs.rmSync(workDirectory, { recursive: true, force: true });
    }
  });
});
