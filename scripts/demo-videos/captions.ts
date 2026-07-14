import type { Caption } from '@remotion/captions';

import type { DemoVideo } from '../../app/data/demoVideos';

const SOCIAL_OUTRO_DURATION_SECONDS = 5;

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
  const scale = demo.productionChannel === 'social'
    ? (durationSeconds - SOCIAL_OUTRO_DURATION_SECONDS)
      / (demo.durationSeconds - SOCIAL_OUTRO_DURATION_SECONDS)
    : durationSeconds / demo.durationSeconds;

  if (!Number.isFinite(scale) || scale <= 0) {
    throw new Error(`Invalid caption duration ${durationSeconds} for ${demo.id}.`);
  }

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

function formatWebVttTimestamp(timestampMs: number): string {
  const safeTimestampMs = Math.max(0, Math.round(timestampMs));
  const hours = Math.floor(safeTimestampMs / 3_600_000);
  const minutes = Math.floor((safeTimestampMs % 3_600_000) / 60_000);
  const seconds = Math.floor((safeTimestampMs % 60_000) / 1_000);
  const milliseconds = safeTimestampMs % 1_000;

  return [
    String(hours).padStart(2, '0'),
    String(minutes).padStart(2, '0'),
    `${String(seconds).padStart(2, '0')}.${String(milliseconds).padStart(3, '0')}`,
  ].join(':');
}

export function buildWebVttForDemo(
  demo: DemoVideo,
  durationSeconds = demo.durationSeconds,
): string {
  const cues = buildCaptionsForDemo(demo, durationSeconds).flatMap((caption, index) => [
    String(index + 1),
    `${formatWebVttTimestamp(caption.startMs)} --> ${formatWebVttTimestamp(caption.endMs)}`,
    caption.text.replaceAll('-->', '—>'),
    '',
  ]);

  return `WEBVTT\n\n${cues.join('\n').trimEnd()}\n`;
}
