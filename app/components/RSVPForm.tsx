// components/RSVPForm.tsx

'use client';

import { useForm } from 'react-hook-form';
import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useWedding } from '@/hooks/useWedding';
import { formatDate } from '@/utils/dateFormat';
import { BUILT_IN_WEDDING_EVENT_OPTIONS, getWeddingEventLabel } from '@/utils/weddingEvents';
import { submitGuestSessionRsvp } from '@/utils/guestAccess';

interface ExistingRsvpData {
  has_rsvp?: boolean;
  submitted_at?: string;
  attending?: string[];
  dietary?: string;
  plus_ones?: PlusOneData[];
}

interface RSVPFormProps {
  guest: any;
  slug: string;
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

/* ─── color helpers ─── */
function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const h = hex.replace('#', '');
  const num = parseInt(h, 16);
  return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
}

/**
 * All theme colors come from CSS custom properties set by RSVPModal on the
 * parent container. They cascade here automatically. We read them via
 * var(--rsvp-accent) etc. in inline styles with safe fallbacks.
 *
 * For computed rgba() we also read the wedding object directly.
 */

function FormCard({ title, children, className = '' }: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-white/10 bg-white/[0.035] overflow-hidden ${className}`}>
      <div className="px-5 py-3 border-b border-white/10">
        <h2
          className="text-xs font-semibold uppercase tracking-[0.18em]"
          style={{ color: 'var(--rsvp-accent, #D4A5A5)' }}
        >
          {title}
        </h2>
      </div>
      <div className="p-5">
        {children}
      </div>
    </section>
  );
}

export default function RSVPForm({ guest, slug, existingRsvp, onSuccess, onViewWeddingPage }: RSVPFormProps) {
  const wedding = useWedding();
  const initialAttendanceChoice = existingRsvp
    ? existingRsvp.attending && existingRsvp.attending.length > 0
      ? 'yes'
      : 'no'
    : '';
  const { register, handleSubmit, watch, setValue, formState: { errors, isSubmitting } } = useForm({
    defaultValues: {
      attendance_choice: initialAttendanceChoice,
      attending: existingRsvp?.attending || [],
      phone: guest.phone || '',
      dietary: existingRsvp?.dietary || '',
      sms_opt_in: !!guest.sms_opt_in,
      email_opt_in: !!guest.email_opt_in,
    },
  });
  const [submitted, setSubmitted] = useState(false);
  const [submittedAttendance, setSubmittedAttendance] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const attendanceChoiceValue = watch('attendance_choice');
  const isAttending = attendanceChoiceValue === 'yes';
  const isDeclining = attendanceChoiceValue === 'no';

  useEffect(() => {
    if (isDeclining) {
      setValue('attending', []);
    }
  }, [isDeclining, setValue]);

  /* ─── theme colors (safe fallbacks to original wedding-rose) ─── */
  const tc = wedding?.theme_config;
  const accent = tc?.accent_color || '#D4A5A5';
  const aRgb = hexToRgb(accent);
  const accentRgba = (opacity: number) => `rgba(${aRgb.r}, ${aRgb.g}, ${aRgb.b}, ${opacity})`;

  /** Reusable accent button style */
  const accentBtnStyle: React.CSSProperties = {
    backgroundColor: accent,
    color: '#0f172a',
    boxShadow: `0 10px 15px -3px ${accentRgba(0.4)}`,
  };

  /** Input focus ring via Tailwind's internal CSS variable */
  const focusRingStyle: React.CSSProperties = {
    '--tw-ring-color': accent,
  } as React.CSSProperties;

  /** Checkbox / radio accent */
  const checkboxStyle: React.CSSProperties = {
    accentColor: accent,
  };

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
        label: getWeddingEventLabel(e.type, e.custom_type_label),
        date: e.date,
        time: e.details?.time,
        venue: e.details?.venue_name,
      }))
    : BUILT_IN_WEDDING_EVENT_OPTIONS.map((option) => ({ value: option.value, label: option.label }));

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

    if (/^\d{1,2}:\d{2}$/.test(timeStr)) {
      const [hours, minutes] = timeStr.split(':');
      return `${hours.padStart(2, '0')}:${minutes}`;
    }

    const colonMatch = timeStr.match(/(\d{1,2}):(\d{2})\s*(am|pm)?/i);
    if (colonMatch) {
      let hours = parseInt(colonMatch[1], 10);
      const minutes = colonMatch[2];
      const period = colonMatch[3]?.toLowerCase();
      if (period === 'pm' && hours !== 12) hours += 12;
      if (period === 'am' && hours === 12) hours = 0;
      return `${hours.toString().padStart(2, '0')}:${minutes}`;
    }

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

      const weddingTimezone = (wedding as any).timezone || 'America/Chicago';

      const formatICSDate = (year: number, month: number, day: number, hour: number, min: number): string => {
        const pad = (n: number) => n.toString().padStart(2, '0');
        return `${year}${pad(month)}${pad(day)}T${pad(hour)}${pad(min)}00`;
      };

      const uidBase = `${guest.id || guest.name || 'guest'}-${wedding.id || wedding.slug || 'event'}`
        .replace(/\s+/g, '-')
        .toLowerCase();
      const vevents = events.map((event, index) => {
        const eventDate = event.date || wedding.date;
        if (!eventDate) return '';

        const startTimeStr = event.details?.time || '12:00';
        const startTime = parseTimeToISO(startTimeStr);
        const [year, month, day] = eventDate.split('-').map(Number);
        const [startHour, startMin] = startTime.split(':').map(Number);

        let endHour = startHour + 3;
        let endDay = day;
        let endMonth = month;
        let endYear = year;
        if (endHour >= 24) {
          endHour -= 24;
          endDay += 1;
        }

        const eventTimezone = event.details?.timezone || weddingTimezone;

        const eventLabel = getWeddingEventLabel(event.type, event.custom_type_label);
        const summary = `${eventLabel} - ${wedding.couple_names || 'Event'}`;
        const location = event.details?.venue_name || event.details?.location || 'Event Venue';
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
          `UID:${uidBase}-${event.type}-${eventDate}-${index}@event-rsvp`,
          'END:VEVENT'
        ].join('\r\n');
      }).filter(Boolean);

      const ics = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Event RSVP//EN',
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
      link.download = 'event_invite.ics';
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

    try {
      const attendingRaw = data.attending;
      const attendingList: string[] = Array.isArray(attendingRaw)
        ? attendingRaw
        : (typeof attendingRaw === 'string' && attendingRaw ? [attendingRaw] : []);
      const isAttendingSubmission = data.attendance_choice === 'yes'
        ? true
        : data.attendance_choice === 'no'
          ? false
          : null;

      if (isAttendingSubmission === null) {
        setError('Please tell us whether you will attend.');
        return;
      }

      const selectedEvents = isAttendingSubmission ? attendingList : [];
      if (isAttendingSubmission && selectedEvents.length === 0) {
        setError('Please select at least one event you plan to attend.');
        return;
      }

      const phonePattern = /^\+?\d{10,15}$/;
      if (isAttendingSubmission) {
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
      }

      const filledPlusOnes = plusOnes
        .filter(p => p.name.trim())
        .map(p => ({
          name: p.name.trim(),
          phone: p.phone?.trim() || undefined,
          email: p.email?.trim() || undefined,
          attending: selectedEvents,
          dietary: p.dietary?.trim() || undefined,
          sms_opt_in: !!p.sms_opt_in,
          email_opt_in: !!p.email_opt_in,
        }));

      const submissionData = {
        attending: selectedEvents,
        phone: (data.phone || '').trim() || undefined,
        dietary: (data.dietary || '').trim() || undefined,
        sms_opt_in: !!data.sms_opt_in,
        email_opt_in: !!data.email_opt_in,
        plus_ones: isAttendingSubmission ? filledPlusOnes : [],
      };

      await submitGuestSessionRsvp(slug, submissionData);
      setSubmittedAttendance(isAttendingSubmission);
      setSubmitted(true);
      if (isAttendingSubmission) {
        generateICS();
      }
      onSuccess?.();
    } catch (err: any) {
      setError(err.message);
    }
  };

  if (submitted) {
    return (
      <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-8 text-center">
        <div
          className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-6"
          style={{ backgroundColor: accentRgba(0.2) }}
        >
          <svg className="w-8 h-8" style={{ color: accent }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h2 className="text-2xl font-semibold text-white mb-3">Thank you, {guest.name}</h2>
        <p className="text-slate-200 mb-1">Your RSVP has been received.</p>
        <p className="text-sm text-slate-400 mb-6">
          {submittedAttendance
            ? 'A calendar invite has been downloaded.'
            : 'Thank you for letting us know you cannot attend.'}
        </p>

        <div className="mt-8 pt-6 border-t border-white/10 space-y-4">
          <p className="text-sm text-slate-300">
            {submittedAttendance
              ? 'We look forward to celebrating with you.'
              : 'We will miss you at the celebration.'}
          </p>

          {onViewWeddingPage && (
            <button
              type="button"
              onClick={onViewWeddingPage}
              className="w-full py-4 font-semibold rounded-full shadow-lg hover:opacity-90 transition-all"
              style={accentBtnStyle}
            >
              View {wedding.couple_names ? `${wedding.couple_names}'s` : 'Event'} Page
            </button>
          )}

          {submittedAttendance && (
            <button
              type="button"
              onClick={generateICS}
              className="w-full py-3 border border-white/20 rounded-full text-sm text-slate-300 hover:text-white transition-all"
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = accentRgba(0.5); }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.2)'; }}
            >
              Download Calendar Invite Again
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center pb-6 border-b border-white/10">
        <div className="inline-flex items-center gap-2 border-b border-white/20 px-2 pb-2 text-xs uppercase tracking-[0.22em] mb-4">
          You&apos;re Invited
        </div>
        <h1 className="text-3xl font-semibold text-white mb-2">Welcome, {guest.name}</h1>
        <p className="text-slate-200 mb-4">
          Please RSVP for <span className="font-semibold" style={{ color: accent }}>{wedding.couple_names}&apos;s</span> event
        </p>
        <p className="text-sm text-slate-400">
          Fields marked with <span className="font-bold" style={{ color: accent }}>*</span> are required.
          Please tell us if you will attend and provide your contact details.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <FormCard title="Attendance *">
          <fieldset>
            <legend className="sr-only">Will you attend?</legend>
            <p className="text-sm text-slate-400 mb-4">
              Please choose one so the planner can count your response correctly.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <label
                className={`flex items-center gap-3 rounded-2xl border p-4 cursor-pointer transition-all ${
                  isAttending
                    ? 'bg-white/10'
                    : 'bg-white/[0.03] hover:bg-white/10'
                }`}
                style={{ borderColor: isAttending ? accentRgba(0.6) : 'rgba(255,255,255,0.1)' }}
              >
                <input
                  type="radio"
                  value="yes"
                  {...register('attendance_choice', { required: 'Please tell us whether you will attend.' })}
                  className="w-4 h-4"
                  style={{ ...checkboxStyle, ...focusRingStyle }}
                />
                <span className="text-sm font-medium text-slate-100">I will attend</span>
              </label>
              <label
                className={`flex items-center gap-3 rounded-2xl border p-4 cursor-pointer transition-all ${
                  isDeclining
                    ? 'bg-white/10'
                    : 'bg-white/[0.03] hover:bg-white/10'
                }`}
                style={{ borderColor: isDeclining ? accentRgba(0.6) : 'rgba(255,255,255,0.1)' }}
              >
                <input
                  type="radio"
                  value="no"
                  {...register('attendance_choice', { required: 'Please tell us whether you will attend.' })}
                  className="w-4 h-4"
                  style={{ ...checkboxStyle, ...focusRingStyle }}
                />
                <span className="text-sm font-medium text-slate-100">I cannot attend</span>
              </label>
            </div>
            {errors.attendance_choice && (
              <p className="text-xs mt-2" style={{ color: accent }}>
                {(errors.attendance_choice as any).message || 'Please choose one option'}
              </p>
            )}
          </fieldset>
        </FormCard>

        {/* Events */}
        <FormCard title={isAttending ? 'Events *' : 'Events'}>
          <p className="text-sm text-slate-400 mb-4">
            {isAttending
              ? 'Select at least one event you plan to attend.'
              : 'Events are disabled when you cannot attend.'}
          </p>
          <div className="space-y-3">
            {eventOptions.map((event: any) => (
              <label
                key={event.value}
                className="flex items-start p-4 rounded-xl border border-white/10 bg-white/[0.03] cursor-pointer transition-all hover:bg-white/10"
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = accentRgba(0.4); }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.1)'; }}
              >
                <input
                  type="checkbox"
                  value={event.value}
                  {...register('attending')}
                  disabled={isDeclining}
                  className="mt-0.5 w-4 h-4 rounded border-white/30 bg-white/10 focus:ring-offset-0 focus:ring-1"
                  style={{ ...checkboxStyle, ...focusRingStyle }}
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
                Phone Number <span className="font-bold" style={{ color: accent }}>*</span>
              </label>
              <input
                id="phone-input"
                type="tel"
                {...register('phone', { required: 'Phone number is required', pattern: { value: /^\+?\d{10,15}$/, message: 'Enter 10-15 digits, optionally starting with +' } })}
                placeholder="+15551234567"
                aria-invalid={errors.phone ? "true" : "false"}
                aria-describedby={errors.phone ? "phone-error" : "phone-hint"}
                className="w-full px-4 py-3 rounded-xl border text-white placeholder-slate-500 focus:ring-1 focus:outline-none transition-all backdrop-blur"
                style={{
                  ...focusRingStyle,
                  borderColor: errors.phone ? accentRgba(0.5) : 'rgba(255,255,255,0.1)',
                  backgroundColor: errors.phone ? accentRgba(0.05) : 'rgba(255,255,255,0.05)',
                }}
              />
              <p id="phone-hint" className="text-xs text-slate-500 mt-1">Enter digits only (10-15 digits). Example: +15551234567</p>
              {errors.phone && <p id="phone-error" className="text-xs mt-1" style={{ color: accent }}>{(errors.phone as any).message || 'Please enter a valid phone number'}</p>}
            </div>
            <div>
              <label className="block text-sm text-slate-200 mb-2">Dietary Restrictions</label>
              <input
                type="text"
                {...register('dietary')}
                placeholder="e.g., Vegetarian, Gluten-free"
                className="w-full px-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white placeholder-slate-500 focus:ring-1 focus:outline-none transition-all backdrop-blur"
                style={focusRingStyle}
              />
              <p className="text-xs text-slate-500 mt-1">Optional. Leave blank if you have no dietary restrictions.</p>
            </div>
          </div>
        </FormCard>

        {/* Notifications */}
        <FormCard title="Notifications">
          <p className="text-sm text-slate-400 mb-4">
            Optional. Choose how you&apos;d like to receive updates and reminders.
          </p>
          <div className="space-y-4">
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  {...register('sms_opt_in')}
                  className="mt-0.5 w-4 h-4 rounded border-white/30 bg-white/10 focus:ring-offset-0 focus:ring-1"
                  style={{ ...checkboxStyle, ...focusRingStyle }}
                />
                <div>
                  <span className="block text-sm font-medium text-white">SMS Reminders</span>
                  <span className="block text-xs text-slate-400 mt-0.5">Receive updates via text message</span>
                </div>
              </label>
              <p className="text-xs text-slate-500 mt-3 pl-7">
                By opting in, you consent to receive automated texts. Reply STOP to opt out. Msg rates may apply.{' '}
                <a
                  href="#"
                  onClick={(e) => { e.preventDefault(); window.open(`${window.location.origin}/${wedding.slug}#footer`, '_blank'); }}
                  className="hover:underline"
                  style={{ color: accent }}
                >
                  Terms
                </a>
              </p>
            </div>

            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.03]">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  {...register('email_opt_in')}
                  className="mt-0.5 w-4 h-4 rounded border-white/30 bg-white/10 focus:ring-offset-0 focus:ring-1"
                  style={{ ...checkboxStyle, ...focusRingStyle }}
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
        {guest.plus_one_allowed && guest.number_of_plus_ones_allowed > 0 && !isDeclining && (
          <FormCard title="Additional Guests">
            <p className="text-sm text-slate-400 mb-4">
              You may bring up to {guest.number_of_plus_ones_allowed} additional {guest.number_of_plus_ones_allowed === 1 ? 'guest' : 'guests'}.
              Click &quot;+ Add Guest&quot; below to add your guests. A name is required for each guest you add.
            </p>

            <div className="space-y-4">
              {plusOnes.map((plusOne, index) => (
                <div key={index} className="p-5 rounded-xl border border-white/10 bg-white/[0.03]">
                  <div className="flex justify-between items-center mb-4">
                    <span className="text-sm font-medium text-white">Guest {index + 1}</span>
                    <button
                      type="button"
                      onClick={() => removePlusOne(index)}
                      className="text-xs font-medium hover:opacity-80 transition-colors"
                      style={{ color: accent }}
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
                        className="w-full px-4 py-3 rounded-xl border text-white placeholder-slate-500 focus:ring-1 focus:outline-none backdrop-blur"
                        style={{
                          ...focusRingStyle,
                          borderColor: !plusOne.name.trim() && error?.includes('Guest') ? accentRgba(0.5) : 'rgba(255,255,255,0.1)',
                          backgroundColor: !plusOne.name.trim() && error?.includes('Guest') ? accentRgba(0.05) : 'rgba(255,255,255,0.05)',
                        }}
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
                          className="w-full px-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white placeholder-slate-500 focus:ring-1 focus:outline-none text-sm backdrop-blur"
                          style={focusRingStyle}
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
                          className="w-full px-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white placeholder-slate-500 focus:ring-1 focus:outline-none text-sm backdrop-blur"
                          style={focusRingStyle}
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
                        className="w-full px-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white placeholder-slate-500 focus:ring-1 focus:outline-none text-sm backdrop-blur"
                        style={focusRingStyle}
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
                          className="w-4 h-4 rounded border-white/30 bg-white/10 focus:ring-offset-0 focus:ring-1"
                          style={{ ...checkboxStyle, ...focusRingStyle }}
                        />
                        <span className="text-xs text-slate-300">SMS reminders</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={plusOne.email_opt_in || false}
                          onChange={(e) => { const n = [...plusOnes]; n[index].email_opt_in = e.target.checked; setPlusOnes(n); }}
                          className="w-4 h-4 rounded border-white/30 bg-white/10 focus:ring-offset-0 focus:ring-1"
                          style={{ ...checkboxStyle, ...focusRingStyle }}
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
                  className="w-full py-3 border border-dashed border-white/20 rounded-xl text-sm text-slate-300 hover:text-white transition-all"
                  onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = accentRgba(0.5); }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.2)'; }}
                >
                  + Add Guest
                </button>
              )}
            </div>
          </FormCard>
        )}

        {error && (
          <div
            className="rounded-2xl p-4 backdrop-blur"
            style={{
              borderWidth: 1,
              borderStyle: 'solid',
              borderColor: accentRgba(0.4),
              backgroundColor: accentRgba(0.1),
            }}
          >
            <div className="flex gap-3">
              <svg className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: accent }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              <div>
                <p className="text-sm font-medium mb-1" style={{ color: accent }}>RSVP could not be submitted</p>
                <p className="text-sm" style={{ color: accentRgba(0.8) }}>{error}</p>
              </div>
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full py-4 font-semibold rounded-full shadow-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
          style={accentBtnStyle}
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
