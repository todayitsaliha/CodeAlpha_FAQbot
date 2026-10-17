"""Validate the FAQ and evaluation datasets and print a summary.

Usage (from the backend/ directory):  python -m scripts.validate_data
"""

import sys
from collections import Counter

from app import config
from app.repositories.evaluation_repository import (
    EvaluationRepository,
    find_leaked_cases,
)
from app.repositories.faq_repository import FaqDataError, FaqRepository


def _fail(message: str) -> int:
    print(f"DATA INVALID: {message}", file=sys.stderr)
    return 1


def main() -> int:
    try:
        faqs = FaqRepository(config.FAQ_PATH).load()
        cases = EvaluationRepository(
            config.EVALUATION_PATH, (faq.id for faq in faqs)
        ).load()
    except FaqDataError as exc:
        return _fail(str(exc))

    if len(faqs) < config.MIN_FAQ_COUNT:
        return _fail(
            f"{len(faqs)} FAQs found, at least {config.MIN_FAQ_COUNT} required."
        )

    leaked = find_leaked_cases(cases, faqs)
    if leaked:
        return _fail(
            "evaluation questions duplicate FAQ phrasings (train/test leakage): "
            + ", ".join(leaked)
        )

    categories = Counter(faq.category or "(uncategorised)" for faq in faqs)
    alt_total = sum(len(faq.alt_questions) for faq in faqs)
    out_of_scope = sum(case.is_out_of_scope for case in cases)

    print(f"FAQ dataset OK: {len(faqs)} FAQs, {alt_total} alternate phrasings")
    for category, count in sorted(categories.items()):
        print(f"  {category:<15} {count:>3}")
    print(
        f"Evaluation set OK: {len(cases)} cases "
        f"({len(cases) - out_of_scope} in-scope, {out_of_scope} out-of-scope), "
        "no phrasing leakage"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
