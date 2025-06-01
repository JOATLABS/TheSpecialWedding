// components/RSVPForm.tsx

'use client';

import { useForm } from 'react-hook-form';
import { useState } from 'react';
import { useWedding } from '@/hooks/useWedding';

interface RSVPFormProps {
  guest: any;
  token: string;
}

export default function RSVPForm({ guest, token }: RSVPFormProps) {
  const wedding = useWedding();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm();
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      const res = await fetch(`/invite/${token}/rsvp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...data, wedding_id: wedding.id })
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
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div>
        <label className="block font-semibold">Events Attending</label>
        <div className="space-x-2">
          <input type="checkbox" value="traditional" {...register('attending')} /> Traditional
          <input type="checkbox" value="white_wedding" {...register('attending')} /> White Wedding
          <input type="checkbox" value="reception" {...register('attending')} /> Reception
        </div>
      </div>

      <div>
        <label className="block font-semibold">Dietary Restrictions</label>
        <input type="text" className="w-full border px-3 py-2" {...register('dietary')} placeholder="None" />
      </div>

      <div>
        <label className="block font-semibold">Phone</label>
        <input type="tel" className="w-full border px-3 py-2" defaultValue={guest.phone} {...register('phone', {
          required: true,
          pattern: /^\+?\d{10,15}$/
        })} />
        {errors.phone && <p className="text-red-500 text-sm">Enter a valid phone number</p>}
      </div>

      {guest.plus_one_allowed && (
        <div className="border-t pt-4">
          <h2 className="text-lg font-semibold">Plus One</h2>
          <input className="w-full border px-3 py-2" type="text" placeholder="Full Name" {...register('plus_one.name')} />
          <input className="w-full border px-3 py-2 mt-2" type="tel" placeholder="Phone Number (optional)" {...register('plus_one.phone')} />
        </div>
      )}

      {error && <p className="text-red-600 text-center">{error}</p>}

      <div className="flex justify-center pt-4">
        <button disabled={isSubmitting} type="submit" className="bg-pink-600 text-white px-6 py-2 rounded">
          {isSubmitting ? 'Submitting...' : 'Submit RSVP'}
        </button>
      </div>
    </form>
  );
}
