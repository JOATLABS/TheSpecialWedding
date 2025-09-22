'use client';

import React from 'react';
import { GlassCard } from '../ui/GlassCard';

interface Benefit {
  title: string;
  description: string;
  icon?: string;
  order: number;
}

interface BenefitsSectionProps {
  benefits: Benefit[];
  theme: {
    primary_color: string;
    secondary_color: string;
  };
}

export const BenefitsSection: React.FC<BenefitsSectionProps> = ({ benefits, theme }) => {
  const sortedBenefits = [...benefits].sort((a, b) => a.order - b.order);

  if (sortedBenefits.length === 0) {
    return null;
  }

  return (
    <GlassCard depth="mid" className="p-8">
      {/* Section Header */}
      <div className="text-center mb-12">
  <h2 className="text-3xl md:text-4xl text-gray-900 mb-4">
          Why Wedding Planners Choose Us
        </h2>
        <p className="text-lg text-gray-600 max-w-3xl mx-auto">
          Transform your wedding planning business with our comprehensive platform designed specifically for professionals
        </p>
      </div>

      {/* Benefits Grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
        {sortedBenefits.map((benefit, index) => (
          <div key={index} className="text-center group">
            {/* Icon placeholder */}
            <div 
              className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center"
              style={{
                background: `linear-gradient(135deg, ${theme.primary_color}20, ${theme.secondary_color}20)`,
                border: `2px solid ${theme.primary_color}30`
              }}
            >
              {benefit.icon ? (
                <span className="text-2xl">{benefit.icon}</span>
              ) : (
                <div 
                  className="w-6 h-6 rounded-full"
                  style={{ backgroundColor: theme.primary_color }}
                />
              )}
            </div>

            {/* Benefit Content */}
            <h3 
              className="text-xl mb-3 group-hover:scale-105 transition-transform duration-300"
              style={{ color: theme.primary_color }}
            >
              {benefit.title}
            </h3>
            <p className="text-gray-600 text-sm leading-relaxed">
              {benefit.description}
            </p>
          </div>
        ))}
      </div>
    </GlassCard>
  );
};