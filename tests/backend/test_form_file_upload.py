"""Tests for FILE_UPLOAD form-field plumbing.

Covers:
- FormUploadService.store_upload + get_upload_for_form_distribution.
- Filename sanitization, MIME / size enforcement.
- submit_form_response refuses unrecognized file_id values for FILE_UPLOAD
  fields and replaces accepted ones with full upload metadata.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import mongomock
import pytest
from fastapi import HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("FRONTEND_URL", "https://app.example.com")

import app.services.form_service as form_service_module  # noqa: E402
import app.services.form_upload_service as form_upload_service_module  # noqa: E402
from app.models.form import SubmitFormRequest  # noqa: E402
from app.services.form_upload_service import (  # noqa: E402
    MAX_UPLOAD_BYTES,
    FormUploadService,
    sanitize_filename,
)


# =============================================================================
# Filename sanitizer
# =============================================================================


@pytest.mark.parametrize(
    "input_name,expected",
    [
        ("photo.jpg", "photo.jpg"),
        # Directory traversal is dropped entirely by rsplit before sanitize.
        ("../etc/passwd", "passwd"),
        ("weird name with spaces.PDF", "weird_name_with_spaces.PDF"),
        ("", "upload"),
        (None, "upload"),
        ("a/" * 200 + "tiny.txt", "tiny.txt"),
    ],
)
def test_sanitize_filename(input_name, expected):
    assert sanitize_filename(input_name) == expected


def test_sanitize_filename_caps_length_preserves_extension():
    long_name = "a" * 200 + ".pdf"
    out = sanitize_filename(long_name)
    assert out.endswith(".pdf")
    assert len(out) <= 100


# =============================================================================
# Storage stubs
# =============================================================================


class FakeMongo:
    def __init__(self, database):
        self.db = AsyncMockDatabase(database)

    def get_forms_collection(self):
        return self.db["forms"]


class AsyncMockCursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def sort(self, *args, **kwargs):
        self.cursor.sort(*args, **kwargs)
        return self

    def limit(self, *args, **kwargs):
        self.cursor.limit(*args, **kwargs)
        return self

    def skip(self, *args, **kwargs):
        self.cursor.skip(*args, **kwargs)
        return self

    async def to_list(self, length=None):
        return list(self.cursor)


class AsyncMockCollection:
    def __init__(self, collection):
        self.collection = collection

    def find(self, *args, **kwargs):
        return AsyncMockCursor(self.collection.find(*args, **kwargs))

    async def find_one(self, *args, **kwargs):
        return self.collection.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self.collection.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self.collection.update_one(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self.collection.delete_one(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self.collection.count_documents(*args, **kwargs)


class AsyncMockDatabase:
    def __init__(self, database):
        self.db = database
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = AsyncMockCollection(self.db[name])
        return self.collections[name]


class FakeS3Client:
    def __init__(self) -> None:
        self.put_calls: list[Dict[str, Any]] = []

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)
        return {"ETag": "fake"}


class FakeStorage:
    def __init__(self) -> None:
        self.client = FakeS3Client()

    def require_target(self, target):
        from types import SimpleNamespace

        return SimpleNamespace(
            bucket_name="form-uploads-test",
            target=target,
            public_domain="https://uploads.test.example.com",
        )

    def build_public_url(self, target, key: str) -> str:
        return f"https://uploads.test.example.com/{key}"


def _form_doc(form_id: str = "form_1") -> Dict[str, Any]:
    return {
        "_id": form_id,
        "name": "Vendor proof",
        "settings": {
            "title": "Vendor proof",
            "description": "Upload your insurance certificate",
            "submit_button_text": "Submit",
            "success_message": "Thanks!",
            "allow_multiple_submissions": True,
            "collect_email": True,
            "is_public": True,
            "requires_auth": False,
        },
        "fields": [
            {
                "id": "name",
                "label": "Name",
                "type": "text",
                "required": False,
                "order": 1,
            },
            {
                "id": "insurance",
                "label": "Insurance certificate",
                "type": "file_upload",
                "required": True,
                "order": 2,
            },
        ],
        "created_by": "planner@example.com",
        "wedding_id": None,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "submission_count": 0,
        "planner_state": {},
    }


@pytest.fixture
def upload_service(monkeypatch):
    client = mongomock.MongoClient()
    database = client["wedding_forms"]
    fake_mongo = FakeMongo(database)
    monkeypatch.setattr(form_upload_service_module, "mongo", fake_mongo)
    service = FormUploadService(storage=FakeStorage())
    return service, database


@pytest.fixture
def configured_form_service(monkeypatch):
    client = mongomock.MongoClient()
    database = client["wedding_forms"]
    fake_mongo = FakeMongo(database)
    monkeypatch.setattr(form_service_module, "mongo", fake_mongo)
    monkeypatch.setattr(form_upload_service_module, "mongo", fake_mongo)
    monkeypatch.setattr(
        form_service_module.rate_limiter,
        "check_rate_limit",
        lambda *args, **kwargs: True,
    )

    service = form_service_module.FormService()
    service.upload_service._storage = FakeStorage()

    async def _noop_notify(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "_notify_planner_form_submission", _noop_notify)

    return service, database


# =============================================================================
# Upload service
# =============================================================================


@pytest.mark.asyncio
async def test_store_upload_persists_record_and_writes_to_s3(upload_service):
    service, database = upload_service
    form = _form_doc()
    distribution = {"_id": "dist-1", "form_id": form["_id"]}

    result = await service.store_upload(
        form=form,
        distribution=distribution,
        field_id="insurance",
        filename="cert.pdf",
        content_type="application/pdf",
        contents=b"hello world",
    )

    assert result["filename"] == "cert.pdf"
    assert result["url"].startswith("https://uploads.test.example.com/")
    assert result["size_bytes"] == 11

    stored = database["form_uploads"].find_one({"_id": result["file_id"]})
    assert stored is not None
    assert stored["form_id"] == "form_1"
    assert stored["distribution_id"] == "dist-1"
    assert stored["field_id"] == "insurance"

    s3_calls = service.storage.client.put_calls
    assert len(s3_calls) == 1
    assert s3_calls[0]["Bucket"] == "form-uploads-test"
    assert s3_calls[0]["Key"].startswith("forms/form_1/dist-1/")
    assert s3_calls[0]["Key"].endswith("-cert.pdf")


@pytest.mark.asyncio
async def test_store_upload_rejects_unsupported_mime(upload_service):
    service, _ = upload_service
    form = _form_doc()
    distribution = {"_id": "dist-1", "form_id": form["_id"]}

    with pytest.raises(HTTPException) as exc:
        await service.store_upload(
            form=form,
            distribution=distribution,
            field_id="insurance",
            filename="bad.exe",
            content_type="application/x-msdownload",
            contents=b"MZ",
        )
    assert exc.value.status_code == 415


@pytest.mark.asyncio
async def test_store_upload_rejects_oversize(upload_service):
    service, _ = upload_service
    form = _form_doc()
    distribution = {"_id": "dist-1", "form_id": form["_id"]}
    payload = b"a" * (MAX_UPLOAD_BYTES + 1)

    with pytest.raises(HTTPException) as exc:
        await service.store_upload(
            form=form,
            distribution=distribution,
            field_id="insurance",
            filename="big.pdf",
            content_type="application/pdf",
            contents=payload,
        )
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_store_upload_rejects_non_file_upload_field(upload_service):
    service, _ = upload_service
    form = _form_doc()
    distribution = {"_id": "dist-1", "form_id": form["_id"]}

    with pytest.raises(HTTPException) as exc:
        await service.store_upload(
            form=form,
            distribution=distribution,
            field_id="name",  # text field, not file_upload
            filename="cert.pdf",
            content_type="application/pdf",
            contents=b"hi",
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_store_upload_rejects_unknown_field(upload_service):
    service, _ = upload_service
    form = _form_doc()
    distribution = {"_id": "dist-1", "form_id": form["_id"]}

    with pytest.raises(HTTPException) as exc:
        await service.store_upload(
            form=form,
            distribution=distribution,
            field_id="not-a-field",
            filename="cert.pdf",
            content_type="application/pdf",
            contents=b"hi",
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_get_upload_for_form_distribution_scopes_correctly(upload_service):
    service, _ = upload_service
    form = _form_doc()
    distribution = {"_id": "dist-1", "form_id": form["_id"]}

    stored = await service.store_upload(
        form=form,
        distribution=distribution,
        field_id="insurance",
        filename="cert.pdf",
        content_type="application/pdf",
        contents=b"hi",
    )
    file_id = stored["file_id"]

    matched = await service.get_upload_for_form_distribution(
        file_id=file_id, form_id="form_1", distribution_id="dist-1"
    )
    assert matched is not None
    assert matched["_id"] == file_id

    # Wrong distribution -> no match (would be a forged reference)
    nope = await service.get_upload_for_form_distribution(
        file_id=file_id, form_id="form_1", distribution_id="dist-other"
    )
    assert nope is None

    # Wrong form -> no match
    nope2 = await service.get_upload_for_form_distribution(
        file_id=file_id, form_id="form_other", distribution_id="dist-1"
    )
    assert nope2 is None


# =============================================================================
# Submission integration
# =============================================================================


@pytest.mark.asyncio
async def test_submit_with_valid_file_upload_reference_persists_metadata(
    configured_form_service,
):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    raw_token = "tok"
    database["form_distributions"].insert_one(
        {
            "_id": "dist-1",
            "form_id": "form_1",
            "recipient_email": "guest@example.com",
            "sent_at": datetime.utcnow(),
            "status": "sent",
            "access_token_hash": service._hash_form_access_token(raw_token),
            "token_expires_at": datetime.utcnow().replace(year=2099),
        }
    )

    upload = await service.upload_service.store_upload(
        form=_form_doc(),
        distribution={"_id": "dist-1", "form_id": "form_1"},
        field_id="insurance",
        filename="cert.pdf",
        content_type="application/pdf",
        contents=b"hi",
    )

    request = SubmitFormRequest(
        responses={"insurance": upload["file_id"]},
        distribution_id="dist-1",
        access_token=raw_token,
    )
    result = await service.submit_form_response("form_1", request)

    response = database["form_responses"].find_one({"_id": result["id"]})
    insurance_value = response["responses"]["insurance"]
    assert isinstance(insurance_value, dict)
    assert insurance_value["file_id"] == upload["file_id"]
    assert insurance_value["filename"] == "cert.pdf"
    assert insurance_value["content_type"] == "application/pdf"
    assert insurance_value["url"].startswith("https://uploads.test.example.com/")


@pytest.mark.asyncio
async def test_submit_with_unknown_file_id_returns_400(configured_form_service):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    raw_token = "tok"
    database["form_distributions"].insert_one(
        {
            "_id": "dist-1",
            "form_id": "form_1",
            "recipient_email": "guest@example.com",
            "sent_at": datetime.utcnow(),
            "status": "sent",
            "access_token_hash": service._hash_form_access_token(raw_token),
            "token_expires_at": datetime.utcnow().replace(year=2099),
        }
    )

    request = SubmitFormRequest(
        responses={"insurance": "does-not-exist"},
        distribution_id="dist-1",
        access_token=raw_token,
    )
    with pytest.raises(HTTPException) as exc:
        await service.submit_form_response("form_1", request)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_submit_with_file_upload_but_no_distribution_id_returns_400(
    configured_form_service,
):
    """FILE_UPLOAD requires the original tokenized link — anonymous fallback can't scope it."""
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())

    request = SubmitFormRequest(
        responses={"insurance": "any-id"},
    )
    with pytest.raises(HTTPException) as exc:
        await service.submit_form_response("form_1", request)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_submit_with_file_id_from_other_distribution_is_rejected(
    configured_form_service,
):
    """A guest cannot replay another guest's upload — file_id is scoped to (form, distribution)."""
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())
    raw_token = "tok"
    database["form_distributions"].insert_many(
        [
            {
                "_id": "dist-mine",
                "form_id": "form_1",
                "recipient_email": "me@example.com",
                "sent_at": datetime.utcnow(),
                "status": "sent",
                "access_token_hash": service._hash_form_access_token(raw_token),
                "token_expires_at": datetime.utcnow().replace(year=2099),
            },
            {
                "_id": "dist-other",
                "form_id": "form_1",
                "recipient_email": "other@example.com",
                "sent_at": datetime.utcnow(),
                "status": "sent",
                "access_token_hash": service._hash_form_access_token("other"),
                "token_expires_at": datetime.utcnow().replace(year=2099),
            },
        ]
    )

    other_upload = await service.upload_service.store_upload(
        form=_form_doc(),
        distribution={"_id": "dist-other", "form_id": "form_1"},
        field_id="insurance",
        filename="other.pdf",
        content_type="application/pdf",
        contents=b"x",
    )

    # Submit using my distribution + token, but reference the OTHER upload's file_id
    request = SubmitFormRequest(
        responses={"insurance": other_upload["file_id"]},
        distribution_id="dist-mine",
        access_token=raw_token,
    )
    with pytest.raises(HTTPException) as exc:
        await service.submit_form_response("form_1", request)
    assert exc.value.status_code == 400


# =============================================================================
# Public upload endpoint contract — regression for the Codex review P1
# =============================================================================
#
# get_form() returns a sanitized public shape (rewrites _id → id, escapes
# labels). FormUploadService.store_upload() keys quotas, S3 paths, and the
# Mongo row by raw form["_id"], so passing the sanitized doc into store_upload
# previously raised KeyError("_id") and 500'd every public file upload. The
# upload endpoint now queries the raw forms_collection directly.


@pytest.mark.asyncio
async def test_get_form_strips_underscore_id_from_public_response(
    configured_form_service,
):
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())

    sanitized = await service.get_form("form_1")
    assert sanitized.get("id") == "form_1"
    assert "_id" not in sanitized, (
        "get_form() is the sanitized public-response shape; the upload "
        "endpoint must NOT pass this dict into FormUploadService."
    )


@pytest.mark.asyncio
async def test_store_upload_keyerrors_on_sanitized_form_doc(configured_form_service):
    """Document the contract that fed the regression: a sanitized doc
    breaks store_upload. Forces the upload endpoint to keep using the
    raw forms_collection lookup."""
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())

    sanitized = await service.get_form("form_1")
    distribution = {"_id": "dist-1", "form_id": "form_1"}

    with pytest.raises(KeyError):
        await service.upload_service.store_upload(
            form=sanitized,
            distribution=distribution,
            field_id="insurance",
            filename="cert.pdf",
            content_type="application/pdf",
            contents=b"hello",
        )


@pytest.mark.asyncio
async def test_store_upload_succeeds_on_raw_form_doc(configured_form_service):
    """Inverse of the above — the raw forms_collection.find_one shape
    has _id and works end-to-end. This is what the upload endpoint
    must use."""
    service, database = configured_form_service
    database["forms"].insert_one(_form_doc())

    raw_form = database["forms"].find_one({"_id": "form_1", "is_active": True})
    assert raw_form is not None and "_id" in raw_form

    distribution = {"_id": "dist-1", "form_id": "form_1"}
    result = await service.upload_service.store_upload(
        form=raw_form,
        distribution=distribution,
        field_id="insurance",
        filename="cert.pdf",
        content_type="application/pdf",
        contents=b"hello",
    )
    assert result.get("filename") == "cert.pdf"
    stored = database["form_uploads"].find_one({"_id": result["file_id"]})
    assert stored is not None and stored["form_id"] == "form_1"
