"""Text preprocessing shared by FAQ indexing and live user questions.

The same pipeline must run on the stored FAQ phrasings (at startup) and on every
incoming user question, otherwise the two sides of the similarity comparison are
not comparable.

Pipeline:
    1. clean     - Unicode-normalise, lowercase, expand contractions, strip punctuation
    2. tokenize  - NLTK word tokenizer
    3. filter    - normalise slang, drop one-letter tokens and stop words
                   (negations and a few meaning-bearing function words are kept)
    4. lemmatize - WordNet lemmatizer (verb form first, then noun form)
"""

import re
import unicodedata

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

# Negations flip the meaning of a question ("can I cancel" vs "I cannot cancel"),
# so they must survive stop-word removal.
NEGATIONS = frozenset(
    {"no", "not", "nor", "never", "none", "nothing", "neither", "nobody", "nowhere"}
)

# Directional / temporal words that NLTK treats as stop words but that carry meaning
# in FAQ text ("sign up", "out of stock", "before it ships").
KEPT_FUNCTION_WORDS = frozenset(
    {"before", "after", "over", "under", "off", "out", "up", "down"}
)

# Conversational filler that never helps matching a question to an FAQ.
CHATTER_WORDS = frozenset(
    {"please", "thanks", "thank", "hi", "hello", "hey", "ok", "okay"}
)

# Minimal chat-speak normalisation. Deliberately small and unambiguous.
SLANG = {
    "u": "you",
    "ur": "your",
    "pls": "please",
    "plz": "please",
    "thx": "thanks",
    "thnx": "thanks",
}

_IRREGULAR_CONTRACTIONS = {
    "won't": "will not",
    "can't": "can not",
    "cannot": "can not",
    "shan't": "shall not",
    "ain't": "is not",
    "let's": "let us",
}
_IRREGULAR_RE = re.compile(
    r"\b(" + "|".join(re.escape(word) for word in _IRREGULAR_CONTRACTIONS) + r")\b"
)
_CONTRACTION_SUFFIXES = (
    (re.compile(r"n't\b"), " not"),
    (re.compile(r"'re\b"), " are"),
    (re.compile(r"'ve\b"), " have"),
    (re.compile(r"'ll\b"), " will"),
    (re.compile(r"'m\b"), " am"),
    (re.compile(r"'d\b"), " would"),
    (re.compile(r"'s\b"), ""),
)
_DOTTED_INITIALS_RE = re.compile(r"\b([a-z])\.(?=[a-z]\b)")  # "p.o." -> "po."
_NON_WORD_RE = re.compile(r"[\W_]+")


class PreprocessingSetupError(RuntimeError):
    """Raised when the required NLTK data packages are not installed."""


class PreprocessingService:
    """Turns raw text into a normalised list of tokens (or a joined string)."""

    def __init__(self) -> None:
        try:
            self._stop_words = (
                set(stopwords.words("english")) - NEGATIONS - KEPT_FUNCTION_WORDS
            ) | CHATTER_WORDS
            self._lemmatizer = WordNetLemmatizer()
            self._lemmatizer.lemmatize("probe")  # forces the WordNet corpus to load
            word_tokenize("probe")  # forces the tokenizer model to load
        except LookupError as exc:
            raise PreprocessingSetupError(
                "Required NLTK data is missing. Run: python -m scripts.setup_nltk"
            ) from exc

    def clean(self, text: str) -> str:
        """Normalise raw text to lowercase words separated by single spaces."""
        self._require_text(text)
        text = unicodedata.normalize("NFKC", text)
        text = text.replace("\u2019", "'").replace("\u2018", "'").lower()
        text = _IRREGULAR_RE.sub(lambda m: _IRREGULAR_CONTRACTIONS[m.group(0)], text)
        for pattern, replacement in _CONTRACTION_SUFFIXES:
            text = pattern.sub(replacement, text)
        text = _DOTTED_INITIALS_RE.sub(r"\1", text)
        return _NON_WORD_RE.sub(" ", text).strip()

    def preprocess(self, text: str) -> list[str]:
        """Return the final token list. Empty if nothing meaningful remains."""
        tokens = word_tokenize(self.clean(text))
        tokens = (SLANG.get(token, token) for token in tokens)
        kept = (
            token
            for token in tokens
            if token not in self._stop_words
            and not (len(token) == 1 and token.isalpha())
        )
        return [self._lemmatize(token) for token in kept]

    def preprocess_to_text(self, text: str) -> str:
        """Return the tokens joined by spaces, ready for a TF-IDF vectoriser."""
        return " ".join(self.preprocess(text))

    def _lemmatize(self, token: str) -> str:
        lemma = self._lemmatizer.lemmatize(token, pos="v")
        if lemma == token:
            lemma = self._lemmatizer.lemmatize(token, pos="n")
        return lemma

    @staticmethod
    def _require_text(text: object) -> None:
        if not isinstance(text, str):
            raise TypeError(f"text must be a str, got {type(text).__name__}")
