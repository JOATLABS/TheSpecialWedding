// components/RSVPForm.tsx

'use client';

import { useForm } from 'react-hook-form';
import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useWedding } from '@/hooks/useWedding';
import { formatDate } from '@/utils/dateFormat';

interface ExistingRsvpData {
  has_rsvp?: boolean;
  submitted_at?: string;
  attending?: string[];
  dietary?: string;
  plus_ones?: PlusOneData[];
}

interface RSVPFormProps {
  guest: any;
  token: string;
  existingRsvp?: ExistingRsvpData | null;
  onSuccess?: () => void;
  onViewWeddingPage?: () => void;
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

const EVENT_TYPE_LABELS: Record<string, string> = {
  traditional: 'Traditional Ceremony',
  white_wedding: 'White Wedding',
  reception: 'Reception',
  engagement: 'Engagement Party',
  rehearsal: 'Rehearsal Dinner',
};

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

export default function RSVPForm({ guest, token, existingRsvp, onSuccess, onViewWeddingPage }: RSVPFormProps) {
  const wedding = useWedding();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    defaultValues: {
      attending: existingRsvp?.attending || [],
      phone: guest.phone || '',
      dietary: existingRsvp?.dietary || '',
      sms_opt_in: !!guest.sms_opt_in,
      email_opt_in: !!guest.email_opt_in,
    },
  });
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initialize plus-ones from existing RSVP data if editing
  const initialPlusOnes: PlusOneData[] = existingRsvp?.plus_ones
    ? existingRsvp.plus_ones.map((po: any) => ({
        name: po.name || '',
        phone: po.phone || '',
        email: po.email || '',
        attending: po.attending || [],
        dietary: po.dietary || '',
        sms_opt_in: !!po.sms_opt_in,
        email_opt_in: !!po.email_opt_in,
      }))
    : [];
  const [plusOnes, setPlusOnes] = useState<PlusOneData[]>(initialPlusOnes);

  // Build dynamic event list from wedding data
  const eventOptions = wedding.events && wedding.events.length > 0
    ? wedding.events.map((e: any) => ({
        value: e.type,
        label: EVENT_TYPE_LABELS[e.type] || e.type.replace('_', ' '),
        date: e.date,
        time: e.details?.time,
        venue: e.details?.venue_name,
      }))
    : [
        { value: 'traditional', label: 'Traditional Ceremony' },
        { value: 'white_wedding', label: 'White Wedding' },
        { value: 'reception', label: 'Reception' },
      ];

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

      // Get wedding timezone (default to America/Chicago for US Central Time)
      const weddingTimezone = (wedding as any).timezone || 'America/Chicago';

      const formatICSDate = (year: number, month: number, day: number, hour: number, min: number): string => {
        const pad = (n: number) => n.toString().padStart(2, '0');
        return `${year}${pad(month)}${pad(day)}T${pad(hour)}${pad(min)}00`;
      };

      const timestamp = Date.now();
      const vevents = events.map((event, index) => {
        const eventDate = event.date || wedding.date;
        if (!eventDate) return '';

        const startTimeStr = event.details?.time || '12:00';
        const startTime = parseTimeToISO(startTimeStr);
        const [year, month, day] = eventDate.split('-').map(Number);
        const [startHour, startMin] = startTime.split(':').map(Number);

        // Calculate end time (3 hours after start), handling midnight rollover
        let endHour = startHour + 3;
        let endDay = day;
        let endMonth = month;
        let endYear = year;
        if (endHour >= 24) {
          endHour -= 24;
          // Roll forward one day (simplified: assumes no month-end edge case
          // will cause issues for a 3-hour offset in calendar display)
          endDay += 1;
        }

        // Get event-specific timezone or fall back to wedding timezone
        const eventTimezone = event.details?.timezone || weddingTimezone;

        const eventLabel = EVENT_TYPE_LABELS[event.type] || event.type.replace('_', ' ');
        const summary = `${eventLabel} - ${wedding.couple_names || 'Wedding'}`;
        const location = event.details?.venue_name || event.details?.location || 'Wedding Venue';
        const attire = event.details?.attire ? `Attire: ${event.details.attire}` : '';
        const description = attire
          ? `You are cordially invited! ${attire}`
          : 'You are cordially invited to celebrate with us!';

        return [
          'BEGIN:VEVENT',
          `DTSTART;TZID=${eventTimezone}:${formatICSDate(year, month, day, startHour, startMin)}`,
          `DTEND;TZID=${eventTimezone}:${formatICSDate(endYear, endMonth, endDay, endHour, startMin)}`,
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
        `X-WR-TIMEZONE:${weddingTimezone}`,
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
    setError(null);

    // Validate plus-one fields before submitting
    const phonePattern = /^\+?\d{10,15}$/;
    for (let i = 0; i < plusOnes.length; i++) {
      const p = plusOnes[i];
      const guestLabel = `Guest ${i + 1}`;
      if (!p.name.trim()) {
        setError(`${guestLabel}: Please enter a name, or remove empty guest cards.`);
        return;
      }
      if (p.name.trim().length < 2) {
        setError(`${guestLabel}: Name must be at least 2 characters.`);
        return;
      }
      if (p.name.trim().length > 100) {
        setError(`${guestLabel}: Name must be 100 characters or fewer.`);
        return;
      }
      if (p.phone && p.phone.trim() && !phonePattern.test(p.phone.trim())) {
        setError(`${guestLabel}: Phone number must be 10-15 digits, optionally starting with +.`);
        return;
      }
    }

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const apiUrl = baseUrl.replace('/admin', '');

      const filledPlusOnes = plusOnes
        .filter(p => p.name.trim())
        .map(p => ({ ...p, attending: data.attending || [] }));

      const submissionData = {
        ...data,
        attending: data.attending || [],
        sms_opt_in: !!data.sms_opt_in,
        email_opt_in: !!data.email_opt_in,
        plus_ones: filledPlusOnes,
      };

      const res = await fetch(`${apiUrl}/rsvp/invite/${token}/rsvp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(submissionData)
      });

      if (!res.ok) {
        let errorMessage = 'Failed to submit RSVP. Please check all required fields and try again.';
        try {
          const errorData = await res.json();
          if (errorData.detail) {
            if (typeof errorData.detail === 'string') {
              errorMessage = errorData.detail;
            } else if (Array.isArray(errorData.detail)) {
              // Pydantic validation errors come as array of objects with loc, msg, type
              const fieldLabels: Record<string, string> = {
                phone: 'Phone number',
                attending: 'Events',
                dietary: 'Dietary restrictions',
                name: 'Name',
                email: 'Email',
                plus_ones: 'Additional guests',
              };
              errorMessage = errorData.detail
                .map((err: any) => {
                  const field = err.loc?.slice(-1)[0] || 'Unknown field';
                  const label = fieldLabels[field] || field;
                  return `${label}: ${err.msg}`;
                })
                .join('. ');
            }
          }
        } catch {
          // JSON parse failed, use default message
        }
        throw new Error(errorMessage);
      }

      localStorage.setItem(`rsvp-${token}`, 'true');
      setSubmitted(true);
      generateICS();
      onSuccess?.();
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
        <p className="text-sm text-slate-400 mb-6">A calendar invite has been downloaded.</p>

        <div className="mt-8 pt-6 border-t border-white/10 space-y-4">
          <p className="text-sm text-slate-300">We look forward to celebrating with you.</p>

          {onViewWeddingPage && (
            <button
              type="button"
              onClick={onViewWeddingPage}
              className="w-full py-4 bg-wedding-rose text-slate-900 font-semibold rounded-full shadow-lg shadow-wedding-rose/40 hover:bg-wedding-blush transition-all"
            >
              View {wedding.couple_names ? `${wedding.couple_names}'s` : 'Wedding'} Page
            </button>
          )}

          <button
            type="button"
            onClick={generateICS}
            className="w-full py-3 border border-white/20 rounded-full text-sm text-slate-300 hover:border-wedding-rose/50 hover:text-white transition-all"
          >
            Download Calendar Invite Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center pb-6 border-b border-white/10">
        <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-5 py-1.5 text-xs uppercase tracking-[0.3em] backdrop-blur mb-4">
          You&apos;re Invited
        </div>
        <h1 className="text-3xl font-semibold text-white mb-2">Welcome, {guest.name}</h1>
        <p className="text-slate-200 mb-4">
          Please RSVP for <span className="font-semibold text-wedding-rose">{wedding.couple_names}&apos;s</span> wedding
        </p>
        <p className="text-sm text-slate-400">
          Fields marked with <span className="text-wedding-rose font-bold">*</span> are required.
          Please select the events you will attend and provide your contact details.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Events */}
        <FormCard title="Events">
          <p className="text-sm text-slate-400 mb-4">
            Select the events you plan to attend. If you cannot attend any events, you may leave all unchecked.
          </p>
          <div className="space-y-3">
            {eventOptions.map((event: any) => (
              <label key={event.value} className="flex items-start p-4 rounded-2xl border border-white/10 bg-white/5 hover:border-wedding-rose/40 hover:bg-wedding-rose/10 cursor-pointer transition-all">
                <input
                  type="checkbox"
                  value={event.value}
                  {...register('attending')}
                  className="mt-0.5 w-4 h-4 rounded border-white/30 bg-white/10 text-wedding-rose focus:ring-wedding-rose focus:ring-offset-0"
                />
                <div className="ml-3">
                  <span className="text-slate-200 block">{event.label}</span>
                  {event.date && (
                    <span className="text-xs text-slate-500 block mt-0.5">
                      {formatDate(event.date, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
                      {event.time && ` at ${event.time}`}
                      {event.venue && ` \u2022 ${event.venue}`}
                    </span>
                  )}
                </div>
              </label>
            ))}
          </div>
        </FormCard>

        {/* Your Details */}
        <FormCard title="Your Details">
          <div className="space-y-5">
            <div>
              <label htmlFor="phone-input" className="block text-sm text-slate-200 mb-2">
                Phone Number <span className="text-wedding-rose font-bold">*</span>
              </label>
              <input
                id="phone-input"
                type="tel"
                {...register('phone', { required: 'Phone number is required', pattern: { value: /^\+?\d{10,15}$/, message: 'Enter 10-15 digits, optionally starting with +' } })}
                placeholder="+15551234567"
                aria-invalid={errors.phone ? "true" : "false"}
                aria-describedby={errors.phone ? "phone-error" : "phone-hint"}
                className={`w-full px-4 py-3 rounded-xl border ${errors.phone ? 'border-wedding-rose/50 bg-wedding-rose/5' : 'border-white/10 bg-white/5'} text-white placeholder-slate-500 focus:ring-1 focus:ring-wedding-rose focus:border-wedding-rose/50 transition-all backdrop-blur`}
              />
              <p id="phone-hint" className="text-xs text-slate-500 mt-1">Enter digits only (10-15 digits). Example: +15551234567</p>
              {errors.phone && <p id="phone-error" className="text-wedding-rose text-xs mt-1">{(errors.phone as any).message || 'Please enter a valid phone number'}</p>}
            </div>
            <div>
              <label className="block text-sm text-slate-200 mb-2">Dietary Restrictions</label>
              <input
                type="text"
                {...register('dietary')}
                placeholder="e.g., Vegetarian, Gluten-free"
                className="w-full px-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white placeholder-slate-500 focus:ring-1 focus:ring-wedding-rose focus:border-wedding-rose/50 transition-all backdrop-blur"
              />
              <p className="text-xs text-slate-500 mt-1">Optional. Leave blank if you have no dietary restrictions.</p>
            </div>
          </div>
        </FormCard>

        {/* Notifications */}
        <FormCard title="Notifications">
          <p className="text-sm text-slate-400 mb-4">
            Optional. Choose how you&apos;d like to receive wedding updates and reminders.
          </p>
          <div className="space-y-4">
            <div className="p-4 rounded-2xl border border-white/10 bg-white/5">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  {...register('sms_opt_in')}
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
              Click &quot;+ Add Guest&quot; below to add your guests. A name is required for each guest you add.
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
                      aria-label={`Remove guest ${index + 1}`}
                    >
                      Remove
                    </button>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label htmlFor={`plus-one-name-${index}`} className="sr-only">Guest {index + 1} Name</label>
                      <input
                        id={`plus-one-name-${index}`}
                        className={`w-full px-4 py-3 rounded-xl border ${!plusOne.name.trim() && error?.includes('Guest') ? 'border-wedding-rose/50 bg-wedding-rose/5' : 'border-white/10 bg-white/5'} text-white placeholder-slate-500 focus:ring-1 focus:ring-wedding-rose focus:border-wedding-rose/50 backdrop-blur`}
                        type="text"
                        placeholder="Full name (required)"
                        maxLength={100}
                        value={plusOne.name}
                        onChange={(e) => { const n = [...plusOnes]; n[index].name = e.target.value; setPlusOnes(n); }}
                      />
                      <p className="text-xs text-slate-500 mt-1">Required. Enter your guest&apos;s full name (at least 2 characters).</p>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label htmlFor={`plus-one-phone-${index}`} className="sr-only">Guest {index + 1} Phone (optional)</label>
                        <input
                          id={`plus-one-phone-${index}`}
                          className="w-full px-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white placeholder-slate-500 focus:ring-1 focus:ring-wedding-rose focus:border-wedding-rose/50 text-sm backdrop-blur"
                          type="tel"
                          placeholder="Phone (optional)"
                          value={plusOne.phone}
                          onChange={(e) => { const n = [...plusOnes]; n[index].phone = e.target.value; setPlusOnes(n); }}
                        />
                      </div>
                      <div>
                        <label htmlFor={`plus-one-email-${index}`} className="sr-only">Guest {index + 1} Email (optional)</label>
                        <input
                          id={`plus-one-email-${index}`}
                          className="w-full px-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white placeholder-slate-500 focus:ring-1 focus:ring-wedding-rose focus:border-wedding-rose/50 text-sm backdrop-blur"
                          type="email"
                          placeholder="Email (optional)"
                          value={plusOne.email || ''}
                          onChange={(e) => { const n = [...plusOnes]; n[index].email = e.target.value; setPlusOnes(n); }}
                        />
                      </div>
                    </div>
                    <div>
                      <label htmlFor={`plus-one-dietary-${index}`} className="sr-only">Guest {index + 1} Dietary restrictions (optional)</label>
                      <input
                        id={`plus-one-dietary-${index}`}
                        className="w-full px-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white placeholder-slate-500 focus:ring-1 focus:ring-wedding-rose focus:border-wedding-rose/50 text-sm backdrop-blur"
                        type="text"
                        placeholder="Dietary restrictions (optional)"
                        value={plusOne.dietary}
                        onChange={(e) => { const n = [...plusOnes]; n[index].dietary = e.target.value; setPlusOnes(n); }}
                      />
                    </div>

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
            <div className="flex gap-3">
              <svg className="w-5 h-5 text-wedding-rose flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              <div>
                <p className="text-sm font-medium text-wedding-rose mb-1">RSVP could not be submitted</p>
                <p className="text-sm text-wedding-rose/80">{error}</p>
              </div>
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full py-4 bg-wedding-rose text-slate-900 font-semibold rounded-full shadow-lg shadow-wedding-rose/40 hover:bg-wedding-blush disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>Submitting...</span>
            </>
          ) : (
            'Confirm RSVP'
          )}
        </button>
      </form>
    </div>
  );
}
