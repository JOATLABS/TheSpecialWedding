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

// Reusable Card component for form sections
function FormCard({ title, icon, children, className = '' }: {
  title: string;
  icon?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`bg-white rounded-2xl shadow-md border border-gray-100 overflow-hidden ${className}`}>
      <div className="bg-gradient-to-r from-wedding-blush/50 to-wedding-ivory px-5 py-4 border-b border-gray-100">
        <h2 className="text-base font-semibold text-wedding-navy flex items-center gap-2">
          {icon && <span className="text-lg">{icon}</span>}
          {title}
        </h2>
      </div>
      <div className="p-5">
        {children}
      </div>
    </div>
  );
}

export default function RSVPForm({ guest, token }: RSVPFormProps) {
  const wedding = useWedding();
  const { register, handleSubmit, formState: { errors, isSubmitting }, watch, setValue } = useForm();
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

  // Helper to parse time strings like "3:00 PM" or "15:00" to 24-hour format "HH:mm"
  const parseTimeToISO = (timeStr: string): string => {
    if (!timeStr) return '12:00';

    // Already in 24-hour format like "15:00"
    if (/^\d{1,2}:\d{2}$/.test(timeStr) && !timeStr.toLowerCase().includes('am') && !timeStr.toLowerCase().includes('pm')) {
      const [hours, minutes] = timeStr.split(':');
      return `${hours.padStart(2, '0')}:${minutes}`;
    }

    // Parse 12-hour format like "3:00 PM" or "3:00PM"
    const match = timeStr.match(/(\d{1,2}):(\d{2})\s*(am|pm)?/i);
    if (match) {
      let hours = parseInt(match[1], 10);
      const minutes = match[2];
      const period = match[3]?.toLowerCase();

      if (period === 'pm' && hours !== 12) hours += 12;
      if (period === 'am' && hours === 12) hours = 0;

      return `${hours.toString().padStart(2, '0')}:${minutes}`;
    }

    return '12:00'; // Default fallback
  };

  const generateICS = () => {
    try {
      // Try to find white_wedding event first, then fall back to first event or wedding date
      const event = wedding.events?.find(e => e.type === 'white_wedding') || wedding.events?.[0];
      const eventDate = event?.date || wedding.date;

      if (!eventDate) {
        console.error('No event date available for calendar invite');
        return;
      }

      const startTimeStr = event?.details?.time || '12:00';
      const startTime = parseTimeToISO(startTimeStr);

      // Create start date - note: parse as local time, not UTC
      const [year, month, day] = eventDate.split('-').map(Number);
      const [startHour, startMin] = startTime.split(':').map(Number);

      const startDate = new Date(year, month - 1, day, startHour, startMin);

      // End time: 3 hours after start (backend doesn't have endTime field)
      const endDate = new Date(startDate.getTime() + 3 * 60 * 60 * 1000);

      // Format dates for ICS (YYYYMMDDTHHMMSS format, local time)
      const formatICSDate = (date: Date): string => {
        const pad = (n: number) => n.toString().padStart(2, '0');
        return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}T${pad(date.getHours())}${pad(date.getMinutes())}00`;
      };

      const location = event?.details?.venue_name || event?.details?.location || 'Wedding Venue';
      const summary = `${wedding.couple_names || 'Wedding'} Celebration`;

      const ics = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Wedding RSVP//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        `DTSTART:${formatICSDate(startDate)}`,
        `DTEND:${formatICSDate(endDate)}`,
        `SUMMARY:${summary}`,
        `LOCATION:${location}`,
        `DESCRIPTION:You are cordially invited to celebrate with us!`,
        `UID:${Date.now()}@wedding-rsvp`,
        'END:VEVENT',
        'END:VCALENDAR'
      ].join('\r\n');

      const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' });
      const url = URL.createObjectURL(blob);

      // Create and trigger download
      const link = document.createElement('a');
      link.href = url;
      link.download = 'wedding_invite.ics';
      link.style.display = 'none';
      document.body.appendChild(link);

      // Small delay to ensure browser processes the link
      setTimeout(() => {
        link.click();
        setTimeout(() => {
          document.body.removeChild(link);
          URL.revokeObjectURL(url);
        }, 100);
      }, 0);

    } catch (error) {
      console.error('Error generating calendar invite:', error);
    }
  };

  const onSubmit = async (data: any) => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const apiUrl = baseUrl.replace('/admin', '');

      const filledPlusOnes = plusOnes.filter(p => p.name.trim());

      const mainRsvpData = {
        ...data,
        wedding_id: wedding.id,
        plus_ones: filledPlusOnes
      };

      const res = await fetch(`${apiUrl}/rsvp/invite/${token}/rsvp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mainRsvpData)
      });

      if (!res.ok) throw new Error('RSVP failed');

      localStorage.setItem(`rsvp-${token}`, 'true');
      setSubmitted(true);
      generateICS();
    } catch (err: any) {
      setError(err.message);
    }
  };

  // Success state with modern card design
  if (submitted) {
    return (
      <div className="bg-white rounded-2xl shadow-lg border border-green-200 overflow-hidden">
        <div className="h-2 bg-gradient-to-r from-green-400 via-wedding-sage to-green-400" />
        <div className="p-8 text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-2xl font-semibold text-wedding-navy mb-2">
            Thank You, {guest.name}!
          </h2>
          <p className="text-gray-600 mb-4">
            Your RSVP has been received.
          </p>
          <p className="text-sm text-gray-500">
            A calendar invite has been downloaded to help you remember the date.
          </p>
          <div className="flex items-center justify-center mt-6">
            <div className="h-px bg-wedding-rose/30 w-12" />
            <span className="mx-3 text-wedding-rose text-lg">&#9829;</span>
            <div className="h-px bg-wedding-rose/30 w-12" />
          </div>
          <p className="text-sm text-gray-500 mt-4">
            We can't wait to celebrate with you!
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Card */}
      <div className="bg-white rounded-2xl shadow-lg border border-wedding-rose/20 overflow-hidden">
        <div className="h-2 bg-gradient-to-r from-wedding-rose via-wedding-gold to-wedding-rose" />
        <div className="p-6 sm:p-8 text-center">
          <p className="text-wedding-rose font-medium text-sm tracking-wide uppercase mb-2">
            You're Invited
          </p>
          <h1 className="text-2xl sm:text-3xl font-semibold text-wedding-navy mb-3">
            Welcome, {guest.name}!
          </h1>
          <p className="text-gray-600">
            Please RSVP for
          </p>
          <p className="text-xl sm:text-2xl font-medium text-wedding-navy mt-1">
            {wedding.couple_names}'s Wedding
          </p>
          <div className="flex items-center justify-center mt-6">
            <div className="h-px bg-wedding-rose/30 w-16" />
            <span className="mx-3 text-wedding-gold">&#10022;</span>
            <div className="h-px bg-wedding-rose/30 w-16" />
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Events Card */}
        <FormCard title="Which events will you attend?" icon="&#128197;">
          <div className="space-y-3">
            {[
              { value: 'traditional', label: 'Traditional Ceremony' },
              { value: 'white_wedding', label: 'White Wedding' },
              { value: 'reception', label: 'Reception' },
            ].map((event) => (
              <label
                key={event.value}
                className="flex items-center p-3 rounded-xl border border-gray-200 hover:border-wedding-rose/50 hover:bg-wedding-blush/20 cursor-pointer transition-all"
              >
                <input
                  type="checkbox"
                  value={event.value}
                  {...register('attending')}
                  className="w-5 h-5 rounded text-wedding-rose focus:ring-wedding-rose focus:ring-offset-0"
                />
                <span className="ml-3 text-gray-700 font-medium">{event.label}</span>
              </label>
            ))}
          </div>
        </FormCard>

        {/* Contact Info Card */}
        <FormCard title="Your Information" icon="&#128100;">
          <div className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Dietary Restrictions
              </label>
              <input
                type="text"
                {...register('dietary')}
                placeholder="e.g., Vegetarian, Gluten-free, Nut allergy"
                className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-wedding-rose/50 focus:border-wedding-rose transition-all"
              />
              <p className="text-xs text-gray-500 mt-1">Leave blank if none</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Phone Number <span className="text-wedding-rose">*</span>
              </label>
              <input
                type="tel"
                defaultValue={guest.phone}
                {...register('phone', {
                  required: true,
                  pattern: /^\+?\d{10,15}$/
                })}
                placeholder="+1 (555) 123-4567"
                className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-wedding-rose/50 focus:border-wedding-rose transition-all"
              />
              {errors.phone && (
                <p className="text-red-500 text-sm mt-1 flex items-center gap-1">
                  <span>&#9888;</span> Please enter a valid phone number
                </p>
              )}
            </div>
          </div>
        </FormCard>

        {/* Notifications Card */}
        <FormCard title="Stay Updated" icon="&#128276;">
          <div className="space-y-5">
            {/* SMS Opt-in */}
            <div className="p-4 rounded-xl bg-gray-50 border border-gray-200">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  {...register('sms_opt_in')}
                  defaultChecked={false}
                  className="mt-1 w-5 h-5 rounded text-wedding-rose focus:ring-wedding-rose"
                />
                <div className="flex-1">
                  <span className="block font-semibold text-gray-800">
                    &#128241; SMS Reminders
                  </span>
                  <span className="block text-sm text-gray-600 mt-1">
                    Receive wedding updates and reminders via text message
                  </span>
                </div>
              </label>

              <div className="mt-3 pt-3 border-t border-gray-200">
                <p className="text-xs text-gray-500 leading-relaxed">
                  <strong>By checking above, you consent to receive automated texts from {wedding.couple_names || 'the couple'}.</strong>{' '}
                  Reply STOP to opt out. Msg & data rates may apply. Message frequency varies. Consent is not required to attend.{' '}
                  <a
                    href="#"
                    onClick={(e) => {
                      e.preventDefault();
                      window.open(window.location.origin + '/' + wedding.slug + '#footer', '_blank');
                    }}
                    className="text-wedding-rose hover:underline"
                  >
                    Terms & Privacy
                  </a>
                </p>
              </div>
            </div>

            {/* Email Opt-in */}
            <div className="p-4 rounded-xl bg-gray-50 border border-gray-200">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  {...register('email_opt_in')}
                  defaultChecked={false}
                  className="mt-1 w-5 h-5 rounded text-wedding-rose focus:ring-wedding-rose"
                />
                <div className="flex-1">
                  <span className="block font-semibold text-gray-800">
                    &#9993; Email Updates
                  </span>
                  <span className="block text-sm text-gray-600 mt-1">
                    Receive event details and updates via email
                  </span>
                </div>
              </label>

              <div className="mt-3 pt-3 border-t border-gray-200">
                <p className="text-xs text-gray-500">
                  Unsubscribe anytime via email link.
                </p>
              </div>
            </div>
          </div>
        </FormCard>

        {/* Plus Ones Card */}
        {guest.plus_one_allowed && guest.number_of_plus_ones_allowed > 0 && (
          <FormCard title="Additional Guests" icon="&#128101;">
            <div className="space-y-4">
              {/* Info banner */}
              <div className="flex items-center gap-2 p-3 bg-wedding-sage/20 rounded-xl border border-wedding-sage/30">
                <span className="text-wedding-sage text-xl">&#8505;</span>
                <p className="text-sm text-gray-700">
                  You may bring up to <strong>{guest.number_of_plus_ones_allowed}</strong> additional
                  {guest.number_of_plus_ones_allowed === 1 ? ' guest' : ' guests'}
                </p>
              </div>

              {/* Plus One Cards */}
              {plusOnes.map((plusOne, index) => (
                <div
                  key={index}
                  className="p-4 bg-white rounded-xl border-2 border-dashed border-gray-200 hover:border-wedding-rose/50 transition-colors"
                >
                  <div className="flex justify-between items-center mb-4">
                    <h3 className="font-semibold text-wedding-navy">
                      Guest {index + 1}
                    </h3>
                    <button
                      type="button"
                      onClick={() => removePlusOne(index)}
                      className="text-red-500 hover:text-red-700 text-sm font-medium flex items-center gap-1"
                    >
                      <span>&#10005;</span> Remove
                    </button>
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Full Name</label>
                      <input
                        className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-wedding-rose/50 focus:border-wedding-rose transition-all"
                        type="text"
                        placeholder="Enter guest's full name"
                        value={plusOne.name}
                        onChange={(e) => {
                          const newPlusOnes = [...plusOnes];
                          newPlusOnes[index].name = e.target.value;
                          setPlusOnes(newPlusOnes);
                        }}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Phone Number (Optional)</label>
                      <input
                        className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-wedding-rose/50 focus:border-wedding-rose transition-all"
                        type="tel"
                        placeholder="+1 (555) 123-4567"
                        value={plusOne.phone}
                        onChange={(e) => {
                          const newPlusOnes = [...plusOnes];
                          newPlusOnes[index].phone = e.target.value;
                          setPlusOnes(newPlusOnes);
                        }}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Email (Optional)</label>
                      <input
                        className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-wedding-rose/50 focus:border-wedding-rose transition-all"
                        type="email"
                        placeholder="guest@example.com"
                        value={plusOne.email || ''}
                        onChange={(e) => {
                          const newPlusOnes = [...plusOnes];
                          newPlusOnes[index].email = e.target.value;
                          setPlusOnes(newPlusOnes);
                        }}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Dietary Restrictions (Optional)</label>
                      <input
                        className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-wedding-rose/50 focus:border-wedding-rose transition-all"
                        type="text"
                        placeholder="e.g., Vegetarian, Gluten-free, etc."
                        value={plusOne.dietary}
                        onChange={(e) => {
                          const newPlusOnes = [...plusOnes];
                          newPlusOnes[index].dietary = e.target.value;
                          setPlusOnes(newPlusOnes);
                        }}
                      />
                    </div>

                    {/* Plus-One SMS Opt-in */}
                    <div className="bg-gray-50 rounded-xl p-3 border border-gray-200">
                      <label className="flex items-start gap-3 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={plusOne.sms_opt_in || false}
                          onChange={(e) => {
                            const newPlusOnes = [...plusOnes];
                            newPlusOnes[index].sms_opt_in = e.target.checked;
                            setPlusOnes(newPlusOnes);
                          }}
                          className="mt-1 w-4 h-4 rounded text-wedding-rose focus:ring-wedding-rose"
                        />
                        <div className="flex-1">
                          <span className="block font-medium text-gray-700 text-sm">
                            Receive SMS reminders
                          </span>
                          <span className="block text-xs text-gray-500 mt-1">
                            Standard message rates may apply. Reply STOP to opt out.
                          </span>
                        </div>
                      </label>
                    </div>

                    {/* Plus-One Email Opt-in */}
                    <div className="bg-gray-50 rounded-xl p-3 border border-gray-200">
                      <label className="flex items-start gap-3 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={plusOne.email_opt_in || false}
                          onChange={(e) => {
                            const newPlusOnes = [...plusOnes];
                            newPlusOnes[index].email_opt_in = e.target.checked;
                            setPlusOnes(newPlusOnes);
                          }}
                          className="mt-1 w-4 h-4 rounded text-wedding-rose focus:ring-wedding-rose"
                        />
                        <div className="flex-1">
                          <span className="block font-medium text-gray-700 text-sm">
                            Receive email updates
                          </span>
                          <span className="block text-xs text-gray-500 mt-1">
                            Unsubscribe anytime via email link.
                          </span>
                        </div>
                      </label>
                    </div>
                  </div>
                </div>
              ))}

              {/* Add Guest Button */}
              {plusOnes.length < guest.number_of_plus_ones_allowed && (
                <button
                  type="button"
                  onClick={addPlusOne}
                  className="w-full py-4 border-2 border-dashed border-wedding-rose/50 rounded-xl text-wedding-rose font-semibold hover:bg-wedding-blush/30 hover:border-wedding-rose transition-all flex items-center justify-center gap-2"
                >
                  <span className="text-xl">+</span>
                  Add a Guest
                </button>
              )}

              <p className="text-sm text-gray-500 italic text-center">
                Leave blank if you're not bringing additional guests
              </p>
            </div>
          </FormCard>
        )}

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center">
            <p className="text-red-600 font-medium">{error}</p>
          </div>
        )}

        {/* Submit Button */}
        <div className="pt-2">
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-4 bg-gradient-to-r from-wedding-rose to-wedding-rose/90 text-white text-lg font-semibold rounded-xl shadow-lg hover:shadow-xl hover:from-wedding-rose/90 hover:to-wedding-rose disabled:opacity-50 disabled:cursor-not-allowed transition-all transform hover:scale-[1.01] active:scale-[0.99]"
          >
            {isSubmitting ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Submitting...
              </span>
            ) : (
              'Confirm RSVP'
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
