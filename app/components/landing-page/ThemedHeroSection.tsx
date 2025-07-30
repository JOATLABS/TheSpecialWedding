import React from "react";
import { Wedding } from "@/types/wedding";

interface ThemedHeroSectionProps {
  wedding: Wedding;
}

export const ThemedHeroSection: React.FC<ThemedHeroSectionProps> = ({ wedding }) => {
  const theme = wedding.theme_config;
  
  // Fix timezone issues by parsing date components directly
  const formattedDate = wedding.date ? (() => {
    // If date is in YYYY-MM-DD format, parse manually to avoid timezone conversion
    if (wedding.date.includes('-')) {
      const [year, month, day] = wedding.date.split('-');
      const dateObj = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
      return dateObj.toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    } else {
      // For other date formats, use direct parsing
      return new Date(wedding.date).toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    }
  })() : '';

  return (
    <section className="flex flex-col items-center justify-center text-white text-center py-16 sm:py-24 md:py-32 px-4">
      <div className="max-w-4xl mx-auto">
        <h1 
          className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold drop-shadow-lg leading-tight"
          style={{ color: theme?.primary_color || '#ffffff' }}
        >
          {wedding.couple_names}
        </h1>
        <div 
          className="w-16 sm:w-24 h-1 mx-auto mt-4 mb-6 drop-shadow-sm"
          style={{ backgroundColor: theme?.secondary_color || '#ffffff' }}
        ></div>
        {formattedDate && (
          <p 
            className="text-base sm:text-lg md:text-xl lg:text-2xl font-light drop-shadow-md"
            style={{ color: theme?.secondary_color || '#ffffff' }}
          >
            {formattedDate}
          </p>
        )}
        <div className="mt-8 sm:mt-12">
          <div 
            className="inline-block px-6 py-3 backdrop-blur-sm rounded-full"
            style={{ 
              backgroundColor: `${theme?.accent_color || '#ffffff'}20`,
              borderColor: theme?.accent_color || '#ffffff',
              borderWidth: '1px',
              borderStyle: 'solid'
            }}
          >
            <p 
              className="text-sm sm:text-base font-medium"
              style={{ color: theme?.accent_color || '#ffffff' }}
            >
              Celebrate with us
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};