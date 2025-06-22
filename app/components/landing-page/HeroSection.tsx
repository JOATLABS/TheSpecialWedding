import React from "react";

interface HeroSectionProps {
  coupleName: string;
  date: string;
}

export const HeroSection: React.FC<HeroSectionProps> = ({ coupleName, date }) => {
  // Fix timezone issues by parsing date components directly
  const formattedDate = date ? (() => {
    // If date is in YYYY-MM-DD format, parse manually to avoid timezone conversion
    if (date.includes('-')) {
      const [year, month, day] = date.split('-');
      const dateObj = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
      return dateObj.toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    } else {
      // For other date formats, use direct parsing
      return new Date(date).toLocaleDateString('en-US', {
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
        <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold drop-shadow-lg leading-tight">
          {coupleName}
        </h1>
        <div className="w-16 sm:w-24 h-1 bg-white mx-auto mt-4 mb-6 drop-shadow-sm"></div>
        {formattedDate && (
          <p className="text-base sm:text-lg md:text-xl lg:text-2xl font-light drop-shadow-md">
            {formattedDate}
          </p>
        )}
        <div className="mt-8 sm:mt-12">
          <div className="inline-block px-6 py-3 bg-white bg-opacity-10 backdrop-blur-sm rounded-full">
            <p className="text-sm sm:text-base font-medium">
              Celebrate with us
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};
