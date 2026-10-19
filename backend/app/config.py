"""Central configuration for the FAQ chatbot backend."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FAQ_PATH = DATA_DIR / "faqs.json"
EVALUATION_PATH = DATA_DIR / "test_questions.json"

# Request limits (STS section 6.2)
MIN_MESSAGE_LENGTH = 1
MAX_MESSAGE_LENGTH = 500

# Dataset quality gate (Sprint 1 exit criterion)
MIN_FAQ_COUNT = 50

# Matching engine settings (STS section 3.3), tuned on the dev split of the evaluation
# set with scripts/tune_thresholds.py. Values are the centre of the best-scoring
# plateau, not the single argmax, to avoid overfitting. See docs/matching-engine.md.
ANSWER_THRESHOLD = 0.70  # best score at or above this returns the FAQ answer
SUGGESTION_THRESHOLD = 0.35  # between the two thresholds, suggest similar questions
WORD_WEIGHT = 0.40  # blend of word TF-IDF vs character TF-IDF (1 - WORD_WEIGHT)
MAX_SUGGESTIONS = 3
