"""Tests for the chatbot service: validation, intents, matching and response shape."""

import json
import logging

import pytest

from app import config
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.faq_repository import FaqDataError, FaqRepository
from app.services.chatbot_service import (
    FALLBACK_REPLY,
    INVALID_MESSAGE,
    SUGGESTIONS_REPLY,
    ChatbotService,
    InvalidMessageError,
)
from app.services.matching_service import MatchingSettings

STS_KEYS = {"answer", "matchedQuestion", "confidence", "fallback", "suggestions"}


@pytest.fixture(scope="module")
def bot():
    return ChatbotService.from_data()


@pytest.fixture(scope="module")
def suggesting_bot():
    """A bot that can never answer confidently, so mid-scores give suggestions."""
    faqs = FaqRepository(config.FAQ_PATH).load()
    return ChatbotService(faqs, settings=MatchingSettings(1.0, 0.2))


class TestValidation:
    @pytest.mark.parametrize("bad", ["", "   ", "\n\t", None, 42, ["hi"]])
    def test_invalid_messages_are_rejected(self, bot, bad):
        with pytest.raises(InvalidMessageError, match="between 1 and 500"):
            bot.ask(bad)

    def test_error_text_matches_the_sts_example(self):
        assert INVALID_MESSAGE == "Message must be between 1 and 500 characters."

    def test_over_length_message_is_rejected(self, bot):
        with pytest.raises(InvalidMessageError):
            bot.ask("a" * (config.MAX_MESSAGE_LENGTH + 1))

    def test_boundary_lengths_are_accepted(self, bot):
        assert bot.ask("a").fallback is True
        assert bot.ask("a" * config.MAX_MESSAGE_LENGTH).fallback is True

    def test_surrounding_whitespace_is_ignored(self, bot):
        padded = bot.ask("   How long does delivery take?   ")
        assert padded.faq_id == 1


class TestAnswers:
    def test_confident_match_returns_the_faq_answer(self, bot):
        response = bot.ask("How long does delivery take?")
        assert response.kind == "answer" and response.faq_id == 1
        assert response.fallback is False
        assert response.matched_question == "How long does delivery take?"
        assert response.confidence == 1.0
        assert response.suggestions == ()
        assert "3-5 business days" in response.answer

    def test_paraphrase_with_synonyms_is_answered(self, bot):
        assert bot.ask("I want to erase my account").faq_id == 39

    def test_greeting_prefix_does_not_hijack_a_question(self, bot):
        response = bot.ask("hi, how long does delivery take")
        assert response.kind == "answer" and response.faq_id == 1

    def test_is_deterministic(self, bot):
        assert bot.ask("Can I track my order?") == bot.ask("Can I track my order?")


class TestIntents:
    @pytest.mark.parametrize(
        "text, expected_fragment",
        [
            ("hello", "answer questions about"),
            ("thanks!", "welcome"),
            ("bye", "Goodbye"),
        ],
    )
    def test_small_talk_gets_canned_replies(self, bot, text, expected_fragment):
        response = bot.ask(text)
        assert response.kind == "intent"
        assert expected_fragment in response.answer
        assert response.matched_question is None
        assert response.fallback is False and response.suggestions == ()

    def test_greeting_names_the_topics_from_the_data(self, bot):
        reply = bot.ask("hi").answer
        assert "shipping" in reply and "returns" in reply


class TestFallbacks:
    def test_out_of_scope_gets_a_plain_polite_fallback(self, bot):
        response = bot.ask("Who wrote Hamlet?")
        assert response.kind == "fallback" and response.fallback is True
        assert response.matched_question is None and response.suggestions == ()
        assert response.answer == FALLBACK_REPLY.format(topics=bot._topics)
        assert "shipping" in response.answer

    def test_medium_confidence_returns_suggestions(self, suggesting_bot):
        response = suggesting_bot.ask("how many days for delivery")
        assert response.kind == "suggestions" and response.fallback is True
        assert response.answer == SUGGESTIONS_REPLY
        assert response.matched_question is None
        assert 1 <= len(response.suggestions) <= 3
        assert "How long does delivery take?" in response.suggestions

    def test_suggestions_are_real_faq_questions(self, suggesting_bot, bot):
        known = {f.question for f in FaqRepository(config.FAQ_PATH).load()}
        response = suggesting_bot.ask("how many days for delivery")
        assert set(response.suggestions) <= known


class TestResponseContract:
    @pytest.mark.parametrize(
        "text", ["How long does delivery take?", "hello", "Who wrote Hamlet?"]
    )
    def test_payload_has_exactly_the_sts_fields_and_types(self, bot, text):
        payload = bot.ask(text).to_dict()
        assert set(payload) == STS_KEYS
        assert isinstance(payload["answer"], str) and payload["answer"]
        assert payload["matchedQuestion"] is None or isinstance(
            payload["matchedQuestion"], str
        )
        assert isinstance(payload["confidence"], float)
        assert 0.0 <= payload["confidence"] <= 1.0
        assert isinstance(payload["fallback"], bool)
        assert isinstance(payload["suggestions"], list)
        json.dumps(payload)  # must be JSON-serialisable

    def test_internal_diagnostics_are_not_exposed(self, bot):
        assert not {"kind", "faq_id"} & set(bot.ask("hello").to_dict())

    def test_confidence_is_rounded_to_two_decimals(self, bot):
        confidence = bot.ask("do u ship abroad").confidence
        assert confidence == round(confidence, 2)

    def test_every_evaluation_question_produces_a_valid_response(self, bot):
        faqs = FaqRepository(config.FAQ_PATH).load()
        cases = EvaluationRepository(
            config.EVALUATION_PATH, (f.id for f in faqs)
        ).load()
        for case in cases:
            assert set(bot.ask(case.question).to_dict()) == STS_KEYS


class TestLogging:
    def test_logs_faq_id_confidence_and_fallback_flag(self, bot, caplog):
        with caplog.at_level(logging.INFO, logger="app.services.chatbot_service"):
            bot.ask("How long does delivery take?")
            bot.ask("Who wrote Hamlet?")
        messages = [r.getMessage() for r in caplog.records]
        assert "faq_id=1" in messages[0] and "fallback=False" in messages[0]
        assert "confidence=1.00" in messages[0]
        assert "kind=fallback" in messages[1] and "fallback=True" in messages[1]

    def test_control_characters_cannot_forge_log_lines(self, bot, caplog):
        with caplog.at_level(logging.INFO, logger="app.services.chatbot_service"):
            bot.ask("hello\nINFO FAKE LOG LINE")
        assert "\n" not in caplog.records[0].getMessage()


class TestSetupAndHelpers:
    def test_from_data_loads_the_shipped_faqs(self, bot):
        assert bot.faq_count >= config.MIN_FAQ_COUNT

    def test_from_data_fails_clearly_on_missing_file(self, tmp_path):
        with pytest.raises(FaqDataError, match="not found"):
            ChatbotService.from_data(tmp_path / "missing.json")

    def test_example_questions_cover_distinct_categories(self, bot):
        faqs = FaqRepository(config.FAQ_PATH).load()
        by_question = {f.question: f.category for f in faqs}
        examples = bot.example_questions(limit=4)
        assert len(examples) == 4
        assert len({by_question[q] for q in examples}) == 4

    def test_welcome_message_is_the_greeting(self, bot):
        assert bot.welcome_message() == bot.ask("hello").answer


class TestRedaction:
    @pytest.mark.parametrize(
        "text, expected",
        [
            ("mail me at jane.doe@example.com please", "mail me at [email] please"),
            ("call 1-800-555-0199 now", "call [number] now"),
            ("card 4111 1111 1111 1111", "card [number]"),
            ("order 20261020 is late", "order [number] is late"),
            ("returns within 30 days", "returns within 30 days"),
            ("takes 3-5 business days", "takes 3-5 business days"),
        ],
    )
    def test_redact(self, text, expected):
        from app.services.chatbot_service import redact

        assert redact(text) == expected
