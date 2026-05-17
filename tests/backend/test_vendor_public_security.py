from app.api.vendor_public import (
    _literal_case_insensitive_regex,
    _normalize_public_vendor_doc,
)


def test_public_vendor_search_regex_treats_input_as_literal() -> None:
    query = _literal_case_insensitive_regex("(a+)+$")

    assert query == {"$regex": r"\(a\+\)\+\$", "$options": "i"}


def test_public_vendor_search_regex_trims_and_caps_input() -> None:
    query = _literal_case_insensitive_regex("  " + "x" * 150 + "  ")

    assert query is not None
    assert query["$regex"] == "x" * 100


def test_public_vendor_response_drops_unsafe_url_schemes() -> None:
    doc = _normalize_public_vendor_doc(
        {
            "website": "javascript:alert(1)",
            "portfolio_urls": [
                "https://example.com/safe",
                "data:text/html,<script>alert(1)</script>",
            ],
        }
    )

    assert doc["website"] is None
    assert doc["portfolio_urls"] == ["https://example.com/safe"]
