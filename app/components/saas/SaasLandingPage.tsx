'use client';

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { IntegratedHeroSection } from './IntegratedHeroSection';
import { PlannerAuthModal } from './PlannerAuthModal';
import ContactSalesModal from './ContactSalesModal';
import { SubscriptionPlan } from './PlannerAuthSection';
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
  impact_metrics?: Array<{
    metric: string;
    label: string;
    icon?: string;
  }>;
  customer_logos?: Array<{
    name: string;
    logo_url?: string;
  }>;
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
  animation_speed?: 'fast' | 'medium' | 'slow';
  animations_enabled?: boolean;
  scroll_animations?: boolean;
  show_impact_metrics?: boolean;
  show_customer_logos?: boolean;
  hero_image_position?: 'left' | 'right';
  hero_layout?: string;
  workflow_steps?: Array<{
    title: string;
    description: string;
    badge?: string;
  }>;
  faqs?: Array<{
    question: string;
    answer: string;
  }>;
  theme?: {
    primary_color: string;
    secondary_color: string;
    fallback_images?: string[];
    background_style?: 'gradient' | 'solid' | 'image';
    font_style?: 'elegant' | 'modern' | 'classic' | 'playful';
  };
}

const DEFAULT_WORKFLOW_STEPS = [
  {
    title: 'Discovery & onboarding',
    description: 'Collect couple questionnaires, import spreadsheets, and set expectations in minutes.',
    badge: 'Week 1',
  },
  {
    title: 'Vendor alignment',
    description: 'Invite vendors to collaborative timelines with guardrails so every deliverable has an owner.',
    badge: 'Week 2',
  },
  {
    title: 'Guest communication',
    description: 'Centralize RSVPs, table assignments, and messaging without endless email threads.',
    badge: 'Week 3',
  },
  {
    title: 'Event execution',
    description: 'Run the wedding from live dashboards that surface contingencies before they become fire drills.',
    badge: 'Wedding week',
  },
];

const DEFAULT_FAQS = [
  {
    question: 'How quickly can I onboard my team?',
    answer:
      'Most planners launch their first collaborative workspace within a week. We include guided templates and concierge migration for legacy spreadsheets.',
  },
  {
    question: 'Do you support client-facing wedding websites?',
    answer:
      'Yes. Every plan includes customizable wedding microsites with RSVP tracking, gallery support, and password protection.',
  },
  {
    question: 'Can vendors access only their assigned tasks?',
    answer:
      'Role-based permissions keep vendor updates scoped to their deliverables while giving you full visibility and audit logs.',
  },
];

export const SaasLandingPage: React.FC = () => {
  const [authMode, setAuthMode] = useState<'signup' | 'login'>('signup');
  const [selectedPlan, setSelectedPlan] = useState<{ id: string; name?: string } | null>(null);
  const [planNotice, setPlanNotice] = useState('');
  const [config, setConfig] = useState<SaasConfig>({
    hero_title: "Welcome to Special Wedding",
    hero_subtitle: "Wedding Planning Made Simple",
    hero_description: "The ultimate wedding planning platform for professional wedding planners. Manage multiple weddings, coordinate with vendors, and create beautiful wedding websites with AI-powered tools.",
    hero_cta_primary: "Start Free Trial",
    contact_cta_label: 'Contact Sales',
    contact_url: process.env.NEXT_PUBLIC_CONTACT_URL || 'mailto:sales@specialwedding.com',
    trust_indicators: ["Free 30-day trial", "No setup fees", "Cancel anytime"],
    // Modern hero defaults
    show_decorative_logo: false, // Use modern design by default
    hero_headline: "Manage 10+ Weddings Simultaneously",
    hero_subheadline: "For Professional Wedding Planners",
    hero_problem_statement: "Stop juggling spreadsheets, email chains, and vendor chaos",
    hero_solution_statement: "One platform to manage guests, vendors, timelines, and budgets—all in sync",
    workflow_steps: [
      {
        title: 'Discovery & onboarding',
        description: 'Collect couple questionnaires, import spreadsheets, and set expectations in minutes.',
        badge: 'Week 1',
      },
      {
        title: 'Vendor alignment',
        description: 'Invite vendors to collaborative timelines with guardrails so every deliverable has an owner.',
        badge: 'Week 2',
      },
      {
        title: 'Guest communication',
        description: 'Centralize RSVPs, table assignments, and messaging without endless email threads.',
        badge: 'Week 3',
      },
    {
      title: 'Event execution',
      description: 'Run the wedding from live dashboards that surface contingencies before they become fire drills.',
      badge: 'Wedding week',
    },
  ],
  faqs: [
    {
      question: 'How quickly can I onboard my team?',
      answer:
        'Most planners launch their first collaborative workspace within a week. We include guided templates and concierge migration for legacy spreadsheets.',
      },
      {
        question: 'Do you support client-facing wedding websites?',
        answer:
          'Yes. Every plan includes customizable wedding microsites with RSVP tracking, gallery support, and password protection.',
      },
      {
        question: 'Can vendors access only their assigned tasks?',
        answer:
          'Role-based permissions keep vendor updates scoped to their deliverables while giving you full visibility and audit logs.',
      },
    ],
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
    demo_url: process.env.NEXT_PUBLIC_SAAS_DEMO_URL || "",
    primary_color: process.env.NEXT_PUBLIC_DEFAULT_PRIMARY_COLOR || "#1e3a5f",
    secondary_color: process.env.NEXT_PUBLIC_DEFAULT_SECONDARY_COLOR || "#d4af37"
  });
  const [loading, setLoading] = useState(true);
  const [planLoading, setPlanLoading] = useState(true);
  const [planError, setPlanError] = useState('');
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [isContactOpen, setIsContactOpen] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const initialPlanSet = useRef(false);  // Track if initial plan selection has been made

  const defaultPlans: SubscriptionPlan[] = useMemo(
    () => [
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
  }, []);

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
  }, [defaultPlans]);

  useEffect(() => {
    fetchSaasConfig();
  }, [fetchSaasConfig]);

  useEffect(() => {
    fetchSubscriptionPlans();
  }, [fetchSubscriptionPlans]);

  useEffect(() => {
    // Only set initial plan once to prevent race condition with user selections
    if (!planLoading && plans.length > 0 && !initialPlanSet.current) {
      const featuredPlan = plans.find((plan) => plan.is_featured) ?? plans[0];
      setSelectedPlan({ id: featuredPlan._id, name: featuredPlan.name });
      initialPlanSet.current = true;
    }
  }, [planLoading, plans]);

  const condensedPlans = useMemo(() => (Array.isArray(plans) ? plans : []).slice(0, 4), [plans]);

  const orderedFeatures = useMemo(() => {
    const features = Array.isArray(config.features) ? config.features : [];
    return [...features].sort((a, b) => a.order - b.order);
  }, [config.features]);

  const orderedBenefits = useMemo(() => {
    const benefits = Array.isArray(config.benefits) ? config.benefits : [];
    return [...benefits].sort((a, b) => a.order - b.order);
  }, [config.benefits]);

  const orderedTestimonials = useMemo(() => {
    const testimonials = Array.isArray(config.testimonials) ? config.testimonials : [];
    return [...testimonials].sort((a, b) => a.order - b.order);
  }, [config.testimonials]);

  const statistics = useMemo(() => {
    if (config.statistics_enabled === false) {
      return [] as SaasConfig['statistics'];
    }
    const stats = Array.isArray(config.statistics) ? config.statistics : [];
    return stats.slice(0, 3);
  }, [config.statistics, config.statistics_enabled]);

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
    primary_color: config.primary_color || config.theme?.primary_color || "#1e3a5f",
    secondary_color: config.secondary_color || config.theme?.secondary_color || "#d4af37",
    accent_color: config.secondary_color,
    background_style: 'gradient' as const,
    font_style: 'elegant' as const,
  };

  const animationsEnabled = config.animations_enabled !== false && config.scroll_animations !== false;
  const themingEnabled = Boolean(
    config.primary_color ||
    config.secondary_color ||
    config.theme?.primary_color ||
    config.theme?.secondary_color ||
    config.hero_layout ||
    config.hero_image_position
  );
  const animationSpeedMs =
    !animationsEnabled ? 0 :
    config.animation_speed === 'fast' ? 200 :
    config.animation_speed === 'slow' ? 600 :
    400;
  const transitionStyle: React.CSSProperties | undefined = animationsEnabled
    ? { transitionDuration: `${animationSpeedMs}ms` }
    : undefined;

  const workflow = (config.workflow_steps && config.workflow_steps.length > 0)
    ? config.workflow_steps
    : DEFAULT_WORKFLOW_STEPS;

  const faqs = (config.faqs && config.faqs.length > 0)
    ? config.faqs
    : DEFAULT_FAQS;

  return (
    <div
      className="relative min-h-screen overflow-hidden bg-slate-950 text-slate-100"
      style={transitionStyle}
    >
      <IntegratedHeroSection
        config={config}
        plans={plans}
        onAuthModalOpen={() => {
          setAuthMode('signup');
          setIsAuthModalOpen(true);
        }}
        animationSpeedMs={animationSpeedMs}
        themeColors={{ primary: theme.primary_color, secondary: theme.secondary_color }}
        useTheming={themingEnabled}
      />

      <div className="relative -mt-24 rounded-t-[3rem] bg-gradient-to-b from-white via-slate-50 to-slate-100 text-slate-900 shadow-[0_-60px_120px_-80px_rgba(15,23,42,0.7)]">
        <main className="relative z-10 mx-auto flex w-full max-w-6xl flex-col gap-24 px-4 pb-28 pt-28 sm:px-6 lg:px-8">
          {config.show_impact_metrics && (config.impact_metrics?.length ?? 0) > 0 && (
            <section className="grid gap-4 rounded-[2rem] border border-slate-200/80 bg-white p-8 shadow-[0_40px_120px_-70px_rgba(15,23,42,0.35)]" style={transitionStyle}>
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Impact metrics</p>
                  <h2 className="text-2xl font-semibold text-slate-900">Measurable outcomes your team can feel</h2>
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {config.impact_metrics?.map((metric, idx) => (
                  <article key={`${metric.metric}-${idx}`} className="rounded-2xl border border-slate-200/70 bg-slate-50/80 p-5 transition hover:border-blue-200/80 hover:bg-white" style={transitionStyle}>
                    <p className="text-3xl font-bold text-slate-900">{metric.metric}</p>
                    <p className="mt-2 text-sm text-slate-600">{metric.label}</p>
                  </article>
                ))}
              </div>
            </section>
          )}

          {config.show_customer_logos && (config.customer_logos?.length ?? 0) > 0 && (
            <section className="space-y-6 rounded-[2rem] border border-slate-200/80 bg-white p-8 shadow-[0_40px_120px_-70px_rgba(15,23,42,0.35)]" style={transitionStyle}>
              <div className="text-center space-y-2">
                <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Trusted partners</p>
                <h2 className="text-2xl font-semibold text-slate-900">Planners and partners who rely on us</h2>
              </div>
              <div className="grid grid-cols-2 gap-6 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
                {config.customer_logos?.map((logo, idx) => (
                  <div key={`${logo.name}-${idx}`} className="flex items-center justify-center rounded-xl border border-slate-200/70 bg-slate-50/80 p-4 transition hover:border-blue-200/80" style={transitionStyle}>
                    {logo.logo_url ? (
                      <img src={logo.logo_url} alt={logo.name || 'Customer logo'} className="max-h-10 object-contain" loading="lazy" />
                    ) : (
                      <span className="text-sm font-medium text-slate-600">{logo.name}</span>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {config.features_enabled && orderedFeatures.length > 0 && (
            <section id="features" className="space-y-12">
              <div className="space-y-4 text-center">
                <span className="inline-flex items-center justify-center rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-900">
                  Platform capabilities
                </span>
                <h2 className="text-3xl font-semibold text-slate-900 sm:text-4xl">Command every detail from one canvas</h2>
                <p className="mx-auto max-w-2xl text-base text-slate-600">
                  Purpose-built modules cover planning workflows end-to-end so your team can focus on the moments that matter most to your couples.
                </p>
              </div>
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {orderedFeatures.slice(0, 6).map((feature) => (
                  <article
                    key={feature.title}
                    className="group flex h-full flex-col justify-between rounded-3xl border border-slate-200/80 bg-white p-6 shadow-[0_24px_90px_-60px_rgba(15,23,42,0.35)] transition hover:-translate-y-1 hover:border-blue-300/80 hover:shadow-[0_40px_120px_-70px_rgba(59,130,246,0.55)]"
                    style={transitionStyle}
                  >
                    <div className="space-y-3 text-left">
                      <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-lg text-blue-600">
                        {feature.icon ?? '✨'}
                      </div>
                      <h3 className="text-lg font-semibold text-slate-900">{feature.title}</h3>
                      <p className="text-sm leading-relaxed text-slate-600">{feature.description}</p>
                    </div>
                    <span className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-slate-900">
                      {feature.status === 'coming_soon' ? 'Coming soon' : 'Available now'}
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </span>
                  </article>
                ))}
              </div>
            </section>
          )}

          <section
            id="workflow"
            className="grid gap-10 rounded-[2.5rem] border border-slate-200/80 bg-white p-10 shadow-[0_40px_120px_-70px_rgba(15,23,42,0.35)] lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:items-center"
          >
            <div className="space-y-6">
              <span className="inline-flex items-center justify-center rounded-full bg-purple-100 px-3 py-1 text-xs font-semibold text-purple-900">
                Orchestrate end-to-end
              </span>
              <h2 className="text-3xl font-semibold text-slate-900 sm:text-4xl">An automation backbone tuned for wedding planners</h2>
              <p className="text-base text-slate-600">
                Turn your signature approach into a repeatable client journey. Each stage is mapped with templates, automations, and visibility to keep couples confident.
              </p>
              <button
                type="button"
                onClick={() => {
                  setAuthMode('signup');
                  setIsAuthModalOpen(true);
                }}
                className="inline-flex items-center justify-center rounded-full bg-slate-900 px-7 py-3 text-base font-semibold text-white shadow-[0_12px_30px_-18px_rgba(15,23,42,0.6)] transition hover:-translate-y-[1px] hover:shadow-[0_22px_50px_-28px_rgba(59,130,246,0.55)]"
              >
                Explore automations
              </button>
            </div>
            <div className="space-y-4">
              {workflow.map((step, index) => (
                <div
                  key={step.title}
                  className="flex flex-col gap-3 rounded-2xl border border-slate-200/70 bg-slate-50/80 p-5 transition hover:border-blue-200/80 hover:bg-white"
                  style={transitionStyle}
                >
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold uppercase tracking-[0.3em] text-slate-500">Step {index + 1}</p>
                    <span className="rounded-full bg-blue-100 px-3 py-1 text-[11px] font-semibold text-blue-900">{step.badge}</span>
                  </div>
                  <h3 className="text-lg font-semibold text-slate-900">{step.title}</h3>
                  <p className="text-sm text-slate-600">{step.description}</p>
                </div>
              ))}
            </div>
          </section>

          {config.benefits_enabled && orderedBenefits.length > 0 && (
            <section id="benefits" className="grid gap-12 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:items-center">
              <div className="space-y-6">
                <h2 className="text-3xl font-semibold text-slate-900 sm:text-4xl">A modern back office for premium planners</h2>
                <p className="text-base text-slate-600">
                  Translate your signature service into a reliable, repeatable system. We pair automation with human-friendly controls so nothing feels generic.
                </p>
                <div className="grid gap-4 sm:grid-cols-2">
                  {statistics.slice(0, 2).map((stat) => (
                    <div key={stat.label} className="rounded-2xl border border-slate-200/70 bg-white p-5 text-left shadow-sm">
                      <p className="text-2xl font-semibold text-slate-900">{stat.value}</p>
                      <p className="text-xs uppercase tracking-[0.3em] text-slate-500">{stat.label}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div className="grid gap-6 sm:grid-cols-2">
                {orderedBenefits.slice(0, 4).map((benefit) => (
                  <div key={benefit.title} className="rounded-3xl border border-slate-200/70 bg-white p-6 shadow-[0_20px_80px_-60px_rgba(15,23,42,0.3)]">
                    <h3 className="text-lg font-semibold text-slate-900">{benefit.title}</h3>
                    <p className="mt-2 text-sm text-slate-600">{benefit.description}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section id="pricing" className="space-y-10">
            <div className="space-y-4 text-center">
              <span className="inline-flex items-center justify-center rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
                Pricing built for momentum
              </span>
              <h2 className="text-3xl font-semibold text-slate-900 sm:text-4xl">Plans that scale with every celebration</h2>
              <p className="mx-auto max-w-2xl text-base text-slate-600">
                Flexible pricing helps boutique studios through enterprise teams orchestrate unforgettable weddings without messy add-ons.
              </p>
            </div>
            <div className="grid gap-6 lg:grid-cols-3">
              {plans.slice(0, 3).map((plan) => (
                <article
                  key={plan._id}
                  className={`flex h-full flex-col rounded-3xl border border-slate-200/80 bg-white p-6 shadow-[0_30px_110px_-70px_rgba(15,23,42,0.35)] transition hover:-translate-y-1 hover:border-blue-300/80 hover:shadow-[0_50px_140px_-80px_rgba(59,130,246,0.5)] ${
                    plan.is_featured ? 'lg:scale-[1.01] lg:border-blue-400/80' : ''
                  }`}
                >
                  <div className="flex items-baseline justify-between text-sm text-slate-500">
                    <span className="font-semibold text-slate-900">{plan.name}</span>
                    {plan.is_featured && (
                      <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-blue-900">
                        Most popular
                      </span>
                    )}
                  </div>
                  <p className="mt-3 text-sm leading-relaxed text-slate-600">{plan.description}</p>
                  <div className="mt-6 flex items-baseline gap-2 text-slate-900">
                    <span className="text-4xl font-semibold">${plan.price_monthly}</span>
                    <span className="text-sm text-slate-500">/month</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedPlan({ id: plan._id, name: plan.name });
                      setAuthMode('signup');
                      setIsAuthModalOpen(true);
                    }}
                    className="mt-6 inline-flex items-center justify-center rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white transition hover:-translate-y-[1px] hover:bg-slate-800"
                  >
                    Start with {plan.name}
                  </button>
                </article>
              ))}
            </div>
            {planError && !planLoading && (
              <p className="rounded-3xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {planError}
              </p>
            )}
            {planNotice && !planError && (
              <p className="rounded-3xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700">
                {planNotice}
              </p>
            )}
          </section>

          {config.testimonials_enabled && orderedTestimonials.length > 0 && (
            <section id="testimonials" className="space-y-10">
              <div className="space-y-4 text-center">
                <span className="inline-flex items-center justify-center rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-900">
                  Planners sharing wins
                </span>
                <h2 className="text-3xl font-semibold text-slate-900 sm:text-4xl">Loved by planners crafting iconic events</h2>
                <p className="mx-auto max-w-2xl text-base text-slate-600">
                  Hear how teams replace patchwork tools with a platform that keeps every couple feeling like your only client.
                </p>
              </div>
              <div className="grid gap-6 lg:grid-cols-3">
                {orderedTestimonials.map((testimonial) => (
                  <blockquote
                    key={testimonial.name}
                    className="flex h-full flex-col justify-between rounded-3xl border border-slate-200/80 bg-white p-6 shadow-[0_30px_110px_-70px_rgba(15,23,42,0.3)]"
                  >
                    <p className="text-sm leading-relaxed text-slate-700">“{testimonial.content}”</p>
                    <footer className="mt-6 text-sm text-slate-500">
                      <div className="font-semibold text-slate-900">{testimonial.name}</div>
                      <div>{testimonial.role}</div>
                      <div className="text-xs uppercase tracking-[0.25em] text-slate-400">{testimonial.company}</div>
                    </footer>
                  </blockquote>
                ))}
              </div>
            </section>
          )}

          <section id="faq" className="grid gap-12 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] lg:items-start">
            <div className="space-y-6">
              <h2 className="text-3xl font-semibold text-slate-900 sm:text-4xl">Answers before you onboard</h2>
              <p className="text-base text-slate-600">
                We partner with you from discovery call to launch. If you have bespoke requirements, our concierge success team is ready to assist.
              </p>
              <button
                type="button"
                onClick={handleContactOpen}
                className="inline-flex items-center justify-center rounded-full border border-slate-900/10 bg-white px-6 py-3 text-sm font-semibold text-slate-900 shadow-[0_12px_35px_-25px_rgba(15,23,42,0.45)] transition hover:-translate-y-[1px] hover:border-slate-900/20"
              >
                Talk to a specialist
              </button>
            </div>
            <div className="space-y-4">
              {faqs.map((faq) => (
                <div key={faq.question} className="rounded-3xl border border-slate-200/80 bg-white p-5 shadow-sm">
                  <h3 className="text-base font-semibold text-slate-900">{faq.question}</h3>
                  <p className="mt-2 text-sm text-slate-600">{faq.answer}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="overflow-hidden rounded-[2.5rem] border border-slate-200/80 bg-gradient-to-r from-blue-600 to-purple-600 p-10 text-center text-white shadow-[0_40px_160px_-80px_rgba(79,70,229,0.55)]">
            <div className="mx-auto max-w-2xl space-y-4">
              <h2 className="text-3xl font-semibold sm:text-4xl">Give every celebration the spotlight it deserves</h2>
              <p className="text-base text-blue-50">
                Secure, collaborative, and elegantly branded—Special Wedding keeps your studio ahead of the expectations of modern couples.
              </p>
              <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
                <button
                  type="button"
                  onClick={() => {
                    setAuthMode('signup');
                    setIsAuthModalOpen(true);
                  }}
                  className="inline-flex items-center justify-center rounded-full bg-white px-8 py-3 text-base font-semibold text-slate-900 transition hover:-translate-y-[1px] hover:bg-blue-50"
                >
                  Create my planner account
                </button>
                <button
                  type="button"
                  onClick={handleContactOpen}
                  className="inline-flex items-center justify-center rounded-full border border-white/60 px-8 py-3 text-base font-semibold text-white transition hover:-translate-y-[1px] hover:bg-white/10"
                >
                  Schedule a guided tour
                </button>
              </div>
            </div>
          </section>
        </main>
      </div>

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
