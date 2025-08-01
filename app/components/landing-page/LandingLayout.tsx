'use client';

import React from "react";
import Link from "next/link";

import { SectionWrapper } from '@/components/landing-page/SectionWrapper';
import { Modern3DBackground } from "@/components/landing-page/Modern3DBackground";
import { ThemedHeroSection } from "@/components/landing-page/ThemedHeroSection";
import { AnchorNav } from "@/components/landing-page/AnchorNav";
import { EventLocationSection } from "@/components/landing-page/EventLocationSection";
import { OurStorySection } from "@/components/landing-page/OurStorySection";
import { GlassCard } from '@/components/ui/GlassCard';
import { LandingLayoutProps } from '@/types/landing';
import { useTheme } from '@/hooks/useTheme';

export const LandingLayout: React.FC<LandingLayoutProps> = ({ wedding, images }) => {
  const theme = useTheme(wedding);
  
  // Get featured image from wedding or use first gallery image
  const featuredImage = wedding.featured_image 
    ? `https://media.thespecialwedding.com/${wedding.featured_image}`
    : images.length > 0 ? images[0].url : undefined;

  return (
    <main className="relative w-full">
      {/* Modern 3D Background */}
      <Modern3DBackground 
        imageUrl={featuredImage}
        fallbackImages={images.map(img => img.url)}
        theme={wedding.theme_config}
      />

      {/* Content with 3D glass cards */}
      <div className="relative z-10">

        {/* Nav */}
        <AnchorNav sections={["rsvp", "story", "gallery", "registry", "venue", "faq"]} />

        {/* Hero */}
        <ThemedHeroSection wedding={wedding} />

        {/* RSVP */}
        <SectionWrapper id="rsvp">
          <GlassCard className="max-w-4xl mx-auto p-8" depth="near" theme={wedding.theme_config}>
            <h2 className="text-4xl font-bold mb-4 text-center theme-primary">RSVP</h2>
            <p className="text-lg text-gray-700 mb-6 text-center">
              {wedding.rsvp_config?.greeting || "Join us in celebrating our special day! Please let us know if you'll be attending."}
            </p>
            <div className="space-y-4 text-center">
              <p className="text-gray-600">
                {wedding.rsvp_config?.help_text || "Check your phone for your personal invitation link, or contact us directly."}
              </p>
              <div className="inline-flex text-white px-6 py-3 rounded-lg theme-bg-accent">
                <div>
                  <p className="font-semibold">Need help?</p>
                  <p className="text-sm">Call us at {wedding.rsvp_config?.phone_numbers?.join(' or ') || "(319) 529-6088 or (405) 708-1076"}</p>
                </div>
              </div>
            </div>
          </GlassCard>
        </SectionWrapper>

        {/* Our Story & Wedding Party */}
        <SectionWrapper id="story">
          <OurStorySection wedding={wedding} />
        </SectionWrapper>

        {/* Gallery */}
        <SectionWrapper id="gallery">
          <GlassCard className="max-w-6xl mx-auto p-8" depth="mid" theme={wedding.theme_config}>
            <h2 className="text-4xl font-bold text-center mb-6 theme-primary">Gallery</h2>
            {images.length > 0 ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                {images.slice(0, 8).map((img, i) => (
                  <div key={img.key} className="relative w-full h-48 rounded-lg overflow-hidden shadow-lg">
                    <img
                      src={img.url}
                      alt={`Memory ${i + 1}`}
                      className="w-full h-full object-cover"
                      onError={(e) => { e.currentTarget.style.display = 'none'; }}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center text-gray-600 mb-6">Photos will be added soon!</p>
            )}
            <div className="text-center">
              <Link
                href={`/${wedding.slug}/gallery`}
                className="text-white px-8 py-3 rounded-lg font-semibold hover:opacity-90 transition-colors theme-bg-primary"
              >
                View Full Gallery
              </Link>
            </div>
          </GlassCard>
        </SectionWrapper>

        {/* Registry */}
        <SectionWrapper id="registry">
          <GlassCard className="max-w-4xl mx-auto p-8 text-center" depth="far" theme={wedding.theme_config}>
            <h2 className="text-4xl font-bold mb-6 theme-primary">Wedding Registry</h2>
            <p className="text-lg text-gray-700 mb-8">
              Your presence is the greatest gift, but if you’d like to celebrate with us, we’re registered at:
            </p>
            {wedding.registries && wedding.registries.length > 0 ? (
              <div className="grid md:grid-cols-2 gap-6">
                {wedding.registries.map((registry, index) => (
                  <div key={index} className="bg-gray-50 p-6 rounded-lg">
                    <h3 className="text-xl font-semibold mb-4">{registry.name}</h3>
                    <a
                      href={registry.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`${registry.color || 'bg-gray-600'} text-white px-6 py-2 rounded-lg hover:opacity-90 transition-opacity inline-block`}
                    >
                      View Registry
                    </a>
                  </div>
                ))}
              </div>
            ) : (
              <div className="grid md:grid-cols-2 gap-6">
                <div className="bg-gray-50 p-6 rounded-lg">
                  <h3 className="text-xl font-semibold mb-4">Target</h3>
                  <a
                    href="https://www.target.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="bg-red-600 text-white px-6 py-2 rounded-lg hover:bg-red-700 transition-colors"
                  >
                    View Registry
                  </a>
                </div>
                <div className="bg-gray-50 p-6 rounded-lg">
                  <h3 className="text-xl font-semibold mb-4">Amazon</h3>
                  <a
                    href="https://www.amazon.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="bg-orange-500 text-white px-6 py-2 rounded-lg hover:bg-orange-600 transition-colors"
                  >
                    View Registry
                  </a>
                </div>
              </div>
            )}
          </GlassCard>
        </SectionWrapper>

        {/* Wedding Details */}
        <SectionWrapper id="venue">
          <GlassCard className="max-w-4xl mx-auto p-8" depth="near" theme={wedding.theme_config}>
            <h2 className="text-4xl font-bold text-center mb-8 theme-primary">Wedding Details</h2>
            <EventLocationSection wedding={wedding} />
          </GlassCard>
        </SectionWrapper>

        {/* FAQ */}
        <SectionWrapper id="faq">
          <GlassCard className="max-w-4xl mx-auto p-8" depth="mid" theme={wedding.theme_config}>
            <h2 className="text-4xl font-bold text-center mb-8 theme-primary">Frequently Asked Questions</h2>
            <div className="space-y-8">
              {wedding.faqs && wedding.faqs.length > 0 ? (
                wedding.faqs.map((faq, index) => (
                  <div key={index} className="bg-gray-50 p-6 rounded-lg">
                    <h3 className="text-xl font-semibold mb-2">{faq.question}</h3>
                    <p className="text-gray-700">{faq.answer}</p>
                  </div>
                ))
              ) : (
                [
                  {
                    q: "What should I wear?",
                    a: "We recommend semi-formal attire. Think cocktail dress or nice slacks with a button-down shirt."
                  },
                  {
                    q: "Where is the venue?",
                    a: wedding.venue || "Venue details will be shared with your RSVP confirmation."
                  },
                  {
                    q: "What time should I arrive?",
                    a: "Please arrive 15–30 minutes before the ceremony begins. Check your invitation for specifics."
                  },
                  {
                    q: "Can I bring a plus one?",
                    a: "Plus ones are by invitation only. Check your RSVP to see if yours is included."
                  },
                  {
                    q: "Is there parking available?",
                    a: "Yes, complimentary parking is available at the venue. Details with your RSVP confirmation."
                  }
                ].map(({ q, a }) => (
                  <div key={q} className="bg-gray-50 p-6 rounded-lg">
                    <h3 className="text-xl font-semibold mb-2">{q}</h3>
                    <p className="text-gray-700">{a}</p>
                  </div>
                ))
              )}
            </div>
          </GlassCard>
        </SectionWrapper>

      </div>
    </main>
  );
};
