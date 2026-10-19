"""Small-talk intent detection: greetings, thanks and goodbyes (STS section 3.3).

An intent fires only when the *whole* message is small talk. "hi" and "thanks a lot"
are intents; "hi, where is my order?" is a real question, so it is left for the FAQ
matcher. This keeps small talk from triggering a wrong FAQ answer without ever
hijacking a genuine question.
"""

import re
from enum import Enum

from app.services.preprocessing_service import PreprocessingService


class Intent(str, Enum):
    GREETING = "greeting"
    THANKS = "thanks"
    GOODBYE = "goodbye"


# Phrases are written in cleaned form: lowercase, apostrophes dropped, so
# "that's all" is "that all" and "how's it going" is "how it going".
_PHRASES: dict[Intent, tuple[str, ...]] = {
    Intent.GOODBYE: (
        "goodbye", "good bye", "bye bye", "bye", "see you later", "see you soon",
        "see you", "see ya", "cya", "take care", "have a nice day",
        "have a great day", "good night", "that is all", "that all",
        "talk to you later", "talk later", "farewell",
    ),
    Intent.THANKS: (
        "thank you very much", "thank you", "thanks", "thanx", "thx", "thnx",
        "many thanks", "much appreciated", "i appreciate it", "appreciate it",
        "cheers",
    ),
    Intent.GREETING: (
        "good morning", "good afternoon", "good evening", "hello", "hi", "hey",
        "hiya", "howdy", "greetings", "how are you", "how it going", "what up",
        "sup", "yo",
    ),
}  # fmt: skip

# If a message mixes intents ("thanks, bye"), the earlier one here wins.
_PRIORITY = (Intent.GOODBYE, Intent.THANKS, Intent.GREETING)

# Words allowed around an intent phrase without turning it into a real question.
_FILLERS = frozenset(
    {
        "a", "again", "all", "and", "assistant", "awesome", "bot", "chatbot",
        "everything", "for", "good", "great", "guys", "help", "it", "its", "lot",
        "much", "nice", "now", "ok", "okay", "perfect", "really", "so", "team",
        "the", "then", "there", "very", "well", "you", "your",
    }
)  # fmt: skip


def _compile(phrases: tuple[str, ...]) -> re.Pattern[str]:
    ordered = sorted(phrases, key=len, reverse=True)  # longest phrase first
    return re.compile(r"\b(?:" + "|".join(re.escape(p) for p in ordered) + r")\b")


_PATTERNS = {intent: _compile(phrases) for intent, phrases in _PHRASES.items()}


class IntentService:
    """Detects whether a whole message is a greeting, thanks or goodbye."""

    def __init__(self, preprocessor: PreprocessingService):
        self._preprocessor = preprocessor

    def detect(self, text: str) -> Intent | None:
        remaining = self._preprocessor.clean(text)
        found: set[Intent] = set()
        for intent in _PRIORITY:
            pattern = _PATTERNS[intent]
            if pattern.search(remaining):
                found.add(intent)
                remaining = pattern.sub(" ", remaining)
        if not found or any(word not in _FILLERS for word in remaining.split()):
            return None
        return next(intent for intent in _PRIORITY if intent in found)
