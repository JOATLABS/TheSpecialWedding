'use client';

export type GuestRsvpStatusFilter =
  | 'all'
  | 'responded'
  | 'confirmed'
  | 'declined'
  | 'pending'
  | 'not_invited';

export type GuestRsvpDisplayStatus =
  | 'confirmed'
  | 'declined'
  | 'pending'
  | 'not_invited';

interface GuestInviteFields {
  invite_sent?: boolean;
}

interface GuestRsvpFields {
  attending?: unknown;
}

export const GUEST_RSVP_STATUS_FILTER_OPTIONS: Array<{
  value: GuestRsvpStatusFilter;
  label: string;
}> = [
  { value: 'all', label: 'All RSVP states' },
  { value: 'responded', label: "RSVP'd" },
  { value: 'confirmed', label: 'Confirmed attending' },
  { value: 'declined', label: 'Declined' },
  { value: 'pending', label: 'Awaiting RSVP' },
  { value: 'not_invited', label: 'Not invited' },
];

export const GUEST_RSVP_STATUS_BADGE_STYLES: Record<
  GuestRsvpDisplayStatus,
  string
> = {
  confirmed: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200',
  declined: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200',
  pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200',
  not_invited: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300',
};

export function getRsvpAttendingList(rsvp?: GuestRsvpFields | null): string[] {
  return Array.isArray(rsvp?.attending) ? rsvp.attending : [];
}

function getRsvpAttendingStatus(
  rsvp?: GuestRsvpFields | null,
): 'confirmed' | 'declined' | 'pending' {
  const attending = rsvp?.attending;

  if (Array.isArray(attending)) {
    return attending.length > 0 ? 'confirmed' : 'declined';
  }

  if (attending && typeof attending === 'object') {
    const values = Object.values(attending as Record<string, unknown>);
    return values.some(Boolean) ? 'confirmed' : 'declined';
  }

  return 'pending';
}

export function getGuestRsvpDisplayStatus(
  guest: GuestInviteFields,
  rsvp?: GuestRsvpFields | null,
): GuestRsvpDisplayStatus {
  if (rsvp) {
    return getRsvpAttendingStatus(rsvp);
  }

  return guest.invite_sent ? 'pending' : 'not_invited';
}

export function getGuestRsvpStatusLabel(status: GuestRsvpDisplayStatus): string {
  switch (status) {
    case 'confirmed':
      return 'Confirmed';
    case 'declined':
      return 'Declined';
    case 'pending':
      return 'Pending';
    case 'not_invited':
      return 'Not invited';
  }
}

export function getGuestRsvpExportLabel(
  guest: GuestInviteFields,
  rsvp?: GuestRsvpFields | null,
): string {
  return getGuestRsvpStatusLabel(getGuestRsvpDisplayStatus(guest, rsvp));
}
