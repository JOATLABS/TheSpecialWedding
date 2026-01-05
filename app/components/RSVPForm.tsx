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
  attending?: string[];
  dietary?: string;
}

export default function RSVPForm({ guest, token }: RSVPFormProps) {
  const wedding = useWedding();
  const { register, handleSubmit, formState: { errors, isSubmitting }, watch, setValue } = useForm();
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plusOnes, setPlusOnes] = useState<PlusOneData[]>([]);
  
  const addPlusOne = () => {
    if (plusOnes.length < guest.number_of_plus_ones_allowed) {
      setPlusOnes([...plusOnes, { name: '', phone: '', attending: [], dietary: '' }]);
    }
  };

  const removePlusOne = (index: number) => {
    const newPlusOnes = [...plusOnes];
    newPlusOnes.splice(index, 1);
    setPlusOnes(newPlusOnes);
  };

  const generateICS = () => {
    const event = wedding.events?.find(e => e.type === 'white_wedding');
    const eventDate = event?.date || wedding.date;
    const startTime = event?.details?.time || '15:00';
    const endTime = event?.details?.endTime || '18:00';

    const start = new Date(`${eventDate}T${startTime}:00Z`);
    const end = new Date(`${eventDate}T${endTime}:00Z`);

    const ics = `BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nSUMMARY:${wedding.couple_names} Wedding\n` +
      `DTSTART:${start.toISOString().replace(/[:\-]/g, '').split('.')[0]}Z\n` +
      `DTEND:${end.toISOString().replace(/[:\-]/g, '').split('.')[0]}Z\n` +
      `LOCATION:${event?.details?.venue_name || 'Wedding Venue'}\nDESCRIPTION:You are invited!\nEND:VEVENT\nEND:VCALENDAR`;

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

  if (submitted) {
    return (
      <div className="text-center">
        <h2 className="text-xl font-bold text-green-600">Thank you for RSVPing!</h2>
        <p className="text-sm text-gray-500">Your calendar invite was downloaded.</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <div>
        <label className="block font-semibold text-gray-700 mb-3">Events Attending</label>
        <div className="space-y-2 sm:space-y-0 sm:space-x-4 sm:flex">
          <label className="flex items-center space-x-2">
            <input type="checkbox" value="traditional" {...register('attending')} className="rounded text-wedding-rose focus:ring-wedding-rose" />
            <span>Traditional</span>
          </label>
          <label className="flex items-center space-x-2">
            <input type="checkbox" value="white_wedding" {...register('attending')} className="rounded text-wedding-rose focus:ring-wedding-rose" />
            <span>White Wedding</span>
          </label>
          <label className="flex items-center space-x-2">
            <input type="checkbox" value="reception" {...register('attending')} className="rounded text-wedding-rose focus:ring-wedding-rose" />
            <span>Reception</span>
          </label>
        </div>
      </div>

      <div>
        <label className="block font-semibold text-gray-700 mb-2">Dietary Restrictions</label>
        <input 
          type="text" 
          className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-wedding-rose focus:border-transparent" 
          {...register('dietary')} 
          placeholder="None" 
        />
      </div>

      <div>
        <label className="block font-semibold text-gray-700 mb-2">Phone Number</label>
        <input 
          type="tel" 
          className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-wedding-rose focus:border-transparent" 
          defaultValue={guest.phone} 
          {...register('phone', {
            required: true,
            pattern: /^\+?\d{10,15}$/
          })} 
          placeholder="+1 (555) 123-4567"
        />
        {errors.phone && <p className="text-red-500 text-sm mt-1">Enter a valid phone number</p>}
      </div>

      {/* SMS Opt-in - Compliant with Toll-Free Requirements */}
      <div className="border border-gray-300 rounded-lg p-4">
        <h3 className="font-semibold text-gray-700 mb-3">SMS Notifications</h3>
        
        <label className="flex items-start space-x-3 mb-4">
          <input 
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

      {/* Email Opt-in */}
      <div className="border border-gray-300 rounded-lg p-4">
        <h3 className="font-semibold text-gray-700 mb-3">Email Notifications</h3>

        <label className="flex items-start space-x-3 mb-4">
          <input
            type="checkbox"
            {...register('email_opt_in')}
            defaultChecked={false}
            className="mt-1 rounded text-wedding-rose focus:ring-wedding-rose"
          />
          <div className="flex-1">
            <span className="block font-medium text-gray-700">
              Receive email updates from {wedding.couple_names || 'the couple'}
            </span>
            <span className="block text-sm text-gray-600 mt-1">
              Event reminders, schedule changes, and important wedding day information
            </span>
          </div>
        </label>

        <div className="bg-gray-50 p-3 rounded text-xs text-gray-600 leading-relaxed">
          <p>
            By checking the box above, you consent to receive email communications about this wedding.
            You can unsubscribe at any time by clicking the unsubscribe link in any email.
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
            {plusOnes.map((plusOne, index) => (
              <div key={index} className="p-4 bg-gray-50 rounded-lg">
                <div className="flex justify-between items-center mb-3">
                  <h3 className="font-medium text-gray-700">Guest {index + 1}</h3>
                  <button type="button" onClick={() => removePlusOne(index)} className="text-red-500 hover:text-red-700 text-sm">Remove</button>
                </div>
                <div className="space-y-4">
                  <div>
                    <label className="block font-medium text-gray-700 mb-2">Full Name</label>
                    <input 
                      className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-wedding-rose focus:border-transparent" 
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
                    <label className="block font-medium text-gray-700 mb-2">Phone Number (Optional)</label>
                    <input 
                      className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-wedding-rose focus:border-transparent" 
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
                    <label className="block font-medium text-gray-700 mb-2">Dietary Restrictions (Optional)</label>
                    <input 
                      className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-wedding-rose focus:border-transparent" 
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
                </div>
              </div>
            ))}
            {plusOnes.length < guest.number_of_plus_ones_allowed && (
              <button type="button" onClick={addPlusOne} className="w-full bg-gray-200 text-gray-700 py-2 px-4 rounded-lg hover:bg-gray-300">
                + Add Guest
              </button>
            )}
            <p className="text-sm text-gray-600 italic">
              * Leave blank if you’re not bringing additional guests
            </p>
          </div>
        </div>
      )}

      {error && <p className="text-red-600 text-center p-3 bg-red-50 rounded-lg">{error}</p>}

      <div className="flex justify-center pt-6">
        <button 
          disabled={isSubmitting} 
          type="submit" 
          className="w-full sm:w-auto bg-wedding-rose text-white px-8 py-4 rounded-lg font-semibold text-lg hover:bg-opacity-90 focus:ring-4 focus:ring-wedding-rose focus:ring-opacity-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          {isSubmitting ? 'Submitting...' : 'Submit RSVP'}
        </button>
      </div>
    </form>
  );
}
