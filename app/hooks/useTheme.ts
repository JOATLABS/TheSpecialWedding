import { useEffect } from 'react';
import { Wedding } from '@/types/wedding';

/**
 * Lighten a hex color for readability on dark backgrounds.
 * percent: 0 = no change, 1 = white
 */
function lightenHex(hex: string, percent: number): string {
  const h = hex.replace('#', '');
  const num = parseInt(h, 16);
  const r = Math.min(255, Math.floor((num >> 16) + (255 - (num >> 16)) * percent));
  const g = Math.min(255, Math.floor(((num >> 8) & 0xff) + (255 - ((num >> 8) & 0xff)) * percent));
  const b = Math.min(255, Math.floor((num & 0xff) + (255 - (num & 0xff)) * percent));
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
}

export const useTheme = (wedding: Wedding | null) => {
  useEffect(() => {
    if (!wedding?.theme_config) return;

    const theme = wedding.theme_config;
    const root = document.documentElement;

    // Apply CSS custom properties (light mode originals)
    root.style.setProperty('--theme-primary', theme.primary_color);
    root.style.setProperty('--theme-secondary', theme.secondary_color);
    root.style.setProperty('--theme-accent', theme.accent_color);

    // Compute lightened variants for dark mode readability
    root.style.setProperty('--theme-primary-light', lightenHex(theme.primary_color, 0.6));
    root.style.setProperty('--theme-secondary-light', lightenHex(theme.secondary_color, 0.5));
    root.style.setProperty('--theme-accent-light', lightenHex(theme.accent_color, 0.45));

    // Apply font style
    switch (theme.font_style) {
      case 'elegant':
        root.style.setProperty('--theme-font-heading', 'Playfair Display, Georgia, serif');
        root.style.setProperty('--theme-font-body', 'Lora, Georgia, serif');
        break;
      case 'modern':
        root.style.setProperty('--theme-font-heading', 'Inter, Helvetica, sans-serif');
        root.style.setProperty('--theme-font-body', 'Inter, Helvetica, sans-serif');
        break;
      case 'classic':
        root.style.setProperty('--theme-font-heading', 'Times New Roman, serif');
        root.style.setProperty('--theme-font-body', 'Georgia, serif');
        break;
      case 'playful':
        root.style.setProperty('--theme-font-heading', 'Pacifico, cursive');
        root.style.setProperty('--theme-font-body', 'Open Sans, sans-serif');
        break;
    }

    // Clean up on unmount
    return () => {
      root.style.removeProperty('--theme-primary');
      root.style.removeProperty('--theme-secondary');
      root.style.removeProperty('--theme-accent');
      root.style.removeProperty('--theme-primary-light');
      root.style.removeProperty('--theme-secondary-light');
      root.style.removeProperty('--theme-accent-light');
      root.style.removeProperty('--theme-font-heading');
      root.style.removeProperty('--theme-font-body');
    };
  }, [wedding?.theme_config]);

  // Return theme utilities
  return {
    getPrimaryColor: () => wedding?.theme_config?.primary_color || '#1e3a5f',
    getSecondaryColor: () => wedding?.theme_config?.secondary_color || '#d4af37',
    getAccentColor: () => wedding?.theme_config?.accent_color || '#c8847e',
    getBackgroundStyle: () => wedding?.theme_config?.background_style || 'gradient',
    getFontStyle: () => wedding?.theme_config?.font_style || 'elegant',
    getBackgroundGradient: () => {
      if (!wedding?.theme_config || wedding.theme_config.background_style !== 'gradient') {
        return 'from-wedding-ivory to-rose-50';
      }
      // Return empty string to use inline styles instead
      return '';
    }
  };
};