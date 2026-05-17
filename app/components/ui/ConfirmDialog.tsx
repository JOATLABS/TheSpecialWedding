'use client';

import { useState, useCallback, createContext, useContext, ReactNode, useRef, useEffect } from 'react';
import { AlertCircle, Info, AlertTriangle } from 'lucide-react';

export interface ConfirmDialogOptions {
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'warning' | 'info';
}

interface ConfirmDialogContextType {
  confirm: (options: ConfirmDialogOptions) => Promise<boolean>;
}

const ConfirmDialogContext = createContext<ConfirmDialogContextType | null>(null);

export function useConfirmDialog() {
  const ctx = useContext(ConfirmDialogContext);
  if (!ctx) throw new Error('useConfirmDialog must be used within ConfirmDialogProvider');
  return ctx;
}

interface DialogState extends ConfirmDialogOptions {
  isOpen: boolean;
  resolve?: (value: boolean) => void;
}

export function ConfirmDialogProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DialogState>({
    isOpen: false,
    message: '',
  });

  const resolveRef = useRef<((value: boolean) => void) | null>(null);
  const confirmButtonRef = useRef<HTMLButtonElement>(null);

  const confirm = useCallback((options: ConfirmDialogOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      resolveRef.current = resolve;
      setState({
        ...options,
        isOpen: true,
      });
    });
  }, []);

  const handleConfirm = () => {
    setState((prev) => ({ ...prev, isOpen: false }));
    resolveRef.current?.(true);
  };

  const handleCancel = () => {
    setState((prev) => ({ ...prev, isOpen: false }));
    resolveRef.current?.(false);
  };

  // Focus the confirm button when dialog opens and handle keyboard
  useEffect(() => {
    if (state.isOpen) {
      confirmButtonRef.current?.focus();

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          handleCancel();
        } else if (e.key === 'Enter') {
          handleConfirm();
        }
      };

      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [state.isOpen]);

  const getIcon = () => {
    const iconProps = 'h-6 w-6';
    switch (state.variant) {
      case 'danger':
        return <AlertCircle className={`${iconProps} text-red-500`} />;
      case 'warning':
        return <AlertTriangle className={`${iconProps} text-yellow-500`} />;
      case 'info':
        return <Info className={`${iconProps} text-blue-500`} />;
      default:
        return <AlertTriangle className={`${iconProps} text-blue-500`} />;
    }
  };

  const getButtonColors = () => {
    switch (state.variant) {
      case 'danger':
        return 'bg-red-500 hover:bg-red-600 text-white focus:ring-red-400/80';
      case 'warning':
        return 'bg-yellow-500 hover:bg-yellow-600 text-white focus:ring-yellow-400/80';
      case 'info':
        return 'bg-blue-600 hover:bg-blue-700 text-white focus:ring-blue-500';
      default:
        return 'bg-wedding-rose hover:bg-wedding-gold text-white focus:ring-wedding-gold/70';
    }
  };

  return (
    <ConfirmDialogContext.Provider value={{ confirm }}>
      {children}

      {state.isOpen && (
        <div className="fixed inset-0 z-[11000] flex items-center justify-center">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-sm"
            onClick={handleCancel}
          />

          {/* Dialog */}
          <div
            className="relative bg-white dark:bg-gray-800 rounded-lg shadow-lg w-full max-w-sm mx-4 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-dialog-title"
            aria-describedby="confirm-dialog-description"
          >
            <div className="p-6">
              {/* Icon and Title */}
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0">
                  {getIcon()}
                </div>
                <div className="flex-1">
                  {state.title && (
                    <h2
                      id="confirm-dialog-title"
                      className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1"
                    >
                      {state.title}
                    </h2>
                  )}
                  <p
                    id="confirm-dialog-description"
                    className="text-sm text-gray-600 dark:text-gray-400"
                  >
                    {state.message}
                  </p>
                </div>
              </div>

              {/* Buttons */}
              <div className="flex flex-col-reverse sm:flex-row sm:justify-end sm:gap-3 mt-6">
                <button
                  onClick={handleCancel}
                  className="px-4 py-2 rounded-md font-medium transition text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-1 dark:focus:ring-offset-gray-800 flex-1 sm:flex-none mb-2 sm:mb-0"
                >
                  {state.cancelText || 'Cancel'}
                </button>
                <button
                  ref={confirmButtonRef}
                  onClick={handleConfirm}
                  className={`px-4 py-2 rounded-md font-medium transition focus:outline-none focus:ring-2 focus:ring-offset-1 dark:focus:ring-offset-gray-800 flex-1 sm:flex-none ${getButtonColors()}`}
                >
                  {state.confirmText || 'Confirm'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </ConfirmDialogContext.Provider>
  );
}
