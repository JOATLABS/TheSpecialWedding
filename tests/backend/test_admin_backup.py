"""Regression tests for the /admin/backup/trigger endpoint.

The literal bug behind the May 2026 backup outage was that the FastAPI
container shipped without `mongodump`. The endpoint now resolves the
binary at import time and returns 503 if it isn't installed, instead of
crashing mid-request with a generic FileNotFoundError. These tests pin
that contract so a future image rebuild can't silently regress.
"""

import os
import sys
from importlib import reload
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def backup_client(monkeypatch):
    monkeypatch.setenv("BACKUP_SECRET", "test-backup-secret")

    import app.api.admin_backup as admin_backup_module

    reload(admin_backup_module)

    app = FastAPI()
    app.include_router(admin_backup_module.router, prefix="/admin")

    return TestClient(app), admin_backup_module


def test_trigger_returns_503_when_mongodump_missing(backup_client, monkeypatch):
    client, module = backup_client
    monkeypatch.setattr(module, "MONGODUMP_BIN", None)

    response = client.post(
        "/admin/backup/trigger",
        headers={"Authorization": "Bearer test-backup-secret"},
    )

    assert response.status_code == 503
    assert "mongodump" in response.json()["detail"]


def test_trigger_returns_401_when_secret_mismatched(backup_client):
    client, _ = backup_client

    response = client.post(
        "/admin/backup/trigger",
        headers={"Authorization": "Bearer wrong-secret"},
    )

    assert response.status_code == 401


def test_trigger_returns_401_when_authorization_header_missing(backup_client):
    client, _ = backup_client

    response = client.post("/admin/backup/trigger")

    assert response.status_code == 401
