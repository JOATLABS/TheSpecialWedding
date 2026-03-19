'use client';

import React, { useEffect, useState } from 'react';
import { X, Phone, Mail, Globe, MapPin, Star, ExternalLink, Eye, EyeOff, HelpCircle, ChevronDown, ChevronUp, Heart, MessageSquare, FileText } from 'lucide-react';
import { SponsoredVendor, recordAdEvent, type AdEventType } from '@/services/advertisingApi';
import { VendorProfile } from '@/services/vendorManagementApi';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';

interface SponsoredVendorDetailsDrawerProps {
  vendor: SponsoredVendor | null;
  isOpen: boolean;
  onClose: () => void;
  onRecordEvent: (eventType: string, sponsoredVendorId: string, vendorProfileId: string) => void;
  vendorProfile?: VendorProfile;
  weddingId?: string;
  onAddToWedding?: (vendorProfileId: string) => void;
  onRequestQuote?: (vendorProfileId: string) => void;
  onMessage?: (vendorProfileId: string) => void;
  onHideVendor?: (vendorProfileId: string) => void;
  onContactClick?: (vendorProfileId: string) => void;
}

export function SponsoredVendorDetailsDrawer({
  vendor,
  isOpen,
  onClose,
  onRecordEvent,
  vendorProfile,
  weddingId,
  onAddToWedding,
  onRequestQuote,
  onMessage,
  onHideVendor,
  onContactClick,
}: SponsoredVendorDetailsDrawerProps) {
  const { token } = useAdmin();
  // Using sonner toast
  const [expandWhySection, setExpandWhySection] = useState(false);

  // Record detail_view event on open
  useEffect(() => {
    if (isOpen && vendor && token) {
      recordAdEvent(token, {
        sponsored_vendor_id: vendor._id,
        vendor_profile_id: vendor.vendor_profile_id,
        event_type: 'vendor_profile_view',
        placement: vendor.placement,
        wedding_id: weddingId,
      }).catch((err) => console.error('Failed to record detail_view event:', err));
    }
  }, [isOpen, vendor, token]);

  const handleAddToWedding = async () => {
    if (!vendor || !token) return;

    // Record assignment event
    await recordAdEvent(token, {
      sponsored_vendor_id: vendor._id,
      vendor_profile_id: vendor.vendor_profile_id,
      event_type: 'vendor_added_to_wedding',
      placement: vendor.placement,
      wedding_id: weddingId,
    }).catch((err) => console.error('Failed to record assignment event:', err));

    if (onAddToWedding) {
      onAddToWedding(vendor.vendor_profile_id);
    }

    toast.success('Vendor added to your wedding!');
  };

  const handleRequestQuote = async () => {
    if (!vendor || !token) return;

    // Record contact_click event
    await recordAdEvent(token, {
      sponsored_vendor_id: vendor._id,
      vendor_profile_id: vendor.vendor_profile_id,
      event_type: 'contact_click',
      placement: vendor.placement,
      wedding_id: weddingId,
    }).catch((err) => console.error('Failed to record contact_click event:', err));

    if (onRequestQuote) {
      onRequestQuote(vendor.vendor_profile_id);
    }
  };

  const handleMessage = async () => {
    if (!vendor || !token) return;

    // Record contact_click event
    await recordAdEvent(token, {
      sponsored_vendor_id: vendor._id,
      vendor_profile_id: vendor.vendor_profile_id,
      event_type: 'contact_click',
      placement: vendor.placement,
      wedding_id: weddingId,
    }).catch((err) => console.error('Failed to record contact_click event:', err));

    if (onMessage) {
      onMessage(vendor.vendor_profile_id);
    }
  };

  const handleHideVendor = async () => {
    if (!vendor || !token) return;

    // Record dismiss event
    await recordAdEvent(token, {
      sponsored_vendor_id: vendor._id,
      vendor_profile_id: vendor.vendor_profile_id,
      event_type: 'dismiss',
      placement: vendor.placement,
      wedding_id: weddingId,
    }).catch((err) => console.error('Failed to record dismiss event:', err));

    if (onHideVendor) {
      onHideVendor(vendor.vendor_profile_id);
    }

    onClose();
  };

  const handleClose = async () => {
    onClose();
  };

  if (!isOpen || !vendor || !vendorProfile) {
    return null;
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 bg-black/30 transition-opacity z-40 ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={handleClose}
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
            onClick={handleClose}
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
          {vendor.headline && (
            <div>
              <h4 className="font-semibold text-wedding-navy mb-1">Featured Offer</h4>
              <p className="text-sm font-medium text-wedding-sage">{vendor.headline}</p>
            </div>
          )}

          {vendor.description && (
            <div>
              <p className="text-sm text-gray-700">{vendor.description}</p>
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

          {/* Why am I seeing this? Section */}
          <div className="pt-2 border-t border-gray-200">
            <button
              onClick={() => setExpandWhySection(!expandWhySection)}
              className="w-full flex items-center justify-between py-2 text-sm text-wedding-navy hover:text-wedding-navy/80 transition-colors"
            >
              <div className="flex items-center gap-2">
                <HelpCircle size={16} className="text-wedding-sage" />
                <span className="font-medium">Why am I seeing this?</span>
              </div>
              {expandWhySection ? (
                <ChevronUp size={16} className="text-gray-400" />
              ) : (
                <ChevronDown size={16} className="text-gray-400" />
              )}
            </button>
            {expandWhySection && (
              <p className="text-xs text-gray-600 mt-2 leading-relaxed">
                This vendor is sponsored and matches your wedding category and location.
              </p>
            )}
          </div>

          {/* Hide this vendor */}
          <div className="flex justify-end pt-2">
            <button
              onClick={handleHideVendor}
              className="text-xs text-gray-500 hover:text-gray-700 transition-colors underline"
            >
              Hide this vendor
            </button>
          </div>

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
          {(vendorProfile.weddings_count > 0 || vendorProfile.internal_rating || vendorProfile.typical_price_min) && (
            <div className="grid grid-cols-3 gap-3 p-3 bg-gray-50 rounded-lg">
              {vendorProfile.weddings_count > 0 && (
                <div>
                  <p className="text-xs text-gray-500">Weddings</p>
                  <p className="text-lg font-semibold text-wedding-navy">
                    {vendorProfile.weddings_count}
                  </p>
                </div>
              )}
              {vendorProfile.internal_rating && (
                <div>
                  <p className="text-xs text-gray-500">Rating</p>
                  <p className="text-lg font-semibold text-wedding-navy">
                    {vendorProfile.internal_rating.toFixed(1)}
                  </p>
                </div>
              )}
              {vendorProfile.typical_price_min && (
                <div>
                  <p className="text-xs text-gray-500">Starting at</p>
                  <p className="text-lg font-semibold text-wedding-navy">
                    {vendorProfile.currency || '$'}{Math.round(vendorProfile.typical_price_min).toLocaleString()}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer - Action Buttons */}
        <div className="sticky bottom-0 bg-white border-t border-gray-200 p-4 space-y-3">
          {/* Primary CTA: Add to wedding */}
          <button
            onClick={handleAddToWedding}
            className="w-full px-4 py-3 bg-wedding-rose hover:bg-wedding-rose/90 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            <Heart size={18} />
            Add to wedding
          </button>

          {/* Secondary CTAs */}
          <div className="space-y-2">
            <button
              onClick={handleRequestQuote}
              className="w-full px-4 py-2.5 border-2 border-wedding-sage text-wedding-sage hover:bg-wedding-sage/10 font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <FileText size={16} />
              Request quote
            </button>
            <button
              onClick={handleMessage}
              className="w-full px-4 py-2.5 border-2 border-wedding-sage text-wedding-sage hover:bg-wedding-sage/10 font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <MessageSquare size={16} />
              Message vendor
            </button>
          </div>

          {/* View Portfolio Button */}
          {vendorProfile.portfolio_urls && vendorProfile.portfolio_urls.length > 0 && (
            <button
              onClick={() => {
                if (vendorProfile.portfolio_urls && vendorProfile.portfolio_urls[0]) {
                  window.open(vendorProfile.portfolio_urls[0], '_blank');
                }
              }}
              className="w-full px-4 py-2.5 border-2 border-gray-300 text-gray-700 hover:bg-gray-50 font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <Eye size={16} />
              View portfolio
            </button>
          )}
        </div>
      </div>
    </>
  );
}
