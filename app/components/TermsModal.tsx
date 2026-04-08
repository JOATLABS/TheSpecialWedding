'use client';

import { Fragment, useMemo } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { formatDate } from '@/utils/dateFormat';

interface TermsModalProps {
  isOpen: boolean;
  onClose: () => void;
  weddingName?: string;
}

export default function TermsModal({
  isOpen,
  onClose,
  weddingName = 'The Special Wedding',
}: TermsModalProps) {
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
                    <h3 className="text-2xl font-bold text-slate-900">Terms of Service</h3>
                    <p className="mt-1 text-sm text-slate-500">Last updated: {lastUpdated}</p>
                  </div>
                  <button onClick={onClose} className="rounded-md p-2 transition-colors hover:bg-slate-100">
                    <XMarkIcon className="h-5 w-5 text-slate-600" />
                  </button>
                </Dialog.Title>

                <div className="prose prose-sm max-h-[60vh] overflow-y-auto text-slate-700">
                  <p>
                    {weddingName} runs on The Special Wedding planner platform. Planner owners are
                    responsible for workspace configuration, team-member access, calendar sharing
                    settings, and the meetings or tasks created in their business workspace.
                  </p>

                  <h4>Canonical scheduling model</h4>
                  <p>
                    Internal schedule items stored in The Special Wedding are the source of truth.
                    Connected Google calendars are projections used for visibility and coordination.
                  </p>

                  <h4>Team access and visibility</h4>
                  <p>
                    Team members may use shared calendar features only within the permissions and
                    wedding scope granted by the planner owner. External personal calendars are not
                    shared by default.
                  </p>

                  <h4>Couple delivery</h4>
                  <p>
                    Couples do not authorize calendars through OAuth in v1. Meeting delivery uses
                    the couple portal plus optional email/ICS delivery from the platform.
                  </p>

                  <h4>Google Calendar connections</h4>
                  <p>
                    By connecting Google Calendar, a user authorizes the app to manage calendar
                    projections for the connected calendars according to the sharing, visibility,
                    and writable-target settings configured in the planner workspace.
                  </p>

                  <p>
                    Read the full public terms at <a href="/terms">/terms</a> or contact{' '}
                    <a href="mailto:support@thespecialwedding.io">support@thespecialwedding.io</a>.
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
