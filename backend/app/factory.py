"""Flask application factory.

Layers: controllers (app.controllers) -> ChatbotService -> repositories.
FAQ vectors are built once here at startup and held in memory (STS section 3.2).
"""

import logging
from pathlib import Path

from flask import Flask, send_from_directory

from app import config
from app.controllers.api import api
from app.controllers.errors import register_error_handlers
from app.controllers.hooks import register_request_hooks
from app.repositories.faq_repository import FaqDataError
from app.services.chatbot_service import ChatbotService
from app.services.preprocessing_service import PreprocessingSetupError

logger = logging.getLogger(__name__)


class StartupError(RuntimeError):
    """Raised in strict mode when the chatbot cannot be initialised."""


def _load_chatbot(faq_path: str | Path) -> tuple[ChatbotService | None, str | None]:
    try:
        return ChatbotService.from_data(faq_path), None
    except (FaqDataError, PreprocessingSetupError) as exc:
        return None, str(exc)


def _register_frontend(app: Flask, frontend_dir: Path) -> None:
    @app.get("/")
    def index():
        return send_from_directory(frontend_dir, "index.html")

    @app.get("/<path:filename>")
    def frontend_asset(filename: str):
        return send_from_directory(frontend_dir, filename)


def create_app(
    faq_path: str | Path = config.FAQ_PATH,
    frontend_dir: str | Path | None = config.FRONTEND_DIR,
    strict: bool = False,
    chatbot: ChatbotService | None = None,
) -> Flask:
    """Build the app.

    strict=True raises StartupError if the FAQ data or NLTK data is unusable (used by
    run.py so the server refuses to start). strict=False starts in a degraded mode
    where /api/health and /api/chat return 503, which suits WSGI deployments whose
    health checks should report the problem (STS section 7.3).
    """
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_REQUEST_BYTES

    startup_error = None
    if chatbot is None:
        chatbot, startup_error = _load_chatbot(faq_path)
    if startup_error:
        logger.error("Chatbot failed to initialise: %s", startup_error)
        if strict:
            raise StartupError(startup_error)
    app.extensions["chatbot"] = chatbot

    register_request_hooks(app)
    register_error_handlers(app)
    app.register_blueprint(api)
    if frontend_dir and Path(frontend_dir).is_dir():
        _register_frontend(app, Path(frontend_dir).resolve())
    return app
