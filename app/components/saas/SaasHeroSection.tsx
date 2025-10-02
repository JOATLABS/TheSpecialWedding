'use client';

import React from 'react';
import Link from 'next/link';
import { GlassCard } from '../ui/GlassCard';
import { SaasLogoTitle } from './SaasLogoTitle';

interface SaasConfig {
  hero_title: string;
  hero_subtitle: string;
  hero_description: string;
  hero_cta_primary: string;
  hero_cta_secondary: string;
  trust_indicators: string[];
  statistics: Array<{
    label: string;
    value: string;
  }>;
  statistics_enabled: boolean;
  demo_url?: string;
  primary_color: string;
  secondary_color: string;
}

interface SaasHeroSectionProps {
  config: SaasConfig;
  theme: {
    primary_color: string;
    secondary_color: string;
    background_style: 'gradient' | 'solid';
  };
}

export const SaasHeroSection: React.FC<SaasHeroSectionProps> = ({ config, theme }) => {
  const handleGetStarted = () => {
    // Scroll to sign-up section or open modal
    const signUpSection = document.getElementById('sign-up');
    if (signUpSection) {
      signUpSection.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleWatchDemo = () => {
    // Open demo modal or redirect to demo
    if (config.demo_url) {
      window.open(config.demo_url, '_blank');
    }
  };

  return (
    <section className="flex flex-col items-center justify-center text-center py-12 sm:py-16 md:py-20 px-4">
      {/* Title and Logo - Floating without card */}
      <div className="w-full mb-6">
        <SaasLogoTitle theme={theme} />
      </div>

      {/* Description Card */}
      <GlassCard 
        className="max-w-4xl mx-auto p-8 sm:p-12 md:p-16" 
        depth="mid" 
        theme={{
          primary_color: theme.primary_color,
          secondary_color: theme.secondary_color,
          accent_color: theme.secondary_color, // Use secondary as accent fallback
          background_style: theme.background_style,
          font_style: 'elegant' as const
        }}
      >
        {/* Subtitle */}
        <p 
          className="text-base sm:text-lg md:text-xl lg:text-2xl font-light mb-6"
          style={{ color: theme?.primary_color || '#1e3a5f' }}
        >
          {config.hero_subtitle}
        </p>
        
        <div 
          className="w-16 sm:w-24 h-1 mx-auto mb-6"
          style={{ backgroundColor: theme?.secondary_color || '#d4af37' }}
        ></div>
        
        {/* Description */}
        <p className="text-base sm:text-lg text-gray-600 mb-8 max-w-3xl mx-auto">
          {config.hero_description}
        </p>
          
        {/* CTA Buttons */}
        <div className="mt-8 sm:mt-12">
          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-4 sm:mb-6">
            <button
              onClick={handleGetStarted}
              className="w-full sm:w-auto px-6 sm:px-8 py-3 sm:py-4 text-white font-semibold rounded-full
                         shadow-xl hover:shadow-2xl transform hover:scale-105
                         transition-all duration-300 text-base sm:text-lg min-w-[200px]"
              style={{
                backgroundColor: theme?.primary_color || '#1e3a5f'
              }}
            >
              {config.hero_cta_primary}
            </button>
            
            <button
              onClick={handleWatchDemo}
              className="w-full sm:w-auto px-6 sm:px-8 py-3 sm:py-4 bg-white/80 backdrop-blur-sm border-2 
                         text-gray-800 font-semibold rounded-full shadow-lg
                         hover:shadow-xl transform hover:scale-105 
                         transition-all duration-300 text-base sm:text-lg min-w-[200px]
                         hover:bg-white/90"
              style={{
                borderColor: theme?.secondary_color || '#d4af37'
              }}
            >
              {config.hero_cta_secondary}
            </button>
          </div>

          <p className="text-sm text-gray-600" role="note">
            Already have an account?{' '}
            <Link
              href="/admin/login"
              className="font-semibold text-gray-800 underline decoration-wavy decoration-2 underline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-gray-400"
            >
              Log in to the planner portal
            </Link>
          </p>
        </div>
          
        {/* Trust Indicators */}
        {config.trust_indicators && config.trust_indicators.length > 0 && (
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-8 text-sm text-gray-600">
            {config.trust_indicators.map((indicator, index) => (
              <div key={index} className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${
                  index === 0 ? 'bg-green-500 animate-pulse' : 
                  index === 1 ? 'bg-blue-500' : 'bg-purple-500'
                }`}></div>
                <span>{indicator}</span>
              </div>
            ))}
          </div>
        )}
      </GlassCard>
        
      {/* Floating Stats - Mobile Responsive */}
      {config.statistics_enabled && config.statistics && config.statistics.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 sm:gap-6 mt-6 md:mt-8">
          {config.statistics.map((stat, index) => (
            <GlassCard key={index} depth="mid" className="p-4 sm:p-6 text-center">
              <div className="text-2xl sm:text-3xl font-bold text-gray-900 mb-2">{stat.value}</div>
              <div className="text-sm sm:text-base text-gray-600">{stat.label}</div>
            </GlassCard>
          ))}
        </div>
      )}
    </section>
  );
};