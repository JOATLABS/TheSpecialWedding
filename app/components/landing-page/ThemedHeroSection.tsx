'use client';

import React from "react";
import { Wedding } from "@/types/wedding";
import { GlassCard } from "@/components/ui/GlassCard";
import { formatDate } from '@/utils/dateFormat';

interface ThemedHeroSectionProps {
  wedding: Wedding;
}

// Helper to lighten a hex color for dark mode
function lightenColor(hex: string, percent: number): string {
  const num = parseInt(hex.replace('#', ''), 16);
  const r = Math.min(255, Math.floor((num >> 16) + (255 - (num >> 16)) * percent));
  const g = Math.min(255, Math.floor(((num >> 8) & 0x00FF) + (255 - ((num >> 8) & 0x00FF)) * percent));
  const b = Math.min(255, Math.floor((num & 0x0000FF) + (255 - (num & 0x0000FF)) * percent));
  return `#${(r << 16 | g << 8 | b).toString(16).padStart(6, '0')}`;
}

export const ThemedHeroSection: React.FC<ThemedHeroSectionProps> = ({ wedding }) => {
  const theme = wedding.theme_config;

  const primaryColor = theme?.primary_color || '#1e3a5f';
  const secondaryColor = theme?.secondary_color || '#d4af37';
  const accentColor = theme?.accent_color || '#c8847e';

  // Lighter versions for dark mode
  const lightPrimary = lightenColor(primaryColor, 0.4);
  const lightSecondary = lightenColor(secondaryColor, 0.3);

  // Format all event dates
  const formattedDates = (() => {
    // Collect all unique dates from events
    const allDates = new Set<string>();

    // Add main wedding date
    if (wedding.date) {
      allDates.add(wedding.date);
    }

    // Add event dates
    if (wedding.events && wedding.events.length > 0) {
      wedding.events.forEach(event => {
        if (event.date) {
          allDates.add(event.date);
        }
      });
    }

    // Sort dates chronologically
    const sortedDates = Array.from(allDates).sort();

    // Format each date
    const formatted = sortedDates
      .map(dateValue =>
        formatDate(dateValue, {
          month: 'long',
          day: 'numeric',
          year: 'numeric',
        }),
      )
      .filter(Boolean);

    // Join with separator
    if (formatted.length === 0) return '';
    if (formatted.length === 1) return formatted[0];
    if (formatted.length === 2) return formatted.join(' - ');
    return `${formatted[0]} - ${formatted[formatted.length - 1]}`;
  })();

  return (
    <section className="flex flex-col items-center justify-center text-center py-16 sm:py-24 md:py-32 px-4">
      {/* CSS variables for theme colors with dark mode variants */}
      <style jsx>{`
        .hero-title {
          color: ${primaryColor};
        }
        .hero-date {
          color: ${primaryColor};
        }
        .hero-divider {
          background-color: ${secondaryColor};
        }
        :global(.dark) .hero-title {
          color: ${lightPrimary};
        }
        :global(.dark) .hero-date {
          color: ${lightSecondary};
        }
        :global(.dark) .hero-divider {
          background-color: ${lightSecondary};
        }
      `}</style>

      <GlassCard
        className="max-w-4xl mx-auto p-8 sm:p-12 md:p-16"
        depth="near"
        theme={theme}
      >
        <h1
          className="hero-title text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold leading-tight transition-colors duration-300"
        >
          {wedding.couple_names}
        </h1>
        <div
          className="hero-divider w-16 sm:w-24 h-1 mx-auto mt-4 mb-6 transition-colors duration-300"
        ></div>
        {formattedDates && (
          <p
            className="hero-date text-base sm:text-lg md:text-xl lg:text-2xl font-light transition-colors duration-300"
          >
            {formattedDates}
          </p>
        )}
        <div className="mt-8 sm:mt-12">
          <div
            className="inline-block px-6 py-3 rounded-full transition-all duration-300 hover:scale-105"
            style={{
              backgroundColor: accentColor,
              color: '#ffffff'
            }}
          >
            <p
              className="text-sm sm:text-base font-medium text-white"
            >
              Celebrate with us
            </p>
          </div>
        </div>
      </GlassCard>
    </section>
  );
};