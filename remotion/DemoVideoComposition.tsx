import { Video } from '@remotion/media';
import {
  AbsoluteFill,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

import type { DemoVideoRemotionProps } from './types';

function getActiveCaption(props: DemoVideoRemotionProps, frame: number, fps: number): string {
  const timestampMs = (frame / fps) * 1000;
  const activeCaption = props.captions.find(
    (caption) => timestampMs >= caption.startMs && timestampMs <= caption.endMs,
  );

  return activeCaption?.text ?? '';
}

function formatLabel(format: DemoVideoRemotionProps['format']): string {
  return format === 'web-16x9' ? 'Website walkthrough' : 'Social cutdown';
}

export function DemoVideoComposition(props: DemoVideoRemotionProps) {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const activeCaption = getActiveCaption(props, frame, fps);
  const introOpacity = interpolate(frame, [0, fps * 0.5], [0, 1], {
    extrapolateRight: 'clamp',
  });
  const isVertical = props.format === 'social-9x16';
  const safePadding = isVertical ? 54 : 64;
  const headerHeight = isVertical ? 250 : 150;
  const footerHeight = isVertical ? 310 : 185;
  const verticalMediaHeight = 820;

  return (
    <AbsoluteFill style={{ backgroundColor: '#020617', color: 'white', fontFamily: 'Inter, Arial, sans-serif' }}>
      <AbsoluteFill
        style={{
          padding: safePadding,
          display: 'flex',
          flexDirection: 'column',
          gap: isVertical ? 34 : 26,
        }}
      >
        <header
          style={{
            minHeight: headerHeight,
            opacity: introOpacity,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'flex-end',
            gap: 14,
          }}
        >
          <div
            style={{
              color: '#d4a5a5',
              fontSize: isVertical ? 24 : 19,
              fontWeight: 800,
              letterSpacing: 5,
              textTransform: 'uppercase',
            }}
          >
            {formatLabel(props.format)}
          </div>
          <div
            style={{
              fontSize: isVertical ? 62 : 54,
              fontWeight: 850,
              lineHeight: 1,
              maxWidth: isVertical ? 900 : 1300,
            }}
          >
            {props.title}
          </div>
          <div
            style={{
              color: '#cbd5e1',
              fontSize: isVertical ? 26 : 24,
              lineHeight: 1.35,
              maxWidth: isVertical ? 860 : 1240,
            }}
          >
            {props.audience}
          </div>
        </header>

        <main
          style={{
            position: 'relative',
            flex: isVertical ? '0 0 auto' : 1,
            height: isVertical ? verticalMediaHeight : undefined,
            minHeight: 0,
            borderRadius: isVertical ? 34 : 30,
            overflow: 'hidden',
            border: '2px solid rgba(255,255,255,0.12)',
            backgroundColor: '#071020',
            boxShadow: '0 34px 100px rgba(0,0,0,0.44)',
          }}
        >
          {props.rawVideoPath ? (
            <Video
              src={staticFile(props.rawVideoPath)}
              muted
              objectFit="contain"
              style={{
                width: '100%',
                height: '100%',
                backgroundColor: '#071020',
              }}
            />
          ) : (
            <AbsoluteFill
              style={{
                alignItems: 'center',
                justifyContent: 'center',
                color: '#cbd5e1',
                fontSize: 32,
              }}
            >
              Browser recording required
            </AbsoluteFill>
          )}
        </main>

        <footer
          style={{
            minHeight: footerHeight,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div
            style={{
              width: '100%',
              minHeight: isVertical ? 210 : 112,
              borderRadius: isVertical ? 30 : 24,
              background: 'rgba(15, 23, 42, 0.86)',
              border: '1px solid rgba(255,255,255,0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: isVertical ? '36px 42px' : '26px 44px',
              textAlign: 'center',
            }}
          >
            <span
              style={{
                color: '#f8fafc',
                fontSize: isVertical ? 34 : 32,
                lineHeight: 1.25,
                fontWeight: 750,
              }}
            >
              {activeCaption || 'The Special Wedding turns planner work into one calm command center.'}
            </span>
          </div>
        </footer>
      </AbsoluteFill>

      <div
        style={{
          position: 'absolute',
          right: safePadding,
          bottom: safePadding * 0.42,
          color: '#94a3b8',
          fontSize: isVertical ? 22 : 18,
          letterSpacing: 3,
          textTransform: 'uppercase',
        }}
      >
        TheSpecialWedding.io
      </div>

      <div
        style={{
          position: 'absolute',
          left: safePadding,
          bottom: safePadding * 0.42,
          color: '#64748b',
          fontSize: isVertical ? 18 : 15,
          letterSpacing: 2,
          textTransform: 'uppercase',
        }}
      >
        {width}x{height}
      </div>
    </AbsoluteFill>
  );
}
