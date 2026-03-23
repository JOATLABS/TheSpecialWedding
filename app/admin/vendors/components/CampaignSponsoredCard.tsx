'use client';

import React, { useState, useEffect, useRef } from 'react';
import { X, Camera, Flower2, Music, UtensilsCrossed, Building2, Video, FolderPlus } from 'lucide-react';
import {
  addToDirectory,
  type SponsoredCard,
} from '@/services/campaignAdvertisingApi';
import { useAdmin } from '@/contexts/AdminContext';

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

function generateClickId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

interface CampaignSponsoredCardProps {
  card: SponsoredCard;
  onRequestQuote: () => void;
  onHide: () => void;
  weddingId?: string;
  weddingName?: string;
}

export function CampaignSponsoredCard({
  card,
  onRequestQuote,
  onHide,
  weddingId,
  weddingName,
}: CampaignSponsoredCardProps) {
  const { token } = useAdmin();
  const cardRef = useRef<HTMLDivElement>(null);
  const [clickId] = useState(generateClickId);
  const [addedToDirectory, setAddedToDirectory] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [isHidden, setIsHidden] = useState(false);

  const handleAddToDirectory = async () => {
    if (!token) return;

    try {
      setAddError(null);
      await addToDirectory(token, {
        campaign_id: card.campaign_id,
        click_id: clickId,
      });
      setAddedToDirectory(true);
    } catch (err: any) {
      const msg = err?.message || 'Could not add vendor';
      if (msg.toLowerCase().includes('already') || msg.toLowerCase().includes('exists')) {
        setAddedToDirectory(true);
      } else {
        setAddError(msg);
      }
    }
  };

  const handleHide = () => {
    setIsHidden(true);
    onHide();
  };

  if (isHidden) return null;

  const priceInfo = card.vendor_service_area || '';

  return (
    <article
      ref={cardRef}
      role="article"
      aria-label={`Sponsored vendor: ${card.vendor_name}`}
      className="relative w-72 flex-shrink-0 lg:w-full lg:flex-shrink rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800/95 shadow-sm hover:shadow-md hover:border-wedding-sage transition-all overflow-hidden lg:mb-2.5 focus-within:ring-2 focus-within:ring-wedding-sage focus-within:ring-offset-1"
    >
      {/* Hide Button */}
      <button
        onClick={(e) => { e.stopPropagation(); handleHide(); }}
        className="absolute top-1 right-1 z-10 w-11 h-11 flex items-center justify-center rounded-full hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors text-gray-500 dark:text-gray-400 hover:text-red-500"
        aria-label={`Hide ${card.vendor_name} from sponsored vendors`}
        title="Hide this vendor"
      >
        <X size={14} />
      </button>

      {/* Card Content */}
      <div className="block p-3 space-y-2">
        {/* Sponsored Badge */}
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide rounded bg-amber-50 text-amber-700">
          Sponsored
        </span>

        {/* Vendor Image */}
        {card.image_url ? (
          <img
            src={card.image_url}
            alt={card.image_alt_text || `${card.vendor_name} image`}
            className="w-full h-20 rounded-md object-cover bg-gray-100"
            loading="lazy"
          />
        ) : card.vendor_logo_url ? (
          <img
            src={card.vendor_logo_url}
            alt={`${card.vendor_name} logo`}
            className="w-full h-20 rounded-md object-cover bg-gray-100"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-20 rounded-md bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center" aria-hidden="true">
            {getCategoryIcon(card.vendor_category)}
          </div>
        )}

        {/* Business Name & Meta */}
        <div>
          <h3 className="text-[13px] font-bold text-wedding-navy line-clamp-1">{card.vendor_name}</h3>
          <p className="text-[11px] text-gray-600 mt-0.5">
            {card.vendor_category?.replace(/_/g, ' ') || 'Service'}
            {priceInfo ? ` · ${priceInfo}` : ''}
          </p>
        </div>

        {/* Headline */}
        {card.headline && (
          <p className="text-xs font-medium text-wedding-navy line-clamp-1">{card.headline}</p>
        )}

        {/* Offer tag */}
        {card.offer && (
          <div className="text-[10px] text-wedding-sage bg-wedding-sage/5 px-2 py-1.5 rounded font-medium">
            {card.offer}
          </div>
        )}
      </div>

      {/* FTC Disclosure: Targeting reason */}
      {card.targeting_reason && (
        <p className="px-3 pb-1 text-[9px] text-gray-400 leading-tight">
          {card.targeting_reason}
        </p>
      )}

      {/* Dual CTA: Add to Directory + Request Quote */}
      <div className="flex gap-1.5 px-3 pb-3">
        <button
          onClick={handleAddToDirectory}
          disabled={addedToDirectory}
          className={`flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-[11px] font-semibold rounded-md transition-colors text-center min-h-[44px] ${
            addedToDirectory
              ? 'bg-green-100 text-green-700 cursor-default'
              : 'text-white bg-wedding-sage hover:bg-wedding-navy'
          }`}
          aria-label={addedToDirectory ? `${card.vendor_name} is in your directory` : `Add ${card.vendor_name} to directory`}
        >
          {addedToDirectory ? (
            '\u2713 In Directory'
          ) : (
            <>
              <FolderPlus size={12} />
              Add to Directory
            </>
          )}
        </button>
        <button
          onClick={onRequestQuote}
          className="flex-1 px-2 py-1.5 text-[11px] font-semibold text-wedding-sage bg-white border border-wedding-sage hover:bg-wedding-sage/5 rounded-md transition-colors text-center min-h-[44px]"
          aria-label={`Request quote from ${card.vendor_name}`}
        >
          Request Quote
        </button>
      </div>
      {addError && (
        <p className="px-3 pb-2 text-[10px] text-red-500">{addError}</p>
      )}
    </article>
  );
}
