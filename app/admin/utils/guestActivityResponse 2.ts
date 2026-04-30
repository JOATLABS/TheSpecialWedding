'use client';

export interface GuestActivityItem {
  id?: string;
  type?: string;
  message?: string;
  timestamp?: string;
  metadata?: Record<string, unknown>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

export function extractGuestActivityItems(payload: unknown): GuestActivityItem[] | null {
  if (!isRecord(payload)) {
    return null;
  }
  if (payload.success === false) {
    return null;
  }

  const data = isRecord(payload.data) ? payload.data : null;
  const activities =
    data?.activities ?? (payload.success === true ? undefined : payload.activities);

  if (!Array.isArray(activities)) {
    return null;
  }

  if (!activities.every(isRecord)) {
    return null;
  }

  return activities as GuestActivityItem[];
}

export async function loadGuestActivityItems({
  apiBaseUrl,
  token,
  guestId,
  fetchImpl = fetch,
}: {
  apiBaseUrl: string;
  token: string;
  guestId: string;
  fetchImpl?: typeof fetch;
}): Promise<GuestActivityItem[]> {
  const response = await fetchImpl(`${apiBaseUrl}/admin/guests/${guestId}/activity`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error('Failed to fetch guest activity');
  }

  const payload = await response.json();
  const activities = extractGuestActivityItems(payload);
  if (!activities) {
    throw new Error('Unexpected guest activity response');
  }

  return activities;
}
