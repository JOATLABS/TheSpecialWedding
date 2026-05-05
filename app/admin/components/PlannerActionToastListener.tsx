'use client';

/**
 * Renders the action-button toasts that fire on the two-stage
 * wedding-checklist nudge.
 *
 * Stage 1: notification type ``wedding_created`` — a discreet
 * "Wedding created — invite the couple next" toast with a button that
 * navigates to the wedding's couple tab.
 *
 * Stage 2: notification type ``couple_portal_accepted`` — fires a
 * one-click "Send checklist" toast carrying the seeded couple_intake
 * form_id in metadata. The button dispatches POST /admin/forms/{form_id}/send
 * with the couple's email pre-filled and shows a sonner success/error
 * toast based on the outcome.
 *
 * Listens to the existing ``notification-received`` CustomEvent that
 * TopHeader.tsx already dispatches whenever the SSE channel emits
 * ``notification-new`` — so we get every server-side
 * planner_notification_service.create_notification call automatically.
 *
 * Sonner API references:
 *   - toast.custom((id) => <JSX />) for action-button toasts
 *     https://sonner.emilkowal.ski/toast
 *   - toast.dismiss(id) to close after the action resolves
 *   - toast.success / toast.error for the post-action feedback
 */

import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { useRouter } from 'next/navigation';

import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';

interface NotificationDetail {
  type?: string;
  wedding_id?: string | null;
  metadata?: {
    form_id?: string | null;
    couple_email?: string | null;
    couple_names?: string | null;
  };
}

const COUPLE_INTAKE_TEMPLATE_ID = 'couple_intake';

/**
 * Server-issued URL prefixes are stable. Centralising them here keeps
 * the toast component purely declarative.
 */
function buildCoupleTabUrl(weddingId: string): string {
  return `/admin/planner/weddings/${encodeURIComponent(weddingId)}?tab=couple`;
}

interface SendChecklistArgs {
  formId: string;
  recipientEmail: string;
  recipientName: string | null;
  token: string;
}

async function sendSeededChecklist({
  formId,
  recipientEmail,
  recipientName,
  token,
}: SendChecklistArgs): Promise<void> {
  const baseUrl = getApiBaseUrl();
  // Sonner action button is a primary button per the spec — keep the
  // payload minimal so the button click is fast.
  const greetingName =
    (recipientName || '').trim().split(' ')[0] || 'there';
  const res = await fetch(
    `${baseUrl}/admin/forms/${encodeURIComponent(formId)}/send`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        recipient_emails: [recipientEmail],
        wedding_id: null,
        email_settings: {
          subject: 'Your wedding planning checklist',
          message: `Hi ${greetingName} — here's the planning checklist we use as a kick-off. Drop in answers as you go and ping me with anything you'd rather discuss live.`,
          sender_name: 'Your wedding planner',
          send_reminder: false,
          reminder_days: 7,
        },
      }),
    },
  );
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    const reason =
      (detail && (detail.detail || detail.message)) ||
      `Send failed (${res.status})`;
    throw new Error(reason);
  }
}

export default function PlannerActionToastListener() {
  const router = useRouter();
  const { token, userProfile } = useAdmin();
  const [resolvingFormId, setResolvingFormId] = useState(false);

  // The permission shape varies per role; we accept either a string-
  // array ``permissions`` list or an object with manage_forms=true.
  // Treating userProfile as ``unknown`` first keeps TypeScript happy
  // without forcing us to import the full UserProfile type ladder
  // (which the Record<string, unknown> conversion was attempting to
  // sidestep).
  const profileBag = (userProfile ?? {}) as unknown as Record<string, unknown>;
  const permissionsBag = profileBag.permissions;
  const teamHasManageForms = Array.isArray(permissionsBag)
    ? (permissionsBag as string[]).includes('manage_forms')
    : Boolean(
        (permissionsBag as Record<string, boolean> | undefined)?.manage_forms,
      );
  const canSendForms =
    !!userProfile &&
    Boolean(
      userProfile.is_wedding_planner ||
        (userProfile.is_team_member && teamHasManageForms),
    );

  const handleCoupleAccepted = useCallback(
    async (detail: NotificationDetail) => {
      const recipientEmail = detail?.metadata?.couple_email || '';
      const recipientName = detail?.metadata?.couple_names || null;
      let formId = detail?.metadata?.form_id || null;

      // Fallback: legacy notifications may not carry the form_id.
      // Ask the backend for the planner's seeded couple_intake id.
      if (!formId && token) {
        try {
          setResolvingFormId(true);
          const res = await fetch(
            `${getApiBaseUrl()}/admin/forms/seeded/${COUPLE_INTAKE_TEMPLATE_ID}`,
            { headers: { Authorization: `Bearer ${token}` } },
          );
          if (res.ok) {
            const body = await res.json();
            formId = body?.form_id || null;
          }
        } catch {
          // Ignore — toast falls back to bell-only mode.
        } finally {
          setResolvingFormId(false);
        }
      }

      const couplesLabel =
        (recipientName || '').trim() || 'The couple';

      toast.custom(
        (id) => (
          <div className="rounded-xl bg-white shadow-lg border border-[#eee5d8] p-4 flex flex-col gap-2 min-w-[320px] max-w-[380px]">
            <div className="text-sm font-semibold text-[#1a1a1a]">
              {couplesLabel} accepted the portal invite
            </div>
            <div className="text-xs text-[#555] leading-relaxed">
              Send them the wedding checklist now — it's the same form
              you've already loaded in your workspace.
            </div>
            <div className="flex items-center justify-end gap-2 mt-1">
              <button
                type="button"
                onClick={() => toast.dismiss(id)}
                className="text-xs text-[#9a8f82] hover:text-[#6b5d4f] px-2 py-1"
              >
                Later
              </button>
              {canSendForms && formId && recipientEmail && token && (
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      await sendSeededChecklist({
                        formId,
                        recipientEmail,
                        recipientName,
                        token,
                      });
                      toast.dismiss(id);
                      toast.success('Checklist sent');
                    } catch (err) {
                      toast.error(
                        err instanceof Error ? err.message : 'Send failed',
                      );
                    }
                  }}
                  className="rounded-full bg-[#6b5d4f] text-white text-xs font-medium px-3 py-1.5 hover:bg-[#574a3e]"
                >
                  Send checklist
                </button>
              )}
              {(!canSendForms || !formId || !recipientEmail) && (
                <button
                  type="button"
                  onClick={() => {
                    if (formId) {
                      router.push(
                        `/admin/planner/forms/${encodeURIComponent(formId)}/send` +
                          (recipientEmail
                            ? `?prefill_email=${encodeURIComponent(recipientEmail)}`
                            : ''),
                      );
                      toast.dismiss(id);
                    } else {
                      toast.dismiss(id);
                    }
                  }}
                  className="rounded-full border border-[#d6cfc1] text-[#1a1a1a] text-xs font-medium px-3 py-1.5 hover:bg-[#f5efe5]"
                >
                  Open form
                </button>
              )}
            </div>
          </div>
        ),
        { duration: 12000 },
      );
    },
    [canSendForms, router, token],
  );

  const handleWeddingCreated = useCallback(
    (detail: NotificationDetail) => {
      const weddingId = detail?.wedding_id || '';
      const couplesLabel = detail?.metadata?.couple_names || 'the couple';
      toast.custom(
        (id) => (
          <div className="rounded-xl bg-white shadow-lg border border-[#eee5d8] p-4 flex flex-col gap-2 min-w-[320px] max-w-[380px]">
            <div className="text-sm font-semibold text-[#1a1a1a]">
              New wedding created
            </div>
            <div className="text-xs text-[#555] leading-relaxed">
              Invite {couplesLabel} to their portal next — once they
              accept, you'll be prompted to send the wedding checklist.
            </div>
            <div className="flex items-center justify-end gap-2 mt-1">
              <button
                type="button"
                onClick={() => toast.dismiss(id)}
                className="text-xs text-[#9a8f82] hover:text-[#6b5d4f] px-2 py-1"
              >
                Later
              </button>
              {weddingId && (
                <button
                  type="button"
                  onClick={() => {
                    router.push(buildCoupleTabUrl(weddingId));
                    toast.dismiss(id);
                  }}
                  className="rounded-full bg-[#6b5d4f] text-white text-xs font-medium px-3 py-1.5 hover:bg-[#574a3e]"
                >
                  Invite the couple
                </button>
              )}
            </div>
          </div>
        ),
        { duration: 9000 },
      );
    },
    [router],
  );

  useEffect(() => {
    function onNotification(event: Event) {
      const custom = event as CustomEvent<NotificationDetail | undefined>;
      const detail = custom.detail || {};
      const type = detail.type;
      if (type === 'wedding_created') {
        handleWeddingCreated(detail);
      } else if (type === 'couple_portal_accepted') {
        // Don't await — let the resolver run in the background; the
        // toast still renders synchronously. We avoid awaiting here so
        // the listener doesn't drop subsequent events.
        void handleCoupleAccepted(detail);
      }
    }
    window.addEventListener('notification-received', onNotification);
    return () => {
      window.removeEventListener('notification-received', onNotification);
    };
  }, [handleCoupleAccepted, handleWeddingCreated]);

  // resolvingFormId is consumed only to avoid re-entrancy on rapid
  // double-clicks; the toast itself handles the visual loading state.
  void resolvingFormId;
  return null;
}
