'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Star, Phone, Mail, ExternalLink, X, Plus, Camera, Flower2, Music, UtensilsCrossed, Building2, Video, MapPin } from 'lucide-react';
import { SponsoredVendor, AdEventType, recordAdEvent, createAdLead, type AdPlacement } from '@/services/advertisingApi';
import { VendorProfile, assignVendorToWedding } from '@/services/vendorManagementApi';
import { useAdmin } from '@/contexts/AdminContext';

/** Maps service categories to Lucide icons for the image placeholder */
function getCategoryIcon(category?: string): React.ReactNode {
  const iconProps = { size: 28, className: 'text-gray-400' };
  switch (category) {
    case 'photographer': return <Camera {...iconProps} />;
    case 'florist': return <Flower2 {...iconProps} />;
    case 'dj': case 'live_music': case 'band': return <Music {...iconProps} />;
    case 'caterer': case 'catering': return <UtensilsCrossed {...iconProps} />;
    case 'venue': return <Building2 {...iconProps} />;
    case 'videographer': return <Video {...iconProps} />;
    default: return <Building2 {...iconProps} />;
  }
}

interface SponsoredVendorCardProps {
  vendor: SponsoredVendor;
  vendorProfile?: VendorProfile;
  onView?: (vendorId: string) => void;
  onRecordEvent: (eventType: AdEventType, sponsoredVendorId: string, vendorProfileId: string, metadata?: Record<string, any>) => void;
  onHide?: (vendorProfileId: string) => void;
  /** Why-tag text explaining why this vendor is shown (e.g. "Serves Austin · You need a photographer") */
  whyTag?: string;
  /** Current wedding ID for vendor assignment */
  weddingId?: string;
  /** Current wedding name for the mailto subject line */
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

export function SponsoredVendorCard({
  vendor,
  vendorProfile,
  onView,
  onRecordEvent,
  onHide,
  whyTag,
  weddingId,
  weddingName,
}: SponsoredVendorCardProps) {
  const { token } = useAdmin();
  const cardRef = useRef<HTMLDivElement>(null);
  const [hasRecordedImpressionServed, setHasRecordedImpressionServed] = useState(false);
  const [hasRecordedViewableImpression, setHasRecordedViewableImpression] = useState(false);
  const [clickId] = useState(generateUUID());
  const [isHidden, setIsHidden] = useState(false);
  const [addedToWedding, setAddedToWedding] = useState(false);
  const [addToWeddingError, setAddToWeddingError] = useState<string | null>(null);

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

  const handleAddToWedding = async () => {
    onRecordEvent('vendor_added_to_wedding', vendor._id, vendor.vendor_profile_id, { click_id: clickId });

    if (!token || !weddingId) {
      // Fallback: navigate to vendor profile if no wedding context
      if (onView) onView(vendor.vendor_profile_id);
      return;
    }

    try {
      setAddToWeddingError(null);
      // Create VendorAssignment record
      await assignVendorToWedding(token, {
        vendor_profile_id: vendor.vendor_profile_id,
        wedding_id: weddingId,
      });

      // Also record an ad lead for attribution
      await createAdLead(token, {
        sponsored_vendor_id: vendor._id,
        vendor_profile_id: vendor.vendor_profile_id,
        wedding_id: weddingId,
        lead_type: 'add_to_wedding',
        click_id: clickId,
        placement: vendor.placement as AdPlacement,
        metadata: { source: 'sponsored_vendor_card' },
      }).catch(() => { /* lead creation is best-effort */ });

      setAddedToWedding(true);
    } catch (err: any) {
      const msg = err?.message || 'Could not add vendor';
      // If already assigned, treat as success
      if (msg.toLowerCase().includes('already') || msg.toLowerCase().includes('duplicate')) {
        setAddedToWedding(true);
      } else {
        setAddToWeddingError(msg);
      }
    }
  };

  const handleViewDetails = () => {
    onRecordEvent('vendor_profile_view', vendor._id, vendor.vendor_profile_id, { click_id: clickId });
    if (onView) {
      onView(vendor.vendor_profile_id);
    }
  };

  const handleRequestQuote = () => {
    onRecordEvent('contact_click', vendor._id, vendor.vendor_profile_id, { click_id: clickId });

    // Create ad lead (best-effort, don't block the mailto)
    if (token) {
      createAdLead(token, {
        sponsored_vendor_id: vendor._id,
        vendor_profile_id: vendor.vendor_profile_id,
        wedding_id: weddingId,
        lead_type: 'quote_request',
        click_id: clickId,
        placement: vendor.placement as AdPlacement,
        metadata: { source: 'sponsored_vendor_card' },
      }).catch(() => { /* best-effort */ });
    }

    // Open the planner's email client with vendor email pre-filled
    if (vendorProfile?.email) {
      const businessName = vendorProfile.business_name || 'Vendor';
      const subject = encodeURIComponent(
        weddingName
          ? `Quote Request – ${businessName} for ${weddingName}`
          : `Quote Request – ${businessName}`
      );
      const body = encodeURIComponent(
        `Hi ${vendorProfile.contact_name || businessName},\n\nI found your profile on The Special Wedding and would love to discuss your services${weddingName ? ` for our wedding (${weddingName})` : ''}.\n\nCould you provide a quote for your services?\n\nThank you!`
      );
      window.location.href = `mailto:${vendorProfile.email}?subject=${subject}&body=${body}`;
    } else {
      // No email available — fall back to vendor profile page
      if (onView) onView(vendor.vendor_profile_id);
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
          Sponsored
        </span>
        {/* Vendor Image */}
        {vendorProfile?.logo_url ? (
          <img
            src={vendorProfile.logo_url}
            alt={`${businessName} logo`}
            className="w-full h-20 rounded-md object-cover bg-gray-100"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-20 rounded-md bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center" aria-hidden="true">
            {getCategoryIcon(vendorProfile?.service_category)}
          </div>
        )}

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
          disabled={addedToWedding}
          className={`flex-1 px-2 py-1.5 text-[11px] font-semibold rounded-md transition-colors text-center min-h-[44px] ${
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
          className="flex-1 px-2 py-1.5 text-[11px] font-semibold text-wedding-sage bg-white border border-wedding-sage hover:bg-wedding-sage/5 rounded-md transition-colors text-center min-h-[44px]"
          aria-label={`Request quote from ${businessName}`}
        >
          Request Quote
        </button>
      </div>
      {addToWeddingError && (
        <p className="px-3 pb-2 text-[10px] text-red-500">{addToWeddingError}</p>
      )}
    </article>
  );
}
