// components/AlreadyRSVPedScreen.tsx

'use client';

interface AlreadyRSVPedScreenProps {
  guest: { name: string };
  rsvp: {
    submitted_at: string;
    attending: string[];
    dietary?: string;
  };
  onEditClick: () => void;
}

const eventLabels: Record<string, string> = {
  traditional: 'Traditional Ceremony',
  white_wedding: 'White Wedding',
  reception: 'Reception',
};

export default function AlreadyRSVPedScreen({ guest, rsvp, onEditClick }: AlreadyRSVPedScreenProps) {
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

  const attendingLabels = rsvp.attending?.map(e => eventLabels[e] || e).join(', ') || 'No events selected';

  return (
    <div className="space-y-6">
      {/* Main Card */}
      <div className="rounded-[2.5rem] border border-white/10 bg-white/5 backdrop-blur-xl overflow-hidden">
        {/* Gradient accent bar */}
        <div className="h-1 bg-gradient-to-r from-wedding-rose via-wedding-gold to-wedding-rose" />

        <div className="p-8 sm:p-10 text-center">
          {/* Success icon */}
          <div className="w-20 h-20 bg-wedding-rose/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg className="w-10 h-10 text-wedding-rose" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>

          {/* Header */}
          <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-5 py-1.5 text-xs uppercase tracking-[0.3em] backdrop-blur mb-4">
            RSVP Confirmed
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
      <div className="rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl p-6">
        <h3 className="text-xs font-semibold text-wedding-rose uppercase tracking-[0.3em] mb-4">
          Your RSVP Details
        </h3>

        <div className="space-y-4">
          <div className="p-4 rounded-2xl border border-white/10 bg-white/5">
            <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Events Attending</p>
            <p className="text-white font-medium">{attendingLabels}</p>
          </div>

          {rsvp.dietary && (
            <div className="p-4 rounded-2xl border border-white/10 bg-white/5">
              <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Dietary Restrictions</p>
              <p className="text-white font-medium">{rsvp.dietary}</p>
            </div>
          )}
        </div>
      </div>

      {/* Edit Button */}
      <button
        onClick={onEditClick}
        className="w-full py-4 bg-wedding-rose text-slate-900 font-semibold rounded-full shadow-lg shadow-wedding-rose/40 hover:bg-wedding-blush transition-all"
      >
        Edit My RSVP
      </button>

      {/* Footer note */}
      <p className="text-center text-sm text-slate-500">
        Need to make changes? Click above to update your response.
      </p>
    </div>
  );
}
