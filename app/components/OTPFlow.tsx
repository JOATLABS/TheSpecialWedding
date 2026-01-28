// app/components/OTPFlow.tsx

'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function OTPFlow({ guest, token, slug }: { guest: any, token: string, slug: string }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const router = useRouter();

  const handleRequestOTP = async () => {
    setLoading(true);
    setError('');

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const response = await fetch(`${apiBase}/otp/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ guest_id: guest.id }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to send OTP');
      }

      // Redirect to the OTP verification page
      router.push(`/otp/verify?guest_id=${guest.id}&token=${token}&slug=${slug}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <p className="text-center text-gray-600 mb-6">
        To protect your privacy, we need to verify your identity before you can RSVP.
      </p>
      <button
        onClick={handleRequestOTP}
        disabled={loading}
        className="w-full bg-wedding-rose text-white py-3 px-6 rounded-lg font-semibold hover:opacity-90 disabled:opacity-50"
      >
        {loading ? 'Sending OTP...' : 'Verify My Identity'}
      </button>
      {error && <p className="text-red-500 text-center mt-4">{error}</p>}
    </div>
  );
}
