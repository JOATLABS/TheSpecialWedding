import React from "react";
import { Wedding } from "@/types/wedding";
import { GlassCard } from "@/components/ui/GlassCard";

interface ThemedHeroSectionProps {
  wedding: Wedding;
}

export const ThemedHeroSection: React.FC<ThemedHeroSectionProps> = ({ wedding }) => {
  const theme = wedding.theme_config;
  
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
    const formatted = sortedDates.map(date => {
      if (date.includes('-')) {
        const [year, month, day] = date.split('-');
        const dateObj = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
        return dateObj.toLocaleDateString('en-US', {
          month: 'long',
          day: 'numeric',
          year: 'numeric'
        });
      } else {
        return new Date(date).toLocaleDateString('en-US', {
          month: 'long',
          day: 'numeric',
          year: 'numeric'
        });
      }
    });
    
    // Join with separator
    if (formatted.length === 0) return '';
    if (formatted.length === 1) return formatted[0];
    if (formatted.length === 2) return formatted.join(' - ');
    return `${formatted[0]} - ${formatted[formatted.length - 1]}`;
  })();

  return (
    <section className="flex flex-col items-center justify-center text-center py-16 sm:py-24 md:py-32 px-4">
      <GlassCard 
        className="max-w-4xl mx-auto p-8 sm:p-12 md:p-16" 
        depth="near" 
        theme={theme}
      >
        <h1 
          className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl leading-tight"
          style={{ color: theme?.primary_color || '#1e3a5f' }}
        >
          {wedding.couple_names}
        </h1>
        <div 
          className="w-16 sm:w-24 h-1 mx-auto mt-4 mb-6"
          style={{ backgroundColor: theme?.secondary_color || '#d4af37' }}
        ></div>
        {formattedDates && (
          <p 
            className="text-base sm:text-lg md:text-xl lg:text-2xl font-light"
            style={{ color: theme?.primary_color || '#1e3a5f' }}
          >
            {formattedDates}
          </p>
        )}
        <div className="mt-8 sm:mt-12">
          <div 
            className="inline-block px-6 py-3 rounded-full"
            style={{ 
              backgroundColor: theme?.accent_color || '#c8847e',
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