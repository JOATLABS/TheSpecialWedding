'use client';

import React, { useCallback, useMemo } from 'react';

import { resolveApiUrl } from '../saas/apiClient';

type AuthFlow = 'signup' | 'login';

type Provider = 'google' | 'apple';

export interface SocialAuthButtonsProps {
  flow: AuthFlow;
  redirectPath?: string;
  className?: string;
  buttonLayout?: 'stacked' | 'inline';
}

const providerMeta: Record<Provider, {
  label: string;
  description: string;
  brandColor: string;
  icon: React.ReactNode;
  defaultPath: string;
}> = {
  google: {
    label: 'Continue with Google',
    description: 'Use your Google Workspace or Gmail account',
    brandColor: '#ffffff',
    icon: (
      <svg aria-hidden="true" focusable="false" className="h-5 w-5" viewBox="0 0 533.5 544.3">
        <path fill="#EA4335" d="M533.5 278.4c0-17.4-1.6-34.1-4.6-50.4H272v95.3h147c-6.4 34.6-26 63.8-55.3 83.4v68.9h89.2c52.3-48.1 80.6-118.9 80.6-197.2z" />
        <path fill="#34A853" d="M272 544.3c74.9 0 137.7-24.8 183.7-67.1l-89.2-68.9c-24.8 16.7-56.5 26.5-94.5 26.5-72.6 0-134-49-155.9-114.9H24.5v72.2C70 486.2 164.3 544.3 272 544.3z" />
        <path fill="#FBBC04" d="M116.1 319.9c-10.6-31.6-10.6-65.5 0-97.1V150.6H24.5c-44.7 89.4-44.7 194.7 0 284.1l91.6-114.8z" />
        <path fill="#4285F4" d="M272 107.7c39.7-.6 77.7 14.5 106.7 42.4l79.4-79.4C409.6 24.5 343.1-1.5 272 0 164.3 0 70 58.1 24.5 150.6l91.6 72.2C138 156.7 199.4 107.7 272 107.7z" />
      </svg>
    ),
    defaultPath: '/auth/google',
  },
  apple: {
    label: 'Continue with Apple',
    description: 'Secure sign in with your Apple ID',
    brandColor: '#000000',
    icon: (
      <svg aria-hidden="true" focusable="false" className="h-5 w-5" viewBox="0 0 24 24">
        <path
          fill="currentColor"
          d="M16.365 1.43c0 1.14-.456 2.223-1.204 3.022-.872.94-2.29 1.67-3.614 1.57-.096-1.1.442-2.258 1.204-3.038.84-.86 2.32-1.52 3.614-1.554.032.166.048.334.048.5zm5.597 16.14c-.595 1.328-.876 1.918-1.64 3.095-1.065 1.7-2.567 3.823-4.43 3.84-1.657.016-2.086-1.065-4.347-1.054-2.26.01-2.747 1.07-4.404 1.055-1.863-.016-3.287-1.92-4.353-3.618-2.38-3.8-2.63-8.26-1.163-10.57 1.058-1.66 2.73-2.63 4.307-2.63 1.982 0 3.23 1.07 4.872 1.07 1.61 0 2.587-1.07 4.866-1.07 1.78 0 3.66.97 4.72 2.62-4.14 2.16-3.47 7.8.172 9.29z"
        />
      </svg>
    ),
    defaultPath: '/auth/apple',
  },
};

export const SocialAuthButtons: React.FC<SocialAuthButtonsProps> = ({
  flow,
  redirectPath,
  className = '',
  buttonLayout = 'stacked',
}) => {
  const destinations = useMemo(() => {
    const computeDestination = (provider: Provider, override?: string | null): string | null => {
      const trimmed = override?.trim();
      if (trimmed) {
        return trimmed;
      }

      try {
        return resolveApiUrl(providerMeta[provider].defaultPath);
      } catch (error) {
        if (process.env.NODE_ENV !== 'production') {
          // eslint-disable-next-line no-console
          console.error(`[social-auth] Unable to resolve ${provider} OAuth URL`, error);
        }
        return null;
      }
    };

    const resolved: Record<Provider, string | null> = {
      google: computeDestination('google', process.env.NEXT_PUBLIC_GOOGLE_OAUTH_URL ?? null),
      apple: computeDestination('apple', process.env.NEXT_PUBLIC_APPLE_OAUTH_URL ?? null),
    };

    return resolved;
  }, []);

  const handleProvider = useCallback(
    (provider: Provider) => {
      if (typeof window === 'undefined') {
        return;
      }

      const destination = destinations[provider];

      if (!destination) {
        if (process.env.NODE_ENV !== 'production') {
          // eslint-disable-next-line no-console
          console.warn(`[social-auth] Missing destination for provider: ${provider}`);
        }
        return;
      }

      let url: URL;

      try {
        url = new URL(destination);
      } catch (error) {
        if (process.env.NODE_ENV !== 'production') {
          // eslint-disable-next-line no-console
          console.error(`[social-auth] Invalid destination URL for ${provider}: ${destination}`, error);
        }
        return;
      }

      const redirectTarget = redirectPath ?? (flow === 'signup' ? '/setup-account' : '/admin');
      const redirectUrl = new URL(redirectTarget, window.location.origin);

      url.searchParams.set('redirect_uri', redirectUrl.toString());
      url.searchParams.set('context', flow);

      window.location.href = url.toString();
    },
    [destinations, flow, redirectPath]
  );

  return (
    <div
      className={`flex ${buttonLayout === 'inline' ? 'flex-row gap-2 sm:gap-3' : 'flex-col gap-2 sm:gap-3'} ${className}`}
      role="group"
      aria-label={`${flow === 'signup' ? 'Sign up' : 'Log in'} with a social account`}
    >
      {(Object.keys(providerMeta) as Provider[]).map((provider) => {
        const meta = providerMeta[provider];
        const isLight = meta.brandColor === '#ffffff';
        const subTextClass = isLight ? 'text-gray-500' : 'text-gray-200';

        const isDisabled = !destinations[provider];

        return (
          <button
            key={provider}
            type="button"
            onClick={() => handleProvider(provider)}
            className={`group relative flex h-12 w-12 items-center justify-center rounded-full border text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60 sm:h-auto sm:w-auto sm:rounded-lg sm:px-4 sm:py-2 sm:gap-3
              ${buttonLayout === 'inline' ? 'sm:flex-1' : 'sm:w-full'}
              ${isLight ? 'border-gray-300 bg-white text-gray-900 hover:bg-gray-50 focus-visible:outline-gray-400' : 'border-transparent bg-black text-white hover:bg-black/90 focus-visible:outline-black'}
            `}
            aria-label={`${meta.label} (${meta.description})`}
            disabled={isDisabled}
            aria-disabled={isDisabled}
          >
            <span
              className={`${isLight ? 'text-current' : 'text-white'} flex items-center justify-center text-base sm:text-inherit`}
              aria-hidden="true"
            >
              {meta.icon}
            </span>
            <span className="hidden sm:flex sm:flex-col sm:items-start sm:leading-tight sm:text-left">
              <span>{meta.label}</span>
              <span className={`text-xs font-normal ${subTextClass}`}>
                {flow === 'signup' ? 'Fast account setup' : 'Quick access without password'}
              </span>
            </span>
            {isDisabled && (
              <span className="pointer-events-none absolute inset-0 rounded-full bg-white/60 sm:rounded-lg" aria-hidden="true" />
            )}
          </button>
        );
      })}
    </div>
  );
};

export default SocialAuthButtons;
