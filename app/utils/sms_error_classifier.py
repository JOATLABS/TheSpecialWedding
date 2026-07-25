# app/utils/sms_error_classifier.py

"""
Twilio SMS error classification utility.

Categorizes Twilio error codes into actionable groups so the system can
take appropriate action (retry, flag phone, alert admin, etc.).
"""

# Temporary errors — safe to retry with exponential backoff
TEMPORARY_ERRORS = {
    "30001",  # Queue overflow - message queue is full
    "30008",  # Unknown error
    "30009",  # Missing segment
}

# Permanent recipient-level errors — phone number is invalid or unreachable
PERMANENT_RECIPIENT_ERRORS = {
    "21211",  # Invalid phone number format
    "21612",  # The 'To' number is not a valid phone number
    "21614",  # Invalid mobile number
    "30003",  # Unreachable destination handset
    "30005",  # Unknown destination handset
    "30006",  # Landline or unreachable carrier
}

# Account-level errors — affects ALL sends, needs immediate ROOT_ADMIN attention
ACCOUNT_LEVEL_ERRORS = {
    "30002",  # Account suspended
    "21408",  # Permission denied
    "30010",  # Message price exceeds max price
}

# Compliance errors — recipient has opted out or carrier blocked
COMPLIANCE_ERRORS = {
    "21610",  # Attempt to send to unsubscribed recipient
    "30004",  # Message blocked
    "30007",  # Carrier violation
}


def classify_error(error_code: int | None) -> str:
    """
    Classify a Twilio error code into an actionable category.

    Returns one of:
        - "temporary" — safe to retry
        - "permanent_recipient" — invalid/unreachable phone, should flag
        - "account_level" — system-wide issue, alert ROOT_ADMIN
        - "compliance" — opt-out/blocked, respect and update guest record
        - "unknown" — unrecognized error code
    """
    if error_code is None:
        return "unknown"

    code_str = str(error_code)

    if code_str in TEMPORARY_ERRORS:
        return "temporary"
    if code_str in PERMANENT_RECIPIENT_ERRORS:
        return "permanent_recipient"
    if code_str in ACCOUNT_LEVEL_ERRORS:
        return "account_level"
    if code_str in COMPLIANCE_ERRORS:
        return "compliance"
    return "unknown"


def should_retry(error_code: int | None) -> bool:
    """Return True if the error is temporary and the message should be retried."""
    return classify_error(error_code) == "temporary"


def is_account_level(error_code: int | None) -> bool:
    """Return True if the error affects the entire Twilio account."""
    return classify_error(error_code) == "account_level"


def is_permanent_recipient(error_code: int | None) -> bool:
    """Return True if the error means the phone number is permanently unreachable."""
    return classify_error(error_code) == "permanent_recipient"


def is_compliance(error_code: int | None) -> bool:
    """Return True if the error is compliance-related (opt-out, blocked)."""
    return classify_error(error_code) == "compliance"
