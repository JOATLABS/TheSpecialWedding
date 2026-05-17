"""
Utilities for normalizing and sanitizing public blog article content.
"""

from __future__ import annotations

import re

import bleach

BLOG_ALLOWED_TAGS = [
    "a",
    "blockquote",
    "br",
    "code",
    "del",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "img",
    "input",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
]

BLOG_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel", "target"],
    "code": ["class"],
    # `img` is allowed for both admin-authored and BabyLoveGrowth-synced
    # body images. `src` is constrained to https:// by the post-bleach
    # _enforce_https_image_src pass below. No `onerror`, no `srcset`,
    # no `style` — keep the attribute surface tight.
    "img": ["src", "alt", "width", "height", "loading"],
    "input": ["checked", "disabled", "type"],
    "td": ["align"],
    "th": ["align"],
}

BLOG_ALLOWED_PROTOCOLS = ["http", "https", "mailto", "tel"]

EDITORIAL_HTML_PATTERN = re.compile(
    r"</?(?:a|blockquote|br|code|del|em|h[1-6]|hr|img|input|li|ol|p|pre|strong|table|tbody|td|tfoot|th|thead|tr|ul)\b[^>]*>",
    re.IGNORECASE,
)
UNSAFE_BLOCK_PATTERN = re.compile(
    r"<(?:script|style)\b[^>]*>.*?</(?:script|style)>",
    re.IGNORECASE | re.DOTALL,
)
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
WORD_PATTERN = re.compile(r"\b[\w'-]+\b")

# Post-bleach guardrail: drop any <img> tag whose src isn't https://.
# Bleach has already normalized the structure and escaped attribute
# values; this pass is the final say on which images are allowed to
# reach the browser. Rejects http://, data:, javascript:, blob:, file:,
# relative paths, and any <img> with no src at all.
_IMG_TAG_PATTERN = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_SRC_ATTR_PATTERN = re.compile(r"""\bsrc\s*=\s*["']?([^"'>\s]+)""", re.IGNORECASE)


def _enforce_https_image_src(html: str) -> str:
    """Drop <img> tags whose src is not an https:// URL.

    Runs after bleach.clean as a defense-in-depth pass. Bleach's
    `protocols` argument governs `href`-style URL attributes; img.src
    enforcement is cleaner as a dedicated post-pass that tests can
    target directly.
    """

    def _filter(match: re.Match[str]) -> str:
        tag = match.group(0)
        src_match = _SRC_ATTR_PATTERN.search(tag)
        if not src_match:
            return ""  # No src attribute — drop the tag entirely.
        src = src_match.group(1)
        if not src.lower().startswith("https://"):
            return ""  # Non-https — drop. Includes http:, data:, javascript:, blob:, file:, relative.
        return tag

    return _IMG_TAG_PATTERN.sub(_filter, html)


def strip_unsafe_blog_blocks(content: str) -> str:
    """Remove whole unsafe blocks before sanitization so their inner text is not preserved."""
    if not content:
        return ""

    without_comments = HTML_COMMENT_PATTERN.sub("", content)
    return UNSAFE_BLOCK_PATTERN.sub("", without_comments)


def blog_content_contains_html(content: str) -> bool:
    """Detect supported editorial HTML without misclassifying plain markdown."""
    if not content:
        return False

    return bool(EDITORIAL_HTML_PATTERN.search(content))


def sanitize_blog_content(content: str) -> str:
    """Keep markdown untouched, but sanitize supported editorial HTML."""
    if not isinstance(content, str):
        return ""

    normalized = strip_unsafe_blog_blocks(content).strip()
    if not normalized:
        return ""

    if not blog_content_contains_html(normalized):
        return normalized

    cleaned = bleach.clean(
        normalized,
        tags=BLOG_ALLOWED_TAGS,
        attributes=BLOG_ALLOWED_ATTRIBUTES,
        protocols=BLOG_ALLOWED_PROTOCOLS,
        strip=True,
    )
    # Final guardrail: enforce https-only on img src. Bleach permits any
    # of BLOG_ALLOWED_PROTOCOLS on URL-bearing attributes; we want a
    # stricter rule specifically for <img>.
    return _enforce_https_image_src(cleaned).strip()


def blog_content_word_count(content: str) -> int:
    """Estimate reading time from visible content rather than raw HTML markup."""
    sanitized = sanitize_blog_content(content)
    if not sanitized:
        return 0

    text_only = (
        bleach.clean(sanitized, tags=[], strip=True)
        if blog_content_contains_html(sanitized)
        else sanitized
    )
    return len(WORD_PATTERN.findall(text_only))
