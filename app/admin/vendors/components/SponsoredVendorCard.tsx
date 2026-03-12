'use client';

import React, { useState, useEffect } from 'react';
import { Star, Phone, Mail, ExternalLink } from 'lucide-react';
import { SponsoredVendor, AdEventType, recordAdEvent } from '@/services/advertisingApi';
import { VendorProfile } from '@/services/vendorManagementApi';

interface SponsoredVendorCardProps {
  vendor: SponsoredVendor;
  vendorProfile?: VendorProfile;
  onView?: (vendorId: string) => void;
  onRecordEvent: (eventType: AdEventType, sponsoredVendorId: string, vendorProfileId: string) => void;
}

export function SponsoredVendorCard({
  vendor,
  vendorProfile,
  onView,
  onRecordEvent,
}: SponsoredVendorCardProps) {
  const [hasRecordedImpression, setHasRecordedImpression] = useState(false);

  // Record impression on mount
  useEffect(() => {
    if (!hasRecordedImpression) {
      onRecordEvent('impression', vendor._id, vendor.vendor_profile_id);
      setHasRecordedImpression(true);
    }
  }, [vendor._id, vendor.vendor_profile_id, hasRecordedImpression, onRecordEvent]);

  const handleContactClick = () => {
    onRecordEvent('click', vendor._id, vendor.vendor_profile_id);
    if (vendorProfile?.website) {
      window.open(vendorProfile.website, '_blank');
    } else if (vendorProfile?.email) {
      window.location.href = `mailto:${vendorProfile.email}`;
    }
  };

  const handleViewDetails = () => {
    onRecordEvent('detail_view', vendor._id, vendor.vendor_profile_id);
    if (onView) {
      onView(vendor.vendor_profile_id);
    }
  };

  const priceRange =
    vendorProfile?.typical_price_min && vendorProfile?.typical_price_max
      ? `${vendorProfile.currency} ${Math.round(vendorProfile.typical_price_min).toLocaleString()}-${Math.round(vendorProfile.typical_price_max).toLocaleString()}`
      : null;

  return (
    <div className="relative flex-shrink-0 w-80 rounded-lg border border-gray-200 bg-white shadow-sm hover:shadow-md transition-shadow overflow-hidden">
      {/* Gradient Border Top */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-wedding-sage via-wedding-gold to-wedding-rose opacity-60" />

      {/* Sponsored Badge */}
      <div className="absolute top-3 right-3 z-10">
        <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-wedding-sage bg-wedding-sage/10 rounded-full">
          Sponsored
        </span>
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
        <div className="flex gap-2 pt-3 border-t border-gray-100">
          <button
            onClick={handleViewDetails}
            className="flex-1 px-3 py-2 text-sm font-medium text-wedding-navy hover:bg-wedding-ivory rounded-md transition-colors"
          >
            View Details
          </button>
          <button
            onClick={handleContactClick}
            className="flex-1 px-3 py-2 text-sm font-medium text-white bg-wedding-sage hover:bg-wedding-sage/90 rounded-md transition-colors"
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
