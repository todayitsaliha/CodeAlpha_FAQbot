"""Data-access layer for the FAQ knowledge base (faqs.json)."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


class FaqDataError(Exception):
    """Raised when the FAQ file is missing, malformed, or empty."""


@dataclass(frozen=True)
class Faq:
    """A single FAQ record (STS section 6.1)."""

    id: int | str
    question: str
    answer: str
    category: str | None = None
    alt_questions: tuple[str, ...] = ()

    @property
    def phrasings(self) -> tuple[str, ...]:
        """The canonical question followed by all alternate phrasings."""
        return (self.question, *self.alt_questions)


def _is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


class FaqRepository:
    """Loads and validates FAQ records from a JSON file."""

    def __init__(self, path: str | Path):
        self._path = Path(path)

    def load(self) -> list[Faq]:
        """Return all FAQs, or raise FaqDataError listing every problem found."""
        raw = self._read_json()
        if not isinstance(raw, list) or not raw:
            raise FaqDataError(
                f"{self._path.name} must contain a non-empty JSON array of FAQ records."
            )

        errors: list[str] = []
        seen_ids: set[int | str] = set()
        faqs: list[Faq] = []
        for index, record in enumerate(raw):
            faq = self._parse_record(index, record, seen_ids, errors)
            if faq is not None:
                faqs.append(faq)

        if errors:
            details = "\n  - ".join(errors)
            raise FaqDataError(f"{self._path.name} failed validation:\n  - {details}")

        logger.info("Loaded %d FAQs from %s", len(faqs), self._path)
        return faqs

    def _read_json(self) -> object:
        try:
            with self._path.open(encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError as exc:
            raise FaqDataError(f"FAQ file not found: {self._path}") from exc
        except json.JSONDecodeError as exc:
            raise FaqDataError(
                f"FAQ file {self._path.name} is not valid JSON "
                f"(line {exc.lineno}, column {exc.colno}): {exc.msg}"
            ) from exc
        except OSError as exc:
            raise FaqDataError(f"Cannot read FAQ file {self._path}: {exc}") from exc

    @staticmethod
    def _parse_record(
        index: int,
        record: object,
        seen_ids: set[int | str],
        errors: list[str],
    ) -> Faq | None:
        label = f"record #{index + 1}"
        if not isinstance(record, dict):
            errors.append(f"{label}: must be a JSON object")
            return None

        problems_before = len(errors)

        faq_id = record.get("id")
        valid_id = (
            isinstance(faq_id, int) and not isinstance(faq_id, bool)
        ) or _is_text(faq_id)
        if not valid_id:
            errors.append(f"{label}: 'id' must be an integer or a non-empty string")
        else:
            label = f"record id={faq_id!r}"
            if faq_id in seen_ids:
                errors.append(f"{label}: duplicate id")
            seen_ids.add(faq_id)

        for field in ("question", "answer"):
            if not _is_text(record.get(field)):
                errors.append(f"{label}: '{field}' must be a non-empty string")

        category = record.get("category")
        if category is not None and not _is_text(category):
            errors.append(f"{label}: 'category' must be a non-empty string if present")

        alt_questions = record.get("alt_questions")
        if alt_questions is not None and not (
            isinstance(alt_questions, list) and all(_is_text(a) for a in alt_questions)
        ):
            errors.append(
                f"{label}: 'alt_questions' must be a list of non-empty strings"
            )

        if len(errors) > problems_before:
            return None

        return Faq(
            id=faq_id,
            question=record["question"].strip(),
            answer=record["answer"].strip(),
            category=category.strip() if category else None,
            alt_questions=tuple(a.strip() for a in (alt_questions or [])),
        )
