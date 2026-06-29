import type { Caption } from '@remotion/captions';

import type { DemoVideo } from '../../app/data/demoVideos';

function parseClock(clock: string): number {
  const [minutesPart, secondsPart] = clock.split(':');
  const minutes = Number(minutesPart);
  const seconds = Number(secondsPart);

  if (!Number.isFinite(minutes) || !Number.isFinite(seconds)) {
    throw new Error(`Invalid timestamp clock "${clock}". Expected m:ss.`);
  }

  return (minutes * 60 + seconds) * 1000;
}

function parseTimestampRange(range: string): { startMs: number; endMs: number } {
  const [start, end] = range.split('-');
  if (!start || !end) {
    throw new Error(`Invalid timestamp range "${range}". Expected m:ss-m:ss.`);
  }

  return { startMs: parseClock(start), endMs: parseClock(end) };
}

export function buildCaptionsForDemo(demo: DemoVideo, durationSeconds = demo.durationSeconds): Caption[] {
  const scale = durationSeconds / demo.durationSeconds;

  return demo.script.map((step) => {
    const { startMs, endMs } = parseTimestampRange(step.timestamp);

    return {
      text: step.voiceover,
      startMs: Math.round(startMs * scale),
      endMs: Math.max(Math.round(endMs * scale), Math.round(startMs * scale) + 500),
      timestampMs: null,
      confidence: 1,
    };
  });
}
