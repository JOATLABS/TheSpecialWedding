'use client';

import React, { useState, useCallback, useRef } from "react";
import Link from "next/link";
import Image from 'next/image';

import { SectionWrapper } from '@/components/landing-page/SectionWrapper';
import { Modern3DBackground } from "@/components/landing-page/Modern3DBackground";
import { ThemedHeroSection } from "@/components/landing-page/ThemedHeroSection";
import { AnchorNav } from "@/components/landing-page/AnchorNav";
import { EventLocationSection } from "@/components/landing-page/EventLocationSection";
import { OurStorySection } from "@/components/landing-page/OurStorySection";
import { GlassCard } from '@/components/ui/GlassCard';
import InfiniteScrollWrapper from '@/components/ui/InfiniteScrollWrapper';
import { LandingLayoutProps } from '@/types/landing';
import { useTheme } from '@/hooks/useTheme';
import TermsModal from '@/components/TermsModal';
import PrivacyModal from '@/components/PrivacyModal';
import RequestRSVPLinkModal from '@/components/RequestRSVPLinkModal';
import RSVPModal from '@/components/RSVPModal';

/* ═══════════════════════════════════════════════════════════
   Wedding page content — rendered as primary + lightweight clone
   ═══════════════════════════════════════════════════════════ */

interface WeddingContentProps {
  isClone: boolean;
  wedding: LandingLayoutProps['wedding'];
  images: LandingLayoutProps['images'];
  onCelebrateClick?: () => void;
}

function WeddingContent({ isClone, wedding, images, onCelebrateClick }: WeddingContentProps) {
  return (
    <div className="relative z-10">
      {/* Hero */}
      <ThemedHeroSection
        wedding={wedding}
        onCelebrateClick={isClone ? undefined : onCelebrateClick}
      />

      {/* RSVP */}
      <SectionWrapper id={isClone ? undefined : "rsvp"}>
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
      <SectionWrapper id={isClone ? undefined : "story"}>
        <OurStorySection wedding={wedding} />
      </SectionWrapper>

      {/* Gallery */}
      <SectionWrapper id={isClone ? undefined : "gallery"}>
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
            {!isClone ? (
              <Link
                href={`/${wedding.slug}/gallery`}
                className="text-white px-8 py-3 rounded-lg font-semibold hover:opacity-90 transition-colors theme-bg-primary"
              >
                View Full Gallery
              </Link>
            ) : (
              <span className="text-white px-8 py-3 rounded-lg font-semibold theme-bg-primary inline-block">
                View Full Gallery
              </span>
            )}
          </div>
        </GlassCard>
      </SectionWrapper>

      {/* Registry */}
      <SectionWrapper id={isClone ? undefined : "registry"}>
        <GlassCard className="max-w-4xl mx-auto p-6 text-center" depth="far" theme={wedding.theme_config}>
          <h2 className="text-4xl font-bold mb-4 theme-primary">Wedding Registry</h2>
          <p className="text-base text-gray-700 dark:text-gray-200 mb-6">
            Your presence is the greatest gift, but if you&apos;d like to celebrate with us, we&apos;re registered at:
          </p>
          {wedding.registries && wedding.registries.length > 0 ? (
            <div className={`grid gap-4 ${wedding.registries.length === 1 ? 'grid-cols-1 max-w-xs mx-auto' : wedding.registries.length === 2 ? 'grid-cols-2' : 'grid-cols-3'}`}>
              {wedding.registries.map((registry, index) => (
                <div key={index} className="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg">
                  <h3 className="text-lg font-semibold mb-3 dark:text-gray-100">{registry.name}</h3>
                  {!isClone ? (
                    <a
                      href={registry.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`${registry.color || 'bg-gray-600'} text-white px-6 py-2 rounded-lg hover:opacity-90 transition-opacity inline-block`}
                    >
                      View Registry
                    </a>
                  ) : (
                    <span className={`${registry.color || 'bg-gray-600'} text-white px-6 py-2 rounded-lg inline-block`}>
                      View Registry
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="grid md:grid-cols-2 gap-6">
              <div className="bg-gray-50 dark:bg-gray-800/50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-4 dark:text-gray-100">Target</h3>
                {!isClone ? (
                  <a
                    href="https://www.target.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="bg-red-600 text-white px-6 py-2 rounded-lg hover:bg-red-700 transition-colors"
                  >
                    View Registry
                  </a>
                ) : (
                  <span className="bg-red-600 text-white px-6 py-2 rounded-lg inline-block">
                    View Registry
                  </span>
                )}
              </div>
              <div className="bg-gray-50 dark:bg-gray-800/50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-4 dark:text-gray-100">Amazon</h3>
                {!isClone ? (
                  <a
                    href="https://www.amazon.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="bg-orange-500 text-white px-6 py-2 rounded-lg hover:bg-orange-600 transition-colors"
                  >
                    View Registry
                  </a>
                ) : (
                  <span className="bg-orange-500 text-white px-6 py-2 rounded-lg inline-block">
                    View Registry
                  </span>
                )}
              </div>
            </div>
          )}
        </GlassCard>
      </SectionWrapper>

      {/* Wedding Details */}
      <SectionWrapper id={isClone ? undefined : "venue"}>
        <EventLocationSection wedding={wedding} />
      </SectionWrapper>

      {/* FAQ */}
      <SectionWrapper id={isClone ? undefined : "faq"}>
        <GlassCard className="max-w-4xl mx-auto p-8" depth="mid" theme={wedding.theme_config}>
          <h2 className="text-4xl font-bold text-center mb-8 theme-primary">Frequently Asked Questions</h2>
          <div className="space-y-8">
            {wedding.faqs && wedding.faqs.length > 0 ? (
              wedding.faqs.map((faq, index) => (
                <div key={index} className="bg-gray-50 dark:bg-gray-800/50 p-6 rounded-lg">
                  <h3 className="text-xl font-semibold mb-2 dark:text-gray-100">{faq.question}</h3>
                  <p className="text-gray-700 dark:text-gray-300">{faq.answer}</p>
                  {faq.link_url && faq.link_label && !isClone && (
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
                  {faq.link_url && faq.link_label && isClone && (
                    <span className="inline-flex items-center gap-2 mt-4 px-5 py-2.5 bg-wedding-rose text-white font-medium rounded-lg shadow-sm">
                      {faq.link_label}
                    </span>
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
                  a: typeof wedding.venue === 'string'
                    ? wedding.venue
                    : wedding.venue?.name || "Venue details will be shared with your RSVP confirmation."
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

      {/* Minimal footer — acts as a bridge back to the cloned hero */}
      <footer className="bg-black bg-opacity-40 backdrop-blur-sm text-white py-6 mt-12">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <div className="mb-3">
            <p className="text-lg font-semibold">TheSpecialWedding</p>
          </div>
          <div className="text-sm text-gray-300">
            <p>Developed by JOAT LABS</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   Main layout — assembles fixed layers + infinite scroll content
   ═══════════════════════════════════════════════════════════ */

export const LandingLayout: React.FC<LandingLayoutProps> = ({ wedding, images, guest, openGuestRsvpOnLoad }) => {
  // Apply theme CSS variables (--theme-primary, --theme-secondary, etc.)
  useTheme(wedding);

  const [showTerms, setShowTerms] = useState(false);
  const [showPrivacy, setShowPrivacy] = useState(false);
  const [showRSVPLinkModal, setShowRSVPLinkModal] = useState(false);
  const [manualRSVPModalOpen, setManualRSVPModalOpen] = useState(false);
  const [dismissedAutoOpenToken, setDismissedAutoOpenToken] = useState<string | null>(null);
  const [loopHeight, setLoopHeight] = useState(0);

  // Shared ref holding the normalised (modulo'd) scroll position.
  // Written by InfiniteScrollWrapper, read by Modern3DBackground —
  // guarantees both layers see the exact same Y on every frame.
  const normalizedScrollRef = useRef(0);

  // Stable callback for InfiniteScrollWrapper height reporting
  const handlePrimaryHeight = useCallback((h: number) => setLoopHeight(h), []);

  const currentAutoOpenToken = openGuestRsvpOnLoad && guest ? `${wedding.slug}:guest-rsvp` : null;
  const showRSVPModal = manualRSVPModalOpen || Boolean(
    currentAutoOpenToken && dismissedAutoOpenToken !== currentAutoOpenToken,
  );

  // Get featured image from wedding or use first gallery image.
  // Backend resolves `featured_image` to a full public URL (see
  // GalleryUploadService.resolve_wedding_media_urls) so we use it as-is and
  // don't concatenate NEXT_PUBLIC_MEDIA_DOMAIN here — that env var is inlined
  // at build time and has historically been the source of broken-image bugs
  // when a build ships without it set.
  const featuredImage = wedding.featured_image
    ? wedding.featured_image
    : images.length > 0 ? images[0].url : undefined;

  return (
    <>
      {/* ── Fixed background layer (stays behind everything) ── */}
      <Modern3DBackground
        imageUrl={featuredImage}
        fallbackImages={images.map(img => img.url)}
        theme={wedding.theme_config}
        loopHeight={loopHeight}
        normalizedScrollRef={normalizedScrollRef}
      />

      {/* ── Fixed nav (stays on top of everything) ── */}
      <AnchorNav sections={["rsvp", "story", "gallery", "registry", "venue", "faq"]} />

      {/* ── Infinite scroll content ── */}
      <main className="relative w-full">
        <InfiniteScrollWrapper onPrimaryHeight={handlePrimaryHeight} normalizedScrollRef={normalizedScrollRef}>
          {(isClone) => (
            <WeddingContent
              isClone={isClone}
              wedding={wedding}
              images={images}
              onCelebrateClick={() => {
                if (guest) {
                  setManualRSVPModalOpen(true);
                  return;
                }
                setShowRSVPLinkModal(true);
              }}
            />
          )}
        </InfiniteScrollWrapper>
      </main>

      {/* ── Legal footer links (accessible via nav, rendered once) ── */}
      <div className="fixed bottom-0 left-0 right-0 z-40 pointer-events-none">
        <div className="flex justify-center gap-6 pb-3 pointer-events-auto">
          <button
            onClick={() => setShowTerms(true)}
            className="text-[10px] uppercase tracking-[0.3em] text-white/40 hover:text-white/70 transition-colors bg-black/20 backdrop-blur-sm px-3 py-1 rounded-full"
          >
            Terms
          </button>
          <button
            onClick={() => setShowPrivacy(true)}
            className="text-[10px] uppercase tracking-[0.3em] text-white/40 hover:text-white/70 transition-colors bg-black/20 backdrop-blur-sm px-3 py-1 rounded-full"
          >
            Privacy
          </button>
        </div>
      </div>

      {/* ── Modals — rendered once, outside scroll wrapper ── */}
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
      {guest && (
        <RSVPModal
          isOpen={showRSVPModal}
          slug={wedding.slug}
          onClose={() => {
            if (currentAutoOpenToken) {
              setDismissedAutoOpenToken(currentAutoOpenToken);
            }
            setManualRSVPModalOpen(false);
          }}
        />
      )}
    </>
  );
};
