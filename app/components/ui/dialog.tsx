// components/ui/dialog.tsx
'use client';

import React from 'react';
import { Dialog as HeadlessDialog, Transition } from '@headlessui/react';
import { Fragment } from 'react';

interface DialogProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}

export function Dialog({ open, onOpenChange, children }: DialogProps) {
  return (
    <Transition appear show={open} as={Fragment}>
      <HeadlessDialog
        as="div"
        className="relative z-50"
        onClose={() => onOpenChange?.(false)}
      >
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
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              {children}
            </Transition.Child>
          </div>
        </div>
      </HeadlessDialog>
    </Transition>
  );
}

interface DialogContentProps {
  className?: string;
  children: React.ReactNode;
}

export function DialogContent({ className = '', children }: DialogContentProps) {
  return (
    <HeadlessDialog.Panel
      className={`bg-white rounded-lg shadow-xl max-w-md w-full p-6 ${className}`}
    >
      {children}
    </HeadlessDialog.Panel>
  );
}

interface DialogHeaderProps {
  className?: string;
  children: React.ReactNode;
}

export function DialogHeader({ className = '', children }: DialogHeaderProps) {
  return <div className={`mb-4 ${className}`}>{children}</div>;
}

interface DialogTitleProps {
  className?: string;
  children: React.ReactNode;
}

export function DialogTitle({ className = '', children }: DialogTitleProps) {
  return (
    <HeadlessDialog.Title className={`text-xl font-semibold text-gray-900 ${className}`}>
      {children}
    </HeadlessDialog.Title>
  );
}

interface DialogDescriptionProps {
  className?: string;
  children: React.ReactNode;
}

export function DialogDescription({ className = '', children }: DialogDescriptionProps) {
  return (
    <HeadlessDialog.Description className={`text-sm text-gray-600 ${className}`}>
      {children}
    </HeadlessDialog.Description>
  );
}

interface DialogFooterProps {
  className?: string;
  children: React.ReactNode;
}

export function DialogFooter({ className = '', children }: DialogFooterProps) {
  return <div className={`flex gap-2 mt-6 ${className}`}>{children}</div>;
}

