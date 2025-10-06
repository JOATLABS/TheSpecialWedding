'use client';

import React from 'react';

interface SaasLogoTitleProps {
  theme?: {
    primary_color: string;
    secondary_color: string;
  };
}

export const SaasLogoTitle: React.FC<SaasLogoTitleProps> = ({ theme }) => {
  const primaryColor = theme?.primary_color || '#1e3a5f';
  const secondaryColor = theme?.secondary_color || '#d4af37';

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col items-center gap-6 px-4 text-center sm:gap-8">
      <div className="md:mb-2">
        <div
          className="relative h-28 w-28 sm:h-32 sm:w-32 md:h-40 md:w-40"
          style={{
            filter: `
              drop-shadow(0 0 24px rgba(255, 255, 255, 0.9))
              drop-shadow(0 0 60px rgba(255, 255, 255, 0.55))
              drop-shadow(0 0 90px ${primaryColor}55)
            `,
          }}
        >
          <img
            src="/Logo.svg"
            alt="Special Wedding Logo"
            className="h-full w-full object-contain"
            style={{ filter: 'brightness(1.05) contrast(1.08)' }}
          />
        </div>
      </div>

      <div className="flex w-full flex-col items-center text-balance text-center md:items-end md:text-right">
        <span
          className="block w-full text-[clamp(2.75rem,5.2vw,4.75rem)] font-medium tracking-[0.25em] text-slate-900"
          style={{
            fontFamily: "'Poppins', sans-serif",
            color: primaryColor,
            textShadow: `
              0 0 28px rgba(255, 255, 255, 0.95),
              0 0 60px rgba(255, 255, 255, 0.65),
              0 4px 12px rgba(15, 23, 42, 0.25)
            `,
            WebkitTextStroke: '1px rgba(255, 255, 255, 0.7)',
          }}
        >
          Welcome
        </span>

        <div className="mt-4 flex w-full flex-col items-center gap-4 md:items-end">
          <div className="flex flex-wrap items-center justify-center gap-3 md:justify-end">
            <span
              className="text-[clamp(1.5rem,3.4vw,2.5rem)] font-semibold uppercase tracking-[0.35em] text-slate-800"
              style={{
                fontFamily: "'Poppins', sans-serif",
                color: secondaryColor,
                textShadow: `
                  0 0 18px rgba(255, 255, 255, 0.9),
                  0 0 45px rgba(255, 255, 255, 0.55)
                `,
                WebkitTextStroke: '0.8px rgba(255, 255, 255, 0.6)',
              }}
            >
              To
            </span>
            <span
              className="text-[clamp(2.75rem,5.5vw,4rem)] font-semibold text-slate-900"
              style={{
                fontFamily: "'Dancing Script', cursive",
                color: primaryColor,
                textShadow: `
                  0 0 30px rgba(255, 255, 255, 0.9),
                  0 0 70px rgba(255, 255, 255, 0.65),
                  0 6px 12px rgba(15, 23, 42, 0.25)
                `,
                WebkitTextStroke: '1px rgba(255, 255, 255, 0.65)',
              }}
            >
              The
            </span>
          </div>

          <span
            className="block w-full text-[clamp(3.5rem,7.5vw,6.5rem)] font-bold leading-[1.05] text-white"
            style={{
              fontFamily: "'Dancing Script', cursive",
              textShadow: `
                0 0 40px rgba(255, 255, 255, 0.95),
                0 0 90px ${primaryColor}80,
                0 0 120px ${secondaryColor}55,
                0 8px 18px rgba(15, 23, 42, 0.3)
              `,
              WebkitTextStroke: `1.6px ${primaryColor}`,
              background: `linear-gradient(135deg, rgba(255,255,255,0.95), ${primaryColor}1f)`,
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