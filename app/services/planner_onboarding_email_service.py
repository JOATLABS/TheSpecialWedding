from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from bson import ObjectId

from app.core.database import mongo
from app.services.email_service_resend import ResendEmailService

logger = logging.getLogger(__name__)

SEQUENCE_VERSION = 1
FRONTEND_FALLBACK_URL = "https://thespecialwedding.io"
CLAIM_TTL = timedelta(minutes=30)


@dataclass(frozen=True)
class SequenceStep:
    key: str
    offset_days: int
    email_type: str
    sent_field: str
    skipped_field: str
    skip_reason_field: str


SEQUENCE_STEPS = (
    SequenceStep(
        key="first_wedding",
        offset_days=1,
        email_type="planner_onboarding_day1_first_wedding",
        sent_field="first_wedding_sent_at",
        skipped_field="first_wedding_skipped_at",
        skip_reason_field="first_wedding_skip_reason",
    ),
    SequenceStep(
        key="couple_portal",
        offset_days=3,
        email_type="planner_onboarding_day3_couple_portal",
        sent_field="couple_portal_sent_at",
        skipped_field="couple_portal_skipped_at",
        skip_reason_field="couple_portal_skip_reason",
    ),
    SequenceStep(
        key="ai_paperwork",
        offset_days=5,
        email_type="planner_onboarding_day5_ai_paperwork",
        sent_field="ai_paperwork_sent_at",
        skipped_field="ai_paperwork_skipped_at",
        skip_reason_field="ai_paperwork_skip_reason",
    ),
    SequenceStep(
        key="team_rules",
        offset_days=8,
        email_type="planner_onboarding_day8_team_rules",
        sent_field="team_rules_sent_at",
        skipped_field="team_rules_skipped_at",
        skip_reason_field="team_rules_skip_reason",
    ),
    SequenceStep(
        key="planners_love",
        offset_days=12,
        email_type="planner_onboarding_day12_social_proof",
        sent_field="planners_love_sent_at",
        skipped_field="planners_love_skipped_at",
        skip_reason_field="planners_love_skip_reason",
    ),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class PlannerOnboardingEmailService:
    def __init__(self):
        self.users_collection = mongo.get_users_collection()
        self.weddings_collection = mongo.db["weddings"]
        self.team_members_collection = mongo.db["team_members"]
        self.subscriptions_collection = mongo.db["user_subscriptions"]
        self.email_service = ResendEmailService()

    async def start_sequence(self, user_id: str, user: Optional[dict[str, Any]] = None, dry_run: bool = False) -> dict[str, Any]:
        if user is None:
            user = await self.users_collection.find_one({"_id": self._to_object_id(user_id)})

        if not user or user.get("role") != "wedding_planner":
            return {"started": False, "reason": "user_not_eligible"}

        if not user.get("email_verified") or not user.get("is_active"):
            return {"started": False, "reason": "user_not_active"}

        state = self._state(user)
        if state.get("welcome_sent_at"):
            return {"started": False, "reason": "already_started"}

        now = _utc_now()
        if dry_run:
            return {"started": True, "email_type": "planner_onboarding_day0_welcome"}

        claim_token = await self._acquire_claim(user["_id"], "welcome")
        if not claim_token:
            refreshed_user = await self.users_collection.find_one({"_id": user["_id"]}) or user
            if self._state(refreshed_user).get("welcome_sent_at"):
                return {"started": False, "reason": "already_started"}
            return {"started": False, "reason": "sequence_in_progress"}

        refreshed_user = await self.users_collection.find_one({"_id": user["_id"]}) or user
        if self._has_explicit_unsubscribe(refreshed_user):
            await self._release_claim(user["_id"], claim_token)
            return {"started": False, "reason": "unsubscribed"}

        send_result = await self._send_named_email("welcome", refreshed_user)
        if not send_result.get("success"):
            await self._release_claim(user["_id"], claim_token)
            return {"started": False, "reason": "email_failed", "error": send_result.get("error")}

        await self._finalize_claim(
            user["_id"],
            claim_token,
            {
                "status": "active",
                "started_at": state.get("started_at") or now,
                "welcome_sent_at": now,
                "last_processed_at": now,
            },
        )
        return {"started": True, "email_type": "planner_onboarding_day0_welcome"}

    async def process_due_emails(self, dry_run: bool = False) -> dict[str, Any]:
        results = {
            "processed": 0,
            "sent": 0,
            "skipped": 0,
            "completed": 0,
            "exited": 0,
            "errors": 0,
            "details": [],
        }

        cursor = self.users_collection.find(
            {
                "role": "wedding_planner",
                "email_verified": True,
                "is_active": True,
                "planner_onboarding_email.started_at": {"$exists": True},
            }
        )

        async for user in cursor:
            results["processed"] += 1
            try:
                outcome = await self._process_user(user, dry_run=dry_run)
                results["details"].append(outcome)
                results["sent"] += outcome.get("sent", 0)
                results["skipped"] += outcome.get("skipped", 0)
                results["completed"] += 1 if outcome.get("completed") else 0
                results["exited"] += 1 if outcome.get("exited") else 0
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Planner onboarding processing failed for %s: %s", user.get("email"), exc, exc_info=True)
                results["errors"] += 1
                results["details"].append(
                    {
                        "user_id": str(user.get("_id")),
                        "email": user.get("email"),
                        "error": str(exc),
                    }
                )

        return results

    async def _process_user(self, user: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
        now = _utc_now()
        state = self._state(user)
        status = state.get("status", "active")
        result = {
            "user_id": str(user.get("_id")),
            "email": user.get("email"),
            "sent": 0,
            "skipped": 0,
            "completed": False,
            "exited": False,
            "actions": [],
        }

        if status in {"completed", "exited", "reengagement_pending"}:
            result["actions"].append(f"sequence_{status}")
            return result

        if self._has_explicit_unsubscribe(user):
            if not dry_run:
                await self._set_state_fields(
                    user["_id"],
                    {
                        "status": "exited",
                        "completed_at": now,
                        "exit_reason": "explicit_unsubscribe",
                        "last_processed_at": now,
                    },
                )
            result["exited"] = True
            result["completed"] = True
            result["actions"].append("exited_unsubscribed")
            return result

        if await self._should_exit_for_signature(user):
            if not state.get("signature_exit_sent_at"):
                if dry_run:
                    result["actions"].append("would_send_signature_exit")
                    return result

                claim_token = await self._acquire_claim(user["_id"], "signature_exit")
                if not claim_token:
                    result["actions"].append("signature_exit_in_progress")
                    return result

                refreshed_user = await self.users_collection.find_one({"_id": user["_id"]}) or user
                if self._has_explicit_unsubscribe(refreshed_user):
                    await self._release_claim(user["_id"], claim_token)
                    result["actions"].append("signature_exit_aborted_unsubscribed")
                    return result

                send_result = await self._send_named_email("signature_exit", refreshed_user)
                if send_result.get("success"):
                    await self._finalize_claim(
                        user["_id"],
                        claim_token,
                        {
                            "signature_exit_sent_at": now,
                            "status": "exited",
                            "completed_at": now,
                            "exit_reason": "upgraded_to_signature",
                            "last_processed_at": now,
                        },
                    )
                    result["sent"] += 1
                    result["exited"] = True
                    result["completed"] = True
                    result["actions"].append("sent_signature_exit")
                    return result
                await self._release_claim(user["_id"], claim_token)

            result["actions"].append("signature_already_exited")
            return result

        if self._is_inactive(user):
            if not dry_run:
                await self._set_state_fields(
                    user["_id"],
                    {
                        "status": "reengagement_pending",
                        "completed_at": now,
                        "exit_reason": "inactive_14_days",
                        "last_processed_at": now,
                    },
                )
            result["exited"] = True
            result["completed"] = True
            result["actions"].append("flagged_reengagement_pending")
            return result

        started_at = _ensure_utc(state.get("started_at")) or now
        for step in SEQUENCE_STEPS:
            if state.get(step.sent_field) or state.get(step.skipped_field):
                continue
            if now < started_at + timedelta(days=step.offset_days):
                continue

            should_send, skip_reason = await self._evaluate_step(user, step)
            if not should_send:
                if not dry_run:
                    updated = await self._mark_step_skipped_once(
                        user["_id"],
                        step,
                        skipped_at=now,
                        skip_reason=skip_reason or "condition_not_met",
                    )
                    if not updated:
                        result["actions"].append(f"skip_already_recorded_{step.key}")
                        continue
                result["skipped"] += 1
                result["actions"].append(f"skipped_{step.key}:{skip_reason}")
                continue

            if dry_run:
                result["actions"].append(f"would_send_{step.key}")
                continue

            claim_token = await self._acquire_claim(user["_id"], step.key, step=step)
            if not claim_token:
                result["actions"].append(f"step_in_progress_{step.key}")
                continue

            refreshed_user = await self.users_collection.find_one({"_id": user["_id"]}) or user
            if self._has_explicit_unsubscribe(refreshed_user):
                await self._release_claim(user["_id"], claim_token)
                result["actions"].append(f"aborted_unsubscribed_{step.key}")
                continue

            send_result = await self._send_named_email(step.key, refreshed_user)
            if not send_result.get("success"):
                await self._release_claim(user["_id"], claim_token)
                result["actions"].append(f"failed_{step.key}")
                break

            await self._finalize_claim(
                user["_id"],
                claim_token,
                {
                    step.sent_field: now,
                    "last_processed_at": now,
                },
            )
            result["sent"] += 1
            result["actions"].append(f"sent_{step.key}")

        refreshed_state = self._state(await self.users_collection.find_one({"_id": user["_id"]}) or user)
        if all(
            refreshed_state.get(step.sent_field) or refreshed_state.get(step.skipped_field)
            for step in SEQUENCE_STEPS
        ):
            if not dry_run and refreshed_state.get("status") != "completed":
                await self._set_state_fields(
                    user["_id"],
                    {
                        "status": "completed",
                        "completed_at": now,
                        "last_processed_at": now,
                    },
                )
            result["completed"] = True
            result["actions"].append("sequence_completed")

        return result

    async def _evaluate_step(self, user: dict[str, Any], step: SequenceStep) -> tuple[bool, Optional[str]]:
        if step.key == "first_wedding":
            if await self._has_created_wedding(user):
                return False, "wedding_already_created"
            return True, None

        if step.key == "team_rules":
            if await self._has_team_members(user):
                return False, "team_members_already_exist"
            return True, None

        return True, None

    async def _has_created_wedding(self, user: dict[str, Any]) -> bool:
        user_id = str(user.get("_id"))
        planner_email = str(user.get("email") or "").strip().lower()
        query: dict[str, Any] = {"assigned_planner_id": user_id}
        if planner_email:
            query = {"$or": [query, {"assigned_planner_email": planner_email}]}
        return await self.weddings_collection.count_documents(query) > 0

    async def _has_team_members(self, user: dict[str, Any]) -> bool:
        user_id = str(user.get("_id"))
        return await self.team_members_collection.count_documents(
            {
                "owner_id": user_id,
                "status": {"$in": ["pending", "active"]},
            }
        ) > 0

    async def _should_exit_for_signature(self, user: dict[str, Any]) -> bool:
        user_id = str(user.get("_id"))
        user_email = str(user.get("email") or "").strip().lower()
        subscription = await self.subscriptions_collection.find_one(
            {
                "$or": [{"user_id": user_id}, {"user_email": user_email}],
                "status": {"$in": ["active", "trial"]},
            }
        )
        if not subscription:
            plan_id = str(user.get("plan_id") or "").lower()
            return "signature" in plan_id

        plan_name = str((subscription.get("plan_snapshot") or {}).get("plan_name") or "").lower()
        plan_id = str(subscription.get("plan_id") or "").lower()
        return "signature" in plan_name or "signature" in plan_id

    def _has_explicit_unsubscribe(self, user: dict[str, Any]) -> bool:
        state = self._state(user)
        if state.get("unsubscribed_at") is not None:
            return True

        explicit_false_flags = (
            user.get("email_opt_in"),
            user.get("marketing_emails"),
            user.get("marketing_email_opt_in"),
        )
        if any(flag is False for flag in explicit_false_flags):
            return True

        explicit_date_fields = (
            user.get("email_unsubscribed_at"),
            user.get("marketing_email_unsubscribed_at"),
        )
        return any(value is not None for value in explicit_date_fields)

    def _is_inactive(self, user: dict[str, Any]) -> bool:
        anchors = [
            _ensure_utc(user.get("last_login")),
            _ensure_utc(user.get("verified_at")),
            _ensure_utc(user.get("created_at")),
        ]
        most_recent = max((anchor for anchor in anchors if anchor is not None), default=None)
        if most_recent is None:
            return False
        return _utc_now() - most_recent >= timedelta(days=14)

    async def _set_state_fields(self, user_id: Any, fields: dict[str, Any]) -> None:
        updates = {f"planner_onboarding_email.{key}": value for key, value in fields.items()}
        updates["planner_onboarding_email.sequence_version"] = SEQUENCE_VERSION
        await self.users_collection.update_one({"_id": user_id}, {"$set": updates})

    async def _acquire_claim(self, user_id: Any, claim_step: str, step: Optional[SequenceStep] = None) -> Optional[str]:
        claim_token = secrets.token_urlsafe(12)
        now = _utc_now()
        stale_before = now - CLAIM_TTL
        query: dict[str, Any] = {
            "_id": user_id,
            "$or": [
                {"planner_onboarding_email.current_claimed_at": {"$exists": False}},
                {"planner_onboarding_email.current_claimed_at": {"$lt": stale_before}},
            ],
        }
        if step is None:
            query["planner_onboarding_email.welcome_sent_at"] = {"$exists": False}
        else:
            query[f"planner_onboarding_email.{step.sent_field}"] = {"$exists": False}
            query[f"planner_onboarding_email.{step.skipped_field}"] = {"$exists": False}

        result = await self.users_collection.update_one(
            query,
            {
                "$set": {
                    "planner_onboarding_email.sequence_version": SEQUENCE_VERSION,
                    "planner_onboarding_email.current_claim_token": claim_token,
                    "planner_onboarding_email.current_claim_step": claim_step,
                    "planner_onboarding_email.current_claimed_at": now,
                }
            },
        )
        if result.modified_count != 1:
            return None
        return claim_token

    async def _release_claim(self, user_id: Any, claim_token: str) -> None:
        await self.users_collection.update_one(
            {
                "_id": user_id,
                "planner_onboarding_email.current_claim_token": claim_token,
            },
            {
                "$unset": {
                    "planner_onboarding_email.current_claim_token": "",
                    "planner_onboarding_email.current_claim_step": "",
                    "planner_onboarding_email.current_claimed_at": "",
                }
            },
        )

    async def _finalize_claim(self, user_id: Any, claim_token: str, fields: dict[str, Any]) -> None:
        updates = {f"planner_onboarding_email.{key}": value for key, value in fields.items()}
        updates["planner_onboarding_email.sequence_version"] = SEQUENCE_VERSION
        await self.users_collection.update_one(
            {
                "_id": user_id,
                "planner_onboarding_email.current_claim_token": claim_token,
            },
            {
                "$set": updates,
                "$unset": {
                    "planner_onboarding_email.current_claim_token": "",
                    "planner_onboarding_email.current_claim_step": "",
                    "planner_onboarding_email.current_claimed_at": "",
                },
            },
        )

    async def _mark_step_skipped_once(
        self,
        user_id: Any,
        step: SequenceStep,
        *,
        skipped_at: datetime,
        skip_reason: str,
    ) -> bool:
        result = await self.users_collection.update_one(
            {
                "_id": user_id,
                f"planner_onboarding_email.{step.sent_field}": {"$exists": False},
                f"planner_onboarding_email.{step.skipped_field}": {"$exists": False},
            },
            {
                "$set": {
                    f"planner_onboarding_email.{step.skipped_field}": skipped_at,
                    f"planner_onboarding_email.{step.skip_reason_field}": skip_reason,
                    "planner_onboarding_email.last_processed_at": skipped_at,
                    "planner_onboarding_email.sequence_version": SEQUENCE_VERSION,
                }
            },
        )
        return result.modified_count == 1

    def _state(self, user: dict[str, Any]) -> dict[str, Any]:
        return user.get("planner_onboarding_email") or {}

    def _to_object_id(self, value: str) -> Any:
        return ObjectId(value) if ObjectId.is_valid(value) else value

    def _frontend_url(self) -> str:
        return (os.getenv("FRONTEND_URL") or FRONTEND_FALLBACK_URL).rstrip("/")

    def _display_name(self, user: dict[str, Any]) -> str:
        first_name = (user.get("first_name") or "").strip()
        if first_name:
            return first_name
        email = user.get("email", "planner")
        return str(email).split("@")[0].replace(".", " ").title()

    def _mask_email(self, email: str) -> str:
        local_part, _, domain = email.partition("@")
        if not domain:
            return email
        if len(local_part) <= 2:
            masked_local = f"{local_part[:1]}*"
        else:
            masked_local = f"{local_part[:1]}{'*' * max(len(local_part) - 2, 1)}{local_part[-1]}"
        return f"{masked_local}@{domain}"

    def _role_label(self, user: dict[str, Any]) -> str:
        return str(user.get("role", "wedding_planner")).replace("_", " ").title()

    def _unsubscribe_url(self, token: str) -> str:
        return f"{self._frontend_url()}/unsubscribe/planner-onboarding?token={token}"

    async def _ensure_unsubscribe_token(self, user: dict[str, Any]) -> str:
        state = self._state(user)
        existing_token = state.get("unsubscribe_token")
        if existing_token:
            return existing_token

        generated_token = secrets.token_urlsafe(24)
        result = await self.users_collection.update_one(
            {
                "_id": user["_id"],
                "planner_onboarding_email.unsubscribe_token": {"$exists": False},
            },
            {
                "$set": {
                    "planner_onboarding_email.unsubscribe_token": generated_token,
                    "planner_onboarding_email.sequence_version": SEQUENCE_VERSION,
                }
            },
        )
        if result.modified_count == 1:
            return generated_token

        refreshed_user = await self.users_collection.find_one(
            {"_id": user["_id"]},
            {"planner_onboarding_email.unsubscribe_token": 1},
        )
        refreshed_token = self._state(refreshed_user or {}).get("unsubscribe_token")
        return refreshed_token or generated_token

    async def get_unsubscribe_status(self, token: str) -> Optional[dict[str, Any]]:
        user = await self.users_collection.find_one(
            {
                "role": "wedding_planner",
                "planner_onboarding_email.unsubscribe_token": token,
            },
            {
                "email": 1,
                "first_name": 1,
                "planner_onboarding_email": 1,
            },
        )
        if not user:
            return None

        state = self._state(user)
        unsubscribed_at = state.get("unsubscribed_at")
        return {
            "email": self._mask_email(str(user.get("email") or "")),
            "first_name": (user.get("first_name") or "").strip() or None,
            "already_unsubscribed": unsubscribed_at is not None,
            "unsubscribed_at": unsubscribed_at,
        }

    async def unsubscribe_by_token(self, token: str) -> Optional[dict[str, Any]]:
        user = await self.users_collection.find_one(
            {
                "role": "wedding_planner",
                "planner_onboarding_email.unsubscribe_token": token,
            },
            {
                "email": 1,
                "first_name": 1,
                "planner_onboarding_email": 1,
            },
        )
        if not user:
            return None

        state = self._state(user)
        now = _utc_now()
        unsubscribed_at = state.get("unsubscribed_at")

        if unsubscribed_at is None:
            await self.users_collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "planner_onboarding_email.unsubscribed_at": now,
                        "planner_onboarding_email.status": "exited",
                        "planner_onboarding_email.completed_at": state.get("completed_at") or now,
                        "planner_onboarding_email.exit_reason": "explicit_unsubscribe",
                        "planner_onboarding_email.last_processed_at": now,
                        "planner_onboarding_email.sequence_version": SEQUENCE_VERSION,
                    },
                    "$unset": {
                        "planner_onboarding_email.current_claim_token": "",
                        "planner_onboarding_email.current_claim_step": "",
                        "planner_onboarding_email.current_claimed_at": "",
                    },
                },
            )
            unsubscribed_at = now

        return {
            "email": self._mask_email(str(user.get("email") or "")),
            "first_name": (user.get("first_name") or "").strip() or None,
            "already_unsubscribed": True,
            "unsubscribed_at": unsubscribed_at,
        }

    async def _send_named_email(self, template_key: str, user: dict[str, Any]) -> dict[str, Any]:
        unsubscribe_token = await self._ensure_unsubscribe_token(user)
        subject, html_content = self._render_email(
            template_key,
            user,
            unsubscribe_url=self._unsubscribe_url(unsubscribe_token),
        )
        return await self.email_service.send_email(
            to_email=user["email"],
            subject=subject,
            html_content=html_content,
            from_name="The Special Wedding Team",
            email_type=self._email_type(template_key),
        )

    def _email_type(self, template_key: str) -> str:
        if template_key == "welcome":
            return "planner_onboarding_day0_welcome"
        if template_key == "signature_exit":
            return "planner_onboarding_signature_exit"
        return next(step.email_type for step in SEQUENCE_STEPS if step.key == template_key)

    def _render_email(self, template_key: str, user: dict[str, Any], *, unsubscribe_url: Optional[str] = None) -> tuple[str, str]:
        if template_key == "welcome":
            return self._welcome_email(user, unsubscribe_url=unsubscribe_url)
        if template_key == "first_wedding":
            return self._first_wedding_email(user, unsubscribe_url=unsubscribe_url)
        if template_key == "couple_portal":
            return self._couple_portal_email(user, unsubscribe_url=unsubscribe_url)
        if template_key == "ai_paperwork":
            return self._ai_paperwork_email(user, unsubscribe_url=unsubscribe_url)
        if template_key == "team_rules":
            return self._team_rules_email(user, unsubscribe_url=unsubscribe_url)
        if template_key == "planners_love":
            return self._planners_love_email(user, unsubscribe_url=unsubscribe_url)
        if template_key == "signature_exit":
            return self._signature_exit_email(user, unsubscribe_url=unsubscribe_url)
        raise ValueError(f"Unknown onboarding template: {template_key}")

    def _email_wrapper(self, *, title: str, eyebrow: str, intro: str, body_html: str, cta_label: str, cta_path: str, outro: str, unsubscribe_url: Optional[str]) -> str:
        cta_url = f"{self._frontend_url()}{cta_path}"
        unsubscribe_html = (
            f'<p style="margin-top:16px;">If you want to stop this onboarding sequence, <a href="{unsubscribe_url}" style="color:#475569;">unsubscribe here</a>.</p>'
            if unsubscribe_url
            else ""
        )
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8fafc; color: #1f2937; margin: 0; padding: 24px; }}
            .container {{ max-width: 640px; margin: 0 auto; background: white; border-radius: 22px; overflow: hidden; border: 1px solid #e5e7eb; }}
            .header {{ background: linear-gradient(135deg, #0b1120, #1e293b); color: white; padding: 38px 32px; }}
            .eyebrow {{ display: inline-block; font-size: 12px; letter-spacing: 0.24em; text-transform: uppercase; color: #e8c46a; margin-bottom: 14px; }}
            .content {{ padding: 32px; line-height: 1.7; }}
            .card {{ background: #f8fafc; border-left: 4px solid #c8847e; border-radius: 0 14px 14px 0; padding: 20px; margin: 24px 0; }}
            .card ul {{ margin: 0; padding-left: 20px; }}
            .button {{ display: inline-block; margin: 24px 0; background: #c8847e; color: white; text-decoration: none; padding: 14px 24px; border-radius: 999px; font-weight: 600; }}
            .footer {{ padding: 24px 32px 32px; color: #64748b; font-size: 14px; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <div class="eyebrow">{eyebrow}</div>
              <h1 style="margin:0;font-size:32px;line-height:1.15;">{title}</h1>
            </div>
            <div class="content">
              <p>{intro}</p>
              {body_html}
              <a class="button" href="{cta_url}">{cta_label}</a>
              <p>{outro}</p>
            </div>
            <div class="footer">
              Reply to this email if you want help from our team. We read every message.
              {unsubscribe_html}
            </div>
          </div>
        </body>
        </html>
        """

    def _welcome_email(self, user: dict[str, Any], *, unsubscribe_url: Optional[str]) -> tuple[str, str]:
        subject = "Welcome to The Special Wedding — your 18-tool command center"
        intro = f"Hi {self._display_name(user)}, welcome to <strong>The Special Wedding</strong>. Your account is live and you now have access to the planner workspace."
        body_html = f"""
        <div class="card">
          <p><strong>What you can do right now:</strong></p>
          <ul>
            <li><strong>Guest Management</strong> for lists, RSVPs, households, and dietary notes</li>
            <li><strong>Couple Portal</strong> for timeline, payments, inbox, and memories</li>
            <li><strong>AI Contracts</strong> plus e-sign support in the Contract Canvas flow</li>
            <li><strong>SMS &amp; Email Reminders</strong> with delivery tracking and fallback handling</li>
            <li><strong>Seating, budget, payments, vendor CRM, and forms</strong> in one workspace</li>
          </ul>
        </div>
        <p>As a <strong>{self._role_label(user)}</strong>{f' at <strong>{user.get("company_name")}</strong>' if user.get("company_name") else ''}, you have the tools you need to run weddings from one system.</p>
        """
        outro = "Tomorrow we will focus on the fastest activation step: creating your first wedding."
        return subject, self._email_wrapper(
            title="Your planner workspace is ready",
            eyebrow="Day 0 • Welcome",
            intro=intro,
            body_html=body_html,
            cta_label="Go to your dashboard",
            cta_path="/admin",
            outro=outro,
            unsubscribe_url=unsubscribe_url,
        )

    def _first_wedding_email(self, user: dict[str, Any], *, unsubscribe_url: Optional[str]) -> tuple[str, str]:
        subject = "Your first wedding in 5 minutes"
        intro = f"Hi {self._display_name(user)}, the fastest way to see the product come alive is to create your first wedding project."
        body_html = """
        <div class="card">
          <ul>
            <li><strong>Step 1:</strong> create a new wedding</li>
            <li><strong>Step 2:</strong> add the couple, date, and venue</li>
            <li><strong>Step 3:</strong> set branding and planning defaults</li>
            <li><strong>Step 4:</strong> import guests or start from scratch</li>
          </ul>
        </div>
        <p>Once you have one wedding in the system, the dashboard, RSVP health, budget tracking, and execution views all have real data to work with.</p>
        """
        outro = "If you already created a wedding, this step is skipped automatically."
        return subject, self._email_wrapper(
            title="Create your first wedding",
            eyebrow="Day 1 • Activation",
            intro=intro,
            body_html=body_html,
            cta_label="Create your first wedding",
            cta_path="/admin/weddings",
            outro=outro,
            unsubscribe_url=unsubscribe_url,
        )

    def _couple_portal_email(self, user: dict[str, Any], *, unsubscribe_url: Optional[str]) -> tuple[str, str]:
        subject = "Meet your couple portal"
        intro = f"Hi {self._display_name(user)}, one of the clearest differentiators in the platform is the <strong>Couple Portal</strong> attached to each wedding."
        body_html = """
        <div class="card">
          <ul>
            <li>Timeline and milestone visibility for the couple</li>
            <li>Payments, invoices, and assigned forms in one place</li>
            <li>A shared inbox so updates stay tied to the wedding</li>
            <li>Memories, registry, and FAQs without another app to manage</li>
          </ul>
        </div>
        <p>The portal reduces scattered text threads and email follow-up because the wedding workspace becomes the source of truth.</p>
        """
        return subject, self._email_wrapper(
            title="The feature couples remember",
            eyebrow="Day 3 • Couple Portal",
            intro=intro,
            body_html=body_html,
            cta_label="Open your wedding workspace",
            cta_path="/admin/weddings",
            outro="You do not need a separate portal product or a custom client dashboard to start using it.",
            unsubscribe_url=unsubscribe_url,
        )

    def _ai_paperwork_email(self, user: dict[str, Any], *, unsubscribe_url: Optional[str]) -> tuple[str, str]:
        subject = "Let AI handle the paperwork"
        intro = f"Hi {self._display_name(user)}, the AI layer in The Special Wedding is built to cut repetitive work without taking control away from you."
        body_html = """
        <div class="card">
          <ul>
            <li><strong>Contract Canvas</strong> for clause suggestions and cleaner contract drafting</li>
            <li><strong>Service Packages</strong> with AI pricing guidance</li>
            <li><strong>Reminder drafting</strong> for RSVP follow-ups in different tones</li>
            <li><strong>Budget and payment forecasting</strong> for earlier risk visibility</li>
          </ul>
        </div>
        <p>Every AI-generated draft is still reviewed by the planner before it is sent or finalized.</p>
        """
        return subject, self._email_wrapper(
            title="Use AI where the admin work stacks up",
            eyebrow="Day 5 • AI workflows",
            intro=intro,
            body_html=body_html,
            cta_label="Open Contract Canvas",
            cta_path="/admin/vendors",
            outro="If you want the fastest proof of value, start with a contract or a package draft.",
            unsubscribe_url=unsubscribe_url,
        )

    def _team_rules_email(self, user: dict[str, Any], *, unsubscribe_url: Optional[str]) -> tuple[str, str]:
        subject = "Your team, your rules"
        intro = f"Hi {self._display_name(user)}, if you collaborate with coordinators or assistants, the planner team workspace lets you keep access clean instead of sharing one login."
        body_html = """
        <div class="card">
          <ul>
            <li>Invite planners, coordinators, or assistants</li>
            <li>Assign access to specific weddings or all weddings</li>
            <li>Control granular permissions instead of using one blanket role</li>
            <li>Keep an activity trail on what changed and who touched it</li>
          </ul>
        </div>
        """
        return subject, self._email_wrapper(
            title="Bring your team in without losing control",
            eyebrow="Day 8 • Team management",
            intro=intro,
            body_html=body_html,
            cta_label="Invite a team member",
            cta_path="/admin/planner/team",
            outro="This email is skipped automatically if your workspace already has team members attached.",
            unsubscribe_url=unsubscribe_url,
        )

    def _planners_love_email(self, user: dict[str, Any], *, unsubscribe_url: Optional[str]) -> tuple[str, str]:
        subject = "You're all set — here's what planners love most"
        intro = f"Hi {self._display_name(user)}, after the first two weeks most planners settle into one rhythm: fewer disconnected tools and fewer status checks spread across inboxes and spreadsheets."
        body_html = """
        <div class="card">
          <p><em>“I replaced multiple disconnected planner tools with one login, and the couple portal changed how client communication feels.”</em></p>
          <p style="margin-top:16px;"><em>“The AI contract and reminder flows save time every single week because the first draft is already in the system.”</em></p>
        </div>
        <p>If you are still on a lower tier, compare the Signature plan against what you are doing manually today and decide whether the extra workflow depth pays for itself.</p>
        """
        return subject, self._email_wrapper(
            title="What planners keep using after onboarding",
            eyebrow="Day 12 • Social proof",
            intro=intro,
            body_html=body_html,
            cta_label="Explore Signature plan",
            cta_path="/admin/planner/billing",
            outro="If Boutique already covers your workflow, keep building. The point is to make the trade-off visible, not to force an upgrade.",
            unsubscribe_url=unsubscribe_url,
        )

    def _signature_exit_email(self, user: dict[str, Any], *, unsubscribe_url: Optional[str]) -> tuple[str, str]:
        subject = "Welcome to Signature — your full planner stack is unlocked"
        intro = f"Hi {self._display_name(user)}, your workspace is now on the <strong>Signature</strong> tier."
        body_html = """
        <div class="card">
          <ul>
            <li>AI contract generation and deeper automation workflows</li>
            <li>Service Packages, vendor CRM, and advanced permissions</li>
            <li>Expanded planner operations without stitching together extra tools</li>
          </ul>
        </div>
        """
        return subject, self._email_wrapper(
            title="Signature is active",
            eyebrow="Upgrade exit",
            intro=intro,
            body_html=body_html,
            cta_label="Open your billing workspace",
            cta_path="/admin/planner/billing",
            outro="The standard onboarding sequence stops here so you do not keep getting starter nudges after the upgrade.",
            unsubscribe_url=unsubscribe_url,
        )


planner_onboarding_email_service = PlannerOnboardingEmailService()
