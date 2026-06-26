// components/AlreadyRSVPedScreen.tsx

'use client';

import { useContext } from 'react';
import { WeddingContext } from '@/contexts/WeddingContext';

interface PlusOneInfo {
  name: string;
  attending?: string[];
  dietary?: string;
}

interface AlreadyRSVPedScreenProps {
  guest: { name: string };
  rsvp: {
    submitted_at: string;
    attending: string[];
    dietary?: string;
    plus_ones?: PlusOneInfo[];
  };
  onEditClick: () => void;
  onViewWeddingPage?: () => void;
}

const eventLabels: Record<string, string> = {
  traditional: 'Traditional Ceremony',
  white_wedding: 'White Wedding',
  reception: 'Reception',
  engagement: 'Engagement Party',
  rehearsal: 'Rehearsal Dinner',
};

/* ─── color helper ─── */
function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const h = hex.replace('#', '');
  const num = parseInt(h, 16);
  return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
}

export default function AlreadyRSVPedScreen({ guest, rsvp, onEditClick, onViewWeddingPage }: AlreadyRSVPedScreenProps) {
  // Safely read theme from context (null-safe — won't throw if context missing)
  const wedding = useContext(WeddingContext);
  const tc = wedding?.theme_config;
  const accent = tc?.accent_color || '#D4A5A5';      // fallback = wedding-rose
  const secondary = tc?.secondary_color || '#E9C46A'; // fallback = wedding-gold
  const aRgb = hexToRgb(accent);
  const sRgb = hexToRgb(secondary);
  const accentRgba = (opacity: number) => `rgba(${aRgb.r}, ${aRgb.g}, ${aRgb.b}, ${opacity})`;

  /** Reusable accent button style */
  const accentBtnStyle: React.CSSProperties = {
    backgroundColor: accent,
    color: '#0f172a',
    boxShadow: `0 10px 15px -3px ${accentRgba(0.4)}`,
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
    } catch {
      return 'Unknown date';
    }
  };

  const isDeclined = !rsvp.attending || rsvp.attending.length === 0;
  const attendanceLabel = isDeclined ? 'Not attending' : 'Attending';
  const attendingLabels = isDeclined
    ? 'Not attending'
    : rsvp.attending?.map(e => eventLabels[e] || e).join(', ') || 'Attending, no specific events selected';

  return (
    <div className="space-y-6">
      {/* Main Card */}
      <div className="rounded-2xl border border-white/10 bg-white/[0.04] overflow-hidden">
        {/* Gradient accent bar — uses couple's theme colors */}
        <div
          className="h-1"
          style={{
            background: `linear-gradient(to right, ${accent}, ${secondary}, ${accent})`,
          }}
        />

        <div className="p-8 sm:p-10 text-center">
          {/* Success icon */}
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-5"
            style={{ backgroundColor: accentRgba(0.2) }}
          >
            <svg className="w-8 h-8" style={{ color: accent }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>

          {/* Header */}
          <div className="inline-flex items-center gap-2 border-b border-white/20 px-2 pb-2 text-xs uppercase tracking-[0.22em] mb-4">
            RSVP Received
          </div>

          <h2 className="text-3xl font-semibold text-white mb-3">
            You've Already RSVPed, {guest.name}
          </h2>
          <p className="text-slate-300">
            Submitted on {formatDate(rsvp.submitted_at)}
          </p>
        </div>
      </div>

      {/* RSVP Details Card */}
      <div className="rounded-xl border border-white/10 bg-white/[0.035] p-5">
        <h3
          className="text-xs font-semibold uppercase tracking-[0.3em] mb-4"
          style={{ color: accent }}
        >
          Your RSVP Details
        </h3>

        <div className="space-y-4">
          <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
            <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Attendance</p>
            <p className="text-white font-medium">{attendanceLabel}</p>
          </div>

          <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
            <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Events</p>
            <p className="text-white font-medium">{attendingLabels}</p>
          </div>

          {rsvp.dietary && (
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
              <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Dietary Restrictions</p>
              <p className="text-white font-medium">{rsvp.dietary}</p>
            </div>
          )}

          {rsvp.plus_ones && rsvp.plus_ones.length > 0 && (
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
              <p className="text-xs text-slate-400 uppercase tracking-wider mb-3">
                Additional Guests ({rsvp.plus_ones.length})
              </p>
              <div className="space-y-3">
                {rsvp.plus_ones.map((po, index) => (
                  <div key={index} className="p-3 rounded-lg border border-white/5 bg-white/[0.03]">
                    <p className="text-white font-medium">{po.name}</p>
                    {po.attending && po.attending.length > 0 && (
                      <p className="text-xs text-slate-400 mt-1">
                        Attending: {po.attending.map(e => eventLabels[e] || e).join(', ')}
                      </p>
                    )}
                    {po.dietary && (
                      <p className="text-xs text-slate-400 mt-0.5">
                        Dietary: {po.dietary}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Edit Button */}
      <button
        onClick={onEditClick}
        className="w-full py-4 font-semibold rounded-full shadow-lg hover:opacity-90 transition-all"
        style={accentBtnStyle}
      >
        Edit My RSVP
      </button>

      {/* View Event Page Button */}
      {onViewWeddingPage && (
        <button
          onClick={onViewWeddingPage}
          className="w-full py-3 border border-white/20 rounded-full text-sm text-slate-300 hover:text-white transition-all"
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = accentRgba(0.5); }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.2)'; }}
        >
          View Event Page
        </button>
      )}

      {/* Footer note */}
      <p className="text-center text-sm text-slate-500">
        Need to make changes? Click &quot;Edit My RSVP&quot; above to update your response.
      </p>
    </div>
  );
}
