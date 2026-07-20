'use client';

import React from 'react';

/**
 * BrandLockup — single source of truth for The Special Wedding brand mark.
 *
 * Renders the rings + heart icon, the "THE SPECIAL / Wedding" wordmark, and
 * (optionally) the "a Joatlabs.dev platform" subtext as an inline SVG so
 * gradients and shadows render consistently at any size.
 *
 * Usage:
 *   <BrandLockup variant="full" size="md" surface="dark" />
 *   <BrandLockup variant="mark" size="sm" surface="light" />
 *   <BrandLockup variant="icon" size="xs" />
 *
 * Variants:
 *   - full: icon + wordmark + tagline (marketing nav, hero, login)
 *   - mark: icon + wordmark, no tagline (sidebars, compact spaces)
 *   - icon: rings + heart only (collapsed sidebar, app icons)
 *
 * Sizes are in pixels, applied to the icon's height. Wordmark and tagline
 * scale proportionally.
 */

export type BrandLockupVariant = 'full' | 'mark' | 'icon';
export type BrandLockupSurface = 'dark' | 'light' | 'theme';
export type BrandLockupSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

export interface BrandLockupProps {
  variant?: BrandLockupVariant;
  surface?: BrandLockupSurface;
  size?: BrandLockupSize;
  className?: string;
  /** When true (default for variant=full), the Joatlabs.dev tagline links to https://joatlabs.dev */
  parentLinkHref?: string;
  /** Optional aria-label override; defaults to "The Special Wedding". */
  ariaLabel?: string;
  /** Stable ID prefix for SVG defs to avoid clashes when multiple lockups render on the same page. */
  idPrefix?: string;
}

const SIZE_PX: Record<BrandLockupSize, number> = {
  xs: 24,
  sm: 36,
  md: 56,
  lg: 80,
  xl: 112,
};

interface SurfacePalette {
  ringStops: Array<{ offset: string; color: string }>;
  heartStops: Array<{ offset: string; color: string }>;
  heartOutline: string;
  shadowColor: string;
  wordmarkEyebrow: string;
  wordmarkHeadline: string;
  taglineText: string;
  taglineLink: string;
  taglineUnderline: string;
}

const PALETTES: Record<BrandLockupSurface, SurfacePalette> = {
  dark: {
    ringStops: [
      { offset: '0%', color: '#FFFFFF' },
      { offset: '15%', color: '#FFE5DC' },
      { offset: '40%', color: '#E8B4B8' },
      { offset: '70%', color: '#7A4B50' },
      { offset: '100%', color: '#1F0A0C' },
    ],
    heartStops: [
      { offset: '0%', color: '#FFE5DC' },
      { offset: '50%', color: '#E8B4B8' },
      { offset: '100%', color: '#5C2F34' },
    ],
    heartOutline: '#3D1418',
    shadowColor: 'black',
    wordmarkEyebrow: 'rgba(232, 180, 184, 0.92)',
    wordmarkHeadline: '#E8B4B8',
    taglineText: 'rgba(255, 255, 255, 0.55)',
    taglineLink: 'rgba(255, 255, 255, 0.9)',
    taglineUnderline: 'rgba(255, 255, 255, 0.35)',
  },
  light: {
    ringStops: [
      { offset: '0%', color: '#FFE5DC' },
      { offset: '20%', color: '#E8B4B8' },
      { offset: '50%', color: '#A87278' },
      { offset: '80%', color: '#5C2F34' },
      { offset: '100%', color: '#1F0A0C' },
    ],
    heartStops: [
      { offset: '0%', color: '#E8B4B8' },
      { offset: '50%', color: '#A87278' },
      { offset: '100%', color: '#1F0A0C' },
    ],
    heartOutline: '#1F0A0C',
    shadowColor: 'rgba(60, 15, 18, 0.85)',
    wordmarkEyebrow: '#5C2F34',
    wordmarkHeadline: '#5C2F34',
    taglineText: 'rgba(92, 47, 52, 0.85)',
    taglineLink: '#3D1418',
    taglineUnderline: 'rgba(61, 20, 24, 0.55)',
  },
  theme: {
    ringStops: [
      { offset: '0%', color: 'var(--theme-secondary-light, #ead79b)' },
      { offset: '35%', color: 'var(--theme-secondary, #d4af37)' },
      { offset: '70%', color: 'var(--theme-accent, #c8847e)' },
      { offset: '100%', color: 'var(--theme-primary, #1e3a5f)' },
    ],
    heartStops: [
      { offset: '0%', color: 'var(--theme-accent-light, #e7b9b5)' },
      { offset: '55%', color: 'var(--theme-accent, #c8847e)' },
      { offset: '100%', color: 'var(--theme-primary, #1e3a5f)' },
    ],
    heartOutline: 'var(--theme-primary, #1e3a5f)',
    shadowColor: 'rgba(0, 0, 0, 0.8)',
    wordmarkEyebrow: 'var(--theme-secondary-light, #ead79b)',
    wordmarkHeadline: 'var(--theme-accent-light, #e7b9b5)',
    taglineText: 'rgba(255, 255, 255, 0.55)',
    taglineLink: 'rgba(255, 255, 255, 0.9)',
    taglineUnderline: 'rgba(255, 255, 255, 0.35)',
  },
};

interface IconSvgProps {
  height: number;
  palette: SurfacePalette;
  idPrefix: string;
  ariaLabel: string;
}

function IconSvg({ height, palette, idPrefix, ariaLabel }: IconSvgProps) {
  const ringId = `${idPrefix}-ring`;
  const heartId = `${idPrefix}-heart`;
  const filterId = `${idPrefix}-shadow`;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 60 60"
      role="img"
      aria-label={ariaLabel}
      style={{ height, width: 'auto', flexShrink: 0 }}
    >
      <defs>
        <linearGradient id={ringId} x1="0%" y1="0%" x2="100%" y2="100%">
          {palette.ringStops.map((stop) => (
            <stop key={stop.offset} offset={stop.offset} stopColor={stop.color} />
          ))}
        </linearGradient>
        <radialGradient id={heartId} cx="30%" cy="25%" r="95%">
          {palette.heartStops.map((stop) => (
            <stop key={stop.offset} offset={stop.offset} stopColor={stop.color} />
          ))}
        </radialGradient>
        <filter id={filterId} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur in="SourceAlpha" stdDeviation="1.6" />
          <feOffset dx="0.6" dy="2" result="offset-blur" />
          <feFlood floodColor={palette.shadowColor} floodOpacity="0.75" />
          <feComposite in2="offset-blur" operator="in" />
          <feMerge>
            <feMergeNode />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <circle cx="24" cy="30" r="11" stroke={`url(#${ringId})`} strokeWidth="5.5" fill="none" />
      <circle cx="36" cy="30" r="11" stroke={`url(#${ringId})`} strokeWidth="5.5" fill="none" />
      <path
        d="M 31.07 38.43 A 11 11 0 0 1 28.65 39.97"
        stroke={`url(#${ringId})`}
        strokeWidth="5.5"
        fill="none"
      />
      <g filter={`url(#${filterId})`}>
        <path
          d="M30 27 C28 24, 24 24, 24 27 C24 31, 30 36, 30 36 C30 36, 36 31, 36 27 C36 24, 32 24, 30 27"
          fill={`url(#${heartId})`}
          stroke={palette.heartOutline}
          strokeWidth="0.35"
        />
      </g>
    </svg>
  );
}

export const BrandLockup: React.FC<BrandLockupProps> = ({
  variant = 'full',
  surface = 'dark',
  size = 'md',
  className,
  parentLinkHref = 'https://joatlabs.dev',
  ariaLabel = 'The Special Wedding',
  idPrefix,
}) => {
  const palette = PALETTES[surface];
  const iconHeight = SIZE_PX[size];
  // Wordmark and tagline scale proportionally to icon height. Numbers tuned
  // against the v6 mockup: at icon-height 80 the headline is ~30px.
  const headlineSize = Math.round(iconHeight * 0.375);
  const eyebrowSize = Math.max(9, Math.round(iconHeight * 0.16));
  const taglineSize = Math.max(8, Math.round(iconHeight * 0.125));
  const eyebrowSpacing = Math.max(0.18, Math.min(0.32, iconHeight * 0.0035));
  const headlineSpacing = Math.max(0.04, iconHeight * 0.0008);
  const generatedPrefix = idPrefix ?? `bl-${variant}-${surface}-${size}`;

  if (variant === 'icon') {
    return (
      <span className={className} style={{ display: 'inline-flex', alignItems: 'center' }}>
        <IconSvg
          height={iconHeight}
          palette={palette}
          idPrefix={generatedPrefix}
          ariaLabel={ariaLabel}
        />
      </span>
    );
  }

  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: Math.round(iconHeight * 0.18),
        lineHeight: 1,
      }}
    >
      <IconSvg
        height={iconHeight}
        palette={palette}
        idPrefix={generatedPrefix}
        ariaLabel={ariaLabel}
      />
      <span
        style={{
          display: 'inline-flex',
          flexDirection: 'column',
          lineHeight: 1,
        }}
      >
        <span
          style={{
            fontFamily: "Georgia, 'Times New Roman', serif",
            fontStyle: 'italic',
            fontSize: `${eyebrowSize}px`,
            fontWeight: 400,
            letterSpacing: `${eyebrowSpacing}em`,
            color: palette.wordmarkEyebrow,
            lineHeight: 1,
          }}
        >
          THE SPECIAL
        </span>
        <span
          style={{
            fontFamily: "Georgia, 'Times New Roman', serif",
            fontSize: `${headlineSize}px`,
            fontWeight: 700,
            letterSpacing: `${headlineSpacing}em`,
            color: palette.wordmarkHeadline,
            lineHeight: 0.95,
            marginTop: Math.round(iconHeight * 0.06),
          }}
        >
          Wedding
        </span>
        {variant === 'full' ? (
          <span
            style={{
              fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif",
              fontSize: `${taglineSize}px`,
              fontWeight: 500,
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
              color: palette.taglineText,
              lineHeight: 1,
              marginTop: Math.round(iconHeight * 0.04),
              whiteSpace: 'nowrap',
            }}
          >
            a{' '}
            {/*
              Rendered as a <button> rather than an <a> because BrandLockup is
              commonly wrapped by a parent <Link> (sidebar brand mark, marketing
              nav) — nesting <a> inside <a> is invalid HTML and triggers a React
              hydration error. The button visually matches an underlined link
              and stops propagation so it doesn't trigger the parent navigation.
            */}
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                if (typeof window !== 'undefined') {
                  window.open(parentLinkHref, '_blank', 'noopener,noreferrer');
                }
              }}
              aria-label="Joatlabs.dev (opens in new tab)"
              style={{
                background: 'none',
                border: 0,
                padding: 0,
                margin: 0,
                font: 'inherit',
                letterSpacing: 'inherit',
                textTransform: 'inherit',
                cursor: 'pointer',
                color: palette.taglineLink,
                textDecoration: 'underline',
                textUnderlineOffset: '2px',
                textDecorationColor: palette.taglineUnderline,
              }}
            >
              Joatlabs.dev
            </button>{' '}
            platform
          </span>
        ) : null}
      </span>
    </span>
  );
};

export default BrandLockup;
