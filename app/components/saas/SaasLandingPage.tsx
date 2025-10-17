'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Modern3DBackground } from '../landing-page/Modern3DBackground';
import { SaasHeroSection } from './SaasHeroSection';
import { ModernHeroSection } from './ModernHeroSection';
import { IntegratedHeroSection } from './IntegratedHeroSection';
import { PlannerAuthSection, SubscriptionPlan } from './PlannerAuthSection';
import { PlannerAuthModal } from './PlannerAuthModal';
import { SaasExperienceCarousel } from './SaasExperienceCarousel';
import ContactSalesModal from './ContactSalesModal';
import { fetchWithTimeout, resolveApiUrl } from './apiClient';

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
  contact_cta_label?: string;
  contact_url?: string;
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
  // Modern hero fields
  show_decorative_logo?: boolean;
  hero_headline?: string;
  hero_subheadline?: string;
  hero_problem_statement?: string;
  hero_solution_statement?: string;
  hero_screenshot_primary?: string;
}

export const SaasLandingPage: React.FC = () => {
  const [authMode, setAuthMode] = useState<'signup' | 'login'>('signup');
  const [selectedPlan, setSelectedPlan] = useState<{ id: string; name?: string } | null>(null);
  const [planNotice, setPlanNotice] = useState('');
  const [config, setConfig] = useState<SaasConfig>({
    hero_title: "Welcome to Special Wedding",
    hero_subtitle: "Wedding Planning Made Simple",
    hero_description: "The ultimate wedding planning platform for professional wedding planners. Manage multiple weddings, coordinate with vendors, and create beautiful wedding websites with AI-powered tools.",
    hero_cta_primary: "Start Free Trial",
    hero_cta_secondary: "Watch Demo",
    contact_cta_label: 'Contact Sales',
    contact_url: process.env.NEXT_PUBLIC_CONTACT_URL || 'mailto:sales@specialwedding.com',
    trust_indicators: ["Free 30-day trial", "No setup fees", "Cancel anytime"],
    // Modern hero defaults
    show_decorative_logo: false, // Use modern design by default
    hero_headline: "Manage 10+ Weddings Simultaneously",
    hero_subheadline: "For Professional Wedding Planners",
    hero_problem_statement: "Stop juggling spreadsheets, email chains, and vendor chaos",
    hero_solution_statement: "One platform to manage guests, vendors, timelines, and budgets—all in sync",
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
  const [planLoading, setPlanLoading] = useState(true);
  const [planError, setPlanError] = useState('');
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [isContactOpen, setIsContactOpen] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [useIntegratedHero, setUseIntegratedHero] = useState(true); // New integrated design by default

  const defaultPlans: SubscriptionPlan[] = useMemo(
    () => [
      {
        _id: 'studio-growth',
        name: 'Studio Growth',
        description: 'Everything established planners need for 10 active weddings.',
        price_monthly: 179,
        price_yearly: 1890,
        is_featured: true,
        is_active: true,
        display_order: 1,
      },
      {
        _id: 'signature',
        name: 'Signature',
        description: 'Collaborate with unlimited vendors and automate client touchpoints.',
        price_monthly: 289,
        price_yearly: 3090,
        is_featured: false,
        is_active: true,
        display_order: 2,
      },
      {
        _id: 'boutique',
        name: 'Boutique',
        description: 'For new planners onboarding their first 3 weddings with concierge support.',
        price_monthly: 89,
        price_yearly: 930,
        is_featured: false,
        is_active: true,
        display_order: 0,
      },
    ],
    []
  );

  const resolveApiUrl = useCallback((path: string) => {
    const configuredBase = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, '');
    if (configuredBase) {
      return `${configuredBase}${path}`;
    }
    return path;
  }, []);

  const fetchWithTimeout = useCallback(
    async (input: RequestInfo | URL, init?: RequestInit, timeoutMs = 8000) => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch(input, {
          ...init,
          signal: controller.signal,
        });
        return response;
      } finally {
        clearTimeout(timer);
      }
    },
    []
  );

  const fetchSaasConfig = useCallback(async () => {
    try {
      const response = await fetchWithTimeout(resolveApiUrl('/saas/config'));
      if (response.ok) {
        const data = await response.json();
        setConfig(prev => ({ ...prev, ...data }));
      }
    } catch (error) {
      // Failed to load SAAS config - will use defaults
    } finally {
      setLoading(false);
    }
  }, [fetchWithTimeout, resolveApiUrl]);

  const fetchSubscriptionPlans = useCallback(async () => {
    let resolvedPlans: SubscriptionPlan[] | null = null;
    try {
      const response = await fetchWithTimeout(resolveApiUrl('/public/subscription-plans'));

      if (response.ok) {
        const data = await response.json();
        const activePlans: SubscriptionPlan[] = (Array.isArray(data) ? data : [])
          .filter((plan: SubscriptionPlan) => plan.is_active)
          .sort((a: SubscriptionPlan, b: SubscriptionPlan) => {
            const orderA = typeof a.display_order === 'number' ? a.display_order : Number.MAX_SAFE_INTEGER;
            const orderB = typeof b.display_order === 'number' ? b.display_order : Number.MAX_SAFE_INTEGER;
            if (orderA !== orderB) {
              return orderA - orderB;
            }
            if (a.is_featured && !b.is_featured) return -1;
            if (!a.is_featured && b.is_featured) return 1;
            return a.name.localeCompare(b.name);
          });
        if (activePlans.length > 0) {
          resolvedPlans = activePlans;
          setPlans(activePlans);
          setPlanError('');
          setPlanNotice('');
          return;
        }
      } else {
        console.warn('Received non-ok response when loading subscription plans', response.statusText);
      }
    } catch (error) {
      console.error('Failed to load subscription plans', error);
    } finally {
      if (!resolvedPlans) {
        setPlans(defaultPlans);
        setPlanError('');
        setPlanNotice('Showing signature tiers while live pricing reconnects. Your selections will sync during onboarding.');
      }
      setPlanLoading(false);
    }
  }, [defaultPlans, fetchWithTimeout, resolveApiUrl]);

  useEffect(() => {
    fetchSaasConfig();
  }, [fetchSaasConfig]);

  useEffect(() => {
    fetchSubscriptionPlans();
  }, [fetchSubscriptionPlans]);

  const scrollToAuthPanel = () => {
    if (typeof document === 'undefined') {
      return;
    }
    const panel = document.getElementById('planner-auth-section');
    if (panel) {
      panel.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    if (typeof window !== 'undefined') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  useEffect(() => {
    if (!planLoading && plans.length > 0 && !selectedPlan) {
      const featuredPlan = plans.find((plan) => plan.is_featured) ?? plans[0];
      setSelectedPlan({ id: featuredPlan._id, name: featuredPlan.name });
    }
  }, [planLoading, plans, selectedPlan]);

  const condensedPlans = useMemo(() => plans.slice(0, 4), [plans]);

  const handleContactOpen = useCallback(() => {
    setIsContactOpen(true);
  }, []);

  const handleContactClose = useCallback(() => {
    setIsContactOpen(false);
  }, []);

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
    <div className="relative min-h-screen bg-slate-950 text-slate-900">
      {/* Use integrated hero by default, fall back to old layout if disabled */}
      {useIntegratedHero ? (
        <>
          {/* New integrated hero with everything built-in */}
          <IntegratedHeroSection
            config={config}
            plans={plans}
            onAuthModalOpen={() => {
              setAuthMode('signup');
              setIsAuthModalOpen(true);
            }}
          />

          {/* Optional: Add FAQ or footer sections below hero if needed */}
        </>
      ) : (
        <>
          <Modern3DBackground imageUrl={config.background_image} fallbackImages={config.fallback_images} theme={theme} />

          <div className="relative z-10">
            <div className="mx-auto flex w-full max-w-7xl flex-col gap-16 px-4 pb-16 pt-12 sm:px-6 lg:px-8 lg:pb-24 lg:pt-16 xl:px-12">
              <div className="grid gap-12 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)] xl:gap-16 xl:items-start">
                {config.show_decorative_logo !== false ? (
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
                    onContactClick={handleContactOpen}
                    className="lg:px-0 lg:py-0"
                  />
                ) : (
                  <ModernHeroSection
                    config={config}
                    onAuthModeChange={(mode) => {
                      setAuthMode(mode);
                      if (mode === 'signup') {
                        scrollToAuthPanel();
                      }
                    }}
                    onRequestSignupFocus={scrollToAuthPanel}
                    className="lg:col-span-2"
                  />
                )}

                <div id="planner-auth-section" className="flex flex-col gap-8 lg:sticky lg:top-16">
                  <PlannerAuthSection
                    mode={authMode}
                    onModeChange={(mode) => {
                      setAuthMode(mode);
                      if (mode === 'signup') {
                        scrollToAuthPanel();
                      }
                    }}
                    theme={theme}
                    plans={condensedPlans}
                    plansLoading={planLoading}
                    plansError={planError}
                    plansNotice={planNotice}
                    selectedPlan={selectedPlan}
                    onSelectPlan={(plan) => {
                      setSelectedPlan(plan);
                      setAuthMode('signup');
                      scrollToAuthPanel();
                    }}
                    className="shadow-[0_28px_120px_-45px_rgba(15,23,42,0.4)]"
                  />

                  {planError && !planLoading && (
                    <div className="rounded-3xl border border-red-200/80 bg-red-50/80 px-4 py-3 text-sm text-red-700 shadow-sm backdrop-blur">
                      {planError}
                    </div>
                  )}

                  {(config.features_enabled || config.benefits_enabled || config.testimonials_enabled) && (
                    <div className="hidden lg:block">
                      <div className="relative overflow-hidden rounded-[2.75rem] border border-white/30 bg-white/25 p-[1px] shadow-[0_30px_90px_-50px_rgba(15,23,42,0.55)] backdrop-blur-2xl">
                        <div
                          aria-hidden="true"
                          className="pointer-events-none absolute inset-0 rounded-[2.75rem] bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.6),transparent_60%)]"
                        />
                        <div className="relative rounded-[2.6rem] bg-white/75 px-6 py-8 xl:px-8 xl:py-10">
                          <SaasExperienceCarousel
                            features={config.features}
                            benefits={config.benefits}
                            testimonials={config.testimonials}
                            theme={theme}
                          />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {(config.features_enabled || config.benefits_enabled || config.testimonials_enabled) && (
                <section aria-labelledby="experience-showcase" className="lg:hidden">
                  <div className="relative overflow-hidden rounded-[2.75rem] border border-white/30 bg-white/20 p-[1px] shadow-[0_25px_80px_-45px_rgba(15,23,42,0.45)] backdrop-blur-2xl">
                    <div
                      aria-hidden="true"
                      className="pointer-events-none absolute inset-0 rounded-[2.75rem] bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.55),transparent_60%)]"
                    />
                    <div className="relative rounded-[2.6rem] bg-white/70 px-5 py-8 sm:px-7 sm:py-9">
                      <SaasExperienceCarousel
                        features={config.features}
                        benefits={config.benefits}
                        testimonials={config.testimonials}
                        theme={theme}
                      />
                    </div>
                  </div>
                </section>
              )}
            </div>
          </div>
        </>
      )}

      {/* Auth modal - opens when any CTA is clicked */}
      <PlannerAuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        mode={authMode}
        onModeChange={setAuthMode}
        theme={theme}
        plans={condensedPlans}
        plansLoading={planLoading}
        plansError={planError}
        plansNotice={planNotice}
        selectedPlan={selectedPlan}
        onSelectPlan={(plan) => {
          setSelectedPlan(plan);
          setAuthMode('signup');
        }}
      />

      <ContactSalesModal isOpen={isContactOpen} onClose={handleContactClose} theme={theme} />
    </div>
  );
};