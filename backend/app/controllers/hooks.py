"""Per-request hooks: request id, security headers and request logging."""

import logging
import time
import uuid

from flask import Flask, Response, g, request

logger = logging.getLogger(__name__)

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    # The UI is served from this origin with no inline scripts, styles or CDNs.
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
    ),
}


def register_request_hooks(app: Flask) -> None:
    @app.before_request
    def start_request() -> None:
        g.request_id = str(uuid.uuid4())
        g.started = time.perf_counter()

    @app.after_request
    def finish_request(response: Response) -> Response:
        response.headers["X-Request-ID"] = g.request_id
        for name, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        duration_ms = (time.perf_counter() - g.started) * 1000
        # %r escapes control characters so a crafted URL cannot forge log lines.
        logger.info(
            "%s %r -> %d in %.1f ms [request_id=%s]",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            g.request_id,
        )
        return response
