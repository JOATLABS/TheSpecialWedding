"""Deliver couple meeting invites as email plus ICS attachments."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any, Optional

from icalendar import Calendar, Event  # type: ignore[import-untyped]
from pymongo import ReturnDocument

from app.core.config import settings
from app.core.database import mongo
from app.models.meeting_invite import MeetingInviteDeliveryStatus
from app.services.calendar_audit_service import calendar_audit_service
from app.services.email_service_resend import ResendEmailService


class MeetingInviteService:
    """Send couple meeting invites and track invite status."""

    def __init__(self):
        self.invites_collection = mongo.get_meeting_invites_collection()
        self.weddings_collection = mongo.get_weddings_collection()

    def _build_ics_uid(self, task: dict[str, Any]) -> str:
        return f"{task.get('_id')}@thespecialwedding.io"

    def _build_couple_meetings_url(self, frontend_url: str) -> str:
        base_url = frontend_url.rstrip("/")
        return f"{base_url}/couple/dashboard?section=meetings"

    def _build_ics_attachment(
        self,
        task: dict[str, Any],
        wedding: Optional[dict[str, Any]],
        *,
        method: str = "REQUEST",
    ) -> dict[str, Any]:
        calendar = Calendar()
        calendar.add("prodid", "-//The Special Wedding//Shared Planner Calendar//EN")
        calendar.add("version", "2.0")
        calendar.add("method", method)

        event = Event()
        uid = self._build_ics_uid(task)
        task_updated_at = task.get("updated_at")
        sequence = (
            int(task_updated_at.timestamp())
            if isinstance(task_updated_at, datetime)
            else 0
        )
        event.add("uid", uid)
        event.add("summary", task.get("title"))
        if task.get("description"):
            event.add("description", task.get("description"))
        event.add("dtstamp", datetime.now(UTC))
        event.add("sequence", sequence)
        if method == "CANCEL":
            event.add("status", "CANCELLED")
        if task.get("start_date"):
            event.add("dtstart", task["start_date"])
        if task.get("end_date"):
            event.add("dtend", task["end_date"])
        elif task.get("start_date"):
            event.add("dtend", task["start_date"])
        if task.get("conference_url"):
            event.add("location", task["conference_url"])
        if wedding and wedding.get("couple_names"):
            event.add("categories", [wedding.get("couple_names")])
        calendar.add_component(event)

        encoded = base64.b64encode(calendar.to_ical()).decode("utf-8")
        return {
            "uid": uid,
            "attachment": {
                "filename": "meeting-invite.ics",
                "content": encoded,
            },
        }

    def _build_email_content(
        self,
        task: dict[str, Any],
        *,
        couple_meetings_url: str,
        method: str,
    ) -> tuple[str, str]:
        title = task.get("title") or "Planner meeting"
        description = (
            task.get("description") or "A planner meeting has been scheduled for you."
        )
        when_text = task.get("start_date")
        ends_text = task.get("end_date")

        if method == "CANCEL":
            subject = f"Meeting cancelled: {title}"
            html = f"""
                <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #1f2937;">
                  <h2 style="margin-bottom: 12px;">{title}</h2>
                  <p>This meeting has been cancelled.</p>
                  <p><strong>Originally scheduled:</strong> {when_text}</p>
                  <p><strong>Portal:</strong> <a href="{couple_meetings_url}">View your meetings</a></p>
                  <p>An updated ICS calendar file is attached so your calendar can remove the meeting.</p>
                </div>
            """
            return subject, html

        subject = f"Meeting invitation: {title}"
        html = f"""
            <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #1f2937;">
              <h2 style="margin-bottom: 12px;">{title}</h2>
              <p>{description}</p>
              <p><strong>When:</strong> {when_text}</p>
              <p><strong>Ends:</strong> {ends_text}</p>
              <p><strong>Portal:</strong> <a href="{couple_meetings_url}">View your meetings</a></p>
              <p>An ICS calendar file is attached so you can add or update this meeting in your calendar.</p>
            </div>
        """
        return subject, html

    async def _upsert_invite_record(
        self,
        *,
        task: dict[str, Any],
        recipient_email: str,
        wedding_id: Optional[str],
        uid: str,
        delivery_mode: str,
        now: datetime,
    ) -> Optional[str]:
        stored_invite = await self.invites_collection.find_one_and_update(
            {"task_id": str(task["_id"]), "recipient_email": recipient_email},
            {
                "$set": {
                    "task_id": str(task["_id"]),
                    "wedding_id": str(wedding_id) if wedding_id is not None else None,
                    "owner_planner_id": task.get("owner_planner_id"),
                    "owner_planner_email": task.get("owner_planner_email")
                    or task.get("planner_email"),
                    "recipient_email": recipient_email,
                    "recipient_name": None,
                    "delivery_mode": delivery_mode,
                    "delivery_status": MeetingInviteDeliveryStatus.QUEUED.value,
                    "response_status": "pending",
                    "ics_uid": uid,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if not stored_invite:
            return None
        return str(stored_invite["_id"])

    async def _send_ics_email(
        self,
        task: dict[str, Any],
        *,
        method: str = "REQUEST",
        recipient_emails: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Send ICS-backed email notifications for one meeting."""
        recipient_emails = recipient_emails or task.get("couple_attendee_emails", [])
        if not recipient_emails:
            return []

        wedding = None
        wedding_id = task.get("wedding_id")
        if wedding_id:
            wedding = await self.weddings_collection.find_one({"_id": wedding_id})

        frontend_url = (
            settings.FRONTEND_URL
            or settings.GOOGLE_APP_PUBLIC_HOME_URL
            or "https://thespecialwedding.io"
        )
        couple_meetings_url = self._build_couple_meetings_url(frontend_url)
        email_service = ResendEmailService()
        ics_payload = self._build_ics_attachment(task, wedding, method=method)
        sent_results: list[dict[str, Any]] = []
        now = datetime.now(UTC)

        for recipient_email in recipient_emails:
            invite_id = await self._upsert_invite_record(
                task=task,
                recipient_email=recipient_email,
                wedding_id=wedding_id,
                uid=ics_payload["uid"],
                delivery_mode=task.get("invite_delivery_mode") or "email_ics",
                now=now,
            )

            subject, html = self._build_email_content(
                task,
                couple_meetings_url=couple_meetings_url,
                method=method,
            )
            send_result = await email_service.send_email(
                to_email=recipient_email,
                subject=subject,
                html_content=html,
                attachments=[ics_payload["attachment"]],
                wedding_id=str(wedding_id) if wedding_id else None,
                email_type="meeting_invite",
            )

            update_doc = {
                "delivery_status": (
                    (
                        MeetingInviteDeliveryStatus.CANCELLED.value
                        if method == "CANCEL"
                        else MeetingInviteDeliveryStatus.SENT.value
                    )
                    if send_result.get("success")
                    else MeetingInviteDeliveryStatus.FAILED.value
                ),
                "last_sent_at": now if send_result.get("success") else None,
                "message_id": send_result.get("id"),
                "last_error": send_result.get("error"),
                "updated_at": datetime.now(UTC),
            }
            await self.invites_collection.update_one(
                {"task_id": str(task["_id"]), "recipient_email": recipient_email},
                {"$set": update_doc},
            )
            if send_result.get("success"):
                await calendar_audit_service.log(
                    action=(
                        "calendar_invite_cancelled"
                        if method == "CANCEL"
                        else "calendar_invite_sent"
                    ),
                    message=(
                        f"Cancelled meeting invite for {recipient_email}"
                        if method == "CANCEL"
                        else f"Sent meeting invite to {recipient_email}"
                    ),
                    owner_planner_email=task.get("owner_planner_email")
                    or task.get("planner_email"),
                    actor_email=task.get("created_by_email")
                    or task.get("owner_planner_email")
                    or task.get("planner_email"),
                    wedding_id=str(wedding_id) if wedding_id else None,
                    metadata={
                        "task_id": str(task.get("_id")),
                        "recipient_email": recipient_email,
                        "delivery_mode": task.get("invite_delivery_mode")
                        or "email_ics",
                        "method": method,
                    },
                )
            sent_results.append(
                {
                    "invite_id": invite_id,
                    "recipient_email": recipient_email,
                    "success": send_result.get("success", False),
                    "message_id": send_result.get("id"),
                    "error": send_result.get("error"),
                }
            )

        return sent_results

    async def queue_invites(
        self,
        task: dict[str, Any],
        *,
        method: str = "REQUEST",
        recipient_emails: Optional[list[str]] = None,
        source: str = "planner",
    ) -> list[dict[str, Any]]:
        """Mark invite recipients as queued before background delivery.

        ``source`` is "planner" for planner-initiated meetings and "couple"
        for couple-initiated bookings; carried through to invite metadata so
        downstream messaging templates can adjust wording.
        """
        recipient_emails = recipient_emails or task.get("couple_attendee_emails", [])
        if not recipient_emails:
            return []

        wedding_id = task.get("wedding_id")
        now = datetime.now(UTC)
        uid = self._build_ics_uid(task)
        queued_rows: list[dict[str, Any]] = []
        for recipient_email in recipient_emails:
            invite_id = await self._upsert_invite_record(
                task=task,
                recipient_email=recipient_email,
                wedding_id=wedding_id,
                uid=uid,
                delivery_mode=task.get("invite_delivery_mode") or "email_ics",
                now=now,
            )
            queued_rows.append(
                {
                    "invite_id": invite_id,
                    "recipient_email": recipient_email,
                    "success": True,
                    "status": "queued",
                    "method": method,
                    "source": source,
                }
            )
        return queued_rows

    async def send_invites(
        self, task: dict[str, Any], *, recipient_emails: Optional[list[str]] = None
    ) -> list[dict[str, Any]]:
        """Send or resend email plus ICS invites to couple attendees for one meeting."""
        return await self._send_ics_email(
            task,
            method="REQUEST",
            recipient_emails=recipient_emails,
        )

    async def send_cancellations(
        self, task: dict[str, Any], *, recipient_emails: Optional[list[str]] = None
    ) -> list[dict[str, Any]]:
        """Send ICS cancellations so couple-side calendars remove the meeting."""
        return await self._send_ics_email(
            task,
            method="CANCEL",
            recipient_emails=recipient_emails,
        )


meeting_invite_service = MeetingInviteService()
