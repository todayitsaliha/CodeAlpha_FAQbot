"""Retrieval-based FAQ matching: TF-IDF vectors compared by cosine similarity.

Each FAQ is represented by several phrasings (its question plus alternates). A user
question is scored against every phrasing and a FAQ takes the score of its best
phrasing. Two feature views of the same preprocessed text are blended:

* word TF-IDF (unigrams + bigrams): captures shared vocabulary and short phrases
* character TF-IDF (char_wb 3-5 grams): tolerant of typos such as "delivry"

Before scoring, words that are not real English words and closely resemble a word
used in the FAQs are corrected ("cancle" -> "cancel"). Real words are never touched,
so out-of-scope questions are not bent towards FAQ vocabulary.

The blended score then drives a three-way decision: answer, suggest, or fall back.
"""

import copy
import difflib
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

import numpy as np
from nltk.corpus import wordnet
from sklearn.feature_extraction.text import TfidfVectorizer

from app import config
from app.repositories.faq_repository import Faq
from app.services.preprocessing_service import PreprocessingService
from app.services.semantic_service import SemanticIndex, SemanticModel

TYPO_MIN_LENGTH = 5  # shorter words are too ambiguous to correct safely
TYPO_CUTOFF = 0.8  # difflib similarity required to accept a correction


class MatchStatus(str, Enum):
    ANSWER = "answer"
    SUGGESTIONS = "suggestions"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class MatchingSettings:
    """Tunable decision parameters."""

    answer_threshold: float = config.ANSWER_THRESHOLD
    suggestion_threshold: float = config.SUGGESTION_THRESHOLD
    word_weight: float = config.WORD_WEIGHT
    max_suggestions: int = config.MAX_SUGGESTIONS
    semantic_weight: float = 0.0  # share of the score from word vectors (0 = off)

    @classmethod
    def default(cls, semantic: bool) -> "MatchingSettings":
        """The tuned profile for TF-IDF-only or TF-IDF plus word vectors."""
        if not semantic:
            return cls()
        return cls(
            answer_threshold=config.SEMANTIC_ANSWER_THRESHOLD,
            suggestion_threshold=config.SEMANTIC_SUGGESTION_THRESHOLD,
            word_weight=config.SEMANTIC_WORD_WEIGHT,
            semantic_weight=config.SEMANTIC_WEIGHT,
        )

    def __post_init__(self) -> None:
        if not 0.0 <= self.suggestion_threshold <= self.answer_threshold <= 1.0:
            raise ValueError(
                "thresholds must satisfy 0 <= suggestion_threshold "
                "<= answer_threshold <= 1"
            )
        if not 0.0 <= self.word_weight <= 1.0:
            raise ValueError("word_weight must be between 0 and 1")
        if not 0.0 <= self.semantic_weight <= 1.0:
            raise ValueError("semantic_weight must be between 0 and 1")
        if self.max_suggestions < 1:
            raise ValueError("max_suggestions must be at least 1")


@dataclass(frozen=True)
class Match:
    faq: Faq
    score: float


@dataclass(frozen=True)
class MatchResult:
    """Outcome of matching one user question."""

    status: MatchStatus
    best: Match | None = None  # set only when status is ANSWER
    suggestions: tuple[Match, ...] = ()  # set only when status is SUGGESTIONS
    top_score: float = 0.0  # best raw score, kept for logging and diagnostics


class MatchingService:
    """Indexes FAQ phrasings once, then matches user questions against them."""

    def __init__(
        self,
        faqs: Iterable[Faq],
        preprocessor: PreprocessingService,
        settings: MatchingSettings | None = None,
        semantic: SemanticModel | None = None,
    ):
        self._faqs = list(faqs)
        if not self._faqs:
            raise ValueError("MatchingService needs at least one FAQ")
        self._preprocessor = preprocessor
        self.settings = settings or MatchingSettings.default(semantic is not None)

        texts: list[str] = []
        starts: list[int] = []
        for faq in self._faqs:
            starts.append(len(texts))
            texts.extend(preprocessor.preprocess_to_text(p) for p in faq.phrasings)
        self._starts = np.array(starts)
        self._vocabulary = sorted(
            {
                word
                for faq in self._faqs
                for phrasing in faq.phrasings
                for word in preprocessor.clean(phrasing).split()
                if word.isalpha()
            }
        )
        self._vocabulary_set = frozenset(self._vocabulary)

        self._word_vectorizer = TfidfVectorizer(
            ngram_range=(1, 2), sublinear_tf=True, token_pattern=r"\S+"
        )
        self._char_vectorizer = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True
        )
        self._word_matrix = self._word_vectorizer.fit_transform(texts)
        self._char_matrix = self._char_vectorizer.fit_transform(texts)
        self._semantic_index = None
        if semantic is not None:
            idf = {
                term: float(self._word_vectorizer.idf_[i])
                for term, i in self._word_vectorizer.vocabulary_.items()
                if " " not in term
            }
            self._semantic_index = SemanticIndex(
                semantic, [text.split() for text in texts], idf, self._starts
            )
        self._component_scores = lru_cache(maxsize=2048)(self._compute_scores)

    def with_settings(self, settings: MatchingSettings) -> "MatchingService":
        """Return a service sharing this index but using different settings."""
        clone = copy.copy(self)
        clone.settings = settings
        return clone

    def rank(self, text: str, k: int | None = None) -> list[Match]:
        """Return FAQs ordered by score (best first), ignoring all thresholds."""
        word, char, semantic = self._component_scores(text)
        weight = self.settings.word_weight
        lexical = weight * word + (1.0 - weight) * char
        share = self.settings.semantic_weight if self._semantic_index else 0.0
        scores = (1.0 - share) * lexical + share * semantic
        order = np.argsort(-scores, kind="stable")
        limit = len(order) if k is None else k
        return [
            Match(self._faqs[i], float(scores[i]))
            for i in order[:limit]
            if scores[i] > 0
        ]

    def match(self, text: str) -> MatchResult:
        """Decide between answering, suggesting similar FAQs, or falling back."""
        settings = self.settings
        ranked = self.rank(text, k=settings.max_suggestions)
        if not ranked:
            return MatchResult(MatchStatus.FALLBACK)

        top = ranked[0].score
        if top >= settings.answer_threshold:
            return MatchResult(MatchStatus.ANSWER, best=ranked[0], top_score=top)
        if top >= settings.suggestion_threshold:
            close = tuple(m for m in ranked if m.score >= settings.suggestion_threshold)
            return MatchResult(
                MatchStatus.SUGGESTIONS, suggestions=close, top_score=top
            )
        return MatchResult(MatchStatus.FALLBACK, top_score=top)

    def _compute_scores(self, text: str) -> tuple[np.ndarray, ...]:
        """Per-FAQ word, character and semantic scores (best phrasing of each FAQ)."""
        processed = self._preprocessor.preprocess_to_text(self._correct_typos(text))
        if not processed:
            zeros = np.zeros(len(self._faqs))
            return zeros, zeros, zeros

        def per_faq(matrix, vectorizer) -> np.ndarray:
            sims = (matrix @ vectorizer.transform([processed]).T).toarray().ravel()
            best = np.maximum.reduceat(sims, self._starts)
            best.setflags(write=False)
            return best

        semantic = (
            self._semantic_index.faq_scores(processed.split())
            if self._semantic_index
            else np.zeros(len(self._faqs))
        )
        return (
            per_faq(self._word_matrix, self._word_vectorizer),
            per_faq(self._char_matrix, self._char_vectorizer),
            semantic,
        )

    def _correct_typos(self, text: str) -> str:
        words = self._preprocessor.clean(text).split()
        return " ".join(self._correct_word(word) for word in words)

    def _correct_word(self, word: str) -> str:
        if (
            len(word) < TYPO_MIN_LENGTH
            or not word.isalpha()
            or word in self._vocabulary_set
            or wordnet.synsets(word)  # a real English word: leave it alone
        ):
            return word
        close = difflib.get_close_matches(
            word, self._vocabulary, n=1, cutoff=TYPO_CUTOFF
        )
        return close[0] if close else word
