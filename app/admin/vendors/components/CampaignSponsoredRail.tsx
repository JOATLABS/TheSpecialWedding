'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ChevronLeft, ChevronRight, HelpCircle, Settings } from 'lucide-react';
import {
  getSponsoredCards,
  type SponsoredCard,
} from '@/services/campaignAdvertisingApi';
import { useAdmin } from '@/contexts/AdminContext';
import { CampaignSponsoredCard } from './CampaignSponsoredCard';
import { QuoteRequestModal } from './QuoteRequestModal';

interface CampaignSponsoredRailProps {
  location?: string;
  categories?: string[];
  maxItems?: number;
  weddings?: Array<{ id: string; name: string }>;
  onWeddingChange?: (weddingId: string) => void;
}

export function CampaignSponsoredRail({
  location,
  categories,
  maxItems = 3,
  weddings,
  onWeddingChange,
}: CampaignSponsoredRailProps) {
  const { token } = useAdmin();
  const [cards, setCards] = useState<SponsoredCard[]>([]);
  const [loading, setLoading] = useState(true);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const [selectedWeddingId, setSelectedWeddingId] = useState<string | null>(null);
  const [quoteModalCard, setQuoteModalCard] = useState<SponsoredCard | null>(null);

  // Fetch sponsored cards from the campaign platform
  useEffect(() => {
    const fetchCards = async () => {
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const response = await getSponsoredCards(token, {
          location,
          categories: categories?.join(','),
          limit: maxItems,
        });
        setCards(response.cards);
      } catch (err) {
        console.error('Failed to fetch sponsored cards:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchCards();
  }, [token, location, categories, maxItems]);

  // Check scroll position
  const checkScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (container) {
      setCanScrollLeft(container.scrollLeft > 0);
      setCanScrollRight(
        container.scrollLeft < container.scrollWidth - container.clientWidth - 10
      );
    }
  }, []);

  useEffect(() => {
    checkScroll();
    const container = scrollContainerRef.current;
    if (container) {
      container.addEventListener('scroll', checkScroll);
      window.addEventListener('resize', checkScroll);
      return () => {
        container.removeEventListener('scroll', checkScroll);
        window.removeEventListener('resize', checkScroll);
      };
    }
  }, [cards, checkScroll]);

  const scroll = (direction: 'left' | 'right') => {
    const container = scrollContainerRef.current;
    if (container) {
      container.scrollBy({
        left: direction === 'left' ? -400 : 400,
        behavior: 'smooth',
      });
    }
  };

  const handleWeddingChange = (weddingId: string) => {
    setSelectedWeddingId(weddingId);
    onWeddingChange?.(weddingId);
  };

  const handleHideCard = (campaignId: string) => {
    setCards((prev) => prev.filter((c) => c.campaign_id !== campaignId));
  };

  const selectedWedding = weddings?.find((w) => w.id === selectedWeddingId) || weddings?.[0];

  // Loading skeleton
  if (loading) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-[13px] font-bold text-wedding-navy">Sponsored Vendors</h3>
        </div>
        <div className="hidden lg:flex lg:flex-col lg:gap-2.5">
          {[1, 2, 3].map((i) => (
            <div key={i} className="w-full h-48 rounded-lg bg-gray-100 animate-pulse" />
          ))}
        </div>
        <div className="flex gap-3 overflow-x-hidden lg:hidden">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex-shrink-0 w-72 h-48 rounded-lg bg-gray-100 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (cards.length === 0) return null;

  const displayCards = cards.slice(0, 3);

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="hidden lg:block text-[13px] font-bold text-wedding-navy">Sponsored Vendors</h3>
          <div className="flex items-center gap-2 lg:hidden">
            <h3 className="text-base font-semibold text-wedding-navy">Recommended for you</h3>
          </div>
        </div>
        <button className="hidden lg:inline-flex items-center gap-1 text-[10px] text-gray-600 hover:text-wedding-sage transition-colors">
          <Settings size={10} />
          Preferences
        </button>
        <div className="relative lg:hidden">
          <button
            onClick={() => setShowTooltip(!showTooltip)}
            className="w-11 h-11 flex items-center justify-center text-gray-600 hover:text-wedding-sage transition-colors"
            aria-label="Why am I seeing this?"
          >
            <HelpCircle size={16} />
          </button>
          {showTooltip && (
            <div role="tooltip" className="absolute right-0 top-full mt-2 z-30 bg-wedding-navy text-white text-xs rounded-lg p-2 w-56 shadow-lg">
              These vendors are sponsored recommendations matched to your wedding.
            </div>
          )}
        </div>
      </div>

      {/* Wedding Context Badge */}
      {selectedWedding && (
        <div className="hidden lg:inline-flex items-center gap-1.5 text-[11px] text-wedding-sage bg-wedding-sage/[0.08] px-2.5 py-1 rounded-md">
          <span className="w-1.5 h-1.5 rounded-full bg-wedding-sage" />
          For: {selectedWedding.name}
        </div>
      )}

      {/* Wedding Selector */}
      {weddings && weddings.length > 1 && (
        <select
          value={selectedWeddingId || ''}
          onChange={(e) => handleWeddingChange(e.target.value)}
          className="w-full px-2 py-1.5 text-xs border border-gray-200 rounded-md text-wedding-navy focus:outline-none focus:ring-2 focus:ring-wedding-sage lg:text-[11px]"
        >
          <option value="">All weddings</option>
          {weddings.map((wedding) => (
            <option key={wedding.id} value={wedding.id}>{wedding.name}</option>
          ))}
        </select>
      )}

      {/* Desktop: Vertical stacked cards */}
      <div className="hidden lg:flex lg:flex-col" role="region" aria-label="Sponsored vendors">
        {displayCards.map((card) => (
          <CampaignSponsoredCard
            key={card.campaign_id}
            card={card}
            onRequestQuote={() => setQuoteModalCard(card)}
            onHide={() => handleHideCard(card.campaign_id)}
            weddingId={selectedWeddingId || weddings?.[0]?.id}
            weddingName={selectedWedding?.name}
          />
        ))}
      </div>

      {/* Mobile: Horizontal scroll carousel */}
      <div className="relative lg:hidden" role="region" aria-label="Sponsored vendors carousel">
        <div
          ref={scrollContainerRef}
          className="flex gap-3 overflow-x-auto scroll-smooth pb-2 snap-x snap-mandatory"
          style={{ WebkitOverflowScrolling: 'touch' }}
        >
          {cards.map((card, index) => (
            <div key={card.campaign_id} className="snap-start" aria-label={`Vendor ${index + 1} of ${cards.length}`}>
              <CampaignSponsoredCard
                card={card}
                onRequestQuote={() => setQuoteModalCard(card)}
                onHide={() => handleHideCard(card.campaign_id)}
                weddingId={selectedWeddingId || weddings?.[0]?.id}
                weddingName={selectedWedding?.name}
              />
            </div>
          ))}
        </div>
        {canScrollLeft && (
          <button
            onClick={() => scroll('left')}
            className="absolute left-0 top-1/2 -translate-y-1/2 z-20 w-11 h-11 flex items-center justify-center rounded-full bg-white shadow-md hover:shadow-lg text-wedding-navy transition-shadow"
            aria-label="Scroll to previous vendors"
          >
            <ChevronLeft size={18} />
          </button>
        )}
        {canScrollRight && (
          <button
            onClick={() => scroll('right')}
            className="absolute right-0 top-1/2 -translate-y-1/2 z-20 w-11 h-11 flex items-center justify-center rounded-full bg-white shadow-md hover:shadow-lg text-wedding-navy transition-shadow"
            aria-label="Scroll to more vendors"
          >
            <ChevronRight size={18} />
          </button>
        )}
      </div>

      {/* Footer */}
      <div className="hidden lg:flex justify-between pt-2 border-t border-gray-200">
        <button
          onClick={() => setShowTooltip(!showTooltip)}
          className="text-[10px] text-wedding-sage font-medium hover:underline"
        >
          Why am I seeing this?
        </button>
        <a href="/admin/vendors" className="text-[10px] text-wedding-sage font-medium hover:underline">
          See more vendors &rsaquo;
        </a>
      </div>

      {showTooltip && (
        <div className="hidden lg:block text-[10px] text-gray-600 bg-gray-50 px-3 py-2 rounded-md border border-gray-200">
          These vendors are sponsored recommendations matched to your wedding location, budget, and vendor needs.
        </div>
      )}

      <div className="flex justify-center pt-2 lg:hidden">
        <a href="/admin/vendors" className="text-xs text-gray-600 hover:text-wedding-sage transition-colors">
          See more vendors &rsaquo;
        </a>
      </div>

      {/* Quote Request Modal */}
      {quoteModalCard && (
        <QuoteRequestModal
          card={quoteModalCard}
          weddings={weddings}
          selectedWeddingId={selectedWeddingId || weddings?.[0]?.id}
          onClose={() => setQuoteModalCard(null)}
        />
      )}
    </div>
  );
}
