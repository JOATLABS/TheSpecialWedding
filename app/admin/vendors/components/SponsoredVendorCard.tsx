'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Star, Phone, Mail, ExternalLink, X, Plus } from 'lucide-react';
import { SponsoredVendor, AdEventType, recordAdEvent } from '@/services/advertisingApi';
import { VendorProfile } from '@/services/vendorManagementApi';

interface SponsoredVendorCardProps {
  vendor: SponsoredVendor;
  vendorProfile?: VendorProfile;
  onView?: (vendorId: string) => void;
  onRecordEvent: (eventType: AdEventType, sponsoredVendorId: string, vendorProfileId: string, metadata?: Record<string, any>) => void;
  onHide?: (vendorProfileId: string) => void;
  /** Why-tag text explaining why this vendor is shown (e.g. "Serves Austin · You need a photographer") */
  whyTag?: string;
}

// Utility to generate UUID v4
function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function SponsoredVendorCard({
  vendor,
  vendorProfile,
  onView,
  onRecordEvent,
  onHide,
  whyTag,
}: SponsoredVendorCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [hasRecordedImpressionServed, setHasRecordedImpressionServed] = useState(false);
  const [hasRecordedViewableImpression, setHasRecordedViewableImpression] = useState(false);
  const [clickId] = useState(generateUUID());
  const [isHidden, setIsHidden] = useState(false);

  // Record impression_served on mount (card rendered)
  useEffect(() => {
    if (!hasRecordedImpressionServed) {
      onRecordEvent('impression_served', vendor._id, vendor.vendor_profile_id, { click_id: clickId });
      setHasRecordedImpressionServed(true);
    }
  }, [vendor._id, vendor.vendor_profile_id, hasRecordedImpressionServed, onRecordEvent, clickId]);

  // IntersectionObserver for viewable_impression tracking
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !hasRecordedViewableImpression) {
            // Card is visible, set a timeout for 1+ seconds
            const timer = setTimeout(() => {
              if (!hasRecordedViewableImpression) {
                onRecordEvent('impression_viewable', vendor._id, vendor.vendor_profile_id, { click_id: clickId });
                setHasRecordedViewableImpression(true);
              }
            }, 1000);

            return () => clearTimeout(timer);
          }
        });
      },
      { threshold: 0.5 }
    );

    if (cardRef.current) {
      observer.observe(cardRef.current);
    }

    return () => {
      if (cardRef.current) {
        observer.unobserve(cardRef.current);
      }
    };
  }, [vendor._id, vendor.vendor_profile_id, hasRecordedViewableImpression, onRecordEvent, clickId]);

  const handleAddToWedding = () => {
    onRecordEvent('vendor_added_to_wedding', vendor._id, vendor.vendor_profile_id, { click_id: clickId });
    // TODO: Implement actual add to wedding logic
    console.log('Add to wedding:', vendor.vendor_profile_id);
  };

  const handleViewDetails = () => {
    onRecordEvent('vendor_profile_view', vendor._id, vendor.vendor_profile_id, { click_id: clickId });
    if (onView) {
      onView(vendor.vendor_profile_id);
    }
  };

  const handleContactClick = () => {
    onRecordEvent('contact_click', vendor._id, vendor.vendor_profile_id, { click_id: clickId });
    if (vendorProfile?.website) {
      window.open(vendorProfile.website, '_blank');
    } else if (vendorProfile?.email) {
      window.location.href = `mailto:${vendorProfile.email}`;
    }
  };

  const handleHide = () => {
    setIsHidden(true);
    onRecordEvent('dismiss', vendor._id, vendor.vendor_profile_id, { click_id: clickId });
    if (onHide) {
      onHide(vendor.vendor_profile_id);
    }
  };

  const priceRange =
    vendorProfile?.typical_price_min && vendorProfile?.typical_price_max
      ? `${vendorProfile.currency} ${Math.round(vendorProfile.typical_price_min).toLocaleString()}-${Math.round(vendorProfile.typical_price_max).toLocaleString()}`
      : null;

  // Don't render if hidden
  if (isHidden) {
    return null;
  }

  return (
    <div
      ref={cardRef}
      className="relative w-72 flex-shrink-0 lg:w-full lg:flex-shrink rounded-lg border border-gray-200 bg-white shadow-sm hover:shadow-md hover:border-wedding-sage transition-all cursor-pointer overflow-hidden lg:mb-2.5"
      onClick={() => onView?.(vendor.vendor_profile_id)}
    >
      {/* Hide Button — top right */}
      <button
        onClick={(e) => { e.stopPropagation(); handleHide(); }}
        className="absolute top-2 right-2 z-10 p-1 rounded-full hover:bg-gray-100 transition-colors text-gray-300 hover:text-red-400"
        aria-label="Hide this vendor"
        title="Hide this vendor"
      >
        <X size={14} />
      </button>

      {/* Content */}
      <div className="p-3 space-y-2">
        {/* Sponsored Badge */}
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide rounded bg-amber-50 text-amber-700">
          ✦ Sponsored
        </span>
        {/* Vendor Image Placeholder */}
        <div className="w-full h-20 rounded-md bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center text-2xl">
          {vendorProfile?.service_category === 'photographer' ? '📸' :
           vendorProfile?.service_category === 'florist' ? '💐' :
           vendorProfile?.service_category === 'dj' || vendorProfile?.service_category === 'live_music' ? '🎶' :
           vendorProfile?.service_category === 'catering' ? '🍽' :
           vendorProfile?.service_category === 'venue' ? '🏛' : '🏢'}
        </div>

        {/* Business Name & Meta */}
        <div>
          <h3 className="text-[13px] font-bold text-wedding-navy line-clamp-1">
            {vendorProfile?.business_name || 'Vendor'}
          </h3>
          <p className="text-[11px] text-gray-500 mt-0.5">
            {vendorProfile?.service_category?.replace(/_/g, ' ') || 'Service'}
            {vendorProfile?.city ? ` · ${vendorProfile.city}${vendorProfile.state ? `, ${vendorProfile.state}` : ''}` : ''}
            {priceRange ? ` · ${priceRange}` : ''}
          </p>
        </div>

        {/* Why Tag — contextual relevance */}
        {whyTag && (
          <div className="text-[10px] text-wedding-sage bg-wedding-sage/5 px-2 py-1 rounded">
            {whyTag}
          </div>
        )}

        {/* Headline (if set by admin) */}
        {vendor.headline && (
          <p className="text-xs font-medium text-wedding-navy line-clamp-1">{vendor.headline}</p>
        )}

        {/* Dual CTA Row — matches mockup cta-row */}
        <div className="flex gap-1.5">
          <button
            onClick={(e) => { e.stopPropagation(); handleAddToWedding(); }}
            className="flex-1 px-2 py-1.5 text-[11px] font-semibold text-white bg-wedding-sage hover:bg-wedding-navy rounded-md transition-colors text-center"
          >
            + Add to Wedding
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); handleContactClick(); }}
            className="flex-1 px-2 py-1.5 text-[11px] font-semibold text-wedding-sage bg-white border border-wedding-sage hover:bg-wedding-sage/5 rounded-md transition-colors text-center"
          >
            Request Quote
          </button>
        </div>
      </div>
    </div>
  );
}
