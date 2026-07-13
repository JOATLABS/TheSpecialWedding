"""Fail-closed replacement primitive for isolated marketing-capture fixtures."""

from __future__ import annotations

from typing import Any

from pymongo.errors import DuplicateKeyError


async def replace_scoped_document(
    collection: Any,
    document: dict[str, Any],
    *,
    seed_source: str,
    seed_scope: str,
) -> None:
    """Insert or replace one deterministic row owned by the exact seed scope."""

    document_id = document.get("_id")
    if document_id is None:
        raise RuntimeError("Scoped seed replacement requires a deterministic _id.")

    ownership = {"seed_source": seed_source, "seed_scope": seed_scope}
    if any(document.get(key) != value for key, value in ownership.items()):
        raise RuntimeError("Seeded document must carry exact seed ownership metadata.")

    existing = await collection.find_one(
        {"_id": document_id},
        {"seed_source": 1, "seed_scope": 1},
    )
    if existing:
        if any(existing.get(key) != value for key, value in ownership.items()):
            raise RuntimeError(
                f"Deterministic seed ID {document_id!s} is not owned by the exact "
                "seed scope; replacement refused."
            )
        result = await collection.replace_one(
            {"_id": document_id, **ownership},
            document,
            upsert=False,
        )
        if result.matched_count != 1:
            raise RuntimeError(
                f"Deterministic seed ID {document_id!s} changed ownership during "
                "replacement."
            )
        return

    try:
        await collection.insert_one(document)
    except DuplicateKeyError as exc:
        raise RuntimeError(
            f"Deterministic seed ID {document_id!s} or another unique field "
            "collided during insertion; replacement refused."
        ) from exc
