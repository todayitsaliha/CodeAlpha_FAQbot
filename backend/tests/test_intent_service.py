"""Tests for greeting / thanks / goodbye detection."""

import pytest

from app import config
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.faq_repository import FaqRepository
from app.services.intent_service import Intent, IntentService
from app.services.preprocessing_service import PreprocessingService


@pytest.fixture(scope="module")
def intents():
    return IntentService(PreprocessingService())


class TestDetection:
    @pytest.mark.parametrize(
        "text",
        [
            "hi", "Hello!", "HEY", "hey there", "Good morning", "good evening!!",
            "hello bot", "Hi team", "howdy", "greetings", "how are you",
            "how's it going?", "what's up",
        ],
    )  # fmt: skip
    def test_greetings(self, intents, text):
        assert intents.detect(text) is Intent.GREETING

    @pytest.mark.parametrize(
        "text",
        [
            "thanks", "Thank you!", "thank you so much", "thanks a lot", "thx",
            "many thanks", "much appreciated", "I appreciate it", "great, thanks!",
            "ok thanks", "thank you for your help", "cheers",
        ],
    )  # fmt: skip
    def test_thanks(self, intents, text):
        assert intents.detect(text) is Intent.THANKS

    @pytest.mark.parametrize(
        "text",
        [
            "bye", "Goodbye!", "see you later", "see ya", "take care",
            "have a nice day", "good night", "that's all", "that is all, bye",
            "talk to you later",
        ],
    )  # fmt: skip
    def test_goodbyes(self, intents, text):
        assert intents.detect(text) is Intent.GOODBYE

    def test_goodbye_outranks_thanks_and_greeting(self, intents):
        assert intents.detect("thanks, bye") is Intent.GOODBYE
        assert intents.detect("hello and goodbye") is Intent.GOODBYE

    def test_thanks_outranks_greeting(self, intents):
        assert intents.detect("hi, thanks") is Intent.THANKS

    @pytest.mark.parametrize(
        "text",
        [
            "hi, where is my order?",
            "hello, how long does delivery take",
            "thanks for the info, can I return it?",
            "bye the way, do you ship abroad",
            "how do I say goodbye to my account",
            "can you help me",
            "what is your return policy",
            "I need help with my order",
        ],
    )
    def test_questions_containing_small_talk_are_not_intents(self, intents, text):
        assert intents.detect(text) is None

    @pytest.mark.parametrize("text", ["", "   ", "???", "banana", "ok", "great"])
    def test_non_intents(self, intents, text):
        assert intents.detect(text) is None

    def test_ignores_case_and_punctuation(self, intents):
        assert intents.detect("  ThAnKs!!!  ") is Intent.THANKS


class TestNeverHijacksRealQuestions:
    def test_no_faq_phrasing_is_an_intent(self, intents):
        faqs = FaqRepository(config.FAQ_PATH).load()
        hijacked = [p for f in faqs for p in f.phrasings if intents.detect(p)]
        assert hijacked == []

    def test_no_evaluation_question_is_an_intent(self, intents):
        faqs = FaqRepository(config.FAQ_PATH).load()
        cases = EvaluationRepository(
            config.EVALUATION_PATH, (f.id for f in faqs)
        ).load()
        assert [c.question for c in cases if intents.detect(c.question)] == []
