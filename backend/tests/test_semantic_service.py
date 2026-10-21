"""Tests for the word-vector layer and the semantic matching profile."""

import logging

import numpy as np
import pytest

from app import config
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.faq_repository import Faq, FaqRepository
from app.services import semantic_service
from app.services.matching_service import (
    MatchingService,
    MatchingSettings,
    MatchStatus,
)
from app.services.preprocessing_service import PreprocessingService
from app.services.semantic_service import SemanticModel


@pytest.fixture(scope="module")
def model():
    loaded = SemanticModel.load()
    assert loaded is not None, "run: pip install -r requirements.txt"
    return loaded


@pytest.fixture(scope="module")
def preprocessor():
    return PreprocessingService()


@pytest.fixture(scope="module")
def faqs():
    return FaqRepository(config.FAQ_PATH).load()


@pytest.fixture(scope="module")
def semantic_matcher(faqs, preprocessor, model):
    return MatchingService(faqs, preprocessor, semantic=model)


class TestModel:
    def test_known_words_have_300_dimensional_vectors(self, model):
        assert model.word_vector("delete").shape == (300,)

    def test_unknown_words_have_no_vector(self, model):
        assert model.word_vector("zzqxvk") is None

    def test_missing_model_degrades_to_none(self, monkeypatch):
        monkeypatch.setattr(semantic_service, "_load_vocab", lambda name: None)
        assert SemanticModel.load() is None

    def test_loader_warns_when_the_model_is_not_installed(self, caplog):
        with caplog.at_level(logging.WARNING, logger="app.services.semantic_service"):
            assert semantic_service._load_vocab.__wrapped__("no_such_model") is None
        assert "Word vectors unavailable" in caplog.text


class TestProfiles:
    def test_tfidf_only_profile_is_the_default_without_a_model(
        self, faqs, preprocessor
    ):
        service = MatchingService(faqs, preprocessor)
        assert service.settings == MatchingSettings.default(False)
        assert service.settings.semantic_weight == 0.0

    def test_semantic_profile_is_used_when_a_model_is_present(self, semantic_matcher):
        s = semantic_matcher.settings
        assert s == MatchingSettings.default(True)
        assert (s.semantic_weight, s.answer_threshold) == (
            config.SEMANTIC_WEIGHT,
            config.SEMANTIC_ANSWER_THRESHOLD,
        )

    def test_semantic_weight_is_ignored_without_a_model(self, faqs, preprocessor):
        plain = MatchingService(faqs, preprocessor)
        weighted = MatchingService(
            faqs, preprocessor, MatchingSettings(semantic_weight=0.9)
        )
        question = "Can I track my order?"
        assert [m.score for m in plain.rank(question)] == [
            m.score for m in weighted.rank(question)
        ]

    def test_invalid_semantic_weight_is_rejected(self):
        with pytest.raises(ValueError, match="semantic_weight"):
            MatchingSettings(semantic_weight=1.5)


class TestScoring:
    def test_exact_question_still_scores_one(self, semantic_matcher):
        top = semantic_matcher.rank("How long does delivery take?", k=1)[0]
        assert top.faq.id == 1 and top.score == pytest.approx(1.0, abs=1e-6)

    def test_scores_are_sorted_and_bounded(self, semantic_matcher):
        ranked = semantic_matcher.rank("my parcel never showed up")
        scores = [m.score for m in ranked]
        assert scores == sorted(scores, reverse=True)
        assert all(0 < s <= 1.0 + 1e-9 for s in scores)

    def test_words_without_vectors_fall_back_to_the_lexical_score(
        self, semantic_matcher
    ):
        assert semantic_matcher.rank("zzqxvk")[:1] == []  # nothing to compare at all

    def test_semantic_index_returns_one_score_per_faq(self, semantic_matcher, faqs):
        scores = semantic_matcher._semantic_index.faq_scores(["delete", "account"])
        assert scores.shape == (len(faqs),) and np.all((0 <= scores) & (scores <= 1))
        assert not semantic_matcher._semantic_index.faq_scores(["zzqxvk"]).any()

    def test_semantic_signal_adds_information_beyond_tfidf(
        self, faqs, preprocessor, model
    ):
        """Raising the semantic share changes at least some rankings."""
        lexical = MatchingService(faqs, preprocessor)
        mixed = MatchingService(
            faqs,
            preprocessor,
            MatchingSettings(0.7, 0.4, 0.2, semantic_weight=0.8),
            model,
        )
        questions = [f.alt_questions[-1] for f in faqs]
        differing = [q for q in questions if lexical.rank(q, k=3) != mixed.rank(q, k=3)]
        assert differing


@pytest.fixture(scope="module")
def main_cases(faqs):
    return EvaluationRepository(config.EVALUATION_PATH, (f.id for f in faqs)).load()


@pytest.fixture(scope="module")
def final_cases(faqs):
    ids = (f.id for f in faqs)
    return EvaluationRepository(config.FINAL_EVALUATION_PATH, ids).load()


class TestSafetyOnShippedData:
    def test_canonical_questions_are_answered_with_their_own_faq(
        self, semantic_matcher, faqs
    ):
        wrong = [
            f.id
            for f in faqs
            if (r := semantic_matcher.match(f.question)).status
            is not MatchStatus.ANSWER
            or r.best.faq.id != f.id
        ]
        assert wrong == []

    @pytest.mark.parametrize("which", ["main_cases", "final_cases"])
    def test_out_of_scope_questions_are_never_answered(
        self, semantic_matcher, request, which
    ):
        cases = request.getfixturevalue(which)
        answered = [
            c.question
            for c in cases
            if c.is_out_of_scope
            and semantic_matcher.match(c.question).status is MatchStatus.ANSWER
        ]
        assert answered == []

    @pytest.mark.parametrize("which", ["main_cases", "final_cases"])
    def test_answers_are_overwhelmingly_correct(self, semantic_matcher, request, which):
        cases = request.getfixturevalue(which)
        answered = right = 0
        for case in cases:
            result = semantic_matcher.match(case.question)
            if result.status is MatchStatus.ANSWER:
                answered += 1
                right += result.best.faq.id == case.expected_faq_id
        assert answered > 0 and right / answered >= 0.95


def test_tiny_index_builds_with_a_single_faq(preprocessor, model):
    single = [Faq(1, "How do I delete my account?", "Use settings.", "Account")]
    service = MatchingService(single, preprocessor, semantic=model)
    assert service.rank("delete account", k=1)[0].faq.id == 1
