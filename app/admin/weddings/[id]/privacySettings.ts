import type { PrivacySettings } from '@/types/wedding';

export type PrivacyMode = PrivacySettings['privacy_mode'];

export const DEFAULT_PRIVACY_SETTINGS: PrivacySettings = {
  privacy_mode: 'private',
  guest_auth_required: true,
  password_protection: '',
  allow_guest_sharing: false,
  require_phone_verification: false,
  require_name_verification: false,
};

export const PRIVACY_MODE_OPTIONS: Array<{
  value: PrivacyMode;
  label: string;
  description: string;
}> = [
  {
    value: 'private',
    label: 'Private',
    description: 'Invite token or one-time code required',
  },
  {
    value: 'password',
    label: 'Password',
    description: 'Anyone with the password can view',
  },
  {
    value: 'public',
    label: 'Public',
    description: 'Anyone with the link can view',
  },
];

export function normalizePrivacySettingsForMode(
  settings: PrivacySettings | null | undefined,
  mode: PrivacyMode,
): PrivacySettings {
  const merged: PrivacySettings = {
    ...DEFAULT_PRIVACY_SETTINGS,
    ...(settings ?? {}),
    privacy_mode: mode,
  };

  if (mode === 'public') {
    return {
      ...merged,
      password_protection: '',
      guest_auth_required: false,
      allow_guest_sharing: false,
      require_phone_verification: false,
      require_name_verification: false,
    };
  }

  if (mode === 'password') {
    return {
      ...merged,
      password_protection: merged.password_protection ?? '',
      guest_auth_required: false,
      allow_guest_sharing: false,
      require_phone_verification: false,
      require_name_verification: false,
    };
  }

  return {
    ...merged,
    password_protection: '',
    guest_auth_required: true,
    allow_guest_sharing: false,
    require_phone_verification: false,
    require_name_verification: false,
  };
}

export function getPrivacyModeSummary(mode: PrivacyMode): string {
  if (mode === 'public') {
    return 'Anyone with the link can open the wedding page and gallery immediately.';
  }

  if (mode === 'password') {
    return 'Guests skip identity verification and use the shared password instead.';
  }

  return 'Guests must use their invite token or request a one-time code sent to the original invitation contact.';
}

export function getPrivacyModeCallout(mode: PrivacyMode): {
  title: string;
  body: string;
} {
  if (mode === 'public') {
    return {
      title: 'Public access',
      body: 'The wedding page and gallery open without a password prompt or verification modal.',
    };
  }

  if (mode === 'password') {
    return {
      title: 'Password access',
      body: 'Share the password directly with guests who should be able to open the wedding page and gallery.',
    };
  }

  return {
    title: 'Private access',
    body: 'Guests can access with their personal invite token, or request a one-time code sent to the phone number or email already on their invitation.',
  };
}
