'use client';

/**
 * Renders the action-button toasts for the two-stage wedding-checklist
 * nudge.
 *
 * Stage 1 — wedding_created: "Invite the couple" toast.
 * Stage 2 — couple_portal_accepted: "Send checklist" toast that POSTs
 *   /admin/forms/{form_id}/send for the seeded couple_intake form.
 *
 * Listens to the existing notification-received CustomEvent that
 * TopHeader dispatches whenever the SSE channel emits notification-new.
 *
 * Batch 11 hardening:
 *   - In-flight Send button disabled + "Sending…" copy while the POST
 *     is outstanding so a double-click can't fire two requests.
 *   - On success: dismiss the action toast, show toast.success, and
 *     POST the new mark-actioned endpoint so the bell stops re-prompting.
 *   - On failure: replace the dismissed action toast with a sticky
 *     toast.error that exposes a Retry button; Retry re-runs the same
 *     payload until success or manual dismiss.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { useRouter } from 'next/navigation';

import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';

interface NotificationDetail {
  id?: string | null;
  type?: string;
  wedding_id?: string | null;
  action_url?: string | null;
  metadata?: {
    form_id?: string | null;
    couple_email?: string | null;
    couple_names?: string | null;
  };
}

const COUPLE_INTAKE_TEMPLATE_ID = 'couple_intake';

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

async function markNotificationActioned(
  notificationId: string,
  token: string,
): Promise<void> {
  // Best-effort — don't surface mark-actioned failures to the user.
  // The unread count will reconcile on the next SSE push.
  try {
    await fetch(
      `${getApiBaseUrl()}/admin/planner/activity-notifications/${encodeURIComponent(
        notificationId,
      )}/actioned`,
      {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}` },
      },
    );
  } catch {
    /* swallow */
  }
}

interface CoupleAcceptedToastBodyProps {
  detail: NotificationDetail;
  formId: string | null;
  canSendForms: boolean;
  token: string | null;
  router: ReturnType<typeof useRouter>;
  toastId: string | number;
  showRetryToast: (
    detail: NotificationDetail,
    formId: string | null,
    failureReason: string,
  ) => void;
}

function CoupleAcceptedToastBody({
  detail,
  formId,
  canSendForms,
  token,
  router,
  toastId,
  showRetryToast,
}: CoupleAcceptedToastBodyProps) {
  const [submitting, setSubmitting] = useState(false);

  const recipientEmail = detail?.metadata?.couple_email || '';
  const recipientName = detail?.metadata?.couple_names || null;
  const couplesLabel = (recipientName || '').trim() || 'The couple';
  const notificationId = detail?.id || null;

  const onSend = async () => {
    if (!formId || !recipientEmail || !token || submitting) return;
    setSubmitting(true);
    try {
      await sendSeededChecklist({
        formId,
        recipientEmail,
        recipientName,
        token,
      });
      toast.dismiss(toastId);
      toast.success('Checklist sent');
      if (notificationId) {
        await markNotificationActioned(notificationId, token);
        // Reconcile the bell.
        window.dispatchEvent(new Event('notifications-updated'));
      }
    } catch (err) {
      toast.dismiss(toastId);
      const reason = err instanceof Error ? err.message : 'Send failed';
      showRetryToast(detail, formId, reason);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="rounded-xl bg-white shadow-lg border border-[#eee5d8] p-4 flex flex-col gap-2 min-w-[320px] max-w-[380px]">
      <div className="text-sm font-semibold text-[#1a1a1a]">
        {couplesLabel} accepted the portal invite
      </div>
      <div className="text-xs text-[#555] leading-relaxed">
        Send them the wedding checklist now — it&apos;s the same form
        you&apos;ve already loaded in your workspace.
      </div>
      <div className="flex items-center justify-end gap-2 mt-1">
        <button
          type="button"
          onClick={() => toast.dismiss(toastId)}
          disabled={submitting}
          className="text-xs text-[#9a8f82] hover:text-[#6b5d4f] px-2 py-1 disabled:opacity-50"
        >
          Later
        </button>
        {canSendForms && formId && recipientEmail && token ? (
          <button
            type="button"
            data-testid="send-checklist-button"
            onClick={onSend}
            disabled={submitting}
            aria-busy={submitting || undefined}
            className="rounded-full bg-[#6b5d4f] text-white text-xs font-medium px-3 py-1.5 hover:bg-[#574a3e] disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {submitting ? 'Sending…' : 'Send checklist'}
          </button>
        ) : (
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
              }
              toast.dismiss(toastId);
            }}
            className="rounded-full border border-[#d6cfc1] text-[#1a1a1a] text-xs font-medium px-3 py-1.5 hover:bg-[#f5efe5]"
          >
            Open form
          </button>
        )}
      </div>
    </div>
  );
}

export default function PlannerActionToastListener() {
  const router = useRouter();
  const { token, userProfile } = useAdmin();
  const [resolvingFormId, setResolvingFormId] = useState(false);

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

  const showRetryToast = useCallback(
    (
      detail: NotificationDetail,
      formId: string | null,
      failureReason: string,
    ) => {
      toast.custom(
        (id) => {
          const recipientEmail = detail?.metadata?.couple_email || '';
          const recipientName = detail?.metadata?.couple_names || null;
          const couplesLabel = (recipientName || '').trim() || 'The couple';
          return (
            <RetryToastBody
              toastId={id}
              couplesLabel={couplesLabel}
              failureReason={failureReason}
              onRetry={async () => {
                if (!formId || !recipientEmail || !token) return;
                try {
                  await sendSeededChecklist({
                    formId,
                    recipientEmail,
                    recipientName,
                    token,
                  });
                  toast.dismiss(id);
                  toast.success('Checklist sent');
                  if (detail?.id) {
                    await markNotificationActioned(detail.id, token);
                    window.dispatchEvent(new Event('notifications-updated'));
                  }
                } catch (err) {
                  const reason =
                    err instanceof Error ? err.message : 'Send failed';
                  // Keep this toast open and refresh the message.
                  toast.dismiss(id);
                  showRetryToast(detail, formId, reason);
                }
              }}
            />
          );
        },
        // Sticky — user must Retry or dismiss manually.
        { duration: Infinity },
      );
    },
    [token],
  );

  const renderCoupleAcceptedToast = useCallback(
    async (detail: NotificationDetail) => {
      let formId = detail?.metadata?.form_id || null;

      // Fallback: legacy notifications may not carry the form_id.
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
          /* fall through to bell-only mode */
        } finally {
          setResolvingFormId(false);
        }
      }

      toast.custom(
        (id) => (
          <CoupleAcceptedToastBody
            detail={detail}
            formId={formId}
            canSendForms={canSendForms}
            token={token ?? null}
            router={router}
            toastId={id}
            showRetryToast={showRetryToast}
          />
        ),
        { duration: 12000 },
      );
    },
    [canSendForms, router, showRetryToast, token],
  );

  const renderWeddingCreatedToast = useCallback(
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
              Invite {couplesLabel} to their portal next — once they accept,
              you&apos;ll be prompted to send the wedding checklist.
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
                  onClick={async () => {
                    router.push(buildCoupleTabUrl(weddingId));
                    toast.dismiss(id);
                    if (detail.id && token) {
                      await markNotificationActioned(detail.id, token);
                      window.dispatchEvent(new Event('notifications-updated'));
                    }
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
    [router, token],
  );

  useEffect(() => {
    function onNotification(event: Event) {
      const custom = event as CustomEvent<NotificationDetail | undefined>;
      const detail = custom.detail || {};
      const type = detail.type;
      if (type === 'wedding_created') {
        renderWeddingCreatedToast(detail);
      } else if (type === 'couple_portal_accepted') {
        void renderCoupleAcceptedToast(detail);
      }
    }
    window.addEventListener('notification-received', onNotification);
    return () => {
      window.removeEventListener('notification-received', onNotification);
    };
  }, [renderCoupleAcceptedToast, renderWeddingCreatedToast]);

  void resolvingFormId;
  return null;
}

interface RetryToastBodyProps {
  toastId: string | number;
  couplesLabel: string;
  failureReason: string;
  onRetry: () => Promise<void>;
}

function RetryToastBody({
  toastId,
  couplesLabel,
  failureReason,
  onRetry,
}: RetryToastBodyProps) {
  const [retrying, setRetrying] = useState(false);
  return (
    <div className="rounded-xl bg-red-50 shadow-lg border border-red-300 p-4 flex flex-col gap-2 min-w-[320px] max-w-[380px]">
      <div className="text-sm font-semibold text-red-900">
        Couldn&apos;t send checklist to {couplesLabel}
      </div>
      <div className="text-xs text-red-700 leading-relaxed">
        {failureReason}
      </div>
      <div className="flex items-center justify-end gap-2 mt-1">
        <button
          type="button"
          onClick={() => toast.dismiss(toastId)}
          disabled={retrying}
          className="text-xs text-red-700 hover:underline px-2 py-1 disabled:opacity-50"
        >
          Dismiss
        </button>
        <button
          type="button"
          data-testid="send-checklist-retry"
          disabled={retrying}
          aria-busy={retrying || undefined}
          onClick={async () => {
            setRetrying(true);
            try {
              await onRetry();
            } finally {
              setRetrying(false);
            }
          }}
          className="rounded-full bg-red-700 text-white text-xs font-medium px-3 py-1.5 hover:bg-red-800 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {retrying ? 'Retrying…' : 'Retry'}
        </button>
      </div>
    </div>
  );
}
