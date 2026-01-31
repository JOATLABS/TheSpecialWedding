// components/RSVPForm.tsx

'use client';

import { useForm } from 'react-hook-form';
import { useState } from 'react';
import { useWedding } from '@/hooks/useWedding';

interface RSVPFormProps {
  guest: any;
  token: string;
}

interface PlusOneData {
  name: string;
  phone?: string;
  email?: string;
  attending?: string[];
  dietary?: string;
  sms_opt_in?: boolean;
  email_opt_in?: boolean;
}

// Glass card component matching SaaS landing page design
function FormCard({ title, children, className = '' }: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl overflow-hidden ${className}`}>
      <div className="px-6 py-4 border-b border-white/10">
        <h2 className="text-xs font-semibold text-wedding-rose uppercase tracking-[0.3em]">
          {title}
        </h2>
      </div>
      <div className="p-6">
        {children}
      </div>
    </div>
  );
}

export default function RSVPForm({ guest, token }: RSVPFormProps) {
  const wedding = useWedding();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm();
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plusOnes, setPlusOnes] = useState<PlusOneData[]>([]);

  const addPlusOne = () => {
    if (plusOnes.length < guest.number_of_plus_ones_allowed) {
      setPlusOnes([...plusOnes, { name: '', phone: '', email: '', attending: [], dietary: '', sms_opt_in: false, email_opt_in: false }]);
    }
  };

  const removePlusOne = (index: number) => {
    const newPlusOnes = [...plusOnes];
    newPlusOnes.splice(index, 1);
    setPlusOnes(newPlusOnes);
  };

  const parseTimeToISO = (timeStr: string): string => {
    if (!timeStr) return '12:00';

    // Handle 24-hour format without AM/PM (e.g., "18:00")
    if (/^\d{1,2}:\d{2}$/.test(timeStr)) {
      const [hours, minutes] = timeStr.split(':');
      return `${hours.padStart(2, '0')}:${minutes}`;
    }

    // Handle formats with colon: "6:00 PM", "6:00PM"
    const colonMatch = timeStr.match(/(\d{1,2}):(\d{2})\s*(am|pm)?/i);
    if (colonMatch) {
      let hours = parseInt(colonMatch[1], 10);
      const minutes = colonMatch[2];
      const period = colonMatch[3]?.toLowerCase();
      if (period === 'pm' && hours !== 12) hours += 12;
      if (period === 'am' && hours === 12) hours = 0;
      return `${hours.toString().padStart(2, '0')}:${minutes}`;
    }

    // Handle hour-only formats: "6PM", "6 PM", "6pm"
    const hourOnlyMatch = timeStr.match(/^(\d{1,2})\s*(am|pm)$/i);
    if (hourOnlyMatch) {
      let hours = parseInt(hourOnlyMatch[1], 10);
      const period = hourOnlyMatch[2].toLowerCase();
      if (period === 'pm' && hours !== 12) hours += 12;
      if (period === 'am' && hours === 12) hours = 0;
      return `${hours.toString().padStart(2, '0')}:00`;
    }

    return '12:00';
  };

  const generateICS = () => {
    try {
      const events = wedding.events && wedding.events.length > 0
        ? wedding.events
        : [{ type: 'white_wedding' as const, date: wedding.date, details: undefined }];

      if (!events.some(e => e.date || wedding.date)) return;

      const formatICSDate = (date: Date): string => {
        const pad = (n: number) => n.toString().padStart(2, '0');
        return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}T${pad(date.getHours())}${pad(date.getMinutes())}00`;
      };

      const eventTypeLabels: Record<string, string> = {
        traditional: 'Traditional Ceremony',
        white_wedding: 'White Wedding',
        reception: 'Reception',
        engagement: 'Engagement Party',
        rehearsal: 'Rehearsal Dinner',
      };

      const timestamp = Date.now();
      const vevents = events.map((event, index) => {
        const eventDate = event.date || wedding.date;
        if (!eventDate) return '';

        const startTimeStr = event.details?.time || '12:00';
        const startTime = parseTimeToISO(startTimeStr);
        const [year, month, day] = eventDate.split('-').map(Number);
        const [startHour, startMin] = startTime.split(':').map(Number);
        const startDate = new Date(year, month - 1, day, startHour, startMin);
        const endDate = new Date(startDate.getTime() + 3 * 60 * 60 * 1000);

        const eventLabel = eventTypeLabels[event.type] || event.type.replace('_', ' ');
        const summary = `${eventLabel} - ${wedding.couple_names || 'Wedding'}`;
        const location = event.details?.venue_name || event.details?.location || 'Wedding Venue';
        const attire = event.details?.attire ? `Attire: ${event.details.attire}` : '';
        const description = attire
          ? `You are cordially invited! ${attire}`
          : 'You are cordially invited to celebrate with us!';

        return [
          'BEGIN:VEVENT',
          `DTSTART:${formatICSDate(startDate)}`,
          `DTEND:${formatICSDate(endDate)}`,
          `SUMMARY:${summary}`,
          `LOCATION:${location}`,
          `DESCRIPTION:${description}`,
          `UID:${timestamp}-${index}@wedding-rsvp`,
          'END:VEVENT'
        ].join('\r\n');
      }).filter(Boolean);

      const ics = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Wedding RSVP//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        ...vevents,
        'END:VCALENDAR'
      ].join('\r\n');

      const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'wedding_invite.ics';
      link.style.display = 'none';
      document.body.appendChild(link);
      setTimeout(() => {
        link.click();
        setTimeout(() => { document.body.removeChild(link); URL.revokeObjectURL(url); }, 100);
      }, 0);
    } catch (err) {
      console.error('Error generating calendar invite:', err);
    }
  };

  const onSubmit = async (data: any) => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const apiUrl = baseUrl.replace('/admin', '');

      const filledPlusOnes = plusOnes
        .filter(p => p.name.trim())
        .map(p => ({ ...p, attending: data.attending || [] }));

      const res = await fetch(`${apiUrl}/rsvp/invite/${token}/rsvp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...data, wedding_id: wedding.id, plus_ones: filledPlusOnes })
      });

      if (!res.ok) throw new Error('RSVP failed');
      localStorage.setItem(`rsvp-${token}`, 'true');
      setSubmitted(true);
      generateICS();
    } catch (err: any) {
      setError(err.message);
    }
  };

  if (submitted) {
    return (
      <div className="rounded-[2.5rem] border border-white/10 bg-white/5 backdrop-blur-xl p-10 text-center">
        <div className="w-16 h-16 bg-wedding-rose/20 rounded-full flex items-center justify-center mx-auto mb-6">
          <svg className="w-8 h-8 text-wedding-rose" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h2 className="text-2xl font-semibold text-white mb-3">Thank you, {guest.name}</h2>
        <p className="text-slate-200 mb-1">Your RSVP has been received.</p>
        <p className="text-sm text-slate-400">A calendar invite has been downloaded.</p>
        <div className="mt-8 pt-6 border-t border-white/10">
          <p className="text-sm text-slate-300">We look forward to celebrating with you.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center pb-6 border-b border-white/10">
        <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-5 py-1.5 text-xs uppercase tracking-[0.3em] backdrop-blur mb-4">
          You're Invited
        </div>
        <h1 className="text-3xl font-semibold text-white mb-2">Welcome, {guest.name}</h1>
        <p className="text-slate-200">
          Please RSVP for <span className="font-semibold text-wedding-rose">{wedding.couple_names}'s</span> wedding
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Events */}
        <FormCard title="Events">
          <div className="space-y-3">
            {[
              { value: 'traditional', label: 'Traditional Ceremony' },
              { value: 'white_wedding', label: 'White Wedding' },
              { value: 'reception', label: 'Reception' },
            ].map((event) => (
              <label key={event.value} className="flex items-center p-4 rounded-2xl border border-white/10 bg-white/5 hover:border-wedding-rose/40 hover:bg-wedding-rose/10 cursor-pointer transition-all">
                <input
                  type="checkbox"
                  value={event.value}
                  {...register('attending')}
                  className="w-4 h-4 rounded border-white/30 bg-white/10 text-wedding-rose focus:ring-wedding-rose focus:ring-offset-0"
                />
                <span className="ml-3 text-slate-200">{event.label}</span>
              </label>
            ))}
          </div>
        </FormCard>

        {/* Your Details */}
        <FormCard title="Your Details">
          <div className="space-y-5">
            <div>
              <label className="block text-sm text-slate-200 mb-2">Dietary Restrictions</label>
              <input
                type="text"
                {...register('dietary')}
                placeholder="e.g., Vegetarian, Gluten-free"
                className="w-full px-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white placeholder-slate-500 focus:ring-1 focus:ring-wedding-rose focus:border-wedding-rose/50 transition-all backdrop-blur"
              />
              <p className="text-xs text-slate-500 mt-1">Leave blank if none</p>
            </div>
            <div>
              <label className="block text-sm text-slate-200 mb-2">
                Phone Number <span className="text-wedding-rose">*</span>
              </label>
              <input
                type="tel"
                defaultValue={guest.phone}
                {...register('phone', { required: true, pattern: /^\+?\d{10,15}$/ })}
                placeholder="+1 (555) 123-4567"
                className="w-full px-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white placeholder-slate-500 focus:ring-1 focus:ring-wedding-rose focus:border-wedding-rose/50 transition-all backdrop-blur"
              />
              {errors.phone && <p className="text-wedding-rose text-xs mt-1">Please enter a valid phone number</p>}
            </div>
          </div>
        </FormCard>

        {/* Notifications */}
        <FormCard title="Notifications">
          <div className="space-y-4">
            <div className="p-4 rounded-2xl border border-white/10 bg-white/5">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  {...register('sms_opt_in')}
                  defaultChecked={false}
                  className="mt-0.5 w-4 h-4 rounded border-white/30 bg-white/10 text-wedding-rose focus:ring-wedding-rose focus:ring-offset-0"
                />
                <div>
                  <span className="block text-sm font-medium text-white">SMS Reminders</span>
                  <span className="block text-xs text-slate-400 mt-0.5">Receive updates via text message</span>
                </div>
              </label>
              <p className="text-xs text-slate-500 mt-3 pl-7">
                By opting in, you consent to receive automated texts. Reply STOP to opt out. Msg rates may apply.{' '}
                <a href="#" onClick={(e) => { e.preventDefault(); window.open(`${window.location.origin}/${wedding.slug}#footer`, '_blank'); }} className="text-wedding-rose hover:underline">
                  Terms
                </a>
              </p>
            </div>

            <div className="p-4 rounded-2xl border border-white/10 bg-white/5">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  {...register('email_opt_in')}
                  defaultChecked={false}
                  className="mt-0.5 w-4 h-4 rounded border-white/30 bg-white/10 text-wedding-rose focus:ring-wedding-rose focus:ring-offset-0"
                />
                <div>
                  <span className="block text-sm font-medium text-white">Email Updates</span>
                  <span className="block text-xs text-slate-400 mt-0.5">Receive updates via email</span>
                </div>
              </label>
              <p className="text-xs text-slate-500 mt-3 pl-7">Unsubscribe anytime via email link.</p>
            </div>
          </div>
        </FormCard>

        {/* Plus Ones */}
        {guest.plus_one_allowed && guest.number_of_plus_ones_allowed > 0 && (
          <FormCard title="Additional Guests">
            <p className="text-sm text-slate-400 mb-4">
              You may bring up to {guest.number_of_plus_ones_allowed} additional {guest.number_of_plus_ones_allowed === 1 ? 'guest' : 'guests'}.
            </p>

            <div className="space-y-4">
              {plusOnes.map((plusOne, index) => (
                <div key={index} className="p-5 rounded-2xl border border-white/10 bg-white/5">
                  <div className="flex justify-between items-center mb-4">
                    <span className="text-sm font-medium text-white">Guest {index + 1}</span>
                    <button
                      type="button"
                      onClick={() => removePlusOne(index)}
                      className="text-xs text-wedding-rose hover:text-wedding-rose/80 font-medium transition-colors"
                    >
                      Remove
                    </button>
                  </div>

                  <div className="space-y-4">
                    <input
                      className="w-full px-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white placeholder-slate-500 focus:ring-1 focus:ring-wedding-rose focus:border-wedding-rose/50 backdrop-blur"
                      type="text"
                      placeholder="Full name"
                      value={plusOne.name}
                      onChange={(e) => { const n = [...plusOnes]; n[index].name = e.target.value; setPlusOnes(n); }}
                    />
                    <div className="grid grid-cols-2 gap-3">
                      <input
                        className="w-full px-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white placeholder-slate-500 focus:ring-1 focus:ring-wedding-rose focus:border-wedding-rose/50 text-sm backdrop-blur"
                        type="tel"
                        placeholder="Phone (optional)"
                        value={plusOne.phone}
                        onChange={(e) => { const n = [...plusOnes]; n[index].phone = e.target.value; setPlusOnes(n); }}
                      />
                      <input
                        className="w-full px-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white placeholder-slate-500 focus:ring-1 focus:ring-wedding-rose focus:border-wedding-rose/50 text-sm backdrop-blur"
                        type="email"
                        placeholder="Email (optional)"
                        value={plusOne.email || ''}
                        onChange={(e) => { const n = [...plusOnes]; n[index].email = e.target.value; setPlusOnes(n); }}
                      />
                    </div>
                    <input
                      className="w-full px-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white placeholder-slate-500 focus:ring-1 focus:ring-wedding-rose focus:border-wedding-rose/50 text-sm backdrop-blur"
                      type="text"
                      placeholder="Dietary restrictions (optional)"
                      value={plusOne.dietary}
                      onChange={(e) => { const n = [...plusOnes]; n[index].dietary = e.target.value; setPlusOnes(n); }}
                    />

                    <div className="flex gap-6 pt-2">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={plusOne.sms_opt_in || false}
                          onChange={(e) => { const n = [...plusOnes]; n[index].sms_opt_in = e.target.checked; setPlusOnes(n); }}
                          className="w-4 h-4 rounded border-white/30 bg-white/10 text-wedding-rose focus:ring-wedding-rose focus:ring-offset-0"
                        />
                        <span className="text-xs text-slate-300">SMS reminders</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={plusOne.email_opt_in || false}
                          onChange={(e) => { const n = [...plusOnes]; n[index].email_opt_in = e.target.checked; setPlusOnes(n); }}
                          className="w-4 h-4 rounded border-white/30 bg-white/10 text-wedding-rose focus:ring-wedding-rose focus:ring-offset-0"
                        />
                        <span className="text-xs text-slate-300">Email updates</span>
                      </label>
                    </div>
                  </div>
                </div>
              ))}

              {plusOnes.length < guest.number_of_plus_ones_allowed && (
                <button
                  type="button"
                  onClick={addPlusOne}
                  className="w-full py-3 border border-dashed border-white/20 rounded-xl text-sm text-slate-300 hover:border-wedding-rose/50 hover:text-white transition-all"
                >
                  + Add Guest
                </button>
              )}
            </div>
          </FormCard>
        )}

        {error && (
          <div className="rounded-2xl border border-wedding-rose/40 bg-wedding-rose/10 p-4 backdrop-blur">
            <p className="text-sm text-wedding-rose">{error}</p>
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full py-4 bg-wedding-rose text-slate-900 font-semibold rounded-full shadow-lg shadow-wedding-rose/40 hover:bg-wedding-blush disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          {isSubmitting ? 'Submitting...' : 'Confirm RSVP'}
        </button>
      </form>
    </div>
  );
}
