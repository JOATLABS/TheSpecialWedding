"""DEPRECATED — billing KB article is now seeded by seed_knowledge_base.py.

History (2026-05-10 forensics):
- This script was a duplicate of the ``understanding-your-trial-billing-
  and-subscription`` article already declared in
  ``app/scripts/seed_knowledge_base.py:SEED_ARTICLES``.
- It additionally wrote to the wrong Mongo collection
  (``knowledge_base`` instead of the canonical ``kb_articles`` that the
  runtime service reads). Anything it inserted has been silently invisible
  to the live KB for as long as that bug existed.
- Both copies carried the OLD pricing strategy ($29 / $59 / $149) and were
  flagged together during the 2026-05-10 pricing-refresh audit.

The article body has been updated in
``app/scripts/seed_knowledge_base.py`` to match the current 4-plan
strategy. This file is left in place as a stub so that any operator who
remembers the old runbook command (``python -m app.scripts.seed_billing_
kb_article``) gets a clear error rather than silently no-oping or
re-introducing stale content into a dead collection.

If you find this file via grep: `git rm` it.
"""

import sys


def main() -> int:
    sys.stderr.write(
        "[DEPRECATED] seed_billing_kb_article was removed. The billing KB "
        "article is now seeded by `app/scripts/seed_knowledge_base.py` and "
        "lives at slug `understanding-your-trial-billing-and-subscription` "
        "in the `kb_articles` collection. Run `python -m "
        "app.scripts.seed_knowledge_base` instead.\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
