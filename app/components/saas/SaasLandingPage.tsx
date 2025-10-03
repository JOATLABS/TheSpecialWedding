'use client';

import React, { useState, useEffect } from 'react';
import { Modern3DBackground } from '../landing-page/Modern3DBackground';
import { SectionWrapper } from '../landing-page/SectionWrapper';
import { GlassCard } from '../ui/GlassCard';
import { SaasAuthPanel, SaasHeroSection } from './SaasHeroSection';
import { FeatureCarousel } from './FeatureCarousel';
import { BenefitsSection } from './BenefitsSection';
import { TestimonialsSection } from './TestimonialsSection';
import { CallToActionSection } from './CallToActionSection';
import { PricingSection } from './PricingSection';

interface Feature {
  title: string;
  description: string;
  icon?: string;
  status: 'available' | 'coming_soon';
  order: number;
}

interface Benefit {
  title: string;
  description: string;
  icon?: string;
  order: number;
}

interface Testimonial {
  name: string;
  company: string;
  role: string;
  content: string;
  avatar_url?: string;
  order: number;
}

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
  features: Feature[];
  benefits: Benefit[];
  testimonials: Testimonial[];
  background_image?: string;
  fallback_images: string[];
  features_enabled: boolean;
  benefits_enabled: boolean;
  testimonials_enabled: boolean;
  statistics_enabled: boolean;
  demo_url?: string;
  primary_color: string;
  secondary_color: string;
}

export const SaasLandingPage: React.FC = () => {
  const [authMode, setAuthMode] = useState<'signup' | 'login'>('signup');
  const [selectedPlan, setSelectedPlan] = useState<{ id: string; name?: string } | null>(null);
  const [config, setConfig] = useState<SaasConfig>({
    hero_title: "Welcome to Special Wedding",
    hero_subtitle: "Wedding Planning Made Simple",
    hero_description: "The ultimate wedding planning platform for professional wedding planners. Manage multiple weddings, coordinate with vendors, and create beautiful wedding websites with AI-powered tools.",
    hero_cta_primary: "Start Free Trial",
    hero_cta_secondary: "Watch Demo",
    trust_indicators: ["Free 30-day trial", "No setup fees", "Cancel anytime"],
    statistics: [
      { label: "Wedding Planners Trust Us", value: "500+" },
      { label: "Weddings Managed", value: "10K+" },
      { label: "Uptime Guarantee", value: "99.9%" }
    ],
    features: [
      {
        title: "Complete Wedding Management",
        description: "Manage multiple weddings with ease. Track guests, RSVPs, vendors, and timelines all in one place.",
        status: "available" as const,
        order: 1
      },
      {
        title: "Vendor Collaboration",
        description: "Give vendors access to update their portions of the wedding checklist and collaborate seamlessly.",
        status: "available" as const,
        order: 2
      },
      {
        title: "Beautiful Wedding Websites",
        description: "Create stunning, customizable wedding websites for each couple with our easy-to-use builder.",
        status: "available" as const,
        order: 3
      },
      {
        title: "RSVP & Guest Management",
        description: "Streamline guest management with advanced RSVP tracking, meal preferences, and seating arrangements.",
        status: "available" as const,
        order: 4
      },
      {
        title: "AI Presentation Generator",
        description: "Create stunning wedding presentations in minutes with our AI-powered design tools.",
        status: "coming_soon" as const,
        order: 5
      },
      {
        title: "Smart Email Assistant",
        description: "Send professional emails with embedded reports and updates using AI-generated content.",
        status: "coming_soon" as const,
        order: 6
      },
      {
        title: "Budget Optimization Engine",
        description: "Calculate optimal spending for maximum impact on your client's special day with AI insights.",
        status: "coming_soon" as const,
        order: 7
      },
      {
        title: "Design Research AI",
        description: "Get color palettes, themes, and design inspiration tailored to your clients' preferences.",
        status: "coming_soon" as const,
        order: 8
      }
    ],
    benefits: [
      {
        title: "Save Time",
        description: "Automate repetitive tasks and streamline wedding planning operations",
        order: 1
      },
      {
        title: "Scale Your Business",
        description: "Manage multiple weddings efficiently and grow your planning business",
        order: 2
      },
      {
        title: "Delight Clients",
        description: "Provide exceptional service with professional tools and beautiful deliverables",
        order: 3
      },
      {
        title: "Increase Revenue",
        description: "Take on more clients and command premium pricing with our platform",
        order: 4
      }
    ],
    testimonials: [
      {
        name: "Sarah Johnson",
        company: "Elegant Events Planning",
        role: "Senior Wedding Planner",
        content: "Special Wedding has revolutionized how I manage my clients' weddings. The AI tools save me hours every week!",
        order: 1
      },
      {
        name: "Michael Chen",
        company: "Dream Day Weddings",
        role: "Wedding Coordinator",
        content: "The vendor collaboration features are game-changing. Everyone stays on the same page effortlessly.",
        order: 2
      },
      {
        name: "Emily Rodriguez",
        company: "Perfect Moments",
        role: "Lead Planner",
        content: "My clients love their custom wedding websites, and I love how easy they are to create and manage.",
        order: 3
      }
    ],
    fallback_images: [
      "/wedding-images/wedding-ceremony.jpg",
      "/wedding-images/wedding-reception.jpg",
      "/wedding-images/wedding-couple.jpg"
    ],
    features_enabled: true,
    benefits_enabled: true,
    testimonials_enabled: true,
    statistics_enabled: true,
    demo_url: process.env.NEXT_PUBLIC_SAAS_DEMO_URL || "https://demo.thespecialwedding.com",
    primary_color: process.env.NEXT_PUBLIC_DEFAULT_PRIMARY_COLOR || "#1e3a5f",
    secondary_color: process.env.NEXT_PUBLIC_DEFAULT_SECONDARY_COLOR || "#d4af37"
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSaasConfig();
  }, []);

  const fetchSaasConfig = async () => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/saas/config`);
      if (response.ok) {
        const data = await response.json();
        setConfig(prev => ({ ...prev, ...data }));
      }
    } catch (error) {
      // Failed to load SAAS config - will use defaults
    } finally {
      setLoading(false);
    }
  };

  const scrollToAuthPanel = () => {
    if (typeof document === 'undefined') {
      return;
    }
    const panel = document.getElementById('saas-auth-panel');
    panel?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  const handlePlanSelect = (plan: { id: string; name?: string }) => {
    setSelectedPlan(plan);
    setAuthMode('signup');
    scrollToAuthPanel();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-emerald-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  const theme = {
    primary_color: config.primary_color,
    secondary_color: config.secondary_color,
    accent_color: config.secondary_color,
    background_style: 'gradient' as const,
    font_style: 'elegant' as const
  };

  return (
    <div className="relative min-h-screen">
      <Modern3DBackground
        imageUrl={config.background_image}
        fallbackImages={config.fallback_images}
        theme={theme}
      />

      <div className="relative z-10">
        <div className="mx-auto flex w-full max-w-[1640px] flex-col gap-12 px-4 pb-16 pt-12 sm:px-6 lg:grid lg:grid-cols-[minmax(0,1fr)_420px] lg:items-start lg:gap-14 lg:px-12 xl:px-16">
          <aside
            id="saas-auth-panel"
            className="order-1 -mx-1 rounded-[2.75rem] border border-white/40 bg-white/30 p-1 backdrop-blur-3xl sm:mx-0 lg:order-2 lg:sticky lg:top-16 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto lg:p-2 lg:pl-3 lg:pr-3 lg:[scrollbar-width:none] lg:[&::-webkit-scrollbar]:hidden"
          >
            <div className="rounded-[2.5rem] border border-white/40 bg-white/40 p-2 shadow-[0_25px_80px_-45px_rgba(15,23,42,0.45)]">
              <SaasAuthPanel
                mode={authMode}
                onModeChange={(mode) => {
                  setAuthMode(mode);
                  if (mode === 'signup') {
                    scrollToAuthPanel();
                  }
                }}
                selectedPlan={selectedPlan}
                theme={theme}
              />
            </div>
          </aside>

          <div className="order-2 flex flex-col gap-16 lg:order-1 lg:pr-4 xl:pr-8">
            <SaasHeroSection
              config={config}
              theme={theme}
              onAuthModeChange={(mode) => {
                setAuthMode(mode);
                if (mode === 'signup') {
                  scrollToAuthPanel();
                }
              }}
              onRequestSignupFocus={scrollToAuthPanel}
            />

            {config.features_enabled && (
              <SectionWrapper id="features" glassEffect={false}>
                <div className="mx-auto w-full max-w-4xl xl:max-w-none">
                  <GlassCard depth="mid" className="rounded-[2.5rem] border border-white/50 bg-white/55 p-8 shadow-xl">
                    <FeatureCarousel features={config.features} theme={theme} />
                  </GlassCard>
                </div>
              </SectionWrapper>
            )}

            {config.benefits_enabled && (
              <SectionWrapper id="benefits" glassEffect={false}>
                <div className="mx-auto w-full max-w-4xl xl:max-w-none">
                  <BenefitsSection benefits={config.benefits} theme={theme} />
                </div>
              </SectionWrapper>
            )}

            {config.testimonials_enabled && (
              <SectionWrapper id="testimonials" glassEffect={false}>
                <div className="mx-auto w-full max-w-4xl xl:max-w-none">
                  <TestimonialsSection testimonials={config.testimonials} theme={theme} />
                </div>
              </SectionWrapper>
            )}

            <SectionWrapper id="pricing" glassEffect={false}>
              <PricingSection theme={theme} onPlanSelect={handlePlanSelect} />
            </SectionWrapper>

            <SectionWrapper id="sign-up" glassEffect={false}>
              <div className="mx-auto w-full max-w-3xl xl:max-w-none">
                <CallToActionSection
                  config={config}
                  theme={theme}
                  onGetStarted={() => {
                    setAuthMode('signup');
                    scrollToAuthPanel();
                  }}
                />
              </div>
            </SectionWrapper>
          </div>
        </div>
      </div>
    </div>
  );
};