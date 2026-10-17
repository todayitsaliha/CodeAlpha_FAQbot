"""Validate the FAQ dataset and print a summary (Sprint 1 demo command).

Usage (from the backend/ directory):  python -m scripts.validate_data
"""

import sys
from collections import Counter

from app import config
from app.repositories.faq_repository import FaqDataError, FaqRepository


def main() -> int:
    try:
        faqs = FaqRepository(config.FAQ_PATH).load()
    except FaqDataError as exc:
        print(f"FAQ data INVALID: {exc}", file=sys.stderr)
        return 1

    if len(faqs) < config.MIN_FAQ_COUNT:
        print(
            f"FAQ data INVALID: {len(faqs)} FAQs found, "
            f"at least {config.MIN_FAQ_COUNT} required.",
            file=sys.stderr,
        )
        return 1

    categories = Counter(faq.category or "(uncategorised)" for faq in faqs)
    alt_total = sum(len(faq.alt_questions) for faq in faqs)

    print(f"FAQ dataset OK: {len(faqs)} FAQs, {alt_total} alternate phrasings")
    for category, count in sorted(categories.items()):
        print(f"  {category:<15} {count:>3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
