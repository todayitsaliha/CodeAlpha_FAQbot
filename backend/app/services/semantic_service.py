"""Word-vector similarity: bridges synonyms and paraphrases that TF-IDF cannot.

A phrasing becomes the IDF-weighted average of its word vectors (spaCy en_core_web_md).
Averaged vectors of unrelated sentences are all fairly similar, so the corpus mean is
subtracted before comparing ("common component removal"), which restores contrast.
The model is optional: if spaCy or the model is missing, `SemanticModel.load()` returns
None and the matcher falls back to its TF-IDF-only profile.
"""

import logging
from collections.abc import Mapping, Sequence
from functools import lru_cache

import numpy as np

from app import config

logger = logging.getLogger(__name__)
_PIPES_NOT_NEEDED = [
    "tok2vec",
    "tagger",
    "parser",
    "attribute_ruler",
    "lemmatizer",
    "ner",
]


@lru_cache(maxsize=1)
def _load_vocab(name: str):
    """Load the spaCy vocabulary once per process (loading takes a few seconds)."""
    try:
        import spacy

        return spacy.load(name, exclude=_PIPES_NOT_NEEDED).vocab
    except (ImportError, OSError) as exc:
        logger.warning(
            "Word vectors unavailable (%s); using TF-IDF only. "
            "Install with: pip install -r requirements.txt",
            exc,
        )
        return None


class SemanticModel:
    """Thin wrapper over a spaCy vocabulary that carries pre-trained word vectors."""

    def __init__(self, vocab):
        self._vocab = vocab

    @classmethod
    def load(cls, name: str = config.SPACY_MODEL) -> "SemanticModel | None":
        vocab = _load_vocab(name)
        return None if vocab is None else cls(vocab)

    def word_vector(self, token: str) -> np.ndarray | None:
        lexeme = self._vocab[token]
        return lexeme.vector if lexeme.has_vector else None


class SemanticIndex:
    """Centred, IDF-weighted average-vector index over all FAQ phrasings."""

    def __init__(
        self,
        model: SemanticModel,
        phrasing_tokens: Sequence[Sequence[str]],
        idf: Mapping[str, float],
        starts: np.ndarray,
    ):
        self._model = model
        self._idf = idf
        self._default_idf = float(np.mean(list(idf.values()))) if idf else 1.0
        self._starts = starts
        raw = [self._embed(tokens) for tokens in phrasing_tokens]
        known = [vector for vector in raw if vector is not None]
        self._dim = len(known[0])
        self._mean = np.mean(known, axis=0)
        self._matrix = np.vstack(
            [self._centre(v) if v is not None else np.zeros(self._dim) for v in raw]
        )

    def faq_scores(self, tokens: Sequence[str]) -> np.ndarray:
        """Best cosine per FAQ (0 when the question has no known words)."""
        vector = self._embed(tokens)
        if vector is None:
            return np.zeros(len(self._starts))
        sims = self._matrix @ self._centre(vector)
        return np.clip(np.maximum.reduceat(sims, self._starts), 0.0, 1.0)

    def _embed(self, tokens: Sequence[str]) -> np.ndarray | None:
        vectors, weights = [], []
        for token in tokens:
            vector = self._model.word_vector(token)
            if vector is not None:
                vectors.append(vector)
                weights.append(self._idf.get(token, self._default_idf))
        if not vectors:
            return None
        return np.average(vectors, axis=0, weights=weights)

    def _centre(self, vector: np.ndarray) -> np.ndarray:
        centred = vector - self._mean
        norm = np.linalg.norm(centred)
        return centred / norm if norm else centred
