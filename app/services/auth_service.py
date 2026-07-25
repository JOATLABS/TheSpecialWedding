import logging
from datetime import UTC, datetime, timedelta

from bson import ObjectId
from fastapi import HTTPException, status

from app.core.database import mongo
from app.utils.auth_utils import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    verify_password,
)
from app.utils.planner_ownership import (
    normalize_planner_email,
    normalize_planner_id,
)
from app.utils.team_subscription_gate import (
    build_team_member_block_reason,
    compute_owner_subscription_block,
)

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self):
        self.users_collection = mongo.get_users_collection()

    async def authenticate_user(self, email: str, password: str):
        # Find user in unified collection
        user = await self.users_collection.find_one({"email": email})

        # Check password - support both password_hash (new) and hashed_password (legacy)
        password_field = None
        if user:
            password_field = user.get("password_hash") or user.get("hashed_password")

        # Use dummy hash if user doesn't exist or has no password to prevent timing attacks
        target_hash = password_field if password_field else DUMMY_PASSWORD_HASH

        # Always verify password to ensure constant time execution (approx)
        is_valid_password = verify_password(password, target_hash)

        if not user or not password_field or not is_valid_password:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Check if account is active (default to True for backward compatibility with legacy users)
        if user.get("is_active") is False:  # Explicitly check for False, not just falsy
            raise HTTPException(
                status_code=401, detail="Account is not active. Please contact support."
            )

        # Check if email is verified for public registrations
        if user.get("registration_source") == "public_signup" and not user.get(
            "email_verified", False
        ):
            raise HTTPException(
                status_code=401,
                detail="Please verify your email address before logging in. Check your email for the verification link.",
            )

        return user

    async def _reject_blocked_team_member(self, user: dict) -> None:
        """Reject login for a team member whose owning planner's subscription is blocked.

        A team member cannot resolve the billing issue themselves — only the
        planner can. Rather than issue a session that would 402 on every
        feature call and leave the team member staring at a broken UI, we
        refuse to mint a token at all and surface the planner's contact info
        in the error message.

        This is the authoritative gate. The frontend surfaces the same
        reason string inline on the login form (via the existing 402 error
        propagation in AdminContext.login), so no additional UI plumbing is
        required here.

        The request-time gate in ``auth_extended.get_current_user_extended``
        remains the safety net: if a team member already has a session when
        their owning planner flips to blocked mid-use, every feature request
        continues to 402 until the frontend logout branch fires.
        """
        if user.get("role") != "team_member":
            return

        team_member_id = user.get("team_member_id")
        if not team_member_id:
            # Malformed team-member record — treat as non-blocking rather
            # than preventing login outright. The request-time gate will
            # surface the same data-integrity problem on the first request.
            logger.warning(
                f"team-member user {user.get('email')} has no team_member_id; "
                "skipping login-time block check"
            )
            return

        try:
            team_doc = await mongo.db["team_members"].find_one(
                {"_id": ObjectId(team_member_id), "status": "active"}
            )
        except Exception as e:
            # DB hiccup — fail open at login, let the request-time gate catch it.
            logger.warning(
                f"team-member login gate: team_members lookup failed for "
                f"{user.get('email')}: {e}"
            )
            return

        if not team_doc:
            # No active team_members row — likely revoked. The request-time
            # path raises 401 "Team membership is no longer active" in this
            # case; mirror that here so we don't silently issue a token to a
            # deactivated team member.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Team membership is no longer active",
                headers={"WWW-Authenticate": "Bearer"},
            )

        owner_id = normalize_planner_id(team_doc.get("owner_id"))
        owner_email = normalize_planner_email(team_doc.get("owner_email"))
        is_blocked, owner_sub_status = await compute_owner_subscription_block(
            owner_id=owner_id,
            owner_email=owner_email,
        )
        if is_blocked:
            reason = build_team_member_block_reason(owner_sub_status, owner_email)
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=reason,
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def login_and_get_token(self, email: str, password: str):
        user = await self.authenticate_user(email, password)

        # Refuse to mint a session for a team member whose owning planner's
        # subscription is blocked. The planner is the only party who can
        # resolve billing, so we don't issue a token that would 402 on every
        # feature call anyway.
        await self._reject_blocked_team_member(user)

        # Update last_login timestamp
        login_time = datetime.now(UTC)
        try:
            await self.users_collection.update_one(
                {"_id": user["_id"]}, {"$set": {"last_login": login_time}}
            )
            logger.info(f"Updated last_login for user: {email}")
        except Exception as e:
            logger.error(f"Failed to update last_login for {email}: {e!s}")
            # Don't fail the login if last_login update fails

        token_data = {"sub": user["email"], "role": user.get("role")}
        access_token_expires = timedelta(minutes=60)
        token = create_access_token(data=token_data, expires_delta=access_token_expires)

        response = {"access_token": token, "token_type": "bearer"}

        # Include onboarding flags for advertising vendors
        if user.get("role") == "advertising_vendor":
            response["must_change_password"] = user.get("must_change_password", False)
            response["name"] = user.get("business_name", user["email"])
            response["user_id"] = str(user["_id"])

        return response
