"""Shared evaluator for FormField conditional_logic.

Schema (compatible with the optional Dict[str, Any] field on FormField):

    {
      "show_when": {
        "all": [<condition>, ...],   # all must match (default semantic)
        # or
        "any": [<condition>, ...],   # any must match
      }
    }

Each <condition> is a dict like::

    {"field_id": "diet_pref", "operator": "equals", "value": "vegetarian"}

Supported operators: ``equals``, ``not_equals``, ``in``, ``not_in``,
``contains``, ``is_empty``, ``is_not_empty``. Unknown operators or
malformed logic default to "field is visible" so that bad authoring
never silently hides a required question.

This same evaluator runs on the frontend (see app/utils/formConditionalLogic.ts)
so the planner sees one consistent semantic in both the renderer and the
server-side required-field check.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

_VALID_OPERATORS = {
    "equals",
    "not_equals",
    "in",
    "not_in",
    "contains",
    "is_empty",
    "is_not_empty",
}


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _evaluate_condition(condition: dict[str, Any], responses: dict[str, Any]) -> bool:
    if not isinstance(condition, dict):
        return True

    field_id = condition.get("field_id")
    operator = condition.get("operator")

    if not isinstance(field_id, str) or not field_id:
        return True
    if operator not in _VALID_OPERATORS:
        return True

    actual = responses.get(field_id)
    expected = condition.get("value")

    if operator == "equals":
        return actual == expected
    if operator == "not_equals":
        return actual != expected
    if operator == "is_empty":
        return _is_empty(actual)
    if operator == "is_not_empty":
        return not _is_empty(actual)
    if operator == "in":
        if not isinstance(expected, (list, tuple, set)):
            return False
        return actual in expected
    if operator == "not_in":
        if not isinstance(expected, (list, tuple, set)):
            return True
        return actual not in expected
    if operator == "contains":
        if isinstance(actual, str) and isinstance(expected, str):
            return expected in actual
        if isinstance(actual, (list, tuple, set)):
            return expected in actual
        return False

    return True


def is_field_visible(field: dict[str, Any], responses: dict[str, Any]) -> bool:
    """Return True if ``field`` should be visible given the current ``responses``.

    Fields with no ``conditional_logic`` (or with malformed logic) are always
    treated as visible. The evaluator never raises — bad logic falls back to
    visibility so a typo cannot silently delete a required question.
    """
    logic = field.get("conditional_logic")
    if not isinstance(logic, dict):
        return True

    show_when = logic.get("show_when")
    if not isinstance(show_when, dict):
        return True

    if "all" in show_when:
        conditions = show_when.get("all")
        if not isinstance(conditions, list) or not conditions:
            return True
        return all(_evaluate_condition(c, responses) for c in conditions)

    if "any" in show_when:
        conditions = show_when.get("any")
        if not isinstance(conditions, list) or not conditions:
            return True
        return any(_evaluate_condition(c, responses) for c in conditions)

    return True


def filter_responses_to_visible(
    fields: Iterable[dict[str, Any]],
    responses: dict[str, Any],
    *,
    keep_unknown: bool = False,
) -> dict[str, Any]:
    """Drop response values for fields that are not visible under the current state.

    Visibility depends on responses to *other* fields, so we evaluate
    against the full submitted ``responses`` map. Fields without
    ``conditional_logic`` are kept untouched.

    Item 5 (audit fix): orphan response keys (keys that don't match any
    current field id — typically because the planner removed a field
    after responses came in) are now dropped by default. Pass
    ``keep_unknown=True`` to retain them — useful when the caller is
    reconstructing historical schemas (e.g. an export tool that wants to
    surface "deleted-field" columns explicitly).
    """
    fields_list = list(fields)
    known_field_ids = {f.get("id") for f in fields_list if isinstance(f, dict)}
    visible_field_ids = {
        field["id"]
        for field in fields_list
        if isinstance(field, dict)
        and "id" in field
        and is_field_visible(field, responses)
    }
    if keep_unknown:
        return {
            field_id: value
            for field_id, value in responses.items()
            if field_id in visible_field_ids or field_id not in known_field_ids
        }
    return {
        field_id: value
        for field_id, value in responses.items()
        if field_id in visible_field_ids
    }


def required_visible_field_ids(
    fields: Iterable[dict[str, Any]], responses: dict[str, Any]
) -> list[str]:
    """List the IDs of fields that are both required and currently visible."""
    out: list[str] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        if not field.get("required"):
            continue
        if is_field_visible(field, responses):
            out.append(field["id"])
    return out


__all__ = [
    "filter_responses_to_visible",
    "is_field_visible",
    "required_visible_field_ids",
]
