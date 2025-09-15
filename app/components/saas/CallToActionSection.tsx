'use client';

import React from 'react';
import { GlassCard } from '../ui/GlassCard';

interface SaasConfig {
  hero_title: string;
  hero_subtitle: string;
  hero_description: string;
  hero_cta_primary: string;
  hero_cta_secondary: string;
  trust_indicators: string[];
  demo_url?: string;
  primary_color: string;
  secondary_color: string;
}

interface CallToActionSectionProps {
  config: SaasConfig;
  theme: {
    primary_color: string;
    secondary_color: string;
  };
  onGetStarted?: () => void;
  contactMode?: boolean;
  onContactClick?: () => void;
}

export const CallToActionSection: React.FC<CallToActionSectionProps> = ({ config, theme, onGetStarted, contactMode = false, onContactClick }) => {
  const handleGetStarted = () => {
    if (onGetStarted) {
      onGetStarted();
    } else {
      // No get started handler configured
    }
  };

  const handleContact = () => {
    if (contactMode && onContactClick) {
      onContactClick();
    } else {
      // Original contact functionality for subscription mode
    }
  };

  if (contactMode) {
    return (
      <GlassCard depth="mid" className="p-8 sm:p-12 md:p-16 text-center">
        {/* Main CTA Header - Contact Mode */}
        <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
          Ready to Transform Your Wedding Planning?
        </h2>

        <div
          className="w-24 h-1 mx-auto mb-6"
          style={{ backgroundColor: theme?.secondary_color || '#d4af37' }}
        ></div>

        <p className="text-lg text-gray-600 mb-8 max-w-2xl mx-auto">
          Whether you're a professional wedding planner or planning your own special day,
          let's discuss how Special Wedding can help you create the perfect celebration.
        </p>

        {/* Contact CTA Button */}
        <div className="flex justify-center mb-8">
          <button
            onClick={handleContact}
            className="px-8 py-4 text-white font-semibold rounded-full
                       shadow-xl hover:shadow-2xl transform hover:scale-105
                       transition-all duration-300 text-lg min-w-[200px]"
            style={{
              backgroundColor: theme?.primary_color || '#1e3a5f'
            }}
          >
            {config.hero_cta_primary || "Contact Us"}
          </button>
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

        {/* Additional assurance text - Contact Mode */}
        <div className="mt-8 pt-6 border-t border-gray-200">
          <p className="text-sm text-gray-500">
            Free consultation • No obligation • Quick response time
          </p>
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard depth="mid" className="p-8 sm:p-12 md:p-16 text-center">
      {/* Main CTA Header */}
      <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
        Ready to Transform Your Wedding Planning?
      </h2>

      <div
        className="w-24 h-1 mx-auto mb-6"
        style={{ backgroundColor: theme?.secondary_color || '#d4af37' }}
      ></div>

      <p className="text-lg text-gray-600 mb-8 max-w-2xl mx-auto">
        Join thousands of wedding planners who have already transformed their businesses with our comprehensive platform. Start your free trial today and see the difference.
      </p>

      {/* CTA Buttons */}
      <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-8">
        <button
          onClick={handleGetStarted}
          className="w-full sm:w-auto px-8 py-4 text-white font-semibold rounded-full
                     shadow-xl hover:shadow-2xl transform hover:scale-105
                     transition-all duration-300 text-lg min-w-[200px]"
          style={{
            backgroundColor: theme?.primary_color || '#1e3a5f'
          }}
        >
          Start Free Trial
        </button>

        <button
          onClick={handleContact}
          className="w-full sm:w-auto px-8 py-4 bg-white/80 backdrop-blur-sm border-2
                     text-gray-800 font-semibold rounded-full shadow-lg
                     hover:shadow-xl transform hover:scale-105
                     transition-all duration-300 text-lg min-w-[200px]
                     hover:bg-white/90"
          style={{
            borderColor: theme?.secondary_color || '#d4af37'
          }}
        >
          Contact Sales
        </button>
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

      {/* Additional assurance text */}
      <div className="mt-8 pt-6 border-t border-gray-200">
        <p className="text-sm text-gray-500">
          No credit card required • Cancel anytime • 24/7 support
        </p>
      </div>
    </GlassCard>
  );
};