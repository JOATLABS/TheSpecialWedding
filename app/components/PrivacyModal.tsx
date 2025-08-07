'use client';

import { Fragment } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { XMarkIcon } from '@heroicons/react/24/outline';

interface PrivacyModalProps {
  isOpen: boolean;
  onClose: () => void;
  weddingName?: string;
}

export default function PrivacyModal({ isOpen, onClose, weddingName = "The Special Wedding" }: PrivacyModalProps) {
  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black bg-opacity-25" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-3xl transform overflow-hidden rounded-2xl bg-white p-6 text-left align-middle shadow-xl transition-all">
                <Dialog.Title as="div" className="flex justify-between items-center mb-4">
                  <h3 className="text-2xl font-bold text-gray-900">Privacy Policy</h3>
                  <button
                    onClick={onClose}
                    className="rounded-md p-2 hover:bg-gray-100 transition-colors"
                  >
                    <XMarkIcon className="h-5 w-5" />
                  </button>
                </Dialog.Title>
                
                <div className="mt-2 max-h-[60vh] overflow-y-auto prose prose-sm">
                  <p className="text-sm text-gray-500 mb-4">Last updated: {new Date().toLocaleDateString()}</p>
                  
                  <h4 className="text-lg font-semibold mt-4">1. Information We Collect</h4>
                  <p>
                    When you RSVP or interact with our wedding website, we may collect:
                  </p>
                  <ul>
                    <li>Your name and contact information</li>
                    <li>Phone number (if you opt-in to SMS notifications)</li>
                    <li>Email address</li>
                    <li>Dietary restrictions or preferences</li>
                    <li>Plus-one information</li>
                    <li>Event attendance selections</li>
                  </ul>

                  <h4 className="text-lg font-semibold mt-4">2. How We Use Your Information</h4>
                  <p>
                    We use the information collected to:
                  </p>
                  <ul>
                    <li>Manage wedding guest lists and RSVPs</li>
                    <li>Send event reminders and updates (if opted-in)</li>
                    <li>Plan catering and seating arrangements</li>
                    <li>Share important wedding-related information</li>
                    <li>Contact you in case of event changes</li>
                  </ul>

                  <h4 className="text-lg font-semibold mt-4">3. SMS/Mobile Information</h4>
                  <p className="font-semibold text-red-600">
                    We will not share or sell your mobile information with third parties for marketing purposes.
                  </p>
                  <p>
                    If you opt-in to receive SMS notifications:
                  </p>
                  <ul>
                    <li>Your phone number will only be used for wedding-related communications</li>
                    <li>You can opt-out at any time by replying STOP</li>
                    <li>Message frequency may vary but typically won't exceed 5 messages per month</li>
                    <li>Standard message and data rates may apply</li>
                  </ul>

                  <h4 className="text-lg font-semibold mt-4">4. Data Sharing and Disclosure</h4>
                  <p>
                    We do not sell, trade, or rent your personal information. We may share your information only:
                  </p>
                  <ul>
                    <li>With wedding vendors (caterers, venues) as necessary for event planning</li>
                    <li>When required by law or legal process</li>
                    <li>To protect the rights and safety of our guests</li>
                  </ul>

                  <h4 className="text-lg font-semibold mt-4">5. Data Security</h4>
                  <p>
                    We implement reasonable security measures to protect your personal information. However, no method of transmission over the internet is 100% secure.
                  </p>

                  <h4 className="text-lg font-semibold mt-4">6. Data Retention</h4>
                  <p>
                    We will retain your information for the duration needed to fulfill the wedding event purposes, typically up to 6 months after the wedding date. After this period, personal information will be deleted or anonymized.
                  </p>

                  <h4 className="text-lg font-semibold mt-4">7. Your Rights</h4>
                  <p>
                    You have the right to:
                  </p>
                  <ul>
                    <li>Access the personal information we have about you</li>
                    <li>Request correction of any inaccurate information</li>
                    <li>Request deletion of your information (subject to event planning needs)</li>
                    <li>Opt-out of SMS communications at any time</li>
                  </ul>

                  <h4 className="text-lg font-semibold mt-4">8. Children's Privacy</h4>
                  <p>
                    Our website is not intended for children under 13. We do not knowingly collect information from children under 13.
                  </p>

                  <h4 className="text-lg font-semibold mt-4">9. Cookies and Tracking</h4>
                  <p>
                    We use cookies to improve your experience and remember your RSVP status. You can disable cookies in your browser settings.
                  </p>

                  <h4 className="text-lg font-semibold mt-4">10. Third-Party Services</h4>
                  <p>
                    We use third-party services for:
                  </p>
                  <ul>
                    <li>SMS messaging (Telnyx/Twilio)</li>
                    <li>Email communications (Resend)</li>
                    <li>Website hosting and analytics</li>
                  </ul>
                  <p>
                    These services have their own privacy policies governing the use of your information.
                  </p>

                  <h4 className="text-lg font-semibold mt-4">11. Changes to This Policy</h4>
                  <p>
                    We may update this privacy policy from time to time. We will notify you of any changes by posting the new policy on this page.
                  </p>

                  <h4 className="text-lg font-semibold mt-4">12. Contact Us</h4>
                  <p>
                    If you have questions about this privacy policy or your personal information, please contact us at:
                  </p>
                  <p>
                    Email: support@thespecialwedding.com<br />
                    Phone: (319) 529-6088<br />
                    Website: thespecialwedding.com
                  </p>
                </div>

                <div className="mt-6">
                  <button
                    type="button"
                    className="w-full justify-center rounded-md border border-transparent bg-wedding-rose px-4 py-2 text-sm font-medium text-white hover:bg-wedding-rose-dark focus:outline-none focus-visible:ring-2 focus-visible:ring-wedding-rose focus-visible:ring-offset-2"
                    onClick={onClose}
                  >
                    Close
                  </button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}