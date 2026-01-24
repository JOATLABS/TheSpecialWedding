"use client";

import React, { useEffect, useMemo, useState } from "react";
import { GlassCard } from "../ui/GlassCard";
import { ThemeConfig } from "@/types/wedding";

interface Feature {
  title: string;
  description: string;
  status: "available" | "coming_soon";
  order: number;
}

interface Benefit {
  title: string;
  description: string;
  order: number;
}

interface Testimonial {
  name: string;
  company: string;
  role: string;
  content: string;
  order: number;
}

interface SaasExperienceCarouselProps {
  features: Feature[];
  benefits: Benefit[];
  testimonials: Testimonial[];
  theme: ThemeConfig;
}

interface SlideDescriptor {
  id: string;
  label: string;
  eyebrow: string;
  content: React.ReactNode;
}

export function SaasExperienceCarousel({
  features,
  benefits,
  testimonials,
  theme,
}: SaasExperienceCarouselProps) {
  const [activeIndex, setActiveIndex] = useState(0);

  const slides = useMemo<SlideDescriptor[]>(() => {
    const featuresArr = Array.isArray(features) ? features : [];
    const benefitsArr = Array.isArray(benefits) ? benefits : [];
    const testimonialsArr = Array.isArray(testimonials) ? testimonials : [];
    const sortedFeatures = [...featuresArr].sort((a, b) => a.order - b.order).slice(0, 6);
    const sortedBenefits = [...benefitsArr].sort((a, b) => a.order - b.order).slice(0, 4);
    const sortedTestimonials = [...testimonialsArr].sort((a, b) => a.order - b.order).slice(0, 3);

    return [
      {
        id: "features",
        label: "Signature features",
        eyebrow: "All-in-one operations",
        content: (
          <div className="grid gap-3 sm:grid-cols-2">
            {sortedFeatures.map((feature) => (
              <GlassCard
                key={feature.title}
                depth="mid"
                blur="xl"
                theme={theme}
                className="group rounded-3xl border border-white/35 bg-white/60 p-5 transition duration-500 hover:-translate-y-1 hover:shadow-xl"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-base font-semibold text-slate-900">{feature.title}</h3>
                    <p className="mt-2 text-sm text-slate-600">{feature.description}</p>
                  </div>
                  <span
                    className={`inline-flex shrink-0 items-center rounded-full px-3 py-1 text-xs font-semibold ${
                      feature.status === "available"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-amber-100 text-amber-700"
                    }`}
                  >
                    {feature.status === "available" ? "Live" : "Coming soon"}
                  </span>
                </div>
              </GlassCard>
            ))}
          </div>
        ),
      },
      {
        id: "benefits",
        label: "Planner outcomes",
        eyebrow: "Why planners switch",
        content: (
          <div className="grid gap-3 sm:grid-cols-2">
            {sortedBenefits.map((benefit) => (
              <GlassCard
                key={benefit.title}
                depth="far"
                blur="lg"
                theme={theme}
                className="rounded-3xl border border-white/30 bg-white/55 p-5"
              >
                <h3 className="text-base font-semibold text-slate-900">{benefit.title}</h3>
                <p className="mt-2 text-sm text-slate-600">{benefit.description}</p>
              </GlassCard>
            ))}
          </div>
        ),
      },
      {
        id: "testimonials",
        label: "Planner voices",
        eyebrow: "Proof in the field",
        content: (
          <div className="space-y-3">
            {sortedTestimonials.map((testimonial) => (
              <GlassCard
                key={`${testimonial.name}-${testimonial.company}`}
                depth="near"
                blur="xl"
                theme={theme}
                className="rounded-3xl border border-white/40 bg-white/65 p-5"
              >
                <p className="text-base font-medium text-slate-800">“{testimonial.content}”</p>
                <div className="mt-4 text-sm text-slate-500">
                  <p className="font-semibold text-slate-700">{testimonial.name}</p>
                  <p>
                    {testimonial.role}
                    {testimonial.company ? ` · ${testimonial.company}` : null}
                  </p>
                </div>
              </GlassCard>
            ))}
          </div>
        ),
      },
    ];
  }, [features, benefits, testimonials, theme]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveIndex((previous) => (previous + 1) % slides.length);
    }, 9000);

    return () => window.clearInterval(timer);
  }, [slides.length]);

  return (
    <div className="space-y-6" aria-labelledby="experience-showcase" aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[0.7rem] font-semibold uppercase tracking-[0.35em] text-slate-500">
            {slides[activeIndex]?.eyebrow}
          </p>
          <h2 id="experience-showcase" className="mt-2 text-2xl font-semibold text-slate-900 sm:text-[1.75rem]">
            {slides[activeIndex]?.label}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {slides.map((slide, index) => (
            <button
              key={slide.id}
              type="button"
              className={`h-2 w-7 rounded-full transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900 ${
                index === activeIndex ? 'bg-slate-900' : 'bg-slate-200 hover:bg-slate-300'
              }`}
              onClick={() => setActiveIndex(index)}
              aria-label={`Show ${slide.label}`}
            />
          ))}
        </div>
      </div>

      <div
        key={slides[activeIndex]?.id}
        className="transition-opacity duration-500"
      >
        {slides[activeIndex]?.content}
      </div>
    </div>
  );
}
