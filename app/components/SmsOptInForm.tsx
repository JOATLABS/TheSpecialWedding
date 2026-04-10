'use client';

import React, { useState } from 'react';

interface SmsOptInFormProps {
  weddingName: string;
  onSubmit: (data: {
    phone: string;
    smsTransactional: boolean;
    smsMarketing: boolean;
  }) => void;
  termsUrl?: string;
  privacyUrl?: string;
}

export function SmsOptInForm({
  weddingName,
  onSubmit,
  termsUrl = '/terms',
  privacyUrl = '/privacy'
}: SmsOptInFormProps) {
  const [phone, setPhone] = useState('');
  const [smsTransactional, setSmsTransactional] = useState(false);
  const [smsMarketing, setSmsMarketing] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!smsTransactional && !smsMarketing) {
      alert('Please select at least one notification type');
      return;
    }
    onSubmit({ phone, smsTransactional, smsMarketing });
    setShowConfirmation(true);
  };

  const formatPhoneNumber = (value: string) => {
    const phoneNumber = value.replace(/[^\d]/g, '');
    const phoneNumberLength = phoneNumber.length;

    if (phoneNumberLength < 4) return phoneNumber;
    if (phoneNumberLength < 7) {
      return `(${phoneNumber.slice(0, 3)}) ${phoneNumber.slice(3)}`;
    }
    return `(${phoneNumber.slice(0, 3)}) ${phoneNumber.slice(3, 6)}-${phoneNumber.slice(6, 10)}`;
  };

  if (showConfirmation) {
    return (
      <div className="bg-green-50 border border-green-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-green-800 mb-2">
          Successfully Subscribed!
        </h3>
        <p className="text-green-700">
          You have been subscribed to SMS notifications from JOAT Labs for {weddingName}.
          You will receive a confirmation message shortly.
        </p>
        <p className="text-sm text-green-600 mt-2">
          Reply STOP at any time to unsubscribe.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold mb-4">SMS Notifications</h3>

        <div className="mb-4">
          <label htmlFor="phone" className="block text-sm font-medium text-gray-700 mb-2">
            Phone Number
          </label>
          <input
            type="tel"
            id="phone"
            value={phone}
            onChange={(e) => setPhone(formatPhoneNumber(e.target.value))}
            placeholder="(555) 123-4567"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-wedding-rose"
            required
          />
        </div>

        <div className="space-y-3">
          <label className="flex items-start">
            <input
              type="checkbox"
              checked={smsTransactional}
              onChange={(e) => setSmsTransactional(e.target.checked)}
              className="mt-1 mr-3 h-4 w-4 text-wedding-rose focus:ring-wedding-rose border-gray-300 rounded"
            />
            <div>
              <span className="font-medium">Wedding Reminders & Updates</span>
              <p className="text-sm text-gray-600">
                Receive important reminders and updates from JOAT Labs for {weddingName}&apos;s wedding events
              </p>
            </div>
          </label>

          <label className="flex items-start">
            <input
              type="checkbox"
              checked={smsMarketing}
              onChange={(e) => setSmsMarketing(e.target.checked)}
              className="mt-1 mr-3 h-4 w-4 text-wedding-rose focus:ring-wedding-rose border-gray-300 rounded"
            />
            <div>
              <span className="font-medium">Special Offers (Optional)</span>
              <p className="text-sm text-gray-600">
                Receive special offers and promotional messages from wedding planner for {weddingName}
              </p>
            </div>
          </label>
        </div>

        <div className="mt-6 p-4 bg-gray-50 rounded-md">
          <p className="text-xs text-gray-600 leading-relaxed">
            <strong>IMPORTANT:</strong> You are subscribing to wedding reminders from JOAT Labs.
            Reply STOP to opt out. Reply HELP for help. Standard message and data rates may apply.
            Message frequency may vary.
          </p>
          <p className="text-xs text-gray-600 mt-2">
            By checking the box(es) above and submitting this form, you consent to receive
            automated text messages from JOAT Labs for the couple: {weddingName} at the phone number provided.
            Consent is not a condition of any purchase.
          </p>
          <div className="mt-2 text-xs">
            <a href={termsUrl} className="text-wedding-rose hover:underline">Terms & Conditions</a>
            {' | '}
            <a href={privacyUrl} className="text-wedding-rose hover:underline">Privacy Policy</a>
          </div>
        </div>
      </div>

      <button
        type="submit"
        className="w-full bg-wedding-rose text-white py-2 px-4 rounded-md hover:bg-wedding-rose-dark transition-colors"
      >
        Subscribe to SMS Notifications
      </button>
    </form>
  );
}
