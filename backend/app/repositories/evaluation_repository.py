"""Data-access layer for the evaluation set (test_questions.json)."""

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from app.repositories.faq_repository import Faq, FaqDataError

NO_MATCH_MARKER = "none"


@dataclass(frozen=True)
class EvaluationCase:
    """A user question and the FAQ it should match (None = out of scope)."""

    id: str
    question: str
    expected_faq_id: int | str | None

    @property
    def is_out_of_scope(self) -> bool:
        return self.expected_faq_id is None


def normalise_for_comparison(text: str) -> str:
    """Light normalisation used only to detect duplicated phrasings."""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def find_leaked_cases(
    cases: Iterable[EvaluationCase], faqs: Iterable[Faq]
) -> list[str]:
    """Return ids of evaluation questions that repeat an existing FAQ phrasing.

    The evaluation set must stay separate from the FAQ data so that tuning is not
    tested against its own phrasings (STS section 6.4).
    """
    known = {normalise_for_comparison(p) for faq in faqs for p in faq.phrasings}
    return [c.id for c in cases if normalise_for_comparison(c.question) in known]


class EvaluationRepository:
    """Loads and validates evaluation cases against the known FAQ ids."""

    def __init__(self, path: str | Path, valid_faq_ids: Iterable[int | str]):
        self._path = Path(path)
        self._valid_ids = set(valid_faq_ids)

    def load(self) -> list[EvaluationCase]:
        raw = self._read_json()
        if not isinstance(raw, list) or not raw:
            raise FaqDataError(
                f"{self._path.name} must contain a non-empty JSON array of test cases."
            )

        errors: list[str] = []
        seen_ids: set[str] = set()
        cases: list[EvaluationCase] = []
        for index, item in enumerate(raw):
            case = self._parse_case(index, item, seen_ids, errors)
            if case is not None:
                cases.append(case)

        if errors:
            details = "\n  - ".join(errors)
            raise FaqDataError(f"{self._path.name} failed validation:\n  - {details}")
        return cases

    def _read_json(self) -> object:
        try:
            with self._path.open(encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError as exc:
            raise FaqDataError(f"Evaluation file not found: {self._path}") from exc
        except json.JSONDecodeError as exc:
            raise FaqDataError(
                f"Evaluation file {self._path.name} is not valid JSON "
                f"(line {exc.lineno}, column {exc.colno}): {exc.msg}"
            ) from exc

    def _parse_case(
        self,
        index: int,
        item: object,
        seen_ids: set[str],
        errors: list[str],
    ) -> EvaluationCase | None:
        label = f"case #{index + 1}"
        if not isinstance(item, dict):
            errors.append(f"{label}: must be a JSON object")
            return None

        problems_before = len(errors)

        case_id = item.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            errors.append(f"{label}: 'id' must be a non-empty string")
        else:
            label = f"case {case_id}"
            if case_id in seen_ids:
                errors.append(f"{label}: duplicate id")
            seen_ids.add(case_id)

        question = item.get("question")
        if not isinstance(question, str) or not question.strip():
            errors.append(f"{label}: 'question' must be a non-empty string")

        expected = item.get("expected_faq_id")
        if expected == NO_MATCH_MARKER:
            expected = None
        elif expected not in self._valid_ids:
            errors.append(
                f"{label}: 'expected_faq_id' {expected!r} is not a known FAQ id "
                f"or '{NO_MATCH_MARKER}'"
            )

        if len(errors) > problems_before:
            return None
        return EvaluationCase(case_id, question.strip(), expected)
