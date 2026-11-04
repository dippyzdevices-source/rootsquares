import logging

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

logger = logging.getLogger(__name__)


def register_error_handlers(app: Flask) -> None:
    """JSON + logged responses for failures Flask would otherwise return silently or as HTML.

    Before this, an oversized upload (413) and an unexpected crash (500) left nothing in the
    backend log and gave the browser a body it couldn't show a reason from."""

    # Under gunicorn nothing configures logging, so make sure warnings/errors reach stderr (Render's log).
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @app.errorhandler(RequestEntityTooLarge)
    def handle_too_large(error):
        limit_mb = (app.config.get("MAX_CONTENT_LENGTH") or 0) // (1024 * 1024)
        logger.warning(
            "Request rejected as too large: %s %s (content_length=%s, limit=%sMB)",
            request.method, request.path, request.content_length, limit_mb,
        )
        return jsonify({"error": f"Upload is too large (limit {limit_mb}MB per request)."}), 413

    @app.errorhandler(Exception)
    def handle_unexpected(error):
        if isinstance(error, HTTPException):
            return error
        logger.exception("Unhandled error on %s %s", request.method, request.path)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Something went wrong on the server."}), 500
        return error
