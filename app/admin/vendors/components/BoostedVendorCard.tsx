'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Star, X } from 'lucide-react';
import {
  type SponsoredVendor,
  type AdEventType,
} from '@/services/advertisingApi';
import { type VendorProfile } from '@/services/vendorManagementApi';

interface BoostedVendorCardProps {
  vendor: SponsoredVendor;
  vendorProfile?: VendorProfile;
  onView?: (vendorId: string) => void;
  onRecordEvent: (
    eventType: AdEventType,
    sponsoredVendorId: string,
    vendorProfileId: string,
    metadata?: Record<string, any>
  ) => void;
  onHide?: (vendorProfileId: string) => void;
  onAddToWedding?: (vendorProfileId: string) => void;
  onRequestQuote?: (vendorProfileId: string) => void;
}

// Utility to generate UUID v4
function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * BoostedVendorCard — Directory Boost variant of SponsoredVendorCard.
 *
 * Matches mockup View 3 spec:
 * - Grid card layout matching organic vendor cards (3-col grid)
 * - 120px image header with "⚡ Boosted" gold gradient badge
 * - "✦ Sponsored" text badge on card body
 * - Vendor name (14px bold), category (11px sage), location (11px), rating stars
 * - Price range
 * - Dual CTA: "+ Add to Wedding" + "Request Quote"
 */
export function BoostedVendorCard({
  vendor,
  vendorProfile,
  onView,
  onRecordEvent,
  onHide,
  onAddToWedding,
  onRequestQuote,
}: BoostedVendorCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [hasRecordedImpressionServed, setHasRecordedImpressionServed] = useState(false);
  const [hasRecordedViewableImpression, setHasRecordedViewableImpression] = useState(false);
  const [clickId] = useState(generateUUID());
  const [isHidden, setIsHidden] = useState(false);

  // Record impression_served on mount
  useEffect(() => {
    if (!hasRecordedImpressionServed) {
      onRecordEvent('impression_served', vendor._id, vendor.vendor_profile_id, {
        click_id: clickId,
        placement: 'directory_boost',
      });
      setHasRecordedImpressionServed(true);
    }
  }, [vendor._id, vendor.vendor_profile_id, hasRecordedImpressionServed, onRecordEvent, clickId]);

  // IntersectionObserver for viewable impression (50% visible for 1+ sec)
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !hasRecordedViewableImpression) {
            const timer = setTimeout(() => {
              if (!hasRecordedViewableImpression) {
                onRecordEvent('impression_viewable', vendor._id, vendor.vendor_profile_id, {
                  click_id: clickId,
                  placement: 'directory_boost',
                });
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

  const handleViewDetails = () => {
    onRecordEvent('vendor_profile_view', vendor._id, vendor.vendor_profile_id, { click_id: clickId });
    if (onView) onView(vendor.vendor_profile_id);
  };

  const handleAddToWedding = () => {
    onRecordEvent('vendor_added_to_wedding', vendor._id, vendor.vendor_profile_id, { click_id: clickId });
    if (onAddToWedding) onAddToWedding(vendor.vendor_profile_id);
  };

  const handleRequestQuote = () => {
    onRecordEvent('contact_click', vendor._id, vendor.vendor_profile_id, { click_id: clickId });
    if (onRequestQuote) onRequestQuote(vendor.vendor_profile_id);
  };

  const handleHide = () => {
    setIsHidden(true);
    onRecordEvent('dismiss', vendor._id, vendor.vendor_profile_id, { click_id: clickId });
    if (onHide) onHide(vendor.vendor_profile_id);
  };

  const currencySymbol = vendorProfile?.currency || '$';
  const priceRange =
    vendorProfile?.typical_price_min && vendorProfile?.typical_price_max
      ? `${currencySymbol}${Math.round(vendorProfile.typical_price_min).toLocaleString()} – ${currencySymbol}${Math.round(vendorProfile.typical_price_max).toLocaleString()}`
      : null;

  const businessName = vendorProfile?.business_name || 'Vendor';
  const categoryLabel = vendorProfile?.service_category?.replace(/_/g, ' ') || 'Service';
  const categoryEmoji =
    vendorProfile?.service_category === 'photographer' ? '📸' :
    vendorProfile?.service_category === 'florist' ? '💐' :
    vendorProfile?.service_category === 'dj' || vendorProfile?.service_category === 'live_music' ? '🎶' :
    vendorProfile?.service_category === 'catering' ? '🍽' :
    vendorProfile?.service_category === 'venue' ? '🏛' :
    vendorProfile?.service_category === 'videographer' ? '📷' : '🏢';

  if (isHidden) return null;

  return (
    <article
      ref={cardRef}
      role="article"
      aria-label={`Boosted vendor: ${businessName}`}
      className="bg-white border border-gray-200 rounded-xl overflow-hidden hover:shadow-lg transition-all cursor-pointer group relative focus-within:ring-2 focus-within:ring-wedding-sage focus-within:ring-offset-1"
    >
      {/* Image Header — 120px with Boosted badge */}
      <div className="relative h-[120px] bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center text-[32px]" aria-hidden="true">
        {categoryEmoji}
        {/* ⚡ Boosted Badge — gold gradient, matches mockup */}
        <span className="absolute top-2 left-2 bg-gradient-to-r from-wedding-gold to-amber-600 text-white text-[9px] font-extrabold uppercase tracking-wider px-2 py-1 rounded shadow-md">
          ⚡ Boosted
        </span>
      </div>

      {/* Card Body */}
      <div className="p-3.5">
        {/* Sponsored Badge */}
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide rounded bg-amber-50 text-amber-700 mb-1" aria-label="Sponsored">
          ✦ Sponsored
        </span>

        {/* Clickable area */}
        <a
          href={`/vendors/${vendor.vendor_profile_id}`}
          onClick={(e) => {
            e.preventDefault();
            handleViewDetails();
          }}
          className="block no-underline focus:ring-2 focus:ring-wedding-sage focus:ring-offset-1 rounded"
          aria-label={`View ${businessName} details`}
        >
          {/* Vendor Name */}
          <h3 className="text-sm font-bold text-wedding-navy mb-0.5 line-clamp-1">{businessName}</h3>
          {/* Category */}
          <p className="text-[11px] font-semibold text-wedding-sage mb-1 capitalize">{categoryLabel}</p>
          {/* Location */}
          {vendorProfile?.city && (
            <p className="text-[11px] text-gray-600 mb-1">
              📍 {vendorProfile.city}{vendorProfile.state ? `, ${vendorProfile.state}` : ''}
              {vendorProfile.service_radius ? ` · ${vendorProfile.service_radius}mi radius` : ''}
            </p>
          )}
          {/* Rating */}
          {vendorProfile?.internal_rating && vendorProfile.internal_rating > 0 && (
            <div className="flex items-center gap-1 mt-1.5 mb-1">
              {[...Array(5)].map((_, i) => (
                <Star
                  key={i}
                  size={12}
                  className={i < (vendorProfile.internal_rating || 0) ? 'text-amber-400 fill-amber-400' : 'text-gray-300'}
                />
              ))}
              <span className="text-[11px] text-gray-600 ml-1">
                {vendorProfile.internal_rating.toFixed(1)}
                {vendorProfile.weddings_count ? ` (${vendorProfile.weddings_count})` : ''}
              </span>
            </div>
          )}
          {/* Price Range */}
          {priceRange && (
            <p className="text-[11px] font-bold text-wedding-navy mt-1.5">{priceRange}</p>
          )}
        </a>

        {/* Dual CTA Row */}
        <div className="flex gap-1 mt-2">
          <button
            onClick={handleAddToWedding}
            className="flex-1 px-2 py-1.5 text-[10px] font-semibold text-white bg-wedding-sage hover:bg-wedding-navy rounded-md transition-colors text-center min-h-[44px] focus:ring-2 focus:ring-wedding-sage focus:ring-offset-1"
          >
            + Add to Wedding
          </button>
          <button
            onClick={handleRequestQuote}
            className="flex-1 px-2 py-1.5 text-[10px] font-semibold text-wedding-sage bg-white border border-wedding-sage hover:bg-wedding-sage/5 rounded-md transition-colors text-center min-h-[44px] focus:ring-2 focus:ring-wedding-sage focus:ring-offset-1"
          >
            Request Quote
          </button>
        </div>
      </div>

      {/* Hide button */}
      <button
        onClick={(e) => { e.stopPropagation(); handleHide(); }}
        className="absolute top-2 right-2 z-10 w-11 h-11 flex items-center justify-center rounded-full bg-black/20 text-white hover:bg-red-500 transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100 focus:ring-2 focus:ring-white focus:ring-offset-1"
        aria-label={`Hide ${businessName} from boosted results`}
        title="Hide this vendor"
      >
        <X size={12} />
      </button>
    </article>
  );
}
