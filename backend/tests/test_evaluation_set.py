"""Tests for the evaluation-set repository and the shipped evaluation data."""

import json

import pytest

from app import config
from app.repositories.evaluation_repository import (
    EvaluationCase,
    EvaluationRepository,
    find_leaked_cases,
    normalise_for_comparison,
)
from app.repositories.faq_repository import Faq, FaqDataError, FaqRepository


@pytest.fixture(scope="module")
def faqs():
    return FaqRepository(config.FAQ_PATH).load()


@pytest.fixture(scope="module")
def cases(faqs):
    return EvaluationRepository(config.EVALUATION_PATH, (f.id for f in faqs)).load()


class TestShippedEvaluationSet:
    def test_has_in_scope_and_out_of_scope_cases(self, cases):
        out_of_scope = [c for c in cases if c.is_out_of_scope]
        assert len(out_of_scope) >= 10
        assert len(cases) - len(out_of_scope) >= config.MIN_FAQ_COUNT

    def test_every_faq_is_covered_by_at_least_one_case(self, faqs, cases):
        covered = {c.expected_faq_id for c in cases}
        assert {f.id for f in faqs} <= covered

    def test_case_ids_are_unique(self, cases):
        ids = [c.id for c in cases]
        assert len(ids) == len(set(ids))

    def test_no_case_repeats_an_faq_phrasing(self, faqs, cases):
        assert find_leaked_cases(cases, faqs) == []


class TestLeakageDetection:
    def test_detects_case_and_punctuation_insensitive_duplicates(self):
        faq = Faq(1, "How long does delivery take?", "A.", "Shipping", ("Is it fast?",))
        leaked = EvaluationCase("T1", "how LONG does delivery take", 1)
        alt_leaked = EvaluationCase("T2", "Is it fast", 1)
        clean = EvaluationCase("T3", "When will my parcel arrive?", 1)
        assert find_leaked_cases([leaked, alt_leaked, clean], [faq]) == ["T1", "T2"]

    def test_normalisation(self):
        assert normalise_for_comparison("  Hello,   World!! ") == "hello world"


class TestValidation:
    def load(self, tmp_path, payload, valid_ids=(1, 2)):
        path = tmp_path / "test_questions.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return EvaluationRepository(path, valid_ids).load()

    def test_none_marker_becomes_out_of_scope(self, tmp_path):
        cases = self.load(
            tmp_path, [{"id": "T1", "question": "Joke?", "expected_faq_id": "none"}]
        )
        assert cases[0].is_out_of_scope

    def test_unknown_faq_id_is_rejected(self, tmp_path):
        with pytest.raises(FaqDataError, match="not a known FAQ id"):
            self.load(tmp_path, [{"id": "T1", "question": "Q?", "expected_faq_id": 99}])

    def test_duplicate_case_ids_are_rejected(self, tmp_path):
        item = {"id": "T1", "question": "Q?", "expected_faq_id": 1}
        with pytest.raises(FaqDataError, match="duplicate id"):
            self.load(tmp_path, [item, item])

    def test_empty_question_is_rejected(self, tmp_path):
        with pytest.raises(FaqDataError, match="'question' must be"):
            self.load(tmp_path, [{"id": "T1", "question": " ", "expected_faq_id": 1}])

    def test_missing_file(self, tmp_path):
        with pytest.raises(FaqDataError, match="not found"):
            EvaluationRepository(tmp_path / "nope.json", [1]).load()

    def test_empty_array(self, tmp_path):
        with pytest.raises(FaqDataError, match="non-empty JSON array"):
            self.load(tmp_path, [])
