'use client';

export interface GuestListSummary {
  totalGuests: number;
  invitedGuests: number;
  notInvitedGuests: number;
  respondedGuests: number;
  confirmedGuests: number;
  declinedGuests: number;
  pendingGuests: number;
  totalPlusOneSlots: number;
  respondedPlusOnes: number;
  pendingPlusOneSlots: number;
  submittedPlusOnes: number;
}

export interface GuestListFilterOptions {
  groups: string[];
  roles: string[];
}

export interface GuestListResponse<T> {
  guests: T[];
  total: number;
  page: number;
  pages: number;
  limit: number;
  summary: GuestListSummary;
  filter_options: GuestListFilterOptions;
}

export const EMPTY_GUEST_LIST_SUMMARY: GuestListSummary = {
  totalGuests: 0,
  invitedGuests: 0,
  notInvitedGuests: 0,
  respondedGuests: 0,
  confirmedGuests: 0,
  declinedGuests: 0,
  pendingGuests: 0,
  totalPlusOneSlots: 0,
  respondedPlusOnes: 0,
  pendingPlusOneSlots: 0,
  submittedPlusOnes: 0,
};

export const EMPTY_GUEST_LIST_FILTER_OPTIONS: GuestListFilterOptions = {
  groups: [],
  roles: [],
};

export function extractGuestListResponse<T>(data: unknown): GuestListResponse<T> {
  if (Array.isArray(data)) {
    return {
      guests: data,
      total: data.length,
      page: 1,
      pages: 1,
      limit: data.length,
      summary: EMPTY_GUEST_LIST_SUMMARY,
      filter_options: EMPTY_GUEST_LIST_FILTER_OPTIONS,
    };
  }

  if (data && typeof data === 'object') {
    const record = data as Partial<GuestListResponse<T>>;

    return {
      guests: Array.isArray(record.guests) ? record.guests : [],
      total: typeof record.total === 'number' ? record.total : 0,
      page: typeof record.page === 'number' ? record.page : 1,
      pages: typeof record.pages === 'number' ? record.pages : 1,
      limit: typeof record.limit === 'number' ? record.limit : 0,
      summary: record.summary ?? EMPTY_GUEST_LIST_SUMMARY,
      filter_options: record.filter_options ?? EMPTY_GUEST_LIST_FILTER_OPTIONS,
    };
  }

  return {
    guests: [],
    total: 0,
    page: 1,
    pages: 1,
    limit: 0,
    summary: EMPTY_GUEST_LIST_SUMMARY,
    filter_options: EMPTY_GUEST_LIST_FILTER_OPTIONS,
  };
}

export function extractGuestList<T>(data: unknown): T[] {
  return extractGuestListResponse<T>(data).guests;
}
