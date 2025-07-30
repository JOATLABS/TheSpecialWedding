import { useEffect } from 'react';
import { Wedding } from '@/types/wedding';

export const useTheme = (wedding: Wedding | null) => {
  useEffect(() => {
    if (!wedding?.theme_config) return;

    const theme = wedding.theme_config;
    const root = document.documentElement;

    // Apply CSS custom properties
    root.style.setProperty('--theme-primary', theme.primary_color);
    root.style.setProperty('--theme-secondary', theme.secondary_color);
    root.style.setProperty('--theme-accent', theme.accent_color);
    
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