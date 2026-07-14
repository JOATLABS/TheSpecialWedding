import { Audio, Video } from '@remotion/media';
import {
  AbsoluteFill,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

import type { DemoVideoRemotionProps } from './types';

const OUTRO_DURATION_SECONDS = 5;

function getActiveCaption(props: DemoVideoRemotionProps, frame: number, fps: number): string {
  const timestampMs = (frame / fps) * 1000;
  const activeCaption = props.captions.find(
    (caption) => timestampMs >= caption.startMs && timestampMs <= caption.endMs,
  );

  return activeCaption?.text ?? '';
}

export function DemoVideoComposition(props: DemoVideoRemotionProps) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const activeCaption = getActiveCaption(props, frame, fps);
  const isVertical = props.format === 'social-9x16';
  const captionSafeArea = isVertical ? 66 : 220;
  const outroStartFrame = Math.max(0, Math.ceil((props.durationSeconds - OUTRO_DURATION_SECONDS) * fps));
  const outroOpacity = interpolate(
    frame,
    [outroStartFrame, outroStartFrame + Math.max(1, Math.round(fps * 0.4))],
    [0, 1],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  );

  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#020617',
        color: 'white',
        fontFamily: 'Inter, Arial, sans-serif',
        overflow: 'hidden',
      }}
    >
      {props.narrationPath ? <Audio src={staticFile(props.narrationPath)} /> : null}

      {props.rawVideoPath ? (
        <div
          data-product-window
          style={{
            position: 'absolute',
            inset: isVertical ? '220px 0 1025px' : 0,
            overflow: 'hidden',
            borderTop: isVertical ? '1px solid rgba(255,255,255,0.16)' : 'none',
            borderBottom: isVertical ? '1px solid rgba(255,255,255,0.16)' : 'none',
            backgroundColor: '#071020',
            opacity: 1 - outroOpacity * 0.68,
          }}
        >
          <Video
            src={staticFile(props.rawVideoPath)}
            muted
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'contain',
              backgroundColor: '#071020',
            }}
          />
        </div>
      ) : null}

      <div
        style={{
          position: 'absolute',
          left: isVertical ? 54 : 32,
          top: isVertical ? 62 : 30,
          zIndex: 2,
          color: 'rgba(255,255,255,0.88)',
          fontFamily: "Georgia, 'Times New Roman', serif",
          fontSize: isVertical ? 30 : 20,
          fontWeight: 700,
          letterSpacing: 0.8,
          textShadow: '0 2px 16px rgba(0,0,0,0.7)',
        }}
      >
        The Special Wedding
      </div>

      {isVertical ? (
        <div
          style={{
            position: 'absolute',
            top: 116,
            left: 54,
            right: 54,
            zIndex: 2,
            color: '#f8fafc',
            fontSize: 42,
            fontWeight: 720,
            lineHeight: 1.08,
          }}
        >
          {props.title}
        </div>
      ) : null}

      {activeCaption && outroOpacity < 0.98 ? (
        <div
          style={{
            position: 'absolute',
            left: captionSafeArea,
            right: captionSafeArea,
            bottom: isVertical ? 132 : 48,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: 'none',
            zIndex: 2,
          }}
        >
          <span
            style={{
              maxWidth: isVertical ? 850 : 1320,
              borderRadius: isVertical ? 22 : 16,
              backgroundColor: 'rgba(2, 6, 23, 0.88)',
              border: '1px solid rgba(255,255,255,0.12)',
              boxShadow: '0 16px 54px rgba(0,0,0,0.4)',
              padding: isVertical ? '22px 28px' : '12px 20px',
              color: '#f8fafc',
              fontSize: isVertical ? 38 : 28,
              fontWeight: 650,
              lineHeight: 1.24,
              textAlign: 'center',
            }}
          >
            {activeCaption}
          </span>
        </div>
      ) : null}

      <AbsoluteFill
        data-demo-outro
        style={{
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(135deg, rgba(2,6,23,0.98), rgba(30,41,59,0.97))',
          opacity: outroOpacity,
          pointerEvents: 'none',
          textAlign: 'center',
          zIndex: 4,
        }}
      >
        <div
          style={{
            color: '#c7d2fe',
            fontSize: isVertical ? 28 : 24,
            fontWeight: 700,
            letterSpacing: 2.4,
            textTransform: 'uppercase',
          }}
        >
          The Special Wedding
        </div>
        <div
          style={{
            marginTop: isVertical ? 30 : 20,
            maxWidth: isVertical ? 900 : 1380,
            color: '#ffffff',
            fontFamily: "Georgia, 'Times New Roman', serif",
            fontSize: isVertical ? 72 : 78,
            fontWeight: 700,
            lineHeight: 1.04,
          }}
        >
          One planner-owned workspace.
        </div>
        <div
          style={{
            marginTop: isVertical ? 30 : 24,
            color: '#e2e8f0',
            fontSize: isVertical ? 44 : 38,
            fontWeight: 560,
          }}
        >
          Start with one wedding.
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}
