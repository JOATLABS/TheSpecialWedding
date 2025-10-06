'use client';

import React from 'react';
import Image from 'next/image';
import { GlassCard } from '../ui/GlassCard';

interface Testimonial {
  name: string;
  company: string;
  role: string;
  content: string;
  avatar_url?: string;
  order: number;
}

interface TestimonialsSectionProps {
  testimonials: Testimonial[];
  theme: {
    primary_color: string;
    secondary_color: string;
  };
}

export const TestimonialsSection: React.FC<TestimonialsSectionProps> = ({ testimonials, theme }) => {
  const sortedTestimonials = [...testimonials].sort((a, b) => a.order - b.order);

  if (sortedTestimonials.length === 0) {
    return null;
  }

  return (
    <GlassCard depth="mid" className="p-8">
      {/* Section Header */}
      <div className="text-center mb-12">
        <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
          What Wedding Planners Say
        </h2>
        <p className="text-lg text-gray-600 max-w-3xl mx-auto">
          Join thousands of wedding professionals who trust our platform to manage their business
        </p>
      </div>

      {/* Testimonials Grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {sortedTestimonials.map((testimonial, index) => (
          <GlassCard key={index} depth="near" className="p-6 group hover:scale-105 transition-all duration-300">
            {/* Quote */}
            <div className="mb-6">
              <svg className="w-8 h-8 text-gray-300 mb-3" fill="currentColor" viewBox="0 0 24 24">
                <path d="M4.583 17.321C3.553 16.227 3 15 3 13.011c0-3.5 2.457-6.637 6.03-8.188l.893 1.378c-3.335 1.804-3.987 4.145-4.247 5.621.537-.278 1.24-.375 1.929-.311 1.804.167 3.226 1.648 3.226 3.489a3.5 3.5 0 01-3.5 3.5c-1.073 0-2.099-.49-2.748-1.179zm10 0C13.553 16.227 13 15 13 13.011c0-3.5 2.457-6.637 6.03-8.188l.893 1.378c-3.335 1.804-3.987 4.145-4.247 5.621.537-.278 1.24-.375 1.929-.311 1.804.167 3.226 1.648 3.226 3.489a3.5 3.5 0 01-3.5 3.5c-1.073 0-2.099-.49-2.748-1.179z"/>
              </svg>
              <p className="text-gray-700 italic leading-relaxed">
                “{testimonial.content}”
              </p>
            </div>

            {/* Author */}
            <div className="flex items-center">
              <div 
                className="w-12 h-12 rounded-full flex items-center justify-center mr-4"
                style={{
                  background: `linear-gradient(135deg, ${theme.primary_color}, ${theme.secondary_color})`
                }}
              >
                {testimonial.avatar_url ? (
                  <Image
                    src={testimonial.avatar_url}
                    alt={testimonial.name}
                    fill
                    className="rounded-full object-cover"
                    sizes="48px"
                  />
                ) : (
                  <span className="text-white font-bold text-lg">
                    {testimonial.name.split(' ').map(n => n[0]).join('')}
                  </span>
                )}
              </div>
              <div>
                <h4 className="font-semibold text-gray-900">{testimonial.name}</h4>
                <p className="text-sm text-gray-600">{testimonial.role}</p>
                <p 
                  className="text-sm font-medium"
                  style={{ color: theme.primary_color }}
                >
                  {testimonial.company}
                </p>
              </div>
            </div>
          </GlassCard>
        ))}
      </div>
    </GlassCard>
  );
};