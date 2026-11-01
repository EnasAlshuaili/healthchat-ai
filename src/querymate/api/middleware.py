"""Request context: request ID, body-size limit, content type, headers, and fail-safe 500s.

Pure ASGI middleware, so it runs before FastAPI reads or parses the body
(FastAPI would turn a non-JSON content type into 422 and a read error into 400).
Validation order follows the contract: 413, then 415, then 422 (in FastAPI).
"""

from __future__ import annotations

import email.message
import logging
import uuid

from querymate.api.errors import (
    MAX_BODY_BYTES,
    NO_STORE_HEADERS,
    REQUEST_ID_KEY,
    error_response,
)

logger = logging.getLogger("querymate.api")

JSON_BODY_ROUTES = {("POST", "/api/chat")}


def _is_json(content_type: str | None) -> bool:
    """`application/json`, with optional parameters such as charset. `+json` types are rejected."""
    if not content_type:
        return False
    message = email.message.Message()
    message["content-type"] = content_type
    return message.get_content_type() == "application/json"


class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        scope[REQUEST_ID_KEY] = request_id
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}

        async def reply_error(code):
            await error_response(code, request_id)(scope, receive, send)

        # 413: declared length first, then the bytes actually received.
        declared = headers.get("content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > MAX_BODY_BYTES):
            await reply_error("payload_too_large")
            return
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > MAX_BODY_BYTES:
                await reply_error("payload_too_large")
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)

        # 415: only for routes that take a JSON body.
        if (scope["method"], scope["path"]) in JSON_BODY_ROUTES and not _is_json(
            headers.get("content-type")
        ):
            await reply_error("unsupported_media_type")
            return

        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        started = False

        async def send_with_headers(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                extra = {**NO_STORE_HEADERS, "X-Request-ID": request_id}
                kept = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.decode("latin-1").lower() not in {h.lower() for h in extra}
                ]
                message = {
                    **message,
                    "headers": kept
                    + [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in extra.items()],
                }
            await send(message)

        try:
            await self.app(scope, replay, send_with_headers)
        except Exception as exc:  # noqa: BLE001 - fail safe: generic 500, no details
            # Log the exception type only: messages and tracebacks may contain request content.
            logger.error("Unhandled API error %s (request_id=%s)", type(exc).__name__, request_id)
            if started:
                raise
            await reply_error("internal_error")
