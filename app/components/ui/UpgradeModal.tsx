import React from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { Fragment } from 'react';
import { Sparkles, Check, ArrowRight, X } from 'lucide-react';
import { useRouter } from 'next/navigation';

interface UpgradeModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
}

export default function UpgradeModal({
  isOpen,
  onClose,
  title = "Unlock Unlimited AI Power",
  description = "You've reached the limit of your free AI credits. Upgrade to a premium plan to continue using the AI assistant for seamless wedding planning.",
}: UpgradeModalProps) {
  const router = useRouter();

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
          <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95 translate-y-4"
              enterTo="opacity-100 scale-100 translate-y-0"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100 translate-y-0"
              leaveTo="opacity-0 scale-95 translate-y-4"
            >
              <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-2xl bg-white dark:bg-slate-800 p-6 text-left align-middle shadow-2xl transition-all border border-slate-200 dark:border-slate-700">
                <button
                  onClick={onClose}
                  className="absolute right-4 top-4 rounded-full p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-300 transition-colors"
                >
                  <X className="h-5 w-5" />
                </button>

                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-indigo-50 dark:bg-indigo-900/30 mb-6">
                  <Sparkles className="h-8 w-8 text-indigo-600 dark:text-indigo-400" />
                </div>

                <Dialog.Title
                  as="h3"
                  className="text-xl font-bold leading-6 text-slate-900 dark:text-white text-center mb-2"
                >
                  {title}
                </Dialog.Title>
                
                <div className="mt-2">
                  <p className="text-sm text-slate-500 dark:text-slate-400 text-center mb-6">
                    {description}
                  </p>

                  <div className="space-y-3 bg-slate-50 dark:bg-slate-900/50 p-4 rounded-xl mb-6">
                    {[
                      'Unlimited AI Chat & Workflow Automation',
                      'Automated Budget & Vendor Insights',
                      'Instant Email & Contract Drafting',
                      'Smart Seating Optimization',
                    ].map((feature, i) => (
                      <div key={i} className="flex items-center gap-3">
                        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400">
                          <Check className="h-3 w-3 flex-shrink-0" />
                        </div>
                        <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{feature}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-6 flex flex-col gap-3">
                  <button
                    type="button"
                    className="inline-flex w-full justify-center rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-3 text-sm font-semibold text-white shadow-md hover:from-indigo-500 hover:to-violet-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 transition-all hover:shadow-lg items-center gap-2 group"
                    onClick={() => {
                      onClose();
                      router.push('/admin/saas');
                    }}
                  >
                    View Premium Plans
                    <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
                  </button>
                  <button
                    type="button"
                    className="inline-flex w-full justify-center rounded-xl bg-white dark:bg-slate-800 px-4 py-3 text-sm font-medium text-slate-700 dark:text-slate-300 shadow-sm ring-1 ring-inset ring-slate-300 dark:ring-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700 focus:outline-none transition-all"
                    onClick={onClose}
                  >
                    Maybe Later
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
