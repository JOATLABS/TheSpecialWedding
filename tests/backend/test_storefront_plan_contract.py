from __future__ import annotations

import ast
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BOOT_SEED = PROJECT_ROOT / "scripts" / "seed_subscription_plans.py"
MANUAL_SEED = PROJECT_ROOT / "app" / "api" / "subscription_management.py"


def _module_assignment(path: Path, name: str) -> ast.AST:
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets
            ):
                return node.value
    raise AssertionError(f"{path}: missing module assignment {name}")


def _function_assignment(path: Path, function_name: str, name: str) -> ast.AST:
    tree = ast.parse(path.read_text())
    function = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        ),
        None,
    )
    assert function is not None, f"{path}: missing function {function_name}"
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            return node.value
    raise AssertionError(f"{path}: missing {name} inside {function_name}")


def _plan_feature_matrix(value: ast.AST) -> dict[str, dict[str, bool]]:
    assert isinstance(value, ast.List)
    matrix: dict[str, dict[str, bool]] = {}
    for item in value.elts:
        assert isinstance(item, ast.Dict)
        fields = {
            ast.literal_eval(key): field_value
            for key, field_value in zip(item.keys, item.values)
            if key is not None and isinstance(key, ast.Constant)
        }
        plan_name = ast.literal_eval(fields["name"])
        features = ast.literal_eval(fields["features"])
        matrix[plan_name] = features
    return matrix


def _seed_version() -> str:
    return ast.literal_eval(_module_assignment(BOOT_SEED, "SEED_VERSION"))


@pytest.fixture(scope="module")
def boot_matrix() -> dict[str, dict[str, bool]]:
    return _plan_feature_matrix(_module_assignment(BOOT_SEED, "plans"))


@pytest.fixture(scope="module")
def manual_matrix() -> dict[str, dict[str, bool]]:
    return _plan_feature_matrix(
        _function_assignment(
            MANUAL_SEED,
            "seed_default_subscription_plans",
            "default_plans",
        )
    )


def test_boot_and_manual_seed_feature_dictionaries_have_exact_parity(
    boot_matrix: dict[str, dict[str, bool]],
    manual_matrix: dict[str, dict[str, bool]],
):
    expected_plans = {"Solo", "Boutique", "Signature", "Enterprise"}
    assert set(boot_matrix) == expected_plans
    assert set(manual_matrix) == expected_plans
    assert manual_matrix == boot_matrix


@pytest.mark.parametrize(
    ("plan_name", "enabled"),
    [
        ("Solo", False),
        ("Boutique", False),
        ("Signature", True),
        ("Enterprise", True),
    ],
)
def test_storefront_features_are_explicit_and_independent_in_both_seed_paths(
    boot_matrix: dict[str, dict[str, bool]],
    manual_matrix: dict[str, dict[str, bool]],
    plan_name: str,
    enabled: bool,
):
    for matrix in (boot_matrix, manual_matrix):
        assert matrix[plan_name]["planner_storefront"] is enabled
        assert matrix[plan_name]["custom_domain"] is enabled


def test_unfinished_vendor_collaboration_is_disabled_in_both_seed_paths(
    boot_matrix: dict[str, dict[str, bool]],
    manual_matrix: dict[str, dict[str, bool]],
):
    for matrix in (boot_matrix, manual_matrix):
        assert matrix["Signature"]["vendor_collaboration"] is False
        assert matrix["Enterprise"]["vendor_collaboration"] is False


def test_plan_catalog_change_bumps_the_seed_version():
    assert _seed_version() == "2026-07-14T00:00:00+00:00"
