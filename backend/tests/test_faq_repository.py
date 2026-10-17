"""Tests for the FAQ data-access layer and the shipped dataset."""

import json

import pytest

from app import config
from app.repositories.faq_repository import FaqDataError, FaqRepository


def write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def record(**overrides):
    base = {"id": 1, "question": "Q?", "answer": "A."}
    base.update(overrides)
    return base


class TestShippedDataset:
    def test_meets_minimum_faq_count(self):
        faqs = FaqRepository(config.FAQ_PATH).load()
        assert len(faqs) >= config.MIN_FAQ_COUNT

    def test_ids_are_unique(self):
        faqs = FaqRepository(config.FAQ_PATH).load()
        ids = [faq.id for faq in faqs]
        assert len(ids) == len(set(ids))

    def test_every_faq_has_category_and_alternate_phrasings(self):
        faqs = FaqRepository(config.FAQ_PATH).load()
        assert all(faq.category for faq in faqs)
        assert all(len(faq.alt_questions) >= 4 for faq in faqs)

    def test_phrasings_include_canonical_question_first(self):
        faq = FaqRepository(config.FAQ_PATH).load()[0]
        assert faq.phrasings[0] == faq.question
        assert faq.phrasings[1:] == faq.alt_questions


class TestLoading:
    def test_loads_valid_records_with_optional_fields_omitted(self, tmp_path):
        path = write_json(tmp_path / "faqs.json", [record()])
        faqs = FaqRepository(path).load()
        assert faqs[0].category is None
        assert faqs[0].alt_questions == ()

    def test_strips_whitespace(self, tmp_path):
        path = write_json(
            tmp_path / "faqs.json", [record(question="  Q?  ", answer=" A. ")]
        )
        faq = FaqRepository(path).load()[0]
        assert (faq.question, faq.answer) == ("Q?", "A.")

    def test_accepts_string_ids(self, tmp_path):
        path = write_json(tmp_path / "faqs.json", [record(id="ship-1")])
        assert FaqRepository(path).load()[0].id == "ship-1"


class TestStartupFailures:
    def test_missing_file(self, tmp_path):
        with pytest.raises(FaqDataError, match="not found"):
            FaqRepository(tmp_path / "missing.json").load()

    def test_malformed_json(self, tmp_path):
        path = tmp_path / "faqs.json"
        path.write_text("[{not json", encoding="utf-8")
        with pytest.raises(FaqDataError, match="not valid JSON"):
            FaqRepository(path).load()

    @pytest.mark.parametrize("payload", [[], {}, "text", 42])
    def test_empty_or_wrong_top_level_type(self, tmp_path, payload):
        path = write_json(tmp_path / "faqs.json", payload)
        with pytest.raises(FaqDataError, match="non-empty JSON array"):
            FaqRepository(path).load()


class TestRecordValidation:
    @pytest.mark.parametrize(
        "bad_record, message",
        [
            (record(id=None), "'id' must be"),
            (record(id=True), "'id' must be"),
            (record(id=""), "'id' must be"),
            (record(question=""), "'question' must be a non-empty string"),
            (record(answer="   "), "'answer' must be a non-empty string"),
            (record(category=5), "'category' must be"),
            (record(alt_questions="not a list"), "'alt_questions' must be a list"),
            (record(alt_questions=["ok", ""]), "'alt_questions' must be a list"),
            ("not an object", "must be a JSON object"),
        ],
    )
    def test_invalid_record_is_rejected(self, tmp_path, bad_record, message):
        path = write_json(tmp_path / "faqs.json", [bad_record])
        with pytest.raises(FaqDataError, match=message):
            FaqRepository(path).load()

    def test_duplicate_ids_are_rejected(self, tmp_path):
        path = write_json(tmp_path / "faqs.json", [record(), record()])
        with pytest.raises(FaqDataError, match="duplicate id"):
            FaqRepository(path).load()

    def test_all_problems_are_reported_together(self, tmp_path):
        path = write_json(
            tmp_path / "faqs.json", [record(question=""), record(id=2, answer="")]
        )
        with pytest.raises(FaqDataError) as excinfo:
            FaqRepository(path).load()
        message = str(excinfo.value)
        assert "'question'" in message and "'answer'" in message
