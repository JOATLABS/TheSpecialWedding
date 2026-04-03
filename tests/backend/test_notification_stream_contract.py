"""
Notification Stream Contract Tests

Verify the SSE endpoint contract stays aligned with the security hardening work.
"""

import inspect

from app.api.notification_stream import notification_stream
from app.dependencies.auth_extended import require_admin_or_planner


def test_notification_stream_does_not_accept_query_token():
    signature = inspect.signature(notification_stream)

    assert "token" not in signature.parameters
    assert "current_user" in signature.parameters

    dependency = signature.parameters["current_user"].default
    assert getattr(dependency, "dependency", None) is require_admin_or_planner


def test_notification_stream_docstring_no_longer_mentions_query_token():
    assert "?token=" not in (notification_stream.__doc__ or "")
