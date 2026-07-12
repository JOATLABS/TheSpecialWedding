import { Video } from '@remotion/media';
import { AbsoluteFill, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

import type { DemoVideoRemotionProps } from './types';

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
  const captionSafeArea = isVertical ? 118 : 74;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#020617',
        color: 'white',
        fontFamily: 'Inter, Arial, sans-serif',
        overflow: 'hidden',
      }}
    >
      {props.rawVideoPath ? (
        <>
          {isVertical ? (
            <Video
              src={staticFile(props.rawVideoPath)}
              muted
              style={{
                position: 'absolute',
                inset: -48,
                width: 'calc(100% + 96px)',
                height: 'calc(100% + 96px)',
                objectFit: 'cover',
                filter: 'blur(30px) brightness(0.28) saturate(0.8)',
                transform: 'scale(1.08)',
              }}
            />
          ) : null}

          <AbsoluteFill
            style={
              isVertical
                ? {
                    inset: '174px 34px 250px',
                    width: 'auto',
                    height: 'auto',
                    overflow: 'hidden',
                    borderRadius: 30,
                    border: '1px solid rgba(255,255,255,0.18)',
                    boxShadow: '0 30px 90px rgba(0,0,0,0.5)',
                    backgroundColor: '#071020',
                  }
                : undefined
            }
          >
            <Video
              src={staticFile(props.rawVideoPath)}
              muted
              style={{
                width: '100%',
                height: '100%',
                objectFit: isVertical ? 'contain' : 'cover',
                backgroundColor: '#071020',
              }}
            />
          </AbsoluteFill>
        </>
      ) : null}

      <div
        style={{
          position: 'absolute',
          left: isVertical ? 54 : 42,
          top: isVertical ? 70 : 34,
          color: 'rgba(255,255,255,0.88)',
          fontFamily: "Georgia, 'Times New Roman', serif",
          fontSize: isVertical ? 30 : 22,
          fontWeight: 700,
          letterSpacing: 0.8,
          textShadow: '0 2px 16px rgba(0,0,0,0.7)',
        }}
      >
        The Special Wedding
      </div>

      {activeCaption ? (
        <div
          style={{
            position: 'absolute',
            left: captionSafeArea,
            right: captionSafeArea,
            bottom: isVertical ? 86 : 42,
            display: 'flex',
            justifyContent: 'center',
            pointerEvents: 'none',
          }}
        >
          <span
            style={{
              maxWidth: isVertical ? 850 : 1320,
              borderRadius: isVertical ? 24 : 18,
              backgroundColor: 'rgba(2, 6, 23, 0.82)',
              border: '1px solid rgba(255,255,255,0.12)',
              boxShadow: '0 16px 54px rgba(0,0,0,0.4)',
              padding: isVertical ? '22px 28px' : '14px 22px',
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
    </AbsoluteFill>
  );
}
