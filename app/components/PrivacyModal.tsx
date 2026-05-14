'use client';

import { Fragment, useMemo } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { formatDate } from '@/utils/dateFormat';

interface PrivacyModalProps {
  isOpen: boolean;
  onClose: () => void;
  weddingName?: string;
}

export default function PrivacyModal({
  isOpen,
  onClose,
  weddingName = 'The Special Wedding',
}: PrivacyModalProps) {
  const lastUpdated = useMemo(() => formatDate(new Date()), []);

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
          <div className="fixed inset-0 bg-black/25" />
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
              <Dialog.Panel className="w-full max-w-3xl transform overflow-hidden rounded-3xl bg-white p-6 text-left align-middle shadow-xl transition-all">
                <Dialog.Title as="div" className="mb-4 flex items-center justify-between">
                  <div>
                    <h3 className="text-2xl font-bold text-slate-900">Privacy Policy</h3>
                    <p className="mt-1 text-sm text-slate-500">Last updated: {lastUpdated}</p>
                  </div>
                  <button onClick={onClose} className="rounded-md p-2 transition-colors hover:bg-slate-100">
                    <XMarkIcon className="h-5 w-5 text-slate-600" />
                  </button>
                </Dialog.Title>

                <div className="prose prose-sm max-h-[60vh] overflow-y-auto text-slate-700">
                  <p>
                    {weddingName} uses The Special Wedding as a planner platform. Planner owners and
                    permitted team members can manage internal schedule items, connect external
                    calendars (Google, Microsoft 365, iCloud, Exchange/EWS), and deliver meetings
                    to couples through the portal plus email/ICS.
                  </p>

                  <h4>What data is collected</h4>
                  <ul>
                    <li>Planner and team-member account information</li>
                    <li>Wedding metadata, couple contact details, and meeting details</li>
                    <li>Connected calendar account email, calendar metadata, and connection health state</li>
                    <li>Encrypted account tokens (issued by our integration provider Aurinko, which brokers OAuth with each upstream provider) required to maintain calendar sync</li>
                  </ul>

                  <h4>How calendar data is used</h4>
                  <p>
                    Internal tasks and meetings remain the canonical records. Connected external
                    calendars are downstream projections used for shared planner visibility,
                    assigned-staff scheduling, and availability coordination.
                  </p>

                  <h4>Privacy defaults</h4>
                  <p>
                    Shared external calendars are opt-in. Personal external events render as
                    busy/free by default and only show full details when the planner owner enables
                    that on a specific connection.
                  </p>

                  <h4>Couples and OAuth</h4>
                  <p>
                    Couples do not connect personal calendars through OAuth in v1. Meetings are
                    shown in the couple portal and can also be delivered through email plus ICS.
                  </p>

                  <h4>Disconnect and deletion</h4>
                  <p>
                    Disconnecting a calendar removes local connection records used for sync and
                    revokes the Aurinko-brokered access for that provider account. Internal meetings
                    remain in the platform.
                  </p>

                  <p>
                    Read the full public privacy page at <a href="/privacy">/privacy</a>, review
                    Google deletion details at <a href="/google-data-deletion">/google-data-deletion</a>,
                    or contact <a href="mailto:support@thespecialwedding.io">support@thespecialwedding.io</a>.
                  </p>
                </div>

                <div className="mt-6">
                  <button
                    type="button"
                    className="w-full rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-700"
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
