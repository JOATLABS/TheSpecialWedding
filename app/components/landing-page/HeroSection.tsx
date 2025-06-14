import React from "react";

interface HeroSectionProps {
  coupleName: string;
  date: string;
}

export const HeroSection: React.FC<HeroSectionProps> = ({ coupleName, date }) => {
  return (
    <section className="flex flex-col items-center justify-center text-white text-center py-32 px-4">
      <h1 className="text-4xl md:text-6xl font-bold drop-shadow-md">
        {coupleName}
      </h1>
      <p className="text-lg md:text-2xl mt-4 font-light drop-shadow-sm">
        {date}
      </p>
    </section>
  );
};
