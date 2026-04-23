// types/messaging.ts
//
// Shared wire types and authorship helpers for the couple ↔ planner thread.
//
// The server stamps each message with BOTH `sender_role` and `sender_email`.
// Authorship detection in the UI must prefer identity (`sender_email`) over
// role because a single email can be associated with more than one account
// (a planner can also be the couple on a separate wedding, and role-only
// checks misrender historic messages when the session role changes).
//
// Back-compat: rows written before the identity-stamping fix do not carry
// `sender_email`. For those, we fall back to role comparison so the UI stays
// sensible.

export type SenderRole = 'couple' | 'planner';

export interface CoupleThreadMessage {
  id: string;
  sender_role: SenderRole;
  sender_name: string;
  /**
   * Email of the account that actually wrote the message.
   * Optional for back-compat with rows stamped before identity tracking.
   */
  sender_email?: string | null;
  content: string;
  read_by_couple: boolean;
  read_by_planner: boolean;
  created_at?: string;
}

export interface CoupleThreadResponse {
  messages: CoupleThreadMessage[];
  count: number;
  /**
   * Cursor for the next (older) page. `null` when the current page is the
   * start of the thread.
   */
  next_cursor?: string | null;
}

export interface Viewer {
  /** Email of the logged-in viewer. Lowercased comparison is done inside. */
  email?: string | null;
  /** The role the viewer is currently acting as. */
  role: SenderRole;
}

/**
 * Returns true when `msg` was authored by the viewer.
 *
 * Identity first (sender_email), role fallback for legacy messages.
 */
export function isSelfAuthored(
  msg: Pick<CoupleThreadMessage, 'sender_role' | 'sender_email'>,
  viewer: Viewer,
): boolean {
  const viewerEmail = (viewer.email ?? '').trim().toLowerCase();
  const senderEmail = (msg.sender_email ?? '').trim().toLowerCase();

  if (viewerEmail && senderEmail) {
    return viewerEmail === senderEmail;
  }

  // Legacy row: no sender_email stamped on the server. Fall back to role.
  return msg.sender_role === viewer.role;
}
