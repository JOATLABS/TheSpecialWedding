import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { describe, it } from 'node:test';

import {
  assembleMaster,
  probeAudioDurationSeconds,
} from '../../scripts/demo-videos/generate-narration';
import { placeNarrationSegments } from '../../scripts/demo-videos/narration-timeline';

function writeToneSegment(filePath: string, durationSeconds: number): void {
  const result = spawnSync(
    'ffmpeg',
    [
      '-y',
      '-v',
      'error',
      '-f',
      'lavfi',
      '-i',
      `sine=frequency=440:duration=${durationSeconds}`,
      '-ar',
      '44100',
      '-ac',
      '1',
      '-c:a',
      'libmp3lame',
      '-b:a',
      '128k',
      filePath,
    ],
    { encoding: 'utf8' },
  );
  assert.equal(result.status, 0, `tone segment synthesis failed: ${result.stderr}`);
}

describe('narration master assembly', () => {
  it('mixes placed segments into a normalized full-length AAC master', () => {
    const workDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'narration-assembly-'));
    try {
      const plans = [
        { index: 0, text: 'first line', scheduledStartSeconds: 0, scheduledEndSeconds: 3 },
        { index: 1, text: 'second line', scheduledStartSeconds: 4, scheduledEndSeconds: 8 },
      ];
      const segmentFiles = plans.map((plan) =>
        path.join(workDirectory, `${plan.index}.mp3`),
      );
      writeToneSegment(segmentFiles[0], 2);
      writeToneSegment(segmentFiles[1], 3);

      const durations = segmentFiles.map((file) => probeAudioDurationSeconds(file));
      const placements = placeNarrationSegments(plans, durations, 10);
      const masterFile = path.join(workDirectory, 'master.m4a');
      assembleMaster(segmentFiles, placements, 10, masterFile);

      assert.ok(fs.existsSync(masterFile), 'master was not written');
      const masterDuration = probeAudioDurationSeconds(masterFile);
      assert.ok(
        Math.abs(masterDuration - 10) < 0.25,
        `master should be padded to the video duration; probed ${masterDuration}s`,
      );
    } finally {
      fs.rmSync(workDirectory, { recursive: true, force: true });
    }
  });

  it('assembles a single-segment master without a mix stage', () => {
    const workDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'narration-assembly-'));
    try {
      const plans = [
        { index: 0, text: 'only line', scheduledStartSeconds: 1, scheduledEndSeconds: 4 },
      ];
      const segmentFile = path.join(workDirectory, '0.mp3');
      writeToneSegment(segmentFile, 2);

      const placements = placeNarrationSegments(plans, [probeAudioDurationSeconds(segmentFile)], 6);
      const masterFile = path.join(workDirectory, 'master.m4a');
      assembleMaster([segmentFile], placements, 6, masterFile);

      const masterDuration = probeAudioDurationSeconds(masterFile);
      assert.ok(Math.abs(masterDuration - 6) < 0.25, `probed ${masterDuration}s`);
    } finally {
      fs.rmSync(workDirectory, { recursive: true, force: true });
    }
  });
});
