'use client';

import { Fragment } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { XMarkIcon } from '@heroicons/react/24/outline';

interface TermsModalProps {
  isOpen: boolean;
  onClose: () => void;
  weddingName?: string;
}

export default function TermsModal({ isOpen, onClose, weddingName = "The Special Wedding" }: TermsModalProps) {
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
                  <h3 className="text-2xl font-bold text-gray-900">Terms of Service</h3>
                  <button
                    onClick={onClose}
                    className="rounded-md p-2 hover:bg-gray-100 transition-colors"
                  >
                    <XMarkIcon className="h-5 w-5" />
                  </button>
                </Dialog.Title>
                
                <div className="mt-2 max-h-[60vh] overflow-y-auto prose prose-sm">
                  <p className="text-sm text-gray-500 mb-4">Last updated: {new Date().toLocaleDateString()}</p>
                  
                  <h4 className="text-lg font-semibold mt-4">1. Acceptance of Terms</h4>
                  <p>
                    By accessing and using this wedding website for {weddingName}, you agree to be bound by these Terms of Service.
                  </p>

                  <h4 className="text-lg font-semibold mt-4">2. Use of Website</h4>
                  <p>
                    This website is provided for the purpose of sharing wedding information and managing RSVPs. You agree to use it only for its intended purpose.
                  </p>

                  <h4 className="text-lg font-semibold mt-4">3. SMS/Text Messaging Terms</h4>
                  <p>
                    By opting in to receive SMS notifications, you agree to receive automated text messages about the wedding events. These may include:
                  </p>
                  <ul>
                    <li>Event reminders and updates</li>
                    <li>Venue or schedule changes</li>
                    <li>Important wedding-related announcements</li>
                  </ul>
                  <p>
                    <strong>Message frequency:</strong> Message frequency may vary. You may receive up to 5 messages per month leading up to the wedding.
                  </p>
                  <p>
                    <strong>Message and data rates:</strong> Standard message and data rates may apply based on your mobile carrier plan.
                  </p>
                  <p>
                    <strong>Opt-out:</strong> You can opt out at any time by replying STOP to any message. You will receive a confirmation of your opt-out.
                  </p>
                  <p>
                    <strong>Help:</strong> For help, reply HELP to any message or contact us at (319) 529-6088.
                  </p>
                  <p>
                    <strong>Carriers:</strong> Messages are supported by major carriers including AT&T, Verizon, T-Mobile, Sprint, and others.
                  </p>

                  <h4 className="text-lg font-semibold mt-4">4. Privacy and Data Use</h4>
                  <p>
                    Your privacy is important to us. Please review our Privacy Policy to understand how we collect and use your information.
                  </p>

                  <h4 className="text-lg font-semibold mt-4">5. RSVP and Guest Information</h4>
                  <p>
                    By submitting an RSVP, you confirm that all information provided is accurate. RSVPs may be used for event planning and catering purposes.
                  </p>

                  <h4 className="text-lg font-semibold mt-4">6. Photo and Media</h4>
                  <p>
                    Photos and videos taken during the wedding events may be shared on this website. By attending, you consent to being photographed and having your image shared.
                  </p>

                  <h4 className="text-lg font-semibold mt-4">7. Limitations of Liability</h4>
                  <p>
                    This website is provided "as is" without warranties of any kind. We are not liable for any damages arising from your use of this website.
                  </p>

                  <h4 className="text-lg font-semibold mt-4">8. Changes to Terms</h4>
                  <p>
                    We reserve the right to update these terms at any time. Continued use of the website constitutes acceptance of any changes.
                  </p>

                  <h4 className="text-lg font-semibold mt-4">9. Contact Information</h4>
                  <p>
                    For questions about these terms, please contact us at:
                  </p>
                  <p>
                    Email: support@thespecialwedding.com<br />
                    Phone: (319) 529-6088
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