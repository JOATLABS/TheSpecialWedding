# RSVP Delivery System — Code Review Report

**Reviewer:** Claude (Automated Code Review)
**Date:** February 28, 2026
**Branch:** `feature-twilio-otp-improvement-final-submitted`
**Scope:** SMS (Twilio/Telnyx) and Email (Resend) invitation & reminder delivery pipeline

---

## Dimension Ratings

| Dimension       | Rating     | Notes |
|-----------------|------------|-------|
| Security        | Good       | Webhook signature validation present, auth guards on all admin routes, IP-based rate limiting on errors |
| Performance     | Acceptable | Rate-limiting sleep on email sends, but `time.sleep()` blocks the event loop in one path |
| **Correctness** | **Needs Work** | Multiple gaps in failure handling, silent skips, missing delivery tracking on one endpoint |
| Maintainability | Acceptable | Clear separation of services, but SMS and Email pipelines share no abstractions for skip/fail reporting |

---

## Positive Observations

Before cataloging issues, the codebase has several things working well:

1. **Webhook signature validation** — `_validate_twilio_signature()` in `twilio_webhooks.py` uses Twilio's `RequestValidator` with proper environment-awareness (strict in production, permissive in dev).

2. **STOP/START/HELP handling** — The incoming message handler at `twilio_webhooks.py:295-317` correctly processes opt-out keywords, updates `sms_opt_in` on the guest record, and sends confirmation replies. This is TCPA-compliant.

3. **Delivery event history** — The `delivery_events` array on reminder log records gives a full timeline of each message's journey (queued → sent → delivered or failed), not just a latest-status snapshot.

4. **Planner-scoped data access** — Both `reminder_twilio.py` and `email_reminders.py` filter logs by `assigned_planner_email`, preventing planners from seeing other weddings' data.

5. **Platform health dashboard** — `admin_platform_metrics.py` aggregates Twilio delivery stats (delivery rate, status breakdown) and presents them alongside system health. The infrastructure for monitoring exists.

6. **Frontend guest reach indicators** — The reminders page computes and displays `guestsWithPhone`, `guestsWithEmail`, and `guestsWithPhoneOrEmail` counts, giving planners some pre-send awareness.

7. **OTP fallback precedent** — `otp_service.py` already implements SMS→Email fallback for verification codes, proving the pattern is feasible in this codebase.

---

## Verified Issues

### CRITICAL — Fix Before Sending RSVPs

#### Issue 2.1 — Individual SMS sends have NO delivery tracking

**File:** `app/api/reminder_twilio.py:157-170`
**Verified:** YES — Confirmed in source code.

The `send-to-guests` endpoint's `twilio_client.messages.create()` calls omit `status_callback`. The log record written at lines 190-200 also lacks `message_sid`, `delivery_status`, and `delivery_events` fields.

Compare with `reminder_service_twilio.py:268-274` which correctly includes `status_callback=status_callback_url` and records `message_sid`.

```python
# BROKEN (reminder_twilio.py:159-163)
message = twilio_client.messages.create(
    messaging_service_sid=MESSAGING_SERVICE_SID,
    body=payload.message,
    to=phone
    # ← NO status_callback
)

# CORRECT (reminder_service_twilio.py:270-274)
twilio_message = self.client.messages.create(
    messaging_service_sid=self.messaging_service_sid,
    body=message,
    to=phone,
    status_callback=status_callback_url  # ← present
)
```

**Impact:** Any SMS sent through the "Send to Selected Guests" button in the planner UI will show "success" (Twilio accepted it) but the planner will never learn whether it actually reached the recipient's phone. This is the endpoint planners will use most for targeted follow-ups.

**Fix:** Add `status_callback` to both `messages.create()` calls (lines 159 and 166), and populate `message_sid`, `delivery_status`, and `delivery_events` in the log record.

---

#### Issue 2.2 + 3.5 — Planners have zero proactive notification of delivery failures

**Files:** `app/api/twilio_webhooks.py:100-156`, `app/admin/reminders/page.tsx`
**Verified:** YES — The webhook handler updates the DB and returns. No planner notification is created.

The `planner_notification` model (in `app/models/planner_notification.py`) has types for `FORM_SUBMISSION`, `RSVP_UPDATE`, `GUEST_MESSAGE`, `PAYMENT_RECEIVED`, `PAYMENT_FAILED`, `CONTRACT_SIGNED`, `VENDOR_RESPONSE`, `REMINDER`, `SYSTEM`, and `SUPPORT_TICKET_RESPONSE` — but **no type for delivery failures**.

A planner must manually navigate to Admin → Reminders → Message History and visually scan for red badges. For a wedding with 100+ guests, this is impractical.

**Impact:** If 15 out of 100 RSVP invitation texts fail to deliver, the planner will not know unless they go looking. Those 15 guests will never receive their RSVP link.

**Fix:** When the webhook receives a `failed` or `undelivered` status, create a `planner_notification` record (add a new `DELIVERY_FAILURE` type) and optionally send an email summary to the planner.

---

#### Issue 2.3 + 3.4 — ROOT_ADMIN is blind to account-level SMS failures

**Files:** `app/api/twilio_webhooks.py:100-156`, `app/api/admin_platform_metrics.py:244-376`
**Verified:** YES — The webhook handler treats error codes 30002 (account suspended) and 21408 (permission denied) identically to all other errors: write to DB and return.

The platform metrics endpoint calculates delivery health status but it is pull-based — nobody is notified when the status transitions from healthy to degraded/unhealthy. The `ErrorHandlerMiddleware` email alerts only trigger for unhandled Python exceptions, not for Twilio business-logic failures which are handled gracefully by the webhook.

**Impact:** If the Twilio account gets suspended or runs out of credit, ALL SMS sending silently fails. The ROOT_ADMIN will only discover this by manually checking the dashboard — potentially hours or days later.

**Fix:** In the webhook handler, check if the error code is in an "account-level" set (30002, 21408, 30010). If so, write to the `errors` collection with severity `critical` and send an email alert to ROOT_ADMIN using the existing `_send_alert_email` pattern from `error_handler.py`.

---

### HIGH PRIORITY — Fix Before Marketing Launch

#### Issue 1.1 + 2.6 — Bulk SMS invites silently skip guests without phone numbers

**File:** `app/services/reminder_service_twilio.py:241`
**Verified:** YES — `if not token or not phone: continue` with no counter or logging.

The response at line 324-328 returns `{"sent": X, "failed": Y}` but skipped guests appear in neither count.

**Fix:** Add a `skipped_count` (and optionally `skipped_reasons` list) to the return value. Log each skip with the reason (no phone, no token, opted out).

#### Issue 1.3 — Email invites silently skip guests without email

**File:** `app/services/email_service_resend.py:148`
**Verified:** YES — `if not email: continue` with no counter.

Same pattern as 1.1. The response at line 203 returns `{"sent": X, "failed": Y}` with no skip count.

**Fix:** Same as 1.1 — add `skipped` count to the response.

#### Issue 1.5 — No identification of completely unreachable guests

**Verified:** YES — No method across SMS or Email services reports which guests have neither a phone number nor an email address. The frontend does compute `guestsWithPhoneOrEmail` but does not highlight the inverse (guests with neither).

**Fix:** Add a count/list of unreachable guests to bulk send responses, and display a warning in the frontend when unreachable guests exist.

#### Issue 3.1 — All Twilio failures treated identically

**File:** `app/api/twilio_webhooks.py:100-156`
**Verified:** YES — The handler writes error_code and error_message but takes no differentiated action. The 14 mapped error codes all result in the same behavior.

**Fix:** Categorize errors and take appropriate action:
- **Temporary** (30001, 30008, 30009): Queue for retry
- **Permanent recipient** (21211, 21612, 21614, 30003, 30005, 30006): Flag phone as invalid
- **Account-level** (30002, 21408, 30010): Alert ROOT_ADMIN immediately
- **Compliance** (21610, 30004, 30007): Set `sms_opt_in = False`

#### Issue 3.2 — Guest phone not flagged on permanent failure

**File:** `app/api/twilio_webhooks.py`, `app/models/guest.py`
**Verified:** YES — The guest model has no `phone_verified` or `phone_invalid` field. When error 21612 ("not a valid phone number") comes in, the error is logged but the guest record is untouched. The planner will keep trying to send to an invalid number.

**Fix:** Add a `phone_status` field to the guest model (values: `unknown`, `valid`, `invalid`, `landline`). Update it when permanent recipient errors arrive.

#### Issue 3.3 — Compliance error 21610 does not update opt-in status

**File:** `app/api/twilio_webhooks.py`
**Verified:** YES — The STOP keyword handler at lines 295-317 correctly sets `sms_opt_in = False`, but when Twilio returns error code 21610 ("attempt to send to unsubscribed recipient") via the status callback, `sms_opt_in` is not updated. The system may attempt to send to this number again.

**Fix:** In the webhook handler, when `error_code == 21610`, update the guest's `sms_opt_in` to `False`.

---

### MEDIUM PRIORITY — Improve Before Scale

#### Issue 1.2 — Bulk event reminders silently skip no-phone guests

**File:** `app/services/reminder_service_twilio.py:67`
**Verified:** YES — `if phone and sms_opt_in:` only sends if both are true. The response at line 103 returns `{"sent": len(logs)}` with no breakdown.

Same pattern as 1.1.

#### Issue 1.4 — No cross-channel fallback between SMS and Email

**Verified:** YES — SMS and Email are entirely independent pipelines. The "Send Both" button fires two separate API calls. The only cross-channel fallback in the entire codebase exists in `otp_service.py` for verification codes.

**Note:** The frontend does show reach counts, which gives partial awareness. Implementing automatic fallback would be valuable but is a larger architectural change.

#### Issue 2.4 — No automatic retry for temporary failures

**File:** `app/api/twilio_webhooks.py`
**Verified:** YES — When Twilio reports a temporary failure (30001, 30008), the message is marked as failed and abandoned.

**Fix:** For temporary error codes, schedule a retry (e.g., using a simple delayed task or a retry queue). Start with a single retry after 60 seconds.

#### Issue 2.5 — No email fallback when SMS fails for guests with both channels

**Verified:** YES — When an SMS fails (either at send time or via webhook), there is no logic to check for an email address and attempt delivery via email.

#### Issue 2.7 — Email delivery events not surfaced to planners

**File:** `app/admin/reminders/page.tsx`
**Verified:** PARTIALLY INCORRECT — The frontend Message History tab actually does fetch and display both SMS and email logs combined (it calls both `/admin/reminders/logs` and `/admin/email/logs` and merges them). However, email logs from the `email_events` collection (Resend webhook events like bounces, opens, clicks) are stored but not exposed through any planner-facing UI.

#### Issue 3.6 — No "Report Delivery Issue" action from the UI

**Verified:** YES — The Message History tab shows status badges but no actionable button to report or escalate a delivery issue.

#### Issue 3.7 — No delivery summary notification after bulk sends

**Verified:** YES — The bulk send API response is shown in the browser but not persisted as a planner notification. If the planner navigates away, the summary is lost.

---

## Additional Issues Found During Review

### PERF-1 — Blocking `time.sleep()` in async email reminder path

**File:** `app/services/email_service_resend.py:288, 352`
**Severity:** Medium

The `send_reminders()` method uses `time.sleep(0.6)` (synchronous) instead of `await asyncio.sleep(0.6)`. This blocks the entire event loop for 600ms per email. For 100 guests, that's 60 seconds of blocked I/O.

Compare with `send_rsvp_invitations()` at line 201 which correctly uses `await asyncio.sleep(0.6)`.

**Fix:** Change `time.sleep(0.6)` to `await asyncio.sleep(0.6)` at lines 288 and 352.

### PERF-2 — N+1 query pattern in SMS reminder sending

**File:** `app/services/reminder_service_twilio.py:61-77`
**Severity:** Low

The `send_reminders()` method iterates all guests and performs a separate `find_one` RSVP lookup per guest. For 200 guests, that's 200 individual DB queries.

**Fix:** Pre-fetch all RSVPs for the wedding in a single query and build a lookup dictionary.

### SEC-1 — Webhook signature validation bypassed in development

**File:** `app/api/twilio_webhooks.py:172-183`
**Severity:** Low (dev only)

When `TWILIO_AUTH_TOKEN` is not set or signature is missing in non-production environments, the validator returns `True`. This is acceptable for development but should be documented. Ensure the Coolify deployment has `ENVIRONMENT=production` set.

### CORR-1 — Missing `await` on async service calls in API routes

**File:** `app/api/reminder_twilio.py:62, 71-73`
**Severity:** Medium

The `send_reminder_twilio` endpoint (line 52-62) is a sync function (`def`) that calls `twilio_reminder_service.send_reminders()` which is an async method. Similarly, `send_invites_twilio` (line 65-74) is sync but calls `send_personalized_rsvp_links()` which is async.

These will return coroutine objects instead of actual results unless FastAPI handles them specially.

**Fix:** Change these endpoint functions from `def` to `async def` and add `await` to the service calls.

---

## Prioritized Fix Order for Wedding Launch

Given that RSVPs are about to be sent out on `thespecialwedding.io/emmanuel-peace`, here is the recommended fix order:

### Phase 1 — Before Sending RSVPs (Days 1-2)

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| P0 | **2.1** — Add `status_callback` to individual sends | 30 min | Delivery tracking works for all SMS |
| P0 | **CORR-1** — Fix missing `await` on async service calls | 15 min | Prevents potential silent failures |
| P0 | **PERF-1** — Fix blocking `time.sleep()` | 5 min | Prevents event loop blocking |
| P1 | **1.1 + 2.6** — Report skip counts in bulk send responses | 1 hr | Planner knows who wasn't reached |
| P1 | **1.3** — Report skip counts in email sends | 30 min | Same for email |
| P1 | **1.5** — Surface unreachable guest count | 1 hr | Planner can take manual action |

### Phase 2 — First Week After RSVP Send (Days 3-7)

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| P1 | **2.2 + 3.5** — Planner notification on delivery failure | 3 hrs | Planner discovers failures proactively |
| P1 | **3.3** — Update opt-in on 21610 compliance error | 30 min | Prevents sending to unsubscribed |
| P1 | **3.4 + 2.3** — ROOT_ADMIN alert on account-level errors | 2 hrs | You know immediately if Twilio breaks |
| P2 | **3.1** — Error categorization in webhook handler | 2 hrs | Foundation for all error-specific handling |
| P2 | **3.2** — Flag invalid phone numbers | 1 hr | Stop wasting sends on bad numbers |

### Phase 3 — Before Marketing Launch (Week 2+)

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| P2 | **2.4** — Automatic retry for temporary failures | 4 hrs | Recovers messages lost to transient issues |
| P2 | **2.5** — Email fallback when SMS fails | 4 hrs | Cross-channel resilience |
| P3 | **3.6** — "Report Issue" button in UI | 2 hrs | Better planner support workflow |
| P3 | **3.7** — Bulk send summary notification | 2 hrs | Persistent record of send results |
| P3 | **1.4** — Cross-channel fallback architecture | 8+ hrs | Full multi-channel delivery intelligence |

---

## Key Files Reference

| File | Role |
|------|------|
| `app/services/reminder_service_twilio.py` | Bulk SMS send logic (invites + event reminders) |
| `app/api/reminder_twilio.py` | SMS API routes including individual sends |
| `app/api/twilio_webhooks.py` | Delivery status webhooks + incoming messages |
| `app/services/email_service_resend.py` | Email send logic (invites + reminders) |
| `app/api/email_reminders.py` | Email API routes |
| `app/admin/reminders/page.tsx` | Planner UI for sending and viewing history |
| `app/models/guest.py` | Guest data model |
| `app/models/planner_notification.py` | Notification types (needs DELIVERY_FAILURE) |
| `app/api/admin_platform_metrics.py` | ROOT_ADMIN monitoring dashboard |
| `app/middleware/error_handler.py` | Error alerting infrastructure |
| `app/core/sms_config.py` | SMS provider configuration |
| `app/services/otp_service.py` | Has SMS→Email fallback (reference pattern) |

---

*Generated: February 28, 2026*
