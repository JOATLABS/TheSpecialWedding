"""
Team Management Service

Handles all business logic for the planner's team management feature:
invite, accept, update, deactivate, reactivate, remove team members,
seat limit enforcement, and permission resolution.
"""

import secrets
import string
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from bson import ObjectId
from fastapi import HTTPException, status

from app.core.database import mongo
from app.utils.auth_utils import get_password_hash
from app.services.email_service_resend import ResendEmailService
from app.services.activity_log_service import activity_log_service
from app.models.team_member import (
    TeamMemberRole,
    TeamMemberStatus,
    WeddingAccessType,
    TeamPermissions,
    ROLE_PRESETS,
)

logger = logging.getLogger(__name__)

# How long an invite token stays valid
INVITE_TOKEN_EXPIRY_DAYS = 7


class TeamManagementService:
    def __init__(self):
        self.team_collection = mongo.db["team_members"]
        self.users_collection = mongo.get_users_collection()
        self.plans_collection = mongo.db["subscription_plans"]
        self.subscriptions_collection = mongo.db["user_subscriptions"]
        self.weddings_collection = mongo.db["weddings"]
        self.email_service = ResendEmailService()

    # ─── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _generate_token(length: int = 48) -> str:
        """Generate a cryptographically secure URL-safe token"""
        return "".join(
            secrets.choice(string.ascii_letters + string.digits)
            for _ in range(length)
        )

    @staticmethod
    def _resolve_permissions(
        role: str, custom_permissions: Optional[Dict[str, bool]] = None
    ) -> Dict[str, bool]:
        """
        Merge role preset with any custom permission overrides.
        Custom permissions take precedence over the preset.
        """
        base = dict(ROLE_PRESETS.get(role, ROLE_PRESETS["viewer"]))
        if custom_permissions:
            for key, value in custom_permissions.items():
                if key in base:
                    base[key] = value
        return base

    async def _get_owner_plan(self, owner_email: str) -> Optional[dict]:
        """Get the owner planner's current subscription plan (with staff_seats)"""
        # Find subscription
        subscription = await self.subscriptions_collection.find_one(
            {"user_email": owner_email, "status": {"$in": ["active", "trial", "trialing"]}}
        )
        if not subscription:
            # Fallback: lookup by user_id
            user = await self.users_collection.find_one({"email": owner_email})
            if user:
                subscription = await self.subscriptions_collection.find_one(
                    {"user_id": str(user["_id"]), "status": {"$in": ["active", "trial", "trialing"]}}
                )
        if not subscription:
            return None

        # Use plan snapshot if available (grandfathering), otherwise live plan
        plan_snapshot = subscription.get("plan_snapshot")
        if plan_snapshot and "staff_seats" in plan_snapshot:
            return plan_snapshot

        plan = await self.plans_collection.find_one({"_id": subscription.get("plan_id")})
        return plan

    def _format_team_member(self, doc: dict) -> dict:
        """Convert a raw MongoDB team_members doc to a safe response dict"""
        return {
            "id": str(doc["_id"]),
            "owner_id": doc.get("owner_id", ""),
            "email": doc.get("email", ""),
            "first_name": doc.get("first_name"),
            "last_name": doc.get("last_name"),
            "status": doc.get("status", "pending"),
            "role": doc.get("role", "viewer"),
            "custom_permissions": doc.get("custom_permissions", {}),
            "wedding_access": doc.get("wedding_access", "all"),
            "assigned_wedding_ids": doc.get("assigned_wedding_ids", []),
            "invited_at": doc.get("invited_at"),
            "accepted_at": doc.get("accepted_at"),
            "deactivated_at": doc.get("deactivated_at"),
            "last_active_at": doc.get("last_active_at"),
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at"),
        }

    # ─── Seat Enforcement ─────────────────────────────────────────────────

    async def check_seat_limit(self, owner_id: str, owner_email: str) -> Dict[str, Any]:
        """
        Check seat usage against the plan limit.
        Returns seat info and whether a new invite is allowed.
        """
        plan = await self._get_owner_plan(owner_email)
        total_seats = plan.get("staff_seats", 0) if plan else 0

        # Count non-removed members (pending + active count toward seats)
        used_seats = await self.team_collection.count_documents({
            "owner_id": owner_id,
            "status": {"$in": ["pending", "active"]},
        })

        return {
            "total_seats": total_seats,
            "used_seats": used_seats,
            "available_seats": max(0, total_seats - used_seats),
            "can_invite": used_seats < total_seats,
        }

    async def get_seats_info(self, owner_id: str, owner_email: str) -> Dict[str, Any]:
        """Get detailed seat usage for the UI"""
        seat_check = await self.check_seat_limit(owner_id, owner_email)

        # Count by status
        pipeline = [
            {"$match": {"owner_id": owner_id}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        status_counts: Dict[str, int] = {}
        async for doc in self.team_collection.aggregate(pipeline):
            status_counts[doc["_id"]] = doc["count"]

        return {
            "total_seats": seat_check["total_seats"],
            "used_seats": seat_check["used_seats"],
            "available_seats": seat_check["available_seats"],
            "members_by_status": status_counts,
        }

    # ─── Invite ───────────────────────────────────────────────────────────

    async def invite_team_member(
        self,
        owner_id: str,
        owner_email: str,
        email: str,
        role: str,
        custom_permissions: Optional[Dict[str, bool]] = None,
        wedding_access: str = "all",
        assigned_wedding_ids: Optional[List[str]] = None,
    ) -> dict:
        """
        Invite a new team member. Creates a team_members doc and sends an email.
        """
        email = email.strip().lower()

        # 1. Seat limit check
        seat_info = await self.check_seat_limit(owner_id, owner_email)
        if not seat_info["can_invite"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "seat_limit_reached",
                    "message": f"Your plan allows {seat_info['total_seats']} team members. All seats are currently filled.",
                    "total_seats": seat_info["total_seats"],
                    "used_seats": seat_info["used_seats"],
                    "upgrade_required": True,
                },
            )

        # 2. Duplicate check
        existing = await self.team_collection.find_one(
            {"owner_id": owner_id, "email": email}
        )
        if existing:
            existing_status = existing.get("status")
            if existing_status == "deactivated":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "member_deactivated",
                        "message": "This person was previously deactivated. Reactivate them instead of sending a new invite.",
                        "team_member_id": str(existing["_id"]),
                    },
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "already_invited",
                    "message": f"A team member with email {email} already exists.",
                    "status": existing_status,
                },
            )

        # 3. Cannot invite yourself
        if email == owner_email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot invite yourself as a team member.",
            )

        # 4. Validate assigned weddings belong to the planner
        if wedding_access == "assigned" and assigned_wedding_ids:
            for wid in assigned_wedding_ids:
                wedding = await self.weddings_collection.find_one({"_id": ObjectId(wid)})
                if not wedding or wedding.get("assigned_planner_email") != owner_email:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Wedding {wid} not found or does not belong to you.",
                    )

        # 5. Resolve permissions
        resolved_perms = self._resolve_permissions(role, custom_permissions)

        # 6. Generate invite token
        token = self._generate_token()
        now = datetime.now(timezone.utc)

        doc = {
            "owner_id": owner_id,
            "owner_email": owner_email,
            "user_id": None,
            "email": email,
            "first_name": None,
            "last_name": None,
            "status": TeamMemberStatus.PENDING.value,
            "role": role,
            "custom_permissions": resolved_perms,
            "wedding_access": wedding_access,
            "assigned_wedding_ids": assigned_wedding_ids or [],
            "invite_token": token,
            "invite_token_expires_at": now + timedelta(days=INVITE_TOKEN_EXPIRY_DAYS),
            "invited_at": now,
            "accepted_at": None,
            "last_active_at": None,
            "created_at": now,
            "updated_at": now,
            "deactivated_at": None,
        }

        result = await self.team_collection.insert_one(doc)
        doc["_id"] = result.inserted_id

        # 7. Send invitation email
        try:
            await self._send_invite_email(
                to_email=email,
                owner_email=owner_email,
                role=role,
                permissions=resolved_perms,
                token=token,
            )
        except Exception as e:
            logger.error(f"Failed to send team invite email to {email}: {e}")
            # Don't fail the invite — the planner can resend later

        logger.info(f"Team member invited: {email} by {owner_email} as {role}")

        # Log activity
        try:
            await activity_log_service.log_team_member_invited(
                planner_email=owner_email, member_email=email, role=role, invited_by=owner_email
            )
        except Exception as log_err:
            logger.warning(f"Failed to log team invite activity: {log_err}")

        return self._format_team_member(doc)

    async def _send_invite_email(
        self,
        to_email: str,
        owner_email: str,
        role: str,
        permissions: Dict[str, bool],
        token: str,
    ):
        """Send the team invitation email via Resend"""
        # Look up planner info for the email
        owner = await self.users_collection.find_one({"email": owner_email})
        company_name = (owner or {}).get("company_name", "A wedding planner")
        planner_name = ""
        if owner:
            fn = owner.get("first_name", "")
            ln = owner.get("last_name", "")
            planner_name = f"{fn} {ln}".strip()

        base_url = os.getenv("FRONTEND_URL", "https://thespecialwedding.io")
        accept_url = f"{base_url}/admin/team/accept?token={token}"

        # Build permissions list for the email
        enabled_perms = [
            k.replace("_", " ").title()
            for k, v in permissions.items()
            if v
        ]
        perms_html = "".join(
            f'<span style="display:inline-block;background:#f0f4f8;padding:4px 10px;border-radius:6px;'
            f'font-size:13px;margin:3px 4px 3px 0;color:#475569;">{p}</span>'
            for p in enabled_perms
        )

        subject = f"You're invited to join {company_name} on TheSpecialWedding"
        html = f"""
        <div style="font-family:Inter,system-ui,sans-serif;max-width:560px;margin:0 auto;color:#1e293b;">
            <div style="text-align:center;padding:32px 0 16px;">
                <span style="font-family:Georgia,serif;font-size:22px;color:#D4A5A5;font-weight:700;">
                    TheSpecialWedding
                </span>
            </div>
            <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;padding:32px;">
                <h2 style="margin:0 0 8px;font-size:20px;">You've been invited!</h2>
                <p style="color:#64748b;margin:0 0 24px;">
                    <strong>{company_name}</strong>{f' ({planner_name})' if planner_name else ''}
                    has invited you to join their team as <strong>{role.title()}</strong>.
                </p>
                <div style="background:#f8fafc;border-radius:10px;padding:16px;margin-bottom:24px;">
                    <div style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">
                        Your Permissions
                    </div>
                    <div>{perms_html if perms_html else '<span style="color:#94a3b8;">View Only</span>'}</div>
                </div>
                <a href="{accept_url}"
                   style="display:block;text-align:center;background:#D4A5A5;color:#ffffff;
                          padding:14px 24px;border-radius:10px;text-decoration:none;
                          font-weight:600;font-size:15px;">
                    Accept Invitation
                </a>
                <p style="color:#94a3b8;font-size:12px;text-align:center;margin:16px 0 0;">
                    This invitation expires in {INVITE_TOKEN_EXPIRY_DAYS} days.
                </p>
            </div>
        </div>
        """

        await self.email_service.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html,
            from_name="TheSpecialWedding",
            email_type="team_invite",
        )

    # ─── Resend Invite ────────────────────────────────────────────────────

    async def resend_invite(self, owner_id: str, team_member_id: str) -> dict:
        """Regenerate token and resend the invitation email"""
        doc = await self.team_collection.find_one({
            "_id": ObjectId(team_member_id),
            "owner_id": owner_id,
        })
        if not doc:
            raise HTTPException(status_code=404, detail="Team member not found")
        if doc["status"] != TeamMemberStatus.PENDING.value:
            raise HTTPException(
                status_code=400,
                detail="Can only resend invites for pending members"
            )

        # Generate new token
        new_token = self._generate_token()
        now = datetime.now(timezone.utc)
        await self.team_collection.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "invite_token": new_token,
                    "invite_token_expires_at": now + timedelta(days=INVITE_TOKEN_EXPIRY_DAYS),
                    "updated_at": now,
                }
            },
        )

        # Resend email
        await self._send_invite_email(
            to_email=doc["email"],
            owner_email=doc["owner_email"],
            role=doc["role"],
            permissions=doc.get("custom_permissions", {}),
            token=new_token,
        )

        logger.info(f"Team invite resent to {doc['email']} by owner {owner_id}")
        doc["invite_token"] = new_token
        doc["updated_at"] = now
        return self._format_team_member(doc)

    # ─── Accept Invite ────────────────────────────────────────────────────

    async def get_invite_info(self, token: str) -> dict:
        """
        Public endpoint: get invite details for the accept page.
        Does NOT require auth.
        """
        doc = await self.team_collection.find_one({"invite_token": token})
        if not doc:
            raise HTTPException(status_code=404, detail="Invitation not found or already used")

        is_expired = (
            doc.get("invite_token_expires_at")
            and datetime.now(timezone.utc) > doc["invite_token_expires_at"].replace(tzinfo=timezone.utc)
            if isinstance(doc.get("invite_token_expires_at"), datetime)
            and doc["invite_token_expires_at"].tzinfo is None
            else (
                doc.get("invite_token_expires_at")
                and datetime.now(timezone.utc) > doc["invite_token_expires_at"]
            )
        )

        # Lookup planner company info
        owner = await self.users_collection.find_one({"email": doc.get("owner_email")})
        company_name = (owner or {}).get("company_name")
        planner_name = None
        if owner:
            fn = owner.get("first_name", "")
            ln = owner.get("last_name", "")
            planner_name = f"{fn} {ln}".strip() or None

        return {
            "email": doc["email"],
            "role": doc["role"],
            "permissions": doc.get("custom_permissions", {}),
            "company_name": company_name,
            "planner_name": planner_name,
            "is_expired": bool(is_expired),
        }

    async def accept_invite(
        self, token: str, first_name: str, last_name: str, password: str
    ) -> dict:
        """
        Public endpoint: accept an invitation, create a user account,
        and activate the team member.
        """
        doc = await self.team_collection.find_one({"invite_token": token})
        if not doc:
            raise HTTPException(status_code=404, detail="Invitation not found or already used")

        if doc["status"] != TeamMemberStatus.PENDING.value:
            raise HTTPException(status_code=400, detail="This invitation has already been accepted")

        # Check token expiry
        expires_at = doc.get("invite_token_expires_at")
        if expires_at:
            if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                raise HTTPException(
                    status_code=400,
                    detail="This invitation has expired. Please ask your team admin to resend it."
                )

        # Check if email already has an account
        existing_user = await self.users_collection.find_one({"email": doc["email"]})
        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists. Please contact the team admin."
            )

        now = datetime.now(timezone.utc)

        # Create user in users collection
        user_doc = {
            "email": doc["email"],
            "password_hash": get_password_hash(password),
            "role": "team_member",
            "parent_planner_id": doc["owner_id"],
            "team_member_id": str(doc["_id"]),
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "company_name": None,
            "plan_id": None,
            "subscription_status": "active",  # team members don't have their own subscription
            "trial_end_date": None,
            "max_weddings": 0,
            "ai_credits_remaining": 0,
            "is_active": True,
            "email_verified": True,  # invited members are pre-verified
            "created_at": now,
            "updated_at": now,
        }

        user_result = await self.users_collection.insert_one(user_doc)
        new_user_id = str(user_result.inserted_id)

        # Update team_members doc
        await self.team_collection.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "user_id": new_user_id,
                    "first_name": first_name.strip(),
                    "last_name": last_name.strip(),
                    "status": TeamMemberStatus.ACTIVE.value,
                    "accepted_at": now,
                    "invite_token": None,  # Consume the token
                    "invite_token_expires_at": None,
                    "updated_at": now,
                }
            },
        )

        logger.info(
            f"Team invite accepted: {doc['email']} joined owner {doc['owner_id']} "
            f"as {doc['role']}"
        )

        # Log activity
        try:
            owner = await self.users_collection.find_one({"_id": ObjectId(doc["owner_id"])})
            owner_email = owner.get("email", "") if owner else ""
            await activity_log_service.log_team_member_accepted(
                planner_email=owner_email,
                member_email=doc["email"],
                member_name=f"{first_name} {last_name}",
            )
        except Exception as log_err:
            logger.warning(f"Failed to log team accept activity: {log_err}")

        return {"success": True, "message": "Invitation accepted. You can now log in."}

    # ─── List / Get ───────────────────────────────────────────────────────

    async def list_team_members(self, owner_id: str) -> List[dict]:
        """List all team members for a planner"""
        cursor = self.team_collection.find({"owner_id": owner_id}).sort("created_at", -1)
        results = []
        async for doc in cursor:
            results.append(self._format_team_member(doc))
        return results

    async def get_team_member(self, owner_id: str, team_member_id: str) -> dict:
        """Get a single team member by ID"""
        doc = await self.team_collection.find_one({
            "_id": ObjectId(team_member_id),
            "owner_id": owner_id,
        })
        if not doc:
            raise HTTPException(status_code=404, detail="Team member not found")
        return self._format_team_member(doc)

    # ─── Update ───────────────────────────────────────────────────────────

    async def update_team_member(
        self,
        owner_id: str,
        team_member_id: str,
        updates: dict,
    ) -> dict:
        """
        Update a team member's role, permissions, or wedding access.
        If role changes, permissions reset to the new role's preset
        (unless custom_permissions are also provided).
        """
        doc = await self.team_collection.find_one({
            "_id": ObjectId(team_member_id),
            "owner_id": owner_id,
        })
        if not doc:
            raise HTTPException(status_code=404, detail="Team member not found")

        set_fields: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}

        # Handle role change
        new_role = updates.get("role")
        custom_perms = updates.get("custom_permissions")
        if new_role and new_role != doc["role"]:
            set_fields["role"] = new_role
            # Reset to preset, then apply any custom overrides
            set_fields["custom_permissions"] = self._resolve_permissions(
                new_role, custom_perms
            )
        elif custom_perms:
            # Just update permissions without changing role
            set_fields["custom_permissions"] = self._resolve_permissions(
                doc["role"], custom_perms
            )

        # Handle wedding access change
        new_access = updates.get("wedding_access")
        if new_access:
            set_fields["wedding_access"] = new_access
            if new_access == "all":
                set_fields["assigned_wedding_ids"] = []
            elif "assigned_wedding_ids" in updates:
                set_fields["assigned_wedding_ids"] = updates["assigned_wedding_ids"]

        if "assigned_wedding_ids" in updates and "wedding_access" not in set_fields:
            set_fields["assigned_wedding_ids"] = updates["assigned_wedding_ids"]

        await self.team_collection.update_one(
            {"_id": doc["_id"]},
            {"$set": set_fields},
        )

        updated = await self.team_collection.find_one({"_id": doc["_id"]})
        logger.info(f"Team member {team_member_id} updated by owner {owner_id}")
        return self._format_team_member(updated)

    # ─── Deactivate / Reactivate / Remove ─────────────────────────────────

    async def deactivate_team_member(self, owner_id: str, team_member_id: str) -> dict:
        """Soft-deactivate a team member (they can no longer log in)"""
        doc = await self.team_collection.find_one({
            "_id": ObjectId(team_member_id),
            "owner_id": owner_id,
        })
        if not doc:
            raise HTTPException(status_code=404, detail="Team member not found")
        if doc["status"] == TeamMemberStatus.DEACTIVATED.value:
            raise HTTPException(status_code=400, detail="Member is already deactivated")

        now = datetime.now(timezone.utc)
        await self.team_collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"status": TeamMemberStatus.DEACTIVATED.value, "deactivated_at": now, "updated_at": now}},
        )

        # Also deactivate the user account so JWT checks reject them
        if doc.get("user_id"):
            await self.users_collection.update_one(
                {"_id": ObjectId(doc["user_id"])},
                {"$set": {"is_active": False, "updated_at": now}},
            )

        logger.info(f"Team member {team_member_id} deactivated by owner {owner_id}")

        try:
            owner = await self.users_collection.find_one({"_id": ObjectId(owner_id)})
            await activity_log_service.log_team_member_deactivated(
                planner_email=owner.get("email", "") if owner else "",
                member_email=doc["email"],
                deactivated_by=owner.get("email", "") if owner else "",
            )
        except Exception as log_err:
            logger.warning(f"Failed to log team deactivation activity: {log_err}")

        doc["status"] = TeamMemberStatus.DEACTIVATED.value
        doc["deactivated_at"] = now
        return self._format_team_member(doc)

    async def reactivate_team_member(self, owner_id: str, owner_email: str, team_member_id: str) -> dict:
        """Reactivate a previously deactivated team member"""
        doc = await self.team_collection.find_one({
            "_id": ObjectId(team_member_id),
            "owner_id": owner_id,
        })
        if not doc:
            raise HTTPException(status_code=404, detail="Team member not found")
        if doc["status"] != TeamMemberStatus.DEACTIVATED.value:
            raise HTTPException(status_code=400, detail="Member is not deactivated")

        # Check seat limit — reactivation uses a seat
        seat_info = await self.check_seat_limit(owner_id, owner_email)
        if not seat_info["can_invite"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "seat_limit_reached",
                    "message": "Cannot reactivate — all seats are filled. Upgrade your plan or remove another member first.",
                    "upgrade_required": True,
                },
            )

        now = datetime.now(timezone.utc)
        await self.team_collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"status": TeamMemberStatus.ACTIVE.value, "deactivated_at": None, "updated_at": now}},
        )

        # Re-enable the user account
        if doc.get("user_id"):
            await self.users_collection.update_one(
                {"_id": ObjectId(doc["user_id"])},
                {"$set": {"is_active": True, "updated_at": now}},
            )

        logger.info(f"Team member {team_member_id} reactivated by owner {owner_id}")

        try:
            await activity_log_service.log_team_member_reactivated(
                planner_email=owner_email,
                member_email=doc["email"],
                reactivated_by=owner_email,
            )
        except Exception as log_err:
            logger.warning(f"Failed to log team reactivation activity: {log_err}")

        doc["status"] = TeamMemberStatus.ACTIVE.value
        doc["deactivated_at"] = None
        return self._format_team_member(doc)

    async def remove_team_member(self, owner_id: str, team_member_id: str) -> dict:
        """
        Permanently remove a team member.
        For pending members: just delete the team_members doc.
        For accepted members: also deactivate (not delete) the user account
        to preserve activity log references.
        """
        doc = await self.team_collection.find_one({
            "_id": ObjectId(team_member_id),
            "owner_id": owner_id,
        })
        if not doc:
            raise HTTPException(status_code=404, detail="Team member not found")

        # If they have a user account, deactivate it (don't hard delete to keep audit trail)
        if doc.get("user_id"):
            await self.users_collection.update_one(
                {"_id": ObjectId(doc["user_id"])},
                {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}},
            )

        # Delete the team_members doc
        await self.team_collection.delete_one({"_id": doc["_id"]})

        logger.info(f"Team member {team_member_id} ({doc['email']}) removed by owner {owner_id}")

        try:
            owner = await self.users_collection.find_one({"_id": ObjectId(owner_id)})
            await activity_log_service.log_team_member_removed(
                planner_email=owner.get("email", "") if owner else "",
                member_email=doc["email"],
                removed_by=owner.get("email", "") if owner else "",
            )
        except Exception as log_err:
            logger.warning(f"Failed to log team removal activity: {log_err}")

        return {"success": True, "message": f"Team member {doc['email']} has been removed."}

    # ─── Permission Resolution (used by auth middleware) ──────────────────

    async def get_member_permissions(self, user_id: str) -> Optional[dict]:
        """
        Load the team_members doc for a given user_id.
        Returns None if the user is not a team member.
        Called by auth middleware on every request from a team_member.
        """
        doc = await self.team_collection.find_one({
            "user_id": user_id,
            "status": TeamMemberStatus.ACTIVE.value,
        })
        if not doc:
            return None

        return {
            "team_member_id": str(doc["_id"]),
            "owner_id": doc["owner_id"],
            "owner_email": doc.get("owner_email", ""),
            "role": doc["role"],
            "permissions": doc.get("custom_permissions", {}),
            "wedding_access": doc.get("wedding_access", "all"),
            "assigned_wedding_ids": doc.get("assigned_wedding_ids", []),
        }
