"use client";

import React from 'react';
import { ThemeConfig } from '@/types/wedding';

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  depth?: 'near' | 'mid' | 'far';
  blur?: 'sm' | 'md' | 'lg' | 'xl';
  theme?: ThemeConfig;
}

export const GlassCard: React.FC<GlassCardProps> = ({
  children,
  className = '',
  depth = 'mid',
  blur = 'lg',
  theme
}) => {
  const depthStyles: Record<NonNullable<GlassCardProps['depth']>, {
    shadow: string;
    scale: string;
    blur: string;
    bg: string;
    zIndex: string;
  }> = {
    near: {
      shadow: 'shadow-2xl dark:shadow-[0_25px_50px_-12px_rgba(0,0,0,0.5)]',
      scale: 'scale-[1.02]',
      blur: 'backdrop-blur-xl',
      bg: 'bg-white/40 dark:bg-gray-900/60',
      zIndex: 'z-30'
    },
    mid: {
      shadow: 'shadow-xl dark:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.4)]',
      scale: 'scale-100',
      blur: 'backdrop-blur-lg',
      bg: 'bg-white/30 dark:bg-gray-900/50',
      zIndex: 'z-20'
    },
    far: {
      shadow: 'shadow-lg dark:shadow-[0_15px_30px_-12px_rgba(0,0,0,0.3)]',
      scale: 'scale-[0.98]',
      blur: 'backdrop-blur-md',
      bg: 'bg-white/20 dark:bg-gray-900/40',
      zIndex: 'z-10'
    }
  };

  const blurMap: Record<NonNullable<GlassCardProps['blur']>, string> = {
    sm: 'backdrop-blur-sm',
    md: 'backdrop-blur-md',
    lg: 'backdrop-blur-lg',
    xl: 'backdrop-blur-xl'
  };

  const resolvedDepth = depthStyles[depth] ?? depthStyles.mid;
  const resolvedBlur = blurMap[blur] ?? blurMap.lg;

  const primary = theme?.primary_color?.trim();
  const secondary = theme?.secondary_color?.trim();
  const themedGradient =
    primary && secondary
      ? `linear-gradient(to right, ${primary}0D, ${secondary}0D)`
      : 'linear-gradient(to right, rgba(200, 132, 126, 0.05), rgba(212, 175, 55, 0.05))';

  return (
    <div
      className={`
        relative
        ${resolvedDepth.bg}
        ${resolvedDepth.shadow}
        ${resolvedDepth.scale}
        ${resolvedDepth.zIndex}
        ${resolvedBlur}
        border border-white/20 dark:border-white/10
        rounded-2xl
        overflow-hidden
        transition-all duration-500
        hover:scale-[1.02]
        hover:shadow-2xl
        group
        ${className}
      `}
    >
      <div className="absolute inset-0 bg-gradient-to-tr from-white/10 dark:from-white/5 via-transparent to-transparent pointer-events-none" />

      <div className="relative z-10">
        {children}
      </div>

      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
        <div
          className="absolute inset-0"
          style={{
            background: themedGradient
          }}
        />
      </div>
    </div>
  );
};
