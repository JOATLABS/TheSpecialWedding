'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  getSponsoredVendors,
  recordAdEvent,
  getAdPreferences,
  hideAdVendor,
  type SponsoredVendor,
  type AdEventType,
  type AdPreferences,
} from '@/services/advertisingApi';
import { getVendorDirectory, type VendorProfile } from '@/services/vendorManagementApi';
import { useAdmin } from '@/contexts/AdminContext';
import { SponsoredVendorCard } from './SponsoredVendorCard';

interface SponsoredMilestoneModuleProps {
  /** The milestone category (e.g. "venue", "photographer") — matches vendor service_category */
  milestoneCategory: string;
  /** Whether this milestone is already booked — if true, module is suppressed */
  isBooked?: boolean;
  /** Wedding ID for attribution tracking */
  weddingId?: string;
  /** Wedding context for why-tags */
  weddingContext?: {
    city?: string;
    state?: string;
    guestCount?: number;
    budgetForCategory?: number;
  };
  onVendorClick?: (vendorProfileId: string) => void;
}

/**
 * SponsoredMilestoneModule — View 4 mockup spec.
 *
 * Contextual sponsored vendor suggestions scoped to a milestone category.
 * Appears below the planner's own shortlist on milestone pages.
 * Auto-suppressed when the milestone is marked as booked.
 * Max 2 cards per module.
 *
 * Design:
 * - "Sponsored {Category} Options" header
 * - "Hide this section" link
 * - 2-column card grid
 * - Why-tags contextual to wedding (location, guest count, budget match)
 * - Footer: "Why am I seeing this?" + "See more {category} ›"
 */
export function SponsoredMilestoneModule({
  milestoneCategory,
  isBooked = false,
  weddingId,
  weddingContext,
  onVendorClick,
}: SponsoredMilestoneModuleProps) {
  const { token } = useAdmin();
  const [vendors, setVendors] = useState<SponsoredVendor[]>([]);
  const [vendorProfiles, setVendorProfiles] = useState<Record<string, VendorProfile>>({});
  const [loading, setLoading] = useState(true);
  const [hidden, setHidden] = useState(false);
  const [showWhyTooltip, setShowWhyTooltip] = useState(false);

  // Don't render if milestone is booked or module is hidden
  const shouldShow = !isBooked && !hidden;

  useEffect(() => {
    const fetchData = async () => {
      if (!token || !shouldShow) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);

        // Fetch planner preferences
        let prefs: AdPreferences | null = null;
        try { prefs = await getAdPreferences(token); } catch { /* continue */ }

        // Fetch sponsored vendors for milestone_module placement, filtered by category
        let sponsored = await getSponsoredVendors(token, {
          placement: 'milestone_module',
          category: milestoneCategory,
          limit: 2,
        });

        // Client-side filtering
        if (prefs) {
          if (prefs.hidden_vendor_ids?.length) {
            sponsored = sponsored.filter(v => !prefs!.hidden_vendor_ids.includes(v.vendor_profile_id));
          }
          if (prefs.hidden_categories?.length) {
            sponsored = sponsored.filter(v => {
              const cats = v.target_categories || [];
              return !cats.some((c: string) => prefs!.hidden_categories.includes(c));
            });
          }
        }

        setVendors(sponsored);

        // Fetch vendor profiles
        if (sponsored.length > 0) {
          try {
            const allProfiles = await getVendorDirectory(token, { limit: 100 });
            const profileMap: Record<string, VendorProfile> = {};
            allProfiles.forEach((p) => { profileMap[p._id] = p; });
            setVendorProfiles(profileMap);
          } catch {
            // Continue without profiles
          }
        }
      } catch (err) {
        console.error('Failed to fetch milestone module vendors:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [token, milestoneCategory, shouldShow]);

  // Event handler
  const handleRecordEvent = async (
    eventType: AdEventType,
    sponsoredVendorId: string,
    vendorProfileId: string,
    metadata?: Record<string, any>
  ) => {
    if (!token) return;
    try {
      await recordAdEvent(token, {
        sponsored_vendor_id: sponsoredVendorId,
        vendor_profile_id: vendorProfileId,
        event_type: eventType,
        placement: 'milestone_module',
        wedding_id: weddingId,
        metadata,
      });
    } catch (err) {
      console.error('Failed to record milestone event:', err);
    }
  };

  // Hide handler
  const handleVendorHide = async (vendorProfileId: string) => {
    if (token) {
      try { await hideAdVendor(token, vendorProfileId); } catch { /* continue */ }
    }
    setVendors(prev => prev.filter(v => v.vendor_profile_id !== vendorProfileId));
  };

  // Generate contextual why-tag based on wedding context + vendor profile
  const getWhyTag = useCallback((vendor: SponsoredVendor): string | undefined => {
    const profile = vendorProfiles[vendor.vendor_profile_id];
    if (!profile) return undefined;

    const parts: string[] = [];
    if (weddingContext?.city && profile.city) {
      const distance = profile.service_radius ? `${profile.service_radius}mi from ${weddingContext.city}` : `Near ${weddingContext.city}`;
      parts.push(distance);
    }
    if (weddingContext?.guestCount) {
      parts.push(`Fits ${weddingContext.guestCount}+ guests`);
    }
    if (weddingContext?.budgetForCategory && profile.typical_price_min && profile.typical_price_max) {
      const budget = weddingContext.budgetForCategory;
      if (profile.typical_price_min <= budget && profile.typical_price_max >= budget * 0.5) {
        parts.push('Budget range match');
      }
    }
    return parts.length > 0 ? parts.join(' · ') : undefined;
  }, [vendorProfiles, weddingContext]);

  // Handle view click
  const handleVendorClick = (vendorProfileId: string) => {
    if (onVendorClick) {
      onVendorClick(vendorProfileId);
    } else {
      window.open(`/vendors/${vendorProfileId}`, '_blank');
    }
  };

  // Format category label for display
  const categoryLabel = milestoneCategory.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

  // Don't render conditions
  if (!shouldShow || loading || vendors.length === 0) return null;

  return (
    <section
      className="mt-6 bg-gradient-to-br from-white to-gray-50/50 border border-gray-200 rounded-xl p-4"
      role="region"
      aria-label={`Sponsored ${categoryLabel} options`}
    >
      {/* Module Header */}
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-[13px] font-bold text-wedding-navy">
          Sponsored {categoryLabel} Options
        </h4>
        <button
          onClick={() => setHidden(true)}
          className="text-[10px] text-gray-600 hover:text-red-500 transition-colors"
        >
          Hide this section
        </button>
      </div>

      {/* Cards — 2-column grid matching mockup */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {vendors.map((vendor) => (
          <SponsoredVendorCard
            key={vendor._id}
            vendor={vendor}
            vendorProfile={vendorProfiles[vendor.vendor_profile_id]}
            onView={handleVendorClick}
            onRecordEvent={handleRecordEvent}
            onHide={handleVendorHide}
            whyTag={getWhyTag(vendor)}
          />
        ))}
      </div>

      {/* Footer */}
      <div className="flex justify-between mt-3 pt-3 border-t border-gray-200">
        <button
          onClick={() => setShowWhyTooltip(!showWhyTooltip)}
          className="text-[10px] text-wedding-sage font-medium hover:underline"
          aria-expanded={showWhyTooltip}
        >
          Why am I seeing this?
        </button>
        <a
          href="/admin/vendors"
          className="text-[10px] text-wedding-sage font-medium hover:underline"
        >
          See more {categoryLabel.toLowerCase()} ›
        </a>
      </div>

      {/* Why Tooltip */}
      {showWhyTooltip && (
        <div role="tooltip" className="text-[10px] text-gray-600 bg-gray-50 px-3 py-2 mt-2 rounded-md border border-gray-200">
          These {categoryLabel.toLowerCase()} vendors are sponsored recommendations matched to your wedding location
          {weddingContext?.guestCount ? `, guest count (${weddingContext.guestCount})` : ''}
          {weddingContext?.budgetForCategory ? `, and budget ($${weddingContext.budgetForCategory.toLocaleString()})` : ''}.
          You can hide any vendor or the entire section.
        </div>
      )}
    </section>
  );
}
