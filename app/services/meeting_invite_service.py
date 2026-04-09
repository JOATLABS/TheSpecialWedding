"""Deliver couple meeting invites as email plus ICS attachments."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any, Optional

from icalendar import Calendar, Event  # type: ignore[import-untyped]

from app.core.config import settings
from app.core.database import mongo
from app.models.meeting_invite import MeetingInviteDeliveryStatus
from app.services.email_service_resend import ResendEmailService


class MeetingInviteService:
    """Send couple meeting invites and track invite status."""

    def __init__(self):
        self.invites_collection = mongo.get_meeting_invites_collection()
        self.weddings_collection = mongo.get_weddings_collection()

    def _build_ics_uid(self, task: dict[str, Any]) -> str:
        return f"{task.get('_id')}@thespecialwedding.io"

    def _build_ics_attachment(
        self, task: dict[str, Any], wedding: Optional[dict[str, Any]]
    ) -> dict[str, Any]:
        calendar = Calendar()
        calendar.add("prodid", "-//The Special Wedding//Shared Planner Calendar//EN")
        calendar.add("version", "2.0")
        calendar.add("method", "REQUEST")

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

    async def send_invites(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        """Send email plus ICS invites to couple attendees for one meeting."""
        recipient_emails = task.get("couple_attendee_emails", [])
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
        email_service = ResendEmailService()
        ics_payload = self._build_ics_attachment(task, wedding)
        sent_results: list[dict[str, Any]] = []
        now = datetime.now(UTC)

        for recipient_email in recipient_emails:
            invite_doc = {
                "task_id": str(task["_id"]),
                "wedding_id": str(wedding_id),
                "owner_planner_id": task.get("owner_planner_id"),
                "owner_planner_email": task.get("owner_planner_email")
                or task.get("planner_email"),
                "recipient_email": recipient_email,
                "recipient_name": None,
                "delivery_mode": task.get("invite_delivery_mode") or "email_ics",
                "delivery_status": MeetingInviteDeliveryStatus.QUEUED.value,
                "response_status": "pending",
                "ics_uid": ics_payload["uid"],
                "updated_at": now,
            }
            await self.invites_collection.update_one(
                {"task_id": str(task["_id"]), "recipient_email": recipient_email},
                {"$set": invite_doc, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
            stored_invite = await self.invites_collection.find_one(
                {"task_id": str(task["_id"]), "recipient_email": recipient_email}
            )
            invite_id = str(stored_invite["_id"]) if stored_invite else None

            subject = f"Meeting invitation: {task.get('title')}"
            html = f"""
                <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #1f2937;">
                  <h2 style="margin-bottom: 12px;">{task.get("title")}</h2>
                  <p>{task.get("description") or "A planner meeting has been scheduled for you."}</p>
                  <p><strong>When:</strong> {task.get("start_date")}</p>
                  <p><strong>Ends:</strong> {task.get("end_date")}</p>
                  <p><strong>Portal:</strong> <a href="{frontend_url}/couple/portal/meetings">View your meetings</a></p>
                  <p>An ICS calendar file is attached so you can add this meeting to your calendar.</p>
                </div>
            """
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
                    MeetingInviteDeliveryStatus.SENT.value
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


meeting_invite_service = MeetingInviteService()
