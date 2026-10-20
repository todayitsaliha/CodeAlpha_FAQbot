"""HTTP layer (STS section 7): routing and request validation only.

All chatbot behaviour lives in ChatbotService; this module never touches FAQ data.
"""

from flask import Blueprint, current_app, jsonify, request

from app.controllers.errors import NOT_READY, ApiError
from app.services.chatbot_service import ChatbotService

api = Blueprint("api", __name__, url_prefix="/api")

BAD_BODY = "Request body must be a JSON object with a 'message' field."
MIN_SUGGESTED, MAX_SUGGESTED, DEFAULT_SUGGESTED = 1, 8, 4


def _chatbot() -> ChatbotService:
    bot = current_app.extensions.get("chatbot")
    if bot is None:
        raise ApiError(503, NOT_READY)
    return bot


@api.post("/chat")
def chat():
    bot = _chatbot()
    payload = request.get_json(silent=True, force=True)
    if not isinstance(payload, dict):
        raise ApiError(400, BAD_BODY)
    # Missing, non-string, empty or over-length messages raise InvalidMessageError,
    # which the global handler reports as HTTP 400.
    return jsonify(bot.ask(payload.get("message")).to_dict())


@api.get("/health")
def health():
    bot = _chatbot()
    return jsonify(status="ok", faqCount=bot.faq_count)


@api.get("/faqs/suggested")
def suggested():
    bot = _chatbot()
    try:
        limit = int(request.args.get("limit", DEFAULT_SUGGESTED))
    except ValueError:
        limit = 0  # not a number: rejected below like any other out-of-range value
    if not MIN_SUGGESTED <= limit <= MAX_SUGGESTED:
        raise ApiError(
            400,
            f"limit must be an integer between {MIN_SUGGESTED} and {MAX_SUGGESTED}.",
        )
    return jsonify(
        welcome=bot.welcome_message(), suggestions=bot.example_questions(limit)
    )
