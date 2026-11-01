"""Structured error responses (docs/API_CONTRACT.md "Structured errors").

Messages are fixed text. They never include request content, exception text,
stack traces, or paths. FastAPI's default validation handler (which echoes the
submitted input) is replaced.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from querymate.api.schemas import ErrorCode, ErrorDetail, ErrorResponse

REQUEST_ID_KEY = "querymate.request_id"
MAX_BODY_BYTES = 131_072  # 128 KiB: covers 20,000 characters in the worst case (contract)

NO_STORE_HEADERS = {"Cache-Control": "no-store"}

MESSAGES: dict[ErrorCode, str] = {
    "not_found": "The requested resource was not found.",
    "method_not_allowed": "This method is not allowed for this resource.",
    "payload_too_large": "The request is too large. The limit is 128 KiB.",
    "unsupported_media_type": "Please send the request as application/json.",
    "invalid_request": (
        "The request could not be processed. Please send a JSON body with a text "
        '"question" field.'
    ),
    # 06_UI_UX_Design §4 service-error wording.
    "internal_error": (
        "Sorry, the assistant is temporarily unavailable. Please try again later. "
        "If this is urgent, contact emergency services or a healthcare professional."
    ),
}

_STATUS: dict[ErrorCode, int] = {
    "not_found": 404,
    "method_not_allowed": 405,
    "payload_too_large": 413,
    "unsupported_media_type": 415,
    "invalid_request": 422,
    "internal_error": 500,
}


def error_body(code: ErrorCode, request_id: str) -> dict:
    return ErrorResponse(
        error=ErrorDetail(code=code, message=MESSAGES[code], request_id=request_id)
    ).model_dump()


def error_response(code: ErrorCode, request_id: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(
        error_body(code, request_id),
        status_code=_STATUS[code],
        headers={**NO_STORE_HEADERS, "X-Request-ID": request_id, **(headers or {})},
    )


def request_id_of(request: Request) -> str:
    return request.scope[REQUEST_ID_KEY]


async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Never include exc.errors() or exc.body: both contain the submitted input.
    return error_response("invalid_request", request_id_of(request))


async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return error_response("not_found", request_id_of(request))
    if exc.status_code == 405:
        allow = (exc.headers or {}).get("Allow")
        return error_response(
            "method_not_allowed", request_id_of(request), {"Allow": allow} if allow else None
        )
    if exc.status_code < 500:
        # Includes FastAPI's 400 "error parsing the body" (e.g. invalid UTF-8): malformed request.
        return error_response("invalid_request", request_id_of(request))
    return error_response("internal_error", request_id_of(request))


def install_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
