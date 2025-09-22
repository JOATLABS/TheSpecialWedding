'use client';

import React, { useState, useEffect, useRef } from 'react';
import { GlassCard } from '@/components/ui/GlassCard';

interface Feature {
  id?: string;
  title: string;
  description: string;
  icon?: string;
  status: 'available' | 'coming_soon';
  order: number;
}

interface FeatureCarouselProps {
  features?: Feature[];
  theme: {
    primary_color: string;
    secondary_color: string;
  };
}

export const FeatureCarousel: React.FC<FeatureCarouselProps> = ({ features = [], theme }) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [touchStart, setTouchStart] = useState(0);
  const [touchEnd, setTouchEnd] = useState(0);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Sort features by order
  const sortedFeatures = [...features].sort((a, b) => a.order - b.order);

  // Auto-play functionality
  useEffect(() => {
    if (!isPaused && sortedFeatures.length > 1) {
      intervalRef.current = setInterval(() => {
        setCurrentIndex((prev) => (prev + 1) % sortedFeatures.length);
      }, 4000); // Change slide every 4 seconds

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      };
    }
  }, [isPaused, sortedFeatures.length]);

  const handlePrevious = () => {
    setCurrentIndex((prev) => 
      prev === 0 ? sortedFeatures.length - 1 : prev - 1
    );
  };

  const handleNext = () => {
    setCurrentIndex((prev) => (prev + 1) % sortedFeatures.length);
  };

  const handleDotClick = (index: number) => {
    setCurrentIndex(index);
  };

  // Touch handlers for mobile swipe
  const handleTouchStart = (e: React.TouchEvent) => {
    setTouchStart(e.targetTouches[0].clientX);
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    setTouchEnd(e.targetTouches[0].clientX);
  };

  const handleTouchEnd = () => {
    if (!touchStart || !touchEnd) return;
    
    const distance = touchStart - touchEnd;
    const isLeftSwipe = distance > 50;
    const isRightSwipe = distance < -50;

    if (isLeftSwipe) {
      handleNext();
    }
    if (isRightSwipe) {
      handlePrevious();
    }
  };

  if (sortedFeatures.length === 0) {
    return null;
  }

  // Show 3 cards at a time on desktop, 1 on mobile
  const getVisibleFeatures = () => {
    const result = [];
    for (let i = 0; i < 3; i++) {
      const index = (currentIndex + i) % sortedFeatures.length;
      result.push(sortedFeatures[index]);
    }
    return result;
  };

  return (
    <div 
      className="relative"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      {/* Section Header */}
      <div className="text-center mb-12">
        <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
          Powerful Features for Wedding Professionals
        </h2>
        <p className="text-lg text-gray-600 max-w-3xl mx-auto">
          Everything you need to manage your wedding planning business effectively, with cutting-edge AI features coming soon
        </p>
      </div>

      {/* Carousel Container */}
      <div className="relative overflow-hidden">
        {/* Desktop View - Show 3 cards */}
        <div className="hidden md:grid md:grid-cols-3 gap-6 transition-all duration-500">
          {getVisibleFeatures().map((feature, index) => (
            <GlassCard 
              key={`${feature.title}-${index}`}
              depth={index === 0 ? "near" : index === 1 ? "mid" : "far"}
              className="p-6 transform transition-all duration-500"
            >
              {/* Status Badge */}
              <div className="flex justify-between items-start mb-4">
                <div className={`inline-flex px-3 py-1 text-xs font-semibold rounded-full ${
                  feature.status === 'available' 
                    ? 'bg-green-100 text-green-800'
                    : 'bg-amber-100 text-amber-800'
                }`}>
                  {feature.status === 'available' ? 'Available Now' : 'Coming Soon'}
                </div>
              </div>

              {/* Feature Content */}
              <h3 className="text-xl font-bold text-gray-900 mb-3">
                {feature.title}
              </h3>
              <p className="text-gray-600 text-sm leading-relaxed">
                {feature.description}
              </p>

              {/* AI Feature Indicator */}
              {feature.status === 'coming_soon' && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <div className="flex items-center text-amber-600 text-sm">
                    <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                    </svg>
                    <span>AI-Powered Feature</span>
                  </div>
                </div>
              )}
            </GlassCard>
          ))}
        </div>

        {/* Mobile View - Show 1 card */}
        <div className="md:hidden">
          <GlassCard depth="near" className="p-6">
            {/* Status Badge */}
            <div className="flex justify-between items-start mb-4">
              <div className={`inline-flex px-3 py-1 text-xs font-semibold rounded-full ${
                sortedFeatures[currentIndex].status === 'available' 
                  ? 'bg-green-100 text-green-800'
                  : 'bg-amber-100 text-amber-800'
              }`}>
                {sortedFeatures[currentIndex].status === 'available' ? 'Available Now' : 'Coming Soon'}
              </div>
            </div>

            {/* Feature Content */}
            <h3 className="text-xl font-bold text-gray-900 mb-3">
              {sortedFeatures[currentIndex].title}
            </h3>
            <p className="text-gray-600 text-sm leading-relaxed">
              {sortedFeatures[currentIndex].description}
            </p>

            {/* AI Indicator for coming soon features */}
            {sortedFeatures[currentIndex].status === 'coming_soon' && (
              <div className="mt-4 pt-4 border-t border-gray-200">
                <div className="flex items-center text-amber-600 text-sm">
                  <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                  </svg>
                  <span>AI-Powered Feature</span>
                </div>
              </div>
            )}
          </GlassCard>
        </div>
      </div>

      {/* Navigation Controls */}
      <div className="flex justify-center items-center mt-8 space-x-4">
        {/* Previous Button */}
        <button
          onClick={handlePrevious}
          className="p-2 rounded-full bg-white/50 hover:bg-white/80 transition-colors"
          aria-label="Previous feature"
        >
          <svg className="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>

        {/* Dots Indicator */}
        <div className="flex space-x-2">
          {sortedFeatures.map((_, index) => (
            <button
              key={index}
              onClick={() => handleDotClick(index)}
              className={`w-2 h-2 rounded-full transition-all duration-300 ${
                index === currentIndex 
                  ? 'w-8 bg-gradient-to-r from-indigo-600 to-emerald-600'
                  : 'bg-gray-300 hover:bg-gray-400'
              }`}
              style={index === currentIndex ? {
                background: `linear-gradient(to right, ${theme.primary_color}, ${theme.secondary_color})`
              } : {}}
              aria-label={`Go to feature ${index + 1}`}
            />
          ))}
        </div>

        {/* Next Button */}
        <button
          onClick={handleNext}
          className="p-2 rounded-full bg-white/50 hover:bg-white/80 transition-colors"
          aria-label="Next feature"
        >
          <svg className="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      {/* Pause Indicator */}
      {isPaused && (
        <div className="absolute top-4 right-4 text-xs text-gray-500">
          Paused
        </div>
      )}
    </div>
  );
};