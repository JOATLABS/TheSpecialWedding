import pytest

from app.utils.support_inbox_links import (
    build_support_inbox_path,
    build_support_inbox_url,
)


def test_build_support_inbox_path_for_sms_support() -> None:
    path = build_support_inbox_path(
        "sms_support",
        ticket_id="abc123",
        wedding_id="wedding-1",
    )

    assert path == (
        "/admin/communications/inbox"
        "?conversation=sms_support&ticket_id=abc123&wedding_id=wedding-1"
    )


def test_build_support_inbox_url_for_support_ticket() -> None:
    url = build_support_inbox_url(
        "https://thespecialwedding.io/",
        "support_ticket",
        ticket_id="ticket-99",
    )

    assert (
        url == "https://thespecialwedding.io/admin/communications/inbox"
        "?conversation=support_ticket&ticket_id=ticket-99"
    )


def test_build_support_inbox_path_rejects_unknown_conversation() -> None:
    with pytest.raises(ValueError):
        build_support_inbox_path("unknown", ticket_id="abc123")  # type: ignore[arg-type]
