"""Tests for the TF-IDF / cosine-similarity matching engine."""

import pytest

from app import config
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.faq_repository import Faq, FaqRepository
from app.services.matching_service import (
    MatchingService,
    MatchingSettings,
    MatchStatus,
)
from app.services.preprocessing_service import PreprocessingService


@pytest.fixture(scope="module")
def preprocessor():
    return PreprocessingService()


@pytest.fixture(scope="module")
def small_faqs():
    return [
        Faq(
            1,
            "How long does delivery take?",
            "3-5 days.",
            "Shipping",
            ("How many days until my order arrives?",),
        ),
        Faq(
            2,
            "What is your return policy?",
            "30 days.",
            "Returns",
            ("Can I send something back?",),
        ),
        Faq(
            3,
            "How do I reset my password?",
            "Use the reset link.",
            "Account",
            ("I forgot my password",),
        ),
    ]


@pytest.fixture(scope="module")
def small(small_faqs, preprocessor):
    return MatchingService(small_faqs, preprocessor)


@pytest.fixture(scope="module")
def full(preprocessor):
    faqs = FaqRepository(config.FAQ_PATH).load()
    return MatchingService(faqs, preprocessor)


class TestSettings:
    def test_defaults_come_from_config(self):
        s = MatchingSettings()
        assert (s.answer_threshold, s.suggestion_threshold) == (
            config.ANSWER_THRESHOLD,
            config.SUGGESTION_THRESHOLD,
        )

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"answer_threshold": 0.3, "suggestion_threshold": 0.5},
            {"answer_threshold": 1.2},
            {"suggestion_threshold": -0.1},
            {"word_weight": 1.5},
            {"max_suggestions": 0},
        ],
    )
    def test_invalid_settings_are_rejected(self, kwargs):
        with pytest.raises(ValueError):
            MatchingSettings(**kwargs)


class TestConstruction:
    def test_requires_at_least_one_faq(self, preprocessor):
        with pytest.raises(ValueError, match="at least one FAQ"):
            MatchingService([], preprocessor)

    def test_with_settings_leaves_original_unchanged(self, small):
        strict = small.with_settings(MatchingSettings(0.99, 0.5))
        assert strict.settings.answer_threshold == 0.99
        assert small.settings.answer_threshold == config.ANSWER_THRESHOLD


class TestRanking:
    def test_exact_question_scores_one(self, small):
        top = small.rank("How long does delivery take?", k=1)[0]
        assert top.faq.id == 1
        assert top.score == pytest.approx(1.0, abs=1e-6)

    def test_paraphrase_ranks_correct_faq_first(self, small):
        assert small.rank("how long is delivery")[0].faq.id == 1
        assert small.rank("I forgot my password again")[0].faq.id == 3

    def test_results_are_sorted_and_bounded(self, small):
        ranked = small.rank("return my order password")
        scores = [m.score for m in ranked]
        assert scores == sorted(scores, reverse=True)
        assert all(0 < s <= 1.0 + 1e-9 for s in scores)

    def test_k_limits_results(self, small):
        assert len(small.rank("return my order password", k=1)) == 1

    @pytest.mark.parametrize("text", ["", "   ", "???", "what is the", "xyzzy qwerty"])
    def test_no_overlap_gives_no_candidates(self, small, text):
        assert small.rank(text) == []

    def test_typos_are_corrected_towards_faq_vocabulary(self, small):
        assert small.rank("delivry time")[0].faq.id == 1
        assert small.rank("how to reset pasword")[0].faq.id == 3

    def test_real_words_are_never_corrected(self, small):
        assert small._correct_typos("tires and tiger") == "tires and tiger"

    def test_short_words_and_numbers_are_not_corrected(self, small):
        assert small._correct_typos("dlvr 12345") == "dlvr 12345"

    def test_both_feature_views_work_alone(self, small_faqs, preprocessor):
        for weight in (0.0, 1.0):
            service = MatchingService(
                small_faqs, preprocessor, MatchingSettings(word_weight=weight)
            )
            assert service.rank("How long does delivery take?")[0].faq.id == 1


class TestDecision:
    def test_confident_match_is_answered(self, small):
        result = small.match("How long does delivery take?")
        assert result.status is MatchStatus.ANSWER
        assert result.best.faq.id == 1
        assert result.suggestions == ()

    @pytest.mark.parametrize("text", ["", "xyzzy qwerty", "what is the"])
    def test_unrelated_or_empty_input_falls_back(self, small, text):
        result = small.match(text)
        assert result.status is MatchStatus.FALLBACK
        assert result.best is None and result.suggestions == ()

    def test_mid_confidence_returns_suggestions_only(self, small_faqs, preprocessor):
        service = MatchingService(
            small_faqs,
            preprocessor,
            MatchingSettings(
                answer_threshold=1.0, suggestion_threshold=0.05, max_suggestions=2
            ),
        )
        result = service.match("delivery password")
        assert result.status is MatchStatus.SUGGESTIONS
        assert result.best is None
        assert 1 <= len(result.suggestions) <= 2
        assert all(m.score >= 0.05 for m in result.suggestions)

    def test_top_score_is_reported(self, small):
        assert small.match("How long does delivery take?").top_score == pytest.approx(
            1.0, abs=1e-6
        )


class TestAgainstTheShippedDataset:
    def test_canonical_questions_are_answered_with_their_own_faq(self, full):
        wrong = []
        for faq in full._faqs:
            result = full.match(faq.question)
            if result.status is not MatchStatus.ANSWER or result.best.faq.id != faq.id:
                wrong.append(faq.id)
        assert wrong == []

    def test_no_phrasing_is_shared_between_two_faqs(self, full):
        """Catches conflicting duplicates: each phrasing must retrieve its own FAQ."""
        wrong = [
            (faq.id, phrasing)
            for faq in full._faqs
            for phrasing in faq.phrasings
            if full.rank(phrasing, k=1)[0].faq.id != faq.id
        ]
        assert wrong == []

    def test_out_of_scope_questions_are_never_answered(self, full):
        """Safety property: a wrong answer is worse than asking to rephrase."""
        cases = EvaluationRepository(
            config.EVALUATION_PATH, (f.id for f in full._faqs)
        ).load()
        answered = [
            c.question
            for c in cases
            if c.is_out_of_scope and full.match(c.question).status is MatchStatus.ANSWER
        ]
        assert answered == []

    def test_answers_are_overwhelmingly_correct(self, full):
        """Of all questions the bot chooses to answer, at least 95% must be right."""
        cases = EvaluationRepository(
            config.EVALUATION_PATH, (f.id for f in full._faqs)
        ).load()
        answered = right = 0
        for case in cases:
            result = full.match(case.question)
            if result.status is MatchStatus.ANSWER:
                answered += 1
                right += result.best.faq.id == case.expected_faq_id
        assert answered > 0
        assert right / answered >= 0.95
