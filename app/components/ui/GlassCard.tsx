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
  // Depth-based styling - More transparent
  const depthStyles = {
    near: {
      shadow: 'shadow-2xl',
      scale: 'scale-[1.02]',
      blur: 'backdrop-blur-xl',
      bg: 'bg-white/40',  // Reduced from 80% to 40%
      zIndex: 'z-30'
    },
    mid: {
      shadow: 'shadow-xl',
      scale: 'scale-100',
      blur: 'backdrop-blur-lg',
      bg: 'bg-white/30',  // Reduced from 70% to 30%
      zIndex: 'z-20'
    },
    far: {
      shadow: 'shadow-lg',
      scale: 'scale-[0.98]',
      blur: 'backdrop-blur-md',
      bg: 'bg-white/20',  // Reduced from 60% to 20%
      zIndex: 'z-10'
    }
  };

  const blurMap = {
    sm: 'backdrop-blur-sm',
    md: 'backdrop-blur-md',
    lg: 'backdrop-blur-lg',
    xl: 'backdrop-blur-xl'
  };

  const style = depthStyles[depth];

  return (
    <div 
      className={`
        relative
        ${style.bg}
        ${style.shadow}
        ${style.scale}
        ${style.zIndex}
        ${blurMap[blur]}
        border border-white/20
        rounded-2xl
        overflow-hidden
        transition-all duration-500
        hover:scale-[1.02]
        hover:shadow-2xl
        group
        ${className}
      `}
    >
      {/* Glass shine effect */}
      <div className="absolute inset-0 bg-gradient-to-tr from-white/10 via-transparent to-transparent pointer-events-none" />
      
      {/* Content */}
      <div className="relative z-10">
        {children}
      </div>
      
      {/* Hover glow with theme colors */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
        <div 
          className="absolute inset-0"
          style={{
            background: theme 
              ? `linear-gradient(to right, ${theme.primary_color}0D, ${theme.secondary_color}0D)`
              : 'linear-gradient(to right, rgba(200, 132, 126, 0.05), rgba(212, 175, 55, 0.05))'
          }}
        />
      </div>
    </div>
  );
};