'use client';

import React, { useEffect, useRef, useState } from 'react';

interface HowItWorksSectionProps {
  theme?: {
    primary_color?: string;
    secondary_color?: string;
  };
}

const steps = [
  {
    number: '01',
    title: 'Import Your Clients',
    description: 'Upload guest lists from Excel/CSV or create them from scratch. Bulk import saves hours of manual data entry.',
    icon: '📥',
    visual: 'upload',
  },
  {
    number: '02',
    title: 'Build Custom Forms',
    description: 'Create RSVP forms, vendor questionnaires, and custom surveys with our drag-and-drop builder. No coding required.',
    icon: '📝',
    visual: 'forms',
  },
  {
    number: '03',
    title: 'Automate Communication',
    description: 'Send email and SMS reminders automatically. Set up workflows once and let the platform handle guest touchpoints.',
    icon: '⚡',
    visual: 'automation',
  },
  {
    number: '04',
    title: 'Track Everything Live',
    description: 'Monitor RSVPs, vendor status, budgets, and timelines in real-time. All your weddings in one beautiful dashboard.',
    icon: '📊',
    visual: 'dashboard',
  },
];

export const HowItWorksSection: React.FC<HowItWorksSectionProps> = ({ theme }) => {
  const sectionRef = useRef<HTMLElement>(null);
  const [visibleSteps, setVisibleSteps] = useState<Set<number>>(new Set());
  const [activeStep, setActiveStep] = useState<number>(0);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const index = parseInt(entry.target.getAttribute('data-step') || '0');
            setVisibleSteps((prev) => new Set([...prev, index]));
          }
        });
      },
      { threshold: 0.3, rootMargin: '0px' }
    );

    const stepElements = sectionRef.current?.querySelectorAll('[data-step]');
    stepElements?.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, []);

  // Auto-cycle active step for visual interest
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % steps.length);
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  return (
    <section ref={sectionRef} className="relative py-24 px-6 overflow-hidden">
      {/* Background elements */}
      <div aria-hidden="true" className="absolute top-1/2 left-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl -translate-y-1/2" />
      <div aria-hidden="true" className="absolute top-1/2 right-0 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl -translate-y-1/2" />

      <div className="relative max-w-7xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-20 max-w-3xl mx-auto">
          <div className="inline-block mb-4 px-4 py-2 rounded-full bg-emerald-500/10 text-emerald-400 text-sm font-medium">
            Simple 4-Step Process
          </div>
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
            From Setup to Success in Minutes
          </h2>
          <p className="text-lg text-slate-400">
            Our proven workflow helps wedding planners go from chaos to complete control—fast.
          </p>
        </div>

        {/* Steps workflow */}
        <div className="relative">
          {/* Connecting line - shows progression */}
          <div className="absolute top-16 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500/20 via-purple-500/20 to-emerald-500/20 hidden lg:block" />

          {/* Animated progress line */}
          <div
            className="absolute top-16 left-0 h-0.5 bg-gradient-to-r from-blue-500 via-purple-500 to-emerald-500 hidden lg:block transition-all duration-1000 ease-out"
            style={{ width: `${(activeStep / (steps.length - 1)) * 100}%` }}
          />

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 lg:gap-6 relative">
            {steps.map((step, index) => {
              const isVisible = visibleSteps.has(index);
              const isActive = activeStep === index;

              return (
                <div
                  key={index}
                  data-step={index}
                  className="relative group"
                  style={{
                    opacity: isVisible ? 1 : 0,
                    transform: isVisible ? 'translateY(0)' : 'translateY(40px)',
                    transition: `all 0.7s cubic-bezier(0.16, 1, 0.3, 1) ${index * 0.15}s`,
                  }}
                  onMouseEnter={() => setActiveStep(index)}
                >
                  {/* Step number indicator */}
                  <div className="relative mb-8">
                    <div
                      className={`w-12 h-12 mx-auto rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300 ${
                        isActive
                          ? 'bg-gradient-to-br from-blue-500 to-purple-500 text-white scale-110 shadow-lg shadow-blue-500/50'
                          : 'bg-slate-800 text-slate-400 group-hover:bg-slate-700 group-hover:text-white'
                      }`}
                    >
                      {step.number}
                    </div>

                    {/* Connection dot for line */}
                    <div
                      className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-4 h-4 rounded-full transition-all duration-300 ${
                        isActive ? 'bg-blue-500 scale-150' : 'bg-slate-700 scale-100'
                      }`}
                    />
                  </div>

                  {/* Icon */}
                  <div className="text-5xl mb-4 text-center transition-transform duration-300 group-hover:scale-110">
                    {step.icon}
                  </div>

                  {/* Content */}
                  <div className="text-center">
                    <h3 className="text-xl font-bold text-white mb-3 group-hover:text-blue-400 transition-colors duration-300">
                      {step.title}
                    </h3>
                    <p className="text-slate-400 text-sm leading-relaxed">
                      {step.description}
                    </p>
                  </div>

                  {/* Hover glow effect */}
                  <div
                    className={`absolute -inset-4 rounded-2xl bg-gradient-to-b from-blue-500/0 via-purple-500/5 to-blue-500/0 opacity-0 transition-opacity duration-300 -z-10 ${
                      isActive ? 'opacity-100' : 'group-hover:opacity-100'
                    }`}
                  />
                </div>
              );
            })}
          </div>
        </div>

        {/* Bottom CTA */}
        <div className="mt-16 text-center">
          <p className="text-slate-400 mb-6">Ready to streamline your wedding planning?</p>
          <div className="inline-flex items-center gap-2 text-blue-400 font-medium group cursor-pointer">
            <span className="group-hover:text-blue-300 transition-colors">Watch 2-min demo</span>
            <svg
              className="w-5 h-5 group-hover:translate-x-1 transition-transform"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
            </svg>
          </div>
        </div>
      </div>
    </section>
  );
};

export default HowItWorksSection;
