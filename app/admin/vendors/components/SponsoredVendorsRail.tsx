'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ChevronLeft, ChevronRight, HelpCircle, Settings } from 'lucide-react';
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
import { SponsoredVendorDetailsDrawer } from './SponsoredVendorDetailsDrawer';

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
  const [dismissAnnouncement, setDismissAnnouncement] = useState<string>('');
  const [drawerVendor, setDrawerVendor] = useState<SponsoredVendor | null>(null);

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
        wedding_id: selectedWeddingId || weddings?.[0]?.id,
        metadata,
      });
    } catch (err) {
      console.error('Failed to record event:', err);
    }
  };

  // Handle vendor hide/dismiss with screen reader announcement
  const handleVendorHide = async (vendorProfileId: string) => {
    // Find vendor name for announcement before removing
    const hiddenVendor = sponsoredVendors.find(v => v.vendor_profile_id === vendorProfileId);
    const vendorName = hiddenVendor ? vendorProfiles[vendorProfileId]?.business_name || 'Vendor' : 'Vendor';

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

    // Announce to screen readers
    setDismissAnnouncement(`${vendorName} has been hidden from sponsored vendors.`);
    setTimeout(() => setDismissAnnouncement(''), 3000);
  };

  // Generate why-tag for a vendor based on their profile and targeting
  const getWhyTag = useCallback((vendor: SponsoredVendor): string | undefined => {
    const profile = vendorProfiles[vendor.vendor_profile_id];
    if (!profile) return undefined;

    const parts: string[] = [];
    if (profile.city) parts.push(`Serves ${profile.city}`);
    if (profile.service_category) {
      const categoryLabel = profile.service_category.replace(/_/g, ' ');
      parts.push(`Offers ${categoryLabel} services`);
    }
    return parts.length > 0 ? parts.join(' · ') : undefined;
  }, [vendorProfiles]);

  // Handle vendor click — use callback if provided, otherwise open details drawer
  const handleVendorClick = (vendorProfileId: string) => {
    if (onVendorClick) {
      onVendorClick(vendorProfileId);
      return;
    }
    // Open the details drawer for this vendor
    const vendor = sponsoredVendors.find(v => v.vendor_profile_id === vendorProfileId);
    if (vendor) {
      setDrawerVendor(vendor);
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

  // Desktop: max 3 cards in vertical rail
  const desktopMaxCards = 3;
  const displayVendors = sponsoredVendors.slice(0, desktopMaxCards);

  // Get wedding context label for rail-context badge
  const selectedWedding = weddings?.find(w => w.id === selectedWeddingId) || weddings?.[0];

  // Loading skeleton — responsive: vertical on desktop, horizontal on mobile
  if (loading) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-[13px] font-bold text-wedding-navy">Sponsored Vendors</h3>
        </div>
        {/* Desktop: vertical stack */}
        <div className="hidden lg:flex lg:flex-col lg:gap-2.5">
          {[1, 2, 3].map((i) => (
            <div key={i} className="w-full h-48 rounded-lg bg-gray-100 animate-pulse" />
          ))}
        </div>
        {/* Mobile: horizontal scroll */}
        <div className="flex gap-3 overflow-x-hidden lg:hidden">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex-shrink-0 w-72 h-48 rounded-lg bg-gray-100 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error || sponsoredVendors.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      {/* ===== HEADER — Desktop: "Sponsored Vendors" + Preferences, Mobile: "Recommended for you" ===== */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Desktop header */}
          <h3 className="hidden lg:block text-[13px] font-bold text-wedding-navy">Sponsored Vendors</h3>
          {/* Mobile header */}
          <div className="flex items-center gap-2 lg:hidden">
            <h3 className="text-base font-semibold text-wedding-navy">Recommended for you</h3>
          </div>
        </div>
        {/* Desktop: Preferences button — contrast-safe gray-600 (5.7:1) */}
        <button className="hidden lg:inline-flex items-center gap-1 text-[10px] text-gray-600 hover:text-wedding-sage transition-colors">
          <Settings size={10} />
          Preferences
        </button>
        {/* Mobile: Info icon — 44px touch target */}
        <div className="relative lg:hidden">
          <button
            onClick={() => setShowTooltip(!showTooltip)}
            className="w-11 h-11 flex items-center justify-center text-gray-600 hover:text-wedding-sage transition-colors"
            aria-label="Why am I seeing this?"
            aria-expanded={showTooltip}
            aria-controls="mobile-tooltip"
          >
            <HelpCircle size={16} />
          </button>
          {showTooltip && (
            <div id="mobile-tooltip" role="tooltip" className="absolute right-0 top-full mt-2 z-30 bg-wedding-navy text-white text-xs rounded-lg p-2 w-56 shadow-lg">
              These vendors are sponsored recommendations matched to your wedding. You can hide any vendor you&apos;re not interested in.
              <div className="absolute bottom-full right-3 -mb-1 w-2 h-2 bg-wedding-navy transform rotate-45" />
            </div>
          )}
        </div>
      </div>

      {/* ===== WEDDING CONTEXT BADGE (Desktop only) ===== */}
      {selectedWedding && (
        <div className="hidden lg:inline-flex items-center gap-1.5 text-[11px] text-wedding-sage bg-wedding-sage/[0.08] px-2.5 py-1 rounded-md">
          <span className="w-1.5 h-1.5 rounded-full bg-wedding-sage" />
          For: {selectedWedding.name}
        </div>
      )}

      {/* ===== WEDDING SELECTOR (both, if multiple weddings) ===== */}
      {weddings && weddings.length > 1 && (
        <select
          value={selectedWeddingId || ''}
          onChange={(e) => handleWeddingChange(e.target.value)}
          className="w-full px-2 py-1.5 text-xs border border-gray-200 rounded-md text-wedding-navy focus:outline-none focus:ring-2 focus:ring-wedding-sage lg:text-[11px]"
        >
          <option value="">All weddings</option>
          {weddings.map((wedding) => (
            <option key={wedding.id} value={wedding.id}>
              {wedding.name}
            </option>
          ))}
        </select>
      )}

      {/* ===== DESKTOP LAYOUT: Vertical stacked cards ===== */}
      <div className="hidden lg:flex lg:flex-col" role="region" aria-label="Sponsored vendors">
        {displayVendors.map((vendor) => (
          <SponsoredVendorCard
            key={vendor._id}
            vendor={vendor}
            vendorProfile={vendorProfiles[vendor.vendor_profile_id]}
            onView={handleVendorClick}
            onRecordEvent={handleRecordEvent}
            onHide={handleVendorHide}
            whyTag={getWhyTag(vendor)}
            weddingId={selectedWeddingId || weddings?.[0]?.id}
            weddingName={selectedWedding?.name}
          />
        ))}
      </div>

      {/* ===== MOBILE LAYOUT: Horizontal scroll carousel ===== */}
      <div className="relative lg:hidden" role="region" aria-label="Sponsored vendors carousel" aria-roledescription="carousel">
        <div
          ref={scrollContainerRef}
          className="flex gap-3 overflow-x-auto scroll-smooth pb-2 snap-x snap-mandatory"
          role="list"
          aria-label="Sponsored vendor cards"
          style={{ WebkitOverflowScrolling: 'touch' }}
        >
          {sponsoredVendors.map((vendor, index) => (
            <div key={vendor._id} className="snap-start" role="listitem" aria-label={`Vendor ${index + 1} of ${sponsoredVendors.length}`}>
              <SponsoredVendorCard
                vendor={vendor}
                vendorProfile={vendorProfiles[vendor.vendor_profile_id]}
                onView={handleVendorClick}
                onRecordEvent={handleRecordEvent}
                onHide={handleVendorHide}
                whyTag={getWhyTag(vendor)}
                weddingId={selectedWeddingId || weddings?.[0]?.id}
                weddingName={selectedWedding?.name}
              />
            </div>
          ))}
        </div>
        {/* Left Arrow — 44px touch target */}
        {canScrollLeft && (
          <button
            onClick={() => scroll('left')}
            className="absolute left-0 top-1/2 -translate-y-1/2 z-20 w-11 h-11 flex items-center justify-center rounded-full bg-white shadow-md hover:shadow-lg text-wedding-navy transition-shadow"
            aria-label="Scroll to previous vendors"
          >
            <ChevronLeft size={18} />
          </button>
        )}
        {/* Right Arrow — 44px touch target */}
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

      {/* ===== FOOTER — Desktop: mockup style, Mobile: centered link ===== */}
      {/* Desktop footer */}
      <div className="hidden lg:flex justify-between pt-2 border-t border-gray-200">
        <button
          onClick={() => setShowTooltip(!showTooltip)}
          className="text-[10px] text-wedding-sage font-medium hover:underline"
          aria-expanded={showTooltip}
          aria-controls="desktop-tooltip"
        >
          Why am I seeing this?
        </button>
        <a
          href="/admin/vendors"
          className="text-[10px] text-wedding-sage font-medium hover:underline"
        >
          See more vendors ›
        </a>
      </div>
      {/* Desktop tooltip (below footer) */}
      {showTooltip && (
        <div id="desktop-tooltip" role="tooltip" className="hidden lg:block text-[10px] text-gray-600 bg-gray-50 px-3 py-2 rounded-md border border-gray-200">
          These vendors are sponsored recommendations matched to your wedding location, budget, and vendor needs. You can hide any vendor or adjust preferences.
        </div>
      )}
      {/* Mobile footer — contrast-safe gray-600 */}
      <div className="flex justify-center pt-2 lg:hidden">
        <a
          href="/admin/vendors"
          className="text-xs text-gray-600 hover:text-wedding-sage transition-colors"
        >
          See more vendors ›
        </a>
      </div>

      {/* Live region for screen reader announcements on vendor dismissal */}
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {dismissAnnouncement}
      </div>

      {/* Vendor Details Drawer — View 2 */}
      <SponsoredVendorDetailsDrawer
        vendor={drawerVendor}
        isOpen={!!drawerVendor}
        onClose={() => setDrawerVendor(null)}
        onRecordEvent={(eventType: string, sponsoredVendorId: string, vendorProfileId: string) => {
          handleRecordEvent(eventType as AdEventType, sponsoredVendorId, vendorProfileId);
        }}
        vendorProfile={drawerVendor ? vendorProfiles[drawerVendor.vendor_profile_id] : undefined}
        weddingId={selectedWeddingId || weddings?.[0]?.id}
        onAddToWedding={(vpId) => {
          handleRecordEvent('vendor_added_to_wedding', drawerVendor?._id || '', vpId);
        }}
        onRequestQuote={(vpId) => {
          const profile = vendorProfiles[vpId];
          if (profile?.email) {
            const weddingName = weddings?.find(w => w.id === selectedWeddingId)?.name || '';
            const subject = encodeURIComponent(`Quote Request - ${profile.business_name}${weddingName ? ` for ${weddingName}` : ''}`);
            const body = encodeURIComponent(`Hi ${profile.contact_name || profile.business_name},\n\nI would like to request a quote for your services.\n\nThank you`);
            window.open(`mailto:${profile.email}?subject=${subject}&body=${body}`, '_self');
          }
        }}
        onHideVendor={(vpId) => {
          handleVendorHide(vpId);
          setDrawerVendor(null);
        }}
      />
    </div>
  );
}
