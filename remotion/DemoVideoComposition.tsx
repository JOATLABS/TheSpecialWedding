import { Video } from '@remotion/media';
import { AbsoluteFill, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

import type { DemoVideoRemotionProps } from './types';

const WEB_CAPTION_BAND_HEIGHT = 176;

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

          {!isVertical ? (
            <div
              data-caption-band
              style={{
                position: 'absolute',
                left: 0,
                right: 0,
                bottom: 0,
                height: WEB_CAPTION_BAND_HEIGHT,
                borderTop: '1px solid rgba(255,255,255,0.12)',
                backgroundColor: '#020617',
              }}
            />
          ) : null}

          <div
            data-product-window
            style={{
              position: 'absolute',
              top: isVertical ? 174 : 0,
              right: isVertical ? 34 : 0,
              bottom: isVertical ? 250 : WEB_CAPTION_BAND_HEIGHT,
              left: isVertical ? 34 : 0,
              overflow: 'hidden',
              borderRadius: isVertical ? 30 : 0,
              border: isVertical ? '1px solid rgba(255,255,255,0.18)' : 'none',
              boxShadow: isVertical ? '0 30px 90px rgba(0,0,0,0.5)' : 'none',
              backgroundColor: '#071020',
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
        </>
      ) : null}

      <div
        style={{
          position: 'absolute',
          left: isVertical ? 54 : 42,
          top: isVertical ? 70 : undefined,
          bottom: isVertical ? undefined : 66,
          zIndex: 2,
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
            left: isVertical ? captionSafeArea : 320,
            right: captionSafeArea,
            bottom: isVertical ? 86 : 0,
            height: isVertical ? undefined : WEB_CAPTION_BAND_HEIGHT,
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
              borderRadius: isVertical ? 24 : 18,
              backgroundColor: 'rgba(2, 6, 23, 0.82)',
              border: '1px solid rgba(255,255,255,0.12)',
              boxShadow: '0 16px 54px rgba(0,0,0,0.4)',
              padding: isVertical ? '22px 28px' : '14px 22px',
              color: '#f8fafc',
              fontSize: isVertical ? 38 : 32,
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
