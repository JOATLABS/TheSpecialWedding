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
    <div ref={cardRef} className="relative flex-shrink-0 w-80 rounded-lg border border-gray-200 bg-white shadow-sm hover:shadow-md transition-shadow overflow-hidden">
      {/* Gradient Border Top */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-wedding-sage via-wedding-gold to-wedding-rose opacity-60" />

      {/* Sponsored Badge & Hide Button */}
      <div className="absolute top-3 right-3 z-10 flex items-center gap-2">
        <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-wedding-sage bg-wedding-sage/10 rounded-full">
          Sponsored
        </span>
        <button
          onClick={handleHide}
          className="p-1.5 rounded-full hover:bg-gray-100 transition-colors text-gray-400 hover:text-gray-600"
          aria-label="Hide vendor"
          title="Hide vendor"
        >
          <X size={16} />
        </button>
      </div>

      {/* Content */}
      <div className="p-4 space-y-3">
        {/* Business Name & Category */}
        <div>
          <h3 className="text-lg font-semibold text-wedding-navy line-clamp-2">
            {vendorProfile?.business_name || 'Vendor'}
          </h3>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs font-medium px-2 py-1 rounded-full bg-wedding-ivory text-wedding-navy">
              {vendorProfile?.service_category.replace(/_/g, ' ').toLowerCase() || 'Service'}
            </span>
            {vendor.priority > 0 && (
              <span className="text-xs text-gray-500">Priority {vendor.priority}</span>
            )}
          </div>
        </div>

        {/* Headline & Description */}
        {vendor.headline && (
          <div>
            <p className="text-sm font-medium text-wedding-navy">{vendor.headline}</p>
          </div>
        )}

        {vendor.description && (
          <p className="text-sm text-gray-600 line-clamp-2">{vendor.description}</p>
        )}

        {/* Price Range & Rating */}
        <div className="flex items-center justify-between pt-1">
          {priceRange && (
            <span className="text-xs font-medium text-gray-600">{priceRange}</span>
          )}
          {vendorProfile?.internal_rating && (
            <div className="flex items-center gap-1">
              {[...Array(5)].map((_, i) => (
                <Star
                  key={i}
                  size={12}
                  className={
                    i < Math.round(vendorProfile.internal_rating || 0)
                      ? 'fill-wedding-gold text-wedding-gold'
                      : 'text-gray-300'
                  }
                />
              ))}
            </div>
          )}
        </div>

        {/* Contact Info */}
        {vendorProfile && (
          <div className="flex gap-2 pt-2 text-gray-500">
            {vendorProfile.phone && (
              <a
                href={`tel:${vendorProfile.phone}`}
                className="hover:text-wedding-sage transition-colors"
                title="Call vendor"
              >
                <Phone size={16} />
              </a>
            )}
            {vendorProfile.email && (
              <a
                href={`mailto:${vendorProfile.email}`}
                className="hover:text-wedding-sage transition-colors"
                title="Email vendor"
              >
                <Mail size={16} />
              </a>
            )}
            {vendorProfile.website && (
              <a
                href={vendorProfile.website}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-wedding-sage transition-colors"
                title="Visit website"
              >
                <ExternalLink size={16} />
              </a>
            )}
          </div>
        )}

        {/* Action Buttons */}
        <div className="space-y-2 pt-3 border-t border-gray-100">
          {/* Primary: Add to Wedding */}
          <button
            onClick={handleAddToWedding}
            className="w-full px-3 py-2.5 text-sm font-medium text-white bg-wedding-sage hover:bg-wedding-sage/90 rounded-md transition-colors flex items-center justify-center gap-2"
          >
            <Plus size={16} />
            Add to wedding
          </button>

          {/* Secondary: View Details */}
          <button
            onClick={handleViewDetails}
            className="w-full px-3 py-2 text-sm font-medium text-wedding-navy border border-wedding-navy hover:bg-wedding-ivory rounded-md transition-colors"
          >
            View Details
          </button>

          {/* Tertiary: Contact */}
          <button
            onClick={handleContactClick}
            className="w-full px-3 py-2 text-sm font-medium text-wedding-sage hover:text-wedding-sage/80 transition-colors text-center"
          >
            Contact
          </button>
        </div>

        {/* Event Tracking Stats */}
        {(vendor.impression_count > 0 || vendor.click_count > 0) && (
          <div className="text-xs text-gray-500 space-y-0.5 pt-1 border-t border-gray-100">
            <div>
              {vendor.impression_count} views • {vendor.click_count} interactions
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
