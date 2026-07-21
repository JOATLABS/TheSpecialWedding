import { Audio, Video } from '@remotion/media';
import {
  AbsoluteFill,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

import { musicVolumeAtSeconds } from './musicDucking';
import type { DemoVideoRemotionProps } from './types';

const OUTRO_DURATION_SECONDS = 5;

export function DemoVideoComposition(props: DemoVideoRemotionProps) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const isVertical = props.format === 'social-9x16';

  if (isVertical && (!props.phaseOnePillar?.trim() || !props.socialOutcome?.trim())) {
    throw new Error('Social video renders require phaseOnePillar and socialOutcome.');
  }

  const outroStartFrame = Math.max(0, Math.ceil((props.durationSeconds - OUTRO_DURATION_SECONDS) * fps));
  const outroTransitionFrames = Math.max(2, Math.round(fps * 0.4));
  const outroContentStartFrame = outroStartFrame + Math.ceil(outroTransitionFrames / 2);
  const outroEndFrame = outroStartFrame + outroTransitionFrames;
  const outroBackdropOpacity = interpolate(
    frame,
    [outroStartFrame, outroContentStartFrame],
    [0, 1],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  );
  const outroContentOpacity = interpolate(
    frame,
    [outroContentStartFrame, outroEndFrame],
    [0, 1],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  );
  const storyOpacity = 1 - outroBackdropOpacity;
  const outroBrandFontSize = isVertical ? 32 : 36;
  const outroHeadlineFontSize = isVertical ? 84 : 96;
  const outroSupportingFontSize = 44;

  const productVideo = props.rawVideoPath ? (
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
  ) : null;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#020617',
        color: 'white',
        fontFamily: 'Arial, sans-serif',
        overflow: 'hidden',
      }}
    >
      {props.narrationPath ? <Audio src={staticFile(props.narrationPath)} /> : null}

      {props.musicPath ? (
        <Audio
          src={staticFile(props.musicPath)}
          loop
          // Computed from the composition frame, not a volume callback: with
          // `loop` the callback frame restarts every loop iteration, while
          // ducking windows are absolute video timestamps.
          volume={musicVolumeAtSeconds(frame / fps, props.narrationWindows ?? [])}
        />
      ) : null}

      {isVertical ? (
        <div
          data-social-story
          style={{
            position: 'absolute',
            inset: 0,
            zIndex: 2,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            gap: 44,
            padding: '100px 80px 140px',
            background:
              'radial-gradient(circle at 90% 8%, rgba(99,102,241,0.22), transparent 30%), linear-gradient(180deg, #071020 0%, #0f172a 58%, #111827 100%)',
            opacity: storyOpacity,
          }}
        >
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 22,
              minHeight: 400,
            }}
          >
            <div
              style={{
                color: 'rgba(255,255,255,0.9)',
                fontFamily: "Georgia, 'Times New Roman', serif",
                fontSize: 32,
                fontWeight: 700,
                letterSpacing: 0.8,
              }}
            >
              The Special Wedding
            </div>
            <div
              data-social-pillar
              style={{
                alignSelf: 'flex-start',
                border: '1px solid rgba(199,210,254,0.5)',
                borderRadius: 999,
                color: '#c7d2fe',
                fontSize: 32,
                fontWeight: 750,
                letterSpacing: 1.5,
                padding: '12px 22px',
                textTransform: 'uppercase',
              }}
            >
              {props.phaseOnePillar}
            </div>
            <div
              style={{
                color: '#f8fafc',
                fontFamily: "Georgia, 'Times New Roman', serif",
                fontSize: 84,
                fontWeight: 700,
                lineHeight: 1.02,
                letterSpacing: -1.5,
              }}
            >
              {props.title}
            </div>
          </div>

          {productVideo ? (
            <div
              data-product-window
              data-social-product-window
              style={{
                aspectRatio: '16 / 10',
                backgroundColor: '#071020',
                border: '2px solid rgba(255,255,255,0.22)',
                borderRadius: 24,
                boxShadow: '0 30px 80px rgba(0,0,0,0.48)',
                boxSizing: 'border-box',
                flexShrink: 0,
                overflow: 'hidden',
                width: '100%',
              }}
            >
              {productVideo}
            </div>
          ) : null}

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 26,
            }}
          >
            <div
              data-social-outcome
              style={{
                color: '#e2e8f0',
                fontSize: 44,
                fontWeight: 560,
                lineHeight: 1.2,
              }}
            >
              {props.socialOutcome}
            </div>
            <div
              style={{
                color: '#a5b4fc',
                fontSize: 32,
                fontWeight: 700,
              }}
            >
              Built for the people running the wedding.
            </div>
          </div>
        </div>
      ) : productVideo ? (
        <div
          data-product-window
          data-web-product-window
          style={{
            position: 'absolute',
            inset: 0,
            overflow: 'hidden',
            backgroundColor: '#071020',
            opacity: storyOpacity,
          }}
        >
          {productVideo}
        </div>
      ) : null}

      <AbsoluteFill
        data-demo-outro
        style={{
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(135deg, rgba(2,6,23,0.98), rgba(30,41,59,0.97))',
          opacity: outroBackdropOpacity,
          pointerEvents: 'none',
          textAlign: 'center',
          zIndex: 4,
        }}
      >
        <div
          data-demo-outro-content
          style={{
            alignItems: 'center',
            display: 'flex',
            flexDirection: 'column',
            opacity: outroContentOpacity,
          }}
        >
          <div
            style={{
              color: '#c7d2fe',
              fontSize: outroBrandFontSize,
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
              fontSize: outroHeadlineFontSize,
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
              fontSize: outroSupportingFontSize,
              fontWeight: 560,
            }}
          >
            Start with one wedding.
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
}
