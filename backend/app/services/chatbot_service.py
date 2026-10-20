"""Chatbot service: validation, intent check, matching and response shaping.

Implements the request flow of STS section 3.2 and the response contract of
section 6.3. This is the single entry point the API layer and the CLI both call.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from app import config
from app.repositories.faq_repository import Faq, FaqRepository
from app.services.intent_service import Intent, IntentService
from app.services.matching_service import (
    MatchingService,
    MatchingSettings,
    MatchStatus,
)
from app.services.preprocessing_service import PreprocessingService

logger = logging.getLogger(__name__)

INVALID_MESSAGE = (
    f"Message must be between {config.MIN_MESSAGE_LENGTH} and "
    f"{config.MAX_MESSAGE_LENGTH} characters."
)
SUGGESTIONS_REPLY = "I'm not sure I understood. Did you mean one of these?"
FALLBACK_REPLY = (
    "Sorry, I couldn't find an answer to that. Could you rephrase it? "
    "I can help with questions about {topics}."
)
INTENT_REPLIES = {
    Intent.GREETING: (
        "Hello! I can answer questions about {topics}. What would you like to know?"
    ),
    Intent.THANKS: "You're welcome! Let me know if there's anything else you need.",
    Intent.GOODBYE: "Goodbye! Come back any time you have a question.",
}
_LOG_PREVIEW_CHARS = 120
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_NUMBER_RE = re.compile(r"\d[\d\s().-]{4,}\d")  # phones, card and order numbers


def redact(text: str) -> str:
    """Mask emails and long digit runs so personal data never reaches the logs."""
    return _NUMBER_RE.sub("[number]", _EMAIL_RE.sub("[email]", text))


class InvalidMessageError(ValueError):
    """Raised when a message is not a string or is empty or too long."""


@dataclass(frozen=True)
class ChatResponse:
    """The chatbot's reply. `to_dict()` is exactly the STS section 6.3 payload."""

    answer: str
    matched_question: str | None
    confidence: float
    fallback: bool
    suggestions: tuple[str, ...] = ()
    # Internal diagnostics: used for logging and the CLI, never sent to clients.
    kind: str = "answer"  # answer | suggestions | fallback | intent
    faq_id: int | str | None = None

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "matchedQuestion": self.matched_question,
            "confidence": self.confidence,
            "fallback": self.fallback,
            "suggestions": list(self.suggestions),
        }


def _join_topics(topics: list[str]) -> str:
    if len(topics) <= 1:
        return "".join(topics) or "our products and services"
    return ", ".join(topics[:-1]) + " and " + topics[-1]


class ChatbotService:
    """Answers user messages using FAQ matching, with small-talk handling."""

    def __init__(
        self,
        faqs: list[Faq],
        preprocessor: PreprocessingService | None = None,
        settings: MatchingSettings | None = None,
    ):
        self._faqs = list(faqs)
        preprocessor = preprocessor or PreprocessingService()
        self._matcher = MatchingService(self._faqs, preprocessor, settings)
        self._intents = IntentService(preprocessor)
        # Topic names come from the data, so the bot adapts to any FAQ domain.
        self._categories = list(dict.fromkeys(f.category for f in faqs if f.category))
        self._topics = _join_topics([c.lower() for c in self._categories])

    @classmethod
    def from_data(cls, faq_path: str | Path = config.FAQ_PATH) -> "ChatbotService":
        """Load, validate and index the FAQ file. Raises FaqDataError on bad data."""
        return cls(FaqRepository(faq_path).load())

    @property
    def faq_count(self) -> int:
        return len(self._faqs)

    def ask(self, message: str) -> ChatResponse:
        """Return the reply to one user message."""
        text = self._validate(message)

        intent = self._intents.detect(text)
        if intent is not None:
            response = ChatResponse(
                answer=INTENT_REPLIES[intent].format(topics=self._topics),
                matched_question=None,
                confidence=1.0,  # small talk is recognised exactly, not scored
                fallback=False,
                kind="intent",
            )
            self._log(text, response, detail=intent.value)
            return response

        result = self._matcher.match(text)
        confidence = round(result.top_score, 2)

        if result.status is MatchStatus.ANSWER:
            faq = result.best.faq
            response = ChatResponse(
                answer=faq.answer,
                matched_question=faq.question,
                confidence=confidence,
                fallback=False,
                kind="answer",
                faq_id=faq.id,
            )
        elif result.status is MatchStatus.SUGGESTIONS:
            response = ChatResponse(
                answer=SUGGESTIONS_REPLY,
                matched_question=None,
                confidence=confidence,
                fallback=True,
                suggestions=tuple(m.faq.question for m in result.suggestions),
                kind="suggestions",
            )
        else:
            response = ChatResponse(
                answer=FALLBACK_REPLY.format(topics=self._topics),
                matched_question=None,
                confidence=confidence,
                fallback=True,
                kind="fallback",
            )
        self._log(text, response)
        return response

    def example_questions(self, limit: int = 4) -> list[str]:
        """One representative question per category, for welcome suggestions."""
        picked: dict[str, str] = {}
        for faq in self._faqs:
            picked.setdefault(faq.category or "", faq.question)
        return list(picked.values())[:limit]

    def welcome_message(self) -> str:
        return INTENT_REPLIES[Intent.GREETING].format(topics=self._topics)

    @staticmethod
    def _validate(message: object) -> str:
        if not isinstance(message, str):
            raise InvalidMessageError(INVALID_MESSAGE)
        text = message.strip()
        if not config.MIN_MESSAGE_LENGTH <= len(text) <= config.MAX_MESSAGE_LENGTH:
            raise InvalidMessageError(INVALID_MESSAGE)
        return text

    @staticmethod
    def _log(text: str, response: ChatResponse, detail: str = "") -> None:
        # %r escapes control characters so user input cannot forge log lines.
        logger.info(
            "chat question=%r kind=%s faq_id=%s confidence=%.2f fallback=%s %s",
            redact(text)[:_LOG_PREVIEW_CHARS],
            response.kind,
            response.faq_id,
            response.confidence,
            response.fallback,
            detail,
        )
