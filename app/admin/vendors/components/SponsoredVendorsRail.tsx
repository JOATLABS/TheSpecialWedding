'use client';

import React, { useState, useEffect, useRef } from 'react';
import { ChevronLeft, ChevronRight, Sparkles, HelpCircle } from 'lucide-react';
import {
  getSponsoredVendors,
  recordAdEvent,
  getFeatureFlag,
  getAdPreferences,
  hideAdVendor,
  type SponsoredVendor,
  type AdPlacement,
  type AdEventType,
  type FeatureFlag,
  type AdPreferences,
} from '@/services/advertisingApi';
import { getVendorDirectory, type VendorProfile } from '@/services/vendorManagementApi';
import { useAdmin } from '@/contexts/AdminContext';
import { SponsoredVendorCard } from './SponsoredVendorCard';

interface SponsoredVendorsRailProps {
  placement?: AdPlacement;
  category?: string;
  weddingStage?: string;
  maxItems?: number;
  onVendorClick?: (vendorProfileId: string) => void;
  weddings?: Array<{ id: string; name: string }>;
  onWeddingChange?: (weddingId: string) => void;
}

type SkeletonCard = { id: string; type: 'skeleton' };

export function SponsoredVendorsRail({
  placement = 'vendor_rail',
  category,
  weddingStage,
  maxItems = 6,
  onVendorClick,
  weddings,
  onWeddingChange,
}: SponsoredVendorsRailProps) {
  const { token } = useAdmin();
  const [sponsoredVendors, setSponsoredVendors] = useState<SponsoredVendor[]>([]);
  const [vendorProfiles, setVendorProfiles] = useState<Record<string, VendorProfile>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const [featureFlag, setFeatureFlag] = useState<FeatureFlag | null>(null);
  const [shouldRender, setShouldRender] = useState(true);
  const [showTooltip, setShowTooltip] = useState(false);
  const [selectedWeddingId, setSelectedWeddingId] = useState<string | null>(null);

  // Fetch feature flag and check frequency capping
  useEffect(() => {
    const checkFrequencyCap = async () => {
      if (!token) return;

      try {
        const flag = await getFeatureFlag(token);
        setFeatureFlag(flag);

        // Check if rail should be rendered based on frequency cap
        const storageKey = `sponsored_rail_impressions_${placement}`;
        const currentCount = parseInt(sessionStorage.getItem(storageKey) || '0', 10);

        if (currentCount >= flag.config.impressions_per_session_limit) {
          setShouldRender(false);
        }
      } catch (err) {
        console.error('Failed to fetch feature flag:', err);
        setFeatureFlag(null);
      }
    };

    checkFrequencyCap();
  }, [token, placement]);

  // Fetch sponsored vendors on mount
  useEffect(() => {
    const fetchData = async () => {
      if (!token || !shouldRender) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        // Fetch planner preferences to filter hidden vendors/categories
        let prefs: AdPreferences | null = null;
        try {
          prefs = await getAdPreferences(token);
        } catch {
          // Continue without preferences — show all vendors
        }

        // Fetch sponsored vendors
        let vendors = await getSponsoredVendors(token, {
          placement,
          category,
          wedding_stage: weddingStage,
          limit: prefs?.reduced_frequency ? Math.ceil(maxItems / 2) : maxItems,
        });

        // Client-side filtering based on planner preferences
        if (prefs) {
          if (prefs.hidden_vendor_ids?.length) {
            vendors = vendors.filter(v => !prefs!.hidden_vendor_ids.includes(v.vendor_profile_id));
          }
          if (prefs.hidden_categories?.length) {
            vendors = vendors.filter(v => {
              const cats = v.target_categories || [];
              return !cats.some((c: string) => prefs!.hidden_categories.includes(c));
            });
          }
        }

        setSponsoredVendors(vendors);

        // Fetch vendor profiles for each sponsored vendor
        if (vendors.length > 0) {
          try {
            const allProfiles = await getVendorDirectory(token, { limit: 100 });
            const profileMap: Record<string, VendorProfile> = {};

            allProfiles.forEach((profile) => {
              profileMap[profile._id] = profile;
            });

            setVendorProfiles(profileMap);
          } catch (err) {
            console.error('Failed to fetch vendor profiles:', err);
            // Continue without vendor details
          }
        }

        setLoading(false);
      } catch (err) {
        console.error('Failed to fetch sponsored vendors:', err);
        // Graceful degradation - render nothing on error
        setLoading(false);
      }
    };

    fetchData();
  }, [token, placement, category, weddingStage, maxItems, shouldRender]);

  // Check scroll position
  const checkScroll = () => {
    const container = scrollContainerRef.current;
    if (container) {
      setCanScrollLeft(container.scrollLeft > 0);
      setCanScrollRight(
        container.scrollLeft < container.scrollWidth - container.clientWidth - 10
      );
    }
  };

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
  }, [sponsoredVendors]);

  // Scroll handlers
  const scroll = (direction: 'left' | 'right') => {
    const container = scrollContainerRef.current;
    if (container) {
      const scrollAmount = 400;
      container.scrollBy({
        left: direction === 'left' ? -scrollAmount : scrollAmount,
        behavior: 'smooth',
      });
    }
  };

  // Record ad event
  const handleRecordEvent = async (
    eventType: AdEventType,
    sponsoredVendorId: string,
    vendorProfileId: string,
    metadata?: Record<string, any>
  ) => {
    if (!token) return;

    try {
      await recordAdEvent(token, {
        sponsored_vendor_id: sponsoredVendorId,
        vendor_profile_id: vendorProfileId,
        event_type: eventType,
        placement,
        metadata,
      });
    } catch (err) {
      console.error('Failed to record event:', err);
    }
  };

  // Handle vendor hide/dismiss
  const handleVendorHide = async (vendorProfileId: string) => {
    // Persist hide preference to backend and remove from local state
    if (token) {
      try {
        await hideAdVendor(token, vendorProfileId);
      } catch (err) {
        console.error('Failed to persist hide preference:', err);
      }
    }
    // Remove from local state immediately for responsive UX
    setSponsoredVendors(prev => prev.filter(v => v.vendor_profile_id !== vendorProfileId));
  };

  // Handle vendor click — use callback if provided, otherwise navigate to public profile
  const handleVendorClick = (vendorProfileId: string) => {
    if (onVendorClick) {
      onVendorClick(vendorProfileId);
    } else {
      window.open(`/vendors/${vendorProfileId}`, '_blank');
    }
  };

  // Handle wedding selection change
  const handleWeddingChange = (weddingId: string) => {
    setSelectedWeddingId(weddingId);
    if (onWeddingChange) {
      onWeddingChange(weddingId);
    }
  };

  // Track impression in sessionStorage
  const trackImpression = () => {
    if (featureFlag) {
      const storageKey = `sponsored_rail_impressions_${placement}`;
      const currentCount = parseInt(sessionStorage.getItem(storageKey) || '0', 10);
      sessionStorage.setItem(storageKey, String(currentCount + 1));
    }
  };

  // Track impression when rail is rendered
  useEffect(() => {
    if (!loading && sponsoredVendors.length > 0) {
      trackImpression();
    }
  }, [loading, sponsoredVendors.length, featureFlag, placement]);

  // Don't render if frequency cap exceeded
  if (!shouldRender) {
    return null;
  }

  // Don't render if loading, error, or no sponsored vendors
  if (loading) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles size={16} className="text-wedding-gold" />
          <h2 className="text-lg font-semibold text-wedding-navy">Recommended for you</h2>
        </div>
        <div className="flex gap-4 overflow-x-hidden">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="flex-shrink-0 w-80 h-72 rounded-lg bg-gray-100 animate-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  if (error || sponsoredVendors.length === 0) {
    // Graceful degradation - render nothing on error or empty state
    return null;
  }

  return (
    <div className="space-y-3">
      {/* Header with Info Icon */}
      <div className="flex items-center gap-2 mb-4">
        <Sparkles size={16} className="text-wedding-gold" />
        <h2 className="text-lg font-semibold text-wedding-navy">Recommended for you</h2>

        {/* "Why am I seeing this?" Info Icon */}
        <div className="relative group">
          <button
            onClick={() => setShowTooltip(!showTooltip)}
            className="p-1 ml-1 text-gray-400 hover:text-wedding-sage transition-colors"
            aria-label="Why am I seeing this?"
            title="Why am I seeing this?"
          >
            <HelpCircle size={16} />
          </button>

          {/* Tooltip */}
          {showTooltip && (
            <div className="absolute left-0 top-full mt-2 z-30 bg-wedding-navy text-white text-xs rounded-lg p-2 whitespace-nowrap shadow-lg">
              These vendors are sponsored recommendations relevant to your wedding. You can hide any vendor you're not interested in.
              <div className="absolute bottom-full left-3 -mb-1 w-2 h-2 bg-wedding-navy transform rotate-45" />
            </div>
          )}
        </div>

        {/* Wedding Context Selector */}
        {weddings && weddings.length > 1 && (
          <select
            value={selectedWeddingId || ''}
            onChange={(e) => handleWeddingChange(e.target.value)}
            className="ml-auto px-2 py-1 text-sm border border-gray-300 rounded-md text-wedding-navy focus:outline-none focus:ring-2 focus:ring-wedding-gold"
          >
            <option value="">All weddings</option>
            {weddings.map((wedding) => (
              <option key={wedding.id} value={wedding.id}>
                {wedding.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Rail Container */}
      <div className="relative">
        {/* Scroll Container */}
        <div
          ref={scrollContainerRef}
          className="flex gap-4 overflow-x-auto scroll-smooth pb-2"
          style={{ scrollBehavior: 'smooth', WebkitOverflowScrolling: 'touch' }}
        >
          {sponsoredVendors.map((vendor) => (
            <SponsoredVendorCard
              key={vendor._id}
              vendor={vendor}
              vendorProfile={vendorProfiles[vendor.vendor_profile_id]}
              onView={handleVendorClick}
              onRecordEvent={handleRecordEvent}
              onHide={handleVendorHide}
            />
          ))}
        </div>

        {/* Left Scroll Arrow */}
        {canScrollLeft && (
          <button
            onClick={() => scroll('left')}
            className="absolute left-0 top-1/2 -translate-y-1/2 z-20 p-2 rounded-full bg-white shadow-md hover:shadow-lg text-wedding-navy transition-shadow"
            aria-label="Scroll left"
          >
            <ChevronLeft size={20} />
          </button>
        )}

        {/* Right Scroll Arrow */}
        {canScrollRight && (
          <button
            onClick={() => scroll('right')}
            className="absolute right-0 top-1/2 -translate-y-1/2 z-20 p-2 rounded-full bg-white shadow-md hover:shadow-lg text-wedding-navy transition-shadow"
            aria-label="Scroll right"
          >
            <ChevronRight size={20} />
          </button>
        )}
      </div>

      {/* Footer with "See all" Link */}
      <div className="flex justify-center pt-2">
        <a
          href="/vendors"
          className="text-sm text-gray-600 hover:text-wedding-sage transition-colors flex items-center gap-1"
        >
          See all sponsored vendors
          <span className="text-xs">→</span>
        </a>
      </div>
    </div>
  );
}
