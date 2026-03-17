'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Star, X, Camera, Flower2, Music, UtensilsCrossed, Building2, Video, MapPin } from 'lucide-react';
import {
  type SponsoredVendor,
  type AdEventType,
  type AdPlacement,
  createAdLead,
} from '@/services/advertisingApi';
import { type VendorProfile, assignVendorToWedding } from '@/services/vendorManagementApi';
import { useAdmin } from '@/contexts/AdminContext';

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
  /** Current wedding ID for vendor assignment */
  weddingId?: string;
  /** Current wedding name for mailto subject line */
  weddingName?: string;
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
 * - 120px image header with "Boosted" gold gradient badge
 * - "Sponsored" text badge on card body
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
  weddingId,
  weddingName,
}: BoostedVendorCardProps) {
  const { token } = useAdmin();
  const cardRef = useRef<HTMLDivElement>(null);
  const [hasRecordedImpressionServed, setHasRecordedImpressionServed] = useState(false);
  const [hasRecordedViewableImpression, setHasRecordedViewableImpression] = useState(false);
  const [clickId] = useState(generateUUID());
  const [isHidden, setIsHidden] = useState(false);
  const [addedToWedding, setAddedToWedding] = useState(false);
  const [addToWeddingError, setAddToWeddingError] = useState<string | null>(null);

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

  const handleAddToWedding = async () => {
    onRecordEvent('vendor_added_to_wedding', vendor._id, vendor.vendor_profile_id, { click_id: clickId });

    if (!token || !weddingId) {
      // No wedding context — navigate to vendor profile instead
      if (onView) onView(vendor.vendor_profile_id);
      return;
    }

    try {
      setAddToWeddingError(null);
      await assignVendorToWedding(token, {
        vendor_profile_id: vendor.vendor_profile_id,
        wedding_id: weddingId,
      });

      // Record ad lead for attribution (best-effort)
      await createAdLead(token, {
        sponsored_vendor_id: vendor._id,
        vendor_profile_id: vendor.vendor_profile_id,
        wedding_id: weddingId,
        lead_type: 'add_to_wedding',
        click_id: clickId,
        placement: vendor.placement as AdPlacement,
        metadata: { source: 'boosted_vendor_card' },
      }).catch(() => {});

      setAddedToWedding(true);
    } catch (err: any) {
      const msg = err?.message || 'Could not add vendor';
      if (msg.toLowerCase().includes('already') || msg.toLowerCase().includes('duplicate')) {
        setAddedToWedding(true);
      } else {
        setAddToWeddingError(msg);
      }
    }
  };

  const handleRequestQuote = () => {
    onRecordEvent('contact_click', vendor._id, vendor.vendor_profile_id, { click_id: clickId });

    // Create ad lead (best-effort)
    if (token) {
      createAdLead(token, {
        sponsored_vendor_id: vendor._id,
        vendor_profile_id: vendor.vendor_profile_id,
        wedding_id: weddingId,
        lead_type: 'quote_request',
        click_id: clickId,
        placement: vendor.placement as AdPlacement,
        metadata: { source: 'boosted_vendor_card' },
      }).catch(() => {});
    }

    // Open planner's email client with vendor email pre-filled
    if (vendorProfile?.email) {
      const name = vendorProfile.business_name || 'Vendor';
      const subject = encodeURIComponent(
        weddingName
          ? `Quote Request – ${name} for ${weddingName}`
          : `Quote Request – ${name}`
      );
      const body = encodeURIComponent(
        `Hi ${vendorProfile.contact_name || name},\n\nI found your profile on The Special Wedding and would love to discuss your services${weddingName ? ` for our wedding (${weddingName})` : ''}.\n\nCould you provide a quote for your services?\n\nThank you!`
      );
      window.location.href = `mailto:${vendorProfile.email}?subject=${subject}&body=${body}`;
    } else {
      if (onView) onView(vendor.vendor_profile_id);
    }
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

  const getCategoryIcon = (): React.ReactNode => {
    const iconProps = { size: 32, className: 'text-gray-400' };
    switch (vendorProfile?.service_category) {
      case 'photographer': return <Camera {...iconProps} />;
      case 'florist': return <Flower2 {...iconProps} />;
      case 'dj': case 'live_music': case 'band': return <Music {...iconProps} />;
      case 'caterer': case 'catering': return <UtensilsCrossed {...iconProps} />;
      case 'venue': return <Building2 {...iconProps} />;
      case 'videographer': return <Video {...iconProps} />;
      default: return <Building2 {...iconProps} />;
    }
  };

  if (isHidden) return null;

  return (
    <article
      ref={cardRef}
      role="article"
      aria-label={`Boosted vendor: ${businessName}`}
      className="bg-white border border-gray-200 rounded-xl overflow-hidden hover:shadow-lg transition-all cursor-pointer group relative focus-within:ring-2 focus-within:ring-wedding-sage focus-within:ring-offset-1"
    >
      {/* Image Header — 120px with Boosted badge */}
      <div className="relative h-[120px]">
        {vendorProfile?.logo_url ? (
          <img
            src={vendorProfile.logo_url}
            alt={`${businessName} logo`}
            className="w-full h-full object-cover bg-gray-100"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center" aria-hidden="true">
            {getCategoryIcon()}
          </div>
        )}
        {/* Boosted Badge — gold gradient */}
        <span className="absolute top-2 left-2 bg-gradient-to-r from-wedding-gold to-amber-600 text-white text-[9px] font-extrabold uppercase tracking-wider px-2 py-1 rounded shadow-md">
          Boosted
        </span>
      </div>

      {/* Card Body */}
      <div className="p-3.5">
        {/* Sponsored Badge */}
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide rounded bg-amber-50 text-amber-700 mb-1" aria-label="Sponsored">
          Sponsored
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
            <p className="text-[11px] text-gray-600 mb-1 flex items-center gap-1">
              <MapPin size={10} className="text-gray-400 flex-shrink-0" />
              {vendorProfile.city}{vendorProfile.state ? `, ${vendorProfile.state}` : ''}
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
            disabled={addedToWedding}
            className={`flex-1 px-2 py-1.5 text-[10px] font-semibold rounded-md transition-colors text-center min-h-[44px] focus:ring-2 focus:ring-wedding-sage focus:ring-offset-1 ${
              addedToWedding
                ? 'bg-green-100 text-green-700 cursor-default'
                : 'text-white bg-wedding-sage hover:bg-wedding-navy'
            }`}
            aria-label={addedToWedding ? `${businessName} added to wedding` : `Add ${businessName} to wedding`}
          >
            {addedToWedding ? 'Added' : '+ Add to Wedding'}
          </button>
          <button
            onClick={handleRequestQuote}
            className="flex-1 px-2 py-1.5 text-[10px] font-semibold text-wedding-sage bg-white border border-wedding-sage hover:bg-wedding-sage/5 rounded-md transition-colors text-center min-h-[44px] focus:ring-2 focus:ring-wedding-sage focus:ring-offset-1"
            aria-label={`Request quote from ${businessName}`}
          >
            Request Quote
          </button>
        </div>
        {addToWeddingError && (
          <p className="text-[9px] text-red-500 mt-1">{addToWeddingError}</p>
        )}
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
