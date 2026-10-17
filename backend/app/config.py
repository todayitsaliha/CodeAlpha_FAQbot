"""Central configuration for the FAQ chatbot backend."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FAQ_PATH = DATA_DIR / "faqs.json"
EVALUATION_PATH = DATA_DIR / "test_questions.json"

# Request limits (STS section 6.2)
MIN_MESSAGE_LENGTH = 1
MAX_MESSAGE_LENGTH = 500
