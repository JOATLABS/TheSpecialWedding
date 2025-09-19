// components/RSVPForm.tsx

'use client';

import { useForm } from 'react-hook-form';
import { useState } from 'react';
import { useWedding } from '@/hooks/useWedding';
import { formAutomationAttrs, guestAutomationAttrs, createAutomationAttrs } from '../utils/automation-attrs';

interface RSVPFormProps {
  guest: any;
  token: string;
}

interface PlusOneData {
  name: string;
  phone?: string;
  attending?: string[];
  dietary?: string;
}

export default function RSVPForm({ guest, token }: RSVPFormProps) {
  const wedding = useWedding();
  const { register, handleSubmit, formState: { errors, isSubmitting }, watch, setValue } = useForm();
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plusOnes, setPlusOnes] = useState<PlusOneData[]>([]);
  
  // Initialize plus-ones array based on allowed number
  useState(() => {
    if (guest.plus_one_allowed && guest.number_of_plus_ones_allowed > 0) {
      const initialPlusOnes = Array(guest.number_of_plus_ones_allowed).fill(null).map(() => ({
        name: '',
        phone: '',
        attending: [],
        dietary: ''
      }));
      setPlusOnes(initialPlusOnes);
    }
  });

  const generateICS = () => {
    const eventDate = wedding.events?.find(e => e.type === 'white_wedding')?.date || wedding.date;
    const start = new Date(eventDate + 'T15:00:00Z');
    const end = new Date(eventDate + 'T18:00:00Z');

    const ics = `BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nSUMMARY:${wedding.couple_names} Wedding\n` +
      `DTSTART:${start.toISOString().replace(/[-:]/g, '').split('.')[0]}Z\n` +
      `DTEND:${end.toISOString().replace(/[-:]/g, '').split('.')[0]}Z\n` +
      `LOCATION:Wedding Venue\nDESCRIPTION:You are invited!\nEND:VEVENT\nEND:VCALENDAR`;

    const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'wedding_invite.ics';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const onSubmit = async (data: any) => {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const apiUrl = baseUrl.replace('/admin', '');
      
      // Get filled plus-ones from form data
      const filledPlusOnes = [];
      for (let i = 0; i < guest.number_of_plus_ones_allowed; i++) {
        const plusOneName = data[`plus_one_${i}_name`];
        if (plusOneName && plusOneName.trim()) {
          filledPlusOnes.push({
            name: plusOneName,
            phone: data[`plus_one_${i}_phone`] || '',
            attending: data.attending || [], // Plus-ones attend same events as main guest
            dietary: data[`plus_one_${i}_dietary`] || ''
          });
        }
      }
      
      // Submit main RSVP with first plus-one (if any)
      const mainRsvpData = {
        ...data,
        wedding_id: wedding.id,
        plus_ones: filledPlusOnes // Send all plus-ones in array format
      };
      
      // Remove individual plus-one fields from main data
      for (let i = 0; i < guest.number_of_plus_ones_allowed; i++) {
        delete mainRsvpData[`plus_one_${i}_name`];
        delete mainRsvpData[`plus_one_${i}_phone`];
        delete mainRsvpData[`plus_one_${i}_dietary`];
      }
      
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

  if (submitted) {
    return (
      <div
        {...createAutomationAttrs({
          entity: 'rsvp',
          action: 'success',
          context: 'guest',
          state: 'submitted',
          custom: {
            'guest-id': guest.id,
            'guest-name': guest.name?.replace(/\s+/g, '-').toLowerCase() || 'unknown'
          }
        })}
        className="text-center"
      >
        <h2 className="text-xl font-bold text-green-600">Thank you for RSVPing!</h2>
        <p className="text-sm text-gray-500">Your calendar invite was downloaded.</p>
      </div>
    );
  }

  return (
    <form
      {...formAutomationAttrs('rsvp', undefined, 'submit', {
        valid: Object.keys(errors).length === 0,
        required: true,
        touched: true
      })}
      onSubmit={handleSubmit(onSubmit)}
      className="space-y-6"
    >
      <div>
        <label className="block font-semibold text-gray-700 mb-3">Events Attending</label>
        <div className="space-y-2 sm:space-y-0 sm:space-x-4 sm:flex">
          <label className="flex items-center space-x-2">
            <input
              {...guestAutomationAttrs(guest, 'checkbox-attending-traditional')}
              type="checkbox"
              value="traditional"
              {...register('attending')}
              className="rounded text-wedding-rose focus:ring-wedding-rose"
            />
            <span>Traditional</span>
          </label>
          <label className="flex items-center space-x-2">
            <input
              {...guestAutomationAttrs(guest, 'checkbox-attending-white-wedding')}
              type="checkbox"
              value="white_wedding"
              {...register('attending')}
              className="rounded text-wedding-rose focus:ring-wedding-rose"
            />
            <span>White Wedding</span>
          </label>
          <label className="flex items-center space-x-2">
            <input
              {...guestAutomationAttrs(guest, 'checkbox-attending-reception')}
              type="checkbox"
              value="reception"
              {...register('attending')}
              className="rounded text-wedding-rose focus:ring-wedding-rose"
            />
            <span>Reception</span>
          </label>
        </div>
      </div>

      <div>
        <label className="block font-semibold text-gray-700 mb-2">Dietary Restrictions</label>
        <input
          {...guestAutomationAttrs(guest, 'input-dietary-restrictions')}
          type="text"
          className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
          {...register('dietary')}
          placeholder="None"
        />
      </div>

      <div>
        <label className="block font-semibold text-gray-700 mb-2">Phone Number</label>
        <input
          {...guestAutomationAttrs(guest, 'input-phone-number')}
          type="tel"
          className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
          defaultValue={guest.phone}
          {...register('phone', {
            required: true,
            pattern: /^\+?\d{10,15}$/
          })}
          placeholder="+1 (555) 123-4567"
          data-field-valid={!errors.phone ? 'true' : 'false'}
          data-field-required="true"
        />
        {errors.phone && <p className="text-red-500 text-sm mt-1">Enter a valid phone number</p>}
      </div>

      {/* SMS Opt-in - Compliant with Toll-Free Requirements */}
      <div className="border border-gray-300 rounded-lg p-4">
        <h3 className="font-semibold text-gray-700 mb-3">SMS Notifications</h3>
        
        <label className="flex items-start space-x-3 mb-4">
          <input
            {...guestAutomationAttrs(guest, 'checkbox-sms-opt-in')}
            type="checkbox"
            {...register('sms_opt_in')}
            defaultChecked={false}
            className="mt-1 rounded text-wedding-rose focus:ring-wedding-rose"
          />
          <div className="flex-1">
            <span className="block font-medium text-gray-700">
              Receive wedding reminders and updates from {wedding.couple_names || 'the couple'}
            </span>
            <span className="block text-sm text-gray-600 mt-1">
              Important reminders about wedding events, venue details, and schedule updates
            </span>
          </div>
        </label>

        <div className="bg-gray-50 p-3 rounded text-xs text-gray-600 leading-relaxed">
          <p className="mb-2">
            <strong>By checking the box above, you consent to receive automated text messages from {wedding.couple_names || 'this wedding'}.</strong>
          </p>
          <p className="mb-2">
            Reply STOP to opt out. Reply HELP for help. Standard message and data rates may apply. 
            Message frequency may vary. Consent is not a condition of attending the wedding.
          </p>
          <p>
            <a 
              href="#" 
              onClick={(e) => {
                e.preventDefault();
                window.open(window.location.origin + '/' + wedding.slug + '#footer', '_blank');
              }}
              className="text-wedding-rose hover:underline"
            >
              Terms & Conditions
            </a>
            {' | '}
            <a 
              href="#" 
              onClick={(e) => {
                e.preventDefault();
                window.open(window.location.origin + '/' + wedding.slug + '#footer', '_blank');
              }}
              className="text-wedding-rose hover:underline"
            >
              Privacy Policy
            </a>
          </p>
          <p className="mt-2 font-medium">
            We will not share or sell your mobile information with third parties.
          </p>
        </div>
      </div>

      {guest.plus_one_allowed && guest.number_of_plus_ones_allowed > 0 && (
        <div className="border-t pt-6 mt-6">
          <h2 className="text-lg font-semibold text-gray-700 mb-4">
            Guest Information 
            <span className="text-sm font-normal text-gray-500 ml-2">
              (You can bring up to {guest.number_of_plus_ones_allowed} {guest.number_of_plus_ones_allowed === 1 ? 'guest' : 'guests'})
            </span>
          </h2>
          <div className="space-y-6">
            {Array.from({ length: guest.number_of_plus_ones_allowed }).map((_, index) => (
              <div key={index} className="p-4 bg-gray-50 rounded-lg">
                <h3 className="font-medium text-gray-700 mb-3">Guest {index + 1}</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block font-medium text-gray-700 mb-2">Full Name</label>
                    <input
                      {...createAutomationAttrs({
                        entity: 'plus-one',
                        action: 'input-name',
                        context: 'rsvp',
                        entityId: `${guest.id}-${index}`,
                        custom: {
                          'plus-one-index': index.toString(),
                          'guest-id': guest.id
                        }
                      })}
                      className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                      type="text"
                      placeholder="Enter guest's full name"
                      {...register(`plus_one_${index}_name`)}
                    />
                  </div>
                  <div>
                    <label className="block font-medium text-gray-700 mb-2">Phone Number (Optional)</label>
                    <input
                      {...createAutomationAttrs({
                        entity: 'plus-one',
                        action: 'input-phone',
                        context: 'rsvp',
                        entityId: `${guest.id}-${index}`,
                        custom: {
                          'plus-one-index': index.toString(),
                          'guest-id': guest.id
                        }
                      })}
                      className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                      type="tel"
                      placeholder="+1 (555) 123-4567"
                      {...register(`plus_one_${index}_phone`)}
                    />
                  </div>
                  <div>
                    <label className="block font-medium text-gray-700 mb-2">Dietary Restrictions (Optional)</label>
                    <input
                      {...createAutomationAttrs({
                        entity: 'plus-one',
                        action: 'input-dietary',
                        context: 'rsvp',
                        entityId: `${guest.id}-${index}`,
                        custom: {
                          'plus-one-index': index.toString(),
                          'guest-id': guest.id
                        }
                      })}
                      className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                      type="text"
                      placeholder="e.g., Vegetarian, Gluten-free, etc."
                      {...register(`plus_one_${index}_dietary`)}
                    />
                  </div>
                </div>
              </div>
            ))}
            <p className="text-sm text-gray-600 italic">
              * Leave blank if you're not bringing additional guests
            </p>
          </div>
        </div>
      )}

      {error && <p className="text-red-600 text-center p-3 bg-red-50 rounded-lg">{error}</p>}

      <div className="flex justify-center pt-6">
        <button
          {...guestAutomationAttrs(guest, 'submit-rsvp', 'public')}
          disabled={isSubmitting}
          type="submit"
          className="w-full sm:w-auto bg-wedding-rose text-white px-8 py-4 rounded-lg font-semibold text-lg hover:bg-opacity-90 focus:ring-4 focus:ring-wedding-rose focus:ring-opacity-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          data-state={isSubmitting ? 'loading' : 'ready'}
          data-form-valid={Object.keys(errors).length === 0 ? 'true' : 'false'}
        >
          {isSubmitting ? 'Submitting...' : 'Submit RSVP'}
        </button>
      </div>
    </form>
  );
}
