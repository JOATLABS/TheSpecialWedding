'use client';

import React, { useState, useEffect, useRef } from 'react';
import { ChevronLeft, ChevronRight, Sparkles } from 'lucide-react';
import {
  getSponsoredVendors,
  recordAdEvent,
  type SponsoredVendor,
  type AdPlacement,
  type AdEventType,
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
}

type SkeletonCard = { id: string; type: 'skeleton' };

export function SponsoredVendorsRail({
  placement = 'vendor_rail',
  category,
  weddingStage,
  maxItems = 6,
  onVendorClick,
}: SponsoredVendorsRailProps) {
  const { token } = useAdmin();
  const [sponsoredVendors, setSponsoredVendors] = useState<SponsoredVendor[]>([]);
  const [vendorProfiles, setVendorProfiles] = useState<Record<string, VendorProfile>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  // Fetch sponsored vendors on mount
  useEffect(() => {
    const fetchData = async () => {
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        // Fetch sponsored vendors
        const vendors = await getSponsoredVendors(token, {
          placement,
          category,
          wedding_stage: weddingStage,
          limit: maxItems,
        });

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
  }, [token, placement, category, weddingStage, maxItems]);

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
    vendorProfileId: string
  ) => {
    if (!token) return;

    try {
      await recordAdEvent(token, {
        sponsored_vendor_id: sponsoredVendorId,
        vendor_profile_id: vendorProfileId,
        event_type: eventType,
        placement,
      });
    } catch (err) {
      console.error('Failed to record event:', err);
    }
  };

  // Handle vendor click
  const handleVendorClick = (vendorProfileId: string) => {
    if (onVendorClick) {
      onVendorClick(vendorProfileId);
    }
  };

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
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <Sparkles size={16} className="text-wedding-gold" />
        <h2 className="text-lg font-semibold text-wedding-navy">Recommended for you</h2>
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
    </div>
  );
}
