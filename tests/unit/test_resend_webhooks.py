"""Unit tests for Resend webhook processing.
"""
import json
import hmac
import hashlib
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os

# Set required env vars early
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_testing_only")
os.environ.setdefault("MONGO_URI", "mongodb://test:27017")

from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def sample_event():
    return {
        "type": "email.delivered",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "data": {
            "email_id": "resend_123",
            "to": "user@example.com",
            "from": "noreply@example.com",
            "subject": "Test Email"
        }
    }

@patch("app.api.webhooks.mongo")
@patch("app.api.webhooks.get_settings")
def test_resend_webhook_success(mock_get_settings, mock_mongo, client, sample_event):
    # Disable signature requirement
    class DummySettings:
        RESEND_WEBHOOK_SECRET = None
    mock_get_settings.return_value = DummySettings()
    mock_mongo.db = {"email_delivery_events": MagicMock(), "email_logs": MagicMock()}
    payload = json.dumps(sample_event)
    resp = client.post("/webhooks/resend", data=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    # Ensure insert called
    mock_mongo.db["email_delivery_events"].insert_one.assert_called_once()

@patch("app.api.webhooks.mongo")
@patch("app.api.webhooks.get_settings")
def test_resend_webhook_invalid_json(mock_get_settings, mock_mongo, client):
    class DummySettings:
        RESEND_WEBHOOK_SECRET = None
    mock_get_settings.return_value = DummySettings()
    mock_mongo.db = {"email_delivery_events": MagicMock(), "email_logs": MagicMock()}
    resp = client.post("/webhooks/resend", data="not-json")
    assert resp.status_code == 400

@patch("app.api.webhooks.mongo")
@patch("app.api.webhooks.get_settings")
def test_resend_webhook_signature_verification(mock_get_settings, mock_mongo, client, sample_event):
    secret = "supersecret"
    class DummySettings:
        RESEND_WEBHOOK_SECRET = secret
    mock_get_settings.return_value = DummySettings()
    mock_mongo.db = {"email_delivery_events": MagicMock(), "email_logs": MagicMock()}
    body = json.dumps(sample_event).encode("utf-8")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {"resend-signature": f"sha256={expected}"}
    resp = client.post("/webhooks/resend", data=body, headers=headers)
    assert resp.status_code == 200

@patch("app.api.webhooks.mongo")
@patch("app.api.webhooks.get_settings")
def test_resend_webhook_bad_signature(mock_get_settings, mock_mongo, client, sample_event):
    secret = "supersecret"
    class DummySettings:
        RESEND_WEBHOOK_SECRET = secret
    mock_get_settings.return_value = DummySettings()
    mock_mongo.db = {"email_delivery_events": MagicMock(), "email_logs": MagicMock()}
    body = json.dumps(sample_event).encode("utf-8")
    headers = {"resend-signature": "sha256=bogus"}
    resp = client.post("/webhooks/resend", data=body, headers=headers)
    assert resp.status_code == 401
