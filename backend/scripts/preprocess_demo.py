"""Show each stage of the preprocessing pipeline for one or more questions.

Usage (from backend/):  python -m scripts.preprocess_demo "How long does delivery take?"
With no arguments a few representative questions are used.
"""

import sys

from app.services.preprocessing_service import PreprocessingService

EXAMPLES = (
    "How long does delivery take?",
    "I can't log in to my account!",
    "do u ship abroad",
    "Is delivery to a P.O. box possible?",
    "Is the return label free?",
)


def main(argv: list[str]) -> int:
    service = PreprocessingService()
    for text in argv or EXAMPLES:
        print(f"raw      : {text}")
        print(f"cleaned  : {service.clean(text)}")
        print(f"tokens   : {service.preprocess(text)}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
