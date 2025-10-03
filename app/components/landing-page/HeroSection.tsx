import React from "react";
import { formatDate } from '@/utils/dateFormat';

interface HeroSectionProps {
  coupleName: string;
  date: string;
}

export const HeroSection: React.FC<HeroSectionProps> = ({ coupleName, date }) => {
  const formattedDate = date
    ? formatDate(date, {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : '';

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
