'use client';

import React, { useEffect, useRef, useState } from 'react';

interface Feature {
  title: string;
  description: string;
  icon?: string;
  status: 'available' | 'coming_soon';
}

interface FeaturesSectionProps {
  features: Feature[];
  theme?: {
    primary_color?: string;
    secondary_color?: string;
  };
}

export const FeaturesSection: React.FC<FeaturesSectionProps> = ({ features, theme }) => {
  const sectionRef = useRef<HTMLElement>(null);
  const [visibleCards, setVisibleCards] = useState<Set<number>>(new Set());

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const index = parseInt(entry.target.getAttribute('data-index') || '0');
            setVisibleCards((prev) => new Set([...prev, index]));
          }
        });
      },
      { threshold: 0.2, rootMargin: '50px' }
    );

    const cards = sectionRef.current?.querySelectorAll('[data-index]');
    cards?.forEach((card) => observer.observe(card));

    return () => observer.disconnect();
  }, [features]);

  const getFeatureIcon = (title: string, customIcon?: string): string => {
    if (customIcon) return customIcon;

    // Smart icon mapping based on feature title
    const iconMap: Record<string, string> = {
      'guest': '👥',
      'rsvp': '✉️',
      'vendor': '🤝',
      'timeline': '📅',
      'budget': '💰',
      'website': '🌐',
      'form': '📝',
      'email': '📧',
      'sms': '💬',
      'checkin': '✅',
      'seating': '🪑',
      'gift': '🎁',
      'photo': '📸',
      'music': '🎵',
      'food': '🍽️',
      'venue': '🏛️',
      'invitation': '💌',
      'calendar': '📆',
      'task': '✓',
      'report': '📊',
      'analytics': '📈',
      'export': '📤',
      'import': '📥',
      'collaborate': '🤝',
      'template': '📋',
      'custom': '⚙️',
      'automate': '⚡',
      'integrate': '🔗',
      'mobile': '📱',
      'security': '🔒',
      'support': '💬',
    };

    const titleLower = title.toLowerCase();
    for (const [key, icon] of Object.entries(iconMap)) {
      if (titleLower.includes(key)) return icon;
    }

    return '✨'; // fallback
  };

  if (!features || features.length === 0) return null;

  return (
    <section ref={sectionRef} className="relative py-24 px-6 overflow-hidden">
      {/* Background gradient orbs */}
      <div aria-hidden="true" className="absolute top-0 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl" />
      <div aria-hidden="true" className="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl" />

      <div className="relative max-w-7xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-16 max-w-3xl mx-auto">
          <div className="inline-block mb-4 px-4 py-2 rounded-full bg-blue-500/10 text-blue-400 text-sm font-medium">
            Everything You Need
          </div>
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
            Powerful Features for Modern Wedding Planners
          </h2>
          <p className="text-lg text-slate-400">
            Stop juggling multiple tools. Everything you need to manage weddings professionally in one platform.
          </p>
        </div>

        {/* Features grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => {
            const isVisible = visibleCards.has(index);
            const isComingSoon = feature.status === 'coming_soon';

            return (
              <div
                key={index}
                data-index={index}
                className="group relative"
                style={{
                  opacity: isVisible ? 1 : 0,
                  transform: isVisible ? 'translateY(0)' : 'translateY(30px)',
                  transition: `all 0.6s cubic-bezier(0.16, 1, 0.3, 1) ${index * 0.1}s`,
                }}
              >
                {/* Card container with gradient border effect */}
                <div className="relative h-full rounded-2xl bg-gradient-to-br from-slate-800/50 to-slate-900/50 p-[1px] backdrop-blur-sm transition-all duration-300 group-hover:from-blue-500/30 group-hover:to-purple-500/30">
                  <div className="relative h-full rounded-2xl bg-slate-900/90 p-8 backdrop-blur-xl">
                    {/* Icon */}
                    <div className="mb-6 inline-flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 text-3xl transition-transform duration-300 group-hover:scale-110 group-hover:rotate-3">
                      {getFeatureIcon(feature.title, feature.icon)}
                    </div>

                    {/* Title */}
                    <h3 className="mb-3 text-xl font-bold text-white">
                      {feature.title}
                    </h3>

                    {/* Description */}
                    <p className="text-slate-400 leading-relaxed">
                      {feature.description}
                    </p>

                    {/* Coming soon badge */}
                    {isComingSoon && (
                      <div className="mt-4 inline-block rounded-full bg-amber-500/10 px-3 py-1 text-xs font-medium text-amber-400 ring-1 ring-amber-500/20">
                        Coming Soon
                      </div>
                    )}

                    {/* Hover glow effect */}
                    <div className="absolute inset-0 -z-10 rounded-2xl bg-gradient-to-r from-blue-600/0 via-purple-600/0 to-blue-600/0 opacity-0 blur-xl transition-opacity duration-300 group-hover:opacity-100" />
                  </div>
                </div>

                {/* 3D tilt effect on hover */}
                <div
                  className="absolute inset-0 -z-20 rounded-2xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 opacity-0 blur-2xl transition-all duration-300 group-hover:opacity-70"
                  style={{
                    transform: 'translateZ(-50px)',
                  }}
                />
              </div>
            );
          })}
        </div>
      </div>

      <style jsx>{`
        @supports (transform-style: preserve-3d) {
          .group:hover {
            transform: perspective(1000px) rotateX(2deg) rotateY(-2deg);
          }
        }
      `}</style>
    </section>
  );
};

export default FeaturesSection;
