"""Tests for the shared NLTK preprocessing pipeline."""

import re

import pytest

from app import config
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.faq_repository import FaqRepository
from app.services.preprocessing_service import (
    PreprocessingService,
    PreprocessingSetupError,
)


@pytest.fixture(scope="module")
def service():
    return PreprocessingService()


class TestCleaning:
    def test_lowercases_and_strips_punctuation(self, service):
        assert service.clean("  How LONG does delivery take?!  ") == (
            "how long does delivery take"
        )

    def test_hyphens_become_spaces(self, service):
        assert service.clean("interest-free payments") == "interest free payments"

    def test_dotted_initials_are_collapsed(self, service):
        assert service.clean("P.O. box") == service.clean("PO box") == "po box"

    def test_curly_apostrophes_are_normalised(self, service):
        assert service.clean("I can\u2019t log in") == service.clean("I can't log in")

    def test_unicode_letters_are_preserved(self, service):
        assert service.clean("Café déjà vu") == "café déjà vu"

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("I don't know", "i do not know"),
            ("It isn't working", "it is not working"),
            ("It won't apply", "it will not apply"),
            ("I can't log in", "i can not log in"),
            ("I cannot log in", "i can not log in"),
            ("What's your policy?", "what your policy"),
            ("I'd like a refund", "i would like a refund"),
            ("We're waiting", "we are waiting"),
        ],
    )
    def test_contractions_are_expanded(self, service, text, expected):
        assert service.clean(text) == expected


class TestPreprocessing:
    def test_basic_pipeline(self, service):
        assert service.preprocess("How LONG does delivery take?!") == [
            "long",
            "delivery",
            "take",
        ]

    def test_stop_words_are_removed(self, service):
        assert service.preprocess("What is the status of my order") == [
            "status",
            "order",
        ]

    @pytest.mark.parametrize(
        "text",
        ["I can't log in", "I cannot log in", "I can not log in"],
    )
    def test_negated_phrasings_normalise_identically(self, service, text):
        assert service.preprocess(text) == ["not", "log"]

    def test_negation_survives_stop_word_removal(self, service):
        tokens = service.preprocess("I did not receive my order")
        assert tokens == ["not", "receive", "order"]

    def test_no_and_never_are_kept(self, service):
        assert "no" in service.preprocess("There is no tracking number")
        assert "never" in service.preprocess("My refund never arrived")

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("returning items", ["return", "item"]),
            ("cards charged twice", ["card", "charge", "twice"]),
            ("orders shipped", ["order", "ship"]),
            ("interest-free payments", ["interest", "free", "payment"]),
        ],
    )
    def test_lemmatisation(self, service, text, expected):
        assert service.preprocess(text) == expected

    def test_meaningful_function_words_are_kept(self, service):
        assert service.preprocess("sign up") == ["sign", "up"]
        assert service.preprocess("out of stock") == ["out", "stock"]

    def test_numbers_are_kept(self, service):
        assert "30" in service.preprocess("Returns within 30 days")

    def test_slang_is_normalised(self, service):
        assert service.preprocess("do u ship abroad") == ["ship", "abroad"]

    def test_chatter_is_removed(self, service):
        assert service.preprocess("Hello, please track my order thanks") == [
            "track",
            "order",
        ]

    def test_single_letters_are_dropped(self, service):
        assert service.preprocess("plan b for x orders") == ["plan", "order"]

    def test_preprocess_to_text_joins_tokens(self, service):
        assert service.preprocess_to_text("How long does delivery take?") == (
            "long delivery take"
        )

    @pytest.mark.parametrize("text", ["", "   ", "?!...", "what is the", "hello"])
    def test_nothing_meaningful_gives_empty_result(self, service, text):
        assert service.preprocess(text) == []
        assert service.preprocess_to_text(text) == ""

    @pytest.mark.parametrize("bad", [None, 42, ["a list"], b"bytes"])
    def test_non_string_input_is_rejected(self, service, bad):
        with pytest.raises(TypeError):
            service.preprocess(bad)

    def test_is_deterministic(self, service):
        text = "Can I swap it for a different size?"
        assert service.preprocess(text) == service.preprocess(text)


@pytest.fixture(scope="module")
def faqs():
    return FaqRepository(config.FAQ_PATH).load()


class TestAgainstTheDataset:
    def test_every_faq_phrasing_keeps_meaningful_tokens(self, service, faqs):
        empty = [p for f in faqs for p in f.phrasings if not service.preprocess(p)]
        assert empty == []

    def test_every_evaluation_question_keeps_meaningful_tokens(self, service, faqs):
        cases = EvaluationRepository(
            config.EVALUATION_PATH, (f.id for f in faqs)
        ).load()
        assert [c.id for c in cases if not service.preprocess(c.question)] == []

    def test_negations_in_faq_phrasings_are_never_lost(self, service, faqs):
        negated = re.compile(r"\bnot\b|n't\b|\bcannot\b|\bno\b|\bnever\b", re.I)
        lost = [
            p
            for f in faqs
            for p in f.phrasings
            if negated.search(p)
            and not {"not", "no", "never"} & set(service.preprocess(p))
        ]
        assert lost == []


class TestSetupFailure:
    def test_missing_nltk_data_gives_actionable_error(self, monkeypatch):
        def missing(*_args, **_kwargs):
            raise LookupError("Resource stopwords not found")

        monkeypatch.setattr(
            "app.services.preprocessing_service.stopwords.words", missing
        )
        with pytest.raises(PreprocessingSetupError, match="scripts.setup_nltk"):
            PreprocessingService()
