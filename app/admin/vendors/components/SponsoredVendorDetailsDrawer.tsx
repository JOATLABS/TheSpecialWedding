'use client';

import React, { useEffect } from 'react';
import { X, Phone, Mail, Globe, MapPin, Star, ExternalLink } from 'lucide-react';
import { SponsoredVendor, recordAdEvent, type AdEventType } from '@/services/advertisingApi';
import { VendorProfile } from '@/services/vendorManagementApi';
import { useAdmin } from '@/contexts/AdminContext';

interface SponsoredVendorDetailsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  sponsoredVendor: SponsoredVendor | null;
  vendorProfile?: VendorProfile;
  onContactClick?: (vendorProfileId: string) => void;
}

export function SponsoredVendorDetailsDrawer({
  isOpen,
  onClose,
  sponsoredVendor,
  vendorProfile,
  onContactClick,
}: SponsoredVendorDetailsDrawerProps) {
  const { token } = useAdmin();

  // Record detail_view event on open
  useEffect(() => {
    if (isOpen && sponsoredVendor && token) {
      recordAdEvent(token, {
        sponsored_vendor_id: sponsoredVendor._id,
        vendor_profile_id: sponsoredVendor.vendor_profile_id,
        event_type: 'detail_view',
        placement: sponsoredVendor.placement,
      }).catch((err) => console.error('Failed to record detail_view event:', err));
    }
  }, [isOpen, sponsoredVendor, token]);

  const handleContactClick = async () => {
    if (!sponsoredVendor || !token) return;

    // Record contact_click event
    await recordAdEvent(token, {
      sponsored_vendor_id: sponsoredVendor._id,
      vendor_profile_id: sponsoredVendor.vendor_profile_id,
      event_type: 'contact_click',
      placement: sponsoredVendor.placement,
    }).catch((err) => console.error('Failed to record contact_click event:', err));

    if (onContactClick) {
      onContactClick(sponsoredVendor.vendor_profile_id);
    }

    // Navigate to contact
    if (vendorProfile?.website) {
      window.open(vendorProfile.website, '_blank');
    } else if (vendorProfile?.email) {
      window.location.href = `mailto:${vendorProfile.email}`;
    }
  };

  const handleDismiss = async () => {
    if (sponsoredVendor && token) {
      await recordAdEvent(token, {
        sponsored_vendor_id: sponsoredVendor._id,
        vendor_profile_id: sponsoredVendor.vendor_profile_id,
        event_type: 'dismiss',
        placement: sponsoredVendor.placement,
      }).catch((err) => console.error('Failed to record dismiss event:', err));
    }
    onClose();
  };

  if (!isOpen || !sponsoredVendor || !vendorProfile) {
    return null;
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 bg-black/30 transition-opacity z-40 ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={handleDismiss}
      />

      {/* Drawer */}
      <div
        className={`fixed right-0 top-0 h-full w-full max-w-md bg-white shadow-xl z-50 transform transition-transform duration-300 overflow-y-auto ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 p-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-wedding-navy">Vendor Details</h2>
            <span className="text-xs text-wedding-sage font-medium">Sponsored</span>
          </div>
          <button
            onClick={handleDismiss}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            aria-label="Close drawer"
          >
            <X size={20} className="text-gray-600" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Photo Placeholder */}
          <div className="w-full h-48 bg-gradient-to-br from-wedding-sage/20 to-wedding-gold/20 rounded-lg flex items-center justify-center">
            <div className="text-center">
              <div className="text-4xl font-wedding text-wedding-sage/40 mb-2">
                {vendorProfile.business_name.charAt(0)}
              </div>
              <p className="text-sm text-gray-400">Photo unavailable</p>
            </div>
          </div>

          {/* Business Name & Category */}
          <div>
            <h3 className="text-2xl font-semibold text-wedding-navy mb-2">
              {vendorProfile.business_name}
            </h3>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-3 py-1 bg-wedding-ivory text-wedding-navy text-sm font-medium rounded-full">
                {vendorProfile.service_category.replace(/_/g, ' ').toLowerCase()}
              </span>
              {vendorProfile.is_preferred && (
                <span className="px-3 py-1 bg-wedding-gold/20 text-wedding-navy text-sm font-medium rounded-full flex items-center gap-1">
                  <Star size={14} className="fill-wedding-gold text-wedding-gold" />
                  Preferred
                </span>
              )}
            </div>
          </div>

          {/* Sponsored Headline & Description */}
          {sponsoredVendor.headline && (
            <div>
              <h4 className="font-semibold text-wedding-navy mb-1">Featured Offer</h4>
              <p className="text-sm font-medium text-wedding-sage">{sponsoredVendor.headline}</p>
            </div>
          )}

          {sponsoredVendor.description && (
            <div>
              <p className="text-sm text-gray-700">{sponsoredVendor.description}</p>
            </div>
          )}

          {/* Service Description */}
          {vendorProfile.service_description && (
            <div>
              <h4 className="font-semibold text-wedding-navy mb-2">About</h4>
              <p className="text-sm text-gray-700 leading-relaxed">
                {vendorProfile.service_description}
              </p>
            </div>
          )}

          {/* Pricing */}
          {(vendorProfile.typical_price_min || vendorProfile.typical_price_max) && (
            <div className="p-3 bg-wedding-ivory rounded-lg">
              <p className="text-sm text-gray-600">Typical Price Range</p>
              <p className="text-lg font-semibold text-wedding-navy">
                {vendorProfile.currency}{' '}
                {vendorProfile.typical_price_min
                  ? Math.round(vendorProfile.typical_price_min).toLocaleString()
                  : '—'}
                {vendorProfile.typical_price_max ? ' - ' : ''}
                {vendorProfile.typical_price_max
                  ? Math.round(vendorProfile.typical_price_max).toLocaleString()
                  : ''}
              </p>
            </div>
          )}

          {/* Contact Information */}
          <div className="space-y-2 pt-2 border-t border-gray-200">
            <h4 className="font-semibold text-wedding-navy mb-3">Contact Information</h4>

            {vendorProfile.phone && (
              <a
                href={`tel:${vendorProfile.phone}`}
                className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded-lg transition-colors"
              >
                <Phone size={18} className="text-wedding-sage flex-shrink-0" />
                <div className="flex-1">
                  <p className="text-xs text-gray-500">Phone</p>
                  <p className="text-sm font-medium text-wedding-navy">{vendorProfile.phone}</p>
                </div>
              </a>
            )}

            {vendorProfile.email && (
              <a
                href={`mailto:${vendorProfile.email}`}
                className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded-lg transition-colors"
              >
                <Mail size={18} className="text-wedding-sage flex-shrink-0" />
                <div className="flex-1">
                  <p className="text-xs text-gray-500">Email</p>
                  <p className="text-sm font-medium text-wedding-navy line-clamp-1">
                    {vendorProfile.email}
                  </p>
                </div>
              </a>
            )}

            {vendorProfile.website && (
              <a
                href={vendorProfile.website}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded-lg transition-colors"
              >
                <Globe size={18} className="text-wedding-sage flex-shrink-0" />
                <div className="flex-1">
                  <p className="text-xs text-gray-500">Website</p>
                  <p className="text-sm font-medium text-wedding-navy line-clamp-1">
                    {vendorProfile.website.replace(/^https?:\/\/(www\.)?/, '')}
                  </p>
                </div>
              </a>
            )}

            {vendorProfile.city && (
              <div className="flex items-center gap-3 p-2">
                <MapPin size={18} className="text-wedding-sage flex-shrink-0" />
                <div className="flex-1">
                  <p className="text-xs text-gray-500">Location</p>
                  <p className="text-sm font-medium text-wedding-navy">
                    {vendorProfile.city}
                    {vendorProfile.state ? `, ${vendorProfile.state}` : ''}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Portfolio Links */}
          {vendorProfile.portfolio_urls && vendorProfile.portfolio_urls.length > 0 && (
            <div className="pt-2 border-t border-gray-200">
              <h4 className="font-semibold text-wedding-navy mb-3">Portfolio</h4>
              <div className="space-y-2">
                {vendorProfile.portfolio_urls.map((url, index) => (
                  <a
                    key={index}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-sm text-wedding-sage hover:text-wedding-sage/80 transition-colors"
                  >
                    <ExternalLink size={14} />
                    <span className="truncate">{url.replace(/^https?:\/\/(www\.)?/, '')}</span>
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Tags */}
          {vendorProfile.tags && vendorProfile.tags.length > 0 && (
            <div className="pt-2 border-t border-gray-200">
              <h4 className="font-semibold text-wedding-navy mb-3">Specialties</h4>
              <div className="flex flex-wrap gap-2">
                {vendorProfile.tags.map((tag, index) => (
                  <span
                    key={index}
                    className="text-xs px-2.5 py-1 bg-gray-100 text-gray-700 rounded-full"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Rating */}
          {vendorProfile.internal_rating && (
            <div className="pt-2 border-t border-gray-200">
              <div className="flex items-center gap-3">
                <div className="flex gap-1">
                  {[...Array(5)].map((_, i) => (
                    <Star
                      key={i}
                      size={14}
                      className={
                        i < Math.round(vendorProfile.internal_rating || 0)
                          ? 'fill-wedding-gold text-wedding-gold'
                          : 'text-gray-300'
                      }
                    />
                  ))}
                </div>
                <span className="text-sm text-gray-600">
                  {vendorProfile.internal_rating.toFixed(1)} / 5.0
                </span>
              </div>
            </div>
          )}

          {/* Stats */}
          {(vendorProfile.weddings_count > 0 || vendorProfile.total_revenue > 0) && (
            <div className="grid grid-cols-2 gap-3 p-3 bg-gray-50 rounded-lg">
              {vendorProfile.weddings_count > 0 && (
                <div>
                  <p className="text-xs text-gray-500">Weddings</p>
                  <p className="text-lg font-semibold text-wedding-navy">
                    {vendorProfile.weddings_count}
                  </p>
                </div>
              )}
              {vendorProfile.total_revenue > 0 && (
                <div>
                  <p className="text-xs text-gray-500">Total Revenue</p>
                  <p className="text-lg font-semibold text-wedding-navy">
                    ${Math.round(vendorProfile.total_revenue).toLocaleString()}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer - Contact Button */}
        <div className="sticky bottom-0 bg-white border-t border-gray-200 p-4 space-y-2">
          <button
            onClick={handleContactClick}
            className="w-full px-4 py-3 bg-wedding-sage hover:bg-wedding-sage/90 text-white font-semibold rounded-lg transition-colors"
          >
            Contact Vendor
          </button>
          <button
            onClick={handleDismiss}
            className="w-full px-4 py-2 text-wedding-navy hover:bg-gray-100 font-medium rounded-lg transition-colors"
          >
            Dismiss
          </button>
        </div>
      </div>
    </>
  );
}
