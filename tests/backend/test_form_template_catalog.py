"""Validation suite for ``app.services.form_template_catalog.FORM_TEMPLATES``.

Every entry in the catalog is parsed through the same ``FormField``
Pydantic model the runtime uses, so a typo in a field type, a malformed
``conditional_logic`` block, or a duplicate ``field_id`` fails CI before
shipping rather than crashing on first request. Also verifies that
forward references in ``conditional_logic.show_when`` point at field
ids that actually exist within the same template.

References / official sources consulted while writing this suite:
- Pydantic v2 validators concept page:
  https://pydantic.dev/docs/validation/latest/concepts/validators/
  Confirms ``@field_validator`` and ``model_validate(...)`` are the
  current canonical patterns we rely on here.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("API_KEY", "test-api-key")

from app.models.form import FieldType, FormField  # noqa: E402
from app.services.form_template_catalog import FORM_TEMPLATES  # noqa: E402


# Required at the top level of every template entry.
_REQUIRED_TEMPLATE_KEYS = {"id", "name", "description", "category", "fields"}
_VALID_FIELD_TYPES = {ft.value for ft in FieldType}


@pytest.mark.parametrize("template", FORM_TEMPLATES, ids=lambda t: t["id"])
def test_template_has_required_top_level_keys(template):
    missing = _REQUIRED_TEMPLATE_KEYS - set(template)
    assert not missing, f"template {template.get('id')} missing keys: {missing}"
    assert isinstance(template["fields"], list)
    assert template["fields"], f"template {template['id']} has zero fields"


def test_catalog_template_ids_are_unique():
    seen = set()
    for template in FORM_TEMPLATES:
        tid = template["id"]
        assert tid not in seen, f"duplicate template id: {tid}"
        seen.add(tid)


@pytest.mark.parametrize("template", FORM_TEMPLATES, ids=lambda t: t["id"])
def test_template_field_ids_are_unique_within_template(template):
    ids = [field["id"] for field in template["fields"]]
    duplicates = {fid for fid in ids if ids.count(fid) > 1}
    assert not duplicates, (
        f"template {template['id']} has duplicate field ids: {duplicates}"
    )


@pytest.mark.parametrize("template", FORM_TEMPLATES, ids=lambda t: t["id"])
def test_template_field_types_are_in_field_type_enum(template):
    for field in template["fields"]:
        assert field["type"] in _VALID_FIELD_TYPES, (
            f"template {template['id']} field {field['id']} uses unknown type "
            f"{field['type']!r}; must be one of {sorted(_VALID_FIELD_TYPES)}"
        )


@pytest.mark.parametrize("template", FORM_TEMPLATES, ids=lambda t: t["id"])
def test_every_field_parses_through_form_field_model(template):
    """The strictest check — uses the same Pydantic model the runtime uses.

    Catches: invalid field id pattern (validate_field_id), malformed
    conditional_logic shape (validate_conditional_logic), bad type, etc.
    """
    for field in template["fields"]:
        # If this raises, the test fails with the Pydantic error which
        # tells us *exactly* which field and which validator rejected it.
        FormField.model_validate(field)


@pytest.mark.parametrize("template", FORM_TEMPLATES, ids=lambda t: t["id"])
def test_conditional_logic_only_references_existing_field_ids(template):
    """A show_when condition pointing at a typo'd field_id is dead weight —
    catches that early."""
    field_ids = {field["id"] for field in template["fields"]}
    for field in template["fields"]:
        logic = field.get("conditional_logic")
        if not logic:
            continue
        show_when = logic.get("show_when") or {}
        for combinator in ("all", "any"):
            for condition in show_when.get(combinator, []):
                target = condition.get("field_id")
                assert target in field_ids, (
                    f"template {template['id']} field {field['id']} "
                    f"references unknown field_id {target!r} in "
                    f"conditional_logic.show_when.{combinator}"
                )


@pytest.mark.parametrize("template", FORM_TEMPLATES, ids=lambda t: t["id"])
def test_select_radio_checkbox_have_options(template):
    """Choice-type fields without options can't render a usable input."""
    for field in template["fields"]:
        if field["type"] in {"select", "radio", "checkbox"}:
            options = field.get("options")
            assert isinstance(options, list) and options, (
                f"template {template['id']} field {field['id']} of type "
                f"{field['type']} must declare a non-empty options list"
            )


@pytest.mark.parametrize("template", FORM_TEMPLATES, ids=lambda t: t["id"])
def test_field_orders_are_strictly_positive_and_distinct(template):
    """Order=0 collides with the default and breaks deterministic sort."""
    orders = [field.get("order") for field in template["fields"]]
    assert all(isinstance(o, int) and o > 0 for o in orders), (
        f"template {template['id']} has fields with non-positive order"
    )
    assert len(set(orders)) == len(orders), (
        f"template {template['id']} has duplicate order values"
    )


def test_catalog_includes_each_lifecycle_stage():
    """Catalog completeness check — at least one template per lifecycle bucket
    so the marketing surface (Phase B/C) can claim full coverage honestly."""
    categories = {t["category"] for t in FORM_TEMPLATES}
    expected_at_least = {"intake", "timeline", "guest", "vendor", "creative"}
    missing = expected_at_least - categories
    assert not missing, (
        f"catalog missing lifecycle categories: {missing}; "
        f"present: {categories}"
    )


def test_catalog_size_meets_phase_a_target():
    """Phase A goal was 8 new templates on top of the 2 baked-in
    (wedding_feedback, vendor_questionnaire). This guards against
    accidental deletion in future refactors."""
    assert len(FORM_TEMPLATES) >= 8, (
        f"expected at least 8 catalog templates, got {len(FORM_TEMPLATES)}"
    )
