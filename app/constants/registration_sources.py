REGISTRATION_SOURCE_PUBLIC_SIGNUP = "public_signup"
REGISTRATION_SOURCE_LEGACY = "legacy"


def is_public_signup_registration(source: str | None) -> bool:
    """Return True when a user came through the public planner signup flow."""

    return source == REGISTRATION_SOURCE_PUBLIC_SIGNUP
