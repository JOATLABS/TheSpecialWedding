'use client';

import React from 'react';
import Image from 'next/image';

interface SaasLogoTitleProps {
  theme?: {
    primary_color: string;
    secondary_color: string;
  };
}

export const SaasLogoTitle: React.FC<SaasLogoTitleProps> = ({ theme }) => {
  return (
    <div className="flex flex-col items-center justify-center w-full max-w-5xl mx-auto">
      {/* Logo on Top with Glass Glow */}
      <div className="mb-6 md:mb-8">
        <div
          className="relative w-32 h-32 sm:w-40 sm:h-40 md:w-48 md:h-48"
          style={{
            filter: `
              drop-shadow(0 0 30px rgba(255, 255, 255, 0.9))
              drop-shadow(0 0 60px rgba(255, 255, 255, 0.6))
              drop-shadow(0 0 90px ${theme?.primary_color || '#1e3a5f'}50)
            `,
          }}
        >
          <Image
            src="/Logo.svg"
            alt="Special Wedding Logo"
            fill
            className="object-contain"
            sizes="(max-width: 768px) 160px, 192px"
            priority
            style={{
              filter: 'brightness(1.1) contrast(1.1)',
            }}
          />
        </div>
      </div>
      {/* Title Text with Enhanced Glass Glow for Visibility */}
      <div className="text-center">
        {/* Welcome - Sans Serif, Bigger with stronger glow */}
        <div className="relative">
          <span
            className="block text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-medium tracking-wider"
            style={{
              fontFamily: "'Poppins', sans-serif",
              color: theme?.primary_color || '#1e3a5f',
              textShadow: `
                0 0 30px rgba(255, 255, 255, 1),
                0 0 60px rgba(255, 255, 255, 0.8),
                0 0 90px rgba(255, 255, 255, 0.6),
                0 0 120px ${theme?.primary_color || '#1e3a5f'}80,
                0 4px 6px rgba(0, 0, 0, 0.3),
                0 8px 12px rgba(0, 0, 0, 0.2)
              `,
              WebkitTextStroke: '1px rgba(255, 255, 255, 0.8)',
              filter: 'drop-shadow(0 0 40px rgba(255, 255, 255, 0.8))',
            }}
          >
            Welcome
          </span>
        </div>

        {/* TO The - Sans Serif, Indented with glow */}
        <div className="relative -mt-2 ml-16 sm:ml-20 md:ml-24 lg:ml-32">
          <span
            className="inline-block text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-medium tracking-widest mr-4"
            style={{
              fontFamily: "'Poppins', sans-serif",
              color: theme?.secondary_color || '#d4af37',
              textShadow: `
                0 0 25px rgba(255, 255, 255, 1),
                0 0 50px rgba(255, 255, 255, 0.8),
                0 0 75px ${theme?.secondary_color || '#d4af37'}80,
                0 3px 5px rgba(0, 0, 0, 0.3)
              `,
              WebkitTextStroke: '0.8px rgba(255, 255, 255, 0.6)',
              filter: 'drop-shadow(0 0 30px rgba(255, 255, 255, 0.7))',
            }}
          >
            TO
          </span>
          <span
            className="inline-block text-6xl sm:text-7xl md:text-8xl lg:text-9xl font-semibold"
            style={{
              fontFamily: "'Dancing Script', cursive",
              color: theme?.primary_color || '#1e3a5f',
              textShadow: `
                0 0 35px rgba(255, 255, 255, 1),
                0 0 70px rgba(255, 255, 255, 0.8),
                0 0 100px ${theme?.primary_color || '#1e3a5f'}60,
                0 4px 8px rgba(0, 0, 0, 0.3)
              `,
              WebkitTextStroke: '1px rgba(255, 255, 255, 0.7)',
              filter: 'drop-shadow(0 0 35px rgba(255, 255, 255, 0.8))',
            }}
          >
            The
          </span>
        </div>

        {/* Special Wedding - Script Font, Much Larger with strongest glow */}
        <div className="relative -mt-6 ml-24 sm:ml-32 md:ml-40 lg:ml-48">
          <span
            className="block text-6xl sm:text-7xl md:text-8xl lg:text-[8rem] font-bold"
            style={{
              fontFamily: "'Dancing Script', cursive",
              color: 'white',
              textShadow: `
                0 0 40px rgba(255, 255, 255, 1),
                0 0 80px rgba(255, 255, 255, 0.9),
                0 0 120px ${theme?.primary_color || '#1e3a5f'}90,
                0 0 160px ${theme?.secondary_color || '#d4af37'}60,
                0 6px 12px rgba(0, 0, 0, 0.4),
                0 12px 24px rgba(0, 0, 0, 0.3)
              `,
              WebkitTextStroke: `2px ${theme?.primary_color || '#1e3a5f'}`,
              filter: `
                drop-shadow(0 0 50px rgba(255, 255, 255, 0.9))
                drop-shadow(0 0 100px ${theme?.primary_color || '#1e3a5f'}80)
              `,
              background: `linear-gradient(135deg, white, ${theme?.primary_color || '#1e3a5f'}20)`,
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            Special Wedding
          </span>
        </div>
      </div>
    </div>
  );
};
