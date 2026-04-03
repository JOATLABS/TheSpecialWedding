'use client';

import { getApiBaseUrl } from '@/utils/env';

const API_URL = getApiBaseUrl().replace('/admin', '');

export interface GuestAccessResponse {
  wedding: any;
  guest?: any;
  rsvp?: any;
  auth_method?: string;
  otp_verified?: boolean;
}

interface GuestOtpResponse {
  message: string;
  contact_type?: 'phone' | 'email';
  fallback_used?: boolean;
}

async function readJson(response: Response): Promise<any> {
  return response.json().catch(() => ({}));
}

async function throwIfError(response: Response, fallbackMessage: string): Promise<void> {
  if (response.ok) {
    return;
  }

  const errorData = await readJson(response);
  const detail = errorData?.detail;

  if (typeof detail === 'string' && detail) {
    throw new Error(detail);
  }

  if (Array.isArray(detail)) {
    const fieldLabels: Record<string, string> = {
      phone: 'Phone number',
      attending: 'Events',
      dietary: 'Dietary restrictions',
      name: 'Name',
      email: 'Email',
      plus_ones: 'Additional guests',
      otp: 'Verification code',
    };

    const message = detail
      .map((entry: any) => {
        const field = entry?.loc?.slice(-1)[0] || 'Unknown field';
        const label = fieldLabels[field] || field;
        return `${label}: ${entry?.msg || 'Invalid value'}`;
      })
      .join('. ');

    throw new Error(message || fallbackMessage);
  }

  if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
    throw new Error(detail.message);
  }

  throw new Error(fallbackMessage);
}

export async function exchangeGuestInviteToken(slug: string, token: string): Promise<GuestAccessResponse> {
  const response = await fetch(
    `${API_URL}/weddings/guest-access/${encodeURIComponent(slug)}/${encodeURIComponent(token)}/exchange`,
    {
      method: 'POST',
      credentials: 'include',
      cache: 'no-store',
    },
  );

  await throwIfError(response, 'Failed to exchange guest invite');
  return readJson(response);
}

export async function fetchGuestSessionAccess(slug: string): Promise<GuestAccessResponse | null> {
  const response = await fetch(
    `${API_URL}/weddings/guest-access/session/${encodeURIComponent(slug)}`,
    {
      credentials: 'include',
      cache: 'no-store',
    },
  );

  if (response.status === 401 || response.status === 403 || response.status === 404) {
    return null;
  }

  await throwIfError(response, 'Failed to load guest access session');
  return readJson(response);
}

export async function requestGuestSessionOtp(): Promise<GuestOtpResponse> {
  const response = await fetch(`${API_URL}/otp/request/session`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
  });

  await throwIfError(response, 'Failed to send verification code');
  return readJson(response);
}

export async function verifyGuestSessionOtp(otp: string): Promise<GuestAccessResponse> {
  const response = await fetch(`${API_URL}/otp/verify/session`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    cache: 'no-store',
    body: JSON.stringify({ otp }),
  });

  await throwIfError(response, 'Failed to verify code');
  return readJson(response);
}

export async function submitGuestSessionRsvp(slug: string, submissionData: unknown): Promise<void> {
  const response = await fetch(`${API_URL}/rsvp/session/${encodeURIComponent(slug)}/rsvp`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    cache: 'no-store',
    body: JSON.stringify(submissionData),
  });

  await throwIfError(response, 'Failed to submit RSVP');
}
