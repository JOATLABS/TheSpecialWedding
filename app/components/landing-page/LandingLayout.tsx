'use client';

import React, { useState, useEffect } from "react";
import Link from "next/link";
import Image from 'next/image';

import { SectionWrapper } from '@/components/landing-page/SectionWrapper';
import { Modern3DBackground } from "@/components/landing-page/Modern3DBackground";
import { ThemedHeroSection } from "@/components/landing-page/ThemedHeroSection";
import { AnchorNav } from "@/components/landing-page/AnchorNav";
import { EventLocationSection } from "@/components/landing-page/EventLocationSection";
import { OurStorySection } from "@/components/landing-page/OurStorySection";
import { GlassCard } from '@/components/ui/GlassCard';
import { LandingLayoutProps } from '@/types/landing';
import { useTheme } from '@/hooks/useTheme';
import TermsModal from '@/components/TermsModal';
import PrivacyModal from '@/components/PrivacyModal';
import RequestRSVPLinkModal from '@/components/RequestRSVPLinkModal';
import RSVPModal from '@/components/RSVPModal';

export const LandingLayout: React.FC<LandingLayoutProps> = ({ wedding, images, rsvpToken }) => {
  // Apply theme CSS variables (--theme-primary, --theme-secondary, etc.)
  useTheme(wedding);

  const [showTerms, setShowTerms] = useState(false);
  const [showPrivacy, setShowPrivacy] = useState(false);
  const [showRSVPLinkModal, setShowRSVPLinkModal] = useState(false);
  const [showRSVPModal, setShowRSVPModal] = useState(!!rsvpToken);

  // Sync modal open state when rsvpToken arrives after initial render
  useEffect(() => {
    if (rsvpToken) {
      setShowRSVPModal(true);
    }
  }, [rsvpToken]);

  // Get featured image from wedding or use first gallery image
  const featuredImage = wedding.featured_image
    ? `${process.env.NEXT_PUBLIC_MEDIA_DOMAIN}/${wedding.featured_image}`
    : images.length > 0 ? images[0].url : undefined;

  return (
    <>
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
        <ThemedHeroSection
          wedding={wedding}
          onCelebrateClick={() => setShowRSVPLinkModal(true)}
        />

        {/* RSVP */}
        <SectionWrapper id="rsvp">
          <GlassCard className="max-w-4xl mx-auto p-8" depth="near" theme={wedding.theme_config}>
            <h2 className="text-4xl font-bold mb-4 text-center theme-primary">RSVP</h2>
            <p className="text-lg text-gray-700 dark:text-gray-200 mb-6 text-center">
              {wedding.rsvp_config?.greeting || "Join us in celebrating our special day! Please let us know if you'll be attending."}
            </p>
            <div className="space-y-4 text-center">
              <p className="text-gray-600 dark:text-gray-300">
                {wedding.rsvp_config?.help_text || "Check your phone for your personal invitation link, or contact the couple directly."}
              </p>
              <div className="inline-flex text-white px-6 py-3 rounded-lg theme-bg-accent">
                <div>
                  <p className="font-semibold">Need help?</p>
                  <p className="text-sm">Call us at {wedding.rsvp_config?.phone_numbers?.join(' or ') || "+1 877-780-4236"}</p>
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
                    <Image
                      src={img.url}
                      alt={`Memory ${i + 1}`}
                      fill
                      className="object-cover"
                      sizes="(max-width: 768px) 50vw, 25vw"
                      onError={(event) => { event.currentTarget.style.display = 'none'; }}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center text-gray-600 dark:text-gray-300 mb-6">Photos will be added soon!</p>
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
            <p className="text-lg text-gray-700 dark:text-gray-200 mb-8">
              Your presence is the greatest gift, but if you'd like to celebrate with us, we're registered at:
            </p>
            {wedding.registries && wedding.registries.length > 0 ? (
              <div className="grid md:grid-cols-2 gap-6">
                {wedding.registries.map((registry, index) => (
                  <div key={index} className="bg-gray-50 dark:bg-gray-800/50 p-6 rounded-lg">
                    <h3 className="text-xl font-semibold mb-4 dark:text-gray-100">{registry.name}</h3>
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
                <div className="bg-gray-50 dark:bg-gray-800/50 p-6 rounded-lg">
                  <h3 className="text-xl font-semibold mb-4 dark:text-gray-100">Target</h3>
                  <a
                    href="https://www.target.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="bg-red-600 text-white px-6 py-2 rounded-lg hover:bg-red-700 transition-colors"
                  >
                    View Registry
                  </a>
                </div>
                <div className="bg-gray-50 dark:bg-gray-800/50 p-6 rounded-lg">
                  <h3 className="text-xl font-semibold mb-4 dark:text-gray-100">Amazon</h3>
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
          <EventLocationSection wedding={wedding} />
        </SectionWrapper>

        {/* FAQ */}
        <SectionWrapper id="faq">
          <GlassCard className="max-w-4xl mx-auto p-8" depth="mid" theme={wedding.theme_config}>
            <h2 className="text-4xl font-bold text-center mb-8 theme-primary">Frequently Asked Questions</h2>
            <div className="space-y-8">
              {wedding.faqs && wedding.faqs.length > 0 ? (
                wedding.faqs.map((faq, index) => (
                  <div key={index} className="bg-gray-50 dark:bg-gray-800/50 p-6 rounded-lg">
                    <h3 className="text-xl font-semibold mb-2 dark:text-gray-100">{faq.question}</h3>
                    <p className="text-gray-700 dark:text-gray-300">{faq.answer}</p>
                    {faq.link_url && faq.link_label && (
                      <a
                        href={faq.link_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 mt-4 px-5 py-2.5 bg-wedding-rose hover:bg-wedding-rose/90 text-white font-medium rounded-lg transition-colors shadow-sm"
                      >
                        {faq.link_label}
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                      </a>
                    )}
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
                  <div key={q} className="bg-gray-50 dark:bg-gray-800/50 p-6 rounded-lg">
                    <h3 className="text-xl font-semibold mb-2 dark:text-gray-100">{q}</h3>
                    <p className="text-gray-700 dark:text-gray-300">{a}</p>
                  </div>
                ))
              )}
            </div>
          </GlassCard>
        </SectionWrapper>

      </div>
    </main>
    
    {/* Footer */}
    <footer className="bg-black bg-opacity-40 backdrop-blur-sm text-white py-6 mt-12">
      <div className="max-w-4xl mx-auto px-6 text-center">
        <div className="mb-3">
          <p className="text-lg font-semibold">TheSpecialWedding</p>
        </div>
        
        {/* Legal Links */}
        <div className="mb-4">
          <button 
            onClick={() => setShowTerms(true)}
            className="text-gray-300 hover:text-white transition-colors mx-3 underline"
          >
            Terms of Service
          </button>
          <span className="text-gray-500">|</span>
          <button 
            onClick={() => setShowPrivacy(true)}
            className="text-gray-300 hover:text-white transition-colors mx-3 underline"
          >
            Privacy Policy
          </button>
        </div>
        
        <div className="text-sm text-gray-300">
          <p>Developed by JOAT LABS</p>
          <a 
            href="mailto:thedeveloper@thespecialwedding.com" 
            className="hover:text-white transition-colors"
          >
            thedeveloper@thespecialwedding.com
          </a>
        </div>
      </div>
    </footer>
    
    {/* Modals */}
    <TermsModal 
      isOpen={showTerms} 
      onClose={() => setShowTerms(false)} 
      weddingName={wedding.couple_names}
    />
    <PrivacyModal
      isOpen={showPrivacy}
      onClose={() => setShowPrivacy(false)}
      weddingName={wedding.couple_names}
    />
    <RequestRSVPLinkModal
      isOpen={showRSVPLinkModal}
      onClose={() => setShowRSVPLinkModal(false)}
      slug={wedding.slug}
      coupleName={wedding.couple_names}
      themeConfig={wedding.theme_config}
    />
    {rsvpToken && (
      <RSVPModal
        isOpen={showRSVPModal}
        token={rsvpToken}
        slug={wedding.slug}
        onClose={() => {
          setShowRSVPModal(false);
          // Clear persisted token after modal closes (RSVP completed or dismissed)
          try { sessionStorage.removeItem('rsvp_token_' + wedding.slug); } catch {}
        }}
      />
    )}
    </>
  );
};
