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

  const businessName = vendorProfile?.business_name || 'Vendor';

  return (
    <article
      ref={cardRef}
      role="article"
      aria-label={`Sponsored vendor: ${businessName}`}
      className="relative w-72 flex-shrink-0 lg:w-full lg:flex-shrink rounded-lg border border-gray-200 bg-white shadow-sm hover:shadow-md hover:border-wedding-sage transition-all overflow-hidden lg:mb-2.5 focus-within:ring-2 focus-within:ring-wedding-sage focus-within:ring-offset-1"
    >
      {/* Hide Button — top right, 44px touch target */}
      <button
        onClick={(e) => { e.stopPropagation(); handleHide(); }}
        className="absolute top-1 right-1 z-10 w-11 h-11 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors text-gray-500 hover:text-red-500"
        aria-label={`Hide ${businessName} from sponsored vendors`}
        title="Hide this vendor"
      >
        <X size={14} />
      </button>

      {/* Clickable card area — keyboard accessible */}
      <a
        href={`/vendors/${vendor.vendor_profile_id}`}
        onClick={(e) => {
          e.preventDefault();
          handleViewDetails();
        }}
        className="block p-3 space-y-2 text-left no-underline focus:outline-none"
        aria-label={`View ${businessName} details`}
      >
        {/* Sponsored Badge */}
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide rounded bg-amber-50 text-amber-700" aria-label="Sponsored">
          ✦ Sponsored
        </span>
        {/* Vendor Image Placeholder */}
        <div className="w-full h-20 rounded-md bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center text-2xl" aria-hidden="true">
          {vendorProfile?.service_category === 'photographer' ? '📸' :
           vendorProfile?.service_category === 'florist' ? '💐' :
           vendorProfile?.service_category === 'dj' || vendorProfile?.service_category === 'live_music' ? '🎶' :
           vendorProfile?.service_category === 'catering' ? '🍽' :
           vendorProfile?.service_category === 'venue' ? '🏛' : '🏢'}
        </div>

        {/* Business Name & Meta — contrast-safe gray-600 on white (5.7:1) */}
        <div>
          <h3 className="text-[13px] font-bold text-wedding-navy line-clamp-1">
            {businessName}
          </h3>
          <p className="text-[11px] text-gray-600 mt-0.5">
            {vendorProfile?.service_category?.replace(/_/g, ' ') || 'Service'}
            {vendorProfile?.city ? ` · ${vendorProfile.city}${vendorProfile.state ? `, ${vendorProfile.state}` : ''}` : ''}
            {priceRange ? ` · ${priceRange}` : ''}
          </p>
        </div>

        {/* Why Tag — contextual relevance */}
        {whyTag && (
          <div className="text-[10px] text-wedding-sage bg-wedding-sage/5 px-2 py-1.5 rounded">
            {whyTag}
          </div>
        )}

        {/* Headline (if set by admin) */}
        {vendor.headline && (
          <p className="text-xs font-medium text-wedding-navy line-clamp-1">{vendor.headline}</p>
        )}
      </a>

      {/* Dual CTA Row — outside the link to avoid nested interactive elements */}
      <div className="flex gap-1.5 px-3 pb-3">
        <button
          onClick={handleAddToWedding}
          className="flex-1 px-2 py-1.5 text-[11px] font-semibold text-white bg-wedding-sage hover:bg-wedding-navy rounded-md transition-colors text-center min-h-[44px]"
        >
          + Add to Wedding
        </button>
        <button
          onClick={handleContactClick}
          className="flex-1 px-2 py-1.5 text-[11px] font-semibold text-wedding-sage bg-white border border-wedding-sage hover:bg-wedding-sage/5 rounded-md transition-colors text-center min-h-[44px]"
        >
          Request Quote
        </button>
      </div>
    </article>
  );
}
