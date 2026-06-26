from typing import Any, Literal, Mapping

RSVP_STATUS_CONFIRMED = "confirmed"
RSVP_STATUS_DECLINED = "declined"
RSVP_STATUS_PENDING = "pending"
RSVP_FILTER_ALL = "all"
RSVP_FILTER_RESPONDED = "responded"
RSVP_FILTER_NOT_INVITED = "not_invited"

GUEST_RSVP_STATUS_FILTERS = {
    RSVP_FILTER_ALL,
    RSVP_FILTER_RESPONDED,
    RSVP_STATUS_CONFIRMED,
    RSVP_STATUS_DECLINED,
    RSVP_STATUS_PENDING,
    RSVP_FILTER_NOT_INVITED,
}

RSVPStatus = Literal["confirmed", "declined", "pending"]


def get_rsvp_status(rsvp: Mapping[str, Any] | None) -> RSVPStatus:
    """
    Classify an RSVP row from its canonical attending payload.

    The current RSVP schema stores attending as a list of event identifiers.
    Legacy rows may store a dict of event -> bool. A submitted RSVP with an
    empty attending selection is a declined RSVP, not a confirmed one.
    """
    if not rsvp:
        return RSVP_STATUS_PENDING

    attending = rsvp.get("attending")
    if attending is None:
        return RSVP_STATUS_PENDING

    if isinstance(attending, list):
        return RSVP_STATUS_CONFIRMED if len(attending) > 0 else RSVP_STATUS_DECLINED

    if isinstance(attending, dict):
        if any(attending.values()):
            return RSVP_STATUS_CONFIRMED
        if all(not value for value in attending.values()):
            return RSVP_STATUS_DECLINED

    return RSVP_STATUS_PENDING
