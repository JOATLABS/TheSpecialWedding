'use client';

/**
 * Couple-side calendar API client.
 *
 * Mirrors the planner-side patterns in app/services/calendarApi.ts but uses
 * the couple-portal endpoints under /couple/portal/* and the cookie-based
 * couple session. Pairs with the SlotPicker UI.
 */

import { coupleFetch, extractApiErrorMessage } from './auth';

export interface AvailabilitySlot {
  staff_id: string;
  staff_email: string | null;
  start: string;
  end: string;
}

export interface AvailabilityResponse {
  slots: AvailabilitySlot[];
  count: number;
}

export interface BookMeetingRequest {
  staff_id: string;
  start: string;
  end: string;
  title: string;
  notes?: string;
  timezone?: string;
  idempotency_key: string;
}

export interface BookMeetingResponse {
  meeting_id: string;
  staff_id: string;
  start: string;
  end: string;
  sync_status: unknown;
  invite_status: unknown;
}

export async function getAvailability(params: {
  durationMinutes: number;
  start?: Date;
  end?: Date;
  staffId?: string;
}): Promise<AvailabilityResponse> {
  const search = new URLSearchParams();
  search.set('duration', String(params.durationMinutes));
  if (params.start) search.set('start', params.start.toISOString());
  if (params.end) search.set('end', params.end.toISOString());
  if (params.staffId) search.set('staff_id', params.staffId);

  const response = await coupleFetch(`/couple/portal/availability?${search.toString()}`);
  if (!response.ok) {
    throw new Error(await extractApiErrorMessage(response, 'Failed to load availability'));
  }
  return response.json();
}

export async function bookMeeting(body: BookMeetingRequest): Promise<BookMeetingResponse> {
  const response = await coupleFetch('/couple/portal/meetings/book', {
    method: 'POST',
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(await extractApiErrorMessage(response, 'Failed to book meeting'));
  }
  return response.json();
}
