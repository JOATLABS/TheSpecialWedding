from __future__ import annotations

import asyncio
from threading import Event
from types import SimpleNamespace

import pytest

import app.services.email_service_resend as resend_service_module
from app.services.email_service_resend import ResendEmailService


class RecordingEmailLog:
    def __init__(self) -> None:
        self.entries: list[dict] = []

    async def insert_one(self, document: dict) -> SimpleNamespace:
        self.entries.append(document)
        return SimpleNamespace(inserted_id="email-log-1")


@pytest.mark.asyncio
async def test_send_email_offloads_synchronous_resend_network_io(monkeypatch):
    service = ResendEmailService.__new__(ResendEmailService)
    service.configured = True
    service.email_log_collection = RecordingEmailLog()
    provider_calls: list[dict] = []
    offloaded: list[tuple[object, tuple]] = []

    def provider_send(params: dict) -> dict:
        provider_calls.append(params)
        return {"id": "resend-1"}

    async def recording_to_thread(function, *args):
        offloaded.append((function, args))
        return function(*args)

    monkeypatch.setattr(resend_service_module.resend.Emails, "send", provider_send)
    monkeypatch.setattr(asyncio, "to_thread", recording_to_thread)

    result = await service.send_email(
        to_email="planner@example.com",
        subject="New storefront inquiry",
        html_content="<p>Hello</p>",
    )

    assert result == {"success": True, "id": "resend-1"}
    assert provider_calls and provider_calls[0]["to"] == ["planner@example.com"]
    assert offloaded == [(provider_send, (provider_calls[0],))]
    assert service.email_log_collection.entries[0]["status"] == "success"


@pytest.mark.asyncio
async def test_send_email_passes_provider_idempotency_options(monkeypatch):
    monkeypatch.setenv("RESEND_FROM_EMAIL", "noreply@thespecialwedding.io")
    service = ResendEmailService.__new__(ResendEmailService)
    service.configured = True
    service.email_log_collection = RecordingEmailLog()
    provider_calls: list[tuple[dict, dict]] = []

    def provider_send(params: dict, options: dict) -> dict:
        provider_calls.append((params, options))
        return {"id": "resend-idempotent-1"}

    monkeypatch.setattr(resend_service_module.resend.Emails, "send", provider_send)

    result = await service.send_email(
        to_email="planner@example.com",
        subject="New storefront inquiry",
        html_content="<p>Hello</p>",
        idempotency_key="storefront-inquiry/65f000000000000000000099",
    )

    assert result == {"success": True, "id": "resend-idempotent-1"}
    assert provider_calls == [
        (
            {
                "from": "noreply@thespecialwedding.io",
                "to": ["planner@example.com"],
                "subject": "New storefront inquiry",
                "html": "<p>Hello</p>",
            },
            {"idempotency_key": ("storefront-inquiry/65f000000000000000000099")},
        )
    ]


@pytest.mark.asyncio
async def test_send_email_keeps_event_loop_responsive_while_provider_waits(monkeypatch):
    service = ResendEmailService.__new__(ResendEmailService)
    service.configured = True
    service.email_log_collection = RecordingEmailLog()
    started = Event()
    release = Event()

    def waiting_provider_send(_params: dict) -> dict:
        started.set()
        release.wait(timeout=2)
        return {"id": "resend-waited"}

    monkeypatch.setattr(
        resend_service_module.resend.Emails,
        "send",
        waiting_provider_send,
    )
    task = asyncio.create_task(
        service.send_email(
            to_email="planner@example.com",
            subject="New storefront inquiry",
            html_content="<p>Hello</p>",
        )
    )

    try:
        assert await asyncio.wait_for(asyncio.to_thread(started.wait, 1), timeout=1.2)
        assert not task.done(), "provider wait must not block the event loop"
    finally:
        release.set()

    result = await asyncio.wait_for(task, timeout=1)
    assert result == {"success": True, "id": "resend-waited"}
